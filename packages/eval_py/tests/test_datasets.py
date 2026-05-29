"""Golden dataset loads and is well-formed."""

from __future__ import annotations

from sports_oracle_eval.citations import check_citations
from sports_oracle_eval.datasets import load_golden


def test_golden_loads_nonempty():
    samples = load_golden()
    assert len(samples) >= 8
    for s in samples:
        assert s.question and s.answer
        assert s.contexts, f"sample missing contexts: {s.question}"
        assert s.reference, f"sample missing reference: {s.question}"


def test_golden_answers_only_cite_marker_one():
    # Each golden answer cites [1] against its single supplied context, so the
    # contract check (with a single citation available) must pass.
    for s in load_golden():
        res = check_citations(s.answer, [{"ref_num": 1, "source_type": "rag_doc", "provider": "d"}])
        assert res.valid, f"orphan markers in golden answer: {s.question} -> {res.orphan_markers}"
