"""Ingest job: pull RSS feeds → chunk → embed → upsert to ``news`` collection.

Reads feed URLs from ``NEWS_FEEDS`` env var (comma-separated).

Run standalone:
    python -m jobs.news
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import models as qmodels
from sports_oracle_rag import (
    COLLECTION_NEWS,
    build_point,
    ensure_collections,
    get_client,
    paragraph_chunk,
)
from sports_oracle_rag.schema import NewsPayload

logger = logging.getLogger(__name__)


class NewsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    news_feeds: str = ""  # comma-separated RSS URLs


_settings = NewsSettings()


def _parse_published(entry: Any) -> datetime | None:
    """Parse entry published date to an aware datetime, or None."""
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    # Try feedparser's parsed tuple
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                import time
                ts = time.mktime(parsed)
                return datetime.fromtimestamp(ts, tz=UTC)
            except Exception:
                pass
    return None


def _entry_id(entry: Any, feed_url: str) -> str:
    """Deterministic ID for a feed entry (hash of feed + entry link/id)."""
    import hashlib
    key = feed_url + (getattr(entry, "id", None) or getattr(entry, "link", "") or "")
    return hashlib.sha256(key.encode()).hexdigest()[:32]


async def _entry_exists(entry_source_id: str) -> bool:
    """Check whether a point with this source_id already exists in news."""
    client = get_client()
    result, _ = await client.scroll(
        collection_name=COLLECTION_NEWS,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="source_id",
                    match=qmodels.MatchValue(value=entry_source_id),
                )
            ]
        ),
        limit=1,
        with_payload=False,
    )
    return len(result) > 0


async def ingest_feed(feed_url: str) -> int:
    """Fetch one RSS feed, chunk all entries, upsert new ones. Returns count upserted."""
    logger.info("Fetching feed: %s", feed_url)
    parsed = feedparser.parse(feed_url)

    upserted = 0
    for entry in parsed.entries:
        source_id = _entry_id(entry, feed_url)

        # Skip already-ingested entries (idempotent)
        if await _entry_exists(source_id):
            logger.debug("Skipping known entry: %s", source_id)
            continue

        # Build full text: title + summary/content
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or ""
        content_list = getattr(entry, "content", [])
        content_text = content_list[0].value if content_list else ""
        full_text = "\n\n".join(filter(None, [title, summary or content_text]))

        if not full_text.strip():
            logger.debug("Empty entry, skipping: %s", source_id)
            continue

        published_at = _parse_published(entry)
        link = getattr(entry, "link", None)
        tags = getattr(entry, "tags", [])
        sport_tag = tags[0].term if tags else None

        # Chunk the entry
        chunks = paragraph_chunk(full_text, min_tokens=50, max_tokens=400)
        if not chunks:
            chunks = [full_text[:2000]]  # fallback: take as-is up to 2 k chars

        points: list[qmodels.PointStruct] = []
        for i, chunk_text in enumerate(chunks):
            payload_obj = NewsPayload(
                text=chunk_text,
                title=title or None,
                url=link,
                source=feed_url,
                sport=sport_tag,
                published_at=published_at,
                feed_url=feed_url,
                metadata={"source_id": source_id, "chunk_index": i},
            )
            # Store source_id at top level for dedup filter
            payload_dict = payload_obj.model_dump(mode="json")
            payload_dict["source_id"] = source_id

            pt = build_point(str(uuid.uuid4()), chunk_text, payload_dict)
            points.append(pt)

        if points:
            client = get_client()
            await client.upsert(
                collection_name=COLLECTION_NEWS,
                points=points,
                wait=True,
            )
            upserted += len(points)
            logger.info(
                "Upserted %d chunks for entry '%s' from %s",
                len(points),
                title[:60],
                feed_url,
            )

    return upserted


async def run() -> None:
    """Run the news ingest job for all configured feeds."""
    await ensure_collections()

    feed_urls = [u.strip() for u in _settings.news_feeds.split(",") if u.strip()]
    if not feed_urls:
        logger.warning("NEWS_FEEDS is empty — no feeds to ingest.")
        return

    total = 0
    for url in feed_urls:
        try:
            count = await ingest_feed(url)
            total += count
        except Exception as exc:
            logger.error("Failed to ingest feed %s: %s", url, exc, exc_info=True)

    logger.info("News ingest complete. Total chunks upserted: %d", total)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
