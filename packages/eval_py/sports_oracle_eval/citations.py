"""Deterministic citation-contract check.

The Sports Oracle contract (ARCHITECTURE.md) is that every claim maps to a
``[n]`` marker resolving to a real source. This module checks that contract
without any LLM: it parses ``[n]`` markers from the answer text and reconciles
them against the citation list attached to the turn.
"""

from __future__ import annotations

import re
from typing import Any

from sports_oracle_shared import Citation

from sports_oracle_eval.schema import CitationCheck

# Matches single citation markers like [1] or [12]. Deliberately does NOT match
# ranges/markdown link refs like [1-3] or [text](url).
_MARKER_RE = re.compile(r"\[(\d{1,3})\]")


def _ref_num(c: Citation | dict[str, Any]) -> int:
    if isinstance(c, Citation):
        return c.ref_num
    return int(c["ref_num"])


def extract_markers(answer: str) -> list[int]:
    """Return the distinct ``[n]`` numbers referenced in *answer*, in order."""
    seen: dict[int, None] = {}
    for m in _MARKER_RE.finditer(answer or ""):
        seen.setdefault(int(m.group(1)), None)
    return list(seen.keys())


def check_citations(
    answer: str,
    citations: list[Citation | dict[str, Any]],
) -> CitationCheck:
    """Reconcile ``[n]`` markers in *answer* against *citations*.

    Valid means: no marker points at a missing citation (no orphans). An
    answer with no markers and no citations is trivially valid; an answer with
    no markers but supplied citations is valid but flags them as unused.
    """
    referenced = extract_markers(answer)
    available = sorted({_ref_num(c) for c in citations})
    available_set = set(available)
    referenced_set = set(referenced)

    orphan_markers = sorted(referenced_set - available_set)
    unused_citations = sorted(available_set - referenced_set)

    return CitationCheck(
        valid=len(orphan_markers) == 0,
        referenced=referenced,
        available=available,
        orphan_markers=orphan_markers,
        unused_citations=unused_citations,
    )
