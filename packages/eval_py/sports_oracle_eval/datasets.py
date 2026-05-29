"""Load the golden evaluation dataset (ground truth from data/reference)."""

from __future__ import annotations

import json
from pathlib import Path

from sports_oracle_eval.schema import EvalSample

_GOLDEN_PATH = Path(__file__).parent / "datasets" / "golden.jsonl"


def load_golden(path: Path | str | None = None) -> list[EvalSample]:
    """Read the golden JSONL set into EvalSamples."""
    p = Path(path) if path else _GOLDEN_PATH
    samples: list[EvalSample] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            samples.append(EvalSample(**json.loads(line)))
    return samples
