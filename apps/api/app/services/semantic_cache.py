"""Semantic cache: serve fresh prior answers for similar factual queries.

Backed by the RAG library's `sports_cache` Qdrant collection (vector similarity
+ TTL/expiry filter) and the DB cache-meta table for hit accounting. Degrades to
a miss whenever the backend is unavailable.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


async def lookup(query: str, entities: dict) -> Optional[dict]:
    """Return a cached answer payload if a fresh, sufficiently-similar one exists."""
    settings = get_settings()
    try:
        from sports_oracle_rag import hybrid_search  # type: ignore

        hits = await hybrid_search(
            query, collection="sports_cache", top_k=1, filters={"kind": "qa_answer"}
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Semantic cache unavailable: %s", exc)
        return None

    if not hits:
        return None
    top = hits[0]
    if top.score < settings.cache_sim_threshold:
        return None
    # Entity guard: don't serve a cached answer for a different team/sport.
    cached_sport = top.metadata.get("sport") if top.metadata else None
    if cached_sport and entities.get("sport") not in (None, "unknown", cached_sport):
        return None
    return {
        "answer": top.text,
        "citations": (top.metadata or {}).get("citations", []),
        "point_id": top.id,
    }


async def store(query: str, entities: dict, answer: str, citations: list) -> None:
    """Write-through: persist the answer to the cache collection with a TTL."""
    try:
        from sports_oracle_rag import upsert_cache_answer  # type: ignore

        await upsert_cache_answer(
            query=query,
            answer=answer,
            sport=entities.get("sport"),
            entities=entities,
            citations=[c.model_dump() if hasattr(c, "model_dump") else c for c in citations],
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Semantic cache write skipped: %s", exc)
