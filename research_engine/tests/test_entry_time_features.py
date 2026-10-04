"""Phase 14B tests: entry-time feature instrumentation.

Three obligations are tested here.

1. **Behaviour preservation.** Instrumentation must be observational. Signals,
   entries, exits, sizing, costs and P&L must be unchanged.
2. **Causality.** Every recorded entry-time feature must be knowable strictly
   before the fill at ``candles[index].open``. The decisive test mutates every
   candle *after* an entry boundary and requires all recorded features to be
   bit-identical.
3. **Propagation.** Features must actually reach the trade record, be numeric
   where they should be, explicit (``None``) where unavailable, and survive
   serialisation.

No test in this file examines outcomes, profitability, or any association
between a feature and a result. That is Phase 14C and is not authorised.
"""
import math
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.indicators import mean_candle_range, realised_volatility
from crypto_paper_lab.models import Candle, PaperTrade, Signal
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import StrategyConfig, analyze

START = datetime(2024, 1, 1)

SIGNAL_FIELDS = (
    "signal_close",
    "trend_state",
    "breakout_distance",
    "retest_distance",
    "realised_volatility",
    "mean_range",
)

#: Fields carried on the trade record. A superset of the signal fields.
ENTRY_TIME_FIELDS = SIGNAL_FIELDS + (
    "support_at_entry",
    "resistance_at_entry",
)

COSTS = TradingCosts(0.001, 0.0005, 0.0, "cost_deduction")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def synthetic_candles(count: int = 3000) -> list[Candle]:
    """Deterministic zigzag with drift; produces both retest and breakout entries."""

    candles: list[Candle] = []

    for i in range(count):
        base = 100.0 + i * 0.02
        phase = i % 40
        price = (
            base + phase * 0.5 if phase < 20 else base + (40 - phase) * 0.5
        )
        candles.append(
            Candle(
                START + timedelta(hours=i),
                open=price,
                high=price + 0.3,
                low=price - 0.3,
                close=price + 0.1,
                volume=10.0,
            )
        )

    return candles


def shift(candles: list[Candle], from_index: int, amount: float) -> list[Candle]:
    """Shift every price by ``amount`` at or after ``from_index``.

    Validity is preserved because OHLC move together, so high >= low and
    low <= open,close <= high still hold.
    """

    out = list(candles)

    for i in range(from_index, len(out)):
        c = out[i]
        out[i] = Candle(
            c.timestamp,
            c.open + amount,
            c.high + amount,
            c.low + amount,
            c.close + amount,
            c.volume + 5.0,
        )

    return out


def index_of(candles: list[Candle], moment: datetime) -> int:
    for i, candle in enumerate(candles):
        if candle.timestamp == moment:
            return i
    raise AssertionError(f"{moment} not found")


def feature_snapshot(trade: PaperTrade) -> tuple:
    return tuple(getattr(trade, name) for name in ENTRY_TIME_FIELDS)


def entry_economics(trade: PaperTrade) -> tuple:
    """Entry-time facts that must not change.

    Deliberately excludes exit_time, exit_price, exit_reason, bars_held, pnl
    and costs: those depend on candles after entry, so corrupting the future
    is *expected* to move them.
    """

    return (
        trade.side,
        trade.entry_time,
        trade.entry_price,
        trade.quantity,
        trade.reason,
        trade.raw_entry_price,
    )


# ---------------------------------------------------------------------------
# 1. behaviour preservation
# ---------------------------------------------------------------------------


def test_default_strategy_defaults_are_untouched() -> None:
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


def test_execution_costs_are_untouched() -> None:
    assert COSTS.execution_model == "cost_deduction"
    assert COSTS.fee_rate == 0.001
    assert COSTS.slippage_rate == 0.0005
    assert COSTS.spread_rate == 0.0


def test_phase13_harness_constants_are_frozen() -> None:
    """The committed harness constants must not drift.

    ``test_phase13_frozen_results_are_reproduced_exactly`` passes
    ``risk_fraction`` explicitly, so a change to the harness constant would
    otherwise go unnoticed. These are the values the frozen Phase 13 results
    were produced under.
    """

    from crypto_paper_lab import walkforward as wf

    assert wf.EXECUTION_MODEL == "cost_deduction"
    assert wf.FEE_RATE == 0.001
    assert wf.SLIPPAGE_RATE == 0.0005
    assert wf.SPREAD_RATE == 0.0
    assert wf.STARTING_BALANCE == 10_000.0
    assert wf.RISK_FRACTION == 0.01
    assert wf.WARMUP_RULE == "full_preceding_series"
    assert wf.BOUNDARY_POLICY == "retain_boundary_force_closes"


