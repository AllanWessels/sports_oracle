"""Payload models, TTL helpers, collection name constants, and per-data-class TTL table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Collection name constants
# ---------------------------------------------------------------------------

COLLECTION_SPORTS_CACHE = "sports_cache"
COLLECTION_REFERENCE_DOCS = "reference_docs"
COLLECTION_NEWS = "news"

ALL_COLLECTIONS = (COLLECTION_SPORTS_CACHE, COLLECTION_REFERENCE_DOCS, COLLECTION_NEWS)

# ---------------------------------------------------------------------------
# TTL table (seconds) per data class
# ---------------------------------------------------------------------------

class DataClass(str, Enum):
    API_RESPONSE = "api_response"
    QA_ANSWER = "qa_answer"
    NEWS_ARTICLE = "news_article"
    REFERENCE_DOC = "reference_doc"


_TTL_SECONDS: dict[DataClass, int] = {
    DataClass.API_RESPONSE: 60 * 60,          # 1 hour
    DataClass.QA_ANSWER: 6 * 60 * 60,         # 6 hours
    DataClass.NEWS_ARTICLE: 7 * 24 * 60 * 60, # 7 days
    DataClass.REFERENCE_DOC: 365 * 24 * 60 * 60,  # 1 year (effectively permanent)
}


def ttl_seconds(data_class: DataClass) -> int:
    """Return the TTL in seconds for a given data class."""
    return _TTL_SECONDS[data_class]


def expires_at(data_class: DataClass, *, now: datetime | None = None) -> datetime:
    """Return the expiry datetime for a newly created item of this data class."""
    base = now or datetime.now(UTC)
    return base + timedelta(seconds=ttl_seconds(data_class))


def is_expired(exp: datetime, *, now: datetime | None = None) -> bool:
    """Return True if the given expiry timestamp has passed."""
    base = now or datetime.now(UTC)
    # Make both offset-aware for comparison
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return base >= exp


# ---------------------------------------------------------------------------
# Payload models (stored in Qdrant point payloads)
# ---------------------------------------------------------------------------

class BasePayload(BaseModel):
    """Fields common to all Qdrant point payloads."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    title: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    sport: Optional[str] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class SportsCachePayload(BasePayload):
    """Payload for the ``sports_cache`` collection."""

    data_class: DataClass  # api_response | qa_answer
    expires_at: datetime

    @classmethod
    def build(
        cls,
        text: str,
        data_class: DataClass,
        *,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> "SportsCachePayload":
        exp = expires_at(data_class, now=now)
        return cls(text=text, data_class=data_class, expires_at=exp, **kwargs)


class ReferenceDocPayload(BasePayload):
    """Payload for the ``reference_docs`` collection."""

    section_title: Optional[str] = None
    doc_hash: Optional[str] = None  # sha256 of source content, for change detection


class NewsPayload(BasePayload):
    """Payload for the ``news`` collection."""

    published_at: Optional[datetime] = None
    feed_url: Optional[str] = None
