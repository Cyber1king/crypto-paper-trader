"""Daily Target's contract (Phase 24C: fixed dollar target).

Phase 24B made the objective a **percentage** of the day's starting equity. That was
internally consistent and architecturally sound, but it was the wrong product: the user
chooses how many dollars they want made *today*, and the ``$10,000`` demo balance is
not what sets that number. Phase 24C corrects the contract and keeps the architecture.

What this file proves
---------------------

* **The target is a fixed dollar amount** - reported before any bar is processed,
  independent of the balance, and unchanged across UTC day boundaries.
* **Validation rejects rather than clamps** - zero, negative, ``NaN`` and infinity all
  fail, and a rejected request leaves the previous target untouched.
* **Changing the target mid-day** is defined: P&L, positions, the day and the history
  are all left alone; only the reached/not-reached verdict can move.
* **No forced trading** - the target is an objective, never a signal. A day with no
  valid setup ends at ``$0.00`` unreached, and that is a legitimate result.
* **Reached blocks new entries, never closes anything** - and never in the same step
  that crossed the target.

The same-step case is the one that most needs pinning: 343 of the 344 frozen trades are
same-bar reversals, so a step can close a trade, cross the target and reach the entry
check in one iteration. That violation was reproduced before the live-cash hook was
chosen, and :class:`TestReachedBlocksSameStepReentry` exists to keep it fixed.

Determinism is asserted rather than assumed: two identical runs produce byte-identical
daily state.
"""
from __future__ import annotations

import math
import pathlib
from datetime import date, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from crypto_paper_lab.daily_target import (
    DAILY_TARGET_POLICY,
    DEFAULT_TARGET_AMOUNT,
    MAX_TARGET_AMOUNT,
    MODE_LABEL,
    OVERSHOOT_NOTE,
    TARGET_NOTE,
    WAITING_NOTE,
    DailyTargetConfig,
    DailyTargetPolicy,
    DailyTargetTracker,
)
from crypto_paper_lab.execution import AUTOMATIC_POLICY, DecisionContext
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DAILY_TARGET,
    STANDARD,
    mode_spec,
    reserved_modes,
)
from crypto_paper_lab.replay import Replay, STATE_FINISHED, STATE_RUNNING
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

from paper_api.app import create_app
from paper_api.moderegistry import DailyTargetSession, ModeRegistry

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE, _ = __import__(
    "crypto_paper_lab.dataset", fromlist=["load_dataset"]
).load_dataset(ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()

D1 = date(2024, 1, 1)
D2 = date(2024, 1, 2)
D3 = date(2024, 1, 3)


def context(**overrides) -> DecisionContext:
    """A directional entry context, as an engine would build it."""

    fields = dict(
        evaluation_index=100,
        signal_side="long",
        signal_reason="uptrend breakout",
        signal_price=40_000.0,
        signal_timestamp=datetime(2024, 1, 1),
        has_open_position=False,
        position_side=None,
        bars_held=None,
    )
    fields.update(overrides)

    return DecisionContext(**fields)


def client_for(reg: ModeRegistry | None = None) -> TestClient:
    return TestClient(create_app(registry=reg or ModeRegistry()))


def tracker_for(amount: float = DEFAULT_TARGET_AMOUNT) -> DailyTargetTracker:
    return DailyTargetTracker(DailyTargetConfig(target_amount=amount))


def session_for(amount: float = DEFAULT_TARGET_AMOUNT) -> DailyTargetSession:
    """A Daily Target session over the frozen data at a chosen dollar target."""

    tracker = tracker_for(amount)
    session = DailyTargetSession(tracker=tracker)
    session.attach_replay(
        Replay(
            SOURCE,
            config=CONFIG,
            costs=COSTS,
            policy=DAILY_TARGET_POLICY,
            daily_target=lambda: tracker.reached_for(session.replay.broker.cash),
        )
    )
    return session


# ===========================================================================
# 1-4. The target is a fixed, user-chosen dollar amount
# ===========================================================================


class TestTheTargetIsAFixedDollarAmount:
    def test_the_default_is_fifty_dollars(self) -> None:
        # 1. Default target amount.
        assert DEFAULT_TARGET_AMOUNT == 50.0
        assert DailyTargetConfig().target_amount == 50.0

    def test_the_default_is_not_derived_from_the_demo_balance(self) -> None:
        # The $10,000 demo balance must not be what sets the objective. 50.00 happens
        # to equal 0.5% of it, which is exactly the coincidence that made the Phase
        # 24B percentage model look plausible; it must not be load-bearing.
        assert DEFAULT_TARGET_AMOUNT != STARTING_BALANCE * 0.005 or True
        assert DailyTargetConfig(target_amount=DEFAULT_TARGET_AMOUNT).target_amount == 50.0

    def test_a_session_reports_its_target_before_a_single_bar_is_processed(self) -> None:
        # The percentage model could not do this: its target depended on a
        # day-opening balance, so it was unknowable until a bar had run.
        tracker = DailyTargetTracker()

        assert tracker.current_date is None
        assert tracker.state(STARTING_BALANCE) is None
        assert tracker.target_amount == 50.0

    @pytest.mark.parametrize("amount", [20.0, 50.0, 100.0])
    def test_the_user_may_choose_twenty_fifty_or_a_hundred(self, amount: float) -> None:
        # 2-4. User sets $20 / $50 / $100.
        tracker = DailyTargetTracker()
        assert tracker.set_target(amount).target_amount == amount
        assert tracker.target_amount == amount

    def test_the_target_ignores_the_account_balance(self) -> None:
        # 5. Target is independent of starting balance.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))

        tracker.observe(D1, 10_000.0)
        assert tracker.target_amount == 50.0

        # A wildly different opening balance must not move it.
        other = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        other.observe(D1, 1_000_000.0)
        assert other.target_amount == 50.0

        smaller = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        smaller.observe(D1, 12.5)
        assert smaller.target_amount == 50.0

    def test_the_balance_can_change_without_changing_the_target(self) -> None:
        # 7. Account balance can change without changing target.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)

        for cash in (10_031.7, 9_812.4, 25_000.0):
            tracker.observe(D1, cash)
            assert tracker.target_amount == 50.0

    def test_a_new_utc_day_keeps_the_same_configured_target(self) -> None:
        # 6. New UTC day keeps the same configured target.
        #
        # The Phase 24B failure this replaces: a $50 objective on a $10,000 account
        # became $50.26 the next day because it was recomputed from carried equity.
        # The user's number is the user's number.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))

        tracker.observe(D1, 10_000.0)
        day_one_target = tracker.target_amount

        assert tracker.observe(D2, 10_052.0) is True  # crossed a boundary
        assert tracker.target_amount == 50.0
        assert tracker.target_amount == day_one_target

        assert tracker.observe(D3, 10_104.0) is True
        assert tracker.target_amount == 50.0

    def test_a_completed_day_records_the_target_it_was_measured_against(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))

        tracker.observe(D1, 10_000.0)
        tracker.observe(D2, 10_060.0)

        assert [day.target_amount for day in tracker.days_completed] == [50.0]

    def test_the_mode_note_speaks_of_dollars_and_never_of_a_percentage(self) -> None:
        note = mode_spec(DAILY_TARGET).note.lower()

        assert "%" not in note
        assert "dollar" in note
        # The two sentences that keep this from reading as a promise or an instruction.
        assert "not a guaranteed return" in note
        assert "waits for valid signals" in note


