"""Robustness and uncertainty analysis for completed paper backtests.

Added in Phase 11. This module is **read-only with respect to strategy
behaviour**: it consumes finished backtest results and never changes
signals, sizing, execution, or costs.

Three capabilities, all deliberately separate from the existing engine
statistics so that reported figures stay backward compatible:

``mark_to_market_drawdown``
    Maximum drawdown of an equity curve valued at every candle close while a
    position is open, in addition to the existing closed-trade-only measure.

``block_bootstrap``
    Moving-block resampling of the trade P&L sequence. Trades are sequential
    and may share market conditions, so an i.i.d. bootstrap can understate
    uncertainty *when dependence is present*.

    Phase 11 measured that dependence on the 2026 out-of-sample sample and
    found none of consequence: lag-1..3 autocorrelation sat inside the
    white-noise band for both configurations, and block intervals came out
    slightly **narrower** than i.i.d., not wider. The method is therefore
    reported as a robustness cross-check, not as a correction that inflates
    the interval. See ``experiments/phase11/dependence_analysis.py``.

``trade_concentration``
    How much of the net result is contributed by the largest winners and
    losers, plus simple outcome-distribution descriptors.

Nothing here estimates future performance. All intervals describe the
uncertainty of the historical sample only.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .models import Candle, PaperTrade
from .stats import total_friction

__all__ = [
    "DrawdownResult",
    "equity_curve_mark_to_market",
    "mark_to_market_drawdown",
    "bootstrap_ci",
    "block_bootstrap_ci",
    "concentration_stats",
    "monthly_breakdown",
]


# --------------------------------------------------------------- drawdown


@dataclass(frozen=True)
class DrawdownResult:
    """Maximum drawdown measured two different ways."""

    closed_trade_max_dd: float
    mark_to_market_max_dd: float
    mark_to_market_max_dd_abs: float
    peak_equity: float
    trough_equity: float
    worst_trough_time: datetime | None
    samples: int
    closed_trade_samples: int


def equity_curve_mark_to_market(
    trades: Sequence[PaperTrade],
    candles: Sequence[Candle],
    starting_balance: float,
) -> list[tuple[datetime, float]]:
    """Equity valued at every candle close, including unrealised P&L.

    Conventions, chosen to match the existing engine as closely as the
    available data allows:

    * A trade's unrealised P&L is **gross** (before fees and slippage),
      because the engine recognises all costs at closure. Valuing net P&L
      intrabar would mix two conventions. The consequence is that the
      mark-to-market curve is slightly optimistic relative to the realised
      figure by roughly the entry-side cost while a trade is open.
    * Equity is sampled at each candle **close**. Intrabar highs and lows are
      deliberately not used, because no intrabar execution data exists and
      inventing it would overstate the drawdown.
    * Cash is credited only when a trade closes, exactly as the engine does.
    * A trade still open on the final candle is valued at that candle's
      close, which equals the price the engine uses to force-close it.
    * Flat stretches between trades carry the last realised equity forward.

    Returns a list of ``(timestamp, equity)`` ordered by time.
    """

    if not trades:
        return []

    index_of: dict[datetime, int] = {c.timestamp: i for i, c in enumerate(candles)}
    ordered = sorted(trades, key=lambda t: t.entry_time)

    curve: list[tuple[datetime, float]] = []
    equity = starting_balance
    cursor = 0

    for trade in ordered:
        entry_i = index_of.get(trade.entry_time)
        exit_i = index_of.get(trade.exit_time) if trade.exit_time else None
        if entry_i is None:
            # entry bar absent from the candle set; skip defensively
            continue
        if exit_i is None:
            exit_i = len(candles) - 1

        # flat period before this trade. The cursor is deliberately NOT reset
        # to entry_i here: the engine can close one trade and open the next on
        # the same bar, in which case entry_i < cursor and rewinding would
        # re-emit that already-covered candle.
        for i in range(cursor, entry_i):
            curve.append((candles[i].timestamp, equity))

        direction = 1.0 if trade.side == "long" else -1.0

        # One sample per candle. The engine can close a trade and open a new
        # one on the same bar (both fill at that bar's open), so the start is
        # clamped to ``cursor``. When that happens the shared bar is valued at
        # the closing trade's exit price, which equals the open, and the new
        # position's first mark appears on the following bar.
        start = max(entry_i, cursor)
        for i in range(start, exit_i + 1):
            mark = (
                trade.exit_price
                if i == exit_i and trade.exit_price is not None
                else candles[i].close
            )
            unrealised = (mark - trade.entry_price) * trade.quantity * direction
            curve.append((candles[i].timestamp, equity + unrealised))
        cursor = max(cursor, exit_i + 1)

        equity += trade.net_pnl or 0.0

    # flat period after the last trade
    for i in range(cursor, len(candles)):
        curve.append((candles[i].timestamp, equity))

    return curve


def _max_drawdown(values: Sequence[float]) -> tuple[float, float, float, int]:
    """Return (max_drawdown_fraction, peak, trough, trough_index)."""

    peak = values[0] if values else 0.0
    best = 0.0
    peak_v = peak
    trough_v = peak
    trough_i = 0
    for i, value in enumerate(values):
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > best:
                best = dd
                peak_v = peak
                trough_v = value
                trough_i = i
    return best, peak_v, trough_v, trough_i


def mark_to_market_drawdown(
    trades: Sequence[PaperTrade],
    candles: Sequence[Candle],
    starting_balance: float,
) -> DrawdownResult:
    """Compare closed-trade drawdown with candle-close mark-to-market drawdown."""

    closed_nets = [t.net_pnl or 0.0 for t in trades if t.net_pnl is not None]

    equity = starting_balance
    closed_curve = [starting_balance]
    for pnl in closed_nets:
        equity += pnl
        closed_curve.append(equity)
    closed_dd, _, _, _ = _max_drawdown(closed_curve)

    curve = equity_curve_mark_to_market(trades, candles, starting_balance)
    values = [value for _, value in curve]
    if values:
        mtm_dd, peak_v, trough_v, trough_i = _max_drawdown(values)
        worst_time = curve[trough_i][0]
    else:
        mtm_dd, peak_v, trough_v, worst_time = 0.0, starting_balance, starting_balance, None

    return DrawdownResult(
        closed_trade_max_dd=closed_dd,
        mark_to_market_max_dd=mtm_dd,
        mark_to_market_max_dd_abs=peak_v - trough_v,
        peak_equity=peak_v,
        trough_equity=trough_v,
        worst_trough_time=worst_time,
        samples=len(values),
        closed_trade_samples=len(closed_curve) - 1,
    )


# ----------------------------------------------------------------- resample


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_values[int(pos)]
    frac = pos - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


def _resample_mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else float("nan")


def bootstrap_ci(
    values: Sequence[float],
    statistic=_resample_mean,
    n_resamples: int = 10_000,
    seed: int = 20260101,
    alpha: float = 0.05,
) -> dict:
    """I.i.d. percentile bootstrap. Kept for comparison with the block method."""

    values = list(values)
    n = len(values)
    if n == 0:
        return {
            "n": 0, "point": float("nan"), "ci_low": float("nan"),
            "ci_high": float("nan"), "n_resamples": 0, "seed": seed,
            "block_length": 1, "method": "iid", "alpha": alpha,
        }

    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(sample))
    stats.sort()

    return {
        "n": n,
        "point": statistic(values),
        "ci_low": _percentile(stats, alpha / 2),
        "ci_high": _percentile(stats, 1 - alpha / 2),
        "n_resamples": n_resamples,
        "seed": seed,
        "block_length": 1,
        "method": "iid",
        "alpha": alpha,
    }


def block_bootstrap_ci(
    values: Sequence[float],
    block_length: int = 10,
    statistic=_resample_mean,
    n_resamples: int = 10_000,
    seed: int = 20260101,
    alpha: float = 0.05,
) -> dict:
    """Moving-block percentile bootstrap over the ordered trade sequence.

    Resampling unit: **one block of ``block_length`` consecutive trades**.
    Blocks are drawn with replacement from all overlapping starting
    positions, then concatenated and truncated to the original length. This
    is the moving-block bootstrap; it preserves short-range dependence
    between neighbouring trades, which an i.i.d. resample destroys.

    Why blocks exist at all: the strategy holds at most one position at a
    time, so consecutive trades are not guaranteed independent draws - they
    can share a prevailing market state and volatility regime. A block
    resample preserves short-range dependence rather than assuming it away,
    so it remains defensible when dependence cannot be ruled out.

    Measured behaviour on this project's 2026 sample: autocorrelation at
    lags 1-3 was inside the white-noise band, and the block interval was
    slightly **narrower** than the i.i.d. interval, because averaging over
    blocks of weakly related observations reduces the resampled spread. So
    blocks are *not* claimed to widen intervals here, and no such claim
    should be read into the returned numbers. Both methods contain zero.

    Block length is a user choice, not a fitted parameter. A default of 10
    is used, and callers should inspect sensitivity across several lengths
    rather than trust one number.

    Reproducibility: all randomness comes from ``random.Random(seed)``, so a
    given ``(values, block_length, n_resamples, seed)`` always yields the
    same interval.
    """

    values = list(values)
    n = len(values)
    if n == 0:
        return {
            "n": 0, "point": float("nan"), "ci_low": float("nan"),
            "ci_high": float("nan"), "n_resamples": 0, "seed": seed,
            "block_length": block_length, "method": "moving_block",
            "alpha": alpha,
        }
    if block_length <= 0:
        raise ValueError("block_length must be positive")
    if block_length > n:
        block_length = n

    rng = random.Random(seed)
    n_blocks = math.ceil(n / block_length)
    max_start = n - block_length

    stats: list[float] = []
    for _ in range(n_resamples):
        sample: list[float] = []
        for _ in range(n_blocks):
            start = rng.randint(0, max_start)
            sample.extend(values[start:start + block_length])
        stats.append(statistic(sample[:n]))
    stats.sort()

    return {
        "n": n,
        "point": statistic(values),
        "ci_low": _percentile(stats, alpha / 2),
        "ci_high": _percentile(stats, 1 - alpha / 2),
        "n_resamples": n_resamples,
        "seed": seed,
        "block_length": block_length,
        "method": "moving_block",
        "alpha": alpha,
    }


def total_pnl_bootstrap_ci(
    values: Sequence[float],
    block_length: int = 10,
    n_resamples: int = 10_000,
    seed: int = 20260101,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap CI for the *total* P&L of the observed trade sequence.

    The sum is not rescaled to the observed sample size; it is resampled as
    a fixed-length sequence, so the interval describes the uncertainty of
    this particular set of trades, not of a larger or smaller future set.
    """

    def total(sample):
        return sum(sample) if sample else float("nan")

    result = block_bootstrap_ci(
        values,
        block_length=block_length,
        statistic=total,
        n_resamples=n_resamples,
        seed=seed,
        alpha=alpha,
    )
    result["statistic"] = "sum"
    return result


