"""Tool: get_head_to_head."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_head_to_head(
        sport: str,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> dict:
        """Retrieve head-to-head fixture history between two teams.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``.
            team_a: Namespaced ID of the first team (``"<provider>:<id>"``).
            team_b: Namespaced ID of the second team (``"<provider>:<id>"``).
            limit: Maximum number of past fixtures to return (default 10).

        Returns:
            ToolEnvelope with ``data`` as a HeadToHead object.
            ``data`` may be ``null`` when no provider supports H2H for this sport.
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        h2h, provider, partial = await registry.get_head_to_head(
            sport_enum, team_a, team_b, limit
        )
        data = h2h.model_dump(mode="json") if h2h else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_head_to_head",
            url=None,
            ttl_seconds=3600,
            partial=partial,
            notes=None if h2h else "H2H not available for this sport/provider combination",
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
