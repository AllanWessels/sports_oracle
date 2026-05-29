"""Run RAGAS metrics over eval samples.

Design for testability + light CI:
- ``trace_to_sample`` / ``sample_to_record`` / ``scores_from_means`` are pure
  and unit-tested directly.
- ``evaluate_samples`` takes an injectable ``runner`` callable; the default
  runner lazily imports RAGAS (only installed via the ``ragas`` extra), so unit
  tests pass a fake runner and never touch the heavy stack.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sports_oracle_eval.schema import RAGAS_METRICS, RagasScores

# A runner maps (records, judge_model) -> {metric_name: mean_score}.
Runner = Callable[[list[dict[str, Any]], str], dict[str, float]]


def trace_to_sample(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a captured ``eval_traces`` row (mapping) into EvalSample kwargs.

    Contexts come from the trace's ``contexts`` (RAG chunk texts) and/or the
    text of tool results, whichever the capture node stored.
    """
    contexts: list[str] = []
    raw_ctx = trace.get("contexts") or []
    for c in raw_ctx:
        if isinstance(c, str):
            contexts.append(c)
        elif isinstance(c, Mapping):
            contexts.append(str(c.get("text") or c.get("snippet") or ""))
    return {
        "question": trace.get("query", ""),
        "answer": trace.get("answer", ""),
        "contexts": [c for c in contexts if c],
        "reference": trace.get("reference"),
        "trace_id": str(trace["id"]) if trace.get("id") is not None else None,
    }


def sample_to_record(sample: Mapping[str, Any]) -> dict[str, Any]:
    """Map an EvalSample(-like mapping) to RAGAS single-turn column names."""
    record: dict[str, Any] = {
        "user_input": sample.get("question", ""),
        "response": sample.get("answer", ""),
        "retrieved_contexts": list(sample.get("contexts", []) or []),
    }
    if sample.get("reference"):
        record["reference"] = sample["reference"]
    return record


def samples_to_records(samples: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [sample_to_record(s) for s in samples]


def scores_from_means(means: Mapping[str, Any]) -> RagasScores:
    """Build a RagasScores from a {metric: mean} mapping, ignoring extras."""
    def _num(v: Any) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return RagasScores(**{m: _num(means.get(m)) for m in RAGAS_METRICS})


def _default_runner(records: list[dict[str, Any]], judge_model: str) -> dict[str, float]:
    """Real RAGAS run. Lazily imports RAGAS (the ``ragas`` extra)."""
    from langchain_anthropic import ChatAnthropic
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    from sports_oracle_eval.embeddings import ragas_embeddings

    llm = LangchainLLMWrapper(ChatAnthropic(model=judge_model, temperature=0))
    emb = ragas_embeddings()
    metrics = [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextPrecisionWithReference(),
        LLMContextRecall(),
    ]
    dataset = EvaluationDataset.from_list(records)
    result = evaluate(dataset=dataset, metrics=metrics, llm=llm, embeddings=emb)
    # RAGAS EvaluationResult is dict-like over metric -> mean score.
    return {k: float(v) for k, v in dict(result).items()}


def evaluate_samples(
    samples: list[Mapping[str, Any]],
    *,
    judge_model: str,
    runner: Runner | None = None,
) -> RagasScores:
    """Score *samples* with RAGAS and return per-metric means.

    Pass ``runner`` to inject a fake in tests; defaults to the real RAGAS run.
    """
    if not samples:
        return RagasScores()
    run = runner or _default_runner
    records = samples_to_records(samples)
    means = run(records, judge_model)
    return scores_from_means(means)
