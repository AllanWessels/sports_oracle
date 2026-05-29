"""Assemble numbered citations from tool results and RAG chunks."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sports_oracle_shared import Citation


def _parse_dt(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def build_citations(tool_results: list[dict], rag_hits: list) -> list[Citation]:
    """Build a flat, numbered citation list. API sources first, then RAG."""
    citations: list[Citation] = []
    ref = 1

    for r in tool_results:
        if r.get("data") is None:
            continue
        source = r.get("source", {}) or {}
        citations.append(
            Citation(
                ref_num=ref,
                source_type="api",
                provider=source.get("provider", r.get("tool", "sports-api")),
                endpoint=source.get("endpoint"),
                url=source.get("url"),
                fetched_at=_parse_dt(source.get("fetched_at")),
                snippet=r.get("tool"),
            )
        )
        ref += 1

    for h in rag_hits:
        collection = getattr(h, "collection", "reference_docs")
        citations.append(
            Citation(
                ref_num=ref,
                source_type="rag_news" if collection == "news" else "rag_doc",
                provider=getattr(h, "source", None) or getattr(h, "id", "doc"),
                url=getattr(h, "url", None),
                fetched_at=getattr(h, "fetched_at", None),
                snippet=(getattr(h, "title", None) or getattr(h, "text", "")[:120]),
            )
        )
        ref += 1

    return citations
