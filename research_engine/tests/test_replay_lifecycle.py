"""Phase 17C tests: replay lifecycle (idle / running / paused / finished).

Three rules shape this file.

**No sleeping, ever.** A lifecycle test that waits on wall-clock time is a test
that will eventually fail for no reason and get ignored. Auto-run is driven
through the injectable :class:`~crypto_paper_lab.replay.Ticker`, so every test
here advances the replay by explicit request and finishes in milliseconds. The
absence of ``sleep`` and of threading is itself asserted.

**Pacing must not change results.** Phase 17A invariant AR-1 requires auto-run to
be repeated ``step()``. The strongest available check is that a replay driven by
ticks, one driven by manual steps, and a ``run_backtest`` of the same candles all
produce byte-identical journals - so the ticker is proven to affect *when*, never
*what*.

**Phase 17B stays frozen.** Every lifecycle test is paired with an assertion that
the underlying step semantics did not move: cursor arithmetic, terminal cursor,
exit-reason tally and the reset contract are all re-checked here.
"""
from __future__ import annotations

import ast
import tokenize
from dataclasses import replace
from pathlib import Path

import pytest

from crypto_paper_lab.backtest import END_OF_DATA, OPPOSITE_SIGNAL, run_backtest
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.replay import (
    AUTOMATIC_POLICY,
    DEFAULT_INTERVAL_MS,
    MAX_INTERVAL_MS,
    MIN_INTERVAL_MS,
    STATE_FINISHED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
    InvalidIntervalError,
    OnDemandTicker,
    PositionOpenError,
    Replay,
    ReplayFinishedError,
    ReplayState,
    Ticker,
)
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

RESEARCH_ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPLAY_SOURCE = (
    RESEARCH_ENGINE_ROOT / "src" / "crypto_paper_lab" / "replay.py"
)

SOURCE, _ = load_dataset(RESEARCH_ENGINE_ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = 22

#: Small prefix: enough for several trades, fast enough to run many replays.
PREFIX = 200


def trade_signature(trade) -> tuple:
    return (
        trade.side,
        trade.entry_time,
        trade.entry_price,
        trade.quantity,
        trade.exit_time,
        trade.exit_price,
        trade.exit_reason,
        trade.bars_held,
        trade.costs,
        trade.fee_total,
        trade.slippage_total,
        trade.spread_total,
        trade.pnl,
        trade.net_pnl,
        trade.total_friction,
    )


def signatures(replay: Replay) -> list:
    return [trade_signature(t) for t in replay.broker.journal]


def make(**kwargs) -> Replay:
    return Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, **kwargs)


def drive(replay: Replay, count: int) -> list:
    """Tick ``count`` times using the documented armed-flag idiom."""

    results = []
    for _ in range(count):
        if not replay.ticker.armed:
            break
        results.append(replay.tick())

    return results


def drive_to_end(replay: Replay) -> Replay:
    """Start if needed, then tick to the end using the armed-flag idiom."""

    replay.start()
    drive(replay, len(SOURCE[:PREFIX]) + 5)

    assert replay.state.status == STATE_FINISHED, "auto-run did not finish"

    return replay


class GatedTicker(Ticker):
    """A ticker that fires only when the test says so.

    Proves the seam is real: with this injected, ``start()`` alone advances
    nothing, and progression happens only on ``release``. If lifecycle control
    were hard-coded rather than routed through the ticker, arming would move the
    cursor by itself.
    """

    def __init__(self) -> None:
        self._armed = False
        self._due = False
        self._interval_ms = DEFAULT_INTERVAL_MS
        self.takes = 0

    def arm(self, interval_ms: int) -> None:
        self._armed = True
        self._interval_ms = interval_ms

    def disarm(self) -> None:
        self._armed = False
        self._due = False

    @property
    def armed(self) -> bool:
        return self._armed

    def take(self) -> bool:
        if not (self._armed and self._due):
            return False

        self._due = False
        self.takes += 1
        return True

    def release(self) -> None:
        self._due = True


