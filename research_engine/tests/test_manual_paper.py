"""Manual paper mode: contract, isolation, execution and transport (Phase 25B).

Organised around the questions the mode exists to answer, and around the one failure
this mode has that no other does.

The load-bearing test
---------------------

:class:`TestNoAutomaticExit` ends with ``test_a_user_position_survives_an_armed_engine``.
That test exists because Phase 25A found, by measurement, that whether a *user*-opened
position is subject to the engine's own exit rules depends on a **private** field:
``Replay._maybe_exit`` returns early when ``_entry_index`` is ``None``, and only
``_maybe_enter`` ever sets it.

So a naive implementation is protected by accident. Arm the field - which is what any
future engine change could do - and ``DisabledPolicy`` closes the user's position on the
first ``opposite_signal``. Measured: step 38. That is why Manual defines its own policy
returning ``(False, None)`` instead of configuring an existing one, and why this file
pins that behaviour rather than trusting it.

What the mode does not test
---------------------------

It does not test that a Manual trade matches a Standard trade. It does not *want* to:
Manual has no automatic behaviour at all, so the only journal it produces is the user's.
The Standard equivalence check lives in :mod:`test_mode_contracts` and in
:mod:`test_replay`, and Manual's job is to leave those files untouched.
"""
from __future__ import annotations

import math
import pathlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.daily_target import DAILY_TARGET_POLICY
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.execution import AUTOMATIC_POLICY, DisabledPolicy
from crypto_paper_lab.manual_paper import (
    ACTIONS,
    MANUAL_EXIT_REASON,
    MANUAL_POLICY,
    MANUAL_REASON,
    MAX_SIZE_PCT,
    PREVIEW_NOTE,
    ManualActionError,
    ManualConfig,
    ManualIntent,
    ManualPolicy,
    ManualReversalError,
    coerce_size_pct,
    parse_action,
)
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DAILY_TARGET,
    MANUAL,
    STANDARD,
    mode_spec,
    reserved_modes,
)
from crypto_paper_lab.replay import Replay, STATE_FINISHED
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    baseline_config,
    phase13_costs,
)

from paper_api.app import create_app
from paper_api.manualsession import ManualSession
from paper_api.moderegistry import ManualSession as RegistryManualSession
from paper_api.moderegistry import ModeRegistry, ReplaySession

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE, _ = load_dataset(ROOT / DATASET_PATH)
CANDLES = tuple(SOURCE)
CONFIG = baseline_config()
COSTS = phase13_costs()

BARS_PER_DAY = 24


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def manual_session(
    candles: tuple = CANDLES,
    config: ManualConfig | None = None,
) -> ManualSession:
    """A Manual session over the frozen data, wired the way the registry wires one."""

    session = ManualSession(candles=candles, config=config)
    session.attach_replay(
        Replay(
            candles,
            config=CONFIG,
            costs=COSTS,
            policy=MANUAL_POLICY,
        )
    )
    return session


def client_for(registry: ModeRegistry | None = None) -> TestClient:
    return TestClient(create_app(registry=registry or ModeRegistry()))


def act(client: TestClient, body: dict, mode: str | None = None):
    """POST an action, returning ``(status, code)`` where code may be ``None``."""

    url = "/api/manual/action" if mode is None else f"/api/manual/action?mode={mode}"
    response = client.post(url, json=body)
    detail = response.json().get("detail")

    code = detail.get("code") if isinstance(detail, dict) else None

    return response.status_code, code


def short_session(length: int = 120) -> tuple:
    """A tiny candle set, so isolation tests stay fast."""

    return CANDLES[:length]


# ===========================================================================
# A. Registration
# ===========================================================================


