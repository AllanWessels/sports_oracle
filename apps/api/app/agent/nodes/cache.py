"""Cache short-circuit + persist/write-through nodes."""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from app.agent.state import OracleState
from app.services import semantic_cache, persistence

logger = logging.getLogger(__name__)


async def stream_cached(state: OracleState) -> dict:
    """Serve the cached answer (the SSE route streams it out)."""
    hit = state.get("cache_hit") or {}
    answer = hit.get("answer", "")
    return {"answer": answer, "messages": [AIMessage(content=answer)], "citations": hit.get("citations", [])}


async def persist_and_cache(state: OracleState) -> dict:
    """Save the turn to Postgres and write the answer through to the semantic cache."""
    answer = state.get("answer", "")
    entities = state.get("entities", {})
    citations = state.get("citations", [])

    saved = await persistence.persist_turn(
        conversation_id=state.get("conversation_id"),
        user_message=state["query"],
        answer=answer,
        intent=state.get("intent", "factual"),
        citations=citations,
        prediction=state.get("prediction"),
    )

    # Only cache stable factual answers (not predictions / chitchat).
    if state.get("intent") == "factual" and answer and not state.get("cache_hit"):
        await semantic_cache.store(state["query"], entities, answer, citations)

    return {"conversation_id": saved["conversation_id"]}
