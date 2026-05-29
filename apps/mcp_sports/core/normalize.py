"""Shared normalization helpers used by all provider adapters.

Conventions
-----------
- IDs are always namespaced: ``"<provider>:<raw_id>"``
- Unknown / missing values stay as ``None`` rather than empty strings.
- Datetime strings are parsed to timezone-aware ``datetime`` objects where
  possible; failures fall back to ``None``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sports_oracle_shared.enums import FixtureStatus, Sport

# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def make_id(provider: str, raw_id: Any) -> str:
    """Return a namespaced ID string ``"<provider>:<raw_id>"``."""
    return f"{provider}:{raw_id}"


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------

_ESPN_DATE_FMT = "%Y-%m-%dT%H:%MZ"
_ISO_FMTS = [
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%MZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def parse_dt(value: str | None) -> datetime | None:
    """Try to parse a datetime string; return ``None`` on failure."""
    if not value:
        return None
    for fmt in _ISO_FMTS:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Enum coercion
# ---------------------------------------------------------------------------

_SPORT_MAP: dict[str, Sport] = {
    "soccer": Sport.SOCCER,
    "football": Sport.AMERICAN_FOOTBALL,
    "basketball": Sport.BASKETBALL,
    "baseball": Sport.BASEBALL,
    "hockey": Sport.HOCKEY,
    "tennis": Sport.TENNIS,
    "motorsport": Sport.MOTORSPORT,
    "racing": Sport.MOTORSPORT,
    "golf": Sport.GOLF,
    "mma": Sport.MMA,
    "cricket": Sport.CRICKET,
    "rugby": Sport.RUGBY,
    # ESPN sport slugs
    "nfl": Sport.AMERICAN_FOOTBALL,
    "nba": Sport.BASKETBALL,
    "mlb": Sport.BASEBALL,
    "nhl": Sport.HOCKEY,
    "nfl-football": Sport.AMERICAN_FOOTBALL,
}

_FIXTURE_STATUS_MAP: dict[str, FixtureStatus] = {
    # ESPN
    "pre": FixtureStatus.SCHEDULED,
    "in": FixtureStatus.LIVE,
    "post": FixtureStatus.FINISHED,
    "canceled": FixtureStatus.CANCELLED,
    "postponed": FixtureStatus.POSTPONED,
    # TheSportsDB
    "not started": FixtureStatus.SCHEDULED,
    "live": FixtureStatus.LIVE,
    "match finished": FixtureStatus.FINISHED,
    "finished": FixtureStatus.FINISHED,
    # API-Football
    "1h": FixtureStatus.LIVE,
    "2h": FixtureStatus.LIVE,
    "ht": FixtureStatus.LIVE,
    "et": FixtureStatus.LIVE,
    "p": FixtureStatus.LIVE,
    "ft": FixtureStatus.FINISHED,
    "aet": FixtureStatus.FINISHED,
    "pen": FixtureStatus.FINISHED,
    "tbd": FixtureStatus.SCHEDULED,
    "ns": FixtureStatus.SCHEDULED,
    "susp": FixtureStatus.POSTPONED,
    "int": FixtureStatus.POSTPONED,
    "pst": FixtureStatus.POSTPONED,
    "canc": FixtureStatus.CANCELLED,
    "awd": FixtureStatus.FINISHED,
    "wo": FixtureStatus.FINISHED,
    # balldontlie
    "final": FixtureStatus.FINISHED,
    "in progress": FixtureStatus.LIVE,
    "scheduled": FixtureStatus.SCHEDULED,
}


def coerce_sport(value: str | None) -> Sport:
    if not value:
        return Sport.UNKNOWN
    return _SPORT_MAP.get(value.lower(), Sport.UNKNOWN)


def coerce_fixture_status(value: str | None) -> FixtureStatus:
    if not value:
        return FixtureStatus.UNKNOWN
    return _FIXTURE_STATUS_MAP.get(value.lower().strip(), FixtureStatus.UNKNOWN)


# ---------------------------------------------------------------------------
# Safe int/float
# ---------------------------------------------------------------------------


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Implied probability helper (de-vig / normalize)
# ---------------------------------------------------------------------------


def implied_prob(decimal_odds: float | None) -> float | None:
    """Convert decimal odds to implied probability."""
    if decimal_odds is None or decimal_odds <= 0:
        return None
    return round(1.0 / decimal_odds, 4)
