"""Provider registry — maps Sport → ordered provider chain with fallback.

Each method tries providers in order and returns the first non-empty result.
Providers that are unavailable (missing API key) are silently skipped.
On error or empty result, the next provider in the chain is tried.
"""

from __future__ import annotations

import logging
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

from providers.apisports import APISportsProvider
from providers.balldontlie import BallDontLieProvider
from providers.base import BaseProvider
from providers.espn import ESPNProvider
from providers.thesportsdb import TheSportsDBProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Singleton-style registry.  Instantiate once at server startup."""

    def __init__(self) -> None:
        self._espn = ESPNProvider()
        self._tsdb = TheSportsDBProvider()
        self._apisports = APISportsProvider()
        self._bdl = BallDontLieProvider()

        # Ordered chains per capability.  The first provider to return a
        # non-empty/non-None result wins.
        self._all: list[BaseProvider] = [
            self._espn,
            self._tsdb,
            self._apisports,
            self._bdl,
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _available(self, providers: list[BaseProvider]) -> list[BaseProvider]:
        return [p for p in providers if p.is_available]

    async def _first_list(
        self,
        providers: list[BaseProvider],
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[list[Any], str, bool]:
        """Try each provider; return (result, provider_name, partial)."""
        tried: list[str] = []
        for p in self._available(providers):
            try:
                result = await getattr(p, method)(*args, **kwargs)
                if result:
                    partial = bool(tried)
                    return result, p.name, partial
                tried.append(p.name)
            except Exception as exc:
                logger.warning("[registry] %s.%s failed: %s", p.name, method, exc)
                tried.append(p.name)
        return [], "none", bool(tried)

    async def _first_obj(
        self,
        providers: list[BaseProvider],
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any | None, str, bool]:
        """Like _first_list but for single-object returns."""
        tried: list[str] = []
        for p in self._available(providers):
            try:
                result = await getattr(p, method)(*args, **kwargs)
                if result is not None:
                    partial = bool(tried)
                    return result, p.name, partial
                tried.append(p.name)
            except Exception as exc:
                logger.warning("[registry] %s.%s failed: %s", p.name, method, exc)
                tried.append(p.name)
        return None, "none", bool(tried)

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    async def search_teams(
        self, query: str, sport: Sport | None = None
    ) -> tuple[list[Team], str, bool]:
        chain = self._all
        return await self._first_list(chain, "search_teams", query, sport)

    async def search_players(
        self, query: str, sport: Sport | None = None
    ) -> tuple[list[Player], str, bool]:
        chain = self._all
        return await self._first_list(chain, "search_players", query, sport)

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    def _fixture_chain(self, sport: Sport) -> list[BaseProvider]:
        if sport == Sport.BASKETBALL:
            return [self._espn, self._bdl]
        if sport == Sport.SOCCER:
            return [self._espn, self._apisports, self._tsdb]
        return [self._espn, self._tsdb]

    async def get_fixtures(
        self,
        sport: Sport,
        *,
        team_id: str | None = None,
        league_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: FixtureStatus | None = None,
    ) -> tuple[list[Fixture], str, bool]:
        return await self._first_list(
            self._fixture_chain(sport),
            "get_fixtures",
            sport,
            team_id=team_id,
            league_id=league_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )

    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> tuple[list[Fixture], str, bool]:
        return await self._first_list(
            self._fixture_chain(sport),
            "get_live_scores",
            sport,
            league_id=league_id,
            team_id=team_id,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _stats_chain(self, sport: Sport) -> list[BaseProvider]:
        if sport == Sport.SOCCER:
            return [self._apisports, self._espn]
        if sport == Sport.BASKETBALL:
            return [self._bdl, self._espn]
        return [self._espn]

    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> tuple[TeamStats | None, str, bool]:
        return await self._first_obj(
            self._stats_chain(sport),
            "get_team_stats",
            sport,
            team_id,
            season,
        )

    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> tuple[PlayerStats | None, str, bool]:
        return await self._first_obj(
            self._stats_chain(sport),
            "get_player_stats",
            sport,
            player_id,
            season,
        )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> tuple[Standings | None, str, bool]:
        if sport == Sport.SOCCER:
            chain = [self._apisports, self._espn, self._tsdb]
        else:
            chain = [self._espn, self._tsdb]
        return await self._first_obj(chain, "get_standings", sport, league_id, season)

    # ------------------------------------------------------------------
    # Head-to-head
    # ------------------------------------------------------------------

    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> tuple[HeadToHead | None, str, bool]:
        if sport == Sport.SOCCER:
            chain = [self._apisports]
        elif sport == Sport.BASKETBALL:
            chain = [self._bdl]
        else:
            chain = []
        return await self._first_obj(chain, "get_head_to_head", sport, team_a, team_b, limit)

    # ------------------------------------------------------------------
    # Injuries
    # ------------------------------------------------------------------

    async def get_injuries(
        self, sport: Sport, team_id: str
    ) -> tuple[list[Injury], str, bool]:
        chain = [self._apisports, self._espn] if sport == Sport.SOCCER else [self._espn]
        return await self._first_list(chain, "get_injuries", sport, team_id)

    # ------------------------------------------------------------------
    # Odds
    # ------------------------------------------------------------------

    async def get_odds(
        self, sport: Sport, fixture_id: str
    ) -> tuple[list[Odds], str, bool]:
        chain = [self._apisports]
        return await self._first_list(chain, "get_odds", sport, fixture_id)


# Singleton instance (created lazily at first import)
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