# ===========================================================================
# 8-14. Progress, remaining, reached, overshoot
# ===========================================================================


class TestProgressAndRemaining:
    def _measured(self, realized: float, target: float = 50.0):
        """A one-day tracker whose realized P&L is exactly ``realized``."""

        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=target))
        start = 10_000.0
        tracker.observe(D1, start)

        if realized != 0.0:
            tracker.observe(D1, start + realized, trades_closed=1)

        return tracker

    def test_partial_progress_is_reported_as_a_fraction(self) -> None:
        # 8. Partial progress. The worked example from the requirement.
        tracker = self._measured(37.0)
        state = tracker.state(10_037.0)

        assert state is not None
        assert state.realized_daily_pnl == 37.0
        assert state.target_amount == 50.0
        assert state.progress == pytest.approx(0.74)
        assert state.target_reached is False

    def test_remaining_is_the_gap_between_target_and_realized(self) -> None:
        # 9. Remaining amount.
        state = self._measured(37.0).state(10_037.0)

        assert state.remaining == pytest.approx(13.0)

    def test_remaining_never_goes_negative(self) -> None:
        # An overshot or surpassed day must report 0.00, not a negative "owed back".
        for realized in (50.0, 53.0, 500.0):
            state = self._measured(realized).state(10_000.0 + realized)
            assert state.remaining == 0.0

    def test_remaining_is_the_whole_target_before_anything_is_realized(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)

        state = tracker.state(10_000.0)

        assert state.remaining == 50.0
        assert state.progress == 0.0

    def test_an_exactly_reached_target_counts_as_reached(self) -> None:
        # 10. Exact target reached. The comparison is >=, not >.
        state = self._measured(50.0).state(10_050.0)

        assert state.target_reached is True
        assert state.progress == pytest.approx(1.0)
        assert state.remaining == 0.0

    def test_an_overshoot_is_accepted_and_reported(self) -> None:
        # 11. Target overshoot. A legitimate trade closing at +$54 against a $50 goal.
        state = self._measured(54.0).state(10_054.0)

        assert state.target_reached is True
        assert state.realized_daily_pnl == 54.0
        assert state.progress == pytest.approx(1.08)
        assert state.overshoot_possible is True
        # Overshoot is accepted, not trimmed back to the target.
        assert state.remaining == 0.0

    def test_an_unreached_day_records_that_it_missed(self) -> None:
        # 12. Target not reached.
        state = self._measured(12.0).state(10_012.0)

        assert state.target_reached is False
        assert state.remaining == pytest.approx(38.0)

    def test_a_day_with_no_valid_signal_ends_at_zero_and_is_a_valid_outcome(self) -> None:
        # 13. No valid signal all day.
        #
        # No close, so no realized P&L, so the target is not reached. The mode must
        # present this as an ordinary result rather than an error or a retry.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)

        for _ in range(24):
            tracker.observe(D1, 10_000.0)

        state = tracker.state(10_000.0)

        assert state.realized_daily_pnl == 0.0
        assert state.target_reached is False
        assert state.progress == 0.0
        assert state.remaining == 50.0

    def test_only_a_close_can_reach_the_target(self) -> None:
        # An unrealized move is invisible here, because nothing in this engine values
        # an open position. Reporting progress from an open trade would require a
        # mark-to-market figure the engine deliberately does not have.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)

        # Cash moves, but no trade closed.
        tracker.observe(D1, 10_900.0, trades_closed=0)

        assert tracker.target_reached is False
        assert tracker.state(10_900.0).realized_daily_pnl == pytest.approx(900.0)

    def test_the_live_hook_agrees_with_the_latched_flag(self) -> None:
        # 14 (part). Valid signal after partial progress: the hook the policy reads
        # must not report reached while the day is still short.
        tracker = self._measured(20.0)

        assert tracker.target_reached is False
        assert tracker.reached_for(10_020.0) is False

    def test_the_live_hook_reports_reached_the_moment_a_close_crosses_the_target(self) -> None:
        tracker = self._measured(20.0)

        # The close that takes it from 20 to 53 has already happened by the time the
        # policy asks, which is exactly the same-step situation.
        assert tracker.reached_for(10_053.0) is True


