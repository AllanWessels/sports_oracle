"""Pure aggregation helpers over captured eval traces.

A "trace" here is a plain dict (or any mapping) with at least the keys written
by the capture node: ``intent``, ``cache_hit``, ``route``, ``latency_ms``,
``num_tool_results``, and the nullable RAGAS score columns. These functions are
used both by the ``run.py`` scorecard and (independently re-implemented in SQL)
by the metrics API; keeping a pure-Python version makes them unit-testable and
usable offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sports_oracle_eval.schema import RAGAS_METRICS

Trace = Mapping[str, Any]


def _percentile(values: Sequence[float], pct: float) -> float | None:
    """Nearest-rank percentile (pct in 0..100). None for empty input."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = max(0, min(len(s) - 1, round((pct / 100.0) * (len(s) - 1))))
    return float(s[rank])


def route_of(trace: Trace) -> str:
    """Derive the route label for a trace.

    Prefers an explicit ``route`` field; otherwise reconstructs it from
    ``cache_hit`` / ``intent`` exactly like the graph's ``route_after_classify``.
    """
    if trace.get("route"):
        return str(trace["route"])
    if trace.get("cache_hit"):
        return "cache"
    intent = trace.get("intent") or "factual"
    return str(intent)


def routing_aggregates(traces: Sequence[Trace]) -> dict[str, Any]:
    """Traffic + effectiveness aggregates, grouped by route.

    Returns total count, per-route count/percentage/latency, overall cache-hit
    rate and tool-call rate — i.e. "what % of traffic is routed where, and how
    is each route performing".
    """
    total = len(traces)
    by_route: dict[str, list[Trace]] = {}
    for t in traces:
        by_route.setdefault(route_of(t), []).append(t)

    routes: dict[str, Any] = {}
    for route, items in sorted(by_route.items()):
        latencies = [float(t["latency_ms"]) for t in items if t.get("latency_ms") is not None]
        routes[route] = {
            "count": len(items),
            "pct": round(100.0 * len(items) / total, 2) if total else 0.0,
            "latency_ms_p50": _percentile(latencies, 50),
            "latency_ms_p95": _percentile(latencies, 95),
            "avg_tool_results": (
                round(sum(int(t.get("num_tool_results", 0) or 0) for t in items) / len(items), 2)
                if items
                else 0.0
            ),
        }

    cache_hits = sum(1 for t in traces if t.get("cache_hit"))
    used_tools = sum(1 for t in traces if int(t.get("num_tool_results", 0) or 0) > 0)
    return {
        "total": total,
        "routes": routes,
        "cache_hit_rate": round(cache_hits / total, 4) if total else 0.0,
        "tool_call_rate": round(used_tools / total, 4) if total else 0.0,
    }


def eval_aggregates(traces: Sequence[Trace]) -> dict[str, Any]:
    """Mean of each RAGAS metric + citation-validity rate over judged traces."""
    means: dict[str, float | None] = {}
    for metric in RAGAS_METRICS:
        vals = [float(t[metric]) for t in traces if t.get(metric) is not None]
        means[metric] = round(sum(vals) / len(vals), 4) if vals else None

    judged = [t for t in traces if t.get("judged_at") is not None]
    cit_vals = [bool(t["citation_valid"]) for t in traces if t.get("citation_valid") is not None]
    return {
        "judged": len(judged),
        "pending": len(traces) - len(judged),
        "means": means,
        "citation_valid_rate": (
            round(sum(1 for v in cit_vals if v) / len(cit_vals), 4) if cit_vals else None
        ),
    }