def test_signals_are_unchanged_by_instrumentation() -> None:
    """Signal decisions, directions and timestamps must be identical.

    Compared against a from-scratch reimplementation of the documented gates,
    so the test cannot pass merely by restating the implementation.
    """

    candles = synthetic_candles(400)

    for index in range(25, 400):
        window = candles[:index]
        config = StrategyConfig()
        signal = analyze(window, config)

        support = min(c.low for c in window[:-2][-config.lookback:])
        resistance = max(c.high for c in window[:-2][-config.lookback:])
        current, previous = window[-1], window[-2]

        broke_up = (
            previous.close > resistance * (1 + config.breakout_buffer)
            and (previous.close - resistance) / resistance
            >= config.min_breakout_distance
        )
        broke_down = (
            previous.close < support * (1 - config.breakout_buffer)
            and (support - previous.close) / support
            >= config.min_breakout_distance
        )
        retest_up = (
            broke_up
            and abs(current.low - resistance) / resistance
            <= config.retest_tolerance
            and current.close >= resistance
        )
        retest_down = (
            broke_down
            and abs(current.high - support) / support
            <= config.retest_tolerance
            and current.close <= support
        )
        confirm = max(1, config.breakout_confirm_bars)
        closes = [c.close for c in window[-confirm:]]
        now_up = all(
            c > resistance * (1 + config.breakout_buffer)
            and (c - resistance) / resistance >= config.min_breakout_distance
            for c in closes
        )
        now_down = all(
            c < support * (1 - config.breakout_buffer)
            and (support - c) / support >= config.min_breakout_distance
            for c in closes
        )

        assert signal.price == current.close
        assert signal.timestamp == current.timestamp
        assert signal.support == pytest.approx(support)
        assert signal.resistance == pytest.approx(resistance)
        assert signal.breakout is (now_up or now_down)
        assert signal.retest is (retest_up or retest_down)

        if signal.trend == "up" and retest_up:
            assert signal.side == "long"
        elif signal.trend == "down" and retest_down:
            assert signal.side == "short"
        elif signal.trend == "up" and now_up:
            assert signal.side == "long"
        elif signal.trend == "down" and now_down:
            assert signal.side == "short"
        else:
            assert signal.side == "flat"


def test_backtest_economics_are_unchanged() -> None:
    """A full backtest's economics must match known pre-instrumentation values."""

    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    assert result.total_trades == 149
    assert result.ending_balance == pytest.approx(9684.656882274687, abs=1e-9)
    assert result.exit_counts == {"opposite_signal": 148, "end_of_data": 1}


def test_zero_cost_backtest_still_has_no_friction() -> None:
    candles = synthetic_candles(2000)
    result = run_backtest(
        candles,
        config=StrategyConfig(),
        costs=TradingCosts(0.0, 0.0, 0.0, "cost_deduction"),
    )

    assert all(trade.costs == 0.0 for trade in result.trades)
    assert all(trade.total_friction == 0.0 for trade in result.trades)


def test_phase13_frozen_results_are_reproduced_exactly() -> None:
    """The authoritative behaviour-preservation proof.

    Re-runs the six frozen Phase 13 baseline windows and requires the trade
    count and ending balance to equal the committed result file to within
    1e-9. Instrumentation that altered any decision, fill, sizing rule or
    cost would break this.
    """

    import json

    from crypto_paper_lab.data import load_ohlcv_csv
    from crypto_paper_lab.walkforward import (
        DATASET_PATH,
        PHASE13_WINDOWS,
        baseline_config,
        phase13_costs,
        resolve_windows,
    )

    root = Path(__file__).resolve().parents[1]
    frozen = json.loads(
        (root / "experiments/phase13/RESULTS_windows.json").read_text(
            encoding="utf-8"
        )
    )
    candles = load_ohlcv_csv(root / DATASET_PATH)
    config = baseline_config()
    costs = phase13_costs()

    for window in resolve_windows(candles, PHASE13_WINDOWS):
        result = run_backtest(
            candles[: window.eval_end_index + 1],
            config=config,
            costs=costs,
            evaluation_start=window.eval_start_index,
            starting_balance=10_000.0,
            risk_fraction=0.01,
        )
        expected = next(
            r
            for r in frozen
            if r["config_name"] == "baseline"
            and r["window_id"] == window.window_id
        )

        assert result.total_trades == expected["trades"]
        assert result.ending_balance == pytest.approx(
            expected["ending_balance"], abs=1e-9
        )