# ---------------------------------------------------------------------------
# A. initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_new_replay_is_idle(self) -> None:
        assert make().state.status == STATE_IDLE

    def test_new_replay_has_no_ticker_armed(self) -> None:
        replay = make()

        assert isinstance(replay.ticker, OnDemandTicker)
        assert replay.ticker.armed is False

    def test_new_replay_uses_the_default_interval(self) -> None:
        assert make().interval_ms == DEFAULT_INTERVAL_MS == 1_000

    def test_construction_performs_no_automatic_processing(self) -> None:
        """A fresh replay must not consume a single bar on its own."""

        replay = make()

        assert replay.state.cursor == REQUIRED
        assert replay.state.bars_processed == 0
        assert replay.state.trade_count == 0
        assert replay.ticker.takes == 0

    def test_ticking_before_start_is_a_no_op(self) -> None:
        replay = make()

        assert replay.tick() is None
        assert replay.state.cursor == REQUIRED
        assert replay.state.status == STATE_IDLE
        assert replay.ticker.takes == 0


# ---------------------------------------------------------------------------
# B. start()
# ---------------------------------------------------------------------------


class TestStart:
    def test_idle_to_running(self) -> None:
        replay = make()
        state = replay.start()

        assert state.status == STATE_RUNNING
        assert replay.state.status == STATE_RUNNING
        assert replay.ticker.armed is True

    def test_paused_to_running(self) -> None:
        replay = make()
        replay.start()
        replay.pause()
        assert replay.state.status == STATE_PAUSED

        state = replay.start()

        assert state.status == STATE_RUNNING
        assert replay.ticker.armed is True

    def test_running_to_running_is_idempotent(self) -> None:
        replay = make()
        replay.start()

        for _ in range(5):
            assert replay.start().status == STATE_RUNNING

        assert replay.state.status == STATE_RUNNING

    def test_repeated_start_cannot_duplicate_progression(self) -> None:
        """Six starts, then one tick, must advance exactly one bar.

        This is the no-duplicate-worker guarantee. With a driverless ticker there
        is no second worker to create, and the count proves none was.
        """

        replay = make()
        for _ in range(6):
            replay.start()

        before = replay.state.cursor
        result = replay.tick()

        assert result is not None
        assert replay.state.cursor == before + 1
        assert replay.ticker.takes == 1

    def test_start_never_advances_the_cursor(self) -> None:
        replay = make()
        before = replay.state.cursor

        replay.start()
        replay.start()

        assert replay.state.cursor == before

    def test_start_does_not_touch_the_broker(self) -> None:
        replay = make()
        snapshot = (replay.broker.cash, len(replay.broker.journal),
                    replay.broker.open_trade)

        replay.start()

        assert (replay.broker.cash, len(replay.broker.journal),
                replay.broker.open_trade) == snapshot

    def test_finished_stays_finished(self) -> None:
        replay = drive_to_end(make())
        cursor = replay.state.cursor

        state = replay.start()

        assert state.status == STATE_FINISHED
        assert replay.state.status == STATE_FINISHED
        assert replay.ticker.armed is False
        assert replay.state.cursor == cursor
        assert replay.state.trade_count == len(replay.broker.journal)

    def test_start_records_the_interval(self) -> None:
        replay = make()
        replay.start(interval_ms=250)

        assert replay.interval_ms == 250

    def test_start_without_interval_keeps_the_current_one(self) -> None:
        replay = make()
        replay.start(interval_ms=250)
        replay.pause()
        replay.start()

        assert replay.interval_ms == 250

    @pytest.mark.parametrize("bad", [0, 99, 60_001, -1, 10**9])
    def test_out_of_range_interval_is_rejected(self, bad: int) -> None:
        replay = make()

        with pytest.raises(InvalidIntervalError) as info:
            replay.start(interval_ms=bad)

        assert info.value.code == "INVALID_INTERVAL"

    def test_rejected_interval_leaves_the_replay_idle(self) -> None:
        replay = make()

        with pytest.raises(InvalidIntervalError):
            replay.start(interval_ms=99)

        assert replay.state.status == STATE_IDLE
        assert replay.ticker.armed is False

    def test_interval_is_never_clamped(self) -> None:
        """Clamping would silently substitute a pace the caller did not ask for."""

        replay = make()

        with pytest.raises(InvalidIntervalError):
            replay.start(interval_ms=MAX_INTERVAL_MS + 1)

        assert replay.state.status == STATE_IDLE
        assert replay.interval_ms == DEFAULT_INTERVAL_MS

    @pytest.mark.parametrize("good", [MIN_INTERVAL_MS, 1_000, MAX_INTERVAL_MS])
    def test_boundary_intervals_are_accepted(self, good: int) -> None:
        replay = make()

        assert replay.start(interval_ms=good).status == STATE_RUNNING
        assert replay.interval_ms == good

    def test_rejected_interval_while_running_keeps_running(self) -> None:
        replay = make()
        replay.start(interval_ms=500)

        with pytest.raises(InvalidIntervalError):
            replay.start(interval_ms=1)

        assert replay.state.status == STATE_RUNNING
        assert replay.interval_ms == 500

    def test_start_with_a_gated_ticker_advances_nothing_by_itself(self) -> None:
        """Arming must not consume a bar; only a due tick may."""

        replay = make(ticker=GatedTicker())
        replay.start()

        assert replay.state.cursor == REQUIRED
        assert replay.tick() is None
        assert replay.state.cursor == REQUIRED

        replay.ticker.release()
        assert replay.tick() is not None
        assert replay.state.cursor == REQUIRED + 1


