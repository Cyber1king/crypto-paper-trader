"""Tests for the Phase 11 robustness module.

Covers reproducibility, small samples, empty inputs, monthly aggregation and
return denominators, trade concentration, drawdown (both definitions), and
preservation of the frozen Phase 10 configurations.

All fixtures are synthetic. No market data is required.
"""

from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Candle, PaperTrade
from crypto_paper_lab.robustness import (
    block_bootstrap_ci,
    bootstrap_ci,
    concentration_stats,
    equity_curve_mark_to_market,
    mark_to_market_drawdown,
    monthly_breakdown,
    monthly_summary,
    total_pnl_bootstrap_ci,
)
from crypto_paper_lab.stats import performance
from crypto_paper_lab.strategy import StrategyConfig

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_trade(side, entry_i, exit_i, entry=100.0, exit=110.0, qty=1.0,
               net=None, reason="test"):
    """Build a PaperTrade. ``net`` is realised by choosing ``costs``.

    ``PaperTrade.net_pnl`` is a derived property (``pnl - costs``), not a
    constructor field, so an arbitrary net result is expressed via costs.
    """

    entry_time = START + timedelta(hours=entry_i)
    exit_time = START + timedelta(hours=exit_i)
    gross = (exit - entry) * qty * (1 if side == "long" else -1)
    costs = 1.0 if net is None else gross - net
    return PaperTrade(
        side=side,
        entry_time=entry_time,
        entry_price=entry,
        quantity=qty,
        exit_time=exit_time,
        exit_price=exit,
        reason=reason,
        costs=costs,
    )


def make_candles(n, prices=None):
    rows = []
    for i in range(n):
        if prices is not None:
            p = prices[i]
            rows.append((p, p + 1, p - 1, p))
        else:
            rows.append((100.0, 101.0, 99.0, 100.0))
    return [
        Candle(timestamp=START + timedelta(hours=i), open=o, high=h,
               low=l, close=c, volume=10.0)
        for i, (o, h, l, c) in enumerate(rows)
    ]


# ------------------------------------------------------ bootstrap basics


def test_bootstrap_is_deterministic_for_a_fixed_seed() -> None:
    values = [1.0, -0.5, 2.0, 0.3, -1.2, 0.8, 1.5, -0.7]

    a = block_bootstrap_ci(values, block_length=3, n_resamples=500, seed=42)
    b = block_bootstrap_ci(values, block_length=3, n_resamples=500, seed=42)

    assert a == b


def test_iid_bootstrap_is_deterministic_for_a_fixed_seed() -> None:
    values = [0.5, -1.0, 1.5, 0.2, -0.8, 1.1]

    a = bootstrap_ci(values, n_resamples=500, seed=7)
    b = bootstrap_ci(values, n_resamples=500, seed=7)

    assert a == b


def test_different_seeds_can_differ() -> None:
    values = [1.0, -0.5, 2.0, 0.3, -1.2, 0.8, 1.5, -0.7, 0.4, -0.6] * 3

    a = block_bootstrap_ci(values, block_length=3, n_resamples=500, seed=1)
    b = block_bootstrap_ci(values, block_length=3, n_resamples=500, seed=2)

    assert a["ci_low"] != b["ci_low"] or a["ci_high"] != b["ci_high"]


def test_bootstrap_empty_input_is_safe() -> None:
    for result in (bootstrap_ci([]), block_bootstrap_ci([])):
        assert result["n"] == 0
        assert result["ci_low"] != result["ci_low"]      # NaN
        assert result["ci_high"] != result["ci_high"]


def test_block_bootstrap_handles_single_value() -> None:
    result = block_bootstrap_ci([2.5], block_length=10, n_resamples=100,
                                seed=1)
    assert result["n"] == 1
    assert result["point"] == 2.5
    assert result["ci_low"] == 2.5
    assert result["ci_high"] == 2.5


def test_block_length_larger_than_sample_is_clamped() -> None:
    values = [1.0, 2.0, 3.0]
    result = block_bootstrap_ci(values, block_length=99, n_resamples=100,
                                seed=1)
    assert result["block_length"] == 3
    assert result["n"] == 3


def test_block_length_must_be_positive() -> None:
    with pytest.raises(ValueError, match="block_length"):
        block_bootstrap_ci([1.0, 2.0], block_length=0)


def test_small_sample_interval_contains_point_estimate() -> None:
    values = [1.0, -1.0]
    result = block_bootstrap_ci(values, block_length=2, n_resamples=200,
                                seed=3)
    assert result["ci_low"] <= result["point"] <= result["ci_high"]