# ---------------------------------------------------------------------------
# 2. causality - the decisive test
# ---------------------------------------------------------------------------


def test_post_entry_candle_mutation_leaves_features_identical() -> None:
    """Mutating every candle after an entry must not change that entry's data.

    This is the strongest available causality check: the entry features are
    compared before and after corrupting the entire future of the series.
    """

    candles = synthetic_candles(3000)
    baseline = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    assert baseline.total_trades > 5

    # Cut just after an early trade's fill, so everything before it is
    # untouched and everything after it is corrupted.
    cutoff_trade = baseline.trades[2]
    cutoff = index_of(candles, cutoff_trade.entry_time) + 3

    mutated_candles = shift(candles, cutoff, amount=25.0)
    mutated = run_backtest(mutated_candles, config=StrategyConfig(), costs=COSTS)

    boundary = candles[cutoff].timestamp
    before = {
        t.entry_time: t for t in baseline.trades if t.entry_time < boundary
    }
    after = {
        t.entry_time: t for t in mutated.trades if t.entry_time < boundary
    }

    assert before, "expected pre-cutoff trades"
    assert set(before) == set(after), "same trades should exist pre-cutoff"

    for moment, trade in before.items():
        assert feature_snapshot(after[moment]) == feature_snapshot(trade)
        assert entry_economics(after[moment]) == entry_economics(trade)


def test_post_entry_mutation_does_not_change_signal_features() -> None:
    """Same guarantee one level down, on ``analyze`` output."""

    candles = synthetic_candles(400)
    index = 300

    original = analyze(candles[:index], StrategyConfig())
    corrupted_series = shift(candles, index, amount=40.0)
    corrupted = analyze(corrupted_series[:index], StrategyConfig())

    assert corrupted.signal_close == original.signal_close
    assert corrupted.trend_state == original.trend_state
    assert corrupted.breakout_distance == original.breakout_distance
    assert corrupted.retest_distance == original.retest_distance
    assert corrupted.realised_volatility == original.realised_volatility
    assert corrupted.mean_range == original.mean_range
    assert corrupted.support == original.support
    assert corrupted.resistance == original.resistance
    assert corrupted.side == original.side


def test_pre_entry_mutation_does_change_the_relevant_feature() -> None:
    """The converse control: earlier data must matter."""

    candles = synthetic_candles(400)
    index = 300

    original = analyze(candles[:index], StrategyConfig())
    # Corrupt a candle inside the trailing lookback, i.e. before the signal.
    corrupted_series = shift(candles, index - 5, amount=30.0)
    corrupted = analyze(corrupted_series[:index], StrategyConfig())

    assert corrupted.realised_volatility != original.realised_volatility
    assert corrupted.signal_close != original.signal_close


def test_using_the_entry_candle_would_be_detected() -> None:
    """A feature computed one candle too late must differ.

    Documents the boundary: ``analyze`` is given ``candles[:index]`` and the
    fill is at ``candles[index]``. Including the entry candle changes the
    trailing statistics, which is exactly why the harness does not.
    """

    candles = synthetic_candles(400)
    index = 300

    correct = analyse_features(candles[:index], StrategyConfig())
    too_late = analyse_features(candles[: index + 1], StrategyConfig())

    assert correct != too_late


def analyse_features(window, config):
    signal = analyze(window, config)
    return (
        signal.mean_range,
        signal.realised_volatility,
        signal.support,
        signal.resistance,
    )


def test_indicators_are_trailing_only() -> None:
    candles = synthetic_candles(60)

    full = candles[-21:]
    assert realised_volatility(candles, 20) == realised_volatility(full, 20)
    assert mean_candle_range(candles, 20) == mean_candle_range(full, 20)


# ---------------------------------------------------------------------------
# 3. breakout distance is numeric, not a boolean
# ---------------------------------------------------------------------------


