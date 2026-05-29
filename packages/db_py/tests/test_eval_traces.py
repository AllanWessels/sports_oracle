"""Eval-trace repository round-trips (SQLite in-memory)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sports_oracle_db import repository as repo


async def _insert(session, **over):
    fields = {
        "query": "Who won?",
        "intent": "factual",
        "route": "factual",
        "answer": "Team A [1].",
        "cache_hit": False,
        "num_tool_results": 1,
        "num_rag_hits": 2,
        "contexts": [{"text": "ctx", "source": "espn"}],
        "citations": [{"ref_num": 1, "source_type": "api", "provider": "espn"}],
        "prediction": None,
        "latency_ms": 1234,
    }
    fields.update(over)
    return await repo.insert_trace(session, **fields)


@pytest.mark.asyncio
async def test_insert_and_serialize(async_session):
    row = await _insert(async_session)
    assert row.id is not None
    d = repo.trace_to_dict(row)
    assert d["query"] == "Who won?"
    assert d["route"] == "factual"
    assert d["latency_ms"] == 1234
    assert d["num_rag_hits"] == 2
    assert d["contexts"][0]["text"] == "ctx"
    # unjudged on insert
    assert d["faithfulness"] is None
    assert d["judged_at"] is None


@pytest.mark.asyncio
async def test_get_unjudged_then_update_scores(async_session):
    row = await _insert(async_session)
    unjudged = await repo.get_unjudged_traces(async_session, limit=10)
    assert len(unjudged) == 1

    await repo.update_trace_scores(
        async_session,
        row.id,
        judge_model="claude-haiku-4-5",
        scores={"faithfulness": 0.9, "answer_relevancy": 0.8, "citation_valid": True},
    )
    # now judged -> excluded from the unjudged scan
    assert await repo.get_unjudged_traces(async_session) == []

    refreshed = (await repo.list_traces(async_session))[0]
    d = repo.trace_to_dict(refreshed)
    assert d["faithfulness"] == 0.9
    assert d["citation_valid"] is True
    assert d["judge_model"] == "claude-haiku-4-5"
    assert d["judged_at"] is not None
    # a score not supplied stays NULL
    assert d["context_recall"] is None


@pytest.mark.asyncio
async def test_list_traces_filters_intent_and_window(async_session):
    await _insert(async_session, intent="factual", route="factual")
    await _insert(async_session, intent="prediction", route="prediction")
    await _insert(async_session, intent="chitchat", route="chitchat")

    only_pred = await repo.list_traces(async_session, intent="prediction")
    assert len(only_pred) == 1
    assert only_pred[0].intent == "prediction"

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert await repo.list_traces(async_session, since=future) == []
    all_rows = await repo.list_traces(async_session, limit=2)
    assert len(all_rows) == 2  # limit respected
