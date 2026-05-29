"""The LangGraph agent state."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from sports_oracle_shared import Citation, Prediction, RagChunk


class OracleState(TypedDict, total=False):
    """Shared state threaded through the graph.

    Reducers: `messages` accumulates via add_messages; everything else is
    last-write-wins per node.
    """

    messages: Annotated[list, add_messages]
    query: str
    conversation_id: Optional[str]

    intent: str  # Intent value: factual | prediction | chitchat
    entities: dict[str, Any]  # {sport, teams[], players[], league, fixture_id, date_range}
    freshness_floor: Optional[datetime]

    tool_plan: list[dict]
    tool_results: list[dict]  # serialized ToolEnvelopes
    rag_hits: list[RagChunk]

    cache_hit: Optional[dict]  # cached answer payload when semantic cache short-circuits

    prediction: Optional[Prediction]
    citations: list[Citation]
    answer: str