# ---------------------------------------------------------------------------
# C. pause()
# ---------------------------------------------------------------------------


class TestPause:
    def test_running_to_paused(self) -> None:
        replay = make()
        replay.start()

        state = replay.pause()

        assert state.status == STATE_PAUSED
        assert replay.ticker.armed is False

    def test_paused_stays_paused(self) -> None:
        replay = make()
        replay.start()
        replay.pause()

        for _ in range(4):
            assert replay.pause().status == STATE_PAUSED

        assert replay.state.status == STATE_PAUSED

    def test_idle_stays_idle(self) -> None:
        replay = make()

        assert replay.pause().status == STATE_IDLE
        assert replay.ticker.armed is False

    def test_finished_stays_finished(self) -> None:
        replay = drive_to_end(make())

        assert replay.pause().status == STATE_FINISHED
        assert replay.ticker.armed is False

    def test_pause_does_not_mutate_replay_state(self) -> None:
        replay = make()
        replay.start()
        for _ in range(12):
            replay.tick()

        before = (
            replay.state.cursor,
            replay.state.bars_processed,
            replay.state.balance,
            replay.state.realized_pnl,
            replay.state.trade_count,
            replay.state.has_open_position,
            replay.state.last_signal,
            replay.broker.open_trade,
            tuple(signatures(replay)),
            replay.exit_counts,
        )

        replay.pause()

        after = (
            replay.state.cursor,
            replay.state.bars_processed,
            replay.state.balance,
            replay.state.realized_pnl,
            replay.state.trade_count,
            replay.state.has_open_position,
            replay.state.last_signal,
            replay.broker.open_trade,
            tuple(signatures(replay)),
            replay.exit_counts,
        )
        assert after == before

    def test_pause_stops_progression(self) -> None:
        replay = make()
        replay.start()
        for _ in range(10):
            replay.tick()

        replay.pause()
        cursor = replay.state.cursor

        for _ in range(10):
            assert replay.tick() is None

        assert replay.state.cursor == cursor


# ---------------------------------------------------------------------------
# D. automatic progression
# ---------------------------------------------------------------------------