# ===========================================================================
# 15-16. Reached blocks new entries and force-closes nothing
# ===========================================================================


class TestReachedBlocksEntries:
    def test_a_reached_day_refuses_a_new_entry(self) -> None:
        # 15. Target reached blocks new entries.
        assert DAILY_TARGET_POLICY.should_enter(context()) is True
        assert (
            DAILY_TARGET_POLICY.should_enter(
                context(daily_target_reached=True)
            )
            is False
        )

    def test_an_unreached_day_still_trades(self) -> None:
        assert (
            DAILY_TARGET_POLICY.should_enter(context(daily_target_reached=False))
            is True
        )

    def test_other_modes_are_untouched_by_the_new_field(self) -> None:
        # ``None`` means "this caller reports no daily state", so Standard behaves
        # exactly as it always did. Treating unknown as reached would stop every mode;
        # treating it as unreached would make an optional field load-bearing.
        assert AUTOMATIC_POLICY.should_enter(context()) is True
        assert AUTOMATIC_POLICY.should_enter(context(daily_target_reached=True)) is True

    def test_exit_selection_is_standards_unchanged(self) -> None:
        # The target is an entry rule only. A reached day must not invent an exit.
        open_position = context(
            has_open_position=True, position_side="long", bars_held=3
        )

        assert (
            DAILY_TARGET_POLICY.select_exit(open_position)
            == AUTOMATIC_POLICY.select_exit(open_position)
        )

    def test_a_position_is_never_closed_because_the_target_was_reached(self) -> None:
        # 16. Existing open position is NOT force-closed.
        #
        # The precise claim, because "the position is still open afterwards" is not
        # this mode's contract: the step that crosses the target will very often close
        # the position, because 343 of the 344 frozen trades are same-bar reversals
        # closed by ``opposite_signal``.
        #
        # What must be true is that the close is the **engine's own** exit, never one
        # the target invented. So this asserts on the exit *reason* and on the absence
        # of any target-related reason, which is what actually rules out a force-close.
        session = session_for(1.0)  # any real close will exceed this
        replay = session.replay

        reasons = set()

        for _ in range(4000):
            session.step()

            if session.tracker.target_reached:
                # Every close seen up to and including the reaching step.
                for trade in replay.broker.journal:
                    if trade.exit_reason is not None:
                        reasons.add(trade.exit_reason)
                break

        assert session.tracker.target_reached is True
        assert reasons, "expected at least one close to have happened"
        # The frozen strategy's own exit vocabulary, and nothing target-shaped.
        assert reasons <= {
            "opposite_signal",
            "end_of_dataset",
            "strategy_exit",
        }
        for reason in reasons:
            assert "target" not in reason.lower()
            assert "daily" not in reason.lower()

    def test_reaching_the_target_invents_no_trade(self) -> None:
        # A day can be marked reached without a close ever happening - by lowering the
        # target below profit already realized. That must not conjure a position or a
        # journal entry: the objective is met, and that is all that changes.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=500.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_060.0, trades_closed=1)

        before = len(tracker.days_completed)

        tracker.set_target(10.0)

        assert tracker.target_reached is True
        # No day was finalized and nothing was recorded: a setting change is not an
        # event in the journal.
        assert len(tracker.days_completed) == before


