"""Ingest job: score captured eval traces with RAGAS, out of band.

Every turn writes an ``eval_traces`` row immediately (free, in the graph). This
job runs on the ingest worker's scheduler, pulls a batch of unjudged traces,
scores each with RAGAS (faithfulness, relevancy, context precision/recall) using
a Claude judge + local fastembed embeddings, plus a deterministic citation
check, and writes the scores back. Keeping it here keeps judge-LLM latency and
cost entirely off the user's request path.

Run standalone:
    python -m jobs.eval_judge
"""

from __future__ import annotations

import asyncio
import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class EvalJudgeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    eval_enabled: bool = True
    model_eval: str = "claude-haiku-4-5"
    eval_sample_rate: float = 1.0  # fraction of the unjudged batch to score
    eval_batch: int = 20  # max traces pulled per pass


def _sample(rows: list, rate: float) -> list:
    """Deterministically take a leading fraction of *rows* (rate in 0..1)."""
    if rate >= 1.0:
        return rows
    if rate <= 0.0 or not rows:
        return []
    return rows[: max(1, int(len(rows) * rate))]


async def judge_once(
    *,
    judge_model: str,
    sample_rate: float = 1.0,
    limit: int = 20,
    session_factory=None,
    runner=None,
) -> int:
    """Score one batch of unjudged traces. Returns the number scored.

    ``session_factory`` and ``runner`` are injectable for hermetic tests;
    defaults use the real DB session factory and the real RAGAS run.
    """
    from sports_oracle_db import repository as repo
    from sports_oracle_eval import check_citations, evaluate_samples, trace_to_sample

    if session_factory is None:
        from sports_oracle_db.session import get_session_factory

        session_factory = get_session_factory()

    scored = 0
    async with session_factory() as session:
        rows = await repo.get_unjudged_traces(session, limit=limit)
        for row in _sample(rows, sample_rate):
            d = repo.trace_to_dict(row)
            scores: dict = {}

            # RAGAS only makes sense when we have retrieved contexts + an answer.
            sample = trace_to_sample(d)
            if sample["contexts"] and sample["answer"]:
                try:
                    rs = evaluate_samples([sample], judge_model=judge_model, runner=runner)
                    scores.update({k: v for k, v in rs.model_dump().items() if v is not None})
                except Exception as exc:  # noqa: BLE001
                    logger.warning("RAGAS failed for trace %s: %s", d["id"], exc)

            # Deterministic citation-contract check (no LLM) — always runs.
            cit = check_citations(d["answer"] or "", d["citations"] or [])
            scores["citation_valid"] = cit.valid

            await repo.update_trace_scores(
                session, row.id, judge_model=judge_model, scores=scores
            )
            scored += 1
        await session.commit()

    logger.info("eval_judge: scored %d trace(s)", scored)
    return scored


async def run() -> None:
    s = EvalJudgeSettings()
    if not s.eval_enabled:
        logger.info("eval_judge disabled (EVAL_ENABLED=false)")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("eval_judge: ANTHROPIC_API_KEY unset — RAGAS will be skipped")
    await judge_once(
        judge_model=s.model_eval, sample_rate=s.eval_sample_rate, limit=s.eval_batch
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