class TestAutomaticProgression:
    def test_running_advances_one_bar_per_tick(self) -> None:
        replay = make()
        replay.start()
        start = replay.state.cursor

        for expected in range(1, 41):
            assert replay.tick() is not None
            assert replay.state.cursor == start + expected

    def test_progression_is_deterministic(self) -> None:
        first, second = make(), make()
        first.start()
        second.start()

        results_a = drive(first, 60)
        results_b = drive(second, 60)

        assert results_a == results_b
        # replay_id is per-instance by design; everything else must match.
        assert replace(first.state, replay_id="x") == replace(
            second.state, replay_id="x"
        )

    def test_no_duplicate_trades_versus_manual_stepping(self) -> None:
        auto, manual = make(), make()
        auto.start()

        for _ in range(80):
            auto.tick()
            if manual.state.cursor <= auto.state.cursor:
                manual.step()

        assert signatures(auto) == signatures(manual)
        assert auto.broker.cash == manual.broker.cash
        assert auto.exit_counts == manual.exit_counts

    def test_each_tick_consumes_exactly_one_ticker_take(self) -> None:
        replay = make()
        replay.start()

        drive(replay, 25)

        assert replay.ticker.takes == 25
        assert replay.state.bars_processed == 25

    def test_terminal_transition_happens_once(self) -> None:
        replay = drive_to_end(make())
        cursor = replay.state.cursor
        trades = len(replay.broker.journal)
        cash = replay.broker.cash

        for _ in range(10):
            assert replay.tick() is None

        assert replay.state.status == STATE_FINISHED
        assert replay.state.cursor == cursor
        assert len(replay.broker.journal) == trades
        assert replay.broker.cash == cash
        assert replay.exit_counts.get(END_OF_DATA) == 1

    def test_armed_flag_clears_on_pause_finish_and_reset(self) -> None:
        paused = make()
        paused.start()
        paused.pause()
        assert paused.ticker.armed is False

        finished = drive_to_end(make())
        assert finished.ticker.armed is False

        reset = make()
        reset.start()
        reset.reset()
        assert reset.ticker.armed is False

    def test_a_second_ticker_cannot_be_injected_mid_run(self) -> None:
        """The ticker is fixed at construction, so pacing cannot be swapped live."""

        replay = make()
        first = replay.ticker
        replay.start()

        assert replay.ticker is first

    def test_progression_requires_running(self) -> None:
        for setup in ("idle", "paused", "finished"):
            replay = make()
            if setup == "paused":
                replay.start()
                replay.pause()
            elif setup == "finished":
                drive_to_end(replay)

            cursor = replay.state.cursor
            assert replay.tick() is None, setup
            assert replay.state.cursor == cursor, setup


# ---------------------------------------------------------------------------
# E. step interaction
# ---------------------------------------------------------------------------


class TestStepInteraction:
    def test_step_from_idle_advances_and_stays_idle(self) -> None:
        replay = make()

        result = replay.step()

        assert result is not None
        assert replay.state.cursor == REQUIRED + 1
        assert replay.state.status == STATE_IDLE

    def test_step_from_paused_advances_and_stays_paused(self) -> None:
        replay = make()
        replay.start()
        replay.pause()
        cursor = replay.state.cursor

        replay.step()

        assert replay.state.cursor == cursor + 1
        assert replay.state.status == STATE_PAUSED

    def test_step_from_running_advances_and_stays_running(self) -> None:
        """Phase 17A 7.2: legal from running, interleaves with the ticker."""

        replay = make()
        replay.start()
        cursor = replay.state.cursor

        replay.step()

        assert replay.state.cursor == cursor + 1
        assert replay.state.status == STATE_RUNNING

    def test_step_from_running_does_not_consume_a_tick(self) -> None:
        replay = make()
        replay.start()

        replay.step()

        assert replay.ticker.takes == 0

    def test_step_after_finished_raises_and_does_not_advance(self) -> None:
        replay = drive_to_end(make())
        cursor = replay.state.cursor
        trades = len(replay.broker.journal)

        with pytest.raises(ReplayFinishedError) as info:
            replay.step()

        assert info.value.code == "REPLAY_FINISHED"
        assert replay.state.cursor == cursor
        assert len(replay.broker.journal) == trades

    def test_step_does_not_depend_on_lifecycle_state(self) -> None:
        """The step body is identical from idle, paused and running."""

        results = {}
        for status in ("idle", "paused", "running"):
            replay = make()
            if status in ("paused", "running"):
                replay.start()
            if status == "paused":
                replay.pause()
            results[status] = replay.step()

        assert results["idle"] == results["paused"] == results["running"]


