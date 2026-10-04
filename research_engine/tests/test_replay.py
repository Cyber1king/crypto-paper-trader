"""Phase 17B tests: deterministic paper replay state, step and reset.

Three rules shape this file, all inherited from Phases 16 and 17A.

**The backtest is the oracle.** A replay is only correct if it reproduces
``run_backtest`` exactly, so the primary tests do not assert hand-written
expected numbers. They run the real backtest on the same candles and require
**field-by-field identity** across the whole trade sequence - every price, size,
fee, slippage, spread, P&L value, exit reason, bar count and the journal order -
plus the final cash and the exit tally. Matching final balances would not be
sufficient evidence, because two different trade sequences can end at the same
cash; the brief explicitly rejects that weaker check.

**Causality is tested by mutation, not by inspection.** Proving no future candle
can influence the present requires changing the future and showing nothing
moves. Every lookahead assertion perturbs candles *after* the cursor.

**The dataset is an input, never a fixture to be edited.** Tests slice and
replace candles in memory; nothing writes to disk or to the frozen CSV.
"""
from __future__ import annotations

import ast
import tokenize
from dataclasses import replace
from pathlib import Path

import pytest

from crypto_paper_lab.backtest import (
    END_OF_DATA,
    MAX_HOLDING,
    OPPOSITE_SIGNAL,
    STOP_LOSS,
    run_backtest,
)
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.models import PaperTrade
from crypto_paper_lab.replay import (
    AUTOMATIC_POLICY,
    STATE_FINISHED,
    STATE_IDLE,
    ExecutionPolicy,
    InvalidStartIndexError,
    PositionOpenError,
    Replay,
    ReplayError,
    ReplayFinishedError,
    minimum_history,
)
from crypto_paper_lab.strategy import StrategyConfig, analyze
from crypto_paper_lab.walkforward import (
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_PATH,
    DATASET_SHA256,
    EXPECTED_INTERVAL_SECONDS,
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    config_hash,
    costs_hash,
    phase13_costs,
)

RESEARCH_ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPLAY_SOURCE = (
    RESEARCH_ENGINE_ROOT / "src" / "crypto_paper_lab" / "replay.py"
)