def test_zero_mean_sample_yields_interval_spanning_zero() -> None:
    values = [1.0, -1.0] * 15
    result = block_bootstrap_ci(values, block_length=5, n_resamples=500,
                                seed=11)
    assert result["ci_low"] <= 0 <= result["ci_high"]


def test_total_pnl_bootstrap_matches_point_estimate() -> None:
    values = [1.0, 2.0, -1.5, 0.5]
    result = total_pnl_bootstrap_ci(values, block_length=2, n_resamples=200,
                                    seed=5)
    assert result["statistic"] == "sum"
    assert result["point"] == pytest.approx(sum(values))


# --------------------------------------------------------- concentration


def test_concentration_empty_input() -> None:
    result = concentration_stats([])
    assert result["n"] == 0
    assert result["net"] == 0.0
    assert result["top1_win_share_of_net"] is None


def test_concentration_single_trade() -> None:
    result = concentration_stats([5.0])
    assert result["n"] == 1
    assert result["largest_win"] == 5.0
    assert result["top1_win_share_of_net"] == pytest.approx(1.0)


def test_concentration_identifies_dominant_trade() -> None:
    values = [50.0, 1.0, 1.0, -1.0, -1.0]
    result = concentration_stats(values)

    assert result["largest_win"] == 50.0
    # the three winners are 50, 1 and 1; removing the top one leaves 2.0 of
    # winning P&L against 2.0 of losing P&L, i.e. essentially nothing
    assert result["wins_without_top1_net"] == pytest.approx(2.0)
    assert result["net"] == pytest.approx(50.0)


def test_concentration_shares_use_net_denominator() -> None:
    values = [10.0, 10.0, -10.0, -5.0]
    result = concentration_stats(values)
    assert result["net"] == pytest.approx(5.0)
    assert result["top1_win_share_of_net"] == pytest.approx(2.0)
    assert result["bottom1_share_of_net"] == pytest.approx(-2.0)


def test_concentration_net_zero_returns_none_shares() -> None:
    result = concentration_stats([5.0, -5.0])
    assert result["net"] == pytest.approx(0.0)
    assert result["top1_win_share_of_net"] is None


# -------------------------------------------------------------- monthly


def test_monthly_breakdown_empty() -> None:
    assert monthly_breakdown([], 10_000.0) == []
    summary = monthly_summary([], 10_000.0)
    assert summary["months_with_trades"] == 0
    assert summary["positive_months"] == 0


def test_monthly_breakdown_assigns_trade_to_entry_month() -> None:
    trades = [
        make_trade("long", 0, 5, net=10.0),      # January
        make_trade("short", 24 * 40, 24 * 41, net=-4.0),   # February
    ]
    rows = monthly_breakdown(trades, 10_000.0)

    assert [r["month"] for r in rows] == ["2026-01", "2026-02"]
    assert rows[0]["net_pnl"] == pytest.approx(10.0)
    assert rows[1]["net_pnl"] == pytest.approx(-4.0)


def test_monthly_return_denominator_is_starting_balance() -> None:
    trades = [make_trade("long", 0, 5, net=100.0)]
    rows = monthly_breakdown(trades, 10_000.0)

    # 100 / 10000 = 1.0%, NOT 100% of some compounding base
    assert rows[0]["return_pct"] == pytest.approx(1.0)


def test_monthly_counts_wins_and_losses() -> None:
    trades = [
        make_trade("long", 0, 1, net=5.0),
        make_trade("long", 2, 3, net=0.0),
        make_trade("short", 4, 5, net=-2.0),
    ]
    rows = monthly_breakdown(trades, 10_000.0)

    assert rows[0]["trades"] == 3
    assert rows[0]["wins"] == 1
    assert rows[0]["losses"] == 1
    assert rows[0]["sign"] == "positive"


def test_monthly_summary_counts_and_range() -> None:
    trades = [
        make_trade("long", 0, 1, net=10.0),
        make_trade("long", 24 * 40, 24 * 41, net=-4.0),
    ]
    rows = monthly_breakdown(trades, 10_000.0)
    summary = monthly_summary(rows, 10_000.0)

    assert summary["months_with_trades"] == 2
    assert summary["positive_months"] == 1
    assert summary["negative_months"] == 1
    assert summary["max_month"] == "2026-01"
    assert summary["min_month"] == "2026-02"
    assert summary["range_pct"] == pytest.approx(0.14)


def test_monthly_trades_are_not_double_counted() -> None:
    trades = [make_trade("long", i, i + 1, net=1.0) for i in range(0, 48)]
    rows = monthly_breakdown(trades, 10_000.0)
    assert sum(r["trades"] for r in rows) == len(trades)