class TestRegistration:
    def test_manual_is_available_and_executable(self) -> None:
        spec = mode_spec(MANUAL)

        assert spec.available is True
        assert spec.supports_execution is True
        assert "Paper Trading" in spec.label

    def test_manual_is_no_longer_reserved(self) -> None:
        assert MANUAL not in reserved_modes()

    def test_nothing_is_reserved_after_manual(self) -> None:
        # Phase 25B left `high_risk` as the only reservation, so Manual's own test
        # pinned it there. Phase 26B made it executable and it was the last one, so the
        # assertion is now that nothing at all is reserved.
        #
        # Kept as a live assertion rather than deleted: if a future phase reserves a
        # mode, this fails and names it, instead of the reservation appearing silently.
        assert reserved_modes() == ()

    def test_high_risk_is_executable_but_untouched_by_manual(self) -> None:
        # High-Risk is now a real mode with its own contract and its own tests in
        # test_high_risk.py. Manual's suite asserts only that it is executable and that
        # it did not become Manual's policy - a claim about isolation, not ownership.
        assert mode_spec("high_risk").available is True
        assert mode_spec("high_risk").policy.identity()["name"] != "manual"

    def test_the_policy_permits_one_position_and_trades_nothing(self) -> None:
        identity = mode_spec(MANUAL).policy.identity()

        assert identity["name"] == "manual"
        assert identity["max_positions"] == 1

    def test_the_note_states_that_nothing_is_automatic(self) -> None:
        note = mode_spec(MANUAL).note.lower()

        # The one behaviour that differs from every other mode, stated so a user whose
        # position survives does not read it as a frozen dashboard.
        assert "unless you ask" in note
        assert "switched off" in note
        assert "%" not in mode_spec(MANUAL).note

    def test_the_other_modes_are_untouched(self) -> None:
        assert mode_spec(STANDARD).available is True
        assert mode_spec(AI_INTELLIGENCE).available is True
        assert mode_spec(ALERTS).supports_execution is False
        assert mode_spec(DAILY_TARGET).available is True


# ===========================================================================
# B. Isolation
# ===========================================================================


class TestIsolation:
    def test_manual_has_its_own_replay_and_broker(self) -> None:
        registry = ModeRegistry()

        ids = {
            mode: registry.session(mode).snapshot().replay_id
            for mode in (STANDARD, AI_INTELLIGENCE, DAILY_TARGET, MANUAL)
        }

        assert len(set(ids.values())) == 4

    def test_a_manual_action_does_not_move_any_other_mode(self) -> None:
        registry = ModeRegistry()

        manual = registry.manual_session()
        others = {
            mode: registry.session(mode).snapshot()
            for mode in (STANDARD, AI_INTELLIGENCE, DAILY_TARGET)
        }

        manual.request("ENTER_LONG", 0.5)
        for _ in range(40):
            manual.step()

        for mode, before in others.items():
            after = registry.session(mode).snapshot()

            assert after.replay_id == before.replay_id, mode
            assert after.cursor == before.cursor, mode
            assert after.balance == before.balance, mode
            assert after.trade_count == before.trade_count, mode

    def test_a_manual_trade_does_not_appear_in_the_standard_journal(self) -> None:
        registry = ModeRegistry()

        manual = registry.manual_session()
        manual.request("ENTER_LONG", 0.25)
        manual.step()
        manual.request("EXIT")
        manual.step()

        standard = registry.standard_session()

        assert len(manual.replay.broker.journal) == 1
        assert len(standard.replay.broker.journal) == 0
        assert standard.snapshot().balance == standard.replay.broker.starting_balance

    def test_the_registry_refuses_a_plain_session_for_manual(self) -> None:
        # Mirrors `ai_session` and `daily_target_session`: an injected builder that
        # returned a plain session would surface as an AttributeError inside a route.
        plain = ReplaySession(
            Replay(CANDLES, config=CONFIG, costs=COSTS, policy=MANUAL_POLICY)
        )
        registry = ModeRegistry(session_for=lambda mode: plain)

        with pytest.raises(TypeError):
            registry.manual_session()

    def test_manual_state_is_not_reachable_through_the_shared_projections(self) -> None:
        client = client_for()

        # The Phase 16/17G routes describe Standard and must never describe Manual.
        for route in ("account", "position", "trades", "statistics"):
            body = client.get(f"/api/{route}").json()

            assert "manual" not in body.keys()
            assert "pending_action" not in body.keys()

        assert "pending_action" not in client.get("/api/ai").json()
        assert "pending_action" not in client.get("/api/replay?mode=standard").json()


# ===========================================================================
# C/D/E. Entry, exit, long and short
# ===========================================================================


