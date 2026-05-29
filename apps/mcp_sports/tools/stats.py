"""Tools: get_team_stats and get_player_stats."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope

_SEASON_STATS_TTL = 6 * 3600  # 6 hours


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_team_stats(
        sport: str,
        team_id: str,
        season: str | None = None,
    ) -> dict:
        """Retrieve team statistics and recent form for a season.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``.
            team_id: Namespaced team ID (``"<provider>:<id>"``).
            season: Optional season identifier, e.g. ``"2024"`` or ``"2024-2025"``.

        Returns:
            ToolEnvelope with ``data`` as a TeamStats object (or ``null`` if unavailable).
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        stats, provider, partial = await registry.get_team_stats(sport_enum, team_id, season)
        data = stats.model_dump(mode="json") if stats else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_team_stats",
            url=None,
            ttl_seconds=_SEASON_STATS_TTL,
            partial=partial,
            notes=None if stats else "No team stats available from any provider",
        )

    @mcp.tool()
    async def get_player_stats(
        sport: str,
        player_id: str,
        season: str | None = None,
    ) -> dict:
        """Retrieve player statistics for a season.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``.
            player_id: Namespaced player ID (``"<provider>:<id>"``).
            season: Optional season identifier, e.g. ``"2024"``.

        Returns:
            ToolEnvelope with ``data`` as a PlayerStats object (or ``null`` if unavailable).
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        stats, provider, partial = await registry.get_player_stats(sport_enum, player_id, season)
        data = stats.model_dump(mode="json") if stats else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_player_stats",
            url=None,
            ttl_seconds=_SEASON_STATS_TTL,
            partial=partial,
            notes=None if stats else "No player stats available from any provider",
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