# ------------------------------------------------------------- drawdown


def test_mark_to_market_empty_input() -> None:
    candles = make_candles(10)
    result = mark_to_market_drawdown([], candles, 10_000.0)
    assert result.closed_trade_max_dd == 0.0
    assert result.mark_to_market_max_dd == 0.0


def test_mark_to_market_curve_covers_every_candle() -> None:
    candles = make_candles(50)
    trades = [make_trade("long", 5, 20)]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)

    assert len(curve) == 50
    assert curve[0][0] == candles[0].timestamp
    assert curve[-1][0] == candles[-1].timestamp


def test_mark_to_market_values_open_position_midway() -> None:
    # price rises to 120 while the long is open, so unrealised P&L is +20
    prices = [100.0] * 10 + [120.0] * 10 + [100.0] * 10
    candles = make_candles(30, prices)
    trades = [make_trade("long", 5, 20, entry=100.0, exit=110.0)]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)
    values = dict(curve)

    assert values[START + timedelta(hours=15)] == pytest.approx(10_020.0)


def test_mark_to_market_captures_intratrade_deepening() -> None:
    # price collapses mid-trade then recovers by the exit price:
    # closed-trade drawdown sees nothing, mark-to-market sees the dip
    prices = [100.0] * 10 + [80.0] * 5 + [110.0] * 15
    candles = make_candles(30, prices)
    trades = [make_trade("long", 5, 25, entry=100.0, exit=110.0, net=9.0)]

    closed = mark_to_market_drawdown(trades, candles, 10_000.0)
    # equity only ever updates at closure, so closed-trade dd is ~0
    assert closed.closed_trade_max_dd < 0.01
    # mark to market saw the 80 print: equity fell 10000 -> 9980
    assert closed.mark_to_market_max_dd_abs == pytest.approx(20.0)
    assert closed.mark_to_market_max_dd == pytest.approx(0.002)
    assert closed.mark_to_market_max_dd > closed.closed_trade_max_dd


def test_mark_to_market_handles_short_position() -> None:
    prices = [100.0] * 10 + [90.0] * 10 + [100.0] * 10
    candles = make_candles(30, prices)
    trades = [make_trade("short", 5, 20, entry=100.0, exit=90.0)]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)
    values = dict(curve)

    # short gains when price falls
    assert values[START + timedelta(hours=15)] == pytest.approx(10_010.0)


def test_mark_to_market_handles_final_open_position() -> None:
    """A trade left open on the last candle is valued at that close."""

    prices = [100.0] * 10 + [130.0] * 10
    candles = make_candles(20, prices)
    trade = PaperTrade(
        side="long",
        entry_time=START + timedelta(hours=5),
        entry_price=100.0,
        quantity=1.0,
        reason="test",
    )
    curve = equity_curve_mark_to_market([trade], candles, 10_000.0)
    assert curve[-1][1] == pytest.approx(10_030.0)


def test_existing_closed_trade_drawdown_metric_is_unchanged() -> None:
    """The legacy metric in stats.performance must not move."""

    trades = [make_trade("long", i * 3, i * 3 + 2,
                         entry=100.0, exit=90.0 if i % 2 else 110.0)
              for i in range(6)]
    trades = []
    for i in range(6):
        gain = 110.0 if i % 2 == 0 else 90.0
        trades.append(make_trade("long", i * 3, i * 3 + 2,
                                 entry=100.0, exit=gain))

    legacy = performance(trades, starting_balance=10_000.0)
    result = mark_to_market_drawdown(trades, make_candles(30), 10_000.0)

    assert legacy["max_drawdown"] == pytest.approx(
        result.closed_trade_max_dd
    )


def test_mark_to_market_reports_trough_timestamp() -> None:
    prices = [100.0] * 10 + [80.0] * 5 + [110.0] * 15
    candles = make_candles(30, prices)
    trades = [make_trade("long", 5, 25, entry=100.0, exit=110.0, net=9.0)]
    result = mark_to_market_drawdown(trades, candles, 10_000.0)

    assert result.worst_trough_time is not None
    assert result.mark_to_market_max_dd_abs > 0


def test_mark_to_market_sample_counts_differ_from_closed_samples() -> None:
    candles = make_candles(100)
    trades = [make_trade("long", 10, 40)]
    result = mark_to_market_drawdown(trades, candles, 10_000.0)

    assert result.samples == 100
    assert result.closed_trade_samples == 1


