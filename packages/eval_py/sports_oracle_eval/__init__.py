"""Sports Oracle evaluation library.

Three independent surfaces:
- ``citations``: deterministic citation-contract checking (no LLM).
- ``routing``: pure aggregation over captured traces (traffic + effectiveness).
- ``ragas_runner`` + ``embeddings``: RAGAS metrics with a Claude judge and local
  fastembed embeddings (requires the ``ragas`` extra).
"""

from __future__ import annotations

from sports_oracle_eval.citations import check_citations, extract_markers
from sports_oracle_eval.datasets import load_golden
from sports_oracle_eval.ragas_runner import (
    evaluate_samples,
    sample_to_record,
    samples_to_records,
    scores_from_means,
    trace_to_sample,
)
from sports_oracle_eval.routing import eval_aggregates, route_of, routing_aggregates
from sports_oracle_eval.schema import (
    RAGAS_METRICS,
    CitationCheck,
    EvalReport,
    EvalSample,
    RagasScores,
)

__all__ = [
    "RAGAS_METRICS",
    "CitationCheck",
    "EvalReport",
    "EvalSample",
    "RagasScores",
    "check_citations",
    "eval_aggregates",
    "evaluate_samples",
    "extract_markers",
    "load_golden",
    "route_of",
    "routing_aggregates",
    "sample_to_record",
    "samples_to_records",
    "scores_from_means",
    "trace_to_sample",
]
