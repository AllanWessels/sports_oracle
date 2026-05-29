"""In-process integration test: drive a full factual turn through the graph.

Claude and the MCP tools are mocked; the DB and RAG backends are absent and
therefore degrade gracefully (cache miss, no retrieval, unsaved ids). This
verifies the router -> gather -> synthesize -> persist wiring and that an answer
plus citations fall out the end.
"""

from __future__ import annotations

import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")


class _FakeModel:
    """Stand-in for a ChatAnthropic model returning a canned response."""

    def __init__(self, response: AIMessage):
        self._response = response

    def bind_tools(self, tools):  # noqa: ANN001
        return self

    def with_config(self, *_a, **_k):
        return self

    async def ainvoke(self, *_a, **_k):
        return self._response


@pytest.mark.asyncio
async def test_factual_turn_produces_answer_and_citation(monkeypatch):
    from app.agent import graph as graph_mod
    from app.agent.nodes import router as router_node
    from app.agent.nodes import synthesize as synth_node
    from app.agent.nodes import tools as tools_node
    from app.mcp import client as mcp_client
    from app.services import semantic_cache

    # Keep the test hermetic: no real vector store / embedding model.
    async def _no_cache(*_a, **_k):
        return None

    async def _no_rag(_state):
        return {"rag_hits": []}

    async def _no_store(*_a, **_k):
        return None

    monkeypatch.setattr(semantic_cache, "lookup", _no_cache)
    monkeypatch.setattr(semantic_cache, "store", _no_store)
    # The graph binds `retrieve` by reference at build time, so patch it there.
    monkeypatch.setattr(graph_mod, "retrieve", _no_rag)

    # Router classifies the query as factual soccer with no tool calls needed.
    monkeypatch.setattr(
        router_node,
        "router_model",
        lambda: _FakeModel(AIMessage(content='{"intent":"factual","sport":"soccer","teams":["Arsenal"]}')),
    )
    # No MCP tools loaded -> gather loop makes no calls but still runs.
    monkeypatch.setattr(mcp_client, "get_tools", lambda: [])
    monkeypatch.setattr(tools_node, "predict_model", lambda: _FakeModel(AIMessage(content="done")))
    # Synthesis returns the final grounded answer.
    monkeypatch.setattr(
        synth_node,
        "synth_model",
        lambda: _FakeModel(AIMessage(content="Arsenal play in the Premier League. [1]")),
    )

    g = graph_mod.build_graph(checkpointer=None)
    state = await g.ainvoke(
        {"query": "Tell me about Arsenal", "messages": [HumanMessage(content="Tell me about Arsenal")]},
        config={"configurable": {"thread_id": "test"}},
    )

    assert state["intent"] == "factual"
    assert "Arsenal" in state["answer"]
    # persist_and_cache ran and produced a conversation id even without a live DB.
    assert state.get("conversation_id")
