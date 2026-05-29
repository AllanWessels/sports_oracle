"""ESPN unofficial API provider (keyless).

Endpoint pattern:
    https://site.api.espn.com/apis/site/v2/sports/{sport_slug}/{league_slug}/{resource}

Sport / league slugs used here:
    soccer    / eng.1 (Premier League), usa.1 (MLS), esp.1, ger.1, ita.1, fra.1
    football  / nfl
    basketball/ nba
    baseball  / mlb
    hockey    / nhl
"""

from __future__ import annotations

import logging
from typing import Any

from sports_oracle_shared.enums import FixtureStatus, Sport
from sports_oracle_shared.sports import (
    Fixture,
    HeadToHead,
    Injury,
    Odds,
    Player,
    PlayerStats,
    StandingRow,
    Standings,
    Team,
    TeamStats,
)

from core.httpclient import SportHttpClient
from core.normalize import (
    coerce_fixture_status,
    make_id,
    parse_dt,
    safe_int,
)
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE = "https://site.api.espn.com"
PROVIDER = "espn"

# Map Sport enum → (sport_slug, [default league slugs])
_SPORT_LEAGUES: dict[Sport, tuple[str, list[str]]] = {
    Sport.SOCCER: ("soccer", ["eng.1", "usa.1", "esp.1", "ger.1", "ita.1", "fra.1"]),
    Sport.AMERICAN_FOOTBALL: ("football", ["nfl"]),
    Sport.BASKETBALL: ("basketball", ["nba"]),
    Sport.BASEBALL: ("baseball", ["mlb"]),
    Sport.HOCKEY: ("hockey", ["nhl"]),
}


def _strip_provider_prefix(tid: str) -> str:
    """If an id is namespaced (``"espn:123"``), return ``"123"``."""
    if ":" in tid:
        return tid.split(":", 1)[1]
    return tid