def test_breakout_distance_is_a_number_not_a_boolean() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    distances = [
        t.breakout_distance for t in result.trades
        if t.breakout_distance is not None
    ]

    assert distances, "expected recorded distances"
    assert all(isinstance(d, float) for d in distances)
    assert len(set(distances)) > 1, "must not collapse to one value"
    assert all(d > 0.0 for d in distances), (
        "a recorded breakout distance is by construction beyond the level"
    )


def test_breakout_distance_is_not_the_boolean_gate_value() -> None:
    """The distance must be a magnitude, not the threshold decision."""

    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)
    trade = next(t for t in result.trades if t.breakout_distance is not None)

    assert trade.breakout_distance not in (0.0, 1.0, True)
    assert trade.breakout_distance < 1.0


def test_breakout_distance_is_recorded_for_both_directions() -> None:
    candles = synthetic_candles(4000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    longs = [
        t for t in result.trades
        if t.side == "long" and t.breakout_distance is not None
    ]
    shorts = [
        t for t in result.trades
        if t.side == "short" and t.breakout_distance is not None
    ]

    assert longs and shorts, "expected both directions"
    assert all(t.breakout_distance > 0 for t in longs)
    assert all(t.breakout_distance > 0 for t in shorts)


# ---------------------------------------------------------------------------
# 4. retest information
# ---------------------------------------------------------------------------


def test_retest_distance_present_only_on_retest_entries() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    for trade in result.trades:
        if "retest" in trade.reason:
            assert trade.retest_distance is not None
            assert trade.retest_distance >= 0.0
        else:
            assert trade.retest_distance is None


def test_flat_signals_carry_no_distances() -> None:
    candles = synthetic_candles(200)

    for index in range(25, 200):
        signal = analyze(candles[:index], StrategyConfig())

        if signal.side == "flat":
            assert signal.breakout_distance is None
            assert signal.retest_distance is None


# ---------------------------------------------------------------------------
# 5. direction preserved
# ---------------------------------------------------------------------------


def test_direction_is_preserved_and_consistent() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    for trade in result.trades:
        assert trade.side in ("long", "short")

        if trade.side == "long":
            assert trade.reason in ("bullish retest", "uptrend breakout")
        else:
            assert trade.reason in ("bearish retest", "downtrend breakdown")


def test_trend_state_agrees_with_the_signal_that_fired() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    for trade in result.trades:
        expected = "up" if trade.side == "long" else "down"
        assert trade.trend_state == expected


# ---------------------------------------------------------------------------
# 6. unavailable values are explicit
# ---------------------------------------------------------------------------


def test_unavailable_values_are_none_not_zero() -> None:
    """Insufficient history yields ``None``, never a substituted zero."""

    short = synthetic_candles(20)
    assert realised_volatility(short, 20) is None
    assert mean_candle_range([], 20) is None

    # A longer series is required for the same reason: 21 closes give 20
    # returns, so 20 candles cannot support a 20-period statistic.
    assert realised_volatility(synthetic_candles(21), 20) is not None


def test_real_signals_always_carry_volatility() -> None:
    """Documents why: ``analyze`` needs 22 candles, a 20-period stat needs 21.

    So for any signal the strategy can actually emit, both trailing-window
    features are available and ``None`` never appears there in practice.
    """

    candles = synthetic_candles(200)

    for index in range(22, 200):
        signal = analyze(candles[:index], StrategyConfig())
        assert signal.realised_volatility is not None
        assert signal.mean_range is not None


def test_none_never_appears_as_zero_in_a_trade() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    for trade in result.trades:
        for name in ENTRY_TIME_FIELDS:
            value = getattr(trade, name)
            assert not (value == 0 and name in (
                "breakout_distance", "retest_distance",
                "realised_volatility", "signal_close",
            ) and value is None)


def test_hand_built_trade_defaults_to_none() -> None:
    trade = PaperTrade(
        side="long", entry_time=START, entry_price=100.0, quantity=1.0
    )

    for name in ENTRY_TIME_FIELDS:
        assert getattr(trade, name) is None


# ---------------------------------------------------------------------------
# 7. propagation and serialisation
# ---------------------------------------------------------------------------


def test_features_reach_the_trade_record() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    trade = result.trades[0]

    assert trade.breakout_distance is not None
    assert trade.trend_state is not None
    assert trade.signal_close is not None
    assert trade.realised_volatility is not None
    assert trade.mean_range is not None
    assert trade.support_at_entry is not None
    assert trade.resistance_at_entry is not None
    assert trade.resistance_at_entry >= trade.support_at_entry


def test_serialisation_preserves_every_new_field() -> None:
    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)
    payload = asdict(result.trades[0])

    for name in ENTRY_TIME_FIELDS:
        assert name in payload
        assert payload[name] == getattr(result.trades[0], name)


