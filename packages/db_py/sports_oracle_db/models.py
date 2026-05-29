"""SQLAlchemy 2.0 ORM models for Sports Oracle persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all Sports Oracle models."""

    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=_now,
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=_now,
        server_default=text("now()"),
        nullable=False,
    )

    # relationships
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name="ck_message_role"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=_now,
        server_default=text("now()"),
        nullable=False,
    )

    # relationships
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    citations: Mapped[list[Citation]] = relationship(
        "Citation", back_populates="message", cascade="all, delete-orphan"
    )
    predictions: Mapped[list[Prediction]] = relationship(
        "Prediction", back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_messages_conversation_idx", "conversation_id", "idx"),
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    ref_num: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # relationship
    message: Mapped[Message] = relationship("Message", back_populates="citations")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    sport: Mapped[str] = mapped_column(Text, nullable=False)
    fixture_ref: Mapped[str] = mapped_column(Text, nullable=False)
    pick: Mapped[str] = mapped_column(Text, nullable=False)
    win_probability: Mapped[Any] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_num: Mapped[Any] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_label: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    caveats: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=_now,
        server_default=text("now()"),
        nullable=False,
    )

    # relationship
    message: Mapped[Message] = relationship("Message", back_populates="predictions")

    __table_args__ = (Index("ix_predictions_fixture_ref", "fixture_ref"),)


class SemanticCacheMeta(Base):
    __tablename__ = "semantic_cache_meta"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    entities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    hit_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    __table_args__ = (Index("ix_semantic_cache_meta_expires_at", "expires_at"),)


class EvalTrace(Base):
    """One captured turn for evaluation + routing observability.

    Written by the in-graph capture node for every turn (free; no LLM). The
    RAGAS score columns are filled in later, out of band, by the async judge
    worker — they are NULL until then.
    """

    __tablename__ = "eval_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # Not an FK: eval stays decoupled from the chat tables (a trace can outlive
    # or precede its conversation row).
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # --- what happened on the turn (captured immediately) ---
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    num_tool_results: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    num_rag_hits: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    contexts: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    prediction: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # tz-aware to match the migration (TIMESTAMP WITH TIME ZONE); without this
    # the ORM infers a naive type and Postgres rejects tz-aware `since` filters.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        server_default=text("now()"),
        nullable=False,
    )

    # --- RAGAS / citation scores (filled by the async judge worker) ---
    faithfulness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    answer_relevancy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context_precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context_recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    citation_valid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    judge_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_eval_traces_created_at", "created_at"),
        Index("ix_eval_traces_intent", "intent"),
        # Partial-ish: speeds the judge worker's "unjudged" scan.
        Index("ix_eval_traces_judged_at", "judged_at"),
    )
