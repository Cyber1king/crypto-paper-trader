"""Read-only access to the frozen BTC/USDT research dataset.

This module **reads** the dataset through the engine's existing public
interfaces. It does not parse CSV, does not implement a second loader, and
does not alter the data in any way:

* ``dataset.load_dataset`` performs the read.
* ``walkforward.validate_dataset_integrity`` verifies the SHA-256 fingerprint,
  the declared bounds and count, strict timestamp ordering, and exact 3600 s
  spacing.
* ``walkforward.sha256_of_file`` computes the fingerprint.

Loading happens **once per API process** and the result is cached, so repeated
requests do not re-read the file. The cached series is returned as a tuple of
frozen ``Candle`` dataclasses, which makes mutation impossible rather than
merely discouraged.

Nothing here contacts a network, downloads anything, interpolates a gap, or
generates a price. If the dataset is missing or fails validation, loading
raises and the endpoint returns an error rather than inventing data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    DATASET_SHA256,
    validate_dataset_integrity,
)

#: ``marketdata.py`` -> ``paper_api`` -> ``src`` -> ``research_engine``.
#: Resolving against the package location rather than the process working
#: directory means the endpoint serves the same file regardless of where uvicorn
#: was launched from.
RESEARCH_ENGINE_ROOT = Path(__file__).resolve().parents[2]

#: Default number of candles returned when the caller supplies no dates: a
#: bounded *recent* slice, never the whole 17,544-candle series.
DEFAULT_LIMIT = 200

#: Upper bound on a single request. Generous enough for a chart, small enough
#: that one call cannot serialise the entire dataset.
MAX_LIMIT = 5000

#: Human-readable provenance. Deliberately not a path: no filesystem location
#: is ever exposed through the API.
SOURCE_LABEL = "local-research-dataset"


def dataset_path() -> Path:
    """Absolute path of the frozen dataset. Internal use only."""

    return RESEARCH_ENGINE_ROOT / DATASET_PATH


@lru_cache(maxsize=1)
def load_research_candles() -> tuple:
    """Load, verify and cache the research candles for this process.

    Raises on a missing file, a hash mismatch, a wrong candle count, a
    timestamp ordering problem, or incorrect candle spacing. There is no
    fallback: a dataset that cannot be verified is not served.
    """

    path = dataset_path()
    candles, _summary = load_dataset(path)

    # Full integrity check: hash, declared bounds and count, strict ordering,
    # exact 1h spacing. Measured at ~8 ms, so running it once per process is
    # effectively free and removes any doubt about what is being served.
    validate_dataset_integrity(candles, path=path)

    return tuple(candles)


def dataset_identity() -> str:
    """SHA-256 of the served file. Stable identity, not a path."""

    return DATASET_SHA256


@lru_cache(maxsize=1)
def candle_index_by_timestamp() -> dict:
    """Map each bar's naive-UTC timestamp to its index.

    Built once alongside the candle cache so an exact-timestamp lookup is a
    dictionary hit rather than a scan. Exact matching only: the endpoint must
    refuse a timestamp that is not a real bar rather than interpolating.
    """

    return {
        candle.timestamp: index
        for index, candle in enumerate(load_research_candles())
    }


def as_utc(moment: datetime) -> datetime:
    """Return ``moment`` as an aware UTC datetime.

    Source timestamps are naive. Rather than letting an aware value be
    reinterpreted in the server's local zone - the classic silent conversion
    bug - a naive source timestamp is *declared* to be UTC and an aware one is
    converted to UTC explicitly.
    """

    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)

    return moment.astimezone(timezone.utc)


def as_naive_utc(moment: datetime) -> datetime:
    """Normalise a query bound to naive UTC for comparison with the source.

    A caller may pass ``2024-01-01T00:00:00Z`` or ``2024-01-01T00:00:00``. Both
    denote the same instant. Converting the aware form to UTC and dropping the
    marker lets it compare against the naive source series.
    """

    if moment.tzinfo is None:
        return moment

    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def select_candles(
    candles: tuple,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> tuple[list, bool]:
    """Filter the series and apply the limit.

    Bounds are **inclusive** on both ends. Source ordering is preserved - the
    result is always chronological ascending. When more candles match than
    ``limit`` allows, the **most recent** ``limit`` are returned, which is the
    useful slice for a chart and matches the unbounded-request default.

    Returns the selected candles and whether the limit truncated the range.
    No candle is ever interpolated, synthesised or reordered.
    """

    lower = as_naive_utc(start) if start is not None else None
    upper = as_naive_utc(end) if end is not None else None

    matched = [
        candle
        for candle in candles
        if (lower is None or candle.timestamp >= lower)
        and (upper is None or candle.timestamp <= upper)
    ]

    if len(matched) > limit:
        return matched[-limit:], True

    return matched, False