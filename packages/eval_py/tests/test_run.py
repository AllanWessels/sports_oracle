"""Scorecard assembly (build_report) + markdown rendering."""

from __future__ import annotations

import json

from sports_oracle_eval.run import _load_traces, build_report, render_markdown
from sports_oracle_eval.schema import EvalSample


def test_golden_report_skips_citation_rate_and_ragas():
    samples = [EvalSample(question="q", answer="a [1]", contexts=["c"], reference="a")]
    rep = build_report(samples, judge_model="m", run_ragas=False, citations_per_sample=None)
    assert rep.n_samples == 1
    assert rep.citation_valid_rate is None  # golden set has no citations
    assert rep.means.faithfulness is None
    assert rep.judge_model is None


def test_trace_report_computes_citation_validity():
    samples = [
        EvalSample(question="q1", answer="good [1]", contexts=[]),
        EvalSample(question="q2", answer="orphan [2]", contexts=[]),
    ]
    cites = [[{"ref_num": 1, "source_type": "api", "provider": "p"}], []]
    rep = build_report(samples, judge_model="m", run_ragas=False, citations_per_sample=cites)
    assert rep.citation_valid_rate == 0.5  # first valid, second orphaned


def test_load_traces_extracts_samples_and_citations(tmp_path):
    p = tmp_path / "traces.json"
    p.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "query": "Who won?",
                    "answer": "A [1].",
                    "contexts": [{"text": "ctx"}],
                    "citations": [{"ref_num": 1, "source_type": "api", "provider": "espn"}],
                }
            ]
        )
    )
    samples, citations = _load_traces(p)
    assert samples[0].question == "Who won?"
    assert samples[0].contexts == ["ctx"]
    assert citations[0][0]["ref_num"] == 1


def test_render_markdown_contains_metrics():
    rep = build_report(
        [EvalSample(question="q", answer="a")], judge_model="m", run_ragas=False
    )
    md = render_markdown(rep)
    assert "Eval Scorecard" in md
    assert "faithfulness" in md
