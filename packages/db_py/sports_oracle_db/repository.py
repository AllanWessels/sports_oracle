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
    EvalTrace,
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


# ---------------------------------------------------------------------------
# Eval trace helpers
# ---------------------------------------------------------------------------

# RAGAS / citation score columns the judge worker fills in.
_SCORE_FIELDS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "citation_valid",
)


async def insert_trace(
    session: AsyncSession,
    *,
    query: str,
    intent: str,
    route: str,
    answer: str,
    cache_hit: bool = False,
    num_tool_results: int = 0,
    num_rag_hits: int = 0,
    contexts: Optional[list] = None,
    citations: Optional[list] = None,
    prediction: Optional[dict] = None,
    latency_ms: Optional[int] = None,
    conversation_id: Optional[uuid.UUID | str] = None,
) -> EvalTrace:
    """Insert one captured turn (scores are filled in later by the judge)."""
    cid = (
        uuid.UUID(str(conversation_id))
        if conversation_id and not isinstance(conversation_id, uuid.UUID)
        else conversation_id
    )
    trace = EvalTrace(
        conversation_id=cid,
        query=query,
        intent=intent,
        route=route,
        answer=answer,
        cache_hit=cache_hit,
        num_tool_results=num_tool_results,
        num_rag_hits=num_rag_hits,
        contexts=contexts,
        citations=citations,
        prediction=prediction,
        latency_ms=latency_ms,
    )
    session.add(trace)
    await session.flush()
    await session.refresh(trace)
    return trace


async def get_unjudged_traces(session: AsyncSession, limit: int = 20) -> list[EvalTrace]:
    """Oldest-first traces that have not been scored yet."""
    stmt = (
        select(EvalTrace)
        .where(EvalTrace.judged_at.is_(None))
        .order_by(EvalTrace.created_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_trace_scores(
    session: AsyncSession,
    trace_id: uuid.UUID | str,
    *,
    judge_model: str,
    scores: dict,
    now: Optional[datetime] = None,
) -> None:
    """Write RAGAS/citation scores onto a trace and stamp ``judged_at``.

    *scores* may contain any of ``_SCORE_FIELDS``; missing keys are left NULL.
    """
    tid = uuid.UUID(str(trace_id)) if not isinstance(trace_id, uuid.UUID) else trace_id
    values: dict = {
        k: scores[k] for k in _SCORE_FIELDS if k in scores and scores[k] is not None
    }
    values["judge_model"] = judge_model
    values["judged_at"] = now or datetime.now(timezone.utc)
    await session.execute(update(EvalTrace).where(EvalTrace.id == tid).values(**values))


async def list_traces(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    intent: Optional[str] = None,
    since: Optional[datetime] = None,
) -> list[EvalTrace]:
    """Recent traces, newest first, optionally filtered by intent / time window."""
    stmt = select(EvalTrace)
    if intent:
        stmt = stmt.where(EvalTrace.intent == intent)
    if since:
        stmt = stmt.where(EvalTrace.created_at >= since)
    stmt = stmt.order_by(EvalTrace.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def trace_to_dict(row: EvalTrace) -> dict:
    """Serialize an EvalTrace to plain JSON-able types (for API / judge / agg)."""
    return {
        "id": str(row.id),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "query": row.query,
        "intent": row.intent,
        "route": row.route,
        "cache_hit": row.cache_hit,
        "num_tool_results": row.num_tool_results,
        "num_rag_hits": row.num_rag_hits,
        "contexts": row.contexts,
        "answer": row.answer,
        "citations": row.citations,
        "prediction": row.prediction,
        "latency_ms": row.latency_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "faithfulness": row.faithfulness,
        "answer_relevancy": row.answer_relevancy,
        "context_precision": row.context_precision,
        "context_recall": row.context_recall,
        "citation_valid": row.citation_valid,
        "judged_at": row.judged_at.isoformat() if row.judged_at else None,
        "judge_model": row.judge_model,
    }