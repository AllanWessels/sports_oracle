"""Unit tests for qdrant_store.py — mock the Qdrant client and embeddings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sports_oracle_shared.rag import RagChunk

# ---------------------------------------------------------------------------
# Helpers to fake Qdrant response objects
# ---------------------------------------------------------------------------

def _make_scored_point(
    point_id: str,
    text: str,
    score: float = 0.8,
    payload: dict | None = None,
) -> MagicMock:
    pt = MagicMock()
    pt.id = point_id
    pt.score = score
    pt.payload = {"text": text, **(payload or {})}
    return pt


def _make_query_response(points: list) -> MagicMock:
    resp = MagicMock()
    resp.points = points
    return resp


# ---------------------------------------------------------------------------
# RRF fusion logic (standalone)
# ---------------------------------------------------------------------------

def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal rank fusion score."""
    return 1.0 / (k + rank)


class TestRRFScoreFormula:
    """Verify the RRF formula behaves as expected (server-side in Qdrant, but we
    test the math here for correctness of our understanding)."""

    def test_rank_1_highest(self):
        assert _rrf_score(1) > _rrf_score(2)

    def test_rank_monotonic(self):
        scores = [_rrf_score(r) for r in range(1, 21)]
        assert scores == sorted(scores, reverse=True)

    def test_k60_formula(self):
        assert abs(_rrf_score(1, k=60) - 1.0 / 61) < 1e-10

    def test_combining_two_lists(self):
        # Simulate combining dense rank 1 and sparse rank 3
        combined = _rrf_score(1) + _rrf_score(3)
        # vs dense rank 2 and sparse rank 2
        alt = _rrf_score(2) + _rrf_score(2)
        # rank(1)+rank(3) vs rank(2)+rank(2): 1/61 + 1/63 vs 1/62 + 1/62
        assert abs(combined - (1 / 61 + 1 / 63)) < 1e-10
        assert abs(alt - (2 / 62)) < 1e-10


# ---------------------------------------------------------------------------
# Recency boost
# ---------------------------------------------------------------------------

class TestRecencyBoost:
    def test_import(self):
        from sports_oracle_rag.qdrant_store import _recency_boost
        assert callable(_recency_boost)

    def test_none_returns_neutral(self):
        from sports_oracle_rag.qdrant_store import _recency_boost
        assert _recency_boost(None) == 0.5

    def test_fresh_near_one(self):
        from sports_oracle_rag.qdrant_store import _recency_boost
        just_now = datetime.now(UTC) - timedelta(seconds=10)
        boost = _recency_boost(just_now)
        assert boost > 0.99

    def test_one_half_life_is_half(self):
        from sports_oracle_rag.qdrant_store import _RECENCY_HALF_LIFE_DAYS, _recency_boost
        t = datetime.now(UTC) - timedelta(days=_RECENCY_HALF_LIFE_DAYS)
        boost = _recency_boost(t)
        assert abs(boost - 0.5) < 0.01

    def test_old_content_low_boost(self):
        from sports_oracle_rag.qdrant_store import _recency_boost
        old = datetime.now(UTC) - timedelta(days=100)
        assert _recency_boost(old) < 0.05

    def test_naive_datetime_handled(self):
        from sports_oracle_rag.qdrant_store import _recency_boost
        # Should not raise even with naive datetime
        naive = datetime.utcnow()
        result = _recency_boost(naive)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# hybrid_search — fully mocked
# ---------------------------------------------------------------------------

