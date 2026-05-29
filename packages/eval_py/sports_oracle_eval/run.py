"""CLI: produce an evaluation scorecard.

    python -m sports_oracle_eval.run                  # RAGAS over the golden set
    python -m sports_oracle_eval.run --citations-only  # no judge LLM needed
    python -m sports_oracle_eval.run --traces traces.json --out scorecard.json

Running RAGAS requires the ``ragas`` extra and an ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sports_oracle_eval.citations import check_citations
from sports_oracle_eval.datasets import load_golden
from sports_oracle_eval.ragas_runner import evaluate_samples
from sports_oracle_eval.schema import EvalReport, EvalSample, RagasScores


def _load_traces(path: Path) -> tuple[list[EvalSample], list[list]]:
    """Return (samples, citations_per_sample) from a captured-traces JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("traces", [])
    samples = [
        EvalSample(
            question=r.get("query", r.get("question", "")),
            answer=r.get("answer", ""),
            contexts=[
                (c if isinstance(c, str) else str(c.get("text", "")))
                for c in (r.get("contexts") or [])
            ],
            reference=r.get("reference"),
            trace_id=str(r["id"]) if r.get("id") is not None else None,
        )
        for r in rows
    ]
    citations = [list(r.get("citations") or []) for r in rows]
    return samples, citations


def build_report(
    samples: list[EvalSample],
    *,
    judge_model: str,
    run_ragas: bool,
    citations_per_sample: list[list] | None = None,
) -> EvalReport:
    # Citation-contract check needs the per-sample citation list. The golden set
    # carries none (it is a RAG ground-truth set), so validity is reported only
    # over captured traces that actually carry citations.
    valid_rate: float | None = None
    if citations_per_sample is not None:
        checks = [
            check_citations(s.answer, cites)
            for s, cites in zip(samples, citations_per_sample, strict=False)
        ]
        valid_rate = sum(1 for c in checks if c.valid) / len(checks) if checks else None

    means = RagasScores()
    if run_ragas:
        means = evaluate_samples([s.model_dump() for s in samples], judge_model=judge_model)

    return EvalReport(
        n_samples=len(samples),
        means=means,
        citation_valid_rate=valid_rate,
        judge_model=judge_model if run_ragas else None,
    )


def render_markdown(report: EvalReport) -> str:
    lines = [
        "# Sports Oracle — Eval Scorecard",
        "",
        f"- samples: **{report.n_samples}**",
        f"- judge: `{report.judge_model or 'n/a'}`",
        "",
        "| metric | mean |",
        "|---|---|",
    ]
    for metric, val in report.means.model_dump().items():
        lines.append(f"| {metric} | {'—' if val is None else f'{val:.3f}'} |")
    cvr = report.citation_valid_rate
    lines.append(f"| citation_valid_rate | {'—' if cvr is None else f'{cvr:.3f}'} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sports Oracle eval scorecard")
    ap.add_argument("--traces", type=Path, help="JSON file of captured traces")
    ap.add_argument("--judge-model", default=os.getenv("MODEL_EVAL", "claude-haiku-4-5"))
    ap.add_argument("--citations-only", action="store_true", help="skip RAGAS (no judge LLM)")
    ap.add_argument("--out", type=Path, help="write JSON scorecard to this path")
    args = ap.parse_args(argv)

    if args.traces:
        samples, citations_per_sample = _load_traces(args.traces)
    else:
        samples, citations_per_sample = load_golden(), None
    report = build_report(
        samples,
        judge_model=args.judge_model,
        run_ragas=not args.citations_only,
        citations_per_sample=citations_per_sample,
    )

    print(render_markdown(report))
    if args.out:
        args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
