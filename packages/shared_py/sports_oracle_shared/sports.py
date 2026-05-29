"""Normalized sports domain models.

These are provider-agnostic. Each MCP provider adapter is responsible for
mapping its upstream API response into these shapes so the rest of the system
never sees a provider-specific format.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from sports_oracle_shared.enums import FixtureStatus, Sport


class Team(BaseModel):
    id: str = Field(description="Normalized id, namespaced as '<provider>:<raw_id>'.")
    name: str
    short_name: Optional[str] = None
    sport: Sport = Sport.UNKNOWN
    country: Optional[str] = None
    logo_url: Optional[str] = None
    provider: str
    provider_ids: dict[str, str] = Field(default_factory=dict)


class Player(BaseModel):
    id: str
    name: str
    sport: Sport = Sport.UNKNOWN
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    provider: str
    provider_ids: dict[str, str] = Field(default_factory=dict)


class Fixture(BaseModel):
    id: str
    sport: Sport = Sport.UNKNOWN
    league: Optional[str] = None
    season: Optional[str] = None
    status: FixtureStatus = FixtureStatus.UNKNOWN
    start_time: Optional[datetime] = None
    home_team: Optional[Team] = None
    away_team: Optional[Team] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    venue: Optional[str] = None
    round: Optional[str] = None
    provider: str
    provider_ids: dict[str, str] = Field(default_factory=dict)


class StandingRow(BaseModel):
    rank: int
    team: Team
    played: Optional[int] = None
    won: Optional[int] = None
    drawn: Optional[int] = None
    lost: Optional[int] = None
    points: Optional[int] = None
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    form: Optional[str] = Field(default=None, description="Recent results e.g. 'WWDLW'.")


class Standings(BaseModel):
    sport: Sport = Sport.UNKNOWN
    league: str
    season: Optional[str] = None
    rows: list[StandingRow] = Field(default_factory=list)
    provider: str


class TeamStats(BaseModel):
    team_id: str
    sport: Sport = Sport.UNKNOWN
    season: Optional[str] = None
    form: Optional[str] = None
    last_results: list[Fixture] = Field(default_factory=list)
    home_record: dict[str, int] = Field(default_factory=dict)
    away_record: dict[str, int] = Field(default_factory=dict)
    points_for: Optional[float] = None
    points_against: Optional[float] = None
    extra: dict = Field(default_factory=dict)
    provider: str


class PlayerStats(BaseModel):
    player_id: str
    sport: Sport = Sport.UNKNOWN
    season: Optional[str] = None
    stats: dict = Field(default_factory=dict)
    provider: str


class Injury(BaseModel):
    player_name: str
    team_id: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    return_estimate: Optional[str] = None
    provider: str


class Odds(BaseModel):
    fixture_id: str
    bookmaker: Optional[str] = None
    home_win: Optional[float] = None
    draw: Optional[float] = None
    away_win: Optional[float] = None
    implied_home: Optional[float] = Field(default=None, description="De-vigged probability.")
    implied_draw: Optional[float] = None
    implied_away: Optional[float] = None
    provider: str


class HeadToHead(BaseModel):
    team_a: str
    team_b: str
    fixtures: list[Fixture] = Field(default_factory=list)
    provider: str
