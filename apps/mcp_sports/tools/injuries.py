"""Tool: get_injuries."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_injuries(
        sport: str,
        team_id: str,
    ) -> dict:
        """Retrieve the current injury list for a team.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"american_football"``.
            team_id: Namespaced team ID (``"<provider>:<id>"``).

        Returns:
            ToolEnvelope with ``data`` as a list of Injury objects.
            ``data`` may be an empty list or ``null`` when no source is available —
            this is expected for sports/providers that don't expose injury data.
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        injuries, provider, partial = await registry.get_injuries(sport_enum, team_id)
        data = [i.model_dump(mode="json") for i in injuries] if injuries else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_injuries",
            url=None,
            ttl_seconds=600,
            partial=partial,
            notes=f"{len(injuries)} injury record(s)" if injuries else "No injury data available",
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
