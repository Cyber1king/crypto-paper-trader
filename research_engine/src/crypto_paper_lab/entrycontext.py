"""Phase 14C descriptive entry-context analysis.

This module **describes** the trades the existing strategy already produced.
It does not optimise, tune, rank or select anything.

Three structural guarantees are enforced by construction rather than by
convention, because each one has been violated somewhere in this project's
history:

1. **Outcomes cannot leak into the feature stage.** A :class:`TradeRecord`
   keeps entry-time values in ``record.features`` and outcome values in
   ``record.outcome``. The D1 and bin-declaration functions are typed against
   ``record.features`` and have no parameter through which an outcome could
   arrive, so "what bins do we use?" cannot depend on P&L even by accident.

2. **``baseline`` and ``A2`` are never pooled.** Every aggregation takes
   records for exactly one ``config_name``; the driver iterates passes and
   joins nothing.

3. **Bins are pre-declared, not searched.** ``QUANTILES`` is a module
   constant fixed before any outcome was examined, and edges are derived from
   feature values only. There is no code path that adjusts an edge to improve
   a cell.

The whole-sample quantile edges are a known limitation and are labelled as
such wherever they appear: an edge computed over all trades means a trade in
window 1 was binned using information from window 6. Phase 14A §9.2 classifies
this as acceptable only as *a descriptive grouping of the sample*, never as a
live-applicable rule. That is the only use made of it here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import fmean, median, stdev
from typing import Iterable, Mapping, Sequence

# Availability labels. Mirrors the Phase 14A §7.3 requirement that every
# feature carry an explicit classification.
ENTRY_TIME = "ENTRY_TIME"
DERIVED_FROM_ENTRY_TIME = "DERIVED_FROM_ENTRY_TIME"
OUTCOME_SIDE = "OUTCOME_SIDE"

#: Pre-declared quartile edges. Fixed before any outcome was inspected.
QUANTILES: tuple[float, ...] = (0.25, 0.50, 0.75)

#: A cell below this many trades is reported but flagged as not interpretable.
#: Phase 14A §14 Q4 records doubt that regime cells are supportable at all at
#: this sample size. The floor is calibrated on **cell counts only**, with no
#: reference to any outcome: quartile cells hold ~67 trades and pass, while the
#: 24 retest trades do not. 20 would have been too permissive here; 30 is a
#: reporting label, not a licence to interpret.
MIN_CELL = 30

#: Quantiles reported for every continuous feature in D1.
REPORT_QUANTILES: tuple[float, ...] = (0.05, 0.25, 0.50, 0.75, 0.95)


@dataclass(frozen=True)
class FeatureSpec:
    """Declaration of one analysable entry-time feature."""

    name: str
    kind: str
    availability: str
    source: str
    rationale: str
    #: True when the raw value is a price level and therefore not stationary
    #: across an 18-month window spanning a large price move.
    price_scale: bool = False


# ---------------------------------------------------------------------------
# Pre-declared feature list.
#
# Frozen before any outcome was examined. Every entry is justified by Phase 14A
# §6/§7 or by Phase 14B instrumentation. Nothing here was added because it
# happened to separate winners from losers.
# ---------------------------------------------------------------------------

FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        name="side",
        kind="categorical",
        availability=ENTRY_TIME,
        source="PaperTrade.side",
        rationale="Phase 14A Class A; direction is known at entry.",
    ),
    FeatureSpec(
        name="trend_state",
        kind="categorical",
        availability=ENTRY_TIME,
        source="PaperTrade.trend_state",
        rationale=(
            "Phase 14A Class B. Recorded for completeness, but it is exactly "
            "determined by side in this strategy, so it carries no "
            "independent information and is not used as a D2 dimension."
        ),
    ),
    FeatureSpec(
        name="signal_kind",
        kind="categorical",
        availability=ENTRY_TIME,
        source="derived from PaperTrade.reason",
        rationale=(
            "Phase 14A §3.3. Retest vs breakout entry is knowable at entry."
        ),
    ),
    FeatureSpec(
        name="signal_close",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B Signal.signal_close",
        rationale="Close of the signal candle; the last knowable price.",
        price_scale=True,
    ),
    FeatureSpec(
        name="breakout_distance",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B Signal.breakout_distance",
        rationale=(
            "Phase 14A §4.1 identified this as computed then discarded. "
            "Fractional distance beyond the broken level, so it is "
            "comparable across price levels."
        ),
    ),
    FeatureSpec(
        name="retest_distance",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B Signal.retest_distance",
        rationale=(
            "Retest quality at entry. Present only on retest entries, so the "
            "sample is far too small to condition on; reported, not analysed."
        ),
    ),
    FeatureSpec(
        name="realised_volatility",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B indicator; stdev of trailing 1h simple returns",
        rationale=(
            "Phase 14A Class C. Per-period dispersion, NOT annualised and not "
            "ATR. Scale-free, so directly comparable across the sample."
        ),
    ),
    FeatureSpec(
        name="mean_range",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B indicator; mean trailing high-low",
        rationale="Phase 14A Class C. Range proxy; NOT ATR.",
        price_scale=True,
    ),
    FeatureSpec(
        name="mean_range_pct",
        kind="continuous",
        availability=DERIVED_FROM_ENTRY_TIME,
        source="mean_range / signal_close",
        rationale=(
            "mean_range is in absolute price units, so over a sample where "
            "price roughly doubles it mostly encodes calendar position. "
            "Dividing by the signal close makes it stationary. Derived only "
            "from entry-time recorded fields; no outcome involved."
        ),
    ),
    FeatureSpec(
        name="support_at_entry",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B PaperTrade.support_at_entry",
        rationale="Trailing support in force at signal time.",
        price_scale=True,
    ),
    FeatureSpec(
        name="resistance_at_entry",
        kind="continuous",
        availability=ENTRY_TIME,
        source="Phase 14B PaperTrade.resistance_at_entry",
        rationale="Trailing resistance in force at signal time.",
        price_scale=True,
    ),
    FeatureSpec(
        name="level_width_pct",
        kind="continuous",
        availability=DERIVED_FROM_ENTRY_TIME,
        source=(
            "(resistance_at_entry - support_at_entry) / support_at_entry"
        ),
        rationale=(
            "Phase 14A §6 Class B 'trailing range width'. Normalised by "
            "support so it is not a price level."
        ),
    ),
    FeatureSpec(
        name="range_position",
        kind="continuous",
        availability=DERIVED_FROM_ENTRY_TIME,
        source=(
            "(signal_close - support_at_entry) "
            "/ (resistance_at_entry - support_at_entry)"
        ),
        rationale=(
            "Phase 14A §6 Class B 'distance to recent extreme'. Where price "
            "sits inside the trailing range. Note this is largely determined "
            "by side, since a long breaks the upper level and a short the "
            "lower one."
        ),
    ),
)

FEATURE_BY_NAME: Mapping[str, FeatureSpec] = {f.name: f for f in FEATURES}

#: D2 dimensions. Pre-declared. Each is justified in FEATURES above.
CATEGORICAL_DIMENSIONS: tuple[str, ...] = ("side", "signal_kind")

CONTINUOUS_DIMENSIONS: tuple[str, ...] = (
    "breakout_distance",
    "realised_volatility",
    "mean_range_pct",
    "level_width_pct",
    "range_position",
)

#: Reported in D1/D2 but deliberately NOT conditioned on, with the reason.
EXCLUDED_FROM_CONDITIONS: Mapping[str, str] = {
    "trend_state": "exactly determined by side; adds no information",
    "retest_distance": (
        "present on too few trades to form a defensible cell"
    ),
    "signal_close": "price level; would encode calendar position, not context",
    "mean_range": "absolute price units; superseded by mean_range_pct",
    "support_at_entry": "price level; superseded by level_width_pct",
    "resistance_at_entry": "price level; superseded by level_width_pct",
}


@dataclass
class TradeRecord:
    """One trade, with entry-time values structurally separated from outcomes.

    The split is the point of this class. D1 and the bin edges are computed
    from ``features`` alone, so they cannot be contaminated by ``outcome``.
    """

    window_id: int
    config_name: str
    entry_time: datetime
    features: dict = field(default_factory=dict)
    outcome: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


#: The only four ``reason`` values that can open a position. Matching is exact
#: rather than by substring: ``"no confirmed breakout or retest"`` contains the
#: word "retest" but describes a *flat* signal, so substring matching would
#: misclassify it as a retest entry.
RETEST_REASONS = frozenset({"bullish retest", "bearish retest"})
BREAKOUT_REASONS = frozenset({"uptrend breakout", "downtrend breakdown"})


def signal_kind(reason: str) -> str:
    """Classify the entry as a retest or a breakout.

    Phase 14A §3.3 established these are the only two entry shapes the
    strategy produces, recoverable from the fixed ``reason`` strings.
    """

    if reason in RETEST_REASONS:
        return "retest"

    if reason in BREAKOUT_REASONS:
        return "breakout"

    return "other"


def record_from_trade(trade, window_id: int, config_name: str) -> TradeRecord:
    """Project a :class:`PaperTrade` onto a :class:`TradeRecord`.

    Only fields recorded at or before the fill enter ``features``. Anything
    known only at the close goes into ``outcome``.
    """

    features: dict = {
        "side": trade.side,
        "trend_state": trade.trend_state,
        "signal_kind": signal_kind(trade.reason),
        "signal_close": trade.signal_close,
        "breakout_distance": trade.breakout_distance,
        "retest_distance": trade.retest_distance,
        "realised_volatility": trade.realised_volatility,
        "mean_range": trade.mean_range,
        "support_at_entry": trade.support_at_entry,
        "resistance_at_entry": trade.resistance_at_entry,
    }

    features.update(_derived_features(features))

    net_pnl = trade.net_pnl
    outcome: dict = {
        "pnl": trade.pnl,
        "net_pnl": net_pnl,
        "total_friction": trade.total_friction,
        "bars_held": trade.bars_held,
        "exit_reason": trade.exit_reason,
        "win": None if net_pnl is None else net_pnl > 0.0,
    }

    return TradeRecord(
        window_id=window_id,
        config_name=config_name,
        entry_time=trade.entry_time,
        features=features,
        outcome=outcome,
    )


def _derived_features(features: Mapping) -> dict:
    """Entry-time ratios built only from already-recorded entry-time fields."""

    derived: dict = {}

    signal_close = features.get("signal_close")
    mean_range = features.get("mean_range")
    support = features.get("support_at_entry")
    resistance = features.get("resistance_at_entry")

    if signal_close and mean_range is not None:
        derived["mean_range_pct"] = mean_range / signal_close
    else:
        derived["mean_range_pct"] = None

    if support and resistance is not None:
        width = resistance - support
        derived["level_width_pct"] = width / support
        if signal_close is not None and width:
            derived["range_position"] = (signal_close - support) / width
        else:
            derived["range_position"] = None
    else:
        derived["level_width_pct"] = None
        derived["range_position"] = None

    return derived


def collect_records(runs, config_name: str) -> list[TradeRecord]:
    """Flatten walk-forward runs into records for a single configuration."""

    records: list[TradeRecord] = []

    for run in runs:
        for trade in run.result.trades:
            records.append(
                record_from_trade(
                    trade, run.resolved.window_id, config_name
                )
            )

    return records


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def quantile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated quantile.

    Matches the usual ``numpy.percentile`` default so the number is not an
    artefact of a different convention.
    """

    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return float(ordered[0])

    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower

    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _numeric(values: Iterable) -> list[float]:
    """Drop ``None`` and non-numeric entries, preserving order."""

    out: list[float] = []

    for value in values:
        if value is None:
            continue

        if isinstance(value, bool):
            continue

        if isinstance(value, (int, float)):
            out.append(float(value))

    return out


