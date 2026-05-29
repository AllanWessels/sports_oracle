"""Metrics API over a seeded in-memory eval_traces store."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from sports_oracle_db import repository as repo
from sports_oracle_db.models import Base

from app.api import routes_metrics
from app.api.routes_metrics import traffic_series


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        f1 = await repo.insert_trace(
            s, query="offside?", intent="factual", route="factual",
            answer="... [1]", num_tool_results=1,
            citations=[{"ref_num": 1, "source_type": "rag_doc", "provider": "d"}],
            contexts=[{"text": "law 11"}],
        )
        f2 = await repo.insert_trace(
            s, query="lakers?", intent="factual", route="factual",
            answer="... [1]", num_tool_results=2, contexts=[{"text": "box score"}],
        )
        await repo.insert_trace(s, query="more", intent="factual", route="factual", answer="x")
        await repo.insert_trace(
            s, query="arsenal v chelsea", intent="prediction", route="prediction", answer="pick"
        )
        await repo.insert_trace(
            s, query="cached", intent="factual", route="cache", answer="c", cache_hit=True
        )
        await repo.update_trace_scores(
            s, f1.id, judge_model="m",
            scores={"faithfulness": 1.0, "answer_relevancy": 0.8, "citation_valid": True},
        )
        await repo.update_trace_scores(
            s, f2.id, judge_model="m",
            scores={"faithfulness": 0.6, "answer_relevancy": 0.4, "citation_valid": False},
        )
        await s.commit()

    monkeypatch.setattr("sports_oracle_db.session.get_session_factory", lambda: factory)

    app = FastAPI()
    app.include_router(routes_metrics.router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest.mark.asyncio
async def test_routing_metrics(client):
    r = await client.get("/metrics/routing?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["routes"]["factual"]["count"] == 3
    assert body["routes"]["prediction"]["count"] == 1
    assert body["routes"]["cache"]["count"] == 1
    assert body["cache_hit_rate"] == 0.2  # 1/5
    assert body["tool_call_rate"] == 0.4  # 2/5 used tools
    assert body["series"]  # at least one time bucket


@pytest.mark.asyncio
async def test_eval_metrics(client):
    r = await client.get("/metrics/eval?hours=24")
    body = r.json()
    assert body["judged"] == 2
    assert body["pending"] == 3
    assert body["means"]["faithfulness"] == 0.8  # (1.0 + 0.6) / 2
    assert body["citation_valid_rate"] == 0.5  # 1 of 2 judged valid


@pytest.mark.asyncio
async def test_traces_drilldown_filtered_by_intent(client):
    r = await client.get("/metrics/traces?intent=prediction")
    traces = r.json()["traces"]
    assert len(traces) == 1
    assert traces[0]["intent"] == "prediction"


def test_traffic_series_buckets_by_hour():
    traces = [
        {"created_at": "2026-05-29T10:05:00+00:00", "route": "factual"},
        {"created_at": "2026-05-29T10:40:00+00:00", "route": "prediction"},
        {"created_at": "2026-05-29T11:10:00+00:00", "route": "factual"},
    ]
    series = traffic_series(traces, hours=24, bucket_minutes=60)
    assert len(series) == 2  # 10:00 and 11:00 buckets
    assert series[0]["total"] == 2
    assert series[0]["factual"] == 1
    assert series[0]["prediction"] == 1
    assert series[1]["total"] == 1