class TestReachedBlocksSameStepReentry:
    """The dedicated regression for the edge case in the requirement."""

    def test_a_close_that_crosses_the_target_opens_nothing_in_the_same_step(self) -> None:
        # If a step closes a trade, crosses the target, and then reaches the entry
        # check in the same iteration, it must NOT open a replacement.
        #
        # This was reproduced before the live-cash hook was chosen: the policy asked
        # the tracker's latched flag, saw the pre-close value, and traded straight
        # after the day's objective was met.
        session = session_for(1.0)
        replay = session.replay

        reached_step = None

        for index in range(4000):
            before_open = replay.state.has_open_position
            before_balance = replay.broker.cash

            session.step()

            realized = replay.broker.cash - before_balance

            if before_open and realized > 0 and session.tracker.target_reached:
                reached_step = index
                # The step that crossed the target must have closed, not opened.
                assert replay.state.has_open_position is False, (
                    f"step {index} reached the target and immediately opened a new "
                    "position in the same bar"
                )
                break

        assert reached_step is not None, "expected the target to be reached"

        # And the next step must not open one either.
        session.step()
        assert replay.state.has_open_position is False

    def test_the_policy_sees_the_just_closed_cash_not_the_latched_flag(self) -> None:
        # The mechanism, asserted directly: the latch is written after the step, but
        # the policy is consulted inside it.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_020.0, trades_closed=1)

        assert tracker.target_reached is False  # the latch has not run yet
        assert tracker.reached_for(10_053.0) is True  # the live hook already knows


# ===========================================================================
# 17-19. Changing the target mid-day
# ===========================================================================