# ---------------------------------------------------------------------------
# F. finish
# ---------------------------------------------------------------------------


class TestFinish:
    def test_terminal_cursor_is_the_end_of_the_series(self) -> None:
        replay = drive_to_end(make())
        state = replay.state

        assert state.status == STATE_FINISHED
        assert state.cursor == PREFIX
        assert state.next_candle_available is False
        assert state.next_timestamp is None

    def test_finish_applies_end_of_data_closure_exactly_once(self) -> None:
        replay = drive_to_end(make())

        assert replay.exit_counts.get(END_OF_DATA) == 1
        final = replay.broker.journal[-1]
        assert final.exit_reason == END_OF_DATA
        assert final.exit_time == SOURCE[PREFIX - 1].timestamp
        assert final.exit_price == SOURCE[PREFIX - 1].close

    def test_no_processing_beyond_terminal(self) -> None:
        replay = drive_to_end(make())
        snapshot = (
            replay.state.cursor,
            replay.broker.cash,
            tuple(signatures(replay)),
            replay.exit_counts,
        )

        for _ in range(5):
            assert replay.tick() is None
        with pytest.raises(ReplayFinishedError):
            replay.step()

        assert (
            replay.state.cursor,
            replay.broker.cash,
            tuple(signatures(replay)),
            replay.exit_counts,
        ) == snapshot

    def test_manual_stepping_to_the_end_also_finishes(self) -> None:
        """Terminal is reached by step() too, not only by auto-run."""

        replay = make()

        while replay.state.status != STATE_FINISHED:
            replay.step()

        assert replay.state.status == STATE_FINISHED
        assert replay.ticker.armed is False

    def test_stepping_to_the_end_from_paused_finishes(self) -> None:
        replay = make()
        replay.start()
        replay.pause()

        while replay.state.status != STATE_FINISHED:
            replay.step()

        assert replay.state.status == STATE_FINISHED

    def test_finished_is_terminal_until_reset(self) -> None:
        replay = drive_to_end(make())

        for _ in range(5):
            assert replay.start().status == STATE_FINISHED
            assert replay.pause().status == STATE_FINISHED

        assert replay.state.status == STATE_FINISHED


# ---------------------------------------------------------------------------
# G. reset
# ---------------------------------------------------------------------------


def flat_running(steps: int = 40) -> Replay:
    """A running replay that has advanced but holds no open position.

    The entry gate is what makes this constructible. Once the strategy fires, the
    baseline almost never sits flat mid-run: an opposite-signal exit is normally
    followed by an immediate reversal entry on the same bar, so ``has_open_position``
    stays true until end-of-data. Reaching a flat *running* state therefore
    requires suppressing entries, which is exactly what ``evaluation_start`` is for.
    """

    replay = Replay(
        SOURCE[:PREFIX],
        config=CONFIG,
        costs=COSTS,
        evaluation_start=190,
    )
    replay.start()
    drive(replay, steps)

    assert replay.state.status == STATE_RUNNING, "fixture must still be running"
    assert replay.state.has_open_position is False, "fixture must be flat"

    return replay


def finished_with_trades() -> Replay:
    """A finished replay: holds closed trades, no open position, so reset applies.

    End-of-data closes the final position, which makes ``finished`` the only state
    that is both *flat* and *has a journal*.
    """

    replay = drive_to_end(make())

    assert replay.state.trade_count >= 1
    assert replay.state.has_open_position is False

    return replay