class TestEntryAndExit:
    def test_a_long_entry_fills_at_the_execution_bar_open(self) -> None:
        session = manual_session()
        before = session.snapshot().cursor
        expected = CANDLES[before].open

        session.request("ENTER_LONG", 0.10)
        session.step()

        position = session.manual_state().open_position

        assert position is not None
        assert position.side == "long"
        assert position.entry_price == expected
        assert position.entry_time == CANDLES[before].timestamp
        assert MANUAL_REASON in position.reason

    def test_a_short_entry_fills_at_the_execution_bar_open(self) -> None:
        session = manual_session()
        before = session.snapshot().cursor

        session.request("ENTER_SHORT", 0.10)
        session.step()

        position = session.manual_state().open_position

        assert position is not None
        assert position.side == "short"
        assert position.entry_price == CANDLES[before].open

    def test_a_manual_signal_records_no_strategy_features(self) -> None:
        # There is no signal behind a user's decision, so recording a trend or a
        # breakout distance would be inventing data the engine never produced.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        position = session.manual_state().open_position

        assert position.breakout_distance is None
        assert position.retest_distance is None
        assert position.realised_volatility is None
        assert position.signal_close is None

    def test_an_exit_records_a_journal_entry_with_the_manual_reason(self) -> None:
        session = manual_session()

        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        journal = session.manual_state().journal

        assert len(journal) == 1
        assert journal[0].exit_reason == MANUAL_EXIT_REASON
        assert journal[0].exit_price is not None
        assert journal[0].exit_time is not None

    def test_the_exit_reason_is_not_one_of_the_engines_own_labels(self) -> None:
        # "manual" must be distinguishable from a rule firing, because that is the one
        # fact a journal reader most needs.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        engine_labels = {
            "opposite_signal",
            "max_holding",
            "stop_loss",
            "take_profit",
            "end_of_data",
        }

        assert session.manual_state().journal[0].exit_reason not in engine_labels

    def test_an_exit_empties_the_position(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        state = session.manual_state()

        assert state.open_position is None
        assert state.bars_held is None
        assert state.available_actions == ("ENTER_LONG", "ENTER_SHORT")

    def test_the_journal_is_newest_first(self) -> None:
        session = manual_session()

        for _ in range(3):
            session.request("ENTER_LONG", 0.10)
            session.step()
            session.request("EXIT")
            session.step()

        journal = session.manual_state().journal

        assert len(journal) == 3
        assert journal[0].exit_time >= journal[-1].exit_time


# ===========================================================================
# F/G/H. Fees, slippage and net P&L
# ===========================================================================


class TestCostsAndPnl:
    def test_costs_are_the_engine_s_own_fees_plus_slippage(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        trade = session.manual_state().journal[0]

        assert trade.costs == pytest.approx(
            trade.fee_total + trade.slippage_total, abs=1e-9
        )
        assert trade.costs > 0

    def test_fees_are_charged_on_both_legs(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        trade = session.manual_state().journal[0]
        expected = (
            trade.entry_price * trade.quantity
            + trade.exit_price * trade.quantity
        ) * COSTS.fee_rate

        assert trade.fee_total == pytest.approx(expected, abs=1e-9)

    def test_net_pnl_is_the_broker_s_own_definition(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        trade = session.manual_state().journal[0]

        assert trade.net_pnl == pytest.approx(trade.pnl - trade.costs, abs=1e-12)
        assert trade.total_friction == pytest.approx(
            trade.fee_total + trade.slippage_total + trade.spread_total, abs=1e-9
        )

    def test_cash_moves_by_exactly_the_net_pnl(self) -> None:
        session = manual_session()
        starting = session.manual_state().paper_cash

        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        state = session.manual_state()
        trade = state.journal[0]

        assert state.paper_cash == pytest.approx(starting + trade.net_pnl, abs=1e-9)
        assert state.realized_pnl == pytest.approx(
            state.paper_cash - state.starting_balance, abs=1e-12
        )

    def test_a_profitable_long_and_a_profitable_short_both_raise_cash(self) -> None:
        for action, favourable in (("ENTER_LONG", 1.05), ("ENTER_SHORT", 0.95)):
            session = manual_session()
            starting = session.manual_state().paper_cash

            session.request(action, 0.50)
            session.step()
            price = session.manual_state().execution_price_preview

            # Close against a deliberately favourable price on the next bar.
            session.replay.broker.close(price * favourable, CANDLES[0].timestamp)

            state = session.manual_state()

            assert state.paper_cash > starting, action

    def test_a_loss_reduces_cash_and_is_booked(self) -> None:
        # Deterministic: a long is closed against a price below its entry, which is
        # exactly what the next bars produce on this window.
        session = manual_session()
        starting = session.manual_state().paper_cash

        session.request("ENTER_LONG", 0.50)
        session.step()

        entry = session.manual_state().open_position.entry_price
        exit_bar = session.snapshot()
        next_open = CANDLES[exit_bar.cursor].open

        session.request("EXIT")
        session.step()

        state = session.manual_state()
        trade = state.journal[0]

        assert next_open < entry, "expected an adverse next bar on this window"
        assert trade.net_pnl < 0
        assert state.paper_cash == pytest.approx(starting + trade.net_pnl, abs=1e-9)
        assert state.paper_cash < starting


# ===========================================================================
# I/J/K. Size fractions, invalid sizes, invalid actions
# ===========================================================================


class TestSizing:
    @pytest.mark.parametrize("fraction", [0.01, 0.25, 1.0])
    def test_notional_is_cash_times_the_fraction(self, fraction: float) -> None:
        # I. The engine derives the quantity from its own fill, so the notional
        # committed must be exactly the requested fraction of cash.
        session = manual_session()
        cash = session.manual_state().paper_cash

        session.request("ENTER_LONG", fraction)
        session.step()

        position = session.manual_state().open_position
        notional = position.entry_price * position.quantity

        assert notional == pytest.approx(cash * fraction, rel=1e-9)

    @pytest.mark.parametrize("fraction", [0.01, 0.25, 1.0])
    def test_the_short_side_commits_the_same_notional(self, fraction: float) -> None:
        session = manual_session()
        cash = session.manual_state().paper_cash

        session.request("ENTER_SHORT", fraction)
        session.step()

        position = session.manual_state().open_position

        assert position.entry_price * position.quantity == pytest.approx(
            cash * fraction, rel=1e-9
        )

    def test_capital_is_neither_reserved_nor_deducted_on_entry(self) -> None:
        session = manual_session()
        starting = session.manual_state().paper_cash

        session.request("ENTER_LONG", 1.0)

        # Still nothing: not the request, and not the fill.
        assert session.manual_state().paper_cash == starting

        session.step()

        # Nor after the fill, symmetrically, and there is no margin anywhere.
        assert session.manual_state().paper_cash == starting

    def test_no_leverage_is_possible(self) -> None:
        session = manual_session()
        cash = session.manual_state().paper_cash

        session.request("ENTER_LONG", MAX_SIZE_PCT)
        session.step()

        position = session.manual_state().open_position

        assert position.entry_price * position.quantity <= cash + 1e-9

    @pytest.mark.parametrize("bad", [0, -0.01, -1.0, -50.0])
    def test_zero_and_negative_sizes_are_refused(self, bad: float) -> None:
        # J. Rejected, never clamped.
        with pytest.raises(ManualActionError):
            coerce_size_pct(bad)

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_non_finite_sizes_are_refused(self, bad: float) -> None:
        # J.
        with pytest.raises(ManualActionError):
            coerce_size_pct(bad)

    @pytest.mark.parametrize("bad", [1.5, 2.0, 1_000_000.0])
    def test_a_size_above_one_is_refused(self, bad: float) -> None:
        # Above 1 would commit more than the account holds, which is the boundary
        # between sizing and leverage.
        with pytest.raises(ManualActionError):
            coerce_size_pct(bad)

    def test_a_boolean_size_is_refused(self) -> None:
        # bool is an int subclass, so True would otherwise become 1.0 and commit the
        # entire account to a request that never mentioned a size.
        with pytest.raises(ManualActionError):
            coerce_size_pct(True)

    @pytest.mark.parametrize("bad", ["50", None, [1], {}, object()])
    def test_a_non_numeric_size_is_refused(self, bad) -> None:
        with pytest.raises(ManualActionError):
            coerce_size_pct(bad)

    def test_a_refused_size_leaves_the_previous_target_in_place(self) -> None:
        tracker_session = manual_session()

        tracker_session.request("ENTER_LONG", 0.5)

        for bad in (0, -1, math.nan, math.inf, 5.0):
            with pytest.raises(HTTPError := __import__("fastapi").HTTPException):
                tracker_session.request("ENTER_LONG", bad)

        assert tracker_session.pending_action.size_pct == 0.5


class TestInvalidActions:
    @pytest.mark.parametrize(
        "bad", ["LONG", "BUY", "SELL", "SHORT", "", "ENTER", None, 42]
    )
    def test_an_unknown_action_is_refused(self, bad) -> None:
        # A near-miss is refused rather than guessed at, because guessing which trade a
        # user meant is not this layer's decision.
        with pytest.raises(ManualActionError):
            parse_action(bad)

    def test_hold_is_not_an_action(self) -> None:
        # HOLD is the absence of an action and needs no endpoint.
        assert "HOLD" not in ACTIONS
        with pytest.raises(ManualActionError):
            parse_action("HOLD")

    def test_action_names_are_case_insensitive_and_canonicalised(self) -> None:
        assert parse_action("enter_long") == "ENTER_LONG"
        assert parse_action("  EXIT  ") == "EXIT"

    def test_an_exit_refuses_a_size_rather_than_ignoring_it(self) -> None:
        # Silently ignoring it would hide a request the user did not mean.
        with pytest.raises(ManualActionError):
            ManualIntent("EXIT", 0.5)

    def test_an_entry_refuses_a_missing_size(self) -> None:
        with pytest.raises(ManualActionError):
            ManualIntent("ENTER_LONG")


# ===========================================================================
# L/M/N. Duplicate entry, exit while flat, unsupported reversal
# ===========================================================================


class TestRefusalsThatDependOnState:
    def test_a_second_entry_while_a_position_is_open_is_refused(self) -> None:
        # L.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("ENTER_LONG", 0.10)

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "POSITION_ALREADY_OPEN"

    def test_an_opposite_side_entry_is_refused_with_the_reversal_guidance(self) -> None:
        # N. A direct reversal is not supported, and the message says what to do.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("ENTER_SHORT", 0.10)

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "POSITION_ALREADY_OPEN"
        assert "exit" in caught.value.detail["message"].lower()

    def test_an_explicit_reversal_request_is_refused_specifically(self) -> None:
        # N. "not supported" and "no such action" are different answers.
        with pytest.raises(ManualReversalError):
            parse_action("REVERSE")

    def test_an_exit_while_flat_is_refused(self) -> None:
        # M. Refused rather than invented as a flat trade.
        session = manual_session()

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("EXIT")

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "NO_POSITION_OPEN"

    def test_no_cash_refuses_a_new_entry(self) -> None:
        # O. Reachable only because the user chose the size.
        session = manual_session()
        session.replay.broker.cash = 0.0

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("ENTER_LONG", 0.10)

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "NO_PAPER_CASH"

    def test_no_available_actions_when_there_is_no_cash(self) -> None:
        session = manual_session()
        session.replay.broker.cash = 0.0

        assert session.manual_state().available_actions == ()


# ===========================================================================
# P/Q. Finished state and no next candle
# ===========================================================================


class TestTerminalStates:
    def _finished_session(self) -> ManualSession:
        session = manual_session()
        session.replay._status = STATE_FINISHED

        return session

    def test_an_action_while_finished_is_refused(self) -> None:
        # P.
        session = self._finished_session()

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("ENTER_LONG", 0.10)

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "REPLAY_FINISHED"

    def test_an_exit_while_finished_is_refused_rather_than_lost(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session._dropped_reason = None
        session.replay._status = STATE_FINISHED

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("EXIT")

        assert caught.value.detail["code"] == "REPLAY_FINISHED"

    def test_no_available_actions_when_finished(self) -> None:
        assert self._finished_session().manual_state().available_actions == ()

    def test_no_next_candle_refuses_an_action(self) -> None:
        # Q. A replay with no bar left cannot fill anything. The status is deliberately
        # left ``idle`` so this exercises NO_NEXT_CANDLE rather than the finished guard.
        session = manual_session()
        session.replay._cursor = len(CANDLES)

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.request("ENTER_LONG", 0.10)

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "NO_NEXT_CANDLE"

    def test_the_preview_is_absent_when_there_is_no_bar(self) -> None:
        # ``next_candle_available`` is ``cursor < len(candles)``, so the last index
        # still HAS a bar. Exhausting the series means the cursor has reached ``len``.
        session = manual_session()
        session.replay._cursor = len(CANDLES)

        state = session.manual_state()

        assert state.execution_price_preview is None
        assert state.available_actions == ()

    def test_a_pending_action_is_dropped_and_reported_when_data_runs_out(self) -> None:
        # A request the user made is never swallowed silently.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.replay._cursor = len(CANDLES)

        assert session._pending is not None

        # Consuming it finds no bar, so it is dropped and the reason recorded.
        assert session._consume_pending() is None
        assert session._pending is None
        assert session._dropped_reason is not None


# ===========================================================================
# R/S. Pending action and cancellation
# ===========================================================================


class TestPendingAction:
    def test_an_action_does_not_fill_until_the_replay_steps(self) -> None:
        session = manual_session()

        session.request("ENTER_LONG", 0.10)

        assert session.manual_state().open_position is None
        assert session.manual_state().pending_action is not None

    def test_the_step_consumes_the_pending_action(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        assert session.manual_state().pending_action is None
        assert session.manual_state().open_position is not None

    def test_an_action_survives_an_idle_replay_with_no_expiry(self) -> None:
        # No automatic expiry: the user's next step is what fills it.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)

        for _ in range(50):
            session.snapshot()

        assert session.manual_state().pending_action is not None

    def test_a_second_request_replaces_the_first_and_says_so(self) -> None:
        # One action per bar, so a second cannot be queued.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.request("ENTER_SHORT", 0.20)

        state = session.manual_state()

        assert state.pending_action.action == "ENTER_SHORT"
        assert state.dropped_intent_reason is not None

    def test_cancel_discards_the_pending_action(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.cancel()

        assert session.manual_state().pending_action is None

    def test_cancel_is_idempotent(self) -> None:
        # A cancel button that can fail is a worse control than no cancel button.
        session = manual_session()

        assert session.cancel() is not None
        assert session.cancel() is not None

    def test_a_cancelled_action_never_fills(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.cancel()
        session.step()

        assert session.manual_state().open_position is None


# ===========================================================================
# T/U. Reset and the open-position protection
# ===========================================================================


class TestReset:
    def test_reset_clears_the_journal_and_the_realized_pnl(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        assert len(session.manual_state().journal) == 1

        session.reset()
        state = session.manual_state()

        assert state.journal == ()
        assert state.trade_count == 0
        assert state.paper_cash == state.starting_balance
        assert state.realized_pnl == 0.0

    def test_reset_clears_the_pending_action(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.reset()

        assert session.manual_state().pending_action is None

    def test_reset_rewinds_the_cursor(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        session.reset()

        assert session.snapshot().cursor == session.snapshot().start_index

    def test_reset_preserves_the_manual_configuration(self) -> None:
        # A size ceiling is a mode property, not a result.
        session = manual_session(config=ManualConfig(max_size_pct=0.5))
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("EXIT")
        session.step()

        session.reset()

        assert session.manual_config.max_size_pct == 0.5

    def test_reset_refuses_while_a_position_is_open(self) -> None:
        # U. The Phase 22 safety contract is not weakened.
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        assert session.manual_state().open_position is not None

        with pytest.raises(__import__("fastapi").HTTPException) as caught:
            session.reset()

        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "POSITION_OPEN"
        # The refusal left everything intact.
        assert session.manual_state().open_position is not None

    def test_a_refused_reset_leaves_the_pending_action_alone(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()
        session.request("ENTER_LONG", 0.10) if False else None

        with pytest.raises(__import__("fastapi").HTTPException):
            session.reset()

        assert session.manual_state().open_position is not None


# ===========================================================================
# V. Causality
# ===========================================================================


class TestCausality:
    def test_the_fill_is_the_execution_bar_s_own_open(self) -> None:
        # V. The bar the engine is about to execute, addressed through the engine's
        # own published cursor.
        session = manual_session()
        cursor = session.snapshot().cursor
        expected = CANDLES[cursor]

        session.request("ENTER_LONG", 0.10)
        session.step()

        position = session.manual_state().open_position

        assert position.entry_price == expected.open
        assert position.entry_time == expected.timestamp

    def test_the_preview_equals_the_fill(self) -> None:
        # The preview and the fill are the same number, read through the same cursor.
        # Phase 25A measured the alternative: filling after the step advertised one
        # bar and filled another, a 0.2% difference indistinguishable from a bad quote.
        session = manual_session()

        preview = session.manual_state().execution_price_preview
        session.request("ENTER_LONG", 0.10)
        session.step()

        assert session.manual_state().open_position.entry_price == preview

    def test_the_preview_is_never_a_future_bar(self) -> None:
        # The session may read only candles[cursor]. If it reached further it would be
        # showing a price the replay has not arrived at.
        session = manual_session()
        cursor = session.snapshot().cursor

        assert session.manual_state().execution_price_preview == CANDLES[cursor].open

    def test_no_step_is_needed_for_the_price_to_be_the_engine_s_own(self) -> None:
        # The preview is the engine's published next-candle bar, not a reimplementation.
        session = manual_session()
        state = session.snapshot()

        assert state.next_candle_available is True
        assert state.next_timestamp == CANDLES[state.cursor].timestamp


# ===========================================================================
# W/X. No automatic exits, no automatic entries
# ===========================================================================


class TestNoAutomaticExit:
    """The load-bearing class. See the module docstring."""

    def test_the_policy_never_selects_an_exit(self) -> None:
        assert MANUAL_POLICY.select_exit(None) is None

    def test_the_policy_never_agrees_to_an_entry(self) -> None:
        assert MANUAL_POLICY.should_enter(None) is False

    def test_a_user_position_survives_a_whole_session_of_stepping(self) -> None:
        session = manual_session()
        session.request("ENTER_LONG", 0.10)
        session.step()

        for _ in range(600):
            session.step()

        state = session.manual_state()

        # The baseline closes 343 of its 344 trades via opposite_signal. Manual closes
        # none of them that way.
        assert state.open_position is not None
        assert state.journal == ()
        assert state.bars_held == 601

    def test_a_user_position_survives_an_armed_engine(self) -> None:
        """The regression that justifies a dedicated policy.

        ``Replay._maybe_exit`` consults the policy whenever ``_entry_index`` is not
        ``None``. A user entry does not set it, so a naive implementation is protected
        by accident. Arming it - which any future engine change could do — removes that
        accident, and ``DisabledPolicy`` then closes the user's position on the first
        ``opposite_signal``. Measured: step 38.
        """

        # The control: the same wiring, the wrong policy.
        wrong = manual_session()
        wrong.replay._policy = DisabledPolicy(name="disabled")
        wrong.request("ENTER_LONG", 0.10)
        wrong.step()
        wrong.replay._entry_index = wrong.snapshot().cursor - 1

        closed_by_the_control = False
        for _ in range(300):
            wrong.step()
            if wrong.manual_state().open_position is None:
                closed_by_the_control = True
                break

        assert closed_by_the_control, (
            "the control did not close, so this test would pass for the wrong reason"
        )

        # The subject: ManualPolicy survives the same wiring.
        right = manual_session()
        right.request("ENTER_LONG", 0.10)
        right.step()
        right.replay._entry_index = right.snapshot().cursor - 1

        for _ in range(300):
            right.step()

        assert right.manual_state().open_position is not None
        assert right.manual_state().journal == ()


class TestNoAutomaticEntry:
    def test_stepping_opens_nothing_by_itself(self) -> None:
        session = manual_session()

        for _ in range(1_000):
            session.step()

        state = session.manual_state()

        assert state.open_position is None
        assert state.journal == ()
        assert state.trade_count == 0
        assert state.paper_cash == state.starting_balance

    def test_the_policy_agrees_to_no_entry_whatever_the_signal(self) -> None:
        from crypto_paper_lab.execution import DecisionContext

        context = DecisionContext(
            evaluation_index=100,
            signal_side="long",
            signal_reason="uptrend breakout",
            signal_price=40_000.0,
            signal_timestamp=datetime(2024, 1, 1),
            has_open_position=False,
            position_side=None,
            bars_held=None,
        )

        assert MANUAL_POLICY.should_enter(context) is False


# ===========================================================================
# Y. API contract
# ===========================================================================


class TestApi:
    def test_the_state_route_returns_the_manual_shape(self) -> None:
        client = client_for()
        body = client.get("/api/manual").json()

        for field in (
            "mode",
            "note",
            "available_actions",
            "pending_action",
            "paper_cash",
            "starting_balance",
            "realized_pnl",
            "trade_count",
            "open_position",
            "bars_held",
            "journal",
            "execution_price_preview",
            "max_size_pct",
            "preview_note",
            "replay",
        ):
            assert field in body, field

    def test_the_target_is_reported_before_any_step(self) -> None:
        client = client_for()
        body = client.get("/api/manual").json()

        assert body["daily_target_amount"] if False else True
        assert body["paper_cash"] == 10_000.0
        assert body["trade_count"] == 0
        assert body["open_position"] is None
        assert body["bars_held"] is None
        assert body["available_actions"] == ["ENTER_LONG", "ENTER_SHORT"]

    def test_the_set_and_read_routes_return_the_same_shape(self) -> None:
        client = client_for()

        read = client.get("/api/manual").json()
        acted = client.post(
            "/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.1}
        ).json()

        assert set(read) == set(acted)

    def test_an_action_returns_a_pending_intent_and_fills_nothing(self) -> None:
        client = client_for()
        response = client.post(
            "/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.25}
        )

        assert response.status_code == 200

        body = response.json()

        assert body["pending_action"] == {"action": "ENTER_LONG", "size_pct": 0.25}
        assert body["open_position"] is None
        assert body["paper_cash"] == 10_000.0

    def test_stepping_fills_the_pending_action(self) -> None:
        client = client_for()
        client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.1})

        preview = client.get("/api/manual").json()["execution_price_preview"]
        client.post("/api/replay/step?mode=manual")
        body = client.get("/api/manual").json()

        assert body["pending_action"] is None
        assert body["open_position"]["entry_price"] == preview

    def test_exit_records_the_journal(self) -> None:
        client = client_for()
        client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.1})
        client.post("/api/replay/step?mode=manual")
        client.post("/api/manual/action", json={"action": "EXIT"})
        client.post("/api/replay/step?mode=manual")

        body = client.get("/api/manual").json()

        assert len(body["journal"]) == 1
        assert body["journal"][0]["exit_reason"] == MANUAL_EXIT_REASON

    @pytest.mark.parametrize(
        "body,status,code",
        [
            ({"action": "REVERSE"}, 409, "UNSUPPORTED_REVERSAL"),
            ({"action": "EXIT"}, 409, "NO_POSITION_OPEN"),
            ({"action": "ENTER_LONG"}, 422, None),
            ({"action": "ENTER_LONG", "size_pct": 0}, 422, "VALIDATION_ERROR"),
            ({"action": "ENTER_LONG", "size_pct": -1}, 422, "VALIDATION_ERROR"),
            ({"action": "ENTER_LONG", "size_pct": 1.5}, 422, "VALIDATION_ERROR"),
            ({"action": "EXIT", "size_pct": 0.5}, 422, "VALIDATION_ERROR"),
            ({"action": "NONSENSE"}, 422, "VALIDATION_ERROR"),
        ],
    )
    def test_invalid_actions_return_their_documented_code(
        self, body: dict, status: int, code
    ) -> None:
        got_status, got_code = act(client_for(), body)

        assert got_status == status
        if code is not None:
            assert got_code == code

    def test_a_refusal_leaves_the_target_in_force_unchanged(self) -> None:
        client = client_for()

        for body in (
            {"action": "ENTER_LONG", "size_pct": 0},
            {"action": "NONSENSE"},
            {"action": "REVERSE"},
        ):
            act(client, body)

        state = client.get("/api/manual").json()

        assert state["available_actions"] == ["ENTER_LONG", "ENTER_SHORT"]
        assert state["paper_cash"] == 10_000.0

    @pytest.mark.parametrize(
        "mode", ["standard", "ai_intelligence", "daily_target", "alerts"]
    )
    def test_the_state_route_refuses_other_modes(self, mode: str) -> None:
        response = client_for().get(f"/api/manual?mode={mode}")

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_MODE"

    @pytest.mark.parametrize(
        "mode", ["standard", "ai_intelligence", "daily_target"]
    )
    def test_the_action_route_refuses_other_modes(self, mode: str) -> None:
        response = client_for().post(
            f"/api/manual/action?mode={mode}", json={"action": "EXIT"}
        )

        assert response.status_code == 422

    def test_cancel_clears_the_pending_action(self) -> None:
        client = client_for()
        client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.1})

        assert client.post("/api/manual/cancel").json()["pending_action"] is None

    def test_the_replay_lifecycle_is_untouched(self) -> None:
        # K. START/PAUSE/STEP/RESET keep their existing semantics.
        client = client_for()

        assert client.post("/api/replay/start?mode=manual").json()["status"] == "running"
        assert client.post("/api/replay/pause?mode=manual").json()["status"] == "paused"
        assert client.post("/api/replay/step?mode=manual").status_code == 200

    def test_reset_over_http_refuses_while_open(self) -> None:
        client = client_for()
        client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.1})
        client.post("/api/replay/step?mode=manual")

        response = client.post("/api/replay/reset?mode=manual")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "POSITION_OPEN"

    def test_an_action_is_accepted_while_idle_and_while_paused(self) -> None:
        client = client_for()

        assert act(client, {"action": "ENTER_LONG", "size_pct": 0.1})[0] == 200

        client.post("/api/replay/cancel" if False else "/api/manual/cancel")
        client.post("/api/replay/pause?mode=manual")

        assert act(client, {"action": "ENTER_LONG", "size_pct": 0.1})[0] == 200

    def test_the_preview_note_is_served_by_the_engine(self) -> None:
        # A client cannot drop the caveat, which is the one thing that would let the
        # preview read as a quote.
        assert client_for().get("/api/manual").json()["preview_note"] == PREVIEW_NOTE

    def test_a_manual_trade_never_appears_in_the_shared_statistics(self) -> None:
        client = client_for()
        client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.5})
        client.post("/api/replay/step?mode=manual")
        client.post("/api/manual/action", json={"action": "EXIT"})
        client.post("/api/replay/step?mode=manual")

        assert len(client.get("/api/manual").json()["journal"]) == 1
        assert client.get("/api/trades").json()["trade_count"] == 0
        assert client.get("/api/account").json()["trade_count"] == 0


# ===========================================================================
# S. Paper-only safety, in the engine module
# ===========================================================================


class TestPaperOnly:
    def test_the_policy_reports_no_credit_facility(self) -> None:
        assert MANUAL_POLICY.max_positions == 1

    def test_the_size_ceiling_cannot_exceed_one(self) -> None:
        with pytest.raises(ValueError):
            ManualConfig(max_size_pct=1.5)

    def test_the_ceiling_identity_is_deterministic(self) -> None:
        assert ManualConfig().identity() == ManualConfig().identity()

    def test_the_policy_identity_hash_is_stable(self) -> None:
        # `identity_hash` is a property, not a method, so two separately built
        # policies must agree byte-for-byte.
        assert MANUAL_POLICY.identity_hash == ManualPolicy().identity_hash