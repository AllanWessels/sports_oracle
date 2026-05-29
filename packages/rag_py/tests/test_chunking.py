"""Unit tests for chunking.py — no live Qdrant, no network calls."""

from __future__ import annotations

import pytest

from sports_oracle_rag.chunking import (
    _approx_tokens,
    cache_summarize,
    heading_aware_chunk,
    paragraph_chunk,
)


# ---------------------------------------------------------------------------
# _approx_tokens
# ---------------------------------------------------------------------------

class TestApproxTokens:
    def test_empty(self):
        assert _approx_tokens("") == 0

    def test_single_word(self):
        assert _approx_tokens("hello") == 1

    def test_multiple_words(self):
        assert _approx_tokens("the quick brown fox") == 4


# ---------------------------------------------------------------------------
# heading_aware_chunk
# ---------------------------------------------------------------------------

SIMPLE_MD = """\
# Overview

This is an overview paragraph with several words in it so we can test the chunker.

## Section One

Section one has its own content that is separate from the overview. It discusses
the first topic in detail across multiple sentences.

## Section Two

Section two covers a completely different topic with unique content.
Here we talk about the second subject matter.
"""


class TestHeadingAwareChunk:
    def test_returns_list(self):
        chunks = heading_aware_chunk(SIMPLE_MD)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_chunks_non_empty(self):
        chunks = heading_aware_chunk(SIMPLE_MD)
        for c in chunks:
            assert c.strip()

    def test_heading_prepended(self):
        chunks = heading_aware_chunk(SIMPLE_MD)
        # At least one chunk should contain "Section One" as a heading
        headings_found = [c for c in chunks if "Section One" in c or "Overview" in c]
        assert headings_found, "Expected heading to be prepended to chunk"

    def test_target_token_respected_approximately(self):
        # Generate content larger than 512 tokens
        long_body = " ".join(["word"] * 600)
        text = f"# Big Section\n\n{long_body}"
        chunks = heading_aware_chunk(text, target_tokens=512)
        # Each chunk should be at most ~512 + overlap tokens
        for c in chunks:
            assert _approx_tokens(c) <= 512 + 64 + 20  # heading + overlap buffer

    def test_no_headings_document(self):
        text = "Just some plain text without any markdown headings at all here."
        chunks = heading_aware_chunk(text)
        assert len(chunks) == 1
        assert "Just some plain text" in chunks[0]

    def test_doc_title_prepended_when_no_heading(self):
        text = "Plain content without headings."
        chunks = heading_aware_chunk(text, doc_title="My Doc")
        assert "My Doc" in chunks[0]

    def test_overlap_repeats_tail(self):
        # Build a document where we force two chunks in the same section
        words_a = " ".join([f"word{i}" for i in range(300)])
        words_b = " ".join([f"term{i}" for i in range(300)])
        text = f"# Section\n\n{words_a}\n\n{words_b}"
        chunks = heading_aware_chunk(text, target_tokens=300, overlap_tokens=20)
        if len(chunks) >= 2:
            # Last 20 words of chunk[0] should appear in chunk[1]
            tail_words = chunks[0].split()[-20:]
            combined = " ".join(chunks[1].split())
            overlap_found = any(w in combined for w in tail_words[-5:])
            assert overlap_found


# ---------------------------------------------------------------------------
# paragraph_chunk
# ---------------------------------------------------------------------------

NEWS_ARTICLE = """\
The match ended in a dramatic fashion last night.

Both teams gave their all in a thrilling encounter that delighted fans worldwide.
The score was tied until the very last minute when a stunning strike decided the outcome.

Analysts are calling it one of the best matches of the season so far.
The players showed tremendous skill and determination throughout the ninety minutes.

Post-match interviews revealed that both managers were proud of their teams despite the result.
"""


class TestParagraphChunk:
    def test_returns_list(self):
        chunks = paragraph_chunk(NEWS_ARTICLE)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_chunks_non_empty(self):
        for c in paragraph_chunk(NEWS_ARTICLE):
            assert c.strip()

    def test_respects_max_tokens(self):
        long_text = "\n\n".join([" ".join(["word"] * 50) for _ in range(20)])
        chunks = paragraph_chunk(long_text, min_tokens=30, max_tokens=100)
        for c in chunks:
            # Allow a small overshoot for sentence-split remainder
            assert _approx_tokens(c) <= 150

    def test_single_paragraph_short(self):
        text = "Short paragraph."
        chunks = paragraph_chunk(text, min_tokens=1, max_tokens=100)
        assert len(chunks) == 1
        assert "Short paragraph." in chunks[0]

    def test_no_overlap(self):
        # paragraph_chunk has no overlap — verify no word appears in two consecutive chunks
        # by checking the chunks are different and content isn't duplicated
        long_text = "\n\n".join([f"Para {i}: " + " ".join([f"w{j}" for j in range(60)]) for i in range(10)])
        chunks = paragraph_chunk(long_text, min_tokens=60, max_tokens=120)
        # Consecutive chunks should not start with the same sentence
        for i in range(len(chunks) - 1):
            assert chunks[i][:30] != chunks[i + 1][:30]


# ---------------------------------------------------------------------------
# cache_summarize
# ---------------------------------------------------------------------------

class TestCacheSummarize:
    def test_uses_summary_field(self):
        data = {"summary": "The team won the championship.", "raw": {"lots": "of data"}}
        result = cache_summarize(data)
        assert result == "The team won the championship."

    def test_uses_description_field(self):
        data = {"description": "A great game was played."}
        result = cache_summarize(data)
        assert result == "A great game was played."

    def test_falls_back_to_flatten(self):
        data = {"team": "Arsenal", "score": 3, "opponent": "Chelsea"}
        result = cache_summarize(data)
        assert "Arsenal" in result
        assert "Chelsea" in result

    def test_truncates_long_summary(self):
        data = {"summary": " ".join(["word"] * 500)}
        result = cache_summarize(data, max_tokens=100)
        assert _approx_tokens(result) <= 100

    def test_nested_dict_flattened(self):
        data = {"match": {"home": "TeamA", "away": "TeamB", "goals": 2}}
        result = cache_summarize(data)
        assert "TeamA" in result or "match" in result

    def test_empty_dict(self):
        result = cache_summarize({})
        assert isinstance(result, str)

    def test_prefers_text_over_flatten(self):
        data = {"text": "Interesting article here.", "irrelevant": "noise"}
        result = cache_summarize(data)
        assert result == "Interesting article here."
