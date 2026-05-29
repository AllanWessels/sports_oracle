"""Async repository functions for Sports Oracle persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sports_oracle_shared.agent import Citation as CitationDTO
from sports_oracle_shared.agent import Prediction as PredictionDTO
from sports_oracle_shared.enums import Intent

from sports_oracle_db.models import (
    Citation,
    Conversation,
    Message,
    Prediction,
    SemanticCacheMeta,
)

# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------


async def create_conversation(
    session: AsyncSession,
    title: Optional[str] = None,
) -> Conversation:
    """Insert a new conversation row and return it."""
    conv = Conversation(title=title)
    session.add(conv)
    await session.flush()
    await session.refresh(conv)
    return conv


async def get_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID | str,
) -> Optional[Conversation]:
    """Fetch a conversation by its primary key (returns None if absent)."""
    cid = uuid.UUID(str(conversation_id)) if not isinstance(conversation_id, uuid.UUID) else conversation_id
    result = await session.get(Conversation, cid)
    return result


async def list_conversations(session: AsyncSession) -> list[Conversation]:
    """Return all conversations ordered by most-recently updated."""
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def touch_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID | str,
    title: Optional[str] = None,
) -> None:
    """Update the ``updated_at`` timestamp (and optionally the title)."""
    cid = uuid.UUID(str(conversation_id)) if not isinstance(conversation_id, uuid.UUID) else conversation_id
    values: dict = {"updated_at": datetime.now(timezone.utc)}
    if title is not None:
        values["title"] = title
    stmt = update(Conversation).where(Conversation.id == cid).values(**values)
    await session.execute(stmt)


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


async def _next_idx(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    """Return the next sequential index for messages in a conversation."""
    stmt = select(func.coalesce(func.max(Message.idx), -1)).where(
        Message.conversation_id == conversation_id
    )
    result = await session.execute(stmt)
    max_idx: int = result.scalar_one()
    return max_idx + 1


async def add_message(
    session: AsyncSession,
    conversation_id: uuid.UUID | str,
    role: str,
    content: str,
    intent: Optional[Intent | str] = None,
    idx: Optional[int] = None,
) -> Message:
    """Append a message to a conversation.

    If *idx* is omitted it is auto-computed as ``max(existing idx) + 1``
    (starting at 0 for the first message).
    """
    cid = uuid.UUID(str(conversation_id)) if not isinstance(conversation_id, uuid.UUID) else conversation_id
    resolved_idx = idx if idx is not None else await _next_idx(session, cid)
    intent_str: Optional[str] = intent.value if isinstance(intent, Intent) else intent
    msg = Message(
        conversation_id=cid,
        role=role,
        content=content,
        intent=intent_str,
        idx=resolved_idx,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    return msg


async def get_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID | str,
) -> list[Message]:
    """Return all messages for a conversation ordered by *idx*."""
    cid = uuid.UUID(str(conversation_id)) if not isinstance(conversation_id, uuid.UUID) else conversation_id
    stmt = (
        select(Message)
        .where(Message.conversation_id == cid)
        .order_by(Message.idx)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Citation helpers
# ---------------------------------------------------------------------------


async def add_citations(
    session: AsyncSession,
    message_id: uuid.UUID | str,
    citations: list[CitationDTO],
) -> list[Citation]:
    """Persist a list of Citation DTOs and return the ORM rows."""
    mid = uuid.UUID(str(message_id)) if not isinstance(message_id, uuid.UUID) else message_id
    rows: list[Citation] = []
    for dto in citations:
        row = Citation(
            message_id=mid,
            ref_num=dto.ref_num,
            source_type=dto.source_type,
            provider=dto.provider,
            endpoint=dto.endpoint,
            url=dto.url,
            fetched_at=dto.fetched_at,
            snippet=dto.snippet,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    for row in rows:
        await session.refresh(row)
    return rows


def citation_to_dto(row: Citation) -> CitationDTO:
    """Convert a Citation ORM row back to the shared DTO."""
    return CitationDTO(
        ref_num=row.ref_num,
        source_type=row.source_type,  # type: ignore[arg-type]
        provider=row.provider,
        endpoint=row.endpoint,
        url=row.url,
        fetched_at=row.fetched_at,
        snippet=row.snippet,
    )


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------


async def add_prediction(
    session: AsyncSession,
    message_id: uuid.UUID | str,
    prediction: PredictionDTO,
) -> Prediction:
    """Persist a Prediction DTO and return the ORM row."""
    mid = uuid.UUID(str(message_id)) if not isinstance(message_id, uuid.UUID) else message_id
    factors_json = [f.model_dump() for f in prediction.key_factors]
    row = Prediction(
        message_id=mid,
        sport=prediction.sport,
        fixture_ref=prediction.fixture_ref,
        pick=prediction.pick,
        win_probability=prediction.win_probability,
        confidence_num=prediction.confidence_num,
        confidence_label=prediction.confidence_label.value
        if hasattr(prediction.confidence_label, "value")
        else prediction.confidence_label,
        factors=factors_json,
        caveats=prediction.caveats,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


def prediction_to_dto(row: Prediction) -> PredictionDTO:
    """Convert a Prediction ORM row back to the shared DTO.

    Note: fields not stored in the DB (draw_probability, data_completeness,
    disclaimer) are returned at their defaults.
    """
    from sports_oracle_shared.agent import PredictionFactor
    from sports_oracle_shared.enums import ConfidenceLabel

    factors = [PredictionFactor(**f) for f in (row.factors or [])]
    return PredictionDTO(
        sport=row.sport,
        fixture_ref=row.fixture_ref,
        pick=row.pick,
        win_probability=float(row.win_probability),
        confidence_num=float(row.confidence_num),
        confidence_label=ConfidenceLabel(row.confidence_label),
        key_factors=factors,
        caveats=list(row.caveats or []),
        # data_completeness is not stored; restore to a neutral sentinel
        data_completeness=1.0,
    )


# ---------------------------------------------------------------------------
# Semantic cache meta helpers
# ---------------------------------------------------------------------------


async def record_cache_meta(
    session: AsyncSession,
    qdrant_point_id: uuid.UUID | str,
    query_text: str,
    tool: str,
    fetched_at: datetime,
    expires_at: datetime,
    entities: Optional[list | dict] = None,
) -> SemanticCacheMeta:
    """Store metadata for a Qdrant semantic cache entry."""
    qpid = (
        uuid.UUID(str(qdrant_point_id))
        if not isinstance(qdrant_point_id, uuid.UUID)
        else qdrant_point_id
    )
    row = SemanticCacheMeta(
        qdrant_point_id=qpid,
        query_text=query_text,
        entities=entities,
        tool=tool,
        fetched_at=fetched_at,
        expires_at=expires_at,
        hit_count=0,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def bump_cache_hit(
    session: AsyncSession,
    qdrant_point_id: uuid.UUID | str,
) -> None:
    """Increment the hit counter for a semantic cache entry."""
    qpid = (
        uuid.UUID(str(qdrant_point_id))
        if not isinstance(qdrant_point_id, uuid.UUID)
        else qdrant_point_id
    )
    stmt = (
        update(SemanticCacheMeta)
        .where(SemanticCacheMeta.qdrant_point_id == qpid)
        .values(hit_count=SemanticCacheMeta.hit_count + 1)
    )
    await session.execute(stmt)


async def find_fresh_cache_meta(
    session: AsyncSession,
    tool: str,
    now: Optional[datetime] = None,
) -> list[SemanticCacheMeta]:
    """Return non-expired semantic cache entries for a given tool."""
    cutoff = now or datetime.now(timezone.utc)
    stmt = (
        select(SemanticCacheMeta)
        .where(
            SemanticCacheMeta.tool == tool,
            SemanticCacheMeta.expires_at > cutoff,
        )
        .order_by(SemanticCacheMeta.fetched_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
