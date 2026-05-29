"""API-Football / API-Sports provider adapter.

Requires env var ``APISPORTS_KEY``.  No-ops gracefully when key is absent.

Base URL: https://v3.football.api-sports.io
Headers:  x-apisports-key: <key>   OR   x-rapidapi-key: <key>

Key endpoints:
    Fixtures:   GET /fixtures?league={id}&season={year}&team={id}&date={YYYY-MM-DD}
    H2H:        GET /fixtures/headtohead?h2h={team_a_id}-{team_b_id}
    Standings:  GET /standings?league={id}&season={year}
    Injuries:   GET /injuries?league={id}&season={year}&team={id}
    Odds:       GET /odds?fixture={id}
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
    StandingRow,
    Standings,
    Team,
    TeamStats,
)

from core.httpclient import SportHttpClient
from core.normalize import (
    coerce_fixture_status,
    implied_prob,
    make_id,
    parse_dt,
    safe_float,
    safe_int,
)
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PROVIDER = "apisports"
_BASE = "https://v3.football.api-sports.io"


def _strip_prefix(tid: str) -> str:
    if ":" in tid:
        return tid.split(":", 1)[1]
    return tid


class APISportsProvider(BaseProvider):
    """API-Football (api-sports.io) adapter — soccer-focused."""

    name = PROVIDER

    def __init__(self) -> None:
        self._key = os.environ.get("APISPORTS_KEY", "")
        self._http = SportHttpClient(
            provider_name=PROVIDER,
            base_url=_BASE,
            rate_per_second=1.0,  # free tier: 100 req/day → be conservative
            cache_ttl=300,
            cache_maxsize=256,
            extra_headers=(
                {"x-apisports-key": self._key} if self._key else {}
            ),
        )

    @property
    def is_available(self) -> bool:
        return bool(self._key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _team_from_raw(self, raw: dict[str, Any], sport: Sport = Sport.SOCCER) -> Team:
        return Team(
            id=make_id(PROVIDER, raw.get("id", "?")),
            name=raw.get("name", ""),
            short_name=raw.get("code"),
            sport=sport,
            country=raw.get("country"),
            logo_url=raw.get("logo"),
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("id", "?"))},
        )

    def _fixture_from_raw(self, raw: dict[str, Any]) -> Fixture:
        fix_data = raw.get("fixture", {})
        teams = raw.get("teams", {})
        goals = raw.get("goals", {})
        league_data = raw.get("league", {})

        eid = str(fix_data.get("id", "?"))
        status_raw = fix_data.get("status", {}).get("short", "")
        status = coerce_fixture_status(status_raw)
        start_time = parse_dt(fix_data.get("date"))

        home_raw = teams.get("home", {})
        away_raw = teams.get("away", {})

        home_team = self._team_from_raw(home_raw) if home_raw else None
        away_team = self._team_from_raw(away_raw) if away_raw else None

        return Fixture(
            id=make_id(PROVIDER, eid),
            sport=Sport.SOCCER,
            league=league_data.get("name"),
            season=str(league_data.get("season", "")) or None,
            status=status,
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            home_score=safe_int(goals.get("home")),
            away_score=safe_int(goals.get("away")),
            venue=fix_data.get("venue", {}).get("name"),
            round=league_data.get("round"),
            provider=PROVIDER,
            provider_ids={PROVIDER: eid},
        )

    # ------------------------------------------------------------------
    # Entity search (not natively supported — return empty)
    # ------------------------------------------------------------------

    async def search_teams(self, query: str, sport: Sport | None = None) -> list[Team]:
        if not self.is_available:
            return []
        try:
            data = await self._http.get_json("/teams", {"search": query})
            teams = [
                self._team_from_raw(r.get("team", {}))
                for r in (data.get("response") or [])
            ]
            return teams
        except Exception as exc:
            logger.warning("[apisports] search_teams error: %s", exc)
            return []

    async def search_players(self, query: str, sport: Sport | None = None) -> list[Player]:
        return []

    # ------------------------------------------------------------------
    # Fixtures
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
        if not self.is_available or sport != Sport.SOCCER:
            return []
        params: dict[str, Any] = {}
        if league_id:
            params["league"] = _strip_prefix(league_id)
        if team_id:
            params["team"] = _strip_prefix(team_id)
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        if not params:
            return []
        try:
            data = await self._http.get_json("/fixtures", params)
            fixtures = [self._fixture_from_raw(r) for r in (data.get("response") or [])]
            if status:
                fixtures = [f for f in fixtures if f.status == status]
            return fixtures
        except Exception as exc:
            logger.warning("[apisports] get_fixtures error: %s", exc)
            return []

    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> list[Fixture]:
        if not self.is_available or sport != Sport.SOCCER:
            return []
        params: dict[str, Any] = {"live": "all"}
        if league_id:
            params["league"] = _strip_prefix(league_id)
        try:
            data = await self._http.get_json("/fixtures", params, use_cache=False)
            return [self._fixture_from_raw(r) for r in (data.get("response") or [])]
        except Exception as exc:
            logger.warning("[apisports] get_live_scores error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> TeamStats | None:
        if not self.is_available or sport != Sport.SOCCER:
            return None
        raw_tid = _strip_prefix(team_id)
        params: dict[str, Any] = {"team": raw_tid}
        if season:
            params["season"] = season
        try:
            data = await self._http.get_json("/teams/statistics", params)
            resp = (data.get("response") or {})
            if not resp:
                return None
            fixtures_data = resp.get("fixtures", {})
            goals_data = resp.get("goals", {})
            form_raw = resp.get("form", "")
            return TeamStats(
                team_id=make_id(PROVIDER, raw_tid),
                sport=Sport.SOCCER,
                season=season,
                form=form_raw or None,
                home_record={
                    "wins": safe_int(fixtures_data.get("wins", {}).get("home")) or 0,
                    "draws": safe_int(fixtures_data.get("draws", {}).get("home")) or 0,
                    "losses": safe_int(fixtures_data.get("loses", {}).get("home")) or 0,
                },
                away_record={
                    "wins": safe_int(fixtures_data.get("wins", {}).get("away")) or 0,
                    "draws": safe_int(fixtures_data.get("draws", {}).get("away")) or 0,
                    "losses": safe_int(fixtures_data.get("loses", {}).get("away")) or 0,
                },
                points_for=safe_float(
                    goals_data.get("for", {}).get("average", {}).get("total")
                ),
                points_against=safe_float(
                    goals_data.get("against", {}).get("average", {}).get("total")
                ),
                extra=resp,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[apisports] get_team_stats error: %s", exc)
            return None

    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> PlayerStats | None:
        if not self.is_available:
            return None
        raw_pid = _strip_prefix(player_id)
        params: dict[str, Any] = {"id": raw_pid}
        if season:
            params["season"] = season
        try:
            data = await self._http.get_json("/players", params)
            entries = data.get("response") or []
            if not entries:
                return None
            entry = entries[0]
            stats_list = entry.get("statistics") or []
            stats_combined: dict[str, Any] = {}
            for stat_block in stats_list:
                stats_combined.update(stat_block)
            return PlayerStats(
                player_id=make_id(PROVIDER, raw_pid),
                sport=Sport.SOCCER,
                season=season,
                stats=stats_combined,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[apisports] get_player_stats error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> Standings | None:
        if not self.is_available or sport != Sport.SOCCER:
            return None
        params: dict[str, Any] = {"league": _strip_prefix(league_id)}
        if season:
            params["season"] = season
        try:
            data = await self._http.get_json("/standings", params)
            response = data.get("response") or []
            if not response:
                return None
            league_data = response[0].get("league", {})
            all_rows: list[StandingRow] = []
            for group in league_data.get("standings", []):
                for entry in group:
                    team_raw = entry.get("team", {})
                    team = self._team_from_raw(team_raw)
                    all_desc = entry.get("all", {})
                    all_rows.append(
                        StandingRow(
                            rank=safe_int(entry.get("rank")) or 0,
                            team=team,
                            played=safe_int(all_desc.get("played")),
                            won=safe_int(all_desc.get("win")),
                            drawn=safe_int(all_desc.get("draw")),
                            lost=safe_int(all_desc.get("lose")),
                            points=safe_int(entry.get("points")),
                            goals_for=safe_int(all_desc.get("goals", {}).get("for")),
                            goals_against=safe_int(
                                all_desc.get("goals", {}).get("against")
                            ),
                            form=entry.get("form"),
                        )
                    )
            return Standings(
                sport=sport,
                league=league_id,
                season=season,
                rows=all_rows,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[apisports] get_standings error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Head-to-head
    # ------------------------------------------------------------------

    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> HeadToHead | None:
        if not self.is_available or sport != Sport.SOCCER:
            return None
        raw_a = _strip_prefix(team_a)
        raw_b = _strip_prefix(team_b)
        try:
            data = await self._http.get_json(
                "/fixtures/headtohead",
                {"h2h": f"{raw_a}-{raw_b}", "last": limit},
            )
            fixtures = [self._fixture_from_raw(r) for r in (data.get("response") or [])]
            return HeadToHead(
                team_a=make_id(PROVIDER, raw_a),
                team_b=make_id(PROVIDER, raw_b),
                fixtures=fixtures,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[apisports] get_head_to_head error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Injuries
    # ------------------------------------------------------------------

    async def get_injuries(self, sport: Sport, team_id: str) -> list[Injury]:
        if not self.is_available or sport != Sport.SOCCER:
            return []
        raw_tid = _strip_prefix(team_id)
        try:
            data = await self._http.get_json("/injuries", {"team": raw_tid})
            injuries: list[Injury] = []
            for r in data.get("response") or []:
                player_data = r.get("player", {})
                injuries.append(
                    Injury(
                        player_name=player_data.get("name", "Unknown"),
                        team_id=make_id(PROVIDER, raw_tid),
                        status=r.get("player", {}).get("reason"),
                        reason=r.get("player", {}).get("type"),
                        provider=PROVIDER,
                    )
                )
            return injuries
        except Exception as exc:
            logger.warning("[apisports] get_injuries error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Odds
    # ------------------------------------------------------------------

    async def get_odds(self, sport: Sport, fixture_id: str) -> list[Odds]:
        if not self.is_available or sport != Sport.SOCCER:
            return []
        raw_fid = _strip_prefix(fixture_id)
        try:
            data = await self._http.get_json("/odds", {"fixture": raw_fid})
            all_odds: list[Odds] = []
            for r in data.get("response") or []:
                bookmaker = r.get("bookmakers", [{}])[0] if r.get("bookmakers") else {}
                bm_name = bookmaker.get("name")
                for bet in bookmaker.get("bets") or []:
                    if bet.get("name") != "Match Winner":
                        continue
                    values = {v["value"]: safe_float(v["odd"]) for v in bet.get("values", [])}
                    home_w = values.get("Home")
                    draw = values.get("Draw")
                    away_w = values.get("Away")
                    all_odds.append(
                        Odds(
                            fixture_id=make_id(PROVIDER, raw_fid),
                            bookmaker=bm_name,
                            home_win=home_w,
                            draw=draw,
                            away_win=away_w,
                            implied_home=implied_prob(home_w),
                            implied_draw=implied_prob(draw),
                            implied_away=implied_prob(away_w),
                            provider=PROVIDER,
                        )
                    )
            return all_odds
        except Exception as exc:
            logger.warning("[apisports] get_odds error: %s", exc)
            return []
