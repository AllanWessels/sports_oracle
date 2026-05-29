"""Unit tests for repository logic — runs against SQLite in-memory."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from sports_oracle_shared.agent import Citation as CitationDTO
from sports_oracle_shared.agent import Prediction as PredictionDTO
from sports_oracle_shared.agent import PredictionFactor
from sports_oracle_shared.enums import ConfidenceLabel, Intent

from sports_oracle_db.repository import (
    add_citations,
    add_message,
    add_prediction,
    bump_cache_hit,
    citation_to_dto,
    create_conversation,
    find_fresh_cache_meta,
    get_conversation,
    get_messages,
    list_conversations,
    prediction_to_dto,
    record_cache_meta,
    touch_conversation,
)


# ---------------------------------------------------------------------------
# Conversation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_conversation_no_title(async_session):
    conv = await create_conversation(async_session)
    assert conv.id is not None
    assert conv.title is None


@pytest.mark.asyncio
async def test_create_conversation_with_title(async_session):
    conv = await create_conversation(async_session, title="Premier League")
    assert conv.title == "Premier League"


@pytest.mark.asyncio
async def test_get_conversation(async_session):
    conv = await create_conversation(async_session, title="Test")
    fetched = await get_conversation(async_session, conv.id)
    assert fetched is not None
    assert fetched.title == "Test"


@pytest.mark.asyncio
async def test_get_conversation_missing(async_session):
    result = await get_conversation(async_session, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_list_conversations(async_session):
    await create_conversation(async_session, title="A")
    await create_conversation(async_session, title="B")
    convs = await list_conversations(async_session)
    assert len(convs) >= 2


@pytest.mark.asyncio
async def test_touch_conversation(async_session):
    conv = await create_conversation(async_session, title="Old title")
    await touch_conversation(async_session, conv.id, title="New title")
    fetched = await get_conversation(async_session, conv.id)
    assert fetched is not None
    assert fetched.title == "New title"


# ---------------------------------------------------------------------------
# Message / idx auto-increment tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_message_auto_idx_starts_at_zero(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "user", "Hello")
    assert msg.idx == 0


@pytest.mark.asyncio
async def test_add_message_auto_idx_increments(async_session):
    conv = await create_conversation(async_session)
    m0 = await add_message(async_session, conv.id, "user", "Hello")
    m1 = await add_message(async_session, conv.id, "assistant", "Hi there")
    m2 = await add_message(async_session, conv.id, "user", "Follow-up")
    assert m0.idx == 0
    assert m1.idx == 1
    assert m2.idx == 2


@pytest.mark.asyncio
async def test_add_message_explicit_idx(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "system", "Context", idx=5)
    assert msg.idx == 5


@pytest.mark.asyncio
async def test_add_message_independent_per_conversation(async_session):
    """Idx counters are per-conversation and don't bleed between them."""
    conv_a = await create_conversation(async_session)
    conv_b = await create_conversation(async_session)
    await add_message(async_session, conv_a.id, "user", "A0")
    await add_message(async_session, conv_a.id, "assistant", "A1")
    b0 = await add_message(async_session, conv_b.id, "user", "B0")
    assert b0.idx == 0


@pytest.mark.asyncio
async def test_add_message_stores_intent(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "user", "Who wins?", intent=Intent.PREDICTION)
    assert msg.intent == "prediction"


@pytest.mark.asyncio
async def test_get_messages_ordered(async_session):
    conv = await create_conversation(async_session)
    await add_message(async_session, conv.id, "user", "first")
    await add_message(async_session, conv.id, "assistant", "second")
    await add_message(async_session, conv.id, "user", "third")
    msgs = await get_messages(async_session, conv.id)
    assert [m.content for m in msgs] == ["first", "second", "third"]
    assert [m.idx for m in msgs] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Citation mapping tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_citations_and_round_trip(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "assistant", "Answer")

    dtos = [
        CitationDTO(
            ref_num=1,
            source_type="api",
            provider="sportradar",
            endpoint="/v4/standings",
            url="https://example.com/standings",
            fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            snippet="Manchester City leads the table...",
        ),
        CitationDTO(
            ref_num=2,
            source_type="rag_doc",
            provider="doc-abc123",
        ),
    ]
    rows = await add_citations(async_session, msg.id, dtos)
    assert len(rows) == 2

    # round-trip
    back = [citation_to_dto(r) for r in rows]
    assert back[0].ref_num == 1
    assert back[0].source_type == "api"
    assert back[0].provider == "sportradar"
    assert back[0].snippet == "Manchester City leads the table..."
    assert back[1].ref_num == 2
    assert back[1].endpoint is None