# ------------------------------------------------------------ concentration


def concentration_stats(values: Sequence[float]) -> dict:
    """Descriptive concentration measures for a trade P&L sequence."""

    values = [float(v) for v in values]
    n = len(values)
    if n == 0:
        return {
            "n": 0, "net": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
            "largest_win": 0.0, "largest_loss": 0.0,
            "top1_win_share_of_net": None, "top3_win_share_of_net": None,
            "top5_win_share_of_net": None,
            "bottom1_share_of_net": None, "bottom5_share_of_net": None,
            "wins_without_top1_net": None,
            "losses_without_top1_net": None,
            "median": 0.0, "mean": 0.0, "stdev": 0.0,
        }

    wins = sorted((v for v in values if v > 0), reverse=True)
    losses = sorted((v for v in values if v < 0))
    net = sum(values)

    def share(amount):
        return (amount / net) if net not in (0,) else None

    return {
        "n": n,
        "net": net,
        "gross_profit": sum(wins),
        "gross_loss": abs(sum(losses)),
        "largest_win": wins[0] if wins else 0.0,
        "largest_loss": losses[0] if losses else 0.0,
        "top1_win_share_of_net": share(wins[0]) if wins else None,
        "top3_win_share_of_net": share(sum(wins[:3])) if len(wins) >= 3 else None,
        "top5_win_share_of_net": share(sum(wins[:5])) if len(wins) >= 5 else None,
        "bottom1_share_of_net": share(losses[0]) if losses else None,
        "bottom5_share_of_net": share(sum(losses[:5])) if len(losses) >= 5 else None,
        "wins_without_top1_net": sum(wins[1:]) if len(wins) > 1 else 0.0,
        "losses_without_top1_net": abs(sum(losses[1:])) if len(losses) > 1 else 0.0,
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if n > 1 else 0.0,
    }


