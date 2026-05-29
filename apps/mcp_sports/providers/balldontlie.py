"""BallDontLie API provider adapter — NBA only.

Requires env var ``BALLDONTLIE_KEY``.  No-ops gracefully when key is absent.

Base URL: https://api.balldontlie.io
Headers:  Authorization: <key>

Key endpoints (v1):
    Teams:          GET /v1/teams
    Players:        GET /v1/players?search={name}
    Games:          GET /v1/games?team_ids[]={id}&dates[]={YYYY-MM-DD}
    Stats:          GET /v1/stats?player_ids[]={id}&seasons[]={year}
    Season avgs:    GET /v1/season_averages?player_ids[]={id}&season={year}
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sports_oracle_shared.enums import FixtureStatus, Sport
from sports_oracle_shared.sports import (
    Fixture,
    HeadToHead,
    Injury,
    Odds,
    Player,
    PlayerStats,
    Standings,
    Team,
    TeamStats,
)

from core.httpclient import SportHttpClient
from core.normalize import coerce_fixture_status, make_id, parse_dt, safe_float, safe_int
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PROVIDER = "balldontlie"
_BASE = "https://api.balldontlie.io"


def _strip_prefix(tid: str) -> str:
    if ":" in tid:
        return tid.split(":", 1)[1]
    return tid


class BallDontLieProvider(BaseProvider):
    """BallDontLie NBA data provider."""

    name = PROVIDER

    def __init__(self) -> None:
        self._key = os.environ.get("BALLDONTLIE_KEY", "")
        self._http = SportHttpClient(
            provider_name=PROVIDER,
            base_url=_BASE,
            rate_per_second=1.0,
            cache_ttl=300,
            cache_maxsize=256,
            extra_headers=({"Authorization": self._key} if self._key else {}),
        )

    @property
    def is_available(self) -> bool:
        return bool(self._key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _team_from_raw(self, raw: dict[str, Any]) -> Team:
        return Team(
            id=make_id(PROVIDER, raw.get("id", "?")),
            name=raw.get("full_name") or raw.get("name", ""),
            short_name=raw.get("abbreviation"),
            sport=Sport.BASKETBALL,
            country="USA",
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("id", "?"))},
        )

    def _player_from_raw(self, raw: dict[str, Any]) -> Player:
        team_raw = raw.get("team") or {}
        return Player(
            id=make_id(PROVIDER, raw.get("id", "?")),
            name=f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip(),
            sport=Sport.BASKETBALL,
            team_id=make_id(PROVIDER, team_raw["id"]) if team_raw.get("id") else None,
            team_name=team_raw.get("full_name") or team_raw.get("name"),
            position=raw.get("position"),
            nationality=None,
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("id", "?"))},
        )

    def _game_to_fixture(self, raw: dict[str, Any]) -> Fixture:
        gid = str(raw.get("id", "?"))
        status_raw = raw.get("status", "")
        # BallDontLie uses "Final", "In Progress", "YYYY-MM-DDTHH:MM:SS.000Z" for scheduled
        if status_raw.startswith("20") or status_raw[0:1].isdigit():
            status = FixtureStatus.SCHEDULED
        else:
            status = coerce_fixture_status(status_raw)

        home_raw = raw.get("home_team", {})
        away_raw = raw.get("visitor_team", {})
        home_team = self._team_from_raw(home_raw) if home_raw else None
        away_team = self._team_from_raw(away_raw) if away_raw else None

        # date field is YYYY-MM-DD
        start_time = parse_dt(raw.get("date"))

        return Fixture(
            id=make_id(PROVIDER, gid),
            sport=Sport.BASKETBALL,
            league="NBA",
            season=str(raw.get("season", "")) or None,
            status=status,
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            home_score=safe_int(raw.get("home_team_score")),
            away_score=safe_int(raw.get("visitor_team_score")),
            provider=PROVIDER,
            provider_ids={PROVIDER: gid},
        )

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    async def search_teams(self, query: str, sport: Sport | None = None) -> list[Team]:
        if not self.is_available:
            return []
        if sport and sport != Sport.BASKETBALL:
            return []
        try:
            data = await self._http.get_json("/v1/teams")
            teams = [self._team_from_raw(t) for t in (data.get("data") or [])]
            q = query.lower()
            return [t for t in teams if q in t.name.lower() or q in (t.short_name or "").lower()]
        except Exception as exc:
            logger.warning("[balldontlie] search_teams error: %s", exc)
            return []

    async def search_players(self, query: str, sport: Sport | None = None) -> list[Player]:
        if not self.is_available:
            return []
        if sport and sport != Sport.BASKETBALL:
            return []
        try:
            data = await self._http.get_json("/v1/players", {"search": query, "per_page": 25})
            return [self._player_from_raw(p) for p in (data.get("data") or [])]
        except Exception as exc:
            logger.warning("[balldontlie] search_players error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Fixtures / scores
    # ------------------------------------------------------------------

    async def get_fixtures(
        self,
        sport: Sport,
        *,
        team_id: str | None = None,
        league_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: FixtureStatus | None = None,
    ) -> list[Fixture]:
        if not self.is_available or sport != Sport.BASKETBALL:
            return []
        params: dict[str, Any] = {"per_page": 25}
        if team_id:
            params["team_ids[]"] = _strip_prefix(team_id)
        if date_from:
            params["start_date"] = date_from
        if date_to:
            params["end_date"] = date_to
        try:
            data = await self._http.get_json("/v1/games", params)
            fixtures = [self._game_to_fixture(g) for g in (data.get("data") or [])]
            if status:
                fixtures = [f for f in fixtures if f.status == status]
            return fixtures
        except Exception as exc:
            logger.warning("[balldontlie] get_fixtures error: %s", exc)
            return []

    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> list[Fixture]:
        if not self.is_available or sport != Sport.BASKETBALL:
            return []
        try:
            data = await self._http.get_json("/v1/games/live", use_cache=False)
            return [self._game_to_fixture(g) for g in (data.get("data") or [])]
        except Exception as exc:
            logger.warning("[balldontlie] get_live_scores error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> TeamStats | None:
        return None  # not directly available; would require aggregating game data

    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> PlayerStats | None:
        if not self.is_available or sport != Sport.BASKETBALL:
            return None
        raw_pid = _strip_prefix(player_id)
        params: dict[str, Any] = {"player_ids[]": raw_pid}
        if season:
            params["season"] = season
        try:
            data = await self._http.get_json("/v1/season_averages", params)
            entries = data.get("data") or []
            if not entries:
                return None
            stats = entries[0]
            return PlayerStats(
                player_id=make_id(PROVIDER, raw_pid),
                sport=Sport.BASKETBALL,
                season=str(stats.get("season", season or "")),
                stats={
                    "pts": safe_float(stats.get("pts")),
                    "ast": safe_float(stats.get("ast")),
                    "reb": safe_float(stats.get("reb")),
                    "stl": safe_float(stats.get("stl")),
                    "blk": safe_float(stats.get("blk")),
                    "fg_pct": safe_float(stats.get("fg_pct")),
                    "fg3_pct": safe_float(stats.get("fg3_pct")),
                    "ft_pct": safe_float(stats.get("ft_pct")),
                    "min": stats.get("min"),
                    "games_played": safe_int(stats.get("games_played")),
                    "turnover": safe_float(stats.get("turnover")),
                },
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[balldontlie] get_player_stats error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> Standings | None:
        return None  # not available in v1 free tier

    # ------------------------------------------------------------------
    # Head-to-head, injuries, odds
    # ------------------------------------------------------------------

    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> HeadToHead | None:
        if not self.is_available or sport != Sport.BASKETBALL:
            return None
        raw_a = _strip_prefix(team_a)
        raw_b = _strip_prefix(team_b)
        try:
            # Fetch recent games involving team_a and filter for matchups vs team_b
            data = await self._http.get_json(
                "/v1/games",
                {"team_ids[]": raw_a, "per_page": 50},
            )
            fixtures: list[Fixture] = []
            for g in data.get("data") or []:
                home_id = str(g.get("home_team", {}).get("id", ""))
                away_id = str(g.get("visitor_team", {}).get("id", ""))
                if raw_b in (home_id, away_id):
                    fixtures.append(self._game_to_fixture(g))
                if len(fixtures) >= limit:
                    break
            return HeadToHead(
                team_a=make_id(PROVIDER, raw_a),
                team_b=make_id(PROVIDER, raw_b),
                fixtures=fixtures,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[balldontlie] get_head_to_head error: %s", exc)
            return None

    async def get_injuries(self, sport: Sport, team_id: str) -> list[Injury]:
        return []

    async def get_odds(self, sport: Sport, fixture_id: str) -> list[Odds]:
        return []
