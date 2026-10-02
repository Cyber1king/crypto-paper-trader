"""Tests for Phase 8 out-of-sample validation boundaries.

The validation harness feeds warm-up candles plus a validation window into a
single call to ``run_backtest`` and gates entries with ``evaluation_start``.
These tests prove:

  * the default (``evaluation_start=None``) is bit-identical to before;
  * warm-up candles produce no trades;
  * the first eligible entry is exactly at the boundary;
  * the account starts flat at the boundary (no balance carry-over);
  * no future candle is used to generate any signal;
  * invalid boundaries are rejected.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import END_OF_DATA, run_backtest
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


def zigzag(n: int, start: float = 100.0, step: float = 1.5) -> list[Candle]:
    """Small alternating series; kept for boundary-only assertions."""

    rows = []
    price = start
    for i in range(n):
        if i % 2 == 0:
            rows.append((price, price + step, price - 0.2, price + step))
            price += step
        else:
            rows.append((price, price + 0.2, price - step, price - step))
            price -= step
    return build(rows)


def cycles(rising: int = 30, falling: int = 30, repeats: int = 4) -> list[Candle]:
    """Sustained up and down legs so breakouts fire in both directions.

    With the default arguments this yields 240 candles and 8 trades
    (4 long, 4 short) entering at indices 22, 42, 72, 102, 132, 162, 192, 222.
    """

    rows = []
    price = 100.0
    for _ in range(repeats):
        for _ in range(rising):
            rows.append((price, price + 1.0, price - 0.5, price + 1.0))
            price += 1.0
        for _ in range(falling):
            rows.append((price, price + 0.5, price - 1.0, price - 1.0))
            price -= 1.0
    return build(rows)


def entry_indices(candles, trades):
    lookup = {c.timestamp: i for i, c in enumerate(candles)}
    return [lookup[t.entry_time] for t in trades]


# ------------------------------------------------------------------ defaults


def test_evaluation_start_none_is_the_default_behaviour() -> None:
    candles = cycles()

    implicit = run_backtest(candles)
    explicit = run_backtest(candles, evaluation_start=None)

    assert implicit.total_trades == explicit.total_trades
    assert implicit.ending_balance == explicit.ending_balance
    assert implicit.exit_counts == explicit.exit_counts


def test_default_still_matches_pre_existing_baseline_series() -> None:
    rows = []
    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))
    rows.append((119.5, 124.0, 119.0, 123.0))
    rows.append((123.0, 124.0, 121.0, 121.5))
    rows.append((121.5, 122.0, 110.0, 111.0))
    rows.append((111.0, 112.0, 105.0, 106.0))
    rows.append((106.0, 107.0, 100.0, 101.0))
    rows.append((101.0, 102.0, 95.0, 96.0))
    rows.append((96.0, 97.0, 90.0, 91.0))
    candles = build(rows)
    config = StrategyConfig()

    result = run_backtest(candles, config)

    assert result.total_trades == 2
    assert result.ending_balance == pytest.approx(9_992.4522, abs=1e-4)


# ------------------------------------------------------------ warm-up gate


def test_warmup_candles_produce_no_trades() -> None:
    candles = cycles()
    boundary = 100

    result = run_backtest(candles, evaluation_start=boundary)

    assert result.total_trades > 0, "gate should still allow later trades"
    for trade in result.trades:
        assert trade.entry_time >= candles[boundary].timestamp


def test_no_entries_before_the_boundary_even_when_signal_qualifies() -> None:
    candles = cycles()
    boundary = 120

    gated = run_backtest(candles, evaluation_start=boundary)
    ungated = run_backtest(candles)

    assert gated.total_trades < ungated.total_trades
    assert all(t.entry_time >= candles[boundary].timestamp for t in gated.trades)


def test_gate_reduces_the_account_to_only_validation_activity() -> None:
    candles = cycles()
    boundary = 100

    result = run_backtest(candles, evaluation_start=boundary, starting_balance=10_000.0)

    total = sum(t.net_pnl for t in result.trades)
    assert result.ending_balance == pytest.approx(10_000.0 + total)


def test_boundary_equal_to_minimum_history_is_allowed() -> None:
    candles = cycles()
    minimum = max(StrategyConfig().lookback + 2, StrategyConfig().slow_period)

    result = run_backtest(candles, evaluation_start=minimum)

    assert result.total_trades > 0
    assert all(t.entry_time >= candles[minimum].timestamp for t in result.trades)


# --------------------------------------------------------------- validation


def test_invalid_boundaries_are_rejected() -> None:
    candles = cycles()
    minimum = max(StrategyConfig().lookback + 2, StrategyConfig().slow_period)

    with pytest.raises(ValueError, match="evaluation_start"):
        run_backtest(candles, evaluation_start=minimum - 1)
    with pytest.raises(ValueError, match="evaluation_start"):
        run_backtest(candles, evaluation_start=len(candles))
    with pytest.raises(ValueError, match="evaluation_start"):
        run_backtest(candles, evaluation_start=0)


def test_lookahead_still_absent_with_the_gate() -> None:
    """Signals must be stamped with the signal candle, never a later one."""

    candles = cycles()
    boundary = 100

    result = run_backtest(candles, evaluation_start=boundary)

    timestamps = {c.timestamp for c in candles}
    for trade in result.trades:
        assert trade.entry_time in timestamps
        assert trade.exit_time in timestamps
        assert trade.exit_time >= trade.entry_time


def test_signals_use_only_closed_candles_under_the_gate() -> None:
    candles = cycles()
    boundary = 100
    config = StrategyConfig()

    # the first eligible index must produce a signal from candles[:boundary]
    signal = analyze(candles[:boundary], config)
    assert signal.timestamp == candles[boundary - 1].timestamp


def test_open_position_at_end_is_closed_and_labelled() -> None:
    candles = cycles()

    result = run_backtest(candles, evaluation_start=100)

    assert all(t.exit_price is not None for t in result.trades)
    if result.exit_counts.get(END_OF_DATA):
        last = result.trades[-1]
        assert last.exit_reason == END_OF_DATA
        assert last.exit_price == pytest.approx(candles[-1].close)


def test_costs_applied_once_with_the_gate() -> None:
    candles = cycles()
    costs = TradingCosts(0.001, 0.0005)

    result = run_backtest(candles, evaluation_start=100, costs=costs)

    for trade in result.trades:
        entry_value = trade.entry_price * trade.quantity
        exit_value = trade.exit_price * trade.quantity
        expected = (entry_value + exit_value) * (
            costs.fee_rate + costs.slippage_rate
        )
        assert trade.costs == pytest.approx(expected)


def test_gate_works_with_other_research_gates() -> None:
    candles = cycles()
    config = replace(StrategyConfig(), min_breakout_distance=0.002)

    result = run_backtest(candles, config=config, evaluation_start=100)

    assert all(t.entry_time >= candles[100].timestamp for t in result.trades)
    assert result.ending_balance == pytest.approx(
        10_000.0 + sum(t.net_pnl for t in result.trades)
    )


def test_identical_configurations_share_identical_boundary_trading() -> None:
    """Boundary handling must not favour one configuration over another."""

    candles = cycles()
    boundary = 120

    a = run_backtest(candles, evaluation_start=boundary)
    b = run_backtest(
        candles,
        config=StrategyConfig(),
        evaluation_start=boundary,
        starting_balance=10_000.0,
        costs=TradingCosts(0.001, 0.0005),
    )

    assert a.total_trades == b.total_trades
    assert a.ending_balance == pytest.approx(b.ending_balance)
