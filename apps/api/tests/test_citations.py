"""Tests for citation assembly (pure, no heavy deps)."""

from __future__ import annotations

from app.services.citations import build_citations


def test_api_sources_numbered_first_then_rag():
    tool_results = [
        {"tool": "get_fixtures", "data": {"x": 1},
         "source": {"provider": "espn", "endpoint": "/scoreboard", "url": "http://e", "fetched_at": "2026-05-29T00:00:00+00:00"}},
        {"tool": "get_odds", "data": None, "source": {"provider": "apifootball"}},  # null data skipped
    ]

    class Chunk:
        collection = "news"
        id = "n1"
        source = "BBC"
        url = "http://bbc"
        title = "Preview"
        text = "Some news text"
        fetched_at = None

    cites = build_citations(tool_results, [Chunk()])
    assert [c.ref_num for c in cites] == [1, 2]
    assert cites[0].source_type == "api"
    assert cites[0].provider == "espn"
    assert cites[1].source_type == "rag_news"
    assert cites[1].provider == "BBC"


def test_null_data_tool_excluded():
    cites = build_citations([{"tool": "get_odds", "data": None, "source": {}}], [])
    assert cites == []
