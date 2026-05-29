"""Text chunking utilities for the RAG ingest pipeline.

Three chunkers are provided:

heading_aware_chunk
    For reference documents (Markdown/RST). Respects heading boundaries,
    targets ~512 tokens (approximated by whitespace), 64-token overlap.
    Prepends the nearest section heading to each chunk for context.

paragraph_chunk
    For news articles. Targets 256-400 tokens per chunk, splits on
    paragraph/sentence boundaries, no overlap (freshness > coherence).

cache_summarize
    Turns a normalised API JSON result (dict) into a single compact text
    chunk suitable for upsert into ``sports_cache``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Token approximation (whitespace-split word count)
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    """Approximate token count by whitespace splitting (fast, no tokenizer needed)."""
    return len(text.split())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '.', '!', '?', keeping the punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Reference-doc heading-aware chunker
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class _Section:
    level: int
    title: str
    body: str  # text after the heading up to (but not including) the next heading


def _extract_sections(text: str) -> list[_Section]:
    """Split a Markdown document into (level, title, body) sections."""
    sections: list[_Section] = []
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        # No headings — treat entire text as one unnamed section
        return [_Section(level=0, title="", body=text)]

    # Text before first heading
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(_Section(level=0, title="", body=preamble))

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(_Section(level=level, title=title, body=body))

    return sections


def heading_aware_chunk(
    text: str,
    *,
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    doc_title: str = "",
) -> list[str]:
    """Return heading-aware chunks of *text* targeting *target_tokens* each.

    Each chunk is prefixed with the nearest section heading (breadcrumb)
    for context, e.g. ``"## Offside Rule\\n\\n<body text>"``.

    Parameters
    ----------
    text:
        Full document text (Markdown).
    target_tokens:
        Approximate maximum tokens per chunk.
    overlap_tokens:
        Number of tokens from the end of a chunk to repeat at the start
        of the next chunk (within the same section).
    doc_title:
        Optional document-level title prepended to every breadcrumb.
    """
    sections = _extract_sections(text)
    chunks: list[str] = []

    for section in sections:
        heading_prefix = ""
        if section.title:
            marker = "#" * max(section.level, 1)
            heading_prefix = f"{marker} {section.title}\n\n"
        elif doc_title:
            heading_prefix = f"# {doc_title}\n\n"

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", section.body) if p.strip()]
        if not paragraphs:
            continue

        current_words: list[str] = []
        current_tokens = 0

        def _flush(words: list[str], _prefix: str = heading_prefix) -> str:
            body = " ".join(words)
            return (_prefix + body).strip()

        for para in paragraphs:
            para_tokens = _approx_tokens(para)

            # Paragraph fits in remaining budget
            if current_tokens + para_tokens <= target_tokens:
                current_words.extend(para.split())
                current_tokens += para_tokens
            else:
                # Flush current buffer
                if current_words:
                    chunks.append(_flush(current_words))
                    # Keep overlap from tail
                    overlap_words = current_words[-overlap_tokens:] if overlap_tokens else []
                    current_words = overlap_words + para.split()
                    current_tokens = _approx_tokens(" ".join(current_words))
                else:
                    # Paragraph alone exceeds target — split by sentences
                    sentences = _split_sentences(para)
                    for sent in sentences:
                        sent_tokens = _approx_tokens(sent)
                        if current_tokens + sent_tokens <= target_tokens:
                            current_words.extend(sent.split())
                            current_tokens += sent_tokens
                        else:
                            if current_words:
                                chunks.append(_flush(current_words))
                                overlap_words = current_words[-overlap_tokens:] if overlap_tokens else []
                                current_words = overlap_words + sent.split()
                                current_tokens = _approx_tokens(" ".join(current_words))
                            else:
                                # Single sentence exceeds target and has no
                                # delimiters to split on — hard-split by words,
                                # leaving room for the heading prefix.
                                budget = max(1, target_tokens - _approx_tokens(heading_prefix))
                                words = sent.split()
                                for i in range(0, len(words), budget):
                                    chunks.append(_flush(words[i : i + budget]))
                                current_words = []
                                current_tokens = 0

        if current_words:
            chunks.append(_flush(current_words))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# News paragraph chunker
# ---------------------------------------------------------------------------

def paragraph_chunk(
    text: str,
    *,
    min_tokens: int = 256,
    max_tokens: int = 400,
) -> list[str]:
    """Split *text* (a news article) into chunks of *min_tokens*–*max_tokens*.

    Splits on paragraph breaks first, then sentence breaks if needed.
    No overlap (recency is more important than cross-chunk coherence).
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _approx_tokens(para)

        if current_tokens + para_tokens <= max_tokens:
            current_parts.append(para)
            current_tokens += para_tokens

            if current_tokens >= min_tokens:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_tokens = 0
        else:
            # Flush current buffer first
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_tokens = 0

            if para_tokens <= max_tokens:
                current_parts.append(para)
                current_tokens = para_tokens
            else:
                # Split paragraph by sentences
                sentences = _split_sentences(para)
                for sent in sentences:
                    sent_tokens = _approx_tokens(sent)
                    if current_tokens + sent_tokens <= max_tokens:
                        current_parts.append(sent)
                        current_tokens += sent_tokens
                        if current_tokens >= min_tokens:
                            chunks.append(" ".join(current_parts))
                            current_parts = []
                            current_tokens = 0
                    else:
                        if current_parts:
                            chunks.append(" ".join(current_parts))
                        # sentence itself may exceed max — emit as-is
                        chunks.append(sent)
                        current_parts = []
                        current_tokens = 0

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# API JSON cache summarizer
# ---------------------------------------------------------------------------

def cache_summarize(data: dict[str, Any], *, max_tokens: int = 400) -> str:
    """Produce a compact, human-readable text representation of *data*.

    Strategy:
    1. If ``data`` has a ``"summary"`` or ``"description"`` key, use it directly.
    2. Otherwise, flatten the JSON to ``key: value`` lines and truncate to
       *max_tokens* words.

    Returns a single string suitable for embedding as one cache chunk.
    """
    # Prefer existing prose fields
    for key in ("summary", "description", "text", "content", "answer"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            text = val.strip()
            words = text.split()
            if len(words) <= max_tokens:
                return text
            return " ".join(words[:max_tokens])

    # Flatten to lines
    lines: list[str] = []
    _flatten_dict(data, prefix="", lines=lines)
    text = "\n".join(lines)
    words = text.split()
    if len(words) > max_tokens:
        text = " ".join(words[:max_tokens])
    return text


def _flatten_dict(
    obj: Any,
    prefix: str,
    lines: list[str],
    *,
    max_depth: int = 4,
    depth: int = 0,
) -> None:
    """Recursively flatten a dict/list to ``key: value`` lines."""
    if depth >= max_depth:
        lines.append(f"{prefix}: {json.dumps(obj)[:200]}")
        return

    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                _flatten_dict(v, full_key, lines, max_depth=max_depth, depth=depth + 1)
            else:
                lines.append(f"{full_key}: {v}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:10]):  # cap list length
            _flatten_dict(item, f"{prefix}[{i}]", lines, max_depth=max_depth, depth=depth + 1)
    else:
        lines.append(f"{prefix}: {obj}")
