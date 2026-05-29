"""APScheduler-based ingest worker.

Schedules:
  - reference_docs  : every 6 hours
  - news            : every 15 minutes
  - reindex         : every hour

Run:
    python worker.py

Individual jobs can also be run one-off:
    python -m jobs.reference_docs
    python -m jobs.news
    python -m jobs.reindex
"""

from __future__ import annotations

import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ingest.worker")


async def _run_job(name: str) -> None:
    """Import and execute a job by module name, with error isolation."""
    try:
        import importlib

        module = importlib.import_module(f"jobs.{name}")
        await module.run()
    except Exception as exc:
        logger.error("Job %s failed: %s", name, exc, exc_info=True)


async def main() -> None:
    scheduler = AsyncIOScheduler()

    # Reference docs: run at startup, then every 6 hours
    scheduler.add_job(
        _run_job,
        trigger=IntervalTrigger(hours=6),
        args=["reference_docs"],
        id="reference_docs",
        name="Reference Docs Ingest",
        max_instances=1,
        coalesce=True,
    )

    # News feeds: every 15 minutes
    scheduler.add_job(
        _run_job,
        trigger=IntervalTrigger(minutes=15),
        args=["news"],
        id="news",
        name="News RSS Ingest",
        max_instances=1,
        coalesce=True,
    )

    # Reindex/cache-purge: every hour
    scheduler.add_job(
        _run_job,
        trigger=IntervalTrigger(hours=1),
        args=["reindex"],
        id="reindex",
        name="Cache Purge + Reindex",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Ingest worker started. Scheduled jobs: %s", [j.id for j in scheduler.get_jobs()])

    # Run reference_docs and news immediately on startup
    await _run_job("reference_docs")
    await _run_job("news")

    try:
        # Keep running forever
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down ingest worker...")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