class ESPNProvider(BaseProvider):
    """Keyless ESPN unofficial API adapter."""

    name = PROVIDER

    def __init__(self) -> None:
        self._http = SportHttpClient(
            provider_name=PROVIDER,
            base_url=_BASE,
            rate_per_second=4.0,
            cache_ttl=30,
            cache_maxsize=256,
        )

    @property
    def is_available(self) -> bool:
        return True  # no key required

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _url(self, sport_slug: str, league_slug: str, resource: str) -> str:
        return f"/apis/site/v2/sports/{sport_slug}/{league_slug}/{resource}"

    def _leagues_for(self, sport: Sport) -> tuple[str, list[str]] | None:
        return _SPORT_LEAGUES.get(sport)

    def _make_team(self, raw: dict[str, Any], sport: Sport) -> Team:
        tid = str(raw.get("id", "unknown"))
        logos = raw.get("logos") or []
        logo_url = logos[0].get("href") if logos else None
        if not logo_url:
            # alternate logo path
            logo = raw.get("logo")
            logo_url = logo if isinstance(logo, str) else None
        return Team(
            id=make_id(PROVIDER, tid),
            name=raw.get("displayName") or raw.get("name", ""),
            short_name=raw.get("abbreviation") or raw.get("shortDisplayName"),
            sport=sport,
            country=raw.get("country"),
            logo_url=logo_url,
            provider=PROVIDER,
            provider_ids={PROVIDER: tid},
        )

    def _make_fixture_from_event(self, event: dict[str, Any], sport: Sport) -> Fixture:
        eid = str(event.get("id", "unknown"))
        competitions = event.get("competitions", [])
        comp = competitions[0] if competitions else {}

        competitors = comp.get("competitors", [])
        home_team: Team | None = None
        away_team: Team | None = None
        home_score: int | None = None
        away_score: int | None = None

        for c in competitors:
            team_data = c.get("team", {})
            team = self._make_team(team_data, sport)
            score = safe_int(c.get("score"))
            if c.get("homeAway") == "home":
                home_team = team
                home_score = score
            else:
                away_team = team
                away_score = score

        status_raw = event.get("status", {})
        status_type = status_raw.get("type", {})
        status_state = status_type.get("state", "")
        status = coerce_fixture_status(status_state)

        # Prefer startDate from event, fall back to competitions
        start_raw = event.get("date") or comp.get("date")
        start_time = parse_dt(start_raw)

        season_data = event.get("season", {})
        season = str(season_data.get("year", "")) or None

        league_data = event.get("league", {})
        league_name = league_data.get("name") or league_data.get("abbreviation")
        if not league_name:
            # Try from competitions
            league_name = comp.get("league", {}).get("name")

        venue_data = comp.get("venue", {})
        venue = venue_data.get("fullName") or venue_data.get("shortName")

        return Fixture(
            id=make_id(PROVIDER, eid),
            sport=sport,
            league=league_name,
            season=season,
            status=status,
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            venue=venue,
            provider=PROVIDER,
            provider_ids={PROVIDER: eid},
        )

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    async def search_teams(self, query: str, sport: Sport | None = None) -> list[Team]:
        """Search ESPN teams by iterating league team lists and name-filtering."""
        results: list[Team] = []
        sports_to_check = (
            [sport] if sport and sport in _SPORT_LEAGUES else list(_SPORT_LEAGUES.keys())
        )
        query_lower = query.lower()
        for sp in sports_to_check:
            sport_slug, leagues = _SPORT_LEAGUES[sp]
            for league in leagues[:2]:  # limit to top 2 leagues per sport for search
                try:
                    url = self._url(sport_slug, league, "teams")
                    data = await self._http.get_json(url)
                    sports_data = data.get("sports", [])
                    for s in sports_data:
                        for lg in s.get("leagues", []):
                            for entry in lg.get("teams", []):
                                raw = entry.get("team", entry)
                                name = (
                                    raw.get("displayName", "")
                                    or raw.get("name", "")
                                ).lower()
                                if query_lower in name:
                                    results.append(self._make_team(raw, sp))
                except Exception as exc:
                    logger.warning("[espn] search_teams error for %s/%s: %s", sp, league, exc)
        return results

    async def search_players(self, query: str, sport: Sport | None = None) -> list[Player]:
        """ESPN does not provide a free player-search endpoint; return empty."""
        return []

    # ------------------------------------------------------------------
    # Fixtures / live scores
    # ------------------------------------------------------------------

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
        entry = self._leagues_for(sport)
        if not entry:
            return []
        sport_slug, leagues = entry

        # If a specific league is given via league_id, use it
        if league_id:
            league_raw = _strip_provider_prefix(league_id)
            leagues = [league_raw]

        params: dict[str, str] = {}
        if date_from:
            params["dates"] = date_from.replace("-", "")
        if date_to and not date_from:
            params["dates"] = date_to.replace("-", "")

        results: list[Fixture] = []
        for league in leagues:
            try:
                url = self._url(sport_slug, league, "scoreboard")
                data = await self._http.get_json(url, params=params or None)
                for event in data.get("events", []):
                    fix = self._make_fixture_from_event(event, sport)
                    # Team filter
                    if team_id:
                        raw_tid = _strip_provider_prefix(team_id)
                        team_ids = set()
                        if fix.home_team:
                            team_ids.add(_strip_provider_prefix(fix.home_team.id))
                        if fix.away_team:
                            team_ids.add(_strip_provider_prefix(fix.away_team.id))
                        if raw_tid not in team_ids:
                            continue
                    # Status filter
                    if status and fix.status != status:
                        continue
                    results.append(fix)
            except Exception as exc:
                logger.warning("[espn] get_fixtures error for %s/%s: %s", sport_slug, league, exc)
        return results

    async def get_live_scores(
        self,
        sport: Sport,
        *,
        league_id: str | None = None,
        team_id: str | None = None,
    ) -> list[Fixture]:
        fixtures = await self.get_fixtures(
            sport,
            league_id=league_id,
            team_id=team_id,
            status=FixtureStatus.LIVE,
        )
        # ESPN scoreboard with no date param returns today's games
        # Filter to only live ones
        return [f for f in fixtures if f.status == FixtureStatus.LIVE]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_team_stats(
        self, sport: Sport, team_id: str, season: str | None = None
    ) -> TeamStats | None:
        """Build TeamStats from recent schedule (last 5 results)."""
        entry = self._leagues_for(sport)
        if not entry:
            return None
        sport_slug, leagues = entry
        raw_tid = _strip_provider_prefix(team_id)
        all_fixtures: list[Fixture] = []
        for league in leagues[:1]:
            try:
                url = self._url(sport_slug, league, f"teams/{raw_tid}/schedule")
                params: dict[str, Any] = {}
                if season:
                    params["season"] = season
                data = await self._http.get_json(url, params=params or None)
                for event in data.get("events", []):
                    fix = self._make_fixture_from_event(event, sport)
                    all_fixtures.append(fix)
            except Exception as exc:
                logger.warning("[espn] get_team_stats error %s: %s", team_id, exc)

        finished = [f for f in all_fixtures if f.status == FixtureStatus.FINISHED]
        recent = finished[-10:]

        # Build form string from recent results (W/D/L from team perspective)
        form_chars: list[str] = []
        for f in recent[-5:]:
            form_chars.append(_fixture_result_char(f, raw_tid))
        form = "".join(form_chars) if form_chars else None

        return TeamStats(
            team_id=make_id(PROVIDER, raw_tid),
            sport=sport,
            season=season,
            form=form,
            last_results=recent[-5:],
            provider=PROVIDER,
        )

    async def get_player_stats(
        self, sport: Sport, player_id: str, season: str | None = None
    ) -> PlayerStats | None:
        return None  # ESPN doesn't expose per-player stats via this free API

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(
        self, sport: Sport, league_id: str, season: str | None = None
    ) -> Standings | None:
        entry = self._leagues_for(sport)
        if not entry:
            return None
        sport_slug, _ = entry
        league_slug = _strip_provider_prefix(league_id)
        try:
            url = self._url(sport_slug, league_slug, "standings")
            params: dict[str, Any] = {}
            if season:
                params["season"] = season
            data = await self._http.get_json(url, params=params or None)
        except Exception as exc:
            logger.warning("[espn] get_standings error %s/%s: %s", sport_slug, league_id, exc)
            return None

        rows = _parse_standings(data, sport)
        return Standings(
            sport=sport,
            league=league_id,
            season=season,
            rows=rows,
            provider=PROVIDER,
        )

    # ------------------------------------------------------------------
    # Head-to-head, injuries, odds — not available keyless
    # ------------------------------------------------------------------

    async def get_head_to_head(
        self,
        sport: Sport,
        team_a: str,
        team_b: str,
        limit: int = 10,
    ) -> HeadToHead | None:
        return None

    async def get_injuries(self, sport: Sport, team_id: str) -> list[Injury]:
        """ESPN injuries endpoint."""
        entry = self._leagues_for(sport)
        if not entry:
            return []
        sport_slug, leagues = entry
        raw_tid = _strip_provider_prefix(team_id)
        injuries: list[Injury] = []
        for league in leagues[:1]:
            try:
                url = self._url(sport_slug, league, f"teams/{raw_tid}/injuries")
                data = await self._http.get_json(url)
                for item in data.get("injuries", []):
                    athlete = item.get("athlete", {})
                    injuries.append(
                        Injury(
                            player_name=athlete.get("displayName", "Unknown"),
                            team_id=make_id(PROVIDER, raw_tid),
                            status=item.get("status"),
                            reason=item.get("type", {}).get("description"),
                            return_estimate=item.get("details", {}).get("returnDate"),
                            provider=PROVIDER,
                        )
                    )
            except Exception as exc:
                logger.warning("[espn] get_injuries error %s: %s", team_id, exc)
        return injuries

    async def get_odds(self, sport: Sport, fixture_id: str) -> list[Odds]:
        return []


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _fixture_result_char(fixture: Fixture, raw_team_id: str) -> str:
    """Return 'W', 'D', or 'L' from the perspective of team *raw_team_id*."""
    if fixture.home_score is None or fixture.away_score is None:
        return "?"
    home_id = ""
    away_id = ""
    if fixture.home_team:
        home_id = _strip_provider_prefix(fixture.home_team.id)
    if fixture.away_team:
        away_id = _strip_provider_prefix(fixture.away_team.id)

    if raw_team_id == home_id:
        ours, theirs = fixture.home_score, fixture.away_score
    elif raw_team_id == away_id:
        ours, theirs = fixture.away_score, fixture.home_score
    else:
        return "?"

    if ours > theirs:
        return "W"
    if ours == theirs:
        return "D"
    return "L"