def test_mark_to_market_emits_exactly_one_sample_per_candle() -> None:
    """Regression guard: no candle may be emitted twice or skipped.

    The engine can close one trade and open the next on the same bar, which
    previously caused that candle to be emitted twice.
    """

    candles = make_candles(60)
    trades = [
        make_trade("long", 5, 12, net=1.0),
        make_trade("short", 12, 20, net=-0.5),   # same bar as previous exit
        make_trade("long", 25, 40, net=2.0),
    ]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)

    stamps = [t for t, _ in curve]
    assert len(stamps) == len(candles)
    assert len(set(stamps)) == len(candles)
    assert stamps == [c.timestamp for c in candles]


def test_mark_to_market_curve_is_time_ordered() -> None:
    candles = make_candles(40)
    trades = [make_trade("long", 5, 15), make_trade("long", 20, 30)]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)

    stamps = [t for t, _ in curve]
    assert stamps == sorted(stamps)


def test_mark_to_market_trades_may_be_supplied_out_of_order() -> None:
    candles = make_candles(40)
    trades = [
        make_trade("long", 20, 30),
        make_trade("long", 5, 15),
    ]
    curve = equity_curve_mark_to_market(trades, candles, 10_000.0)

    stamps = [t for t, _ in curve]
    assert stamps == sorted(stamps)
    assert len(stamps) == len(candles)


# --------------------------------------- frozen configuration preservation


def test_baseline_defaults_match_phase11_specification() -> None:
    config = StrategyConfig()

    assert config.lookback == 20
    assert config.fast_period == 5
    assert config.slow_period == 12
    assert config.breakout_buffer == 0.001
    assert config.retest_tolerance == 0.002
    assert config.min_breakout_distance == 0.0
    assert config.trend_strength_min == 0.001
    assert config.retest_use_close is False
    assert config.breakout_confirm_bars == 1
    assert config.max_holding_bars is None
    assert config.stop_loss_pct is None
    assert config.take_profit_pct is None
    assert config.allowed_sides is None


def test_a2_differs_from_baseline_only_in_min_breakout_distance() -> None:
    from dataclasses import replace

    base = StrategyConfig()
    a2 = replace(base, min_breakout_distance=0.002)

    differing = {k for k in vars(a2) if getattr(base, k) != getattr(a2, k)}
    assert differing == {"min_breakout_distance"}
    assert a2.min_breakout_distance == 0.002


def test_phase10_baseline_still_reproduces() -> None:
    from pathlib import Path

    from crypto_paper_lab.data import load_ohlcv_csv

    dataset = Path("data") / "BTCUSDT_1h_Cleaned (1).csv"
    if not dataset.exists():
        pytest.skip("research dataset not present")

    result = run_backtest(load_ohlcv_csv(dataset))

    assert result.total_trades == 344
    assert round(result.ending_balance, 2) == pytest.approx(9842.86, abs=1e-9)


def test_phase10_a2_still_reproduces() -> None:
    from dataclasses import replace
    from pathlib import Path

    from crypto_paper_lab.data import load_ohlcv_csv

    dataset = Path("data") / "BTCUSDT_1h_Cleaned (1).csv"
    if not dataset.exists():
        pytest.skip("research dataset not present")

    config = replace(StrategyConfig(), min_breakout_distance=0.002)
    result = run_backtest(load_ohlcv_csv(dataset), config=config)

    assert result.total_trades == 284
    assert round(result.ending_balance, 2) == pytest.approx(9912.84, abs=1e-9)


def test_robustness_module_does_not_alter_backtest_behaviour() -> None:
    """Running robustness code must not perturb the engine."""

    from pathlib import Path

    from crypto_paper_lab.data import load_ohlcv_csv

    dataset = Path("data") / "BTCUSDT_1h_Cleaned (1).csv"
    if not dataset.exists():
        pytest.skip("research dataset not present")

    candles = load_ohlcv_csv(dataset)
    before = run_backtest(candles)

    mark_to_market_drawdown(before.trades, candles, before.starting_balance)
    concentration_stats([t.net_pnl for t in before.trades])
    monthly_breakdown(before.trades, before.starting_balance)

    after = run_backtest(candles)
    assert after.ending_balance == before.ending_balance
    assert after.total_trades == before.total_trades


def test_zero_cost_configuration_still_available() -> None:
    """The Phase 5 costs override must remain functional."""

    candles = [
        Candle(timestamp=START + timedelta(hours=i), open=100.0 + i,
               high=101.5 + i, low=99.0 + i, close=100.5 + i, volume=10.0)
        for i in range(40)
    ]
    config = StrategyConfig(lookback=5, fast_period=2, slow_period=4,
                            breakout_buffer=0)

    default = run_backtest(candles, config)
    zero = run_backtest(candles, config, costs=TradingCosts(0.0, 0.0))

    assert zero.ending_balance >= default.ending_balance
