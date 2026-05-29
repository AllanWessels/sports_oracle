"""Data shapes for evaluation.

These are deliberately decoupled from the live ``OracleState`` /
``eval_traces`` row so the eval library can be run over either captured traces
or a static golden dataset.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# RAGAS metric names we compute. Kept here so the runner, the report, and the
# dashboards all reference one list.
RAGAS_METRICS: tuple[str, ...] = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


class EvalSample(BaseModel):
    """One question/answer/contexts triple to evaluate.

    Maps onto a RAGAS single-turn sample. ``reference`` (the ground-truth
    answer) is required for context_recall / answer_correctness but optional
    for faithfulness / answer_relevancy, so captured production traces (which
    have no ground truth) can still be partially scored.
    """

    question: str
    answer: str
    contexts: list[str] = Field(default_factory=list)
    reference: str | None = None
    # Free-form provenance so a score can be traced back to its source.
    trace_id: str | None = None


class CitationCheck(BaseModel):
    """Result of the deterministic citation-contract check for one answer."""

    valid: bool
    referenced: list[int] = Field(default_factory=list)
    available: list[int] = Field(default_factory=list)
    # Markers like ``[3]`` that appear in the answer with no matching citation.
    orphan_markers: list[int] = Field(default_factory=list)
    # Citations supplied but never cited in the answer text.
    unused_citations: list[int] = Field(default_factory=list)


class RagasScores(BaseModel):
    """Per-metric RAGAS scores (0..1). Missing metrics are None."""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None


class EvalReport(BaseModel):
    """Aggregate scorecard over a set of samples."""

    n_samples: int
    means: RagasScores
    citation_valid_rate: float | None = None
    judge_model: str | None = None
