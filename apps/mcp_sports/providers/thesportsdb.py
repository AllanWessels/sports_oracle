"""TheSportsDB provider adapter.

Free tier key defaults to ``"3"`` (the public demo key).
Set env var ``THESPORTSDB_KEY`` to use a paid key.

Key endpoints used:
    Search teams:   /api/v1/json/{key}/searchteams.php?t={name}
    Search players: /api/v1/json/{key}/searchplayers.php?p={name}
    Team details:   /api/v1/json/{key}/lookupteam.php?id={id}
    Events today:   /api/v1/json/{key}/eventsnow.php   (paid only — skipped)
    Events by team: /api/v1/json/{key}/eventslast.php?id={team_id}
    League table:   /api/v1/json/{key}/lookuptable.php?l={league_id}&s={season}
"""

from __future__ import annotations

import logging
import os

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
    coerce_sport,
    make_id,
    parse_dt,
    safe_int,
)
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PROVIDER = "thesportsdb"
_BASE = "https://www.thesportsdb.com"


def _strip_prefix(tid: str) -> str:
    if ":" in tid:
        return tid.split(":", 1)[1]
    return tid


class TheSportsDBProvider(BaseProvider):
    """TheSportsDB free API adapter."""

    name = PROVIDER

    def __init__(self) -> None:
        self._key = os.environ.get("THESPORTSDB_KEY", "3")
        self._http = SportHttpClient(
            provider_name=PROVIDER,
            base_url=_BASE,
            rate_per_second=2.0,
            cache_ttl=300,
            cache_maxsize=512,
        )

    @property
    def is_available(self) -> bool:
        return True  # falls back to free key "3"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"/api/v1/json/{self._key}/{path}"

    def _team_from_raw(self, raw: dict) -> Team:
        sport = coerce_sport(raw.get("strSport"))
        return Team(
            id=make_id(PROVIDER, raw.get("idTeam", "?")),
            name=raw.get("strTeam", ""),
            short_name=raw.get("strTeamShort") or raw.get("strAlternate"),
            sport=sport,
            country=raw.get("strCountry"),
            logo_url=raw.get("strTeamBadge"),
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("idTeam", "?"))},
        )

    def _player_from_raw(self, raw: dict) -> Player:
        sport = coerce_sport(raw.get("strSport"))
        return Player(
            id=make_id(PROVIDER, raw.get("idPlayer", "?")),
            name=raw.get("strPlayer", ""),
            sport=sport,
            team_id=make_id(PROVIDER, raw.get("idTeam")) if raw.get("idTeam") else None,
            team_name=raw.get("strTeam"),
            position=raw.get("strPosition"),
            nationality=raw.get("strNationality"),
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("idPlayer", "?"))},
        )

    def _fixture_from_raw(self, raw: dict, sport: Sport) -> Fixture:
        status_raw = raw.get("strStatus", "")
        status = coerce_fixture_status(status_raw)

        home_team = None
        away_team = None
        if raw.get("idHomeTeam"):
            home_team = Team(
                id=make_id(PROVIDER, raw["idHomeTeam"]),
                name=raw.get("strHomeTeam", ""),
                sport=sport,
                provider=PROVIDER,
                provider_ids={PROVIDER: raw["idHomeTeam"]},
            )
        if raw.get("idAwayTeam"):
            away_team = Team(
                id=make_id(PROVIDER, raw["idAwayTeam"]),
                name=raw.get("strAwayTeam", ""),
                sport=sport,
                provider=PROVIDER,
                provider_ids={PROVIDER: raw["idAwayTeam"]},
            )

        start_str = raw.get("strTimestamp") or raw.get("dateEvent")
        start_time = parse_dt(start_str)

        return Fixture(
            id=make_id(PROVIDER, raw.get("idEvent", "?")),
            sport=sport,
            league=raw.get("strLeague"),
            season=raw.get("strSeason"),
            status=status,
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            home_score=safe_int(raw.get("intHomeScore")),
            away_score=safe_int(raw.get("intAwayScore")),
            venue=raw.get("strVenue"),
            round=raw.get("intRound"),
            provider=PROVIDER,
            provider_ids={PROVIDER: str(raw.get("idEvent", "?"))},
        )

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    async def search_teams(self, query: str, sport: Sport | None = None) -> list[Team]:
        try:
            data = await self._http.get_json(self._url("searchteams.php"), {"t": query})
            teams = data.get("teams") or []
            results = [self._team_from_raw(t) for t in teams]
            if sport:
                results = [t for t in results if t.sport == sport]
            return results
        except Exception as exc:
            logger.warning("[thesportsdb] search_teams error: %s", exc)
            return []

    async def search_players(self, query: str, sport: Sport | None = None) -> list[Player]:
        try:
            data = await self._http.get_json(self._url("searchplayers.php"), {"p": query})
            players = data.get("player") or []
            results = [self._player_from_raw(p) for p in players]
            if sport:
                results = [p for p in results if p.sport == sport]
            return results
        except Exception as exc:
            logger.warning("[thesportsdb] search_players error: %s", exc)
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
        if not team_id:
            return []
        raw_tid = _strip_prefix(team_id)
        try:
            data = await self._http.get_json(
                self._url("eventslast.php"), {"id": raw_tid}
            )
            events = data.get("results") or []
            fixtures = [self._fixture_from_raw(e, sport) for e in events]
            if status:
                fixtures = [f for f in fixtures if f.status == status]
            return fixtures
        except Exception as exc:
            logger.warning("[thesportsdb] get_fixtures error: %s", exc)
            return []

    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> list[Fixture]:
        """TheSportsDB free tier does not support live scores."""
        return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> TeamStats | None:
        return None  # not available in free tier

    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> PlayerStats | None:
        return None

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> Standings | None:
        raw_lid = _strip_prefix(league_id)
        params: dict = {"l": raw_lid}
        if season:
            params["s"] = season
        try:
            data = await self._http.get_json(self._url("lookuptable.php"), params)
            table = data.get("table") or []
            rows: list[StandingRow] = []
            for i, entry in enumerate(table, start=1):
                team = Team(
                    id=make_id(PROVIDER, entry.get("idTeam", i)),
                    name=entry.get("strTeam", ""),
                    sport=sport,
                    logo_url=entry.get("strTeamBadge"),
                    provider=PROVIDER,
                    provider_ids={PROVIDER: str(entry.get("idTeam", i))},
                )
                rows.append(
                    StandingRow(
                        rank=safe_int(entry.get("intRank")) or i,
                        team=team,
                        played=safe_int(entry.get("intPlayed")),
                        won=safe_int(entry.get("intWin")),
                        drawn=safe_int(entry.get("intDraw")),
                        lost=safe_int(entry.get("intLoss")),
                        points=safe_int(entry.get("intPoints")),
                        goals_for=safe_int(entry.get("intGoalsFor")),
                        goals_against=safe_int(entry.get("intGoalsAgainst")),
                        form=entry.get("strForm"),
                    )
                )
            return Standings(
                sport=sport,
                league=league_id,
                season=season,
                rows=rows,
                provider=PROVIDER,
            )
        except Exception as exc:
            logger.warning("[thesportsdb] get_standings error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Head-to-head, injuries, odds — not available
    # ------------------------------------------------------------------

    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> HeadToHead | None:
        return None

    async def get_injuries(self, sport: Sport, team_id: str) -> list[Injury]:
        return []

    async def get_odds(self, sport: Sport, fixture_id: str) -> list[Odds]:
        return []
