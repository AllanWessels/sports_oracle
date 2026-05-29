"""Tool: get_standings."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_standings(
        sport: str,
        league_id: str,
        season: str | None = None,
    ) -> dict:
        """Retrieve the standings table for a league.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``.
            league_id: League/competition ID (provider-namespaced or raw slug, e.g.
                       ``"eng.1"`` for Premier League via ESPN).
            season: Optional season identifier, e.g. ``"2024"`` or ``"2024-2025"``.

        Returns:
            ToolEnvelope with ``data`` as a Standings object (or ``null``).
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        standings, provider, partial = await registry.get_standings(
            sport_enum, league_id, season
        )
        data = standings.model_dump(mode="json") if standings else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_standings",
            url=None,
            ttl_seconds=900,
            partial=partial,
            notes=None if standings else "No standings available from any provider",
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
