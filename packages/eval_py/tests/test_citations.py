"""Citation-contract checker — pure, no LLM."""

from __future__ import annotations

from sports_oracle_shared import Citation

from sports_oracle_eval.citations import check_citations, extract_markers


def _cit(n: int) -> Citation:
    return Citation(ref_num=n, source_type="api", provider="espn")


def test_extract_markers_distinct_in_order():
    assert extract_markers("foo [2] bar [1] baz [2]") == [2, 1]


def test_extract_markers_ignores_ranges_and_links():
    # [1-3] and markdown links should not be parsed as single markers.
    assert extract_markers("see [1-3] and [text](url)") == []


def test_valid_when_every_marker_resolves():
    res = check_citations("A [1] and B [2].", [_cit(1), _cit(2)])
    assert res.valid
    assert res.referenced == [1, 2]
    assert res.available == [1, 2]
    assert res.orphan_markers == []
    assert res.unused_citations == []


def test_orphan_marker_is_invalid():
    res = check_citations("Claim [3].", [_cit(1)])
    assert not res.valid
    assert res.orphan_markers == [3]


def test_unused_citation_flagged_but_still_valid():
    res = check_citations("Only [1] used.", [_cit(1), _cit(2)])
    assert res.valid
    assert res.unused_citations == [2]


def test_no_markers_no_citations_is_valid():
    res = check_citations("chit-chat answer", [])
    assert res.valid
    assert res.referenced == []


def test_accepts_dict_citations():
    res = check_citations("X [1].", [{"ref_num": 1, "source_type": "rag_doc", "provider": "d"}])
    assert res.valid
