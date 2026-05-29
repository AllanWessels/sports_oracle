"""Ingest job: load reference/*.md files into the ``reference_docs`` collection.

Idempotent — skips files whose SHA-256 hash matches the stored ``doc_hash``.

Run standalone:
    python -m jobs.reference_docs
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from qdrant_client import models as qmodels
from sports_oracle_rag import (
    COLLECTION_REFERENCE_DOCS,
    build_point,
    ensure_collections,
    get_client,
    heading_aware_chunk,
)
from sports_oracle_rag.schema import ReferenceDocPayload

logger = logging.getLogger(__name__)

# Absolute path so job works regardless of cwd
_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"


async def _get_existing_hashes() -> dict[str, str]:
    """Return {source_path: doc_hash} for all points currently in reference_docs."""
    client = get_client()
    existing: dict[str, str] = {}
    offset = None

    while True:
        result, next_offset = await client.scroll(
            collection_name=COLLECTION_REFERENCE_DOCS,
            scroll_filter=None,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        for pt in result:
            payload = pt.payload or {}
            src = payload.get("source")
            h = payload.get("doc_hash")
            if src and h:
                existing[src] = h

        if next_offset is None:
            break
        offset = next_offset

    return existing


async def _delete_by_source(source: str) -> None:
    """Delete all points with the given source path."""
    client = get_client()
    await client.delete(
        collection_name=COLLECTION_REFERENCE_DOCS,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="source",
                        match=qmodels.MatchValue(value=source),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted existing chunks for source: %s", source)


async def run() -> None:
    """Load all .md files from data/reference/ into reference_docs."""
    await ensure_collections()

    existing_hashes = await _get_existing_hashes()

    md_files = sorted(_DATA_DIR.glob("*.md"))
    if not md_files:
        logger.warning("No .md files found in %s", _DATA_DIR)
        return

    for md_path in md_files:
        source = str(md_path)
        content = md_path.read_text(encoding="utf-8")
        doc_hash = hashlib.sha256(content.encode()).hexdigest()
        doc_title = md_path.stem.replace("_", " ").replace("-", " ").title()

        if existing_hashes.get(source) == doc_hash:
            logger.info("Skipping unchanged file: %s", md_path.name)
            continue

        logger.info("Processing: %s (hash=%s…)", md_path.name, doc_hash[:8])

        # Remove stale chunks for this source
        if source in existing_hashes:
            await _delete_by_source(source)

        # Chunk the document
        chunks = heading_aware_chunk(
            content,
            target_tokens=512,
            overlap_tokens=64,
            doc_title=doc_title,
        )

        # Build and upsert points in batches of 32
        batch_size = 32
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            points: list[qmodels.PointStruct] = []

            for chunk_text in batch:
                # Extract heading from chunk if present
                lines = chunk_text.strip().splitlines()
                section_title: str | None = None
                if lines and lines[0].startswith("#"):
                    section_title = lines[0].lstrip("#").strip()

                payload_obj = ReferenceDocPayload(
                    text=chunk_text,
                    title=doc_title,
                    source=source,
                    section_title=section_title,
                    doc_hash=doc_hash,
                )
                point_id = str(uuid.uuid4())
                pt = build_point(point_id, chunk_text, payload_obj.model_dump(mode="json"))
                points.append(pt)

            client = get_client()
            await client.upsert(
                collection_name=COLLECTION_REFERENCE_DOCS,
                points=points,
                wait=True,
            )
            logger.info(
                "Upserted %d chunks for %s (batch %d–%d)",
                len(points),
                md_path.name,
                batch_start,
                batch_start + len(batch) - 1,
            )

    logger.info("Reference docs ingest complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
