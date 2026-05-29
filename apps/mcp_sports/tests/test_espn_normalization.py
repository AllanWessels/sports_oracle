"""Unit tests for ESPN provider normalization logic.

Uses respx to mock httpx calls so no real network requests are made.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure app root is on path (also done in conftest, but be explicit)
_app_root = str(Path(__file__).parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

from sports_oracle_shared.enums import FixtureStatus, Sport
from sports_oracle_shared.sports import Fixture, Standings


class TestESPNScoreboardNormalization:
    """Test that ESPN scoreboard JSON → Fixture list works correctly."""

    def _load_scoreboard(self) -> dict:
        path = Path(__file__).parent / "fixtures" / "espn_scoreboard.json"
        return json.loads(path.read_text())

    def test_fixture_count(self, espn_scoreboard_json: dict) -> None:
        """Should produce one Fixture per event in the scoreboard."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        fixtures = [
            provider._make_fixture_from_event(e, Sport.SOCCER)
            for e in espn_scoreboard_json.get("events", [])
        ]
        assert len(fixtures) == 2

    def test_fixture_ids_are_namespaced(self, espn_scoreboard_json: dict) -> None:
        """Fixture IDs must be prefixed with 'espn:'."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.id.startswith("espn:")
        assert fix.id == "espn:663377"

    def test_finished_status_mapped(self, espn_scoreboard_json: dict) -> None:
        """State 'post' → FixtureStatus.FINISHED."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.status == FixtureStatus.FINISHED

    def test_live_status_mapped(self, espn_scoreboard_json: dict) -> None:
        """State 'in' → FixtureStatus.LIVE."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[1], Sport.SOCCER)
        assert fix.status == FixtureStatus.LIVE

    def test_scores_parsed(self, espn_scoreboard_json: dict) -> None:
        """Home and away scores are parsed as integers."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.home_score == 2
        assert fix.away_score == 1

    def test_teams_populated(self, espn_scoreboard_json: dict) -> None:
        """Home and away teams are populated with namespaced IDs."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.home_team is not None
        assert fix.away_team is not None
        assert fix.home_team.id == "espn:360"
        assert fix.away_team.id == "espn:382"
        assert fix.home_team.name == "Manchester United"
        assert fix.away_team.name == "Arsenal"

    def test_sport_preserved(self, espn_scoreboard_json: dict) -> None:
        """Sport enum value is carried through to the Fixture."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.sport == Sport.SOCCER

    def test_provider_set(self, espn_scoreboard_json: dict) -> None:
        """provider field must be 'espn'."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.provider == "espn"

    def test_venue_parsed(self, espn_scoreboard_json: dict) -> None:
        """Venue name should be extracted from competitions[0].venue."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert fix.venue == "Old Trafford"

    def test_fixture_is_pydantic_model(self, espn_scoreboard_json: dict) -> None:
        """Returned object should be a Fixture pydantic model."""
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        events = espn_scoreboard_json["events"]
        fix = provider._make_fixture_from_event(events[0], Sport.SOCCER)
        assert isinstance(fix, Fixture)


class TestESPNStandingsNormalization:
    """Test ESPN standings JSON → Standings object."""

    def test_standings_rows_count(self, espn_standings_json: dict) -> None:
        """Should parse all entries from the children structure."""
        from providers.espn import _parse_standings

        rows = _parse_standings(espn_standings_json, Sport.SOCCER)
        assert len(rows) == 2

    def test_standings_sorted_by_rank(self, espn_standings_json: dict) -> None:
        """Rows are sorted by rank ascending."""
        from providers.espn import _parse_standings

        rows = _parse_standings(espn_standings_json, Sport.SOCCER)
        ranks = [r.rank for r in rows]
        assert ranks == sorted(ranks)

    def test_standings_team_ids_namespaced(self, espn_standings_json: dict) -> None:
        """Team IDs in standings rows must be 'espn:' namespaced."""
        from providers.espn import _parse_standings

        rows = _parse_standings(espn_standings_json, Sport.SOCCER)
        for row in rows:
            assert row.team.id.startswith("espn:")

    def test_standings_points_parsed(self, espn_standings_json: dict) -> None:
        """Points field should be parsed as an integer."""
        from providers.espn import _parse_standings

        rows = _parse_standings(espn_standings_json, Sport.SOCCER)
        # Liverpool should have 68 points
        liverpool = next(r for r in rows if r.rank == 1)
        assert liverpool.points == 68


