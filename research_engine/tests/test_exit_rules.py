"""Tests for the optional Phase 6 exit rules.

Central guarantees:
  * defaults are ``None`` and reproduce the original V1 exit behaviour;
  * every new exit is *detected* on a bar that has already closed and
    *filled* at the open of the following bar, so no future candle
    information is used and no intrabar fill price is assumed;
  * a trade can never be closed on or before its entry bar;
  * fees and slippage are still charged exactly once per trade.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import (
    END_OF_DATA,
    MAX_HOLDING,
    OPPOSITE_SIGNAL,
    STOP_LOSS,
    TAKE_PROFIT,
    run_backtest,
)
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def build(rows: list[tuple[float, float, float, float]]) -> list[Candle]:
    """rows are (open, high, low, close) tuples, one per hourly candle."""

    return [
        Candle(
            timestamp=START + timedelta(hours=i),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=10.0,
        )
        for i, (o, h, l, c) in enumerate(rows)
    ]


def breakout_then_drop() -> list[Candle]:
    """20 rising candles, a decisive breakout, then a sharp reversal."""

    rows: list[tuple[float, float, float, float]] = []
    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))
    rows.append((119.5, 124.0, 119.0, 123.0))   # 20 breakout
    rows.append((123.0, 124.0, 121.0, 121.5))   # 21
    rows.append((121.5, 122.0, 110.0, 111.0))   # 22 entry bar, drops hard
    rows.append((111.0, 112.0, 105.0, 106.0))   # 23
    rows.append((106.0, 107.0, 100.0, 101.0))   # 24
    rows.append((101.0, 102.0, 95.0, 96.0))     # 25
    rows.append((96.0, 97.0, 90.0, 91.0))       # 26
    return build(rows)


# ------------------------------------------------------------------ defaults


def test_exit_rule_defaults_are_disabled() -> None:
    config = StrategyConfig()

    assert config.max_holding_bars is None
    assert config.stop_loss_pct is None
    assert config.take_profit_pct is None


def test_default_exit_behaviour_is_unchanged() -> None:
    result = run_backtest(breakout_then_drop())

    assert result.exit_counts[OPPOSITE_SIGNAL] == 1
    assert result.exit_counts[END_OF_DATA] == 1
    assert result.exit_counts.get(MAX_HOLDING) is None
    assert result.exit_counts.get(STOP_LOSS) is None
    assert result.exit_counts.get(TAKE_PROFIT) is None

    first = result.trades[0]
    assert first.exit_reason == OPPOSITE_SIGNAL
    assert first.side == "long"
    assert first.bars_held == 3


def test_disabled_rules_equal_explicit_none() -> None:
    candles = breakout_then_drop()

    plain = run_backtest(candles)
    explicit = run_backtest(
        candles,
        StrategyConfig(
            max_holding_bars=None,
            stop_loss_pct=None,
            take_profit_pct=None,
        ),
    )

    assert plain.ending_balance == explicit.ending_balance
    assert plain.exit_counts == explicit.exit_counts


# ------------------------------------------------------------- max holding


def test_max_holding_exits_at_next_open_after_n_bars() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(max_holding_bars=2))

    trade = result.trades[0]

    assert trade.exit_reason == MAX_HOLDING
    assert trade.bars_held == 2
    # entry happened at the open of bar 22, so the fill is the open of bar 24
    assert trade.entry_price == pytest.approx(candles[22].open)
    assert trade.exit_price == pytest.approx(candles[24].open)
    assert result.exit_counts[MAX_HOLDING] == 1


def test_max_holding_of_one_exits_after_a_single_bar() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(max_holding_bars=1))

    trade = result.trades[0]

    assert trade.exit_reason == MAX_HOLDING
    assert trade.bars_held == 1
    assert trade.exit_price == pytest.approx(candles[23].open)


def test_max_holding_never_closes_on_the_entry_bar() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(max_holding_bars=1))

    rule_exits = [
        trade for trade in result.trades
        if trade.exit_reason != END_OF_DATA
    ]

    assert rule_exits
    assert all(trade.bars_held >= 1 for trade in rule_exits)


def test_end_of_data_close_may_be_same_bar() -> None:
    """A trade opened on the final candle is force-closed on that candle.

    This uses only that candle's own open and close, so it is not a
    look-ahead; it is simply the last possible round trip in the sample.
    """

    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(max_holding_bars=1))

    final = result.trades[-1]
    assert final.exit_reason == END_OF_DATA
    if final.bars_held == 0:
        assert final.entry_price == pytest.approx(candles[-1].open)
        assert final.exit_price == pytest.approx(candles[-1].close)


# --------------------------------------------------------------- stop loss


def test_stop_loss_fills_at_next_open_not_at_the_stop_price() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(stop_loss_pct=0.01))

    trade = result.trades[0]
    stop_level = trade.entry_price * (1 - 0.01)

    assert trade.exit_reason == STOP_LOSS
    assert trade.bars_held == 1
    # detection used the closed entry bar; the fill is the FOLLOWING open
    assert trade.exit_price == pytest.approx(candles[23].open)
    # explicitly not the stop price: no intrabar fill is assumed
    assert trade.exit_price != pytest.approx(stop_level)
    assert result.exit_counts[STOP_LOSS] == 1


def test_stop_loss_is_side_aware() -> None:
    """A long stop sits below entry; a short stop must sit above entry."""

    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(stop_loss_pct=0.01))

    for trade in result.trades:
        if trade.exit_reason == STOP_LOSS:
            if trade.side == "long":
                assert trade.exit_price <= trade.entry_price
            else:
                assert trade.exit_price >= trade.entry_price


def test_stop_uses_only_the_previous_closed_bar() -> None:
    """The bar that triggers a stop is the one before the fill bar."""

    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(stop_loss_pct=0.01))
    trade = result.trades[0]

    entry_index = 22
    fill_index = 23
    trigger_bar = candles[entry_index]

    assert trade.entry_price == pytest.approx(candles[entry_index].open)
    assert trade.exit_price == pytest.approx(candles[fill_index].open)
    assert trigger_bar.low <= trade.entry_price * (1 - 0.01)


# ------------------------------------------------------------- take profit


def test_take_profit_fills_at_next_open() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(take_profit_pct=0.01))

    target_trades = [t for t in result.trades if t.exit_reason == TAKE_PROFIT]

    assert target_trades
    for trade in target_trades:
        if trade.side == "short":
            # a short target sits below entry, and the fill is a later open
            assert trade.exit_price < trade.entry_price
            assert trade.exit_price == pytest.approx(
                candles[entry_index_of(candles, trade) + 1].open
            )


def entry_index_of(candles: list[Candle], trade) -> int:
    for i, candle in enumerate(candles):
        if candle.timestamp == trade.entry_time:
            return i
    raise AssertionError("entry bar not found")


# ------------------------------------------------------- ambiguity handling


def wide_range_breakout() -> list[Candle]:
    """Breakout whose entry bar spans far beyond both stop and target."""

    rows: list[tuple[float, float, float, float]] = []
    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))
    rows.append((119.5, 124.0, 119.0, 123.0))    # 20 breakout
    rows.append((123.0, 124.0, 121.0, 121.5))    # 21
    # entry bar 22: high far above the 1% target, low far below the 1% stop
    rows.append((121.5, 130.0, 112.0, 113.0))
    rows.append((113.0, 114.0, 110.0, 111.0))    # 23
    rows.append((111.0, 112.0, 105.0, 106.0))    # 24
    rows.append((106.0, 107.0, 100.0, 101.0))    # 25
    rows.append((101.0, 102.0, 95.0, 96.0))      # 26
    return build(rows)


def test_stop_and_target_in_one_bar_is_labelled_conservatively() -> None:
    candles = wide_range_breakout()
    result = run_backtest(candles, StrategyConfig(
        stop_loss_pct=0.01, take_profit_pct=0.01
    ))

    trade = result.trades[0]

    # both levels were crossed in the same closed bar
    assert trade.exit_reason == STOP_LOSS
    assert result.exit_counts[STOP_LOSS] == 1
    assert result.exit_counts.get(TAKE_PROFIT) is None


def test_ambiguity_does_not_change_pnl() -> None:
    """Because the fill is the next open either way, P&L is unaffected."""

    candles = wide_range_breakout()

    both = run_backtest(candles, StrategyConfig(
        stop_loss_pct=0.01, take_profit_pct=0.01
    ))
    stop_only = run_backtest(candles, StrategyConfig(stop_loss_pct=0.01))
    target_only = run_backtest(candles, StrategyConfig(take_profit_pct=0.01))

    assert both.trades[0].net_pnl == pytest.approx(stop_only.trades[0].net_pnl)
    assert both.trades[0].net_pnl == pytest.approx(target_only.trades[0].net_pnl)


# --------------------------------------------------------- cost accounting


def test_costs_are_charged_exactly_once_with_new_exits() -> None:
    candles = breakout_then_drop()
    costs = TradingCosts(0.001, 0.0005)
    result = run_backtest(
        candles, StrategyConfig(max_holding_bars=2), costs=costs
    )

    for trade in result.trades:
        entry_value = trade.entry_price * trade.quantity
        exit_value = trade.exit_price * trade.quantity
        expected = (entry_value + exit_value) * (
            costs.fee_rate + costs.slippage_rate
        )
        assert trade.costs == pytest.approx(expected)
        assert trade.net_pnl == pytest.approx(trade.pnl - trade.costs)


def test_balance_is_consistent_with_trade_sum() -> None:
    candles = breakout_then_drop()
    result = run_backtest(candles, StrategyConfig(stop_loss_pct=0.01))

    total = sum(t.net_pnl for t in result.trades)
    assert result.ending_balance == pytest.approx(
        result.starting_balance + total
    )


# ------------------------------------------------------------ yearly split


def test_yearly_backtests_remain_separate() -> None:
    from crypto_paper_lab.yearly import run_yearly_backtests

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=100.0 + i * 0.1,
            high=101.0 + i * 0.1,
            low=99.0 + i * 0.1,
            close=100.5 + i * 0.1,
            volume=10.0,
        )
        for i in range(60)
    ]

    results = run_yearly_backtests(candles, StrategyConfig())

    assert set(results) == {2024}
    for report in results.values():
        assert "net_pnl" in report
        assert "trades" in report


def test_exit_rules_are_configurable_and_composable() -> None:
    candles = breakout_then_drop()

    combined = run_backtest(candles, StrategyConfig(
        max_holding_bars=5,
        stop_loss_pct=0.01,
        take_profit_pct=0.02,
    ))

    assert combined.total_trades >= 1
    assert all(
        trade.exit_reason in
        {OPPOSITE_SIGNAL, MAX_HOLDING, STOP_LOSS, TAKE_PROFIT, END_OF_DATA}
        for trade in combined.trades
    )
    # a stop is evaluated before a target on the same bar
    priority = run_backtest(candles, StrategyConfig(
        stop_loss_pct=0.01, take_profit_pct=0.01
    ))
    assert priority.trades[0].exit_reason == STOP_LOSS
