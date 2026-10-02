"""Tests for the optional Phase 5 research gates.

The central guarantee is that every new option defaults to the original V1
behaviour, so the baseline backtest is unchanged.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.indicators import trend
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig, analyze

FAST = 3
SLOW = 8


def series(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=value - 0.5,
            high=value + 1,
            low=value - 1,
            close=value,
            volume=10,
        )
        for i, value in enumerate(closes)
    ]


# ---------------------------------------------------------------- defaults


def test_research_gate_defaults_match_v1() -> None:
    config = StrategyConfig()

    assert config.lookback == 20
    assert config.fast_period == 5
    assert config.slow_period == 12
    assert config.breakout_buffer == 0.001
    assert config.retest_tolerance == 0.002

    # new gates default to "off", i.e. original V1 behaviour
    assert config.min_breakout_distance == 0.0
    assert config.trend_strength_min == 0.001
    assert config.retest_use_close is False
    assert config.breakout_confirm_bars == 1


def test_default_gates_equal_explicit_v1_config() -> None:
    v1 = StrategyConfig(
        lookback=20,
        fast_period=5,
        slow_period=12,
        breakout_buffer=0.001,
        retest_tolerance=0.002,
    )

    assert StrategyConfig() == v1


def test_trend_default_strength_is_v1_behaviour() -> None:
    candles = series([100 + i for i in range(20)])

    assert trend(candles, 3, 8) == trend(candles, 3, 8, strength=0.001)
    assert trend(candles, 3, 8) == "up"


def test_trend_strength_gate_can_flatten_a_weak_uptrend() -> None:
    # A gentle rise: the fast/slow separation is ~2.5% of price, so it clears
    # the V1 0.1% tolerance but not a deliberately strict one.
    candles = series([100 + i for i in range(20)])

    assert trend(candles, 3, 8) == "up"
    assert trend(candles, 3, 8, strength=0.05) == "sideways"


# ------------------------------------------------------- baseline regression


def test_baseline_signal_is_unchanged_by_new_gates() -> None:
    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    config = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    signal = analyze(candles, config)

    assert signal.side == "long"
    assert signal.reason == "uptrend breakout"
    assert signal.resistance == 124
    assert signal.trend == "up"
    assert signal.breakout is True
    assert signal.retest is False


def test_baseline_backtest_result_is_pinned() -> None:
    """Regression guard: default config must keep the original numbers."""

    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    config = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    result = run_backtest(candles, config)

    assert result.total_trades == 1
    assert result.ending_balance == pytest.approx(10_011.789462, abs=1e-6)


# ------------------------------------------------------------ cost override


def test_backtest_costs_override_is_optional_and_defaults_unchanged() -> None:
    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    config = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    default_run = run_backtest(candles, config)
    explicit_default_costs = run_backtest(
        candles, config, costs=TradingCosts(0.001, 0.0005)
    )
    zero_cost_run = run_backtest(
        candles, config, costs=TradingCosts(0.0, 0.0)
    )

    assert default_run.ending_balance == explicit_default_costs.ending_balance
    assert default_run.total_trades == zero_cost_run.total_trades
    # removing costs can only improve the balance here
    assert zero_cost_run.ending_balance > default_run.ending_balance
    assert all(trade.costs == 0 for trade in zero_cost_run.trades)


# ------------------------------------------------------------- E1 distance


def test_min_breakout_distance_rejects_shallow_breakouts() -> None:
    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    base = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    permissive = analyze(candles, base)
    strict = analyze(
        candles, replace(base, min_breakout_distance=0.5)
    )

    assert permissive.side == "long"
    assert strict.side == "flat"
    assert strict.reason == "no confirmed breakout or retest"


def test_min_breakout_distance_keeps_strong_breakouts() -> None:
    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    base = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    # resistance is 124; the final close is 125, i.e. ~0.8% beyond it
    signal = analyze(candles, replace(base, min_breakout_distance=0.005))

    assert signal.side == "long"
    assert signal.reason == "uptrend breakout"


# ------------------------------------------------------------- E3 retest


def test_retest_use_close_can_reject_a_wick_only_retest() -> None:
    # Build a case where the wick touches the level but the close is far above.
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []

    # 20 quiet candles establishing resistance = 101
    for i in range(20):
        candles.append(
            Candle(
                timestamp=start + timedelta(hours=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10,
            )
        )

    # candle 20 breaks out well above resistance
    candles.append(
        Candle(
            timestamp=start + timedelta(hours=20),
            open=100.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=10,
        )
    )
    # candle 21 wicks back onto the level but closes far above it
    candles.append(
        Candle(
            timestamp=start + timedelta(hours=21),
            open=102.0,
            high=103.0,
            low=100.5,
            close=103.0,
            volume=10,
        )
    )

    base = StrategyConfig(
        lookback=20,
        fast_period=5,
        slow_period=12,
        breakout_buffer=0,
        retest_tolerance=0.01,
    )

    wick_version = analyze(candles, base)
    close_version = analyze(
        candles, replace(base, retest_use_close=True)
    )

    # wick at 100.5 is within 1% of resistance 101 -> retest in the baseline
    assert wick_version.retest is True
    assert wick_version.reason == "bullish retest"
    # the close at 103 is ~2% away from resistance -> not a retest
    assert close_version.retest is False
    assert close_version.reason == "uptrend breakout"


# --------------------------------------------------------- E4 confirmation


def test_breakout_confirm_bars_requires_two_closes() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []

    # 21 quiet candles, then a single breakout candle (22 total, which is the
    # minimum history for lookback=20).
    for i in range(21):
        candles.append(
            Candle(
                timestamp=start + timedelta(hours=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10,
            )
        )

    candles.append(
        Candle(
            timestamp=start + timedelta(hours=21),
            open=100.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=10,
        )
    )

    base = StrategyConfig(
        lookback=20,
        fast_period=5,
        slow_period=12,
        breakout_buffer=0,
    )

    assert analyze(candles, base).reason == "uptrend breakout"
    assert analyze(
        candles, replace(base, breakout_confirm_bars=2)
    ).reason == "no confirmed breakout or retest"


def test_breakout_confirm_bars_accepts_two_consecutive_closes() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []

    for i in range(20):
        candles.append(
            Candle(
                timestamp=start + timedelta(hours=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10,
            )
        )

    candles.append(
        Candle(
            timestamp=start + timedelta(hours=20),
            open=100.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=10,
        )
    )
    candles.append(
        Candle(
            timestamp=start + timedelta(hours=21),
            open=102.0,
            high=104.0,
            low=101.5,
            close=103.0,
            volume=10,
        )
    )

    base = StrategyConfig(
        lookback=20,
        fast_period=5,
        slow_period=12,
        breakout_buffer=0,
    )

    signal = analyze(candles, replace(base, breakout_confirm_bars=2))

    assert signal.reason == "uptrend breakout"


# -------------------------------------------------------------- guards


def test_no_lookahead_confirmation_uses_only_closed_candles() -> None:
    """breakout_confirm_bars must only look at the final closed candles."""

    candles = series([100 + i for i in range(20)] + [123, 124, 125])
    base = StrategyConfig(
        lookback=10,
        fast_period=FAST,
        slow_period=SLOW,
        breakout_buffer=0,
    )

    strict = replace(base, breakout_confirm_bars=2)
    signal = analyze(candles, strict)

    # signal must be stamped with the last candle, not a future one
    assert signal.timestamp == candles[-1].timestamp
    assert signal.price == candles[-1].close


def test_insufficient_history_still_raises() -> None:
    with pytest.raises(ValueError, match="not enough candles"):
        analyze(series([100, 101, 102]))