# ------------------------------------------------------------------ monthly


def monthly_breakdown(
    trades: Sequence[PaperTrade],
    starting_balance: float,
) -> list[dict]:
    """Per-month aggregation of closed trades.

    A trade is assigned to the month of its **entry** timestamp, so each
    trade contributes to exactly one month and nothing is double counted.

    ``return_pct`` uses the fixed ``starting_balance`` as the denominator
    rather than a month-opening balance. That keeps months comparable to each
    other and to the headline return, and it avoids implying compounding
    that did not occur, since compounding requires chaining month-opening
    balances that a per-trade ledger does not define.
    """

    buckets: dict[str, list[PaperTrade]] = defaultdict(list)
    for trade in trades:
        buckets[trade.entry_time.strftime("%Y-%m")].append(trade)

    rows: list[dict] = []
    for month in sorted(buckets):
        group = buckets[month]
        nets = [t.net_pnl or 0.0 for t in group]
        gross = [t.pnl or 0.0 for t in group]
        costs = total_friction(group)
        rows.append({
            "month": month,
            "trades": len(group),
            "net_pnl": sum(nets),
            "gross_pnl": sum(gross),
            "costs": costs,
            "return_pct": sum(nets) / starting_balance * 100.0,
            "wins": sum(1 for v in nets if v > 0),
            "losses": sum(1 for v in nets if v < 0),
            "sign": "positive" if sum(nets) > 0 else "negative",
        })
    return rows


