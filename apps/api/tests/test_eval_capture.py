"""Unit tests for the pure trace-field builder (no DB)."""

from __future__ import annotations

import time

from sports_oracle_shared import Citation, RagChunk

from app.agent.nodes.eval_capture import build_trace_fields


def _chunk(text: str, **kw) -> RagChunk:
    base = {"id": "c1", "text": text, "collection": "reference_docs", "score": 0.9}
    base.update(kw)
    return RagChunk(**base)


def test_factual_route_and_counts_and_latency():
    state = {
        "started_at": time.time() - 0.5,
        "query": "What are the offside rules?",
        "intent": "factual",
        "answer": "Offside is ... [1]",
        "rag_hits": [_chunk("law 11 text", source="offside.md")],
        "tool_results": [{"data": {"x": 1}}, {"data": None}],
        "citations": [Citation(ref_num=1, source_type="rag_doc", provider="offside.md")],
    }
    f = build_trace_fields(state)
    assert f["route"] == "factual"
    assert f["intent"] == "factual"
    assert f["cache_hit"] is False
    assert f["num_rag_hits"] == 1
    assert f["num_tool_results"] == 2
    assert f["contexts"][0] == {"text": "law 11 text", "source": "offside.md", "collection": "reference_docs"}
    assert f["citations"][0]["ref_num"] == 1  # pydantic dumped to dict
    assert f["latency_ms"] is not None and f["latency_ms"] >= 400


def test_cache_route_takes_precedence_over_intent():
    f = build_trace_fields({"intent": "factual", "cache_hit": {"answer": "x"}, "answer": "x"})
    assert f["route"] == "cache"
    assert f["cache_hit"] is True


def test_prediction_route_and_dumped_prediction():
    state = {
        "intent": "prediction",
        "answer": "Pick A",
        "prediction": {"pick": "A", "win_probability": 0.6},  # plain dict tolerated
    }
    f = build_trace_fields(state)
    assert f["route"] == "prediction"
    assert f["prediction"] == {"pick": "A", "win_probability": 0.6}


def test_chitchat_and_missing_started_at():
    f = build_trace_fields({"intent": "chitchat", "answer": "hello"})
    assert f["route"] == "chitchat"
    assert f["latency_ms"] is None  # no started_at -> no latency
    assert f["num_rag_hits"] == 0
    assert f["contexts"] == []