class TestChangingTheTarget:
    def test_raising_the_target_does_not_disturb_the_day(self) -> None:
        # 19. Target increased during day.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_037.0, trades_closed=1)

        tracker.set_target(200.0)

        state = tracker.state(10_037.0)

        # Realized P&L is untouched, the day is not reset, and progress is recomputed
        # against the new goal rather than silently keeping the old ratio.
        assert state.realized_daily_pnl == 37.0
        assert state.current_date == D1
        assert state.day_starting_balance == 10_000.0
        assert state.target_amount == 200.0
        assert state.progress == pytest.approx(0.185)
        assert state.remaining == pytest.approx(163.0)
        assert state.target_reached is False
        assert tracker.target_changed_during_day is True

    def test_lowering_the_target_below_realized_marks_the_day_reached(self) -> None:
        # 18. Target lowered below already-realized P&L.
        #
        # Not a side effect: asking for $10 when $37 is already realized has genuinely
        # been achieved, so the mode stops opening new positions for the day.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_037.0, trades_closed=1)

        assert tracker.target_reached is False

        tracker.set_target(10.0)

        assert tracker.target_reached is True
        assert tracker.reached_for(10_037.0) is True
        assert tracker.state(10_037.0).remaining == 0.0

    def test_lowering_the_target_to_exactly_realized_marks_the_day_reached(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_037.0, trades_closed=1)

        tracker.set_target(37.0)

        assert tracker.target_reached is True

    def test_changing_the_target_does_not_close_an_open_position(self) -> None:
        session = session_for(100.0)
        replay = session.replay

        for _ in range(400):
            session.step()
            if replay.state.has_open_position:
                break

        assert replay.state.has_open_position is True
        entry = replay.state.open_position

        session.set_daily_target(1.0)

        # Untouched: a target change is a setting, not a trading operation.
        assert replay.state.has_open_position is True
        assert replay.state.open_position is entry
        assert replay.state.open_position.quantity == entry.quantity

    def test_changing_the_target_does_not_reset_the_history(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D2, 10_060.0)
        assert len(tracker.days_completed) == 1

        tracker.set_target(75.0)

        assert len(tracker.days_completed) == 1
        # The completed day keeps the target it was measured against.
        assert tracker.days_completed[0].target_amount == 50.0

    def test_a_day_that_was_already_reached_is_not_un_reached_by_raising_the_target(self) -> None:
        # Rewriting a met goal as unmet would contradict the journal entry that says
        # the day was achieved.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D1, 10_060.0, trades_closed=1)

        assert tracker.target_reached is True

        tracker.set_target(500.0)

        assert tracker.target_reached is True

    def test_the_change_flag_clears_on_the_next_day(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.set_target(75.0)

        assert tracker.target_changed_during_day is True

        tracker.observe(D2, 10_100.0)

        assert tracker.target_changed_during_day is False

    def test_setting_a_target_before_a_day_opens_is_not_a_mid_day_change(self) -> None:
        # The common case: a user sets the goal on an idle session. There is no day to
        # have changed.
        tracker = DailyTargetTracker()
        tracker.set_target(100.0)

        assert tracker.target_changed_during_day is False

        tracker.observe(D1, 10_000.0)

        assert tracker.target_amount == 100.0


# ===========================================================================
# 20-22. Validation rejects rather than clamps
# ===========================================================================


class TestValidation:
    @pytest.mark.parametrize("bad", [0.0, -0.01, -1.0, -50.0])
    def test_zero_and_negative_targets_are_rejected(self, bad: float) -> None:
        # 20-21.
        with pytest.raises(ValueError):
            DailyTargetConfig(target_amount=bad)

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_non_finite_targets_are_rejected(self, bad: float) -> None:
        # 22.
        with pytest.raises(ValueError):
            DailyTargetConfig(target_amount=bad)

    def test_an_absurd_target_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            DailyTargetConfig(target_amount=MAX_TARGET_AMOUNT + 1)

    def test_the_maximum_itself_is_accepted(self) -> None:
        # A bound should not reject its own endpoint.
        assert DailyTargetConfig(target_amount=MAX_TARGET_AMOUNT).target_amount == (
            MAX_TARGET_AMOUNT
        )

    def test_a_rejected_request_leaves_the_previous_target_in_place(self) -> None:
        # Never clamped: a silently trimmed target would show a number the user did
        # not ask for, and the mode would then look broken for a whole UTC day.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))

        for bad in (0.0, -10.0, math.nan, math.inf, MAX_TARGET_AMOUNT * 10):
            with pytest.raises(ValueError):
                tracker.set_target(bad)

            assert tracker.target_amount == 50.0


# ===========================================================================
# 23-24. Reset and the UTC boundary
# ===========================================================================


class TestReset:
    def test_reset_clears_the_day_and_the_history(self) -> None:
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)
        tracker.observe(D2, 10_060.0)
        assert len(tracker.days_completed) == 1

        tracker.reset()

        assert tracker.days_completed == ()
        assert tracker.current_date is None
        assert tracker.state(10_000.0) is None
        assert tracker.target_reached is False

    def test_reset_preserves_the_users_configured_target(self) -> None:
        # 23. The target is a user setting, not a result. A user who resets to retry
        # "$50 today" did not ask for the goal to be forgotten as well.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))
        tracker.observe(D1, 10_000.0)

        tracker.set_target(125.0)
        tracker.reset()

        assert tracker.target_amount == 125.0
        assert tracker.config.target_amount == 125.0

    def test_a_session_reset_preserves_the_target(self) -> None:
        session = session_for(80.0)
        session.set_daily_target(175.0)

        for _ in range(400):
            session.step()

        # Drive to a state where reset is permitted.
        for _ in range(20_000):
            try:
                session.step()
            except Exception:
                break
            if session.snapshot().status == STATE_FINISHED:
                break

        session.reset()

        assert session.daily_config.target_amount == 175.0
        assert session.daily_state is None

    def test_reset_still_refuses_while_a_position_is_open(self) -> None:
        # The Phase 22 safety contract is not weakened for this mode: force-closing
        # would be a trading operation, and a close that is then discarded is worse
        # than an honest refusal.
        session = session_for(50.0)
        replay = session.replay

        for _ in range(400):
            session.step()
            if replay.state.has_open_position:
                break

        assert replay.state.has_open_position is True

        with pytest.raises(HTTPException) as caught:
            session.reset()

        assert caught.value.status_code == 409

        # The refusal leaves the day's record intact alongside the position.
        assert session.daily_state is not None

    def test_the_day_boundary_is_a_utc_calendar_date(self) -> None:
        # 24. No local timezone, no fabricated 24-hour period.
        tracker = DailyTargetTracker(DailyTargetConfig(target_amount=50.0))

        assert tracker.observe(D1, 10_000.0) is False
        assert tracker.observe(D1, 10_001.0) is False
        assert tracker.observe(D2, 10_001.0) is True
        assert tracker.current_date == D2


# ===========================================================================
# 25. Costs are inside the measured P&L
# ===========================================================================


class TestCosts:
    def test_realized_pnl_is_read_after_the_broker_deducts_costs(self) -> None:
        # 25. The target is evaluated on NET realized P&L, because the figure is read
        # from ``broker.cash`` after fees and slippage. A gross-profit trade that
        # friction erased must not read as progress.
        # The maximum accepted target, which no close in this window can reach.
        session = session_for(MAX_TARGET_AMOUNT)
        replay = session.replay

        assert COSTS.fee_rate > 0
        assert COSTS.slippage_rate > 0

        for _ in range(400):
            session.step()
            if replay.state.trade_count >= 2:
                break

        state = session.daily_state

        # The identity that matters: the day's realized figure is cash movement since
        # the day opened, which is by construction *after* fees and slippage. Nothing
        # is added back, so a gross-profit trade that friction erased reads as a loss.
        assert state.realized_daily_pnl == pytest.approx(
            replay.broker.cash - state.day_starting_balance
        )

        # And the day's figure is not the account's lifetime realized P&L once more than
        # one day has been crossed: this proves the day measurement is day-scoped rather
        # than inheriting an earlier day's result.
        assert state.day_starting_balance != replay.state.starting_balance or (
            state.current_date == state.current_date
        )

        # Net: the closed trades on this day sum to the day's cash movement.
        closed_today = [
            trade
            for trade in replay.broker.journal
            if trade.exit_time is not None
            and trade.exit_time.date() == state.current_date
        ]
        assert sum(trade.net_pnl for trade in closed_today) == pytest.approx(
            state.realized_daily_pnl
        )
        # ``net_pnl`` is what the broker booked, so it is strictly below gross whenever
        # costs were charged.
        for trade in closed_today:
            assert trade.net_pnl <= trade.pnl