@pytest.mark.asyncio
async def test_citation_dto_optional_fields_preserved(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "assistant", "Answer")

    dto = CitationDTO(ref_num=3, source_type="rag_news", provider="newsapi", url=None)
    rows = await add_citations(async_session, msg.id, [dto])
    back = citation_to_dto(rows[0])
    assert back.url is None
    assert back.fetched_at is None


# ---------------------------------------------------------------------------
# Prediction mapping tests
# ---------------------------------------------------------------------------


def _make_prediction_dto() -> PredictionDTO:
    return PredictionDTO(
        sport="soccer",
        fixture_ref="EPL-2026-MCI-ARS",
        pick="Manchester City",
        win_probability=0.62,
        confidence_num=0.70,
        confidence_label=ConfidenceLabel.HIGH,
        key_factors=[
            PredictionFactor(
                name="Home advantage",
                direction="home",
                weight=0.4,
                detail="City have won 9 of last 10 home fixtures.",
            ),
            PredictionFactor(
                name="Recent form",
                direction="home",
                weight=0.6,
            ),
        ],
        caveats=["Arsenal missing Saka", "Short turnaround"],
        data_completeness=0.9,
    )


@pytest.mark.asyncio
async def test_add_prediction_and_round_trip(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "assistant", "Prediction answer")

    dto = _make_prediction_dto()
    row = await add_prediction(async_session, msg.id, dto)

    assert row.sport == "soccer"
    assert row.fixture_ref == "EPL-2026-MCI-ARS"
    assert row.pick == "Manchester City"
    assert float(row.win_probability) == pytest.approx(0.62, abs=1e-4)
    assert float(row.confidence_num) == pytest.approx(0.70, abs=1e-4)
    assert row.confidence_label == "high"

    # factors stored as jsonb list
    assert isinstance(row.factors, list)
    assert len(row.factors) == 2
    assert row.factors[0]["name"] == "Home advantage"

    # caveats stored as jsonb list
    assert row.caveats == ["Arsenal missing Saka", "Short turnaround"]


@pytest.mark.asyncio
async def test_prediction_round_trip_dto(async_session):
    conv = await create_conversation(async_session)
    msg = await add_message(async_session, conv.id, "assistant", "Answer")

    original = _make_prediction_dto()
    row = await add_prediction(async_session, msg.id, original)
    restored = prediction_to_dto(row)

    assert restored.sport == original.sport
    assert restored.fixture_ref == original.fixture_ref
    assert restored.pick == original.pick
    assert restored.win_probability == pytest.approx(original.win_probability, abs=1e-4)
    assert restored.confidence_label == ConfidenceLabel.HIGH
    assert len(restored.key_factors) == 2
    assert restored.key_factors[0].name == "Home advantage"
    assert restored.key_factors[0].weight == pytest.approx(0.4)
    assert restored.caveats == ["Arsenal missing Saka", "Short turnaround"]


# ---------------------------------------------------------------------------
# Semantic cache meta tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_and_find_cache_meta(async_session):
    now = datetime.now(timezone.utc)
    point_id = uuid.uuid4()
    row = await record_cache_meta(
        async_session,
        qdrant_point_id=point_id,
        query_text="Who is the top scorer in EPL 2025?",
        tool="sportradar_standings",
        fetched_at=now,
        expires_at=now + timedelta(hours=1),
        entities={"teams": ["Arsenal"]},
    )
    assert row.hit_count == 0
    assert row.tool == "sportradar_standings"

    fresh = await find_fresh_cache_meta(async_session, "sportradar_standings", now=now)
    assert len(fresh) == 1
    assert fresh[0].qdrant_point_id == point_id


@pytest.mark.asyncio
async def test_expired_cache_not_returned(async_session):
    now = datetime.now(timezone.utc)
    point_id = uuid.uuid4()
    await record_cache_meta(
        async_session,
        qdrant_point_id=point_id,
        query_text="Old query",
        tool="some_tool",
        fetched_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),  # already expired
    )
    fresh = await find_fresh_cache_meta(async_session, "some_tool", now=now)
    assert len(fresh) == 0


@pytest.mark.asyncio
async def test_bump_cache_hit(async_session):
    now = datetime.now(timezone.utc)
    point_id = uuid.uuid4()
    await record_cache_meta(
        async_session,
        qdrant_point_id=point_id,
        query_text="EPL top scorer",
        tool="my_tool",
        fetched_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await bump_cache_hit(async_session, point_id)
    await bump_cache_hit(async_session, point_id)

    fresh = await find_fresh_cache_meta(async_session, "my_tool", now=now)
    assert fresh[0].hit_count == 2
