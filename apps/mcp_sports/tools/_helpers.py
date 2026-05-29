"""Shared helpers for tool modules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sports_oracle_shared.envelope import SourceRef, ToolEnvelope


def make_envelope(
    data: Any,
    provider: str,
    endpoint: str,
    url: str | None,
    ttl_seconds: int,
    partial: bool = False,
    notes: str | None = None,
) -> dict:
    """Build a ToolEnvelope and serialize it to a dict for MCP transport."""
    env = ToolEnvelope(
        data=data,
        source=SourceRef(
            provider=provider,
            endpoint=endpoint,
            url=url,
            fetched_at=datetime.now(UTC),
        ),
        ttl_seconds=ttl_seconds,
        partial=partial,
        notes=notes,
    )
    return env.model_dump(mode="json")
