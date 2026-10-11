"""Missing-interval classification for 24x7 crypto series.

Phase 41. A gap in an hourly series is a **data defect**, not a market closure:
crypto spot trades continuously. That distinguishes this module from forex, where
a missing hour may be a legitimate weekend or holiday closure and therefore needs
session awareness that does not exist in this repository.

Keeping the distinction explicit matters because the two cases demand opposite
responses. For crypto a gap means the dataset is incomplete and should be
repaired or rejected. For forex a gap might be expected, and rejecting it would
be wrong. This module therefore refuses to generalise to forex rather than
guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import Candle

__all__ = [
    "Gap",
    "classify_intervals",
    "CRYPTO_SPOT",
    "FOREX_REFERENCE",
]

#: Market classification this module can speak about. Only 24x7 crypto.
CRYPTO_SPOT = "crypto_spot"

#: Named for documentation completeness only. Deliberately unsupported: no
#: session, holiday or DST validator exists in this repository, so a "missing
#: interval" in forex cannot be classified as closure rather than defect.
FOREX_REFERENCE = "forex_reference_rates"

_GAP_UNSUPPORTED = (
    "interval classification is implemented for 24x7 crypto spot only; "
    "classifying a gap in a forex series requires session, holiday and DST "
    "knowledge that this repository does not have. Refused rather than guessed, "
    "because in forex a missing bar may be a legitimate closure rather than a "
    "defect, and guessing wrong in either direction is harmful."
)


@dataclass(frozen=True)
class Gap:
    """One missing interval between two consecutive candles."""

    after: datetime
    before: datetime
    expected_seconds: int
    observed_seconds: int

    @property
    def missing_bars(self) -> int:
        """Whole bars absent, excluding the two endpoints that are present."""

        return max(0, (self.observed_seconds // self.expected_seconds) - 1)

    def as_record(self) -> dict[str, object]:
        return {
            "after": self.after.isoformat(),
            "before": self.before.isoformat(),
            "expected_seconds": self.expected_seconds,
            "observed_seconds": self.observed_seconds,
            "missing_bars": self.missing_bars,
        }


def classify_intervals(
    candles: Sequence[Candle],
    *,
    expected_interval_seconds: int,
    market_type: str = CRYPTO_SPOT,
    allow_gaps: bool = False,
) -> list[Gap]:
    """Return every gap against the expected spacing.

    ``allow_gaps=False`` (the default) raises on the first gap, because an
    incomplete series silently evaluated is worse than one refused.

    ``allow_gaps=True`` returns the gaps instead, for a caller that wants to
    repair or subset first. Even then, in 24x7 crypto every gap is a defect:
    there is no legitimate closure to distinguish it from.
    """

    if market_type != CRYPTO_SPOT:
        raise ValueError(_GAP_UNSUPPORTED)

    if expected_interval_seconds <= 0:
        raise ValueError(
            f"expected_interval_seconds must be positive, got "
            f"{expected_interval_seconds}"
        )

    if len(candles) < 2:
        return []

    gaps: list[Gap] = []
    for previous, current in zip(candles, candles[1:]):
        observed = int(
            (current.timestamp - previous.timestamp).total_seconds()
        )
        if observed == expected_interval_seconds:
            continue

        if observed <= 0:
            # Ordering is validate_dataset's concern; here it is a gap of zero
            # width, which is a duplicate or reversal rather than a closure.
            raise ValueError(
                f"non-increasing timestamps between {previous.timestamp} and "
                f"{current.timestamp}; ordering must be validated first"
            )

        gap = Gap(
            after=previous.timestamp,
            before=current.timestamp,
            expected_seconds=expected_interval_seconds,
            observed_seconds=observed,
        )
        gaps.append(gap)

        if not allow_gaps:
            raise ValueError(
                f"missing {gap.missing_bars} bar(s) between "
                f"{previous.timestamp.isoformat()} and "
                f"{current.timestamp.isoformat()}: expected "
                f"{expected_interval_seconds}s spacing, observed {observed}s. "
                "Crypto spot trades continuously, so a gap is a data defect "
                "rather than a market closure."
            )

    return gaps


def expected_bar_count(
    first: datetime,
    last: datetime,
    *,
    expected_interval_seconds: int,
) -> int:
    """Bars a complete series would contain, for a completeness cross-check."""

    if last < first:
        raise ValueError(f"last {last.isoformat()} precedes first {first.isoformat()}")
    span = int((last - first).total_seconds())
    return span // expected_interval_seconds + 1


def contiguous_slice(
    candles: Sequence[Candle],
    *,
    expected_interval_seconds: int,
    market_type: str = CRYPTO_SPOT,
) -> tuple[int, int, list[Gap]]:
    """Locate the longest contiguous run, without modifying the data.

    Returns ``(start_index, end_index_exclusive, dropped_gaps)``. Repairing by
    dropping data is a decision for the caller; this only reports where a
    contiguous series exists, so no price is ever invented or interpolated.
    """

    gaps = classify_intervals(
        candles,
        expected_interval_seconds=expected_interval_seconds,
        market_type=market_type,
        allow_gaps=True,
    )

    if not gaps:
        return 0, len(candles), []

    best_start, best_end = 0, 0
    run_start = 0
    for gap in gaps:
        run_length = 0
        for index, candle in enumerate(candles):
            if candle.timestamp == gap.before:
                run_start = index
                run_length = len(candles) - index
                break
        if run_length > (best_end - best_start):
            best_start, best_end = run_start, run_start + run_length

    return best_start, best_end, gaps