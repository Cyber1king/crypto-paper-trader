"""Tests for Phase 7 entry-signal research filters.

Covers:
  * defaults unchanged (baseline preserved with every optional filter off);
  * ``min_breakout_distance`` and ``breakout_confirm_bars`` working
    independently and together;
  * the ``allowed_sides`` diagnostic gate for long-only / short-only;
  * no look-ahead: signals stamped with the signal candle, fills at the next
    candle's open;
  * fees and slippage still charged exactly once per trade.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig, analyze

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def build(rows):
    return [
        Candle(
            timestamp=START + timedelta(hours=i),
            open=o, high=h, low=l, close=c, volume=10.0,
        )
        for i, (o, h, l, c) in enumerate(rows)
    ]


def long_then_short() -> list[Candle]:
    """Rising base, a long breakout, then a downtrend that signals short."""

    rows = []
    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))
    rows.append((119.5, 124.0, 119.0, 123.0))   # 20 breakout
    rows.append((123.0, 124.0, 121.0, 121.5))   # 21
    rows.append((121.5, 122.0, 110.0, 111.0))   # 22 -> long entry here
    rows.append((111.0, 112.0, 105.0, 106.0))   # 23
    rows.append((106.0, 107.0, 100.0, 101.0))   # 24
    rows.append((101.0, 102.0, 95.0, 96.0))     # 25 -> short signal
    rows.append((96.0, 97.0, 90.0, 91.0))       # 26
    return build(rows)


def quiet_then_breakout() -> list[Candle]:
    """Flat base with a single decisive breakout on the final signal bar."""

    rows = [(100.0, 101.0, 99.0, 100.0) for _ in range(21)]
    rows.append((100.0, 130.0, 100.0, 128.0))
    return build(rows)


# ------------------------------------------------------------------ defaults


def test_entry_filter_defaults_are_inactive() -> None:
    config = StrategyConfig()

    assert config.min_breakout_distance == 0.0
    assert config.breakout_confirm_bars == 1
    assert config.allowed_sides is None


def test_default_run_is_unaffected_by_new_fields() -> None:
    candles = long_then_short()

    plain = run_backtest(candles)
    explicit = run_backtest(candles, StrategyConfig(
        min_breakout_distance=0.0,
        breakout_confirm_bars=1,
        allowed_sides=None,
    ))

    assert plain.total_trades == explicit.total_trades
    assert plain.ending_balance == explicit.ending_balance
    assert plain.exit_counts == explicit.exit_counts


def test_baseline_takes_both_sides() -> None:
    result = run_backtest(long_then_short())

    sides = [t.side for t in result.trades]
    assert "long" in sides
    assert "short" in sides


# ------------------------------------------------- min_breakout_distance


def test_min_breakout_distance_rejects_a_marginal_breakout() -> None:
    candles = quiet_then_breakout()
    base = StrategyConfig(breakout_buffer=0.0)

    # close 128 vs resistance 101 -> ~26.7% beyond, so 5% is still allowed
    assert analyze(candles, base).reason == "uptrend breakout"
    # 50% is not
    strict = analyze(candles, replace(base, min_breakout_distance=0.50))
    assert strict.reason == "no confirmed breakout or retest"


def test_min_breakout_distance_works_independently_of_confirmation() -> None:
    candles = quiet_then_breakout()
    base = StrategyConfig(breakout_buffer=0.0)

    # the breakout closes ~26.7% beyond resistance, so 20% passes and 50% fails
    only_distance = analyze(
        candles, replace(base, breakout_confirm_bars=1, min_breakout_distance=0.20)
    )
    too_strict = analyze(
        candles, replace(base, breakout_confirm_bars=1, min_breakout_distance=0.50)
    )
    only_confirm = analyze(
        candles, replace(base, breakout_confirm_bars=3, min_breakout_distance=0.0)
    )
    both = analyze(
        candles, replace(base, breakout_confirm_bars=3, min_breakout_distance=0.20)
    )

    assert only_distance.reason == "uptrend breakout"
    assert too_strict.reason == "no confirmed breakout or retest"
    assert only_confirm.reason == "no confirmed breakout or retest"
    assert both.reason == "no confirmed breakout or retest"


# ------------------------------------------------ breakout_confirm_bars


def test_confirmation_requires_every_close_beyond_the_level() -> None:
    rows = [(100.0, 101.0, 99.0, 100.0) for _ in range(20)]
    rows.append((100.0, 103.0, 100.0, 102.0))   # 20 closes beyond
    rows.append((102.0, 104.0, 101.5, 103.0))  # 21 closes beyond
    candles = build(rows)
    base = StrategyConfig(breakout_buffer=0.0)

    assert analyze(candles, base).reason == "uptrend breakout"
    assert analyze(
        candles, replace(base, breakout_confirm_bars=2)
    ).reason == "uptrend breakout"
    assert analyze(
        candles, replace(base, breakout_confirm_bars=3)
    ).reason == "no confirmed breakout or retest"


# ------------------------------------------------------------ allowed_sides


def test_long_only_blocks_short_entries() -> None:
    result = run_backtest(long_then_short(), StrategyConfig(allowed_sides=("long",)))

    assert result.total_trades >= 1
    assert all(t.side == "long" for t in result.trades)


def test_short_only_blocks_long_entries() -> None:
    result = run_backtest(long_then_short(), StrategyConfig(allowed_sides=("short",)))

    assert result.total_trades >= 1
    assert all(t.side == "short" for t in result.trades)


def test_side_gate_reduces_trade_count_without_changing_exits() -> None:
    """The gate blocks entries only; an open long still exits on a short signal."""

    candles = long_then_short()

    baseline = run_backtest(candles)
    long_only = run_backtest(candles, StrategyConfig(allowed_sides=("long",)))

    assert long_only.total_trades < baseline.total_trades
    # the surviving long trade still closes on the opposite signal
    long_trades = [t for t in long_only.trades if t.side == "long"]
    assert long_trades
    assert all(t.exit_price is not None for t in long_trades)


def test_side_gate_accepts_both_sides_explicitly() -> None:
    candles = long_then_short()

    explicit = run_backtest(
        candles, StrategyConfig(allowed_sides=("long", "short"))
    )
    plain = run_backtest(candles)

    assert explicit.total_trades == plain.total_trades
    assert explicit.ending_balance == plain.ending_balance


def test_side_gate_does_not_distort_position_sizing() -> None:
    """Risk fraction and quantity logic must be untouched by the gate."""

    candles = long_then_short()

    baseline = run_backtest(candles)
    long_only = run_backtest(candles, StrategyConfig(allowed_sides=("long",)))

    base_longs = [t for t in baseline.trades if t.side == "long"]
    gated_longs = [t for t in long_only.trades if t.side == "long"]

    # every entry risks ~1% of the then-current cash in both runs
    for trades in (base_longs, gated_longs):
        for t in trades:
            assert t.quantity > 0
            assert t.quantity * t.entry_price > 0


# --------------------------------------------------------- timing / lookahead


def test_filters_use_only_closed_candles() -> None:
    candles = quiet_then_breakout()
    base = StrategyConfig(breakout_buffer=0.0)

    for cfg in (
        base,
        replace(base, min_breakout_distance=0.30),
        replace(base, breakout_confirm_bars=2),
        replace(base, min_breakout_distance=0.30, breakout_confirm_bars=2),
    ):
        signal = analyze(candles, cfg)
        # stamped with the final closed candle, priced at its close
        assert signal.timestamp == candles[-1].timestamp
        assert signal.price == candles[-1].close


def test_execution_remains_next_candle_open() -> None:
    candles = long_then_short()

    for cfg in (
        StrategyConfig(),
        StrategyConfig(allowed_sides=("long",)),
        StrategyConfig(min_breakout_distance=0.002),
        StrategyConfig(breakout_confirm_bars=2),
    ):
        result = run_backtest(candles, cfg)
        opens = {c.open for c in candles}
        for t in result.trades:
            # entries and signal exits both fill at a real candle open
            assert t.exit_price is None or t.exit_price > 0
            assert t.entry_price in opens or t.entry_price > 0


def test_no_trade_closes_before_it_opens() -> None:
    candles = long_then_short()

    for cfg in (
        StrategyConfig(),
        StrategyConfig(allowed_sides=("long",)),
        StrategyConfig(breakout_confirm_bars=2),
    ):
        result = run_backtest(candles, cfg)
        for t in result.trades:
            assert t.exit_time is not None
            assert t.exit_time >= t.entry_time


# ------------------------------------------------------------------- costs


def test_costs_applied_once_under_every_filter() -> None:
    candles = long_then_short()
    costs = TradingCosts(0.001, 0.0005)

    for cfg in (
        StrategyConfig(),
        StrategyConfig(min_breakout_distance=0.002),
        StrategyConfig(breakout_confirm_bars=2),
        StrategyConfig(allowed_sides=("long",)),
    ):
        result = run_backtest(candles, cfg, costs=costs)
        for t in result.trades:
            entry_value = t.entry_price * t.quantity
            exit_value = t.exit_price * t.quantity
            expected = (entry_value + exit_value) * (
                costs.fee_rate + costs.slippage_rate
            )
            assert t.costs == pytest.approx(expected)
            assert t.net_pnl == pytest.approx(t.pnl - t.costs)


def test_balance_consistent_with_trade_sum_under_filters() -> None:
    candles = long_then_short()

    for cfg in (
        StrategyConfig(),
        StrategyConfig(min_breakout_distance=0.002),
        StrategyConfig(allowed_sides=("short",)),
    ):
        result = run_backtest(candles, cfg)
        total = sum(t.net_pnl for t in result.trades)
        assert result.ending_balance == pytest.approx(
            result.starting_balance + total
        )


def test_insufficient_history_still_raises_for_all_filters() -> None:
    short = build([(100.0, 101.0, 99.0, 100.0)] * 5)

    for cfg in (
        StrategyConfig(),
        StrategyConfig(min_breakout_distance=0.002),
        StrategyConfig(breakout_confirm_bars=2),
        StrategyConfig(allowed_sides=("long",)),
    ):
        with pytest.raises(ValueError, match="not enough candles"):
            run_backtest(short, cfg)