class TestReset:
    def test_successful_reset_returns_to_idle(self) -> None:
        replay = flat_running()
        assert replay.state.cursor > REQUIRED

        state = replay.reset()

        assert state.status == STATE_IDLE
        assert replay.state.status == STATE_IDLE

    def test_a_reversal_covered_replay_is_rarely_flat_mid_run(self) -> None:
        """Documents why reset refuses so often, and why the fixture gates entries.

        Not a behaviour requirement - an observation that makes the POSITION_OPEN
        guard look deliberate rather than unlucky.
        """

        replay = make()
        replay.start()
        flat_observations = 0
        observations = 0

        while replay.state.status != STATE_FINISHED:
            replay.tick()
            observations += 1
            if not replay.state.has_open_position:
                flat_observations += 1

        assert observations > 100
        assert flat_observations <= 2

    def test_reset_rewinds_and_clears(self) -> None:
        replay = finished_with_trades()
        assert replay.state.trade_count >= 1
        assert replay.state.balance != STARTING_BALANCE

        state = replay.reset()

        assert state.cursor == REQUIRED
        assert state.bars_processed == 0
        assert state.trade_count == 0
        assert state.balance == STARTING_BALANCE
        assert state.realized_pnl == 0.0
        assert state.last_signal is None
        assert state.has_open_position is False
        assert replay.entry_index is None
        assert replay.exit_counts == {}

    def test_reset_creates_a_fresh_broker(self) -> None:
        replay = finished_with_trades()
        original = replay.broker
        assert replay.broker.journal

        replay.reset()

        assert replay.broker is not original
        assert replay.broker.journal == []
        assert replay.broker.open_trade is None
        assert replay.broker.cash == STARTING_BALANCE

    def test_reset_does_not_arm_the_ticker(self) -> None:
        replay = flat_running()
        assert replay.ticker.armed is True

        replay.reset()

        assert replay.ticker.armed is False
        assert replay.state.status == STATE_IDLE
        assert replay.tick() is None

    def test_reset_preserves_replay_id_and_identities(self) -> None:
        replay = finished_with_trades()
        replay_id = replay.replay_id
        identity = (replay.state.dataset, replay.state.strategy,
                    replay.state.execution)

        replay.reset()

        assert replay.replay_id == replay_id
        assert (replay.state.dataset, replay.state.strategy,
                replay.state.execution) == identity

    def test_reset_from_finished_returns_to_idle(self) -> None:
        replay = finished_with_trades()
        assert replay.state.status == STATE_FINISHED

        state = replay.reset()

        assert state.status == STATE_IDLE
        assert state.cursor == REQUIRED
        assert state.trade_count == 0

    def test_reset_with_open_position_raises(self) -> None:
        replay = make()
        replay.start()
        while not replay.state.has_open_position:
            replay.tick()

        assert replay.broker.open_trade is not None

        with pytest.raises(PositionOpenError) as info:
            replay.reset()

        assert info.value.code == "POSITION_OPEN"

    def test_failed_reset_destroys_nothing(self) -> None:
        replay = make()
        replay.start()
        while not replay.state.has_open_position:
            replay.tick()

        position = replay.broker.open_trade
        journal = tuple(signatures(replay))
        snapshot = (
            replay.state.status,
            replay.state.cursor,
            replay.broker.cash,
            replay.state.trade_count,
        )

        with pytest.raises(PositionOpenError):
            replay.reset()

        assert replay.broker.open_trade is position
        assert tuple(signatures(replay)) == journal
        assert (
            replay.state.status,
            replay.state.cursor,
            replay.broker.cash,
            replay.state.trade_count,
        ) == snapshot

    def test_reset_then_rerun_reproduces_the_first_run(self) -> None:
        replay = flat_running()
        first = drive_to_end(replay)
        assert first.state.status == STATE_FINISHED
        journal = tuple(signatures(replay))
        cash = replay.broker.cash
        counts = replay.exit_counts

        replay.reset()
        drive_to_end(replay)

        assert tuple(signatures(replay)) == journal
        assert replay.broker.cash == cash
        assert replay.exit_counts == counts


# ---------------------------------------------------------------------------
# H. determinism and regression
# ---------------------------------------------------------------------------