def _parse_standings(data: dict[str, Any], sport: Sport) -> list[StandingRow]:
    """Parse ESPN standings response into StandingRow list."""
    rows: list[StandingRow] = []
    # ESPN standings JSON varies; try common structures
    children = data.get("children", []) or data.get("standings", {}).get("entries", [])

    # Structure 1: children[] with entries[]
    for child in children:
        for entry in child.get("standings", {}).get("entries", []):
            row = _parse_standing_entry(entry, sport)
            if row:
                rows.append(row)

    # Structure 2: direct entries at top level
    if not rows:
        for entry in data.get("standings", {}).get("entries", []):
            row = _parse_standing_entry(entry, sport)
            if row:
                rows.append(row)

    # Sort by rank
    rows.sort(key=lambda r: r.rank)
    return rows


def _parse_standing_entry(entry: dict[str, Any], sport: Sport) -> StandingRow | None:
    team_raw = entry.get("team", {})
    if not team_raw:
        return None
    team = Team(
        id=make_id(PROVIDER, str(team_raw.get("id", "?"))),
        name=team_raw.get("displayName") or team_raw.get("name", ""),
        short_name=team_raw.get("abbreviation"),
        sport=sport,
        provider=PROVIDER,
        provider_ids={PROVIDER: str(team_raw.get("id", "?"))},
    )

    stats: dict[str, Any] = {}
    for stat in entry.get("stats", []):
        stats[stat.get("name", "")] = stat.get("value")

    rank = safe_int(stats.get("playoffSeed") or stats.get("rank") or stats.get("seed"))
    if rank is None:
        rank = 999  # will be sorted out

    return StandingRow(
        rank=rank,
        team=team,
        played=safe_int(stats.get("gamesPlayed")),
        won=safe_int(stats.get("wins")),
        drawn=safe_int(stats.get("ties")),
        lost=safe_int(stats.get("losses")),
        points=safe_int(stats.get("points")),
        goals_for=safe_int(stats.get("pointsFor") or stats.get("goalsFor")),
        goals_against=safe_int(stats.get("pointsAgainst") or stats.get("goalsAgainst")),
        form=None,
    )
