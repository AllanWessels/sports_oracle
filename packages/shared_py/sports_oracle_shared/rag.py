"""RAG retrieval contract."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RagChunk(BaseModel):
    """A retrieved+reranked chunk, carrying provenance for citation."""

    id: str
    text: str
    collection: str = Field(description="sports_cache | reference_docs | news")
    score: float = Field(description="Final fused+reranked relevance score.")
    title: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    sport: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)
