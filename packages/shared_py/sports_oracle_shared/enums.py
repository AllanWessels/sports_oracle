"""Enumerations shared across services."""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    """Routing intent for an incoming user turn."""

    FACTUAL = "factual"
    PREDICTION = "prediction"
    CHITCHAT = "chitchat"


class Sport(str, Enum):
    """Supported sports. Providers map these onto upstream league/sport codes."""

    SOCCER = "soccer"
    BASKETBALL = "basketball"
    AMERICAN_FOOTBALL = "american_football"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    TENNIS = "tennis"
    MOTORSPORT = "motorsport"
    GOLF = "golf"
    MMA = "mma"
    CRICKET = "cricket"
    RUGBY = "rugby"
    UNKNOWN = "unknown"


class FixtureStatus(str, Enum):
    """Normalized fixture lifecycle status."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ConfidenceLabel(str, Enum):
    """Human-readable confidence bucket for predictions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
