"""Unit tests for core/normalize.py helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_app_root = str(Path(__file__).parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

from sports_oracle_shared.enums import FixtureStatus, Sport  # noqa: E402

from core.normalize import (  # noqa: E402
    coerce_fixture_status,
    coerce_sport,
    implied_prob,
    make_id,
    parse_dt,
    safe_float,
    safe_int,
)


class TestMakeId:
    def test_basic(self) -> None:
        assert make_id("espn", "123") == "espn:123"

    def test_integer_raw_id(self) -> None:
        assert make_id("balldontlie", 42) == "balldontlie:42"

    def test_provider_prefix(self) -> None:
        result = make_id("thesportsdb", "456")
        assert result.startswith("thesportsdb:")


class TestCoerceSport:
    def test_soccer(self) -> None:
        assert coerce_sport("soccer") == Sport.SOCCER

    def test_basketball(self) -> None:
        assert coerce_sport("basketball") == Sport.BASKETBALL

    def test_case_insensitive(self) -> None:
        assert coerce_sport("SOCCER") == Sport.SOCCER

    def test_nba_slug(self) -> None:
        assert coerce_sport("nba") == Sport.BASKETBALL

    def test_nfl_slug(self) -> None:
        assert coerce_sport("nfl") == Sport.AMERICAN_FOOTBALL

    def test_unknown(self) -> None:
        assert coerce_sport("quidditch") == Sport.UNKNOWN

    def test_none(self) -> None:
        assert coerce_sport(None) == Sport.UNKNOWN


class TestCoerceFixtureStatus:
    def test_espn_post(self) -> None:
        assert coerce_fixture_status("post") == FixtureStatus.FINISHED

    def test_espn_pre(self) -> None:
        assert coerce_fixture_status("pre") == FixtureStatus.SCHEDULED

    def test_espn_in(self) -> None:
        assert coerce_fixture_status("in") == FixtureStatus.LIVE

    def test_apisports_ft(self) -> None:
        assert coerce_fixture_status("FT") == FixtureStatus.FINISHED

    def test_apisports_ns(self) -> None:
        assert coerce_fixture_status("NS") == FixtureStatus.SCHEDULED

    def test_apisports_1h(self) -> None:
        assert coerce_fixture_status("1H") == FixtureStatus.LIVE

    def test_balldontlie_final(self) -> None:
        assert coerce_fixture_status("Final") == FixtureStatus.FINISHED

    def test_unknown(self) -> None:
        assert coerce_fixture_status("xyz") == FixtureStatus.UNKNOWN

    def test_none(self) -> None:
        assert coerce_fixture_status(None) == FixtureStatus.UNKNOWN


class TestParseDt:
    def test_iso_z_format(self) -> None:

        dt = parse_dt("2025-03-15T15:00Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 3
        assert dt.tzinfo is not None

    def test_iso_with_seconds(self) -> None:
        dt = parse_dt("2025-06-01T12:30:00Z")
        assert dt is not None
        assert dt.hour == 12
        assert dt.minute == 30

    def test_date_only(self) -> None:
        dt = parse_dt("2025-12-25")
        assert dt is not None
        assert dt.day == 25

    def test_none_input(self) -> None:
        assert parse_dt(None) is None

    def test_empty_string(self) -> None:
        assert parse_dt("") is None

    def test_invalid_string(self) -> None:
        assert parse_dt("not-a-date") is None


class TestSafeInt:
    def test_integer(self) -> None:
        assert safe_int(42) == 42

    def test_string(self) -> None:
        assert safe_int("10") == 10

    def test_float_string(self) -> None:
        assert safe_int("3.0") is None  # int("3.0") raises ValueError

    def test_none(self) -> None:
        assert safe_int(None) is None

    def test_invalid(self) -> None:
        assert safe_int("abc") is None


class TestSafeFloat:
    def test_float(self) -> None:
        assert safe_float(1.5) == 1.5

    def test_string(self) -> None:
        assert safe_float("2.75") == 2.75

    def test_none(self) -> None:
        assert safe_float(None) is None

    def test_invalid(self) -> None:
        assert safe_float("bad") is None


class TestImpliedProb:
    def test_evens(self) -> None:
        prob = implied_prob(2.0)
        assert prob == pytest.approx(0.5, abs=0.001)

    def test_heavy_favourite(self) -> None:
        prob = implied_prob(1.25)
        assert prob == pytest.approx(0.8, abs=0.001)

    def test_none(self) -> None:
        assert implied_prob(None) is None

    def test_zero(self) -> None:
        assert implied_prob(0.0) is None