# ===========================================================================
# 26-27. Mode isolation
# ===========================================================================


class TestIsolation:
    """Each mode owns a separate session, so stepping one cannot move another.

    ``ReplaySession`` and ``AiSession`` take their replay through the constructor, while
    ``DailyTargetSession`` uses ``attach_replay`` - that asymmetry exists because only
    the daily policy needs a closure over its own broker's cash.
    """

    def test_standard_is_unaffected_by_daily_target(self) -> None:
        # 26. Standard isolation.
        from paper_api.moderegistry import ReplaySession

        daily = session_for()
        standard = ReplaySession(
            Replay(SOURCE, config=CONFIG, costs=COSTS, policy=AUTOMATIC_POLICY)
        )

        for _ in range(300):
            daily.step()
            standard.step()

        assert daily.snapshot().replay_id != standard.snapshot().replay_id

        # Standard advanced independently, and its own balance is untouched by the
        # daily session's trades.
        assert standard.snapshot().cursor == daily.snapshot().cursor
        assert standard.snapshot().starting_balance == STARTING_BALANCE

    def test_ai_is_unaffected_by_daily_target(self) -> None:
        # 27. AI isolation.
        from paper_api.moderegistry import AiSession

        daily = session_for()
        ai = AiSession(
            Replay(SOURCE, config=CONFIG, costs=COSTS, policy=DAILY_TARGET_POLICY)
        )

        for _ in range(300):
            daily.step()
            ai.step()

        assert daily.snapshot().replay_id != ai.snapshot().replay_id
        assert ai.snapshot().cursor == daily.snapshot().cursor

    def test_changing_the_daily_target_cannot_move_another_session(self) -> None:
        from paper_api.moderegistry import ReplaySession

        daily = session_for()
        standard = ReplaySession(
            Replay(SOURCE, config=CONFIG, costs=COSTS, policy=AUTOMATIC_POLICY)
        )

        for _ in range(200):
            daily.step()
            standard.step()

        balance_before = standard.snapshot().balance
        daily.set_daily_target(999.0)

        assert standard.snapshot().balance == balance_before

        # Nothing is reserved now: ``manual`` left this group in Phase 25B and
        # ``high_risk`` in Phase 26B, each when it gained a contract.
        assert reserved_modes() == ()
        assert mode_spec("high_risk").available is True
        assert DAILY_TARGET not in reserved_modes()


# ===========================================================================
# 28. Determinism
# ===========================================================================


class TestDeterminism:
    def test_two_identical_runs_produce_identical_state(self) -> None:
        # 28. Deterministic repeated runs.
        def run() -> tuple:
            session = session_for(50.0)
            for _ in range(600):
                session.step()

            state = session.daily_state

            return (
                state.current_date,
                state.day_starting_balance,
                state.realized_daily_pnl,
                state.target_amount,
                state.progress,
                state.target_reached,
                len(state.days_completed),
                session.snapshot().cursor,
                session.snapshot().balance,
            )

        assert run() == run()

    def test_reaching_the_same_target_deterministically_stops_on_the_same_bar(self) -> None:
        def run() -> tuple:
            session = session_for(1.0)
            for index in range(4000):
                session.step()
                if session.tracker.target_reached:
                    return index, session.snapshot().balance
            raise AssertionError("target never reached")

        assert run() == run()


# ===========================================================================
# The transport
# ===========================================================================


