"""Tool: get_odds."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_odds(
        sport: str,
        fixture_id: str,
    ) -> dict:
        """Retrieve betting odds for a fixture.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``.
            fixture_id: Namespaced fixture ID (``"<provider>:<id>"``).

        Returns:
            ToolEnvelope with ``data`` as a list of Odds objects.
            ``data`` will be ``null`` when no odds source is available —
            this is expected (odds require a paid API key).
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        odds_list, provider, partial = await registry.get_odds(sport_enum, fixture_id)
        data = [o.model_dump(mode="json") for o in odds_list] if odds_list else None
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_odds",
            url=None,
            ttl_seconds=60,
            partial=partial,
            notes=(
                f"{len(odds_list)} odds record(s)"
                if odds_list
                else "No odds available (set APISPORTS_KEY for odds data)"
            ),
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
