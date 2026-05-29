"""RAG retrieval node: hybrid search over reference docs + news (+ cache)."""

from __future__ import annotations

import logging

from app.agent.state import OracleState

logger = logging.getLogger(__name__)


async def retrieve(state: OracleState) -> dict:
    """Retrieve supporting chunks from the reference and news collections.

    Uses the shared RAG library. Degrades gracefully to no hits if the RAG
    backend is unavailable so the agent can still answer from tool results.
    """
    query = state["query"]
    try:
        from sports_oracle_rag import hybrid_search  # type: ignore

        ref_hits = await hybrid_search(query, collection="reference_docs", top_k=4)
        news_hits = await hybrid_search(query, collection="news", top_k=3)
        hits = list(ref_hits) + list(news_hits)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG retrieval unavailable: %s", exc)
        hits = []

    logger.info("RAG retrieved %d chunks", len(hits))
    return {"rag_hits": hits}