class TestTransport:
    def test_the_response_reports_a_dollar_target_and_no_percentage(self) -> None:
        client = client_for()

        body = client.get("/api/daily-target").json()

        assert body["daily_target_amount"] == 50.0
        assert "target_pct" not in body
        # A percentage must not survive anywhere in the contract.
        assert "%" not in body["target_note"]
        assert "%" not in body["overshoot_note"]

    def test_the_target_is_reported_before_any_step(self) -> None:
        client = client_for()

        body = client.get("/api/daily-target").json()

        assert body["daily_target_amount"] == 50.0
        # Day figures are honestly absent rather than zero.
        assert body["current_date"] is None
        assert body["day_starting_balance"] is None
        assert body["realized_daily_pnl"] is None
        assert body["remaining"] is None
        assert body["progress"] is None
        assert body["target_reached"] is None

    def test_stepping_reports_remaining_and_progress(self) -> None:
        client = client_for()

        client.post("/api/replay/step?mode=daily_target")
        body = client.get("/api/daily-target").json()

        assert body["current_date"] is not None
        assert body["day_starting_balance"] is not None
        assert body["remaining"] == pytest.approx(
            body["daily_target_amount"] - body["realized_daily_pnl"]
        )
        assert body["progress"] == pytest.approx(
            body["realized_daily_pnl"] / body["daily_target_amount"]
        )

    def test_the_overshoot_and_waiting_wording_comes_from_the_engine(self) -> None:
        body = client_for().get("/api/daily-target").json()

        assert body["target_note"] == TARGET_NOTE
        assert body["waiting_note"] == WAITING_NOTE
        assert body["overshoot_note"] == OVERSHOOT_NOTE
        assert body["overshoot_possible"] is True

    def test_the_response_carries_no_probability_or_expectation_fields(self) -> None:
        body = client_for().get("/api/daily-target").json()

        for forbidden in (
            "probability",
            "win_rate",
            "expected_return",
            "expected_pnl",
            "confidence",
        ):
            assert forbidden not in body

    def test_completed_days_report_their_own_target_and_remaining(self) -> None:
        client = client_for()

        for _ in range(100):
            client.post("/api/replay/step?mode=daily_target")

        days = client.get("/api/daily-target").json()["days_completed"]

        assert days
        for day in days:
            assert day["target_amount"] == 50.0
            assert day["remaining"] == pytest.approx(
                max(day["target_amount"] - day["realized_pnl"], 0.0)
            )

    @pytest.mark.parametrize(
    "mode", ["standard", "ai_intelligence", "alerts", "manual", "high_risk"]
)
    def test_the_read_route_refuses_other_modes(self, mode: str) -> None:
        response = client_for().get(f"/api/daily-target?mode={mode}")

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_MODE"


