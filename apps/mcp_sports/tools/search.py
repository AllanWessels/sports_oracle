"""Tool: search_entities — search for teams or players across providers."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_entities(
        query: str,
        kind: Literal["team", "player"],
        sport: str | None = None,
    ) -> dict:
        """Search for teams or players by name.

        Args:
            query: The search term (team or player name).
            kind: Either ``"team"`` or ``"player"``.
            sport: Optional sport filter (e.g. ``"soccer"``, ``"basketball"``).
                   If omitted, all sports are searched.

        Returns:
            ToolEnvelope with ``data`` as a list of Team or Player objects.
        """
        sport_enum: Sport | None = None
        if sport:
            try:
                sport_enum = Sport(sport.lower())
            except ValueError:
                sport_enum = None

        registry = get_registry()
        if kind == "team":
            results, provider, partial = await registry.search_teams(query, sport_enum)
        else:
            results, provider, partial = await registry.search_players(query, sport_enum)

        data = [r.model_dump(mode="json") for r in results]
        return make_envelope(
            data=data,
            provider=provider,
            endpoint=f"search_{kind}s",
            url=None,
            ttl_seconds=600,
            partial=partial,
            notes=f"Searched {len(results)} results for '{query}' (kind={kind})",
        )
