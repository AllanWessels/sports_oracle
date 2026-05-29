"""Embedding and reranking singletons via fastembed.

GPU selection logic
-------------------
- ``EMBED_DEVICE=cuda``  → always use CUDA providers
- ``EMBED_DEVICE=auto``  → probe for a CUDA device; use CUDA if found, else CPU
- ``EMBED_DEVICE=cpu``   → always CPU

fastembed's GPU support is exposed via:
  TextEmbedding(model_name=..., providers=[...])
  SparseTextEmbedding(model_name=..., cuda=True)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    from fastembed.sparse import SparseTextEmbedding
    from sports_oracle_shared.rag import RagChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device resolution
# ---------------------------------------------------------------------------


def _use_cuda() -> bool:
    """Determine whether to use CUDA based on EMBED_DEVICE and availability."""
    device = settings.embed_device

    if device == "cpu":
        logger.info("RAG embeddings: device=cpu (forced by EMBED_DEVICE=cpu)")
        return False

    if device == "cuda":
        logger.info("RAG embeddings: device=cuda (forced by EMBED_DEVICE=cuda)")
        return True

    # device == "auto" — probe
    try:
        import onnxruntime as ort  # fastembed uses onnxruntime under the hood

        available = [ep for ep in ort.get_available_providers() if "CUDA" in ep]
        if available:
            logger.info(
                "RAG embeddings: device=cuda (auto-detected CUDA providers: %s)",
                available,
            )
            return True
    except Exception:
        pass

    logger.info("RAG embeddings: device=cpu (auto, no CUDA device found)")
    return False


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_dense_encoder: TextEmbedding | None = None
_sparse_encoder: SparseTextEmbedding | None = None
_reranker: TextCrossEncoder | None = None
_cuda: bool | None = None  # cached result of _use_cuda()


def _get_cuda() -> bool:
    global _cuda
    if _cuda is None:
        _cuda = _use_cuda()
    return _cuda


def get_dense_encoder() -> TextEmbedding:
    global _dense_encoder
    if _dense_encoder is None:
        from fastembed import TextEmbedding

        cuda = _get_cuda()
        if cuda:
            _dense_encoder = TextEmbedding(
                model_name=settings.embed_model,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
        else:
            _dense_encoder = TextEmbedding(model_name=settings.embed_model)

        logger.info(
            "Dense encoder loaded: %s (cuda=%s)", settings.embed_model, cuda
        )
    return _dense_encoder


def get_sparse_encoder() -> SparseTextEmbedding:
    global _sparse_encoder
    if _sparse_encoder is None:
        from fastembed.sparse import SparseTextEmbedding

        cuda = _get_cuda()
        if cuda:
            _sparse_encoder = SparseTextEmbedding(
                model_name=settings.sparse_model,
                cuda=True,
            )
        else:
            _sparse_encoder = SparseTextEmbedding(model_name=settings.sparse_model)

        logger.info(
            "Sparse encoder loaded: %s (cuda=%s)", settings.sparse_model, cuda
        )
    return _sparse_encoder


def get_reranker() -> TextCrossEncoder:
    global _reranker
    if _reranker is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _reranker = TextCrossEncoder(model_name=settings.rerank_model)
        logger.info("Cross-encoder reranker loaded: %s", settings.rerank_model)
    return _reranker


# ---------------------------------------------------------------------------
# Public embedding functions
# ---------------------------------------------------------------------------


def embed_dense(texts: list[str]) -> list[list[float]]:
    """Return dense embeddings for a batch of texts.

    Processes in chunks of ``embed_batch_size`` and returns a flat list
    parallel to *texts*.
    """
    enc = get_dense_encoder()
    batch_size = settings.embed_batch_size
    results: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for emb in enc.embed(batch):
            results.append(emb.tolist())  # numpy → plain list

    return results


def embed_sparse(texts: list[str]) -> list[dict[int, float]]:
    """Return sparse embeddings (SPLADE) as {token_index: weight} dicts.

    Processes in chunks of ``embed_batch_size``.
    """
    enc = get_sparse_encoder()
    batch_size = settings.embed_batch_size
    results: list[dict[int, float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for sparse_emb in enc.embed(batch):
            # SparseEmbedding has .indices and .values arrays
            results.append(
                {
                    int(idx): float(val)
                    for idx, val in zip(
                        sparse_emb.indices, sparse_emb.values, strict=False
                    )
                }
            )

    return results


def rerank(
    query: str,
    chunks: list[RagChunk],
    *,
    top_n: int | None = None,
) -> list[RagChunk]:
    """Cross-encoder rerank *chunks* for *query*, returning at most *top_n*.

    The returned list is sorted by descending cross-encoder score and each
    chunk's ``.score`` field is updated to the cross-encoder score.
    """
    if not chunks:
        return []

    ranker = get_reranker()
    texts = [c.text for c in chunks]

    scores: list[float] = list(ranker.rerank(query, texts))

    scored_chunks = sorted(
        zip(scores, chunks, strict=False), key=lambda t: t[0], reverse=True
    )

    result = []
    for score, chunk in scored_chunks[:top_n]:
        result.append(chunk.model_copy(update={"score": float(score)}))

    return result
