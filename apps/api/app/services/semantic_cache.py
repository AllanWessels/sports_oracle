"""Semantic cache: serve fresh prior answers for similar factual queries.

Backed by the RAG library's `sports_cache` Qdrant collection (vector similarity
+ TTL/expiry filter built into hybrid_search). Degrades to a miss whenever the
backend is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# A down vector store must degrade fast, not stall the request on client retries.
_BACKEND_TIMEOUT_S = 3.0


async def lookup(query: str, entities: dict) -> Optional[dict]:
    """Return a cached answer payload if a fresh, similar QA answer exists."""
    settings = get_settings()
    try:
        from qdrant_client import models as qmodels  # type: ignore
        from sports_oracle_rag import hybrid_search  # type: ignore
        from sports_oracle_rag.schema import COLLECTION_SPORTS_CACHE  # type: ignore

        flt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="data_class", match=qmodels.MatchValue(value="qa_answer")
                )
            ]
        )
        hits = await asyncio.wait_for(
            hybrid_search(query, COLLECTION_SPORTS_CACHE, top_k=1, filters=flt),
            timeout=_BACKEND_TIMEOUT_S,
        )
    except (Exception, asyncio.TimeoutError) as exc:  # noqa: BLE001
        logger.debug("Semantic cache unavailable: %s", exc)
        return None

    if not hits:
        return None
    top = hits[0]
    if top.score < settings.cache_sim_threshold:
        return None
    # Entity guard: don't serve a cached answer for a different sport.
    if top.sport and entities.get("sport") not in (None, "unknown", top.sport):
        return None
    extra = (top.metadata or {}).get("metadata", {})
    return {
        "answer": top.text,
        "citations": extra.get("citations", []),
        "point_id": top.id,
    }


async def store(query: str, entities: dict, answer: str, citations: list) -> None:
    """Write-through: persist the answer to the cache collection with a TTL."""
    try:
        from sports_oracle_rag import build_point, upsert  # type: ignore
        from sports_oracle_rag.schema import (  # type: ignore
            COLLECTION_SPORTS_CACHE,
            DataClass,
            SportsCachePayload,
        )

        sport = entities.get("sport") if entities.get("sport") != "unknown" else None
        payload = SportsCachePayload.build(
            text=answer,
            data_class=DataClass.QA_ANSWER,
            sport=sport,
            metadata={
                "query": query,
                "entities": entities,
                "citations": [
                    c.model_dump(mode="json") if hasattr(c, "model_dump") else c
                    for c in citations
                ],
            },
        ).model_dump(mode="json")
        point = build_point(str(uuid.uuid4()), answer, payload)
        await upsert(COLLECTION_SPORTS_CACHE, [point])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Semantic cache write skipped: %s", exc)
