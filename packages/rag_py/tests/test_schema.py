"""Unit tests for schema.py — TTL helpers, expiry logic, and payload models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sports_oracle_rag.schema import (
    COLLECTION_NEWS,
    COLLECTION_REFERENCE_DOCS,
    COLLECTION_SPORTS_CACHE,
    DataClass,
    NewsPayload,
    ReferenceDocPayload,
    SportsCachePayload,
    expires_at,
    is_expired,
    ttl_seconds,
)


class TestCollectionConstants:
    def test_names(self):
        assert COLLECTION_SPORTS_CACHE == "sports_cache"
        assert COLLECTION_REFERENCE_DOCS == "reference_docs"
        assert COLLECTION_NEWS == "news"


class TestTtlSeconds:
    def test_api_response_ttl(self):
        assert ttl_seconds(DataClass.API_RESPONSE) == 3600  # 1 hour

    def test_qa_answer_ttl(self):
        assert ttl_seconds(DataClass.QA_ANSWER) == 6 * 3600  # 6 hours

    def test_news_article_ttl(self):
        assert ttl_seconds(DataClass.NEWS_ARTICLE) == 7 * 24 * 3600  # 7 days

    def test_reference_doc_ttl(self):
        assert ttl_seconds(DataClass.REFERENCE_DOC) == 365 * 24 * 3600  # 1 year


class TestExpiresAt:
    def test_future_expiry(self):
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        exp = expires_at(DataClass.API_RESPONSE, now=now)
        expected = now + timedelta(seconds=3600)
        assert exp == expected

    def test_qa_answer_expiry(self):
        now = datetime(2025, 6, 15, 0, 0, 0, tzinfo=UTC)
        exp = expires_at(DataClass.QA_ANSWER, now=now)
        assert exp == now + timedelta(hours=6)

    def test_defaults_to_utc_now(self):
        before = datetime.now(UTC)
        exp = expires_at(DataClass.API_RESPONSE)
        after = datetime.now(UTC)
        assert before + timedelta(seconds=3600) <= exp <= after + timedelta(seconds=3600)


class TestIsExpired:
    def test_past_is_expired(self):
        past = datetime(2000, 1, 1, tzinfo=UTC)
        assert is_expired(past) is True

    def test_future_is_not_expired(self):
        future = datetime(2099, 1, 1, tzinfo=UTC)
        assert is_expired(future) is False

    def test_exact_now_is_expired(self):
        now = datetime.now(UTC)
        # Passing `now` as both the anchor and the expiry — should be expired (>=)
        assert is_expired(now, now=now) is True

    def test_naive_datetime_treated_as_utc(self):
        # A naive datetime far in the future should not be expired
        far_future = datetime(2099, 1, 1)  # naive
        assert is_expired(far_future) is False

    def test_custom_now(self):
        exp = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        before = datetime(2025, 6, 1, 11, 59, 59, tzinfo=UTC)
        after = datetime(2025, 6, 1, 12, 0, 1, tzinfo=UTC)
        assert is_expired(exp, now=before) is False
        assert is_expired(exp, now=after) is True


class TestSportsCachePayload:
    def test_build_sets_expires_at(self):
        now = datetime(2025, 1, 1, tzinfo=UTC)
        payload = SportsCachePayload.build(
            text="Result: Arsenal 2–1 Chelsea",
            data_class=DataClass.API_RESPONSE,
            now=now,
        )
        expected_exp = now + timedelta(seconds=3600)
        assert payload.expires_at == expected_exp
        assert payload.data_class == DataClass.API_RESPONSE

    def test_build_with_extra_fields(self):
        payload = SportsCachePayload.build(
            text="Some answer",
            data_class=DataClass.QA_ANSWER,
            sport="soccer",
            title="Match result",
        )
        assert payload.sport == "soccer"
        assert payload.title == "Match result"
        assert not is_expired(payload.expires_at)


class TestReferenceDocPayload:
    def test_defaults(self):
        payload = ReferenceDocPayload(text="The offside rule in football...")
        assert payload.text.startswith("The offside rule")
        assert payload.section_title is None
        assert payload.doc_hash is None

    def test_with_section_title(self):
        payload = ReferenceDocPayload(
            text="A player is in an offside position...",
            section_title="Offside Rule",
            doc_hash="abc123",
        )
        assert payload.section_title == "Offside Rule"
        assert payload.doc_hash == "abc123"


class TestNewsPayload:
    def test_with_published_at(self):
        pub = datetime(2025, 5, 20, 10, 0, 0, tzinfo=UTC)
        payload = NewsPayload(
            text="Breaking: Team wins league title.",
            published_at=pub,
            feed_url="https://example.com/feed.rss",
        )
        assert payload.published_at == pub
        assert payload.feed_url == "https://example.com/feed.rss"

    def test_without_published_at(self):
        payload = NewsPayload(text="Generic news item.")
        assert payload.published_at is None
