"""Ingest job: maintenance sweep.

1. Delete expired ``sports_cache`` points (expires_at <= now).
2. Re-embed reference docs whose on-disk content has changed.

Run standalone:
    python -m jobs.reindex
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from qdrant_client import models as qmodels
from sports_oracle_rag import ensure_collections, get_client
from sports_oracle_rag.schema import COLLECTION_SPORTS_CACHE

logger = logging.getLogger(__name__)


async def purge_expired_cache() -> int:
    """Delete all sports_cache points where expires_at <= now. Returns count deleted."""
    client = get_client()
    now_iso = datetime.now(UTC).isoformat()

    # Qdrant range filter: expires_at <= now  →  range(lte=now)
    delete_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="expires_at",
                range=qmodels.DatetimeRange(lte=now_iso),
            )
        ]
    )

    # Count before delete
    count_result = await client.count(
        collection_name=COLLECTION_SPORTS_CACHE,
        count_filter=delete_filter,
        exact=False,
    )
    approx_count = count_result.count
    logger.info(
        "sports_cache: ~%d expired points to delete (now=%s)", approx_count, now_iso
    )

    if approx_count > 0:
        await client.delete(
            collection_name=COLLECTION_SPORTS_CACHE,
            points_selector=qmodels.FilterSelector(filter=delete_filter),
            wait=True,
        )
        logger.info("Deleted ~%d expired sports_cache points.", approx_count)

    return approx_count


async def reindex_changed_reference_docs() -> int:
    """Re-embed any reference docs whose on-disk file has changed.

    Delegates to the reference_docs job which is idempotent (hash-checked).
    """
    from jobs.reference_docs import run as run_reference_docs

    logger.info("Checking reference docs for changes...")
    await run_reference_docs()
    return 0  # run_reference_docs logs its own counts


async def run() -> None:
    """Run the full reindex sweep."""
    await ensure_collections()

    deleted = await purge_expired_cache()
    logger.info("Cache purge: %d points removed.", deleted)

    await reindex_changed_reference_docs()

    logger.info("Reindex sweep complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