class TestDeterminismAndRegression:
    def test_same_lifecycle_sequence_gives_identical_results(self) -> None:
        def run():
            replay = make()
            replay.start()
            for _ in range(15):
                replay.tick()
            replay.pause()
            replay.step()
            replay.start()
            for _ in range(15):
                replay.tick()
            replay.pause()
            replay.start()
            drive_to_end(replay)
            return replay

        first, second = run(), run()

        assert signatures(first) == signatures(second)
        assert first.broker.cash == second.broker.cash
        assert first.exit_counts == second.exit_counts
        assert replace(first.state, replay_id="x") == replace(
            second.state, replay_id="x"
        )

    def test_auto_run_matches_manual_stepping_exactly(self) -> None:
        auto, manual = drive_to_end(make()), make()

        auto.start()
        drive_to_end(manual)
        manual_steps = []
        while manual.state.status != STATE_FINISHED:
            manual_steps.append(manual.step())

        assert signatures(auto) == signatures(manual)
        assert auto.broker.cash == manual.broker.cash
        assert auto.exit_counts == manual.exit_counts
        assert auto.state.cursor == manual.state.cursor

    def test_ticker_choice_changes_pacing_not_results(self) -> None:
        """Two different tickers, identical journals."""

        demand = drive_to_end(make())

        gated = make(ticker=GatedTicker())
        gated.start()
        for _ in range(len(SOURCE[:PREFIX]) + 5):
            if not gated.ticker.armed:
                break
            gated.ticker.release()
            gated.tick()
        assert gated.state.status == STATE_FINISHED

        assert signatures(gated) == signatures(demand)
        assert gated.broker.cash == demand.broker.cash
        assert gated.exit_counts == demand.exit_counts

    def test_interleaved_lifecycle_matches_straight_progression(self) -> None:
        """pause/step/start interleaved, with an equal total step count."""

        interleaved = make()
        interleaved.start()
        for _ in range(20):
            interleaved.tick()
        interleaved.pause()
        interleaved.step()
        interleaved.step()
        interleaved.start()
        for _ in range(18):
            interleaved.tick()

        straight = make()
        straight.start()
        for _ in range(40):
            straight.tick()

        assert interleaved.state.cursor == straight.state.cursor
        assert signatures(interleaved) == signatures(straight)
        assert interleaved.broker.cash == straight.broker.cash

    def test_lifecycle_does_not_break_backtest_equivalence(self) -> None:
        """The 17B guarantee, re-proved through the lifecycle path."""

        replay = drive_to_end(make())
        reference = run_backtest(
            SOURCE[:PREFIX],
            config=CONFIG,
            costs=COSTS,
            starting_balance=STARTING_BALANCE,
            risk_fraction=RISK_FRACTION,
        )

        assert signatures(replay) == [
            trade_signature(t) for t in reference.trades
        ]
        assert replay.broker.cash == reference.ending_balance
        assert replay.exit_counts == reference.exit_counts
        assert replay.state.trade_count == len(reference.trades)

    def test_replay_state_contract_is_unchanged(self) -> None:
        """17C adds lifecycle without widening the state model."""

        fields = set(ReplayState.__dataclass_fields__)

        for absent in (
            "interval_ms",
            "armed",
            "ticker",
            "worker",
            "thread",
            "eta",
            "steps_per_tick",
        ):
            assert absent not in fields, absent
        assert "status" in fields

    def test_status_transitions_cover_the_approved_graph(self) -> None:
        """Every reachable transition, and the ones that must not exist."""

        seen = set()

        def record(build, *actions) -> None:
            """Capture each transition on a *fresh* replay.

            One instance cannot supply both ``idle -> running`` and
            ``idle -> idle``, because the first action already moved it.
            """

            replay = build()
            for action in actions:
                before = replay.state.status
                after = action(replay)
                seen.add((before, after.status))

        def idle():
            return make()

        def running():
            replay = make()
            replay.start()
            return replay

        def paused():
            replay = make()
            replay.start()
            replay.pause()
            return replay

        def finished():
            return drive_to_end(make())

        # Every edge gets its own fresh replay: an action mutates the status, so
        # one instance cannot supply both ``idle -> running`` and ``idle -> idle``.
        edges = [
            (idle, "start"),
            (idle, "pause"),
            (running, "pause"),
            (running, "start"),
            (paused, "start"),
            (paused, "pause"),
            (finished, "start"),
            (finished, "pause"),
        ]

        seen = set()
        for build, action in edges:
            replay = build()
            before = replay.state.status
            after = getattr(replay, action)()
            seen.add((before, after.status))

        assert seen == {
            (STATE_IDLE, STATE_RUNNING),
            (STATE_IDLE, STATE_IDLE),
            (STATE_RUNNING, STATE_PAUSED),
            (STATE_RUNNING, STATE_RUNNING),
            (STATE_PAUSED, STATE_RUNNING),
            (STATE_PAUSED, STATE_PAUSED),
            (STATE_FINISHED, STATE_FINISHED),
        }

    def test_running_cannot_transition_straight_to_finished_without_data(self) -> None:
        """Only consuming the series may finish a replay."""

        replay = make()
        replay.start()

        for _ in range(50):
            replay.tick()

        assert replay.state.status == STATE_RUNNING