def monthly_summary(rows: Sequence[dict], starting_balance: float) -> dict:
    if not rows:
        return {
            "months_with_trades": 0, "positive_months": 0,
            "negative_months": 0, "flat_months": 0, "min_month": None,
            "min_month_net": None, "max_month": None, "max_month_net": None,
            "range_pct": None, "total_trades": 0,
            "mean_monthly_return_pct": None,
        }

    nets = [r["net_pnl"] for r in rows]
    positive = sum(1 for v in nets if v > 0)
    negative = sum(1 for v in nets if v < 0)
    lo = min(rows, key=lambda r: r["net_pnl"])
    hi = max(rows, key=lambda r: r["net_pnl"])

    return {
        "months_with_trades": len(rows),
        "positive_months": positive,
        "negative_months": negative,
        "flat_months": sum(1 for v in nets if v == 0),
        "min_month": lo["month"],
        "min_month_net": lo["net_pnl"],
        "max_month": hi["month"],
        "max_month_net": hi["net_pnl"],
        "range_pct": (
            (hi["net_pnl"] - lo["net_pnl"]) / starting_balance * 100.0
            if starting_balance else None
        ),
        "total_trades": sum(r["trades"] for r in rows),
        "mean_monthly_return_pct": statistics.fmean(
            r["return_pct"] for r in rows
        ),
    }