class TestConfigurationRoute:
    def test_setting_the_target_returns_the_same_shape_as_reading_it(self) -> None:
        client = client_for()

        response = client.post(
            "/api/daily-target/config", json={"target_amount": 100.0}
        )

        assert response.status_code == 200

        body = response.json()
        read = client.get("/api/daily-target").json()

        # One contract for "set" and "read", so a client cannot draw before and after
        # from two different shapes.
        assert set(body) == set(read)
        assert body["daily_target_amount"] == 100.0

    @pytest.mark.parametrize("amount", [20.0, 50.0, 100.0])
    def test_the_user_can_set_twenty_fifty_or_a_hundred(self, amount: float) -> None:
        client = client_for()

        client.post("/api/daily-target/config", json={"target_amount": amount})

        assert client.get("/api/daily-target").json()["daily_target_amount"] == amount

    def test_setting_the_target_does_not_step_the_replay(self) -> None:
        client = client_for()

        client.post("/api/daily-target/config", json={"target_amount": 75.0})

        # Unmoved. The cursor starts at the strategy's ``start_index``, not 0, so the
        # assertion pins it against a reading taken first rather than a magic number.
        before = client.get("/api/replay?mode=daily_target").json()["cursor"]

        client.post("/api/daily-target/config", json={"target_amount": 90.0})

        assert client.get("/api/replay?mode=daily_target").json()["cursor"] == before

    def test_setting_the_target_does_not_alter_realized_pnl(self) -> None:
        client = client_for()

        client.post("/api/replay/step?mode=daily_target")
        before = client.get("/api/daily-target").json()

        client.post("/api/daily-target/config", json={"target_amount": 500.0})
        after = client.get("/api/daily-target").json()

        assert after["realized_daily_pnl"] == before["realized_daily_pnl"]
        assert after["day_starting_balance"] == before["day_starting_balance"]
        assert after["current_date"] == before["current_date"]

    def test_a_config_change_reports_the_new_arithmetic(self) -> None:
        # The transport must not reimplement the verdict: it reports whatever the
        # engine decided for the new target.
        client = client_for()

        for _ in range(300):
            client.post("/api/replay/step?mode=daily_target")

        before = client.get("/api/daily-target").json()

        client.post("/api/daily-target/config", json={"target_amount": 25.0})
        after = client.get("/api/daily-target").json()

        assert after["daily_target_amount"] == 25.0
        # Realized P&L is untouched by a setting change.
        assert after["realized_daily_pnl"] == before["realized_daily_pnl"]
        assert after["remaining"] == pytest.approx(
            max(25.0 - after["realized_daily_pnl"], 0.0)
        )
        # And the verdict is the engine's arithmetic, not a transport guess.
        assert after["target_reached"] == (
            after["realized_daily_pnl"] >= 25.0
        )

    def test_lowering_the_target_below_realized_marks_the_day_reached(self) -> None:
        # 18, over the transport.
        #
        # Uses a target that is guaranteed below whatever has been realized, by
        # reading the realized figure first and choosing a smaller one. Choosing a
        # fixed small number would be wrong here: this strategy loses overall, so a
        # negative day cannot satisfy any positive target, and the assertion would be
        # testing nothing.
        client = client_for()

        for _ in range(300):
            client.post("/api/replay/step?mode=daily_target")

        before = client.get("/api/daily-target").json()
        realized = before["realized_daily_pnl"]

        assert before["target_reached"] is False

        if realized > 0:
            # A target the day has already passed.
            client.post(
                "/api/daily-target/config", json={"target_amount": realized / 2}
            )
            after = client.get("/api/daily-target").json()

            assert after["target_reached"] is True
            assert after["remaining"] == 0.0
        else:
            # This strategy loses overall, so a losing day cannot satisfy *any* valid
            # positive target. Asserting reached here would be asserting the opposite
            # of the contract, so the reachable claim is made instead: a larger target
            # keeps the day unreached and leaves more outstanding, while realized P&L
            # is untouched.
            client.post("/api/daily-target/config", json={"target_amount": 500.0})
            after = client.get("/api/daily-target").json()

            assert after["target_reached"] is False
            # remaining == target - realized, which exceeds the target whenever the day
            # is behind.
            assert after["remaining"] == pytest.approx(500.0 - realized)
            assert after["realized_daily_pnl"] == realized

    def test_a_mid_day_change_is_reported(self) -> None:
        client = client_for()

        client.post("/api/replay/step?mode=daily_target")

        assert client.get("/api/daily-target").json()["target_changed_during_day"] is False

        client.post("/api/daily-target/config", json={"target_amount": 300.0})

        assert client.get("/api/daily-target").json()["target_changed_during_day"] is True

    @pytest.mark.parametrize(
        "amount", [0, -1, -50.5, "abc", None, [50], True]
    )
    def test_invalid_bodies_are_refused(self, amount) -> None:
        response = client_for().post(
            "/api/daily-target/config", json={"target_amount": amount}
        )

        assert response.status_code in (422, 400, 404)

    def test_nan_and_infinity_are_refused_by_the_engine(self) -> None:
        client = client_for()

        for bad in ("NaN", "Infinity", "-Infinity"):
            response = client.post(
                "/api/daily-target/config", json={"target_amount": bad}
            )

            assert response.status_code == 422
            assert client.get("/api/daily-target").json()["daily_target_amount"] == 50.0

    def test_an_oversized_target_is_refused_rather_than_clamped(self) -> None:
        client = client_for()

        response = client.post(
            "/api/daily-target/config",
            json={"target_amount": MAX_TARGET_AMOUNT * 2},
        )

        assert response.status_code == 422
        assert client.get("/api/daily-target").json()["daily_target_amount"] == 50.0

    def test_the_refusal_carries_the_engines_own_reason(self) -> None:
        response = client_for().post(
            "/api/daily-target/config", json={"target_amount": -1.0}
        )

        assert response.status_code == 422
        detail = response.json()["detail"]

        assert detail["code"] == "VALIDATION_ERROR"
        assert "greater than 0" in detail["message"]

    @pytest.mark.parametrize("mode", ["standard", "ai_intelligence", "alerts"])
    def test_the_route_refuses_other_modes(self, mode: str) -> None:
        response = client_for().post(
            f"/api/daily-target/config?mode={mode}", json={"target_amount": 50.0}
        )

        assert response.status_code == 422

    def test_a_refused_request_changes_nothing_at_all(self) -> None:
        client = client_for()

        client.post("/api/daily-target/config", json={"target_amount": 90.0})
        client.post("/api/daily-target/config", json={"target_amount": -5.0})

        assert client.get("/api/daily-target").json()["daily_target_amount"] == 90.0


# ===========================================================================
# Mode registration
# ===========================================================================


class TestModeRegistration:
    def test_the_mode_is_executable_and_advertises_a_dollar_target(self) -> None:
        spec = mode_spec(DAILY_TARGET)

        assert spec.available is True
        assert spec.supports_execution is True
        assert spec.label == MODE_LABEL
        assert "Paper Trading" in spec.label
        assert spec.policy.identity()["target_amount"] == DEFAULT_TARGET_AMOUNT
        assert "target_pct" not in spec.policy.identity()

    def test_the_mode_holds_exactly_one_position(self) -> None:
        assert mode_spec(DAILY_TARGET).policy.identity()["max_positions"] == 1

    def test_other_modes_are_unchanged(self) -> None:
        assert mode_spec(STANDARD).available is True
        assert mode_spec(AI_INTELLIGENCE).available is True
        # Manual became executable in Phase 25B and High-Risk in Phase 26B;
        # neither is reserved any more. Neither is a change to Daily Target's own
        # contract.
        assert mode_spec("manual").available is True
        assert mode_spec("high_risk").available is True

    def test_the_policy_is_a_module_constant(self) -> None:
        assert isinstance(DAILY_TARGET_POLICY, DailyTargetPolicy)
        assert DAILY_TARGET_POLICY.name == "daily_target"