class TestESPNProviderAsync:
    """Async tests using respx to mock httpx."""

    @pytest.mark.asyncio
    async def test_get_fixtures_calls_scoreboard(
        self, espn_scoreboard_json: dict
    ) -> None:
        """get_fixtures should call the ESPN scoreboard endpoint and normalize results."""
        import respx
        import httpx
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"

        with respx.mock:
            respx.get(url).mock(
                return_value=httpx.Response(200, json=espn_scoreboard_json)
            )
            fixtures = await provider.get_fixtures(
                Sport.SOCCER, league_id="eng.1"
            )

        assert len(fixtures) == 2
        assert all(isinstance(f, Fixture) for f in fixtures)

    @pytest.mark.asyncio
    async def test_get_live_scores_filters_live(
        self, espn_scoreboard_json: dict
    ) -> None:
        """get_live_scores should only return fixtures with status=LIVE."""
        import respx
        import httpx
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        # Soccer uses all default leagues; mock all potential calls
        url_eng = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
        url_usa = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
        url_esp = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"
        url_ger = "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"
        url_ita = "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"
        url_fra = "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"

        empty = {"events": []}

        with respx.mock:
            respx.get(url_eng).mock(
                return_value=httpx.Response(200, json=espn_scoreboard_json)
            )
            for u in [url_usa, url_esp, url_ger, url_ita, url_fra]:
                respx.get(u).mock(return_value=httpx.Response(200, json=empty))

            live = await provider.get_live_scores(Sport.SOCCER)

        assert all(f.status == FixtureStatus.LIVE for f in live)
        assert len(live) == 1  # only the second event is live

    @pytest.mark.asyncio
    async def test_get_standings_normalizes_rows(
        self, espn_standings_json: dict
    ) -> None:
        """get_standings should return a Standings object with rows."""
        import respx
        import httpx
        from providers.espn import ESPNProvider

        provider = ESPNProvider()
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/standings"

        with respx.mock:
            respx.get(url).mock(
                return_value=httpx.Response(200, json=espn_standings_json)
            )
            standings = await provider.get_standings(Sport.SOCCER, "eng.1")

        assert isinstance(standings, Standings)
        assert len(standings.rows) == 2
        assert standings.provider == "espn"


class TestEnvelopeShape:
    """Tests verifying that tool helpers produce valid ToolEnvelope dicts."""

    def test_make_envelope_structure(self) -> None:
        """make_envelope should return a dict matching ToolEnvelope schema."""
        from tools._helpers import make_envelope

        env = make_envelope(
            data=[{"id": "espn:1", "name": "Arsenal"}],
            provider="espn",
            endpoint="get_fixtures",
            url="https://example.com",
            ttl_seconds=300,
            partial=False,
        )
        assert "data" in env
        assert "source" in env
        assert "ttl_seconds" in env
        assert "partial" in env
        assert env["ttl_seconds"] == 300
        assert env["partial"] is False
        assert env["source"]["provider"] == "espn"
        assert env["source"]["endpoint"] == "get_fixtures"
        assert "fetched_at" in env["source"]

    def test_make_envelope_partial_flag(self) -> None:
        """partial=True should be serialized correctly."""
        from tools._helpers import make_envelope

        env = make_envelope(
            data=None,
            provider="none",
            endpoint="test",
            url=None,
            ttl_seconds=60,
            partial=True,
            notes="fallback used",
        )
        assert env["partial"] is True
        assert env["notes"] == "fallback used"
        assert env["data"] is None

    def test_make_envelope_data_is_serializable(self) -> None:
        """Data containing pydantic model dicts should be JSON-serializable."""
        import json
        from tools._helpers import make_envelope

        env = make_envelope(
            data=[{"id": "espn:42", "name": "Test Team"}],
            provider="espn",
            endpoint="search_teams",
            url=None,
            ttl_seconds=600,
        )
        # Should not raise
        serialized = json.dumps(env)
        assert "espn:42" in serialized
