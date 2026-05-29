"""Evaluation + routing observability endpoints (read-only).

Powers the two dashboards. Reads captured ``eval_traces`` and reuses the pure
aggregation helpers from ``sports_oracle_eval`` (kept in one place, unit-tested
there). Degrades to empty/zero payloads if the DB is unavailable, like the other
read routes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics")


def _window_start(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def traffic_series(traces: list[dict], *, hours: int, bucket_minutes: int = 60) -> list[dict]:
    """Bucket trace volume per route over time (oldest→newest).

    Pure helper so the dashboard's time-series chart is unit-testable.
    """
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    width = timedelta(minutes=bucket_minutes)
    for t in traces:
        created = t.get("created_at")
        if not created:
            continue
        dt = datetime.fromisoformat(created)
        # floor to the bucket boundary
        epoch_min = int(dt.timestamp() // (bucket_minutes * 60)) * (bucket_minutes * 60)
        key = datetime.fromtimestamp(epoch_min, tz=timezone.utc).isoformat()
        route = t.get("route") or t.get("intent") or "factual"
        buckets[key]["total"] += 1
        buckets[key][route] += 1
    _ = width  # documented bucket width; boundaries computed above
    return [{"bucket": k, **v} for k, v in sorted(buckets.items())]


async def _load_window(hours: int, *, intent: str | None = None, limit: int = 10000) -> list[dict]:
    from sports_oracle_db import repository as repo  # type: ignore
    from sports_oracle_db.session import get_session_factory  # type: ignore

    async with get_session_factory()() as session:
        rows = await repo.list_traces(
            session, limit=limit, since=_window_start(hours), intent=intent
        )
        return [repo.trace_to_dict(r) for r in rows]


@router.get("/routing")
async def routing_metrics(hours: int = Query(24, ge=1, le=720)) -> dict:
    """Traffic split per route + cache/tool rates + volume over time."""
    from sports_oracle_eval import routing_aggregates

    try:
        traces = await _load_window(hours)
    except Exception as exc:  # noqa: BLE001
        logger.warning("routing_metrics unavailable: %s", exc)
        return {"window_hours": hours, "total": 0, "routes": {}, "series": []}

    agg = routing_aggregates(traces)
    agg["window_hours"] = hours
    agg["series"] = traffic_series(traces, hours=hours)
    return agg


@router.get("/eval")
async def eval_metrics(hours: int = Query(24, ge=1, le=720)) -> dict:
    """RAGAS metric means + citation-validity rate over the window."""
    from sports_oracle_eval import eval_aggregates

    try:
        traces = await _load_window(hours)
    except Exception as exc:  # noqa: BLE001
        logger.warning("eval_metrics unavailable: %s", exc)
        return {"window_hours": hours, "judged": 0, "pending": 0, "means": {}, "citation_valid_rate": None}

    agg = eval_aggregates(traces)
    agg["window_hours"] = hours
    return agg


@router.get("/traces")
async def list_traces(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    intent: str | None = None,
) -> dict:
    """Recent traces for drill-down (newest first)."""
    from sports_oracle_db import repository as repo  # type: ignore
    from sports_oracle_db.session import get_session_factory  # type: ignore

    try:
        async with get_session_factory()() as session:
            rows = await repo.list_traces(session, limit=limit, offset=offset, intent=intent)
            return {"traces": [repo.trace_to_dict(r) for r in rows]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_traces unavailable: %s", exc)
        return {"traces": []}
