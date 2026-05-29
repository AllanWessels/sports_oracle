"""Abstract base class / protocol defining the provider interface.

Every provider MUST implement all methods.  Methods that the provider cannot
satisfy (e.g. because the upstream API doesn't have the data, or a required
API key is absent) should return ``None`` or an empty list rather than raising.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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


class BaseProvider(ABC):
    """Abstract provider.  All methods are async."""

    #: Short lowercase identifier, e.g. ``"espn"``.
    name: str

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return ``False`` when a required API key is missing."""
        ...

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    @abstractmethod
    async def search_teams(self, query: str, sport: Sport | None = None) -> list[Team]:
        """Search for teams matching *query*."""
        ...

    @abstractmethod
    async def search_players(self, query: str, sport: Sport | None = None) -> list[Player]:
        """Search for players matching *query*."""
        ...

    # ------------------------------------------------------------------
    # Fixtures / scores
    # ------------------------------------------------------------------

    @abstractmethod
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
        """Return fixtures matching the given filters."""
        ...

    @abstractmethod
    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> list[Fixture]:
        """Return currently live fixtures."""
        ...

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> TeamStats | None:
        """Return stats/form for a team."""
        ...

    @abstractmethod
    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> PlayerStats | None:
        """Return stats for a player."""
        ...

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> Standings | None:
        """Return standings for a league."""
        ...

    # ------------------------------------------------------------------
    # Head-to-head
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> HeadToHead | None:
        """Return head-to-head history between two teams."""
        ...

    # ------------------------------------------------------------------
    # Supplementary
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_injuries(self, sport: Sport, team_id: str) -> list[Injury]:
        """Return current injuries for a team."""
        ...

    @abstractmethod
    async def get_odds(self, sport: Sport, fixture_id: str) -> list[Odds]:
        """Return odds for a fixture."""
        ...

    # ------------------------------------------------------------------
    # Optional: raw entity fetch used by registry helpers
    # ------------------------------------------------------------------

    async def get_team(self, sport: Sport, team_id: str) -> Team | None:  # noqa: ARG002
        """Return a single team by provider-namespaced *team_id* if supported."""
        return None

    async def get_extra(self, key: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Hook for provider-specific capabilities not covered by the protocol."""
        return None
