"""Routing + eval aggregates — pure functions over trace dicts."""

from __future__ import annotations

from sports_oracle_eval.routing import eval_aggregates, route_of, routing_aggregates


def _trace(**kw):
    base = {"intent": "factual", "cache_hit": False, "latency_ms": 100, "num_tool_results": 0}
    base.update(kw)
    return base


def test_route_of_prefers_explicit_then_cache_then_intent():
    assert route_of({"route": "prediction"}) == "prediction"
    assert route_of({"cache_hit": True, "intent": "factual"}) == "cache"
    assert route_of({"intent": "chitchat"}) == "chitchat"
    assert route_of({}) == "factual"


def test_routing_aggregates_traffic_split_and_rates():
    traces = [
        _trace(intent="factual", num_tool_results=2, latency_ms=100),
        _trace(intent="factual", num_tool_results=0, latency_ms=300),
        _trace(intent="prediction", latency_ms=500),
        _trace(cache_hit=True, latency_ms=10),
    ]
    agg = routing_aggregates(traces)
    assert agg["total"] == 4
    assert agg["routes"]["factual"]["count"] == 2
    assert agg["routes"]["factual"]["pct"] == 50.0
    assert agg["routes"]["cache"]["count"] == 1
    assert agg["cache_hit_rate"] == 0.25
    # one of four traces used tools
    assert agg["tool_call_rate"] == 0.25
    assert agg["routes"]["factual"]["avg_tool_results"] == 1.0


def test_routing_aggregates_empty():
    agg = routing_aggregates([])
    assert agg == {"total": 0, "routes": {}, "cache_hit_rate": 0.0, "tool_call_rate": 0.0}


def test_eval_aggregates_means_and_pending():
    traces = [
        {"faithfulness": 1.0, "answer_relevancy": 0.8, "citation_valid": True, "judged_at": "t"},
        {"faithfulness": 0.6, "answer_relevancy": 0.4, "citation_valid": False, "judged_at": "t"},
        {"faithfulness": None},  # unjudged
    ]
    agg = eval_aggregates(traces)
    assert agg["judged"] == 2
    assert agg["pending"] == 1
    assert agg["means"]["faithfulness"] == 0.8
    assert agg["means"]["answer_relevancy"] == 0.6
    assert agg["means"]["context_precision"] is None
    assert agg["citation_valid_rate"] == 0.5
