"""The uniform envelope every MCP tool returns.

The envelope carries the payload plus provenance (for citations) and freshness
(for the semantic cache TTL). The agent never trusts bare data — it always
receives a ToolEnvelope so it can cite the source and reason about staleness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Provenance for a single tool result, used to build citations."""

    provider: str
    endpoint: str
    url: Optional[str] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolEnvelope(BaseModel):
    """Standard return shape for all MCP sports tools."""

    data: Any = Field(description="The normalized payload (model or list of models).")
    source: SourceRef
    ttl_seconds: int = Field(
        default=300,
        description="How long this result may be served from cache before it is stale.",
    )
    partial: bool = Field(
        default=False,
        description="True when fallbacks produced incomplete data (lowers prediction confidence).",
    )
    notes: Optional[str] = None

    @property
    def expires_at(self) -> datetime:
        from datetime import timedelta

        return self.source.fetched_at + timedelta(seconds=self.ttl_seconds)