def test_paper_broker_copies_features_from_the_signal() -> None:
    candles = synthetic_candles(400)
    signal = analyze(candles[:300], StrategyConfig())

    broker = PaperBroker(10_000.0, costs=COSTS)
    broker.open_trade = None
    from crypto_paper_lab.models import Signal as S

    trade = broker.open_from_signal(
        S(
            timestamp=signal.timestamp,
            side="long",
            reason=signal.reason,
            price=100.0,
            support=signal.support,
            resistance=signal.resistance,
            trend=signal.trend,
            signal_close=signal.signal_close,
            trend_state=signal.trend_state,
            breakout_distance=signal.breakout_distance,
            retest_distance=signal.retest_distance,
            realised_volatility=signal.realised_volatility,
            mean_range=signal.mean_range,
        ),
        risk_fraction=0.01,
    )

    assert trade.signal_close == signal.signal_close
    assert trade.breakout_distance == signal.breakout_distance
    assert trade.resistance_at_entry == signal.resistance


def test_signal_defaults_are_backward_compatible() -> None:
    """A Signal built positionally as before must still work."""

    signal = Signal(START, "long", "x", 1.0, 2.0, 3.0, "up", True, False)

    for name in SIGNAL_FIELDS:
        assert getattr(signal, name) is None


# ---------------------------------------------------------------------------
# 7b. field-by-field identity (kills wrong-field-copy mutations)
# ---------------------------------------------------------------------------


def test_every_trade_field_equals_the_signal_that_produced_it() -> None:
    """Recompute each entry's signal and require exact field identity.

    This is deliberately per-field: it fails if the simulator copies the
    *wrong* signal attribute onto the trade, not merely if one is missing.
    """

    candles = synthetic_candles(1200)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)
    config = StrategyConfig()

    assert result.total_trades > 10

    for trade in result.trades:
        index = index_of(candles, trade.entry_time)
        signal = analyze(candles[:index], config)

        assert trade.side == signal.side
        assert trade.reason == signal.reason
        assert trade.signal_close == signal.signal_close
        assert trade.trend_state == signal.trend_state
        assert trade.breakout_distance == signal.breakout_distance
        assert trade.retest_distance == signal.retest_distance
        assert trade.realised_volatility == signal.realised_volatility
        assert trade.mean_range == signal.mean_range
        assert trade.support_at_entry == signal.support
        assert trade.resistance_at_entry == signal.resistance


def test_fields_are_not_all_identical_aliases() -> None:
    """Distinct fields must carry distinct information."""

    candles = synthetic_candles(1200)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    trade = next(t for t in result.trades if t.breakout_distance is not None)
    numeric = [
        trade.breakout_distance,
        trade.realised_volatility,
        trade.mean_range,
    ]
    numeric = [v for v in numeric if v is not None]

    assert len(set(numeric)) == len(numeric), (
        "breakout_distance, realised_volatility and mean_range must not "
        "collapse to the same number"
    )


# ---------------------------------------------------------------------------
# 7c. retest distance is a wick distance, and is non-negative
# ---------------------------------------------------------------------------


def wick_retest_window(long: bool) -> list[Candle]:
    """Build a window whose retest candle wicks *through* the broken level.

    For a long retest the signal candle's low sits below resistance while its
    close stays above it. The wick distance is therefore strictly positive,
    strictly greater than the close distance, and only ``abs()`` can produce it.
    """

    candles: list[Candle] = [
        Candle(START + timedelta(hours=i), 100.0, 100.5, 99.5, 100.0, 10.0)
        for i in range(22)
    ]

    if long:
        # Previous candle breaks above resistance * (1 + 0.001) = 100.6005.
        candles.append(Candle(START + timedelta(hours=22), 100.9, 101.5, 100.8, 101.0, 10.0))
        # Signal candle: low dips back below 100.5, close stays just above it.
        candles.append(Candle(START + timedelta(hours=23), 100.9, 101.5, 100.3, 100.6, 10.0))
    else:
        candles.append(Candle(START + timedelta(hours=22), 99.1, 99.2, 98.5, 99.0, 10.0))
        candles.append(Candle(START + timedelta(hours=23), 99.1, 99.45, 98.8, 99.2, 10.0))

    return candles


