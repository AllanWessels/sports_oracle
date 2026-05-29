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

from sports_oracle_eval.schema import RagasScores

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
    """Build a RagasScores from a {metric: mean} mapping.

    Tolerant of RAGAS's verbose metric names (e.g.
    ``llm_context_precision_without_reference``) by fuzzy-matching onto our four
    canonical fields. Non-numeric / unknown keys are ignored.
    """
    def _num(v: Any) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    out: dict[str, float] = {}
    for raw_key, raw_val in means.items():
        num = _num(raw_val)
        if num is None:
            continue
        key = raw_key.lower()
        if "faith" in key:
            out["faithfulness"] = num
        elif "relevanc" in key:
            out["answer_relevancy"] = num
        elif "recall" in key:  # check before "precision" (context_recall)
            out["context_recall"] = num
        elif "precision" in key:
            out["context_precision"] = num
    return RagasScores(**out)


def _default_runner(records: list[dict[str, Any]], judge_model: str) -> dict[str, float]:
    """Real RAGAS run. Lazily imports RAGAS (the ``ragas`` extra)."""
    from langchain_anthropic import ChatAnthropic
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    from sports_oracle_eval.embeddings import ragas_embeddings

    # temperature is deprecated on newer Claude models — don't pass it.
    # max_tokens must be generous: RAGAS emits structured JSON and truncation
    # raises LLMDidNotFinishException.
    llm = LangchainLLMWrapper(ChatAnthropic(model=judge_model, max_tokens=4096))
    emb = ragas_embeddings()

    # Captured production traces have no ground-truth `reference`, so use the
    # reference-free metrics; only the golden set (which supplies a reference)
    # gets context-recall + reference-based precision.
    has_reference = any(r.get("reference") for r in records)
    metrics = [Faithfulness(), ResponseRelevancy()]
    if has_reference:
        metrics += [LLMContextPrecisionWithReference(), LLMContextRecall()]
    else:
        metrics.append(LLMContextPrecisionWithoutReference())

    dataset = EvaluationDataset.from_list(records)
    # raise_exceptions=False: a single failing metric/judge call yields NaN for
    # that metric instead of aborting the whole evaluation (best-effort scoring).
    result = evaluate(
        dataset=dataset, metrics=metrics, llm=llm, embeddings=emb, raise_exceptions=False
    )
    # RAGAS EvaluationResult is dict-like over metric -> mean score; drop NaN.
    out: dict[str, float] = {}
    for k, v in dict(result).items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == fv:  # filter NaN
            out[k] = fv
    return out


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
