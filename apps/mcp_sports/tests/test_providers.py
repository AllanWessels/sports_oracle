"""Tests for TheSportsDB, APISports, and BallDontLie provider adapters.

Uses respx to intercept httpx calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_app_root = str(Path(__file__).parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

from sports_oracle_shared.enums import Sport  # noqa: E402
from sports_oracle_shared.sports import Player, Team  # noqa: E402

# ---------------------------------------------------------------------------
# TheSportsDB
# ---------------------------------------------------------------------------


class TestTheSportsDBProvider:
    @pytest.mark.asyncio
    async def test_search_teams_returns_list(self) -> None:
        import httpx
        import respx

        from providers.thesportsdb import TheSportsDBProvider

        provider = TheSportsDBProvider()
        url = f"https://www.thesportsdb.com/api/v1/json/{provider._key}/searchteams.php"
        mock_response = {
            "teams": [
                {
                    "idTeam": "133604",
                    "strTeam": "Arsenal",
                    "strTeamShort": "ARS",
                    "strSport": "Soccer",
                    "strCountry": "England",
                    "strTeamBadge": "https://example.com/badge.png",
                }
            ]
        }
        with respx.mock:
            respx.get(url).mock(return_value=httpx.Response(200, json=mock_response))
            teams = await provider.search_teams("Arsenal")

        assert len(teams) == 1
        assert isinstance(teams[0], Team)
        assert teams[0].id == "thesportsdb:133604"
        assert teams[0].name == "Arsenal"
        assert teams[0].sport == Sport.SOCCER

    @pytest.mark.asyncio
    async def test_search_teams_empty_response(self) -> None:
        import httpx
        import respx

        from providers.thesportsdb import TheSportsDBProvider

        provider = TheSportsDBProvider()
        url = f"https://www.thesportsdb.com/api/v1/json/{provider._key}/searchteams.php"
        with respx.mock:
            respx.get(url).mock(return_value=httpx.Response(200, json={"teams": None}))
            teams = await provider.search_teams("NonExistentXYZ")

        assert teams == []

    @pytest.mark.asyncio
    async def test_search_players_returns_list(self) -> None:
        import httpx
        import respx

        from providers.thesportsdb import TheSportsDBProvider

        provider = TheSportsDBProvider()
        url = f"https://www.thesportsdb.com/api/v1/json/{provider._key}/searchplayers.php"
        mock_response = {
            "player": [
                {
                    "idPlayer": "34145937",
                    "strPlayer": "Bukayo Saka",
                    "strSport": "Soccer",
                    "idTeam": "133604",
                    "strTeam": "Arsenal",
                    "strPosition": "Forward",
                    "strNationality": "England",
                }
            ]
        }
        with respx.mock:
            respx.get(url).mock(return_value=httpx.Response(200, json=mock_response))
            players = await provider.search_players("Saka")

        assert len(players) == 1
        assert isinstance(players[0], Player)
        assert players[0].id == "thesportsdb:34145937"
        assert "Saka" in players[0].name

    @pytest.mark.asyncio
    async def test_is_available_always_true(self) -> None:
        from providers.thesportsdb import TheSportsDBProvider

        provider = TheSportsDBProvider()
        assert provider.is_available is True


# ---------------------------------------------------------------------------
# APISports
# ---------------------------------------------------------------------------


class TestAPISportsProvider:
    def test_unavailable_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import providers.apisports as mod

        monkeypatch.delenv("APISPORTS_KEY", raising=False)
        # Re-instantiate with no key
        provider = mod.APISportsProvider()
        provider._key = ""
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_get_fixtures_noops_without_key(self) -> None:
        from providers.apisports import APISportsProvider

        provider = APISportsProvider()
        provider._key = ""  # force unavailable
        fixtures = await provider.get_fixtures(Sport.SOCCER)
        assert fixtures == []

    @pytest.mark.asyncio
    async def test_get_fixtures_with_key(self) -> None:
        import httpx
        import respx

        from providers.apisports import APISportsProvider

        provider = APISportsProvider()
        provider._key = "testkey"
        provider._http._client.headers["x-apisports-key"] = "testkey"

        mock_response = {
            "response": [
                {
                    "fixture": {
                        "id": 99001,
                        "date": "2025-04-10T19:45:00+00:00",
                        "status": {"short": "FT"},
                        "venue": {"name": "Emirates Stadium"},
                    },
                    "league": {"id": 39, "name": "Premier League", "season": 2024},
                    "teams": {
                        "home": {"id": 42, "name": "Arsenal", "logo": ""},
                        "away": {"id": 40, "name": "Liverpool", "logo": ""},
                    },
                    "goals": {"home": 2, "away": 0},
                }
            ]
        }
        with respx.mock:
            respx.get("https://v3.football.api-sports.io/fixtures").mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            fixtures = await provider.get_fixtures(Sport.SOCCER, league_id="39")

        assert len(fixtures) == 1
        from sports_oracle_shared.enums import FixtureStatus

        assert fixtures[0].status == FixtureStatus.FINISHED
        assert fixtures[0].home_score == 2
        assert fixtures[0].away_score == 0


# ---------------------------------------------------------------------------
# BallDontLie
# ---------------------------------------------------------------------------


class TestBallDontLieProvider:
    def test_unavailable_when_no_key(self) -> None:
        from providers.balldontlie import BallDontLieProvider

        provider = BallDontLieProvider()
        provider._key = ""
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_search_teams_noops_without_key(self) -> None:
        from providers.balldontlie import BallDontLieProvider

        provider = BallDontLieProvider()
        provider._key = ""
        teams = await provider.search_teams("Lakers")
        assert teams == []

    @pytest.mark.asyncio
    async def test_get_fixtures_maps_game(self) -> None:
        import httpx
        import respx

        from providers.balldontlie import BallDontLieProvider

        provider = BallDontLieProvider()
        provider._key = "testkey"
        provider._http._client.headers["Authorization"] = "testkey"

        mock_response = {
            "data": [
                {
                    "id": 47,
                    "date": "2025-02-20",
                    "home_team": {"id": 14, "full_name": "Los Angeles Lakers", "abbreviation": "LAL"},
                    "visitor_team": {
                        "id": 2,
                        "full_name": "Boston Celtics",
                        "abbreviation": "BOS",
                    },
                    "home_team_score": 112,
                    "visitor_team_score": 108,
                    "status": "Final",
                    "season": 2024,
                }
            ],
            "meta": {"total_pages": 1, "current_page": 1, "next_page": None, "per_page": 25},
        }
        with respx.mock:
            respx.get("https://api.balldontlie.io/v1/games").mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            from sports_oracle_shared.enums import FixtureStatus

            fixtures = await provider.get_fixtures(Sport.BASKETBALL)

        assert len(fixtures) == 1
        fix = fixtures[0]
        assert fix.sport == Sport.BASKETBALL
        assert fix.status == FixtureStatus.FINISHED
        assert fix.home_score == 112
        assert fix.home_team is not None
        assert fix.home_team.name == "Los Angeles Lakers"

    @pytest.mark.asyncio
    async def test_get_player_stats(self) -> None:
        import httpx
        import respx
        from sports_oracle_shared.sports import PlayerStats

        from providers.balldontlie import BallDontLieProvider

        provider = BallDontLieProvider()
        provider._key = "testkey"
        provider._http._client.headers["Authorization"] = "testkey"

        mock_response = {
            "data": [
                {
                    "player_id": 237,
                    "season": 2024,
                    "min": "35:20",
                    "fgm": 9.5,
                    "pts": 27.1,
                    "ast": 8.3,
                    "reb": 7.9,
                    "stl": 1.3,
                    "blk": 0.6,
                    "fg_pct": 0.525,
                    "fg3_pct": 0.391,
                    "ft_pct": 0.878,
                    "turnover": 3.5,
                    "games_played": 71,
                }
            ]
        }
        with respx.mock:
            respx.get("https://api.balldontlie.io/v1/season_averages").mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            stats = await provider.get_player_stats(Sport.BASKETBALL, "balldontlie:237", "2024")

        assert stats is not None
        assert isinstance(stats, PlayerStats)
        assert stats.stats["pts"] == pytest.approx(27.1)
        assert stats.stats["ast"] == pytest.approx(8.3)
