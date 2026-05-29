"""Tools: get_fixtures and get_live_scores."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sports_oracle_shared.enums import FixtureStatus, Sport

from core.registry import get_registry
from tools._helpers import make_envelope


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_fixtures(
        sport: str,
        team_id: str | None = None,
        league_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Retrieve fixtures (scheduled or historical games) for a sport.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``, ``"american_football"``.
            team_id: Optional namespaced team ID (``"<provider>:<id>"``).
            league_id: Optional league/competition ID.
            date_from: Optional ISO date string ``"YYYY-MM-DD"`` (inclusive start).
            date_to:   Optional ISO date string ``"YYYY-MM-DD"`` (inclusive end).
            status: Optional status filter: ``"scheduled"``, ``"live"``, ``"finished"``.

        Returns:
            ToolEnvelope with ``data`` as a list of Fixture objects.
        """
        sport_enum = _parse_sport(sport)
        status_enum: FixtureStatus | None = None
        if status:
            import contextlib

            with contextlib.suppress(ValueError):
                status_enum = FixtureStatus(status.lower())

        registry = get_registry()
        fixtures, provider, partial = await registry.get_fixtures(
            sport_enum,
            team_id=team_id,
            league_id=league_id,
            date_from=date_from,
            date_to=date_to,
            status=status_enum,
        )
        data = [f.model_dump(mode="json") for f in fixtures]
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_fixtures",
            url=None,
            ttl_seconds=300,
            partial=partial,
            notes=f"{len(fixtures)} fixture(s) for sport={sport}",
        )

    @mcp.tool()
    async def get_live_scores(
        sport: str,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> dict:
        """Return currently live scores for a sport.

        Args:
            sport: Sport identifier, e.g. ``"soccer"``, ``"basketball"``.
            league_id: Optional league/competition filter.
            team_id: Optional team filter.

        Returns:
            ToolEnvelope with ``data`` as a list of live Fixture objects.
            TTL is 30 seconds — callers should re-fetch frequently.
        """
        sport_enum = _parse_sport(sport)
        registry = get_registry()
        fixtures, provider, partial = await registry.get_live_scores(
            sport_enum, league_id=league_id, team_id=team_id
        )
        data = [f.model_dump(mode="json") for f in fixtures]
        return make_envelope(
            data=data,
            provider=provider,
            endpoint="get_live_scores",
            url=None,
            ttl_seconds=30,
            partial=partial,
            notes=f"{len(fixtures)} live game(s)",
        )


def _parse_sport(sport: str) -> Sport:
    try:
        return Sport(sport.lower())
    except ValueError:
        return Sport.UNKNOWN
