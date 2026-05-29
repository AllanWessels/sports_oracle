"""Wire the LangGraph StateGraph for the Sports Oracle agent.

Flow:
    START -> classify_and_cache
        (cache hit)   -> stream_cached -> persist_and_cache -> eval_capture -> END
        (factual)     -> [gather || retrieve] -> synthesize -> persist_and_cache -> ... -> END
        (prediction)  -> gather_predict -> reason_predict -> synthesize -> ... -> END
        (chitchat)    -> synthesize -> persist_and_cache -> eval_capture -> END

eval_capture records one trace per turn (free, graceful) for the eval + routing
dashboards; the async judge worker scores it later.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.cache import persist_and_cache, stream_cached
from app.agent.nodes.eval_capture import eval_capture
from app.agent.nodes.predict import gather_predict, reason_predict
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.router import classify_and_cache
from app.agent.nodes.synthesize import synthesize
from app.agent.nodes.tools import gather
from app.agent.state import OracleState


def route_after_classify(state: OracleState) -> list[str]:
    """Fan-out decision. Returning a list triggers parallel branches."""
    if state.get("cache_hit"):
        return ["stream_cached"]
    intent = state.get("intent", "factual")
    if intent == "prediction":
        return ["gather_predict"]
    if intent == "chitchat":
        return ["synthesize"]
    # factual: gather tool data and RAG context in parallel
    return ["gather", "retrieve"]


def build_graph(checkpointer=None):
    g = StateGraph(OracleState)

    g.add_node("classify_and_cache", classify_and_cache)
    g.add_node("stream_cached", stream_cached)
    g.add_node("gather", gather)
    g.add_node("retrieve", retrieve)
    g.add_node("gather_predict", gather_predict)
    g.add_node("reason_predict", reason_predict)
    g.add_node("synthesize", synthesize)
    g.add_node("persist_and_cache", persist_and_cache)
    g.add_node("eval_capture", eval_capture)

    g.add_edge(START, "classify_and_cache")
    g.add_conditional_edges(
        "classify_and_cache",
        route_after_classify,
        ["stream_cached", "gather", "retrieve", "gather_predict", "synthesize"],
    )

    # factual branches converge on synthesize (join)
    g.add_edge("gather", "synthesize")
    g.add_edge("retrieve", "synthesize")

    # prediction branch
    g.add_edge("gather_predict", "reason_predict")
    g.add_edge("reason_predict", "synthesize")

    # tails
    g.add_edge("synthesize", "persist_and_cache")
    g.add_edge("stream_cached", "persist_and_cache")
    # capture runs last so it sees the saved conversation_id + full final state
    g.add_edge("persist_and_cache", "eval_capture")
    g.add_edge("eval_capture", END)

    return g.compile(checkpointer=checkpointer)
