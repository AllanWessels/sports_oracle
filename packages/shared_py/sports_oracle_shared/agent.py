"""Agent-facing contracts: citations, predictions, chat I/O and SSE events."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from sports_oracle_shared.enums import ConfidenceLabel, Intent


class Citation(BaseModel):
    """A numbered reference attached to an answer ([1], [2], ...)."""

    ref_num: int
    source_type: Literal["api", "rag_doc", "rag_news"]
    provider: str = Field(description="API provider name or RAG doc id.")
    endpoint: Optional[str] = None
    url: Optional[str] = None
    fetched_at: Optional[datetime] = None
    snippet: Optional[str] = None


class PredictionFactor(BaseModel):
    name: str
    direction: Literal["home", "away", "draw", "neutral"]
    weight: float = Field(ge=0.0, le=1.0)
    detail: Optional[str] = None


class Prediction(BaseModel):
    sport: str
    fixture_ref: str
    pick: str
    win_probability: float = Field(ge=0.0, le=1.0)
    draw_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_num: float = Field(ge=0.0, le=1.0, description="Blended, calibrated confidence.")
    confidence_label: ConfidenceLabel
    key_factors: list[PredictionFactor] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    data_completeness: float = Field(
        ge=0.0, le=1.0, description="Fraction of expected signals that were available."
    )
    disclaimer: str = "Informational only — not betting advice."


class ChatRequest(BaseModel):
    """Incoming chat turn from the web client."""

    message: str
    conversation_id: Optional[str] = None


class SSEEventType(str):
    """String constants for the SSE event stream (see SSEEvent.type)."""

    TOKEN = "token"            # a streamed answer token
    INTENT = "intent"         # router decision
    TOOL = "tool"             # a tool/MCP call was made
    CITATION = "citation"     # a citation was attached
    PREDICTION = "prediction" # a structured prediction payload
    DONE = "done"             # end of stream (carries conversation_id, message_id)
    ERROR = "error"


class SSEEvent(BaseModel):
    """One server-sent event. `type` is one of SSEEventType's constants."""

    type: str
    data: dict = Field(default_factory=dict)
    conversation_id: Optional[str] = None

    def sse(self) -> str:
        import json

        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"