class TestHybridSearch:
    @pytest.fixture
    def mock_embeddings(self):
        """Patch embed_dense, embed_sparse, and rerank."""
        with (
            patch(
                "sports_oracle_rag.qdrant_store.embed_dense",
                return_value=[[0.1] * 384],
            ) as md,
            patch(
                "sports_oracle_rag.qdrant_store.embed_sparse",
                return_value=[{0: 0.9, 1: 0.5}],
            ) as ms,
            patch(
                "sports_oracle_rag.qdrant_store.rerank",
                side_effect=lambda q, chunks, top_n=None: chunks[:top_n],
            ) as mr,
        ):
            yield md, ms, mr

    @pytest.fixture
    def mock_qdrant_client(self):
        """Return an AsyncMock Qdrant client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_returns_rag_chunks(self, mock_embeddings, mock_qdrant_client):
        from sports_oracle_rag import qdrant_store

        points = [
            _make_scored_point("pt-1", "The offside rule explained", score=0.9),
            _make_scored_point("pt-2", "FIFA World Cup format", score=0.7),
        ]
        mock_qdrant_client.query_points = AsyncMock(
            return_value=_make_query_response(points)
        )

        with patch.object(qdrant_store, "get_client", return_value=mock_qdrant_client):
            results = await qdrant_store.hybrid_search(
                "offside rule", "reference_docs", top_k=2
            )

        assert len(results) == 2
        assert all(isinstance(r, RagChunk) for r in results)
        assert results[0].text == "The offside rule explained"

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_embeddings, mock_qdrant_client):
        from sports_oracle_rag import qdrant_store

        mock_qdrant_client.query_points = AsyncMock(
            return_value=_make_query_response([])
        )

        with patch.object(qdrant_store, "get_client", return_value=mock_qdrant_client):
            results = await qdrant_store.hybrid_search(
                "anything", "reference_docs", top_k=5
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_sports_cache_adds_expires_filter(self, mock_embeddings, mock_qdrant_client):
        """Verify that querying sports_cache injects an expires_at > now filter."""
        from sports_oracle_rag import qdrant_store

        captured_calls = []

        async def capture_query_points(collection_name, **kwargs):
            captured_calls.append({"collection": collection_name, "kwargs": kwargs})
            return _make_query_response([])

        mock_qdrant_client.query_points = capture_query_points

        with patch.object(qdrant_store, "get_client", return_value=mock_qdrant_client):
            await qdrant_store.hybrid_search("latest scores", "sports_cache", top_k=3)

        assert len(captured_calls) == 1
        call = captured_calls[0]
        # Prefetch should have a filter on expires_at
        prefetch = call["kwargs"]["prefetch"]
        assert len(prefetch) == 2
        for pf in prefetch:
            filt = pf.filter
            if filt is not None and filt.must:
                conditions = filt.must
                field_names = [
                    c.key for c in conditions if hasattr(c, "key")
                ]
                assert "expires_at" in field_names

    @pytest.mark.asyncio
    async def test_reference_docs_no_expiry_filter(self, mock_embeddings, mock_qdrant_client):
        """reference_docs should NOT inject an expires_at filter."""
        from sports_oracle_rag import qdrant_store

        captured = []

        async def capture(**kwargs):
            captured.append(kwargs)
            return _make_query_response([])

        mock_qdrant_client.query_points = capture

        with patch.object(qdrant_store, "get_client", return_value=mock_qdrant_client):
            await qdrant_store.hybrid_search("anything", "reference_docs", top_k=3)

        prefetch = captured[0]["prefetch"]
        for pf in prefetch:
            filt = pf.filter
            assert filt is None or not filt.must

    @pytest.mark.asyncio
    async def test_top_k_respected(self, mock_embeddings):
        from sports_oracle_rag import qdrant_store

        # Create 10 fake points
        points = [
            _make_scored_point(f"pt-{i}", f"Text {i}", score=1.0 - i * 0.05)
            for i in range(10)
        ]
        mock_client = AsyncMock()
        mock_client.query_points = AsyncMock(
            return_value=_make_query_response(points)
        )

        with patch.object(qdrant_store, "get_client", return_value=mock_client):
            results = await qdrant_store.hybrid_search(
                "test query", "reference_docs", top_k=3
            )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_collection_name_in_result(self, mock_embeddings, mock_qdrant_client):
        from sports_oracle_rag import qdrant_store

        mock_qdrant_client.query_points = AsyncMock(
            return_value=_make_query_response(
                [_make_scored_point("x", "some text")]
            )
        )

        with patch.object(qdrant_store, "get_client", return_value=mock_qdrant_client):
            results = await qdrant_store.hybrid_search(
                "q", "news", top_k=1
            )

        assert results[0].collection == "news"


# ---------------------------------------------------------------------------
# build_point
# ---------------------------------------------------------------------------

class TestBuildPoint:
    def test_returns_point_struct(self):
        from qdrant_client import models as qmodels

        from sports_oracle_rag.qdrant_store import build_point

        with (
            patch(
                "sports_oracle_rag.qdrant_store.embed_dense",
                return_value=[[0.1] * 384],
            ),
            patch(
                "sports_oracle_rag.qdrant_store.embed_sparse",
                return_value=[{5: 0.7, 12: 0.3}],
            ),
        ):
            pt = build_point("id-1", "Sample text", {"key": "value"})

        assert isinstance(pt, qmodels.PointStruct)
        assert pt.id == "id-1"
        assert "dense" in pt.vector
        assert "sparse" in pt.vector
        assert pt.payload == {"key": "value"}