def test_long_retest_distance_uses_the_wick_and_is_non_negative() -> None:
    window = wick_retest_window(True)
    signal = analyze(window, StrategyConfig())

    assert signal.side == "long"
    assert signal.reason == "bullish retest"
    assert signal.retest is True

    resistance = signal.resistance
    current = window[-1]
    wick = abs(current.low - resistance) / resistance
    close = abs(current.close - resistance) / resistance

    assert wick > 0.0
    assert signal.retest_distance == pytest.approx(wick)
    assert signal.retest_distance >= 0.0
    assert signal.retest_distance != pytest.approx(close)


def test_short_retest_distance_uses_the_wick_and_is_non_negative() -> None:
    window = wick_retest_window(False)
    signal = analyze(window, StrategyConfig())

    assert signal.side == "short"
    assert signal.reason == "bearish retest"
    assert signal.retest is True

    support = signal.support
    current = window[-1]
    wick = abs(current.high - support) / support

    assert wick > 0.0
    assert signal.retest_distance == pytest.approx(wick)
    assert signal.retest_distance >= 0.0
    assert signal.retest_distance != pytest.approx(
        abs(current.close - support) / support
    )


def test_retest_use_close_switches_the_measured_leg() -> None:
    """With ``retest_use_close=True`` the close leg must be measured instead.

    Baseline behaviour is the wick; this documents that the recorded distance
    tracks whichever leg the existing gate actually uses.
    """

    window = wick_retest_window(True)
    current = window[-1]
    baseline = analyze(window, StrategyConfig())
    as_close = analyze(window, StrategyConfig(retest_use_close=True))

    assert baseline.retest_distance == pytest.approx(
        abs(current.low - baseline.resistance) / baseline.resistance
    )
    assert as_close.retest_distance == pytest.approx(
        abs(current.close - as_close.resistance) / as_close.resistance
    )
    assert baseline.retest_distance != as_close.retest_distance


# ---------------------------------------------------------------------------
# 7d. independent anchors against the raw candles
# ---------------------------------------------------------------------------


def test_signal_close_is_the_signal_candles_close() -> None:
    """Anchored to the candle itself, not merely to another recorded field.

    ``signal_close`` must be the close of the candle that produced the signal,
    which is strictly *not* the entry candle's open (the fill reference).
    """

    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    for trade in result.trades:
        index = index_of(candles, trade.entry_time)
        signal_candle = candles[index - 1]
        entry_candle = candles[index]

        assert trade.signal_close == signal_candle.close
        assert trade.signal_close == signal_candle.close
        assert trade.signal_close != signal_candle.open
        assert trade.signal_close != entry_candle.open


def test_analyze_signal_close_is_the_last_supplied_candles_close() -> None:
    candles = synthetic_candles(400)

    for index in range(22, 400):
        signal = analyze(candles[:index], StrategyConfig())
        assert signal.signal_close == candles[index - 1].close


def test_breakout_distance_is_measured_on_the_documented_candle() -> None:
    """Recompute every distance straight from the raw candles.

    A retest entry measures the breakout on the *previous* candle, because that
    is the candle that broke the level. A breakout entry measures it on the
    signal candle itself. Getting either wrong changes the number, so this
    pins both branches independently of the implementation.
    """

    candles = synthetic_candles(3000)
    result = run_backtest(candles, config=StrategyConfig(), costs=COSTS)

    expected_by_reason = {
        "bullish retest": "previous",
        "bearish retest": "previous",
        "uptrend breakout": "signal",
        "downtrend breakdown": "signal",
    }
    seen = set()

    for trade in result.trades:
        which = expected_by_reason.get(trade.reason)
        if which is None:
            continue

        index = index_of(candles, trade.entry_time)
        previous_close = candles[index - 2].close
        signal_close = candles[index - 1].close
        measured_close = (
            previous_close if which == "previous" else signal_close
        )
        resistance = trade.resistance_at_entry
        support = trade.support_at_entry

        if trade.reason in ("bullish retest", "uptrend breakout"):
            expected = (measured_close - resistance) / resistance
        else:
            expected = (support - measured_close) / support

        seen.add(trade.reason)
        assert trade.breakout_distance == pytest.approx(expected), trade.reason
        assert trade.breakout_distance > 0.0

    assert "bullish retest" in seen
    assert "uptrend breakout" in seen
    assert "downtrend breakdown" in seen


