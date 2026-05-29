"""Eval-capture node: record one trace per turn for evaluation + observability.

Runs after ``persist_and_cache`` (so it has the saved ``conversation_id``) and
before END. The write is free (no LLM) and fire-and-forget: any failure is
swallowed so eval never breaks a turn — the same graceful-degradation contract
the persistence/cache services use. RAGAS scores are added later, out of band,
by the async judge worker.
"""

from __future__ import annotations

import logging
import time

from app.agent.state import OracleState
from app.config import get_settings

logger = logging.getLogger(__name__)


def _dump(obj):
    """Best-effort JSON-able form of a pydantic model / list / scalar."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def build_trace_fields(state: OracleState) -> dict:
    """Pure: derive the eval_traces row fields from final graph state.

    Kept separate from the DB write so it can be unit-tested without a database.
    """
    started = state.get("started_at")
    latency_ms = int((time.time() - started) * 1000) if started else None

    rag_hits = state.get("rag_hits") or []
    tool_results = state.get("tool_results") or []

    contexts: list[dict] = []
    for h in rag_hits:
        text = getattr(h, "text", None) if not isinstance(h, dict) else h.get("text")
        source = getattr(h, "source", None) if not isinstance(h, dict) else h.get("source")
        collection = (
            getattr(h, "collection", None) if not isinstance(h, dict) else h.get("collection")
        )
        contexts.append({"text": text or "", "source": source, "collection": collection})

    intent = state.get("intent", "factual")
    cache_hit = bool(state.get("cache_hit"))
    route = "cache" if cache_hit else ("prediction" if intent == "prediction" else intent)

    citations = [_dump(c) for c in (state.get("citations") or [])]

    return {
        "conversation_id": state.get("conversation_id"),
        "query": state.get("query", ""),
        "intent": intent,
        "route": route,
        "cache_hit": cache_hit,
        "num_tool_results": len(tool_results),
        "num_rag_hits": len(rag_hits),
        "contexts": contexts,
        "answer": state.get("answer", "") or "",
        "citations": citations,
        "prediction": _dump(state.get("prediction")),
        "latency_ms": latency_ms,
    }


async def eval_capture(state: OracleState) -> dict:
    """Write the trace row. Degrades silently if eval is off or the DB is down."""
    if not get_settings().eval_enabled:
        return {}
    try:
        from sports_oracle_db import repository as repo  # type: ignore
        from sports_oracle_db.session import get_session_factory  # type: ignore

        fields = build_trace_fields(state)
        async with get_session_factory()() as session:
            await repo.insert_trace(session, **fields)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Eval capture skipped (non-fatal): %s", exc)
    return {}
