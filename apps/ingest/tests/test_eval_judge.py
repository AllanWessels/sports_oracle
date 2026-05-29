"""Hermetic test for the async eval judge (fake RAGAS runner, SQLite traces)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sports_oracle_db import repository as repo
from sports_oracle_db.models import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from jobs.eval_judge import _sample, judge_once


@pytest_asyncio.fixture
async def factory():
    # StaticPool keeps a single in-memory connection so data seeded in one
    # session is visible to the separate session judge_once opens.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def test_sample_leading_fraction():
    rows = [1, 2, 3, 4]
    assert _sample(rows, 1.0) == rows
    assert _sample(rows, 0.5) == [1, 2]
    assert _sample(rows, 0.0) == []
    assert _sample([], 0.5) == []


@pytest.mark.asyncio
async def test_judge_scores_factual_and_citation_only_chitchat(factory):
    async with factory() as s:
        await repo.insert_trace(
            s,
            query="What are the offside rules?",
            intent="factual",
            route="factual",
            answer="Offside means ... [1]",
            contexts=[{"text": "Law 11 ...", "source": "offside.md"}],
            citations=[{"ref_num": 1, "source_type": "rag_doc", "provider": "offside.md"}],
        )
        await repo.insert_trace(
            s, query="hi", intent="chitchat", route="chitchat", answer="hello!", contexts=[]
        )
        await s.commit()

    def fake_runner(records, judge_model):
        assert judge_model == "claude-haiku-4-5"
        return {"faithfulness": 0.9, "answer_relevancy": 0.8}

    n = await judge_once(
        judge_model="claude-haiku-4-5", session_factory=factory, runner=fake_runner
    )
    assert n == 2

    async with factory() as s:
        rows = {r.intent: r for r in await repo.list_traces(s)}
        # all judged now
        assert await repo.get_unjudged_traces(s) == []

    factual = rows["factual"]
    assert factual.faithfulness == 0.9
    assert factual.answer_relevancy == 0.8
    assert factual.citation_valid is True
    assert factual.judge_model == "claude-haiku-4-5"

    chitchat = rows["chitchat"]
    # no contexts -> RAGAS skipped, but the deterministic citation check still runs
    assert chitchat.faithfulness is None
    assert chitchat.citation_valid is True  # no markers, no citations -> valid


@pytest.mark.asyncio
async def test_judge_marks_orphan_citation_invalid(factory):
    async with factory() as s:
        await repo.insert_trace(
            s, query="q", intent="factual", route="factual",
            answer="claim [3]", contexts=[], citations=[],
        )
        await s.commit()

    n = await judge_once(judge_model="m", session_factory=factory, runner=lambda r, j: {})
    assert n == 1
    async with factory() as s:
        row = (await repo.list_traces(s))[0]
        assert row.citation_valid is False  # [3] has no matching citation