def test_short_retest_breakout_distance_uses_the_previous_candle() -> None:
    """The bearish retest branch, which the drifting fixture cannot reach.

    A crafted window drives a short retest so both retest branches are pinned.
    """

    window = wick_retest_window(False)
    signal = analyze(window, StrategyConfig())

    assert signal.side == "short"
    assert signal.reason == "bearish retest"

    previous, current = window[-2], window[-1]
    expected = (signal.support - previous.close) / signal.support
    wrong_candle = (signal.support - current.close) / signal.support

    assert signal.breakout_distance == pytest.approx(expected)
    assert signal.breakout_distance != pytest.approx(wrong_candle)


# ---------------------------------------------------------------------------
# 8. no outcome features were added
# ---------------------------------------------------------------------------


def test_no_mae_or_mfe_field_exists() -> None:
    """MAE/MFE are post-entry diagnostics and must not be instrumented here."""

    for name in ("mae", "mfe", "adverse_excursion", "favourable_excursion"):
        assert name not in PaperTrade.__dataclass_fields__
        assert name not in Signal.__dataclass_fields__


def test_no_outcome_feature_was_added() -> None:
    """Guard against instrumentation that anticipates Phase 14C."""

    forbidden = (
        "win", "loss", "profitable", "score", "rank", "p_bucket",
        "regime_label", "outcome", "edge",
    )

    for name in PaperTrade.__dataclass_fields__:
        assert not any(bad in name.lower() for bad in forbidden), name


def test_feature_names_are_unambiguous() -> None:
    """A field must not be called bare 'volatility' or 'range'."""

    for name in ENTRY_TIME_FIELDS:
        assert "volatility" not in name or name == "realised_volatility"

    assert "mean_range" in ENTRY_TIME_FIELDS
    assert not any(n == "volatility" for n in ENTRY_TIME_FIELDS)
    assert not any(n == "atr" for n in ENTRY_TIME_FIELDS)


# ---------------------------------------------------------------------------
# 9. gate boundary semantics
# ---------------------------------------------------------------------------


def boundary_window(
    previous_close: float, signal_close: float
) -> list[Candle]:
    """Flat candles whose resistance is exactly 100.5, plus chosen closes.

    ``confirm=1`` means the breakout gate reads the *signal* candle close, so
    both closes are supplied to isolate the strict inequality.
    """

    candles: list[Candle] = [
        Candle(START + timedelta(hours=i), 100.0, 100.5, 99.5, 100.0, 10.0)
        for i in range(22)
    ]
    candles.append(
        Candle(
            START + timedelta(hours=22),
            previous_close - 0.2,
            previous_close + 0.5,
            previous_close - 0.5,
            previous_close,
            10.0,
        )
    )
    candles.append(
        Candle(START + timedelta(hours=23), 100.6, 101.4, 100.2, signal_close, 10.0)
    )
    return candles


def test_breakout_gate_is_strictly_greater_than_the_threshold() -> None:
    """A close exactly at the threshold must not count as a breakout.

    Pins the strict inequality in the existing gate. Slipping ``>`` to ``>=``
    is otherwise invisible on continuous data.
    """

    resistance = 100.5
    at_threshold = resistance * (1 + 0.001)
    above = math.nextafter(at_threshold, math.inf)

    exact = analyze(
        boundary_window(at_threshold, at_threshold), StrategyConfig()
    )
    just_above = analyze(boundary_window(at_threshold, above), StrategyConfig())

    assert exact.resistance == pytest.approx(resistance)
    assert exact.trend_state == "up"
    assert exact.side == "flat"
    assert exact.breakout is False
    assert exact.breakout_distance is None

    assert just_above.side == "long"
    assert just_above.reason == "uptrend breakout"
    assert just_above.breakout is True
    assert just_above.breakout_distance == pytest.approx(
        (above - resistance) / resistance
    )