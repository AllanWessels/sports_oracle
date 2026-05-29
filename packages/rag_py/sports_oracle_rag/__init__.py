"""sports_oracle_rag — reusable RAG library for the Sports Oracle platform.

Public API
----------
Config
    :data:`config.settings`           RagSettings instance (pydantic-settings)

Embeddings
    :func:`embeddings.embed_dense`    list[str] → list[list[float]]
    :func:`embeddings.embed_sparse`   list[str] → list[dict[int,float]]
    :func:`embeddings.rerank`         (query, chunks, top_n?) → list[RagChunk]
    :func:`embeddings.get_dense_encoder`
    :func:`embeddings.get_sparse_encoder`
    :func:`embeddings.get_reranker`

Qdrant store (async)
    :func:`qdrant_store.ensure_collections`  () → None
    :func:`qdrant_store.upsert`              (collection, points) → None
    :func:`qdrant_store.hybrid_search`       (query, collection, *, top_k, filters) → list[RagChunk]
    :func:`qdrant_store.build_point`         (point_id, text, payload) → PointStruct
    :func:`qdrant_store.get_client`          () → AsyncQdrantClient

Chunking
    :func:`chunking.heading_aware_chunk`  (text, *, target_tokens, overlap_tokens, doc_title) → list[str]
    :func:`chunking.paragraph_chunk`      (text, *, min_tokens, max_tokens) → list[str]
    :func:`chunking.cache_summarize`      (data_dict, *, max_tokens) → str

Schema / helpers
    :data:`schema.COLLECTION_SPORTS_CACHE`
    :data:`schema.COLLECTION_REFERENCE_DOCS`
    :data:`schema.COLLECTION_NEWS`
    :class:`schema.DataClass`
    :func:`schema.expires_at`
    :func:`schema.is_expired`
    :class:`schema.SportsCachePayload`
    :class:`schema.ReferenceDocPayload`
    :class:`schema.NewsPayload`
"""

from .chunking import cache_summarize, heading_aware_chunk, paragraph_chunk
from .config import RagSettings, settings
from .embeddings import embed_dense, embed_sparse, rerank
from .qdrant_store import build_point, ensure_collections, get_client, hybrid_search, upsert
from .schema import (
    COLLECTION_NEWS,
    COLLECTION_REFERENCE_DOCS,
    COLLECTION_SPORTS_CACHE,
    DataClass,
    NewsPayload,
    ReferenceDocPayload,
    SportsCachePayload,
    expires_at,
    is_expired,
)

__all__ = [
    # config
    "RagSettings",
    "settings",
    # embeddings
    "embed_dense",
    "embed_sparse",
    "rerank",
    # qdrant store
    "ensure_collections",
    "upsert",
    "hybrid_search",
    "build_point",
    "get_client",
    # chunking
    "heading_aware_chunk",
    "paragraph_chunk",
    "cache_summarize",
    # schema
    "COLLECTION_SPORTS_CACHE",
    "COLLECTION_REFERENCE_DOCS",
    "COLLECTION_NEWS",
    "DataClass",
    "expires_at",
    "is_expired",
    "SportsCachePayload",
    "ReferenceDocPayload",
    "NewsPayload",
]
