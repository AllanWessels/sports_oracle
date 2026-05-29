"""Async Qdrant store: collection management, upsert, and hybrid search."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from sports_oracle_shared.rag import RagChunk

from .config import settings
from .embeddings import embed_dense, embed_sparse, rerank
from .schema import (
    COLLECTION_NEWS,
    COLLECTION_REFERENCE_DOCS,
    COLLECTION_SPORTS_CACHE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension constants
# ---------------------------------------------------------------------------

DENSE_DIM = 384          # BAAI/bge-small-en-v1.5
SPARSE_MAX_DIM = 30_522  # SPLADE vocab size (BERT vocab)

# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        kwargs: dict[str, Any] = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        _client = AsyncQdrantClient(**kwargs)
        logger.info("Qdrant async client created: %s", settings.qdrant_url)
    return _client


# ---------------------------------------------------------------------------
# Collection definitions
# ---------------------------------------------------------------------------

def _named_vectors_config() -> dict[str, models.VectorParams]:
    """Named vector params shared by all three collections."""
    return {
        "dense": models.VectorParams(
            size=DENSE_DIM,
            distance=models.Distance.COSINE,
        ),
    }


def _sparse_vectors_config() -> dict[str, models.SparseVectorParams]:
    return {
        "sparse": models.SparseVectorParams(
            index=models.SparseIndexParams(on_disk=False),
        ),
    }


async def ensure_collections() -> None:
    """Idempotently create the three collections if they do not exist."""
    client = get_client()
    existing = {c.name for c in (await client.get_collections()).collections}

    for name in (COLLECTION_SPORTS_CACHE, COLLECTION_REFERENCE_DOCS, COLLECTION_NEWS):
        if name in existing:
            logger.debug("Collection already exists: %s", name)
            continue

        await client.create_collection(
            collection_name=name,
            vectors_config=_named_vectors_config(),
            sparse_vectors_config=_sparse_vectors_config(),
        )
        logger.info("Created collection: %s", name)

    # Index expires_at for sports_cache TTL filtering
    sc_payload_schema = await client.get_collection(COLLECTION_SPORTS_CACHE)
    existing_indexes = set(
        sc_payload_schema.config.params.payload_schema or {}
    )
    if "expires_at" not in existing_indexes:
        try:
            await client.create_payload_index(
                collection_name=COLLECTION_SPORTS_CACHE,
                field_name="expires_at",
                field_schema=models.PayloadSchemaType.DATETIME,
            )
            logger.info("Created payload index on sports_cache.expires_at")
        except Exception as exc:
            logger.warning("Could not create expires_at index: %s", exc)

    # Index published_at for news recency queries
    news_info = await client.get_collection(COLLECTION_NEWS)
    existing_news_indexes = set(news_info.config.params.payload_schema or {})
    if "published_at" not in existing_news_indexes:
        try:
            await client.create_payload_index(
                collection_name=COLLECTION_NEWS,
                field_name="published_at",
                field_schema=models.PayloadSchemaType.DATETIME,
            )
            logger.info("Created payload index on news.published_at")
        except Exception as exc:
            logger.warning("Could not create published_at index: %s", exc)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def upsert(
    collection: str,
    points: list[models.PointStruct],
) -> None:
    """Upsert a batch of points into *collection*."""
    client = get_client()
    await client.upsert(collection_name=collection, points=points, wait=True)
    logger.debug("Upserted %d points to %s", len(points), collection)


def build_point(
    point_id: str,
    text: str,
    payload: dict[str, Any],
) -> models.PointStruct:
    """Helper: embed one text and return a PointStruct ready for upsert."""
    dense_vecs = embed_dense([text])
    sparse_vecs = embed_sparse([text])

    dense_vec = dense_vecs[0]
    sparse_map = sparse_vecs[0]

    return models.PointStruct(
        id=point_id,
        vector={
            "dense": dense_vec,
            "sparse": models.SparseVector(
                indices=list(sparse_map.keys()),
                values=list(sparse_map.values()),
            ),
        },
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Recency-decay score boost
# ---------------------------------------------------------------------------

_RECENCY_HALF_LIFE_DAYS = 7.0  # news score halves every 7 days


def _recency_boost(published_at: datetime | None) -> float:
    """Exponential decay boost: 1.0 when fresh, approaches 0 when old."""
    if published_at is None:
        return 0.5  # no date → neutral
    now = datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_days = max(0.0, (now - published_at).total_seconds() / 86400)
    return math.exp(-math.log(2) * age_days / _RECENCY_HALF_LIFE_DAYS)


# ---------------------------------------------------------------------------
# Hybrid search
# ---------------------------------------------------------------------------

async def hybrid_search(
    query: str,
    collection: str,
    *,
    top_k: int = 5,
    filters: models.Filter | None = None,
) -> list[RagChunk]:
    """Hybrid dense+sparse search with server-side RRF fusion and cross-encoder rerank.

    Parameters
    ----------
    query:
        The user query string.
    collection:
        One of ``sports_cache``, ``reference_docs``, ``news``.
    top_k:
        Number of final results to return after reranking.
    filters:
        Optional caller-supplied Qdrant filter merged with built-in filters.
    """
    client = get_client()
    candidates = settings.rerank_candidates

    # ---- embed query -------------------------------------------------------
    dense_vec = embed_dense([query])[0]
    sparse_map = embed_sparse([query])[0]

    # ---- build mandatory collection filters --------------------------------
    mandatory: list[models.Condition] = []

    if collection == COLLECTION_SPORTS_CACHE:
        now_iso = datetime.now(UTC).isoformat()
        mandatory.append(
            models.FieldCondition(
                key="expires_at",
                range=models.DatetimeRange(gt=now_iso),
            )
        )

    if filters is not None:
        combined_filter = models.Filter(
            must=(mandatory + (list(filters.must) if filters.must else [])),
        )
    else:
        combined_filter = models.Filter(must=mandatory) if mandatory else None

    # ---- prefetch over dense + sparse, fuse with RRF ----------------------
    prefetch = [
        models.Prefetch(
            query=dense_vec,
            using="dense",
            limit=candidates,
            filter=combined_filter,
        ),
        models.Prefetch(
            query=models.SparseVector(
                indices=list(sparse_map.keys()),
                values=list(sparse_map.values()),
            ),
            using="sparse",
            limit=candidates,
            filter=combined_filter,
        ),
    ]

    query_response = await client.query_points(
        collection_name=collection,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=candidates,
        with_payload=True,
    )

    points = query_response.points

    if not points:
        return []

    # ---- convert to RagChunk for reranker ----------------------------------
    chunks: list[RagChunk] = []
    for pt in points:
        payload: dict[str, Any] = pt.payload or {}
        base_score = pt.score or 0.0

        # Apply recency boost for news and sports_cache collections
        if collection in (COLLECTION_NEWS, COLLECTION_SPORTS_CACHE):
            pub_raw = payload.get("published_at") or payload.get("fetched_at")
            if pub_raw:
                try:
                    pub_dt = (
                        datetime.fromisoformat(pub_raw)
                        if isinstance(pub_raw, str)
                        else pub_raw
                    )
                    base_score = base_score * _recency_boost(pub_dt)
                except (ValueError, TypeError):
                    pass

        published_at: datetime | None = None
        fetched_at: datetime | None = None
        try:
            if payload.get("published_at"):
                raw = payload["published_at"]
                published_at = (
                    datetime.fromisoformat(raw) if isinstance(raw, str) else raw
                )
        except (ValueError, TypeError):
            pass
        try:
            if payload.get("fetched_at"):
                raw = payload["fetched_at"]
                fetched_at = (
                    datetime.fromisoformat(raw) if isinstance(raw, str) else raw
                )
        except (ValueError, TypeError):
            pass

        chunks.append(
            RagChunk(
                id=str(pt.id),
                text=payload.get("text", ""),
                collection=collection,
                score=base_score,
                title=payload.get("title"),
                url=payload.get("url"),
                source=payload.get("source"),
                sport=payload.get("sport"),
                published_at=published_at,
                fetched_at=fetched_at,
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k
                    not in {
                        "text",
                        "title",
                        "url",
                        "source",
                        "sport",
                        "published_at",
                        "fetched_at",
                        "chunk_id",
                    }
                },
            )
        )

    # ---- cross-encoder rerank ---------------------------------------------
    reranked = rerank(query, chunks, top_n=top_k)

    return reranked