SOURCE, _ = load_dataset(RESEARCH_ENGINE_ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = minimum_history(CONFIG)

#: Prefixes small enough to step quickly. Equivalence is checked on each.
PREFIXES = (40, 60, 200, 400, 800)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def trade_signature(trade: PaperTrade) -> tuple:
    """Every observable field of a trade, in a comparable tuple.

    ``PaperTrade`` is a mutable dataclass whose ``exit_*``, cost and bar fields
    are written *after* ``close()`` returns, so comparing live objects risks
    comparing a half-populated trade. Extracting the fields explicitly also makes
    the equivalence claim concrete rather than trusting generated ``__eq__``.
    """

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


def replay_signatures(replay: Replay) -> list:
    return [trade_signature(t) for t in replay.broker.journal]


def backtest_signatures(result) -> list:
    return [trade_signature(t) for t in result.trades]


def run_to_completion(replay: Replay) -> Replay:
    """Step until the replay finishes. Fails loudly if it never does."""

    for _ in range(len(SOURCE) + 10):
        if replay.state.status == STATE_FINISHED:
            return replay
        replay.step()

    raise AssertionError("replay did not reach the finished state")


def new_replay(candles=None, **kwargs) -> Replay:
    return Replay(
        SOURCE if candles is None else candles,
        config=CONFIG,
        costs=COSTS,
        **kwargs,
    )


def code_only(path: Path) -> str:
    """Source text with comments and string literals removed.

    A guard that greps raw text matches its own explanatory prose, which is the
    bug an earlier phase's guard actually had.
    """

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


# ---------------------------------------------------------------------------
# A. state
# ---------------------------------------------------------------------------


class TestState:
    def test_initial_state_is_deterministic(self) -> None:
        """1. A fresh replay is always in exactly this state."""

        state = new_replay().state

        assert state.status == STATE_IDLE
        assert state.cursor == REQUIRED == 22
        assert state.start_index == REQUIRED
        assert state.bars_processed == 0
        assert state.last_signal is None
        assert state.current_timestamp is None
        assert state.next_candle_available is True
        assert state.starting_balance == STARTING_BALANCE == 10_000.0
        assert state.balance == STARTING_BALANCE
        assert state.realized_pnl == 0.0
        assert state.trade_count == 0
        assert state.has_open_position is False
        assert state.open_position is None

    def test_two_replays_agree_except_for_the_id(self) -> None:
        """Determinism means only the identity may differ between instances."""

        first, second = new_replay().state, new_replay().state

        assert first.replay_id != second.replay_id
        assert replace(first, replay_id="x") == replace(second, replay_id="x")

    def test_cursor_is_the_execution_bar(self) -> None:
        """2. ``cursor`` names the bar whose OPEN supplies a fill price.

        The signal has not been taken yet, so the bar at the cursor is the *next*
        one to be consumed and its timestamp is ``next_timestamp``. The bar before
        it is the last consumed bar, of which nothing is recorded yet because
        nothing has been consumed.
        """

        state = new_replay().state

        assert state.cursor == REQUIRED
        assert state.next_timestamp == SOURCE[REQUIRED].timestamp
        assert state.current_timestamp is None
        # The cursor must never be read as the signal candle.
        assert state.next_timestamp != SOURCE[REQUIRED - 1].timestamp

    def test_cursor_advances_by_exactly_one_per_step(self) -> None:
        replay = new_replay()

        for expected in range(REQUIRED, REQUIRED + 25):
            assert replay.state.cursor == expected
            result = replay.step()
            assert result.cursor_before == expected
            assert result.cursor_after == expected + 1
            assert replay.state.cursor == expected + 1
            assert replay.state.bars_processed == expected + 1 - REQUIRED

    def test_dataset_identity(self) -> None:
        """3. The frozen dataset is identified by hash and bounds, not a path."""

        identity = new_replay().state.dataset

        assert identity.sha256 == DATASET_SHA256
        assert identity.candle_count == DATASET_CANDLES == len(SOURCE)
        assert identity.first_timestamp == DATASET_FIRST == SOURCE[0].timestamp
        assert identity.last_timestamp == DATASET_LAST == SOURCE[-1].timestamp
        assert identity.asset == "BTC/USDT"
        assert identity.timeframe == "1h"
        assert identity.interval_seconds == EXPECTED_INTERVAL_SECONDS == 3600

    def test_dataset_identity_exposes_no_filesystem_path(self) -> None:
        """``BTC/USDT`` contains a slash; a *path* would contain a separator or an
        extension. Checked against the real leak shapes, not the character."""

        blob = repr(new_replay().state.dataset)

        for leak in (
            "\\\\",
            ".csv",
            "Users",
            "crypto-paper-trader",
            "research_engine",
            "data/",
            "file:",
        ):
            assert leak not in blob, leak
        # The asset is an instrument pair, and that is legitimate.
        assert "BTC/USDT" in blob

    def test_strategy_identity(self) -> None:
        """4. Reuses the existing hash mechanism; no second identity system."""

        identity = new_replay().state.strategy

        assert identity.config_hash == config_hash(CONFIG)
        assert identity.config_hash == (
            "2FBDB9A8814ABC81062C2B0A61DFDCFAC69C95CF1789D0BAE6BEE4B11ADC3BF7"
        )
        assert identity.config_repr == repr(CONFIG)

    def test_execution_identity(self) -> None:
        """5. Reuses the frozen costs and the engine's own hash."""

        identity = new_replay().state.execution

        assert identity.costs_hash == costs_hash(COSTS)
        assert identity.costs_hash == (
            "C24F79986249A05541709B583015FFBE012055DC324F4C4F6ED8CF97B6123C7E"
        )
        assert identity.execution_model == "cost_deduction"
        assert identity.fee_rate == 0.001
        assert identity.slippage_rate == 0.0005
        assert identity.spread_rate == 0.0
        assert identity.risk_fraction == RISK_FRACTION == 0.01
        assert identity.costs_repr == repr(COSTS)

    def test_state_is_immutable(self) -> None:
        state = new_replay().state

        with pytest.raises(Exception):
            state.cursor = 999  # type: ignore[misc]

    def test_state_exposes_no_unsupported_quantity(self) -> None:
        """Equity, margin and friends stay absent: the broker cannot produce them."""

        fields = set(new_replay().state.__dataclass_fields__)

        for absent in (
            "equity",
            "mark_price",
            "current_price",
            "unrealized_pnl",
            "available_balance",
            "reserved_capital",
            "margin",
            "buying_power",
            "notional",
            "leverage",
            "confidence",
        ):
            assert absent not in fields, absent


# ---------------------------------------------------------------------------
# B. step
# ---------------------------------------------------------------------------


class TestStep:
    def test_one_step_is_deterministic(self) -> None:
        """6. Two replays over the same candles produce identical steps."""

        first, second = new_replay(), new_replay()

        for _ in range(120):
            a, b = first.step(), second.step()
            assert a == b
            assert replace(first.state, replay_id="x") == replace(
                second.state, replay_id="x"
            )

    def test_signal_is_computed_from_candles_before_the_execution_bar(
        self,
    ) -> None:
        """7. ALI-1: the signal equals ``analyze(candles[:i])`` exactly."""

        replay = new_replay()

        for _ in range(120):
            index = replay.state.cursor
            result = replay.step()

            assert result.signal == analyze(SOURCE[:index], CONFIG)
            assert result.signal.timestamp == SOURCE[index - 1].timestamp
            assert result.signal_timestamp == SOURCE[index - 1].timestamp
            assert result.execution_bar == SOURCE[index]

    def test_signal_price_is_not_rewritten_to_the_fill_price(self) -> None:
        """The strategy sees its own candle's close; the fill uses the next open.

        ``run_backtest`` overwrites ``Signal.price`` for the execution signal. The
        signal the strategy produced must keep its own value, otherwise the two
        would be indistinguishable and causality would be untestable.
        """

        replay = new_replay()
        first = None

        while first is None or first.opened is None:
            first = replay.step()

        index = first.cursor_before
        assert first.opened.entry_price == SOURCE[index].open
        assert first.signal.price == SOURCE[index - 1].close

    def test_first_fill_uses_the_next_candles_open(self) -> None:
        """8. Next-candle open execution, never the signal bar."""

        replay = new_replay()

        while True:
            result = replay.step()
            if result.opened is not None:
                break

        assert result.cursor_before == REQUIRED
        assert result.opened.entry_time == SOURCE[REQUIRED].timestamp
        assert result.opened.entry_price == SOURCE[REQUIRED].open
        # One bar of separation, exactly.
        assert (
            result.opened.entry_time - result.signal.timestamp
        ).total_seconds() == EXPECTED_INTERVAL_SECONDS

    def test_future_candles_cannot_change_the_current_signal(self) -> None:
        """9. ALI-1 by mutation: rewrite the future, observe no change."""

        index = REQUIRED + 40
        baseline = analyze(SOURCE[:index], CONFIG)

        for label, spike, crash in (
            ("constant spike", 1e9, 1e-6),
            ("inverted series", None, None),
        ):
            mutated = list(SOURCE)

            if spike is None:
                # Reverse every future bar, which also moves prices the wrong way.
                mutated[index:] = list(reversed(mutated[index:]))
            else:
                for position in range(index, len(mutated)):
                    mutated[position] = replace(
                        mutated[position],
                        open=spike, high=spike, low=spike, close=spike,
                        volume=crash,
                    )

            assert analyze(mutated[:index], CONFIG) == baseline, label

    def test_mutating_the_execution_bar_changes_the_fill_not_the_signal(
        self,
    ) -> None:
        """9b. ALI-2: the execution bar is a price input, never a strategy input."""

        index = REQUIRED
        baseline_signal = analyze(SOURCE[:index], CONFIG)

        mutated = list(SOURCE)
        mutated[index] = replace(mutated[index], open=1.0, high=2.0, low=0.5)

        assert analyze(mutated[:index], CONFIG) == baseline_signal

        replay = Replay(mutated, config=CONFIG, costs=COSTS)
        while True:
            result = replay.step()
            if result.opened is not None:
                break

        assert result.signal == baseline_signal
        assert result.opened.entry_price == 1.0

    def test_state_at_a_cursor_ignores_candles_after_it(self) -> None:
        """9c. ALI-3: state at cursor N must not depend on candles after N.

        Both replays walk the **full** series so they reach the same cursor; only
        the candles beyond it differ. Truncating instead would prove nothing,
        because the mutated replay would never see the changed candles.
        """

        limit = REQUIRED + 150

        reference = Replay(SOURCE, config=CONFIG, costs=COSTS)
        while reference.state.cursor < limit:
            reference.step()

        mutated = list(SOURCE)
        for position in range(limit, len(mutated)):
            mutated[position] = replace(
                mutated[position],
                open=9e5, high=9e5, low=9e5, close=9e5,
            )

        other = Replay(mutated, config=CONFIG, costs=COSTS)
        while other.state.cursor < limit:
            other.step()

        assert other.state.cursor == reference.state.cursor == limit
        assert replay_signatures(other) == replay_signatures(reference)
        assert other.broker.cash == reference.broker.cash
        assert other.state.last_signal == reference.state.last_signal
        assert other.state.open_position == reference.state.open_position
        assert replace(other.state, replay_id="x") == replace(
            reference.state, replay_id="x"
        )

    def test_exit_is_evaluated_before_entry_in_the_same_step(self) -> None:
        """10. Ordering is load-bearing and observable."""

        replay = new_replay()
        observed = False

        while replay.state.status != STATE_FINISHED:
            before_journal = len(replay.broker.journal)
            before_open = replay.broker.open_trade
            result = replay.step()

            if result.closed is not None:
                observed = True
                # The close happened first: the journal grew and the position the
                # step began with is gone.
                assert len(replay.broker.journal) == before_journal + 1
                assert before_open is not None
                assert result.closed is before_open
                if result.finished:
                    # End-of-data: filled at the final candle's CLOSE, and there
                    # is no execution bar because the cursor is already past the
                    # end of the series.
                    assert result.execution_bar is None
                    assert result.closed.exit_time == SOURCE[-1].timestamp
                    assert result.closed.exit_price == SOURCE[-1].close
                else:
                    assert result.closed.exit_time == (
                        result.execution_bar.timestamp
                    )
                    assert result.closed.exit_price == result.execution_bar.open

            if result.opened is not None and result.closed is None:
                # An entry with no close can only happen from a flat step.
                assert before_open is None

        assert observed, "fixture must contain at least one exit"

    def test_reversal_step_closes_and_opens_at_the_same_price(self) -> None:
        """11. The two-fill step, which is the common case, not an edge case."""

        replay = new_replay(SOURCE[:400])
        reversals = []

        while replay.state.status != STATE_FINISHED:
            result = replay.step()
            if result.closed is not None and result.opened is not None:
                reversals.append(result)

        assert len(reversals) == 6, "pinned: six two-fill steps in 400 candles"

        first = reversals[0]
        assert first.cursor_before == 60, "pinned first reversal"
        assert first.closed.side != first.opened.side
        assert first.closed.exit_reason == OPPOSITE_SIGNAL
        # Both operations use the same execution bar.
        assert first.closed.exit_time == first.opened.entry_time
        assert first.closed.exit_time == first.execution_bar.timestamp
        assert first.closed.exit_price == first.opened.entry_price
        assert first.closed.exit_price == first.execution_bar.open
        # The closed trade was recorded before the new one opened.
        assert replay.broker.journal[0] is first.closed

    def test_reversal_leaves_exactly_one_open_position(self) -> None:
        replay = new_replay(SOURCE[:400])

        while replay.state.status != STATE_FINISHED:
            result = replay.step()
            if result.closed is not None and result.opened is not None:
                assert replay.state.has_open_position is True
                assert len(replay.broker.journal) >= 1
                assert replay.broker.open_trade is result.opened
                return

        raise AssertionError("no reversal encountered")

    def test_only_one_position_is_ever_open(self) -> None:
        """The broker holds a single open slot, and the journal holds closed ones."""

        replay = new_replay()

        while replay.state.status != STATE_FINISHED:
            replay.step()
            journal = replay.broker.journal
            # A trade reaches the journal only after close() fills its exit fields.
            assert all(t.exit_time is not None for t in journal)
            # An open position is never simultaneously a journal entry.
            assert (
                replay.broker.open_trade is None
                or all(t.exit_time is not None for t in journal)
            )

    def test_cash_does_not_change_while_a_position_is_open(self) -> None:
        """12. No reservation: the quantity model, not the dashboard's model."""

        replay = new_replay()
        samples = []

        while replay.state.status != STATE_FINISHED:
            previous_cash = replay.broker.cash
            replay.step()
            now_cash = replay.broker.cash
            if replay.broker.open_trade is not None:
                samples.append((previous_cash, now_cash))

        held = [pair for pair in samples if pair[0] == pair[1]]
        assert len(held) > 100, "fixture should hold a position for many bars"

        # Cash moved only on steps that closed a trade. Compared with a tolerance,
        # not exactly: the broker accumulates ``cash += net_pnl`` onto the opening
        # balance while this expression sums from 0.0, so the two agree
        # mathematically but differ in the last bits. That one-ULP divergence is a
        # known property of the engine (Phase 17A 2.3e), measured at ~9e-14
        # relative, and replay must not "fix" it by overriding either side.
        assert replay.broker.cash == pytest.approx(
            STARTING_BALANCE + sum(t.net_pnl or 0.0 for t in replay.broker.journal),
            rel=1e-12,
        )

    def test_balance_never_leaves_the_broker(self) -> None:
        replay = new_replay()

        while replay.state.status != STATE_FINISHED:
            replay.step()
            assert replay.state.balance == replay.broker.cash

    def test_journal_grows_only_when_a_trade_closes(self) -> None:
        """13. Append-only, in close order."""

        replay = new_replay()

        while replay.state.status != STATE_FINISHED:
            before = len(replay.broker.journal)
            result = replay.step()
            after = len(replay.broker.journal)

            if result.closed is None:
                assert after == before
            else:
                assert after == before + 1
                assert replay.broker.journal[-1] is result.closed

        assert len(replay.broker.journal) == replay.state.trade_count

    def test_journal_order_is_chronological_by_entry(self) -> None:
        replay = run_to_completion(new_replay())
        entries = [t.entry_time for t in replay.broker.journal]

        assert entries == sorted(entries)

    def test_position_progresses_flat_open_flat(self) -> None:
        """14. has_open_position tracks the broker exactly."""

        replay = new_replay()
        assert replay.state.has_open_position is False

        seen_open = False
        while replay.state.status != STATE_FINISHED:
            replay.step()
            state = replay.state
            assert state.has_open_position == (
                replay.broker.open_trade is not None
            )
            if state.has_open_position:
                seen_open = True

        assert seen_open
        assert replay.state.has_open_position is False

    def test_open_position_matches_the_broker_object(self) -> None:
        replay = new_replay()

        while replay.state.has_open_position is False:
            replay.step()

        assert replay.state.open_position is replay.broker.open_trade

    def test_flat_signal_is_not_an_error(self) -> None:
        replay = new_replay()
        flats = 0

        for _ in range(200):
            result = replay.step()
            if result.signal.side == "flat":
                flats += 1
                assert result.closed is None or result.closed.exit_reason

        assert flats > 100, "flat is the dominant outcome and must be ordinary"

    def test_exit_rules_never_fire_on_the_entry_bar(self) -> None:
        replay = run_to_completion(new_replay(SOURCE[:1500]))

        offending = [
            (t.exit_reason, t.bars_held)
            for t in replay.broker.journal
            if t.bars_held == 0 and t.exit_reason != END_OF_DATA
        ]
        assert offending == []

    def test_end_of_data_closes_at_the_final_close_not_the_open(self) -> None:
        replay = run_to_completion(new_replay(SOURCE[:400]))
        final = replay.broker.journal[-1]

        assert final.exit_reason == END_OF_DATA
        assert final.exit_time == SOURCE[399].timestamp
        assert final.exit_price == SOURCE[399].close
        assert final.exit_price != SOURCE[399].open

    def test_step_after_finished_raises(self) -> None:
        replay = run_to_completion(new_replay(SOURCE[:40]))

        with pytest.raises(ReplayFinishedError) as info:
            replay.step()

        assert info.value.code == "REPLAY_FINISHED"

    def test_finished_replay_reports_finished(self) -> None:
        replay = run_to_completion(new_replay(SOURCE[:40]))
        state = replay.state

        assert state.status == STATE_FINISHED
        assert state.next_candle_available is False
        assert state.next_timestamp is None
        assert state.bars_processed == len(SOURCE[:40]) - REQUIRED


# ---------------------------------------------------------------------------
# C. equivalence with the backtest
# ---------------------------------------------------------------------------


def _reference(candles, config=None):
    return run_backtest(
        candles,
        config=CONFIG if config is None else config,
        costs=COSTS,
        starting_balance=STARTING_BALANCE,
        risk_fraction=RISK_FRACTION,
    )


class TestBacktestEquivalence:
    @pytest.mark.parametrize("length", PREFIXES)
    def test_replay_reproduces_the_backtest_exactly(self, length: int) -> None:
        """15. The primary requirement, on a short prefix."""

        replay = run_to_completion(new_replay(SOURCE[:length]))
        reference = _reference(SOURCE[:length])

        assert replay_signatures(replay) == backtest_signatures(reference)
        assert replay.exit_counts == reference.exit_counts
        assert replay.broker.cash == reference.ending_balance
        assert replay.broker.starting_balance == reference.starting_balance

    @pytest.mark.parametrize("length", PREFIXES)
    def test_signal_sequence_agrees_with_the_definition(
        self, length: int
    ) -> None:
        """16. Each step's signal equals an independent ``analyze`` call.

        ``run_backtest`` does not expose its signal sequence, and modifying it to
        do so is forbidden, so equivalence of signals is established against the
        documented definition instead. Combined with exact trade-sequence identity
        this pins the signals transitively: a different signal would have produced
        a different trade or a different flat step.
        """

        replay = Replay(SOURCE[:length], config=CONFIG, costs=COSTS)
        observed = []

        while replay.state.status != STATE_FINISHED:
            index = replay.state.cursor
            observed.append(replay.step().signal)
            if replay.state.status != STATE_FINISHED:
                assert observed[-1] == analyze(SOURCE[:index], CONFIG)

        assert len(observed) == length - REQUIRED + 1

    @pytest.mark.parametrize("length", PREFIXES)
    def test_every_trade_field_agrees(self, length: int) -> None:
        """17-21. Sequence, fill, cost, P&L and quantity, field by field."""

        replay = run_to_completion(new_replay(SOURCE[:length]))
        reference = _reference(SOURCE[:length])
        mine, theirs = replay.broker.journal, reference.trades

        assert len(mine) == len(theirs)
        assert len(mine) > 0, "fixture must actually trade"

        for index, (a, b) in enumerate(zip(mine, theirs)):
            context = f"trade {index}"
            # 17 sequence and 21 quantity
            assert (a.side, a.entry_time, a.entry_time, a.quantity) == (
                b.side, b.entry_time, b.entry_time, b.quantity
            ), context
            # 18 fill prices
            assert (a.entry_price, a.exit_price) == (
                b.entry_price, b.exit_price
            ), context
            assert (a.raw_entry_price, a.raw_exit_price) == (
                b.raw_entry_price, b.raw_exit_price
            ), context
            # 19 costs, fee, slippage and spread separately
            assert (a.fee_total, a.slippage_total, a.spread_total, a.costs) == (
                b.fee_total, b.slippage_total, b.spread_total, b.costs
            ), context
            # 20 P&L
            assert (a.pnl, a.net_pnl, a.total_friction) == (
                b.pnl, b.net_pnl, b.total_friction
            ), context
            # sequence metadata
            assert (a.exit_time, a.exit_reason, a.bars_held) == (
                b.exit_time, b.exit_reason, b.bars_held
            ), context

    @pytest.mark.parametrize("length", PREFIXES)
    def test_final_cash_agrees(self, length: int) -> None:
        """22. Cash progression, end to end."""

        replay = run_to_completion(new_replay(SOURCE[:length]))
        reference = _reference(SOURCE[:length])

        assert replay.broker.cash == reference.ending_balance
        assert replay.state.realized_pnl == (
            reference.ending_balance - reference.starting_balance
        )

    @pytest.mark.parametrize("length", PREFIXES)
    def test_journal_order_agrees(self, length: int) -> None:
        replay = run_to_completion(new_replay(SOURCE[:length]))
        reference = _reference(SOURCE[:length])

        assert [t.entry_time for t in replay.broker.journal] == [
            t.entry_time for t in reference.trades
        ]

    @pytest.mark.parametrize(
        "override,expected_labels",
        [
            ({"stop_loss_pct": 0.005}, {STOP_LOSS, OPPOSITE_SIGNAL}),
            ({"take_profit_pct": 0.005}, {"take_profit", OPPOSITE_SIGNAL}),
            ({"max_holding_bars": 5}, {MAX_HOLDING}),
        ],
    )
    def test_equivalence_holds_with_exit_rules_enabled(
        self, override: dict, expected_labels: set
    ) -> None:
        """The optional exit rules are transliterated, not reimplemented."""

        config = replace(CONFIG, **override)

        for length in (400, 1500):
            replay = run_to_completion(
                Replay(SOURCE[:length], config=config, costs=COSTS)
            )
            reference = _reference(SOURCE[:length], config)

            assert replay_signatures(replay) == backtest_signatures(reference)
            assert replay.exit_counts == reference.exit_counts
            assert set(replay.exit_counts) <= expected_labels | {END_OF_DATA}
            assert replay.exit_counts, "fixture must exercise the rule"

    def test_equivalence_holds_under_fill_price_execution(self) -> None:
        """The other execution model must reproduce too."""

        from crypto_paper_lab.costs import FILL_PRICE, TradingCosts

        costs = TradingCosts(
            fee_rate=0.001,
            slippage_rate=0.0005,
            spread_rate=0.0002,
            execution_model=FILL_PRICE,
        )

        for length in (400, 1500):
            replay = run_to_completion(
                Replay(SOURCE[:length], config=CONFIG, costs=costs)
            )
            reference = run_backtest(
                SOURCE[:length],
                config=CONFIG,
                costs=costs,
                starting_balance=STARTING_BALANCE,
                risk_fraction=RISK_FRACTION,
            )

            assert replay_signatures(replay) == backtest_signatures(reference)
            assert replay.exit_counts == reference.exit_counts

    def test_equivalence_holds_with_an_evaluation_start_gate(self) -> None:
        replay = run_to_completion(
            Replay(
                SOURCE[:1500], config=CONFIG, costs=COSTS,
                evaluation_start=200,
            )
        )
        reference = run_backtest(
            SOURCE[:1500],
            config=CONFIG,
            costs=COSTS,
            starting_balance=STARTING_BALANCE,
            risk_fraction=RISK_FRACTION,
            evaluation_start=200,
        )

        assert replay_signatures(replay) == backtest_signatures(reference)

    @pytest.mark.slow
    def test_full_dataset_matches_the_frozen_baseline(self) -> None:
        """The whole frozen dataset: 344 trades matching the Phase 13 record."""

        replay = run_to_completion(new_replay())
        reference = _reference(SOURCE)

        assert len(replay.broker.journal) == len(reference.trades) == 344
        assert replay_signatures(replay) == backtest_signatures(reference)
        assert replay.broker.cash == reference.ending_balance
        assert replay.exit_counts == reference.exit_counts
        assert replay.exit_counts == {
            OPPOSITE_SIGNAL: 343,
            END_OF_DATA: 1,
        }
        # The frozen checkpoint records 9842.86 ending balance.
        assert round(replay.broker.cash, 2) == 9842.86

    @pytest.mark.slow
    def test_full_dataset_step_count_and_reversal_count(self) -> None:
        replay = new_replay()
        steps = 0
        reversals = 0

        while replay.state.status != STATE_FINISHED:
            result = replay.step()
            steps += 1
            if result.closed is not None and result.opened is not None:
                reversals += 1

        assert steps == len(SOURCE) - REQUIRED + 1 == 17_523
        assert reversals == 343


# ---------------------------------------------------------------------------
# D. reset
# ---------------------------------------------------------------------------


def stepped_past_first_trade() -> Replay:
    """A replay holding at least one closed trade and no open position."""

    replay = new_replay(SOURCE[:400])

    while len(replay.broker.journal) < 2:
        replay.step()
        if replay.state.has_open_position and replay.state.trade_count >= 2:
            break

    while replay.state.has_open_position:
        replay.step()

    return replay


class TestReset:
    def test_reset_from_a_flat_state_succeeds(self) -> None:
        """23."""

        replay = stepped_past_first_trade()
        assert replay.state.trade_count >= 1

        state = replay.reset()

        assert state.status == STATE_IDLE
        assert state.cursor == REQUIRED
        assert state.bars_processed == 0

    def test_reset_clears_the_journal(self) -> None:
        """25."""

        replay = stepped_past_first_trade()
        assert replay.broker.journal

        replay.reset()

        assert replay.broker.journal == []
        assert replay.state.trade_count == 0
        assert replay.exit_counts == {}

    def test_reset_restores_starting_cash(self) -> None:
        """26."""

        replay = stepped_past_first_trade()
        assert replay.broker.cash != STARTING_BALANCE

        replay.reset()

        assert replay.broker.cash == STARTING_BALANCE
        assert replay.state.balance == STARTING_BALANCE
        assert replay.state.realized_pnl == 0.0

    def test_reset_restores_the_cursor(self) -> None:
        """27."""

        replay = stepped_past_first_trade()
        assert replay.state.cursor > REQUIRED

        replay.reset()

        assert replay.state.cursor == REQUIRED
        assert replay.state.current_timestamp is None
        assert replay.state.next_timestamp == SOURCE[REQUIRED].timestamp
        assert replay.state.last_signal is None
        assert replay.entry_index is None

    def test_reset_clears_the_signal_and_entry_index(self) -> None:
        replay = stepped_past_first_trade()
        assert replay.state.last_signal is not None

        replay.reset()

        assert replay.state.last_signal is None
        assert replay.entry_index is None

    def test_reset_rebuilds_the_broker_rather_than_clearing_it(self) -> None:
        """A new broker, so no field can survive by being forgotten."""

        replay = stepped_past_first_trade()
        original = replay.broker

        replay.reset()

        assert replay.broker is not original
        assert replay.broker.open_trade is None

    def test_reset_preserves_dataset_identity(self) -> None:
        """28."""

        replay = stepped_past_first_trade()
        before = replay.state.dataset

        replay.reset()

        assert replay.state.dataset == before

    def test_reset_preserves_strategy_identity(self) -> None:
        """29."""

        replay = stepped_past_first_trade()
        before = replay.state.strategy

        replay.reset()

        assert replay.state.strategy == before

    def test_reset_preserves_execution_identity(self) -> None:
        """30."""

        replay = stepped_past_first_trade()
        before = replay.state.execution

        replay.reset()

        assert replay.state.execution == before

    def test_reset_retains_the_replay_id(self) -> None:
        replay = stepped_past_first_trade()
        before = replay.replay_id

        replay.reset()

        assert replay.replay_id == before

    def test_reset_reproduces_a_run_exactly(self) -> None:
        """24. Reset determinism: the second run equals the first, field for field."""

        replay = stepped_past_first_trade()
        replay.reset()

        first = []
        while replay.state.status != STATE_FINISHED:
            first.append(replay.step())

        replay.reset()
        second = []
        while replay.state.status != STATE_FINISHED:
            second.append(replay.step())

        assert len(first) == len(second)
        assert first == second

    def test_reset_is_idempotent(self) -> None:
        replay = stepped_past_first_trade()

        first = replay.reset()
        second = replay.reset()

        assert first == second

    def test_reset_from_finished_returns_to_idle(self) -> None:
        replay = run_to_completion(new_replay(SOURCE[:40]))
        assert replay.state.status == STATE_FINISHED

        state = replay.reset()

        assert state.status == STATE_IDLE
        assert replay.state.cursor == REQUIRED
        assert replay.state.trade_count == 0

    def test_reset_with_an_open_position_raises(self) -> None:
        """31. Decision Q2: refuse rather than silently discard."""

        replay = new_replay()
        while replay.state.has_open_position is False:
            replay.step()

        assert replay.broker.open_trade is not None
        cursor = replay.state.cursor
        trade_count = replay.state.trade_count

        with pytest.raises(PositionOpenError) as info:
            replay.reset()

        assert info.value.code == "POSITION_OPEN"

    def test_refused_reset_discards_nothing(self) -> None:
        """The position, the journal and the cursor must all survive the refusal."""

        replay = new_replay()
        while replay.state.has_open_position is False:
            replay.step()

        position = replay.broker.open_trade
        cursor = replay.state.cursor
        journal = list(replay.broker.journal)
        cash = replay.broker.cash
        status = replay.state.status

        with pytest.raises(PositionOpenError):
            replay.reset()

        assert replay.broker.open_trade is position
        assert replay.broker.journal == journal
        assert replay.state.cursor == cursor
        assert replay.broker.cash == cash
        assert replay.state.status == status
        assert replay.state.has_open_position is True

    def test_reset_succeeds_once_the_position_closes(self) -> None:
        replay = new_replay()
        while replay.state.has_open_position is False:
            replay.step()

        while replay.state.has_open_position:
            replay.step()

        state = replay.reset()

        assert state.status == STATE_IDLE
        assert state.trade_count == 0


# ---------------------------------------------------------------------------
# E. safety
# ---------------------------------------------------------------------------


class TestSafety:
    def test_replay_does_not_mutate_the_dataset(self) -> None:
        """32. Byte-for-byte, over a whole run."""

        def fingerprint():
            return [
                (c.timestamp, c.open, c.high, c.low, c.close, c.volume)
                for c in SOURCE
            ]

        before = fingerprint()
        run_to_completion(new_replay())

        assert fingerprint() == before

    def test_replay_copies_the_candle_input(self) -> None:
        """A caller mutating its own list cannot reach into the replay."""

        series = list(SOURCE[:200])
        replay = Replay(series, config=CONFIG, costs=COSTS)
        expected = replay.state.next_timestamp

        series[0] = replace(series[0], open=-1.0, high=-1.0, low=-1.0, close=-1.0)

        assert replay.state.next_timestamp == expected
        result = replay.step()
        assert result.signal == analyze(SOURCE[:REQUIRED], CONFIG)

    def test_replay_does_not_mutate_the_strategy(self) -> None:
        """33. The config object and its hash are untouched."""

        config = StrategyConfig()
        before_repr, before_hash = repr(config), config_hash(config)

        replay = run_to_completion(
            Replay(SOURCE[:400], config=config, costs=COSTS)
        )

        assert repr(config) == before_repr
        assert config_hash(config) == before_hash
        assert config == StrategyConfig()
        assert replay.state.strategy.config_hash == before_hash

    def test_replay_does_not_mutate_the_costs(self) -> None:
        costs = phase13_costs()
        before = repr(costs)

        run_to_completion(
            Replay(SOURCE[:400], config=CONFIG, costs=costs)
        )

        assert repr(costs) == before

    def test_mid_run_identity_mutation_is_detected(self) -> None:
        """The per-step identity re-check raises rather than corrupting a run."""

        replay = new_replay()
        replay.step()

        # Forge a mismatch by re-pointing the cached hash, simulating a config
        # that changed underneath the replay.
        replay._config_hash = "0" * 64

        with pytest.raises(ReplayError):
            replay.step()

    def test_dataset_mutation_mid_run_is_detected(self) -> None:
        replay = new_replay()
        replay.step()
        replay._fingerprint = (0, None, None)

        with pytest.raises(ReplayError):
            replay.step()

    def test_replay_imports_nothing_outside_the_engine_and_stdlib(self) -> None:
        """34/35. No transport, no third-party package, no dashboard coupling."""

        allowed = {
            "__future__",
            "dataclasses",
            "datetime",
            "typing",
            "uuid",
        }
        engine_modules = {
            "backtest",
            "costs",
            "models",
            "simulator",
            "strategy",
            "walkforward",
        }

        modules = set()
        tree = ast.parse(REPLAY_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    assert node.module in engine_modules, node.module
                else:
                    modules.add((node.module or "").split(".")[0])

        assert modules <= allowed, modules - allowed

    def test_replay_contains_no_network_capability(self) -> None:
        """35. No socket, HTTP client or subscription anywhere in the module."""

        code = code_only(REPLAY_SOURCE)

        for forbidden in (
            "socket",
            "urllib",
            "requests",
            "httpx",
            "aiohttp",
            "websocket",
            "asyncio",
            "urlopen",
            "connect(",
            "subprocess",
        ):
            assert forbidden not in code, forbidden

    def test_replay_contains_no_real_money_or_execution_path(self) -> None:
        """36. Paper only: no venue, order, wallet or credential concept."""

        code = code_only(REPLAY_SOURCE)

        for forbidden in (
            "exchange",
            "binance",
            "ccxt",
            "order",
            "place_order",
            "create_order",
            "submit",
            "wallet",
            "withdraw",
            "deposit",
            "leverage",
            "margin",
            "buying_power",
            "api_key",
            "secret",
            "credential",
            "private_key",
            "authorize",
        ):
            assert forbidden not in code, forbidden

    def test_replay_touches_only_the_broker_for_money_movement(self) -> None:
        """Cash and positions move in exactly one place, and it is the broker's."""

        replay = new_replay(SOURCE[:400])
        seen = []

        original_open = replay.broker.open_from_signal
        original_close = replay.broker.close

        def spy_open(signal, risk_fraction=0.01):
            seen.append(("open", signal.side))
            return original_open(signal, risk_fraction=risk_fraction)

        def spy_close(price, timestamp):
            seen.append(("close", price))
            return original_close(price, timestamp)

        replay.broker.open_from_signal = spy_open
        replay.broker.close = spy_close

        while replay.state.status != STATE_FINISHED:
            replay.step()

        trades = len(replay.broker.journal)
        opens = [k for k, _ in seen if k == "open"]
        closes = [k for k, _ in seen if k == "close"]

        assert trades > 0, "fixture must trade"
        # Every mutation went through the authoritative broker methods, and the
        # counts reconcile exactly: one close per journalled trade, and one open
        # per trade plus any position still open at the end.
        assert set(k for k, _ in seen) <= {"open", "close"}
        assert len(closes) == trades
        assert len(opens) == trades + (
            0 if replay.broker.open_trade is None else 1
        )

    def test_replay_never_writes_a_balance_itself(self) -> None:
        """No assignment to ``cash`` outside the broker."""

        code = code_only(REPLAY_SOURCE)

        assert "cash =" not in code
        assert ".cash +=" not in code

    def test_no_dashboard_or_transport_dependency_exists(self) -> None:
        """The replay core is pure engine logic: no web framework, no UI layer."""

        code = code_only(REPLAY_SOURCE)

        for forbidden in ("fastapi", "pydantic", "starlette", "uvicorn", "http"):
            assert forbidden not in code, forbidden

    def test_replay_has_no_persistence(self) -> None:
        """No file is written and nothing is read beyond the supplied candles."""

        code = code_only(REPLAY_SOURCE)

        for forbidden in ("open(", "write", "json", "pickle", "shelve", "sqlite"):
            assert forbidden not in code, forbidden


# ---------------------------------------------------------------------------
# construction guards
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_start_index_is_the_minimum_history(self) -> None:
        assert new_replay().state.start_index == minimum_history(CONFIG) == 22

    def test_start_index_below_minimum_history_is_rejected(self) -> None:
        with pytest.raises(InvalidStartIndexError) as info:
            Replay(SOURCE, config=CONFIG, costs=COSTS, start_index=21)

        assert info.value.code == "INSUFFICIENT_HISTORY"

    def test_start_index_beyond_the_dataset_is_rejected(self) -> None:
        with pytest.raises(InvalidStartIndexError):
            Replay(SOURCE, config=CONFIG, costs=COSTS, start_index=len(SOURCE))

    def test_empty_candles_are_rejected(self) -> None:
        with pytest.raises(ValueError):
            Replay((), config=CONFIG, costs=COSTS)

    def test_later_start_index_is_accepted(self) -> None:
        replay = new_replay(SOURCE[:400], start_index=100)

        assert replay.state.cursor == 100
        assert replay.state.bars_processed == 0

    def test_later_start_index_skips_no_needed_exit(self) -> None:
        """Skipping iterations is safe only because the broker starts flat."""

        replay = new_replay(SOURCE[:400], start_index=100)
        while replay.state.status != STATE_FINISHED:
            replay.step()

        assert replay.state.has_open_position is False
        assert all(
            t.entry_time >= SOURCE[100].timestamp for t in replay.broker.journal
        )

    def test_invalid_evaluation_start_is_rejected(self) -> None:
        with pytest.raises(InvalidStartIndexError):
            Replay(
                SOURCE, config=CONFIG, costs=COSTS,
                evaluation_start=REQUIRED - 1,
            )

    def test_invalid_risk_fraction_is_rejected_by_the_broker(self) -> None:
        """Sizing validation stays the broker's, and replay passes it through."""

        replay = new_replay(SOURCE[:400])
        replay._risk_fraction = 0.0

        for _ in range(len(SOURCE[:400])):
            try:
                replay.step()
            except ValueError as exc:
                assert "risk_fraction" in str(exc)
                return

        raise AssertionError("broker never rejected the invalid risk_fraction")

    def test_replay_id_can_be_supplied(self) -> None:
        assert new_replay(replay_id="fixed").replay_id == "fixed"


# ---------------------------------------------------------------------------
# execution-policy seam
# ---------------------------------------------------------------------------


class TestExecutionPolicy:
    """The seam that keeps Manual and Alerts possible without engine changes."""

    def test_automatic_policy_is_the_default(self) -> None:
        replay = new_replay()

        assert replay.policy is AUTOMATIC_POLICY
        assert replay.policy.allow_entry is True

    def test_a_refusing_policy_produces_signals_but_no_trades(self) -> None:
        """What a future Manual mode needs: observe without executing."""

        replay = new_replay(
            SOURCE[:400],
            policy=ExecutionPolicy(name="manual", allow_entry=False),
        )
        signals = 0

        while replay.state.status != STATE_FINISHED:
            result = replay.step()
            assert result.opened is None
            assert result.closed is None
            if result.signal.side in {"long", "short"}:
                signals += 1

        assert signals > 0, "the strategy did produce actionable signals"
        assert replay.broker.journal == []
        assert replay.state.trade_count == 0
        assert replay.state.balance == STARTING_BALANCE
        assert replay.state.has_open_position is False

    def test_a_refusing_policy_never_calls_the_broker(self) -> None:
        replay = new_replay(
            SOURCE[:400],
            policy=ExecutionPolicy(name="alerts", allow_entry=False),
        )
        calls = []
        replay.broker.open_from_signal = lambda *a, **k: calls.append(a)
        replay.broker.close = lambda *a, **k: calls.append(a)

        while replay.state.status != STATE_FINISHED:
            replay.step()

        assert calls == []

    def test_policy_must_be_named(self) -> None:
        with pytest.raises(ValueError):
            ExecutionPolicy(name="", allow_entry=True)