"""Sidecar per-bar identity index for protected research windows.

The registry (``data/research_registry.json``) records whole-series and
evaluation-slice fingerprints. Those catch an exact copy and an exact evaluation
slice. They do not catch an arbitrary sub-slice -- a middle chunk of the reserved
window, or a handful of bars lifted out of the middle of it.

This module holds those per-bar digests so the guard can recognise *partial*
protected content. Keeping them here rather than in the registry is deliberate:
the registry stays a short, human-reviewable document, while this is a 2 MB
machine artefact that exists to be read by code.

Design notes
------------
* Digests are 16 bytes (32 hex chars) -- a truncated SHA-256 per bar. Long
  enough that a collision is not a practical concern, short enough that indexing
  48k bars stays small.
* A match is a *threshold*, not any-hit. One coincidentally identical synthetic
  candle must not make an unrelated dataset look protected, so a series is
  treated as protected only when at least half its bars are registered, and
  never when it has fewer than three.
* The index is derived data, fully reconstructible from the datasets via
  :func:`build_index`. It is not an independent source of truth, and a
  disagreement between this index and a dataset file means the index is stale.

Nothing here computes prices, signals, trades or performance. It hashes candles
that already exist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "INDEX_FILENAME",
    "line_digest",
    "build_index",
    "load_index",
    "index_path",
    "minimum_bars_for_match",
    "is_indexed_series",
]

#: Bars below this count are never treated as protected, so a one- or two-bar
#: synthetic fixture cannot trip the partial-match rule.
MINIMUM_BARS = 3

#: Fraction of a supplied series that must appear in an index before the series
#: is treated as protected.
MATCH_FRACTION = 0.5


def _root() -> Path:
    """``src/crypto_paper_lab`` -> ``data``."""

    return Path(__file__).resolve().parents[2] / "data"


INDEX_FILENAME = "research_registry.candle_index.json"


def index_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return _root() / INDEX_FILENAME


def line_digest(candle: Any) -> str:
    """Canonical digest of one candle.

    Must stay byte-identical to
    :func:`crypto_paper_lab.researchguard.candle_fingerprint`, because a series
    is only recognised when these agree. ``test_index_matches_guard_fingerprint``
    enforces that.
    """

    payload = candle.timestamp.isoformat().encode("utf-8") + b"|"
    for value in (candle.open, candle.high, candle.low, candle.close, candle.volume):
        payload += repr(float(value)).encode("ascii") + b","
    return hashlib.sha256(payload).hexdigest()[:32]


def build_index(candles: Sequence[Any]) -> list[str]:
    return [line_digest(c) for c in candles]


def load_index(path: str | Path | None = None) -> dict[str, Any]:
    """Load the index. A missing index is an empty mapping, not an error.

    Callers treat an absent index as "no per-bar identity recorded", which is the
    pre-Phase-40 behaviour. That is a deliberate, documented degradation: the
    whole-series and evaluation-slice fingerprints still apply.
    """

    target = index_path(path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def minimum_bars_for_match(supplied: int) -> int:
    return max(MINIMUM_BARS, (supplied + 1) // 2)


def is_indexed_series(candles: Sequence[Any], index: dict[str, Any] | None = None) -> str | None:
    """Return the window key whose index covers this series, else ``None``."""

    if len(candles) < MINIMUM_BARS:
        return None

    supplied = {d for d in build_index(candles)}
    if not supplied:
        return None
    required = minimum_bars_for_match(len(supplied))

    windows = index if index is not None else load_index()
    for key, digests in windows.items():
        if not isinstance(digests, list) or not digests:
            continue
        registered = {str(d) for d in digests}
        if len(supplied & registered) >= required:
            return str(key)
    return None