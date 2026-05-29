"""Shared contracts for Sports Oracle services.

This package is the single source of truth for the data shapes exchanged
between the MCP server, the LangGraph agent, the RAG pipeline, the database
layer, and the web frontend. Every service depends on these models, so changes
here are contract changes — keep them backward compatible where possible.
"""

from sports_oracle_shared.enums import Intent, Sport, FixtureStatus, ConfidenceLabel
from sports_oracle_shared.sports import (
    Team,
    Player,
    Fixture,
    Standings,
    StandingRow,
    Injury,
    Odds,
    TeamStats,
    PlayerStats,
    HeadToHead,
)
from sports_oracle_shared.envelope import ToolEnvelope, SourceRef
from sports_oracle_shared.rag import RagChunk
from sports_oracle_shared.agent import (
    Citation,
    Prediction,
    PredictionFactor,
    ChatRequest,
    SSEEvent,
    SSEEventType,
)

__all__ = [
    "Intent",
    "Sport",
    "FixtureStatus",
    "ConfidenceLabel",
    "Team",
    "Player",
    "Fixture",
    "Standings",
    "StandingRow",
    "Injury",
    "Odds",
    "TeamStats",
    "PlayerStats",
    "HeadToHead",
    "ToolEnvelope",
    "SourceRef",
    "RagChunk",
    "Citation",
    "Prediction",
    "PredictionFactor",
    "ChatRequest",
    "SSEEvent",
    "SSEEventType",
]