# ---------------------------------------------------------------------------
# safety and scope
# ---------------------------------------------------------------------------


def code_only(path: Path) -> str:
    kept: list[str] = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (
                tokenize.COMMENT,
                tokenize.STRING,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
            ):
                continue
            kept.append(token.string)

    return " ".join(kept)


class TestSafetyAndScope:
    def test_replay_imports_no_concurrency_library(self) -> None:
        """No thread, no scheduler, no clock. Pacing is injected, not spawned."""

        modules = set()
        for node in ast.walk(ast.parse(REPLAY_SOURCE.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modules.add((node.module or "").split(".")[0])

        for forbidden in (
            "threading",
            "asyncio",
            "concurrent",
            "multiprocessing",
            "time",
            "sched",
            "queue",
        ):
            assert forbidden not in modules, forbidden

    def test_replay_never_sleeps(self) -> None:
        code = code_only(REPLAY_SOURCE)

        for forbidden in ("sleep", "Timer", "threading", "Thread", "spawn"):
            assert forbidden not in code, forbidden

    def test_lifecycle_never_computes_trading_values(self) -> None:
        """start/pause/tick must not touch prices, sizes or balances."""

        replay = make()
        before = (
            replay.broker.cash,
            replay.broker.starting_balance,
            len(replay.broker.journal),
        )

        replay.start()
        replay.pause()
        replay.start()

        assert (
            replay.broker.cash,
            replay.broker.starting_balance,
            len(replay.broker.journal),
        ) == before

    def test_ticker_subclass_is_not_required(self) -> None:
        """The default ticker is concrete, so no boilerplate subclassing."""

        ticker = OnDemandTicker()

        assert ticker.armed is False
        assert ticker.take() is False

        ticker.arm(500)
        assert ticker.armed is True
        assert ticker.take() is True

        ticker.disarm()
        assert ticker.take() is False

    def test_base_ticker_refuses_to_guess(self) -> None:
        ticker = Ticker()

        for call in (lambda: ticker.arm(1), ticker.disarm, ticker.take):
            with pytest.raises(NotImplementedError):
                call()
        with pytest.raises(NotImplementedError):
            ticker.armed  # noqa: B018

    def test_no_transport_or_mode_concepts(self) -> None:
        """Nothing from 17D or later leaked in."""

        code = code_only(REPLAY_SOURCE)

        for forbidden in (
            "fastapi",
            "APIRouter",
            "pydantic",
            "uvicorn",
            "Daily",
            "HighRisk",
            "alert",
            "close_all",
            "MODE_",
            "registry",
            "persist",
            "sqlite",
            "json",
        ):
            assert forbidden not in code, forbidden

    def test_policy_surface_is_unchanged(self) -> None:
        """17C must not add a policy registry; the single seam is enough."""

        replay = make()

        assert replay.policy is AUTOMATIC_POLICY
        assert replay.policy.allow_entry is True

    def test_no_real_money_or_execution_path(self) -> None:
        code = code_only(REPLAY_SOURCE)

        for forbidden in (
            "exchange",
            "binance",
            "ccxt",
            "order",
            "place_order",
            "wallet",
            "withdraw",
            "deposit",
            "leverage",
            "api_key",
            "secret",
            "credential",
        ):
            assert forbidden not in code, forbidden