def _round(value, digits: int = 10):
    """Round for output so repeated runs are byte-identical."""

    if value is None:
        return None

    if isinstance(value, float):
        return round(value, digits)

    return value


def _ranks(values: Sequence[float]) -> list[float]:
    """Average ranks, ties shared, for a rank-correlation summary."""

    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0

    while i < len(order):
        j = i

        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1

        average = (i + j) / 2.0 + 1.0

        for k in range(i, j + 1):
            ranks[order[k]] = average

        i = j + 1

    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation. Descriptive only; no p-value, no test.

    Reported because Phase 14A §9.3 recommends continuous summaries over
    bucketing. It is a description of rank co-movement in this sample and
    carries no inferential claim.
    """

    if len(xs) != len(ys) or len(xs) < 3:
        return None

    rx = _ranks(xs)
    ry = _ranks(ys)
    mx = fmean(rx)
    my = fmean(ry)

    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5

    if not dx or not dy:
        return None

    return num / (dx * dy)


# ---------------------------------------------------------------------------
# D1 - feature distributions
# ---------------------------------------------------------------------------


def feature_summary(records: Sequence[TradeRecord], spec: FeatureSpec) -> dict:
    """Summarise one entry-time feature.

    Reads ``record.features`` only. There is no parameter by which an outcome
    could reach this function.
    """

    values = [r.features.get(spec.name) for r in records]
    row: dict = {
        "feature": spec.name,
        "kind": spec.kind,
        "availability": spec.availability,
        "price_scale": spec.price_scale,
        "n_total": len(values),
    }

    if spec.kind == "categorical":
        counts: dict[str, int] = {}

        for value in values:
            key = "MISSING" if value is None else str(value)
            counts[key] = counts.get(key, 0) + 1

        row["n_present"] = sum(
            n for k, n in counts.items() if k != "MISSING"
        )
        row["n_missing"] = counts.get("MISSING", 0)
        row["levels"] = "; ".join(
            f"{k}={counts[k]} ({counts[k] / len(values):.4f})"
            for k in sorted(counts)
        )
        row["count"] = None
        row["missing"] = None
        row["minimum"] = None
        row["maximum"] = None
        row["mean"] = None
        row["median"] = None
        row["stdev"] = None
        row["quantiles"] = ""
        return row

    numeric = _numeric(values)
    present = len(numeric)
    row["n_present"] = present
    row["n_missing"] = len(values) - present
    row["count"] = present
    row["missing"] = len(values) - present

    if not numeric:
        row.update(
            {
                "levels": "",
                "minimum": None,
                "maximum": None,
                "mean": None,
                "median": None,
                "stdev": None,
                "quantiles": "",
            }
        )
        return row

    row["levels"] = ""
    row["minimum"] = _round(min(numeric))
    row["maximum"] = _round(max(numeric))
    row["mean"] = _round(fmean(numeric))
    row["median"] = _round(median(numeric))
    row["stdev"] = _round(stdev(numeric) if present > 1 else None)
    row["quantiles"] = "; ".join(
        f"q{int(q * 100):02d}={_round(quantile(numeric, q))}"
        for q in REPORT_QUANTILES
    )

    return row


def feature_table(records: Sequence[TradeRecord]) -> list[dict]:
    """D1 for every pre-declared feature, in declaration order."""

    return [feature_summary(records, spec) for spec in FEATURES]


FEATURE_CSV_FIELDS: tuple[str, ...] = (
    "config_name",
    "feature",
    "kind",
    "availability",
    "price_scale",
    "n_total",
    "n_present",
    "n_missing",
    "levels",
    "count",
    "missing",
    "minimum",
    "maximum",
    "mean",
    "median",
    "stdev",
    "quantiles",
    "excluded_from_conditions",
    "exclusion_reason",
)


# ---------------------------------------------------------------------------
# D2 bins - pre-declared, feature-derived, outcome-blind
# ---------------------------------------------------------------------------


def declare_bins(
    records: Sequence[TradeRecord],
    dimensions: Sequence[str] = CONTINUOUS_DIMENSIONS,
    quantiles: Sequence[float] = QUANTILES,
) -> dict[str, list[float]]:
    """Derive quartile edges from feature values alone.

    Reads ``record.features`` only. Returns ``{dimension: [lo, mid, hi]}``.

    These edges are computed over the whole sample, so a trade in window 1 is
    binned partly using information from window 6. That is accepted only as a
    *descriptive grouping of this sample* (Phase 14A §9.2) and is labelled as
    such in every output. It is not a live-applicable rule and no bin edge may
    be moved in response to an outcome.
    """

    bins: dict[str, list[float]] = {}

    for name in dimensions:
        numeric = _numeric(r.features.get(name) for r in records)

        if not numeric:
            bins[name] = []
            continue

        edges: list[float] = []

        for q in quantiles:
            edge = quantile(numeric, q)

            if edge is not None:
                edges.append(_round(edge, 12))

        bins[name] = edges

    return bins


def assign_bin(value, edges: Sequence[float]) -> str | None:
    """Label a value with its quartile cell name.

    Returns ``None`` when the value is missing or no edges were declared.
    Ties at an edge fall into the lower cell so that every trade lands in
    exactly one cell.
    """

    if value is None or not edges:
        return None

    for index, edge in enumerate(edges):
        if value < edge:
            return f"q{index * 25:02d}_q{(index + 1) * 25:02d}"

    return f"q{len(edges) * 25:02d}_inf"


def condition_cells(
    records: Sequence[TradeRecord], bins: Mapping[str, Sequence[float]]
) -> list[tuple[str, str, list[TradeRecord]]]:
    """Build every ``(dimension, cell, records)`` group.

    Categorical dimensions yield their observed levels; continuous dimensions
    yield the pre-declared quartile cells. Groups are emitted in a fixed order
    so output is byte-stable across runs.
    """

    cells: list[tuple[str, str, list[TradeRecord]]] = []

    for dimension in CATEGORICAL_DIMENSIONS:
        levels = sorted(
            {
                "MISSING" if r.features.get(dimension) is None
                else str(r.features.get(dimension))
                for r in records
            }
        )

        for level in levels:
            members = [
                r for r in records
                if (
                    "MISSING" if r.features.get(dimension) is None
                    else str(r.features.get(dimension))
                ) == level
            ]
            cells.append((dimension, level, members))

    for dimension in CONTINUOUS_DIMENSIONS:
        edges = bins.get(dimension, [])

        if not edges:
            continue

        buckets: dict[str, list[TradeRecord]] = {}

        for record in records:
            label = assign_bin(record.features.get(dimension), edges)

            if label is None:
                continue

            buckets.setdefault(label, []).append(record)

        for label in sorted(buckets):
            cells.append((dimension, label, buckets[label]))

    return cells


def outcome_stats(members: Sequence[TradeRecord]) -> dict:
    """Descriptive outcome statistics for one cell.

    Deliberately reports count alongside every rate so a reader cannot quote a
    win rate without its denominator.
    """

    net = _numeric(r.outcome.get("net_pnl") for r in members)
    gross = _numeric(r.outcome.get("pnl") for r in members)
    friction = _numeric(r.outcome.get("total_friction") for r in members)
    bars = _numeric(r.outcome.get("bars_held") for r in members)
    wins = [r.outcome.get("win") for r in members]
    resolved = [w for w in wins if w is not None]
    windows = sorted({r.window_id for r in members})

    return {
        "n_trades": len(members),
        "n_windows": len(windows),
        "window_ids": ";".join(str(w) for w in windows),
        "wins": sum(1 for w in resolved if w),
        "losses": sum(1 for w in resolved if not w),
        "win_rate": (
            round(sum(1 for w in resolved if w) / len(resolved), 10)
            if resolved else None
        ),
        "net_pnl_total": _round(sum(net)) if net else None,
        "net_pnl_mean": _round(fmean(net)) if net else None,
        "net_pnl_median": _round(median(net)) if net else None,
        "gross_pnl_total": _round(sum(gross)) if gross else None,
        "friction_total": _round(sum(friction)) if friction else None,
        "friction_mean": _round(fmean(friction)) if friction else None,
        "bars_held_mean": _round(fmean(bars)) if bars else None,
        "bars_held_median": _round(median(bars)) if bars else None,
        "insufficient_sample": len(members) < MIN_CELL,
    }


def condition_table(
    records: Sequence[TradeRecord],
    bins: Mapping[str, Sequence[float]],
    config_name: str,
) -> list[dict]:
    """D2 for one configuration. Never pools configurations."""

    rows: list[dict] = []

    for dimension, label, members in condition_cells(records, bins):
        stats = outcome_stats(members)
        row = {
            "config_name": config_name,
            "dimension": dimension,
            "cell": label,
            "binning": (
                "predeclared_quartiles_over_whole_sample"
                if dimension in CONTINUOUS_DIMENSIONS
                else "observed_levels"
            ),
        }
        row.update(stats)
        rows.append(row)

    return rows


CONDITION_CSV_FIELDS: tuple[str, ...] = (
    "config_name",
    "dimension",
    "cell",
    "binning",
    "n_trades",
    "n_windows",
    "window_ids",
    "wins",
    "losses",
    "win_rate",
    "net_pnl_total",
    "net_pnl_mean",
    "net_pnl_median",
    "gross_pnl_total",
    "friction_total",
    "friction_mean",
    "bars_held_mean",
    "bars_held_median",
    "insufficient_sample",
)


def rank_associations(records: Sequence[TradeRecord]) -> list[dict]:
    """Spearman rho between each continuous feature and net P&L.

    Descriptive rank co-movement only. No p-value and no significance test is
    computed, because with trades this clustered and windows this few, a
    p-value would imply an independence assumption the sample does not support.
    """

    rows: list[dict] = []

    for name in CONTINUOUS_DIMENSIONS:
        pairs = [
            (float(r.features.get(name)), float(r.outcome.get("net_pnl")))
            for r in records
            if r.features.get(name) is not None
            and r.outcome.get("net_pnl") is not None
        ]

        if len(pairs) < 3:
            rows.append(
                {
                    "config_name": records[0].config_name if records else "",
                    "feature": name,
                    "n_pairs": len(pairs),
                    "spearman_rho": None,
                }
            )
            continue

        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]

        rows.append(
            {
                "config_name": records[0].config_name if records else "",
                "feature": name,
                "n_pairs": len(pairs),
                "spearman_rho": _round(spearman(xs, ys), 10),
            }
        )

    return rows


# ---------------------------------------------------------------------------
# D3 - robustness context
# ---------------------------------------------------------------------------


def robustness_summary(
    records: Sequence[TradeRecord],
    config_name: str,
    bins: Mapping[str, Sequence[float]],
) -> dict:
    """Assemble the sample facts that bound how D2 may be read.

    Reports counts and structural facts. It performs no significance testing
    and draws no conclusion beyond what the counts support.
    """

    net = _numeric(r.outcome.get("net_pnl") for r in records)
    bars = _numeric(r.outcome.get("bars_held") for r in records)
    cells = condition_cells(records, bins)
    small = [
        {"dimension": d, "cell": c, "n_trades": len(m)}
        for d, c, m in cells
        if len(m) < MIN_CELL
    ]

    windows = sorted({r.window_id for r in records})
    per_window = []

    for window_id in windows:
        members = [r for r in records if r.window_id == window_id]
        member_net = _numeric(r.outcome.get("net_pnl") for r in members)
        per_window.append(
            {
                "window_id": window_id,
                "n_trades": len(members),
                "net_pnl_total": _round(sum(member_net)) if member_net else None,
            }
        )

    return {
        "config_name": config_name,
        "n_trades": len(records),
        "n_windows": len(windows),
        "window_ids": windows,
        "cells_tested": len(cells),
        "dimensions_tested": len(CATEGORICAL_DIMENSIONS)
        + len(CONTINUOUS_DIMENSIONS),
        "cells_below_min": len(small),
        "min_cell_size": MIN_CELL,
        "undersized_cells": small,
        "mean_bars_held": _round(fmean(bars)) if bars else None,
        "min_bars_held": _round(min(bars)) if bars else None,
        "max_bars_held": _round(max(bars)) if bars else None,
        "net_pnl_total": _round(sum(net)) if net else None,
        "net_pnl_mean": _round(fmean(net)) if net else None,
        "net_pnl_median": _round(median(net)) if net else None,
        "dependence_note": (
            "One position at a time and a mean holding period of tens of "
            "hours mean trades are mechanically separated, not independent "
            "draws. No interval estimate is reported for that reason."
        ),
        "window_structure_note": (
            "Windows are sequential periods of one continuous series, not "
            "independent samples. Per-window figures describe spread, not "
            "significance."
        ),
        "per_window": per_window,
    }


def trade_population(records: Sequence[TradeRecord]) -> dict:
    """Outcome-side context. Explicitly NOT entry-time."""

    from collections import Counter

    exits = Counter(str(r.outcome.get("exit_reason")) for r in records)
    bars = _numeric(r.outcome.get("bars_held") for r in records)

    return {
        "availability": OUTCOME_SIDE,
        "note": (
            "Descriptive context for the trade population. None of this is "
            "knowable at entry and none of it is used as a condition."
        ),
        "exit_reason_counts": dict(sorted(exits.items())),
        "bars_held_mean": _round(fmean(bars)) if bars else None,
        "bars_held_median": _round(median(bars)) if bars else None,
    }