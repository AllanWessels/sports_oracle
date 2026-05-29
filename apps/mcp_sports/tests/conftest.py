"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure the app root is importable
_app_root = str(Path(__file__).parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file by filename (without extension)."""
    path = FIXTURE_DIR / f"{name}.json"
    return json.loads(path.read_text())


@pytest.fixture
def espn_scoreboard_json() -> dict:
    return load_fixture("espn_scoreboard")


@pytest.fixture
def espn_standings_json() -> dict:
    return load_fixture("espn_standings")
