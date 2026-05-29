"""RAGAS runner — pure conversions + an injected fake runner (no real RAGAS)."""

from __future__ import annotations

from sports_oracle_eval.ragas_runner import (
    evaluate_samples,
    sample_to_record,
    samples_to_records,
    scores_from_means,
    trace_to_sample,
)


def test_trace_to_sample_pulls_query_answer_and_context_texts():
    trace = {
        "id": 7,
        "query": "Who won?",
        "answer": "Team A [1].",
        "contexts": ["plain ctx", {"text": "dict ctx"}, {"snippet": "snip ctx"}, {"x": 1}],
    }
    s = trace_to_sample(trace)
    assert s["question"] == "Who won?"
    assert s["answer"] == "Team A [1]."
    assert s["contexts"] == ["plain ctx", "dict ctx", "snip ctx"]  # empty dropped
    assert s["trace_id"] == "7"


def test_sample_to_record_uses_ragas_column_names_and_omits_empty_reference():
    rec = sample_to_record({"question": "q", "answer": "a", "contexts": ["c"]})
    assert rec == {"user_input": "q", "response": "a", "retrieved_contexts": ["c"]}
    rec2 = sample_to_record({"question": "q", "answer": "a", "contexts": [], "reference": "r"})
    assert rec2["reference"] == "r"


def test_scores_from_means_ignores_extras_and_coerces():
    scores = scores_from_means({"faithfulness": "0.9", "answer_relevancy": 0.5, "junk": 1})
    assert scores.faithfulness == 0.9
    assert scores.answer_relevancy == 0.5
    assert scores.context_precision is None


def test_evaluate_samples_uses_injected_runner():
    captured = {}

    def fake_runner(records, judge_model):
        captured["records"] = records
        captured["judge_model"] = judge_model
        return {"faithfulness": 0.75, "context_recall": 0.6}

    samples = [{"question": "q", "answer": "a [1]", "contexts": ["ctx"]}]
    scores = evaluate_samples(samples, judge_model="claude-haiku-4-5", runner=fake_runner)

    assert captured["judge_model"] == "claude-haiku-4-5"
    assert captured["records"] == [
        {"user_input": "q", "response": "a [1]", "retrieved_contexts": ["ctx"]}
    ]
    assert scores.faithfulness == 0.75
    assert scores.context_recall == 0.6


def test_evaluate_samples_empty_is_noop():
    scores = evaluate_samples([], judge_model="m", runner=lambda r, j: {})
    assert scores.faithfulness is None


def test_samples_to_records_roundtrips_list():
    recs = samples_to_records([{"question": "a", "answer": "b"}, {"question": "c", "answer": "d"}])
    assert [r["user_input"] for r in recs] == ["a", "c"]
