"""Phase 13 descriptive window statistics.

Implements the frozen metric set from ``experiments/phase13/PLAN.md`` section
10. Every field here is **descriptive**. This module contains no threshold,
no pass/fail rule, no score, no ranking and no configuration-selection logic,
and it must not grow any.

Metrics that are not available are reported as ``None`` rather than estimated.
In particular ``exposure`` / percent-of-time-in-market is **not** computed:
``stats.py`` has no market-time accounting, and deriving it from ``bars_held``
would be an approximation that ignores gaps and intrabar paths. The
pre-registration forbids fabricating it.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import fmean, median

from .stats import cost_breakdown, median_pnl, performance
from .walkforward import (
    BOUNDARY_POLICY,
    DATASET_SHA256,
    WARMUP_RULE,
    ResolvedWindow,
    WindowRun,
    config_disclosure,
)

#: Exit reason used when ``run_backtest`` force-closes at the final candle.
END_OF_DATA = "end_of_data"


@dataclass(frozen=True)
class WindowStats:
    """Descriptive statistics for one evaluation window.

    All fields are observations. None of them implies a judgement about the
    strategy, and none may be compared across configurations to declare a
    winner.
    """

    # ---- window identity ----
    window_id: int
    config_name: str
    config_repr: str
    config_hash: str
    costs_repr: str
    costs_hash: str
    train_start: datetime
    train_end: datetime
    eval_start: datetime
    eval_end: datetime
    train_candles: int
    eval_candles: int
    warmup_candles: int

    # ---- trade counts ----
    trades: int
    end_of_data_count: int
    boundary_affected_count: int
    exit_counts: dict[str, int] = field(default_factory=dict)

    # ---- profitability observations ----
    win_rate: float | None = None
    profit_factor: float | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    average_pnl: float | None = None
    median_pnl: float | None = None
    max_drawdown: float | None = None
    ending_balance: float | None = None

    # ---- cost observations ----
    fee_total: float | None = None
    spread_total: float | None = None
    slippage_total: float | None = None
    total_friction: float | None = None

    # ---- holding behaviour ----
    bars_held_mean: float | None = None
    bars_held_median: float | None = None

    # ---- timing ----
    first_entry: datetime | None = None
    last_exit: datetime | None = None

    # ---- provenance ----
    warmup_rule: str = WARMUP_RULE
    boundary_policy: str = BOUNDARY_POLICY
    selection_disclosure: str = ""

    #: SHA-256 of the dataset the record was produced from. Required by
    #: PLAN.md section 13 on every window record. Populated from the single
    #: authoritative constant :data:`DATASET_SHA256`; deliberately defaults to
    #: an empty string so that a missing value is detectable rather than
    #: silently defaulted to something plausible.
    dataset_sha256: str = ""

    def as_row(self) -> dict[str, object]:
        """Return a flat dictionary suitable for a CSV row."""

        row = asdict(self)
        row["exit_counts"] = ";".join(
            f"{key}={value}" for key, value in sorted(self.exit_counts.items())
        )
        row.pop("config_repr", None)
        row.pop("costs_repr", None)
        return row


def _safe_profit_factor(value: float | int) -> float | None:
    """Normalise a non-finite profit factor to ``None``.

    ``performance`` returns ``inf`` when a window has no losing trade. That is
    a real observation but is not serialisable, so it is reported as ``None``
    and the raw trade counts remain available for interpretation.
    """

    if value is None:
        return None

    number = float(value)

    if math.isinf(number) or math.isnan(number):
        return None

    return number


def window_stats(run: WindowRun) -> WindowStats:
    """Compute the frozen descriptive metrics for one completed window."""

    resolved: ResolvedWindow = run.resolved
    trades = run.result.trades
    report = performance(trades, run.result.starting_balance)
    costs = cost_breakdown(trades)

    closed = [trade for trade in trades if trade.net_pnl is not None]

    end_of_data = [
        trade
        for trade in closed
        if trade.exit_reason == END_OF_DATA
    ]

    # Every boundary-affected trade is an end_of_data force-close. The two
    # counts are reported separately for clarity but must agree, because the
    # boundary policy retains rather than discards them.
    boundary_affected = len(end_of_data)

    held = [trade.bars_held for trade in closed if trade.bars_held > 0]

    return WindowStats(
        window_id=resolved.window_id,
        config_name=run.config_name,
        config_repr=run.config_repr,
        config_hash=run.config_hash,
        costs_repr=run.costs_repr,
        costs_hash=run.costs_hash,
        train_start=resolved.spec.train_start,
        train_end=resolved.spec.train_end,
        eval_start=resolved.spec.eval_start,
        eval_end=resolved.spec.eval_end,
        train_candles=resolved.train_candles,
        eval_candles=resolved.eval_candles,
        warmup_candles=resolved.warmup_candles,
        trades=report["trades"],
        end_of_data_count=boundary_affected,
        boundary_affected_count=boundary_affected,
        exit_counts=dict(sorted(run.result.exit_counts.items())),
        win_rate=report["win_rate"],
        profit_factor=_safe_profit_factor(report["profit_factor"]),
        gross_pnl=sum(trade.pnl or 0.0 for trade in closed),
        net_pnl=report["net_pnl"],
        average_pnl=report["average_pnl"],
        median_pnl=median_pnl(trades),
        max_drawdown=report["max_drawdown"],
        ending_balance=report["ending_balance"],
        fee_total=costs["fee_total"],
        spread_total=costs["spread_total"],
        slippage_total=costs["slippage_total"],
        total_friction=costs["total_friction"],
        bars_held_mean=fmean(held) if held else None,
        bars_held_median=median(held) if held else None,
        first_entry=min((t.entry_time for t in closed), default=None),
        last_exit=max((t.exit_time for t in closed), default=None),
        selection_disclosure=config_disclosure(run.config_name),
        dataset_sha256=DATASET_SHA256,
    )


def window_stats_for(
    runs: Sequence[WindowRun],
) -> tuple[WindowStats, ...]:
    """Compute :func:`window_stats` for every run, in window order.

    Raises ``ValueError`` if any produced record is missing its dataset
    fingerprint, so the provenance field required by PLAN.md section 13 cannot
    silently disappear from a future result set.
    """

    rows = tuple(window_stats(run) for run in runs)

    for row in rows:
        if not row.dataset_sha256:
            raise ValueError(
                f"window {row.window_id} ({row.config_name}) is missing "
                f"dataset_sha256; PLAN.md section 13 requires it on every "
                f"window record"
            )

    return rows


def sign_counts(rows: Sequence[WindowStats]) -> dict[str, int]:
    """Count positive, negative and zero windows by net P&L.

    Reported as counts so a poor window can never be hidden inside a mean.
    """

    positive = negative = zero = 0

    for row in rows:
        value = row.net_pnl or 0.0

        if value > 0:
            positive += 1
        elif value < 0:
            negative += 1
        else:
            zero += 1

    return {
        "positive": positive,
        "negative": negative,
        "zero": zero,
        "total": len(rows),
    }


def distribution(rows: Sequence[WindowStats], field_name: str = "net_pnl") -> dict:
    """Return the full sorted distribution of a per-window metric.

    With six windows the sorted list *is* the distribution; a mean alone would
    be misleading, so this deliberately returns every value.
    """

    values = [
        getattr(row, field_name)
        for row in rows
        if getattr(row, field_name) is not None
    ]

    if not values:
        return {"count": 0, "sorted": [], "minimum": None, "maximum": None,
                "median": None, "mean": None}

    return {
        "count": len(values),
        "sorted": sorted(values),
        "minimum": min(values),
        "maximum": max(values),
        "median": median(values),
        "mean": fmean(values),
    }


def same_sign_runs(rows: Sequence[WindowStats]) -> dict:
    """Return the longest run of consecutive same-sign windows.

    A measure of consistency across sequential windows. Descriptive only.
    """

    if not rows:
        return {"longest": 0, "runs": []}

    runs: list[dict] = []
    current_sign = 0
    current_length = 0

    for row in rows:
        value = row.net_pnl or 0.0
        sign = 1 if value > 0 else (-1 if value < 0 else 0)

        if sign == current_sign:
            current_length += 1
        else:
            if current_length:
                runs.append({"sign": current_sign, "length": current_length})

            current_sign = sign
            current_length = 1

    if current_length:
        runs.append({"sign": current_sign, "length": current_length})

    longest = max((entry["length"] for entry in runs), default=0)

    return {"longest": longest, "runs": runs}


__all__ = [
    "END_OF_DATA",
    "WindowStats",
    "distribution",
    "same_sign_runs",
    "sign_counts",
    "window_stats",
    "window_stats_for",
]