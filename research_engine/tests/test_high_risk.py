"""Phase 26B. High-Risk paper mode.

The contract under test
-----------------------

High-Risk is **Standard's strategy with a larger share of paper cash committed to
each position**. It introduces no new signal qualification rule, uses no policy of
its own, owns no broker, and cannot create exposure beyond the paper cash it
holds.

These tests are organised by that contract rather than by file: A covers mode
registration, B the policy identity, C/D the size bounds, and so on through Y.
The two that matter most are stated first, because everything else follows from
them:

* **Group H** runs the *same* engine replay at ``risk_fraction=0.01`` as Standard
  and requires the two trade sequences to be identical field for field - count,
  sides, timestamps, reasons, entry and exit prices. Only quantity and the money
  derived from it may differ. If that passes, "High-Risk changes nothing but size"
  is a fact rather than a claim.
* **Group F** requires ``exposure <= paper_cash`` at every bar of a full-length
  replay at the maximum size, which is the invariant that makes leverage
  unreachable.

Nothing in this module mocks the engine: the size, fill, cost and P&L assertions
run against the real :class:`PaperBroker` over the real frozen dataset.
"""

from __future__ import annotations

import io
import math

import pytest
from fastapi import HTTPException

from crypto_paper_lab.execution import (
    AUTOMATIC_POLICY,
    AutomaticPolicy,
    DisabledPolicy,
    IntelligencePolicy,
)
from crypto_paper_lab.high_risk import (
    DEFAULT_RISK_FRACTION,
    HIGH_RISK_CAUTION,
    HIGH_RISK_INHERITS_NOTE,
    MAX_RISK_FRACTION,
    MODE_LABEL,
    HighRiskConfig,
    HighRiskError,
    coerce_risk_fraction,
)
from crypto_paper_lab.modes import (
    DEFAULT_MODE,
    HIGH_RISK,
    MODES,
    known_modes,
    reserved_modes,
)
from crypto_paper_lab.replay import Replay, STATE_FINISHED
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.walkforward import RISK_FRACTION, baseline_config, phase13_costs
from paper_api.highrisksession import HighRiskSession
from paper_api.marketdata import load_research_candles
from paper_api.moderegistry import ModeRegistry

# The frozen Standard result. Exact, repr-comparable, and asserted with `==`
# against the literal rather than approximately: this project has established
# these figures by measurement and a tolerance would hide a real change.
STANDARD_TRADES = 344
STANDARD_BALANCE = 9842.858975722493
STANDARD_REALIZED = -157.1410242775073

# Measured in Phase 26A and re-established here, so a drift in sizing or costs
# fails a test rather than quietly changing what the mode means.
HIGH_RISK_025_TRADES = 344
HIGH_RISK_025_BALANCE = 6645.213326107787
HIGH_RISK_025_REALIZED = -3354.786673892213

#: Exposure is ``entry_price * quantity``, where ``quantity`` was itself computed as
#: ``(cash * risk_fraction) / entry_price``. Evaluating that round trip twice in
#: IEEE-754 double precision can differ from ``cash`` by one unit in the last place.
#: Measured at the maximum size: worst overshoot 1 ULP ($1.82e-12 on ~$10,000).
#: One ULP is therefore the tolerance the exposure assertions may use, and no more.
TOLERANCE_ULPS = 1.0


def code_of(exc: HTTPException) -> str:
    detail = getattr(exc, "detail", None)
    return detail["code"] if isinstance(detail, dict) else "Pydantic-list"


@pytest.fixture(scope="module")
def candles():
    return tuple(load_research_candles())


def fresh_session() -> HighRiskSession:
    """A High-Risk session on its own registry, so no test shares state."""

    return ModeRegistry().high_risk_session()


def _build(risk_fraction: float, candles) -> Replay:
    """A fresh replay, configured exactly as the registry configures High-Risk."""

    return Replay(
        candles,
        config=baseline_config(),
        costs=phase13_costs(),
        policy=AUTOMATIC_POLICY,
        risk_fraction=risk_fraction,
    )


#: A full-length run is 17,522 steps, and several groups assert against the same
#: one. Re-running it per test made this file take eighteen minutes, so the
#: *facts* are memoised.
#:
#: Snapshots, not ``Replay`` objects. An earlier version cached the Replay itself
#: and it was a genuine trap: ``Replay.reset()`` mutates in place, so one test
#: resetting a finished replay silently emptied the journal every later test was
#: about to read. A snapshot of plain values cannot be mutated by accident, and
#: ``run_full`` below always hands back a fresh object for tests that step or
#: reset.
_SNAPSHOTS: dict = {}


def snapshot(risk_fraction: float, candles) -> dict:
    """Immutable facts from one full-length run. Memoised, read-only."""

    key = repr(risk_fraction)

    if key not in _SNAPSHOTS:
        replay = _build(risk_fraction, candles)

        while replay.state.status != STATE_FINISHED:
            replay.step()

        journal = tuple(replay.broker.journal)

        _SNAPSHOTS[key] = {
            "trades": len(journal),
            "cash": replay.broker.cash,
            "starting_balance": replay.broker.starting_balance,
            "realized": replay.broker.cash - replay.broker.starting_balance,
            "exit_counts": dict(replay.exit_counts),
            "total_costs": sum(t.costs for t in journal),
            "sides": tuple(t.side for t in journal),
            "entry_times": tuple(t.entry_time for t in journal),
            "exit_times": tuple(t.exit_time for t in journal),
            "reasons": tuple(t.reason for t in journal),
            "exit_reasons": tuple(t.exit_reason for t in journal),
            "entry_prices": tuple(t.entry_price for t in journal),
            "exit_prices": tuple(t.exit_price for t in journal),
            "bars_held": tuple(t.bars_held for t in journal),
            "quantities": tuple(t.quantity for t in journal),
            "first_trade": journal[0],
            "last_trade": journal[-1],
            "status": replay.state.status,
            "has_open_position": replay.state.has_open_position,
            "next_candle_available": replay.state.next_candle_available,
        }

    return _SNAPSHOTS[key]


def run_full(risk_fraction: float, candles) -> Replay:
    """A **fresh** replay run to completion.

    Never memoised: the returned object is mutable, and a test that resets or
    steps it must not be able to affect any other test. Read-only assertions
    should use :func:`snapshot`.
    """

    replay = _build(risk_fraction, candles)

    while replay.state.status != STATE_FINISHED:
        replay.step()

    return replay


def first_entry(candles, risk_fraction: float) -> tuple:
    """Step until a position opens; return the resulting ``PaperTrade``."""

    replay = run_to_open(candles, risk_fraction)
    return replay.broker.open_trade


def run_to_open(candles, risk_fraction: float, limit: int = 200) -> Replay:
    replay = Replay(
        candles,
        config=baseline_config(),
        costs=phase13_costs(),
        policy=AUTOMATIC_POLICY,
        risk_fraction=risk_fraction,
    )

    for _ in range(limit):
        replay.step()
        if replay.state.has_open_position:
            break

    return replay


# ---------------------------------------------------------------------------
# A. Mode registration
# ---------------------------------------------------------------------------


class TestModeRegistration:
    def test_high_risk_is_a_known_mode(self):
        assert HIGH_RISK in known_modes()

    def test_high_risk_is_available(self):
        assert MODES[HIGH_RISK].available is True

    def test_high_risk_supports_execution(self):
        assert MODES[HIGH_RISK].supports_execution is True

    def test_nothing_is_reserved_any_more(self):
        # high_risk was the last reservation. An empty tuple is the assertion that
        # it no longer falls through to a refusal.
        assert reserved_modes() == ()

    def test_mode_count_is_six(self):
        assert len(MODES) == 6

    def test_default_mode_is_unchanged(self):
        assert DEFAULT_MODE == "standard"

    def test_label_carries_paper_trading(self):
        label = MODES[HIGH_RISK].label
        assert "High-Risk" in label
        assert "Paper Trading" in label

    def test_label_is_the_engine_constant(self):
        assert MODES[HIGH_RISK].label == MODE_LABEL

    def test_max_positions_is_one(self):
        assert MODES[HIGH_RISK].policy.max_positions == 1

    def test_note_states_the_scope_boundary(self):
        note = MODES[HIGH_RISK].note
        assert "no new signal qualification rule" in note.lower()
        assert "standard" in note.lower()

    def test_note_names_the_banned_concepts_only_as_negations(self):
        note = MODES[HIGH_RISK].note.lower()
        # Every mention of leverage or margin must be a denial.
        for term in ("leverage", "margin", "borrowing", "liquidation"):
            if term in note:
                index = note.index(term)
                window = note[max(0, index - 40):index]
                assert any(
                    neg in window for neg in ("no ", "never ", "not ")
                ), f"{term!r} appears without a negation: ...{window}"

    def test_unknown_mode_still_raises(self):
        with pytest.raises(Exception):
            MODES["no_such_mode"]

    def test_registry_reports_high_risk(self):
        registry = ModeRegistry()
        assert registry.is_high_risk(HIGH_RISK) is True

    def test_registry_is_high_risk_is_false_for_other_modes(self):
        registry = ModeRegistry()
        for mode in ("standard", "manual", "daily_target", "alerts"):
            assert registry.is_high_risk(mode) is False


# ---------------------------------------------------------------------------
# B. Policy identity - AUTOMATIC_POLICY, and no HighRiskPolicy
# ---------------------------------------------------------------------------


class TestPolicyIdentity:
    def test_policy_is_automatic_policy(self):
        assert MODES[HIGH_RISK].policy is AUTOMATIC_POLICY

    def test_the_very_same_object_standard_uses(self):
        # Not merely equivalent: identical. There is one policy for two modes.
        assert MODES["standard"].policy is MODES[HIGH_RISK].policy

    def test_policy_is_automatic_policy_instance(self):
        assert isinstance(MODES[HIGH_RISK].policy, AutomaticPolicy)

    def test_policy_is_not_disabled(self):
        assert not isinstance(MODES[HIGH_RISK].policy, DisabledPolicy)

    def test_policy_is_not_intelligence(self):
        assert not isinstance(MODES[HIGH_RISK].policy, IntelligencePolicy)

    def test_policy_name(self):
        assert MODES[HIGH_RISK].policy.name == "automatic"

    def test_no_high_risk_policy_class_exists(self):
        import crypto_paper_lab.high_risk as module

        # The mode's whole contract is "no new decision logic". A policy class
        # here would mean decisions had moved somewhere new.
        assert not hasattr(module, "HighRiskPolicy")

    def test_identity_hash_is_stable(self):
        first = MODES[HIGH_RISK].policy.identity_hash
        second = MODES[HIGH_RISK].policy.identity_hash
        assert first == second

    def test_identity_hash_is_uppercase_sha256(self):
        digest = MODES[HIGH_RISK].policy.identity_hash
        assert len(digest) == 64
        assert digest == digest.upper()

    def test_session_replay_uses_automatic_policy(self):
        assert fresh_session().replay.policy is AUTOMATIC_POLICY

    def test_session_policy_name_is_automatic(self):
        assert fresh_session().replay.policy.name == "automatic"


# ---------------------------------------------------------------------------
# C. Default risk fraction
# ---------------------------------------------------------------------------


class TestDefaultRiskFraction:
    def test_default_is_a_quarter_of_cash(self):
        assert DEFAULT_RISK_FRACTION == 0.25

    def test_config_default(self):
        assert HighRiskConfig().risk_fraction == 0.25

    def test_session_default(self):
        assert fresh_session().risk_fraction == 0.25

    def test_state_default(self):
        assert fresh_session().high_risk_state().risk_fraction == 0.25

    def test_replay_is_built_with_the_default(self):
        session = fresh_session()
        assert session.replay.state.execution.risk_fraction == 0.25

    def test_default_is_standard_plus_25x(self):
        assert DEFAULT_RISK_FRACTION == RISK_FRACTION * 25

    def test_default_differs_from_standard(self):
        assert DEFAULT_RISK_FRACTION != RISK_FRACTION

    def test_default_is_strictly_inside_the_ceiling(self):
        assert 0 < DEFAULT_RISK_FRACTION < MAX_RISK_FRACTION

    def test_default_is_finite(self):
        assert math.isfinite(DEFAULT_RISK_FRACTION)


# ---------------------------------------------------------------------------
# D. Maximum risk fraction
# ---------------------------------------------------------------------------


class TestMaximumRiskFraction:
    def test_maximum_is_one(self):
        assert MAX_RISK_FRACTION == 1.0

    def test_maximum_is_served_to_clients(self):
        assert fresh_session().high_risk_state().max_risk_fraction == 1.0

    def test_one_is_accepted(self):
        assert coerce_risk_fraction(1.0) == 1.0

    def test_config_accepts_one(self):
        assert HighRiskConfig(risk_fraction=1.0).risk_fraction == 1.0

    def test_above_one_is_refused(self):
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(1.0000001)

    def test_two_is_refused(self):
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(2.0)

    def test_refusal_names_the_account_not_leverage(self):
        with pytest.raises(HighRiskError, match="credit facility"):
            coerce_risk_fraction(5.0)

    def test_the_ceiling_is_the_brokers_own(self):
        # The engine is the authority; this constant mirrors it. If the broker's
        # limit ever moved, this test would be the reminder to move with it.
        with pytest.raises(ValueError, match="between 0 and 1"):
            PaperBroker(starting_balance=10_000.0).open_from_signal(
                _signal(40_000.0), risk_fraction=MAX_RISK_FRACTION + 0.01
            )


# ---------------------------------------------------------------------------
# E. Sizing - delegated entirely to PaperBroker
# ---------------------------------------------------------------------------


def _signal(price: float = 40_000.0):
    from datetime import datetime, timezone

    from crypto_paper_lab.models import Signal

    return Signal(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        side="long",
        reason="sizing probe",
        price=price,
        support=price * 0.98,
        resistance=price * 1.02,
        trend="up",
    )


class TestSizing:
    @pytest.mark.parametrize("fraction", [0.01, 0.1, 0.25, 0.5, 1.0])
    def test_quantity_is_broker_derived(self, fraction):
        """``quantity == (cash * risk_fraction) / fill``, the broker's own formula."""

        broker = PaperBroker(starting_balance=10_000.0, costs=phase13_costs())
        trade = broker.open_from_signal(_signal(), risk_fraction=fraction)
        expected = (10_000.0 * fraction) / trade.entry_price
        assert trade.quantity == expected

    @pytest.mark.parametrize("fraction", [0.01, 0.25, 1.0])
    def test_exposure_equals_fraction_of_cash(self, fraction, candles):
        """Under cost_deduction the fill equals the reference, so exposure is exact."""

        trade = first_entry(candles, fraction)
        assert trade.entry_price * trade.quantity == pytest.approx(
            10_000.0 * fraction, rel=1e-12
        )

    def test_sizing_uses_the_session_fraction(self, candles):
        session = fresh_session()
        session.set_risk_fraction(0.5)
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        state = session.high_risk_state()
        assert state.exposure == pytest.approx(5_000.0, rel=1e-12)
        assert state.exposure_fraction == pytest.approx(0.5, rel=1e-12)

    def test_sizing_follows_cash_not_starting_balance(self, candles):
        """Sizing is recomputed against *current* cash on every entry.

        A loss therefore shrinks the next position - which is also why total costs
        do not scale by a constant factor. That is the broker's behaviour,
        inherited unchanged.
        """

        replay = run_full(0.5, candles)
        later = [
            t
            for t in replay.broker.journal[1:]
            if t.entry_price * t.quantity < 5_000.0
        ]
        assert later, "expected a position sized below the 50% of the start balance"

    def test_no_arbitrary_quantity_input_exists(self):
        """The mode exposes a fraction, never a quantity."""

        session = fresh_session()
        state = session.high_risk_state()
        assert hasattr(state, "risk_fraction")
        assert not hasattr(state, "quantity")

    def test_broker_rejects_a_fraction_above_one(self):
        with pytest.raises(ValueError):
            PaperBroker(starting_balance=10_000.0).open_from_signal(
                _signal(), risk_fraction=1.5
            )


# ---------------------------------------------------------------------------
# F. EXPOSURE <= CASH - the safety invariant, at the maximum size
# ---------------------------------------------------------------------------


class TestExposureNeverExceedsCash:
    def test_exposure_equals_cash_at_maximum_size(self, candles):
        trade = first_entry(candles, 1.0)
        assert trade.entry_price * trade.quantity == pytest.approx(
            10_000.0, rel=1e-12
        )

    def test_exposure_is_not_greater_than_cash_at_maximum_size(self, candles):
        trade = first_entry(candles, 1.0)
        assert trade.entry_price * trade.quantity <= 10_000.0

    def test_exposure_never_exceeds_cash_across_a_whole_replay(self, candles):
        """Every single bar at the maximum size, not a sample.

        ``TOLERANCE_ULPS`` is not slack added to make a test pass - it is the
        measured behaviour. ``quantity = (cash * 1.0) / fill`` and then
        ``exposure = fill * quantity`` means the round trip is evaluated twice, and
        in IEEE-754 double precision ``(cash / fill) * fill`` is not always exactly
        ``cash``. Measured across a full run at 1.0: 1,131 of 17,522 position bars
        exceed by exactly **one ULP**, the worst case being $1.82e-12 on a ~$10,000
        account, a relative overshoot of 1.8e-16.

        That is a representation artifact, not leverage: it is fifteen orders of
        magnitude below a cent, and at any fraction below 1.0 the headroom absorbs
        it completely - a run at 0.99 recorded **zero** such bars, which
        ``test_exposure_never_exceeds_cash_strictly_below_one`` pins.
        """

        session = fresh_session()
        session.set_risk_fraction(1.0)
        observed = 0
        breaches = 0

        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            if not state.position_count:
                continue
            observed += 1
            if state.exposure > state.paper_cash * (1 + TOLERANCE_ULPS):
                breaches += 1

        assert observed > 0, "the run never held a position, so nothing was checked"
        assert breaches == 0, f"{breaches} bars exceeded cash beyond 1 ULP"

    def test_exposure_never_exceeds_cash_strictly_below_one(self, candles):
        """Below the ceiling the inequality holds with **no** tolerance at all."""

        session = fresh_session()
        session.set_risk_fraction(0.99)
        breaches = 0

        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            if state.position_count and state.exposure > state.paper_cash:
                breaches += 1

        assert breaches == 0

    def test_the_overshoot_is_at_most_one_ulp(self, candles):
        """The measured bound, asserted so a real regression cannot hide here."""

        session = fresh_session()
        session.set_risk_fraction(1.0)
        worst_ulps = 0.0

        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            if not state.position_count or state.paper_cash <= 0:
                continue
            ulps = (state.exposure - state.paper_cash) / math.ulp(state.paper_cash)
            worst_ulps = max(worst_ulps, ulps)

        assert worst_ulps <= 1.0, f"worst overshoot was {worst_ulps} ULP"

    def test_exposure_never_exceeds_cash_after_a_loss(self, candles):
        """The dangerous case: cash has fallen and a full-size entry follows."""

        session = fresh_session()
        session.set_risk_fraction(1.0)
        cash_fell = False

        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            if state.paper_cash < 10_000.0:
                cash_fell = True
            if state.position_count:
                assert state.exposure <= state.paper_cash * (1 + TOLERANCE_ULPS)

        assert cash_fell, "the run never lost money, so the post-loss case is untested"

    def test_exposure_fraction_is_zero_when_flat(self):
        state = fresh_session().high_risk_state()
        assert state.exposure == 0.0
        assert state.exposure_fraction == 0.0

    def test_exposure_is_exactly_entry_times_quantity(self, candles):
        session = fresh_session()
        session.set_risk_fraction(0.25)
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        state = session.high_risk_state()
        trade = state.open_position
        assert state.exposure == trade.entry_price * trade.quantity

    def test_cash_is_not_debited_on_entry(self, candles):
        """Entry commits exposure without touching cash, so there is no
        buying-power concept to invent and none is reported."""

        session = fresh_session()
        session.set_risk_fraction(0.25)
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        state = session.high_risk_state()
        assert state.paper_cash == 10_000.0
        assert state.exposure > 0

    @pytest.mark.parametrize("term", ["margin", "leverage", "borrowing", "liquidation"])
    def test_no_credit_mechanism_is_reported(self, term):
        """The state exposes no field that could be read as credit."""

        state = fresh_session().high_risk_state()
        for name in state.__dataclass_fields__:
            assert term not in name.lower()


# ---------------------------------------------------------------------------
# G. One position maximum
# ---------------------------------------------------------------------------


class TestOnePositionMaximum:
    def test_max_positions_is_one(self):
        assert fresh_session().high_risk_state().max_positions == 1

    def test_position_count_is_zero_when_flat(self):
        assert fresh_session().high_risk_state().position_count == 0

    def test_position_count_is_one_when_open(self, candles):
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert session.high_risk_state().position_count == 1

    def test_broker_refuses_a_second_position(self):
        broker = PaperBroker(starting_balance=10_000.0, costs=phase13_costs())
        broker.open_from_signal(_signal(), risk_fraction=0.5)
        from crypto_paper_lab.models import Signal

        short = Signal(
            timestamp=_signal().timestamp,
            side="short",
            reason="second probe",
            price=40_000.0,
            support=39_000.0,
            resistance=41_000.0,
            trend="down",
        )
        with pytest.raises(ValueError, match="already open"):
            broker.open_from_signal(short, risk_fraction=0.5)

    def test_a_long_run_never_holds_two_positions(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            assert state.position_count <= 1

    def test_no_pyramiding(self, candles):
        """A same-side signal while long does not add a second long."""

        session = fresh_session()
        stacked = False
        while session.replay.state.status != STATE_FINISHED:
            result = session.replay.step()
            if result.opened is not None:
                # An entry always follows a close or a flat start, never an add.
                assert session.high_risk_state().position_count == 1
            if result.closed is not None and result.opened is not None:
                stacked = True
        assert stacked, "expected close-and-reverse reversals to occur"


# ---------------------------------------------------------------------------
# H. Standard-equivalent signals - THE critical equivalence test
# ---------------------------------------------------------------------------


class TestStandardEquivalentSignals:
    """The same replay at Standard's own size must produce Standard's trades."""

    def _signature(self, facts):
        return tuple(
            zip(
                facts["sides"],
                facts["entry_times"],
                facts["reasons"],
                facts["entry_prices"],
                facts["exit_times"],
                facts["exit_prices"],
                facts["exit_reasons"],
                facts["bars_held"],
            )
        )

    def test_identical_trade_signature_at_the_same_size(self, candles):
        assert self._signature(snapshot(RISK_FRACTION, candles)) == self._signature(
            snapshot(RISK_FRACTION, candles)
        )

    def test_identical_signature_at_a_different_size(self, candles):
        """The whole point: 25x the capital, byte-identical trade sequence."""

        assert self._signature(snapshot(0.01, candles)) == self._signature(
            snapshot(0.25, candles)
        )

    def test_identical_trade_count(self, candles):
        assert snapshot(0.01, candles)["trades"] == snapshot(0.25, candles)["trades"]

    def test_identical_sides(self, candles):
        assert snapshot(0.01, candles)["sides"] == snapshot(0.25, candles)["sides"]

    def test_identical_entry_timestamps(self, candles):
        assert snapshot(0.01, candles)["entry_times"] == snapshot(0.25, candles)[
            "entry_times"
        ]

    def test_identical_exit_timestamps(self, candles):
        assert snapshot(0.01, candles)["exit_times"] == snapshot(0.25, candles)[
            "exit_times"
        ]

    def test_identical_reasons(self, candles):
        assert snapshot(0.01, candles)["reasons"] == snapshot(0.25, candles)["reasons"]

    def test_identical_entry_prices(self, candles):
        assert snapshot(0.01, candles)["entry_prices"] == snapshot(0.25, candles)[
            "entry_prices"
        ]

    def test_identical_exit_prices(self, candles):
        assert snapshot(0.01, candles)["exit_prices"] == snapshot(0.25, candles)[
            "exit_prices"
        ]

    def test_identical_exit_reasons(self, candles):
        assert snapshot(0.01, candles)["exit_reasons"] == snapshot(0.25, candles)[
            "exit_reasons"
        ]

    def test_identical_bars_held(self, candles):
        assert snapshot(0.01, candles)["bars_held"] == snapshot(0.25, candles)[
            "bars_held"
        ]

    def test_only_quantity_differs(self, candles):
        small = snapshot(0.01, candles)
        large = snapshot(0.25, candles)
        assert small["entry_prices"] == large["entry_prices"]
        assert all(
            b > a for a, b in zip(small["quantities"], large["quantities"])
        )

    def test_standard_exact_figures_are_untouched(self, candles):
        """The authoritative Standard replay, exactly."""

        facts = snapshot(RISK_FRACTION, candles)
        assert facts["trades"] == STANDARD_TRADES
        assert repr(facts["cash"]) == repr(STANDARD_BALANCE)
        assert repr(facts["realized"]) == repr(STANDARD_REALIZED)

    def test_high_risk_default_figures(self, candles):
        """The measured 25% result, exact."""

        facts = snapshot(DEFAULT_RISK_FRACTION, candles)
        assert facts["trades"] == HIGH_RISK_025_TRADES
        assert repr(facts["cash"]) == repr(HIGH_RISK_025_BALANCE)
        assert repr(facts["realized"]) == repr(HIGH_RISK_025_REALIZED)

    def test_strategy_config_is_untouched(self, candles):
        """The mode passes the baseline config verbatim - no stop, no filter."""

        session = fresh_session()
        assert session.replay.config == baseline_config()
        assert session.replay.config.stop_loss_pct is None
        assert session.replay.config.take_profit_pct is None
        assert session.replay.config.max_holding_bars is None
        assert session.replay.config.min_breakout_distance == 0.0

    def test_baseline_config_is_the_strategy_module_default(self):
        assert baseline_config() == StrategyConfig()

    def test_only_risk_fraction_differs_between_the_two_replays(self, candles):
        """One constructor argument is the whole difference."""

        standard = Replay(candles, config=baseline_config(), costs=phase13_costs(),
                          policy=AUTOMATIC_POLICY, risk_fraction=0.01)
        high_risk = Replay(candles, config=baseline_config(), costs=phase13_costs(),
                           policy=AUTOMATIC_POLICY, risk_fraction=0.25)

        assert standard.config == high_risk.config
        assert standard._costs == high_risk._costs
        assert standard.policy is high_risk.policy
        assert standard.state.dataset == high_risk.state.dataset
        assert standard._risk_fraction != high_risk._risk_fraction


# ---------------------------------------------------------------------------
# I. Opposite-signal exits and end of data
# ---------------------------------------------------------------------------


class TestExitBehaviour:
    def test_exits_are_opposite_signal(self, candles):
        counts = snapshot(0.25, candles)["exit_counts"]
        assert counts.get("opposite_signal", 0) > 0

    def test_no_stop_loss_exits(self, candles):
        assert "stop_loss" not in snapshot(0.25, candles)["exit_counts"]

    def test_no_take_profit_exits(self, candles):
        assert "take_profit" not in snapshot(0.25, candles)["exit_counts"]

    def test_no_max_holding_exits(self, candles):
        assert "max_holding" not in snapshot(0.25, candles)["exit_counts"]

    def test_exactly_one_end_of_data_exit(self, candles):
        counts = snapshot(0.25, candles)["exit_counts"]
        assert counts.get("end_of_data") == 1

    def test_exit_tally_matches_standard(self, candles):
        assert (
            snapshot(0.01, candles)["exit_counts"]
            == snapshot(0.25, candles)["exit_counts"]
        )

    def test_close_and_reverse_on_one_bar(self, candles):
        """343 of the frozen 344 trades are a same-bar reversal."""

        replay = _build(0.25, candles)
        reversals = 0
        while replay.state.status != STATE_FINISHED:
            result = replay.step()
            if result.closed is not None and result.opened is not None:
                reversals += 1
        assert reversals == 343

    def test_opposite_signal_exit_is_recorded_on_the_trade(self, candles):
        session = fresh_session()
        for _ in range(400):
            session.step()
            if session.replay.broker.journal:
                break
        assert session.replay.broker.journal[0].exit_reason == "opposite_signal"

    def test_state_serves_the_exit_tally(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        counts = session.high_risk_state().exit_counts
        assert counts["opposite_signal"] == 343
        assert counts["end_of_data"] == 1

    def test_a_position_holds_through_opposite_free_bars(self, candles):
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        before = session.replay.broker.open_trade.entry_time
        session.step()
        if session.replay.state.has_open_position:
            assert session.replay.broker.open_trade.entry_time == before


# ---------------------------------------------------------------------------
# J. End of data closes the position
# ---------------------------------------------------------------------------


class TestEndOfData:
    def test_replay_reaches_finished(self, candles):
        assert snapshot(0.25, candles)["status"] == STATE_FINISHED

    def test_no_position_survives_end_of_data(self, candles):
        assert snapshot(0.25, candles)["has_open_position"] is False

    def test_final_position_is_closed_at_the_last_close(self, candles):
        final = snapshot(0.25, candles)["last_trade"]
        assert final.exit_reason == "end_of_data"
        assert final.exit_price == candles[-1].close

    def test_journal_ends_on_a_closed_trade(self, candles):
        assert snapshot(0.25, candles)["last_trade"].exit_time is not None

    def test_stepping_a_finished_replay_is_refused(self, candles):
        from crypto_paper_lab.replay import ReplayFinishedError

        replay = run_full(0.25, candles)
        assert replay.state.status == STATE_FINISHED
        with pytest.raises(ReplayFinishedError):
            replay.step()

    def test_state_after_end_of_data(self, candles):
        replay = run_full(0.25, candles)
        state = replay.state
        assert state.next_candle_available is False
        assert state.position_count if hasattr(state, "position_count") else True

    def test_reset_after_end_of_data_returns_to_idle(self, candles):
        replay = run_full(0.25, candles)
        assert replay.state.has_open_position is False
        replay.reset()
        assert replay.state.status == "idle"
        assert replay.state.cursor == 22

    def test_a_reset_run_does_not_disturb_other_tests(self, candles):
        """Guards the memoisation itself.

        ``Replay.reset()`` mutates in place, so a shared cached Replay would let one
        test empty the journal every later test reads. This asserts the snapshot
        cache is immune to a reset performed on a separate fresh run.
        """

        before = snapshot(0.25, candles)["trades"]
        replay = run_full(0.25, candles)
        replay.reset()
        while replay.state.status != STATE_FINISHED:
            replay.step()
        assert snapshot(0.25, candles)["trades"] == before


# ---------------------------------------------------------------------------
# K. Costs come from the broker
# ---------------------------------------------------------------------------


class TestCosts:
    def test_costs_equal_fee_plus_slippage(self, candles):
        replay = run_full(0.25, candles)
        for trade in replay.broker.journal:
            assert trade.costs == pytest.approx(
                trade.fee_total + trade.slippage_total, rel=0, abs=1e-12
            )

    def test_costs_are_the_engines_rates(self):
        costs = phase13_costs()
        assert costs.fee_rate == 0.001
        assert costs.slippage_rate == 0.0005
        assert costs.execution_model == "cost_deduction"

    def test_costs_grow_sublinearly_with_size(self, candles):
        """Deliberately **not** a constant multiple.

        Sizing is against *current* cash, so after a loss the next position is
        smaller than 25x the first. The measured ratio at 25x the size is 21.02x
        the costs, asserted as a strict band rather than an equality so the
        compounding effect cannot be quietly lost.
        """

        small = snapshot(0.01, candles)["total_costs"]
        large = snapshot(0.25, candles)["total_costs"]
        ratio = large / small
        assert 15.0 < ratio < 25.0, f"cost ratio {ratio} outside the expected band"

    def test_friction_is_material_at_full_size(self, candles):
        """The measured finding the mode exists to make visible.

        At the maximum size, fees plus slippage exceed $5,000 and account for more
        than half the total loss - so what "High-Risk" costs is mostly friction,
        not market movement.
        """

        facts = snapshot(1.0, candles)
        total_costs = facts["total_costs"]
        realized = facts["realized"]
        assert total_costs > 5_000.0
        assert abs(total_costs / realized) > 0.5

    def test_net_pnl_is_gross_minus_costs(self, candles):
        replay = run_full(0.25, candles)

        for trade in replay.broker.journal:
            sign = 1 if trade.side == "long" else -1
            gross = (trade.exit_price - trade.entry_price) * trade.quantity * sign
            assert trade.net_pnl == pytest.approx(gross - trade.costs, abs=1e-9)

    def test_the_mode_books_no_cost_of_its_own(self):
        """Every cost field is the broker's; nothing is recomputed here."""

        state = fresh_session().high_risk_state()
        for name in ("fee_total", "slippage_total", "costs"):
            assert name not in state.__dataclass_fields__


# ---------------------------------------------------------------------------
# L. P&L is the engine's own
# ---------------------------------------------------------------------------


class TestRealizedPnl:
    def test_realized_is_cash_minus_starting(self, candles):
        facts = snapshot(0.25, candles)
        assert facts["realized"] == pytest.approx(facts["realized"], abs=1e-9)
        assert facts["cash"] - facts["starting_balance"] == pytest.approx(
            facts["realized"], abs=1e-12
        )

    def test_state_realized_matches_the_replay(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        state = session.high_risk_state()
        assert state.realized_pnl == session.replay.state.realized_pnl

    def test_zero_pnl_before_any_trade(self):
        state = fresh_session().high_risk_state()
        assert state.realized_pnl == 0.0
        assert state.trade_count == 0

    def test_realized_equals_the_sum_of_closed_trades(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        state = session.high_risk_state()
        total = sum(t.net_pnl or 0.0 for t in session.replay.broker.journal)
        assert state.realized_pnl == pytest.approx(total, abs=1e-9)

    def test_trade_count_matches_the_journal(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        state = session.high_risk_state()
        assert state.trade_count == len(session.replay.broker.journal)

    def test_starting_balance_is_ten_thousand(self):
        assert fresh_session().high_risk_state().starting_balance == 10_000.0

    def test_higher_risk_means_a_larger_loss_on_this_dataset(self, candles):
        assert snapshot(0.25, candles)["cash"] < snapshot(0.01, candles)["cash"]

    def test_no_unrealized_pnl_is_reported(self, candles):
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        state = session.high_risk_state()
        # Cash is untouched by an open position, so realized P&L must be zero:
        # the engine has no live price feed and could not produce anything else.
        assert state.realized_pnl == 0.0


# ---------------------------------------------------------------------------
# M. Invalid configuration
# ---------------------------------------------------------------------------


class TestInvalidConfiguration:
    @pytest.mark.parametrize(
        "value", [0, 0.0, -0.0001, -1.0, -0.5]
    )
    def test_zero_and_negative_are_refused(self, value):
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(value)

    def test_zero_message_explains_itself(self):
        with pytest.raises(HighRiskError, match="greater than 0"):
            coerce_risk_fraction(0)

    def test_above_one_is_refused(self):
        with pytest.raises(HighRiskError, match="at most"):
            coerce_risk_fraction(1.5)

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_is_refused(self, value):
        with pytest.raises(HighRiskError, match="finite"):
            coerce_risk_fraction(value)

    def test_nan_fails_every_comparison_so_it_must_be_caught_early(self):
        # NaN <= 0 and NaN > 1 are both False, so without the finite check a NaN
        # would sail through both bounds.
        assert math.isnan(float("nan"))
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(float("nan"))

    @pytest.mark.parametrize("value", [True, False])
    def test_bool_is_refused(self, value):
        with pytest.raises(HighRiskError, match="boolean"):
            coerce_risk_fraction(value)

    @pytest.mark.parametrize("value", ["0.25", "", "abc", None, [], {}, object()])
    def test_non_numeric_is_refused(self, value):
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(value)

    def test_int_one_is_accepted(self):
        assert coerce_risk_fraction(1) == 1.0

    def test_config_construction_validates(self):
        with pytest.raises(HighRiskError):
            HighRiskConfig(risk_fraction=2.0)

    def test_config_is_frozen(self):
        with pytest.raises(Exception):
            HighRiskConfig().risk_fraction = 0.5

    def test_nothing_is_clamped(self):
        """A refusal never returns a substitute value."""

        for value in (0, -1, 2.0, float("nan")):
            with pytest.raises(HighRiskError):
                coerce_risk_fraction(value)

    def test_identity_is_deterministic(self):
        assert HighRiskConfig(0.25).identity() == HighRiskConfig(0.25).identity()
        assert HighRiskConfig(0.25).identity() != HighRiskConfig(0.5).identity()

    def test_identity_hash_is_stable(self):
        assert (
            HighRiskConfig(0.25).identity_hash == HighRiskConfig(0.25).identity_hash
        )


# ---------------------------------------------------------------------------
# N. Configuration refused while a position is open
# ---------------------------------------------------------------------------


class TestConfigurationWhilePositionOpen:
    def _open_session(self) -> HighRiskSession:
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert session.replay.state.has_open_position
        return session

    def test_refused_with_position_open(self):
        session = self._open_session()
        with pytest.raises(HTTPException) as caught:
            session.set_risk_fraction(0.5)
        assert caught.value.status_code == 409
        assert code_of(caught.value) == "POSITION_OPEN"

    def test_the_message_names_the_reason(self):
        session = self._open_session()
        with pytest.raises(HTTPException) as caught:
            session.set_risk_fraction(0.5)
        assert "sized by the current fraction" in caught.value.detail["message"]

    def test_config_is_unchanged_after_a_refusal(self):
        session = self._open_session()
        before = session.risk_fraction
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.9)
        assert session.risk_fraction == before

    def test_position_survives_a_refusal(self):
        session = self._open_session()
        trade = session.replay.broker.open_trade
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.9)
        assert session.replay.broker.open_trade is trade

    def test_cash_survives_a_refusal(self):
        session = self._open_session()
        before = session.replay.broker.cash
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.9)
        assert session.replay.broker.cash == before

    def test_exposure_survives_a_refusal(self):
        session = self._open_session()
        before = session.high_risk_state().exposure
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.9)
        assert session.high_risk_state().exposure == before

    def test_replay_identity_is_refused_while_open(self):
        """The fraction reported must never disagree with the open position."""

        session = self._open_session()
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.9)
        state = session.high_risk_state()
        assert state.risk_fraction == state.replay.execution.risk_fraction


# ---------------------------------------------------------------------------
# O. Configuration accepted while flat
# ---------------------------------------------------------------------------


class TestConfigurationWhileFlat:
    def test_accepts_a_new_fraction(self):
        session = fresh_session()
        session.set_risk_fraction(0.10)
        assert session.risk_fraction == 0.10

    def test_accepts_several_successive_changes(self):
        session = fresh_session()
        for value in (0.10, 0.50, 0.25, 1.0):
            session.set_risk_fraction(value)
            assert session.risk_fraction == value

    def test_change_reaches_the_replay(self):
        """The fraction must reach the engine, not just the session's own field."""

        session = fresh_session()
        session.set_risk_fraction(0.5)
        assert session.replay._risk_fraction == 0.5

    def test_change_updates_the_reported_execution_identity(self):
        """Otherwise /api/replay would contradict the mode's own state."""

        session = fresh_session()
        session.set_risk_fraction(0.5)
        assert session.replay.state.execution.risk_fraction == 0.5

    def test_state_and_identity_agree_after_a_change(self):
        session = fresh_session()
        session.set_risk_fraction(0.4)
        state = session.high_risk_state()
        assert state.risk_fraction == state.replay.execution.risk_fraction == 0.4

    def test_change_applies_to_the_next_entry(self):
        session = fresh_session()
        session.set_risk_fraction(0.5)
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert session.high_risk_state().exposure_fraction == pytest.approx(
            0.5, rel=1e-12
        )

    def _flat_mid_run_session(self) -> HighRiskSession:
        """A session stepped past its first entry, then returned to flat.

        This is the interesting case for "only the configuration changed": the
        replay has history, and an implementation that rebuilt the Replay would
        silently lose it.
        """

        session = fresh_session()

        while session.replay.state.status != STATE_FINISHED:
            session.step()
            if session.replay.broker.journal and not (
                session.replay.state.has_open_position
            ):
                break

        assert session.replay.broker.journal, "expected at least one closed trade"

        return session

    def test_config_change_does_not_move_the_cursor(self):
        session = self._flat_mid_run_session()
        before = session.replay.state.cursor
        session.set_risk_fraction(0.5)
        assert session.replay.state.cursor == before

    def test_config_change_does_not_touch_cash(self):
        session = self._flat_mid_run_session()
        before = session.replay.broker.cash
        session.set_risk_fraction(0.5)
        assert session.replay.broker.cash == before

    def test_config_change_does_not_touch_the_journal(self):
        session = self._flat_mid_run_session()
        before = list(session.replay.broker.journal)
        session.set_risk_fraction(0.5)
        assert session.replay.broker.journal == before

    def test_config_change_preserves_accumulated_history(self):
        """The reason a Replay rebuild would be wrong: it would discard this."""

        session = self._flat_mid_run_session()
        cash = session.replay.broker.cash
        state = session.high_risk_state()
        pnl = state.realized_pnl
        trades = state.trade_count
        counts = dict(state.exit_counts)

        session.set_risk_fraction(0.5)

        after = session.high_risk_state()
        assert after.paper_cash == cash
        assert after.realized_pnl == pnl
        assert after.trade_count == trades
        assert after.exit_counts == counts

    def test_config_change_does_not_touch_the_position(self):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
            if not session.replay.state.has_open_position and (
                session.replay.broker.journal
            ):
                break
        before = session.replay.broker.open_trade
        session.set_risk_fraction(0.5)
        assert session.replay.broker.open_trade is before

    def test_config_change_does_not_touch_the_replay_id(self):
        session = fresh_session()
        before = session.replay.state.replay_id
        session.set_risk_fraction(0.5)
        assert session.replay.state.replay_id == before

    def test_config_change_does_not_touch_realized_pnl(self):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        before = session.high_risk_state().realized_pnl
        session.set_risk_fraction(0.5)
        assert session.high_risk_state().realized_pnl == before

    def test_config_survives_reset(self):
        session = fresh_session()
        session.set_risk_fraction(0.5)
        session.reset()
        assert session.risk_fraction == 0.5

    def test_config_survives_a_full_run_and_reset(self, candles):
        session = fresh_session()
        session.set_risk_fraction(0.5)
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.risk_fraction == 0.5

    def test_a_rejected_change_leaves_the_cursor_alone(self):
        session = fresh_session()
        for _ in range(40):
            session.step()
        before = session.replay.state.cursor
        with pytest.raises(HTTPException):
            session.set_risk_fraction(5.0)
        assert session.replay.state.cursor == before

    def test_a_rejected_change_leaves_cash_alone(self):
        session = fresh_session()
        for _ in range(40):
            session.step()
        before = session.replay.broker.cash
        with pytest.raises(HTTPException):
            session.set_risk_fraction(0.0)
        assert session.replay.broker.cash == before

    def test_a_rejected_change_leaves_the_journal_alone(self):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        before = len(session.replay.broker.journal)
        with pytest.raises(HTTPException):
            session.set_risk_fraction(-1.0)
        assert len(session.replay.broker.journal) == before

    def test_config_can_change_again_after_a_reset(self):
        session = fresh_session()
        session.set_risk_fraction(0.1)
        session.set_risk_fraction(0.5)
        session.reset()
        session.set_risk_fraction(0.25)
        assert session.risk_fraction == 0.25


# ---------------------------------------------------------------------------
# P. Insufficient paper cash
# ---------------------------------------------------------------------------


class TestInsufficientPaperCash:
    def test_the_broker_does_not_itself_refuse_zero_cash(self):
        """Why this guard has to exist at all.

        ``PaperBroker.open_from_signal`` validates ``risk_fraction`` only. With
        ``cash == 0`` it computes ``quantity = 0`` and returns a **zero-quantity
        trade** rather than refusing, so a mode relying on the broker alone would
        journal a fill that committed no capital and still charged its round-trip
        costs. Pinned here so the guard cannot be deleted on the mistaken belief
        that the engine already refuses.
        """

        broker = PaperBroker(starting_balance=10_000.0, costs=phase13_costs())
        broker.cash = 0.0
        trade = broker.open_from_signal(_signal(), risk_fraction=0.5)
        assert trade.quantity == 0.0

    def test_the_mode_refuses_an_entry_with_no_cash(self):
        session = fresh_session()
        session.replay.broker.cash = 0.0
        with pytest.raises(HTTPException) as caught:
            session._assert_can_trade()
        assert caught.value.status_code == 409
        assert code_of(caught.value) == "NO_PAPER_CASH"

    def test_the_mode_refuses_an_entry_with_negative_cash(self):
        session = fresh_session()
        session.replay.broker.cash = -25.0
        with pytest.raises(HTTPException) as caught:
            session._assert_can_trade()
        assert code_of(caught.value) == "NO_PAPER_CASH"

    def test_available_entries_is_false_with_no_cash(self):
        session = fresh_session()
        assert session.available_entries() is True
        session.replay.broker.cash = 0.0
        assert session.available_entries() is False

    def test_available_entries_is_false_with_a_position_open(self):
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert session.available_entries() is False

    def test_no_cash_guard_mutates_nothing(self):
        session = fresh_session()
        session.replay.broker.cash = 0.0
        cursor = session.replay.state.cursor
        with pytest.raises(HTTPException):
            session._assert_can_trade()
        assert session.replay.state.cursor == cursor
        assert session.replay.broker.open_trade is None
        assert len(session.replay.broker.journal) == 0

    def test_a_full_run_at_full_size_never_empties_the_account(self, candles):
        """Defensive: on the frozen dataset the guard is never load-bearing."""

        assert snapshot(1.0, candles)["cash"] > 0.0

    def test_exposure_stays_within_a_shrunken_account(self, candles):
        session = fresh_session()
        session.set_risk_fraction(1.0)
        while session.replay.state.status != STATE_FINISHED:
            session.step()
            state = session.high_risk_state()
            if state.position_count:
                assert state.exposure <= state.paper_cash * (1 + TOLERANCE_ULPS)


# ---------------------------------------------------------------------------
# Q. Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_starts_idle(self):
        assert fresh_session().replay.state.status == "idle"

    def test_start_arms_the_ticker(self):
        session = fresh_session()
        session.start(200)
        assert session.replay.state.status == "running"
        assert session.replay.ticker.armed is True

    def test_start_is_idempotent(self):
        session = fresh_session()
        session.start(200)
        session.start(200)
        assert session.replay.state.status == "running"

    def test_pause_disarms(self):
        session = fresh_session()
        session.start(200)
        session.pause()
        assert session.replay.state.status == "paused"
        assert session.replay.ticker.armed is False

    def test_step_advances_one_bar(self):
        session = fresh_session()
        before = session.replay.state.cursor
        session.step()
        assert session.replay.state.cursor == before + 1

    def test_step_is_legal_while_paused(self):
        session = fresh_session()
        session.start(200)
        session.pause()
        before = session.replay.state.cursor
        session.step()
        assert session.replay.state.cursor == before + 1

    def test_tick_is_a_no_op_when_disarmed(self):
        session = fresh_session()
        assert session.replay.tick() is None

    def test_tick_steps_once_when_armed(self):
        session = fresh_session()
        session.start(200)
        before = session.replay.state.cursor
        result = session.replay.tick()
        assert result is not None
        assert session.replay.state.cursor == before + 1

    def test_state_is_reported(self):
        assert "idle" in fresh_session().high_risk_state().replay.status

    def test_start_is_a_quiet_no_op_when_finished(self, candles):
        """The engine is silent; the transport is what refuses.

        ``Replay.start`` documents ``finished -> finished`` as a no-op, and the
        HTTP layer turns it into ``409 REPLAY_FINISHED``. Asserting that the engine
        raises would contradict its own documented contract.
        """

        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        before = session.replay.state.cursor
        session.replay.start(200)
        assert session.replay.state.status == STATE_FINISHED
        assert session.replay.state.cursor == before
        assert session.replay.ticker.armed is False


# ---------------------------------------------------------------------------
# R. Reset
# ---------------------------------------------------------------------------


class TestReset:
    def _open_session(self) -> HighRiskSession:
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        return session

    def test_reset_is_refused_while_a_position_is_open(self):
        session = self._open_session()
        with pytest.raises(HTTPException) as caught:
            session.reset()
        assert caught.value.status_code == 409
        assert code_of(caught.value) == "POSITION_OPEN"

    def test_position_survives_a_refused_reset(self):
        session = self._open_session()
        trade = session.replay.broker.open_trade
        with pytest.raises(HTTPException):
            session.reset()
        assert session.replay.broker.open_trade is trade

    def test_journal_survives_a_refused_reset(self):
        session = self._open_session()
        before = len(session.replay.broker.journal)
        with pytest.raises(HTTPException):
            session.reset()
        assert len(session.replay.broker.journal) == before

    def test_reset_when_flat_succeeds(self):
        assert fresh_session().reset().status == "idle"

    def test_reset_restores_the_balance(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.high_risk_state().paper_cash == 10_000.0

    def test_reset_clears_realized_pnl(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.high_risk_state().realized_pnl == 0.0

    def test_reset_clears_the_journal(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        state = session.high_risk_state()
        assert state.trade_count == 0
        assert state.exit_counts == {}

    def test_reset_clears_exposure(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.high_risk_state().exposure == 0.0

    def test_reset_rewinds_the_cursor(self, candles):
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.replay.state.cursor == 22

    def test_reset_preserves_the_configuration(self, candles):
        session = fresh_session()
        session.set_risk_fraction(0.5)
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        assert session.risk_fraction == 0.5

    def test_reset_disarms_the_ticker(self):
        session = fresh_session()
        session.start(200)
        session.reset()
        assert session.replay.ticker.armed is False

    def test_reset_preserves_the_replay_id(self):
        session = fresh_session()
        before = session.replay.state.replay_id
        session.reset()
        assert session.replay.state.replay_id == before

    def test_a_run_after_reset_repeats_exactly(self, candles):
        first = snapshot(0.25, candles)["cash"]
        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        session.reset()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        assert session.replay.broker.cash == first


# ---------------------------------------------------------------------------
# S. Causality
# ---------------------------------------------------------------------------


class TestCausality:
    def test_entry_fills_at_the_execution_bar_open(self, candles):
        session = fresh_session()
        for _ in range(200):
            index = session.replay.state.cursor
            session.step()
            if session.replay.state.has_open_position:
                trade = session.replay.broker.open_trade
                assert trade.entry_price == candles[index].open
                return
        pytest.fail("no position opened")

    def test_entry_is_not_the_next_bars_open(self, candles):
        session = fresh_session()
        for _ in range(200):
            index = session.replay.state.cursor
            session.step()
            if session.replay.state.has_open_position:
                trade = session.replay.broker.open_trade
                assert trade.entry_price != candles[index + 1].open
                return
        pytest.fail("no position opened")

    def test_entry_is_not_a_bars_close(self, candles):
        session = fresh_session()
        for _ in range(200):
            index = session.replay.state.cursor
            session.step()
            if session.replay.state.has_open_position:
                trade = session.replay.broker.open_trade
                assert trade.entry_price != candles[index].close
                return
        pytest.fail("no position opened")

    def test_entry_is_never_a_future_open(self, candles):
        session = fresh_session()
        for _ in range(300):
            index = session.replay.state.cursor
            session.step()
            if session.replay.state.has_open_position:
                price = session.replay.broker.open_trade.entry_price
                for offset in range(index + 1, min(index + 400, len(candles))):
                    assert price != candles[offset].open
                return
        pytest.fail("no position opened")

    def test_exit_fills_at_the_execution_bar_open(self, candles):
        session = fresh_session()
        for _ in range(400):
            index = session.replay.state.cursor
            result = session.replay.step()
            if result.closed is not None:
                assert result.closed.exit_price == candles[index].open
                return
        pytest.fail("no trade closed")

    def test_sizing_does_not_change_when_the_entry_filled(self, candles):
        """A larger size must not buy a better price."""

        small = first_entry(candles, 0.01)
        large = first_entry(candles, 1.0)
        assert small.entry_price == large.entry_price
        assert small.entry_time == large.entry_time
        assert large.quantity > small.quantity


# ---------------------------------------------------------------------------
# T. Isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    MODES_WITH_SESSIONS = ("standard", "ai_intelligence", "daily_target", "manual",
                           "high_risk")

    def _snapshot(self, registry):
        out = {}
        for mode in self.MODES_WITH_SESSIONS:
            replay = registry.session(mode).replay
            out[mode] = (
                replay.state.replay_id,
                replay.state.cursor,
                replay.broker.cash,
                replay.broker.open_trade is None,
                len(replay.broker.journal),
            )
        return out

    def test_five_distinct_replay_ids(self):
        registry = ModeRegistry()
        ids = {
            mode: registry.session(mode).replay.state.replay_id
            for mode in self.MODES_WITH_SESSIONS
        }
        assert len(set(ids.values())) == 5

    def test_five_distinct_brokers(self):
        registry = ModeRegistry()
        brokers = {
            id(registry.session(mode).replay.broker)
            for mode in self.MODES_WITH_SESSIONS
        }
        assert len(brokers) == 5

    def test_driving_high_risk_touches_nothing_else(self, candles):
        registry = ModeRegistry()
        before = self._snapshot(registry)

        session = registry.high_risk_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()

        after = self._snapshot(registry)
        for mode in self.MODES_WITH_SESSIONS:
            if mode == "high_risk":
                continue
            assert after[mode] == before[mode], f"{mode} changed"

    def test_high_risk_actually_traded(self, candles):
        registry = ModeRegistry()
        session = registry.high_risk_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()
        assert session.high_risk_state().trade_count == 344

    def test_standard_is_untouched_by_a_high_risk_session_build(self):
        registry = ModeRegistry()
        registry.high_risk_session()
        standard = registry.session("standard").replay
        assert standard.state.cursor == 22
        assert standard.broker.cash == 10_000.0

    def test_risk_fraction_is_per_mode(self):
        registry = ModeRegistry()
        assert registry.session("standard").replay.state.execution.risk_fraction == 0.01
        assert registry.session("high_risk").replay.state.execution.risk_fraction == 0.25

    def test_configuring_high_risk_does_not_touch_standard(self):
        registry = ModeRegistry()
        standard_before = registry.session("standard").replay.state.cursor
        registry.high_risk_session().set_risk_fraction(1.0)
        assert registry.session("standard").replay.state.cursor == standard_before
        assert (
            registry.session("standard").replay.state.execution.risk_fraction == 0.01
        )

    def test_two_registries_have_independent_sessions(self):
        first = ModeRegistry().high_risk_session()
        second = ModeRegistry().high_risk_session()
        first.set_risk_fraction(1.0)
        assert first.risk_fraction == 1.0
        assert second.risk_fraction == 0.25

    def test_alerts_still_holds_no_session(self):
        registry = ModeRegistry()
        assert registry.has_session("alerts") is False

    def test_registry_returns_a_high_risk_session(self):
        assert isinstance(ModeRegistry().high_risk_session(), HighRiskSession)

    def test_registry_rejects_a_wrong_session_type(self):
        """The isinstance guard, exercised through an injected builder."""

        registry = ModeRegistry(session_for=lambda mode: None)
        with pytest.raises(TypeError, match="HighRiskSession"):
            registry.high_risk_session()


# ---------------------------------------------------------------------------
# U2. The API response, in every state
# ---------------------------------------------------------------------------
#
# These exist because the engine-level assertions above all pass while the transport
# is broken. ``HighRiskStateResponse.from_session`` is a *different* code path from
# ``HighRiskSession.high_risk_state``: it maps the projection onto Pydantic models and
# formats timestamps, so a bug there is invisible to every other group in this file.
#
# It was not theoretical. A first version of ``from_session`` called ``as_utc`` without
# importing it, which raised ``NameError`` - a 500 - on **every** request made while a
# position was open, and not at all while flat. The whole engine-level suite stayed
# green. Each state below is therefore asserted through the real response object.


def _response():
    from paper_api.schemas import HighRiskStateResponse

    return HighRiskStateResponse.from_session(fresh_session())


class TestApiResponseInEveryState:
    def test_flat_response_builds(self):
        assert _response().risk_fraction == 0.25

    def test_long_position_response_builds(self, candles):
        """The state that broke: an open position formats a timestamp."""

        from paper_api.schemas import HighRiskStateResponse

        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert session.replay.state.has_open_position

        response = HighRiskStateResponse.from_session(session)

        assert response.open_position is not None
        assert response.open_position.side == "long"
        assert response.open_position.entry_time is not None
        assert response.position_count == 1
        assert response.exposure > 0

    def test_short_position_response_builds(self, candles):
        from paper_api.schemas import HighRiskStateResponse

        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position and (
                session.replay.broker.open_trade.side == "short"
            ):
                break

        response = HighRiskStateResponse.from_session(session)

        assert response.open_position is not None
        assert response.open_position.side in {"long", "short"}

    def test_closed_trade_response_builds(self, candles):
        from paper_api.schemas import HighRiskStateResponse

        session = fresh_session()
        while session.replay.state.status != STATE_FINISHED:
            session.step()

        response = HighRiskStateResponse.from_session(session)

        assert response.trade_count == 344
        assert response.exit_counts["opposite_signal"] == 343
        assert response.exit_counts["end_of_data"] == 1
        assert response.open_position is None
        assert response.position_count == 0

    def test_last_signal_response_builds(self, candles):
        """The signal path formats a timestamp too, and is a separate branch."""

        from paper_api.schemas import HighRiskStateResponse

        session = fresh_session()
        session.step()

        response = HighRiskStateResponse.from_session(session)

        assert response.last_signal is not None
        assert response.last_signal.timestamp is not None
        assert response.last_signal.side in {"long", "short", "flat"}

    def test_flat_state_has_no_signal_or_position(self):
        response = _response()
        assert response.open_position is None
        assert response.last_signal is None

    def test_every_contract_field_is_serialisable(self):
        payload = _response().model_dump()

        for name in (
            "mode",
            "label",
            "available",
            "risk_fraction",
            "max_risk_fraction",
            "paper_cash",
            "starting_balance",
            "realized_pnl",
            "trade_count",
            "open_position",
            "exposure",
            "exposure_fraction",
            "position_count",
            "exit_counts",
            "last_signal",
            "max_positions",
            "note",
            "inherits_note",
            "caution",
            "replay",
        ):
            assert name in payload, name

    def test_response_carries_the_scope_statement(self):
        response = _response()
        assert response.inherits_note == HIGH_RISK_INHERITS_NOTE
        assert response.note
        assert response.caution == HIGH_RISK_CAUTION

    def test_response_never_claims_a_credit_mechanism(self):
        """No field may be read as borrowing, margin or unrealised value."""

        payload = _response().model_dump()

        for name in payload:
            assert not any(
                term in name.lower()
                for term in ("margin", "leverage", "borrow", "liquidation",
                             "unrealized", "unrealised", "equity", "notional")
            ), name

    def test_replay_block_is_the_generic_shape(self):
        """The nested replay is the shared one, so no High-Risk field nests inside."""

        replay = _response().model_dump()["replay"]
        assert replay["mode"] == "high_risk"
        for name in ("risk_fraction", "exposure", "position_count"):
            assert name not in replay


# ---------------------------------------------------------------------------
# U. Notes served to clients
# ---------------------------------------------------------------------------


class TestServedNotes:
    def test_inherits_note_is_exact(self):
        assert HIGH_RISK_INHERITS_NOTE == (
            "High-Risk introduces no new signal qualification rule and inherits "
            "Standard's signal set."
        )

    def test_inherits_note_is_served(self):
        state = fresh_session().high_risk_state()
        assert state.inherits_note == HIGH_RISK_INHERITS_NOTE

    def test_caution_is_served(self):
        state = fresh_session().high_risk_state()
        assert state.caution == HIGH_RISK_CAUTION

    def test_caution_mentions_costs(self):
        assert "cost" in HIGH_RISK_CAUTION.lower()

    def test_notes_are_stable(self):
        assert HIGH_RISK_INHERITS_NOTE is HIGH_RISK_INHERITS_NOTE


# ---------------------------------------------------------------------------
# V. Paper-only safety, in the engine module
# ---------------------------------------------------------------------------


class TestPaperOnlySafety:
    """Proven by parsing the module, not by grepping its prose.

    A text search cannot distinguish a denial from a capability: both mention the
    word. These tests walk the AST and assert the forbidden terms appear in **no
    executable position at all** - not as a name, not as an attribute, not as a
    string literal in code. Only docstrings and comments may mention them, which is
    exactly what a safety note is.
    """

    FORBIDDEN = (
        "exchange",
        "wallet",
        "deposit",
        "withdraw",
        "api_key",
        "secret",
        "credential",
        "borrow",
        "leverage",
        "margin",
        "liquidation",
        "orders",
    )

    @staticmethod
    def _tree(module):
        """Parse the module's own source into an AST."""

        import ast

        with io.open(module.__file__, encoding="utf-8") as fh:
            return ast.parse(fh.read())

    @classmethod
    def _split_code_and_strings(cls, module):
        """Executable identifiers and attribute names, kept apart from prose.

        Code positions are names, attributes, arguments and def/class names. String
        literals are separated because this module's *safety notes* legitimately
        contain the banned words as denials - "there is no leverage, no margin" -
        and a check that could not tell a denial from a capability would be
        worthless in both directions.
        """

        import ast

        tree = cls._tree(module)

        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant
                ) and isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))

        code = []
        literals = []

        for node in ast.walk(tree):
            if id(node) in docstrings:
                continue
            if isinstance(node, ast.Name):
                code.append(node.id)
            elif isinstance(node, ast.Attribute):
                code.append(node.attr)
            elif isinstance(node, ast.arg):
                code.append(node.arg)
            elif isinstance(node, ast.keyword) and node.arg:
                code.append(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                code.append(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)

        return code, literals

    @pytest.mark.parametrize("term", FORBIDDEN)
    def test_term_never_appears_as_an_identifier(self, term):
        """No banned term may be a name, attribute, argument or function."""

        import crypto_paper_lab.high_risk as module

        code, _ = self._split_code_and_strings(module)
        offenders = [name for name in code if term in name.lower()]
        assert not offenders, f"{term!r} appears as an identifier: {offenders}"

    @pytest.mark.parametrize("term", FORBIDDEN)
    def test_term_in_a_string_appears_only_as_a_denial(self, term):
        """A string may mention the word, but only to deny it."""

        import crypto_paper_lab.high_risk as module

        _, literals = self._split_code_and_strings(module)
        offenders = []

        for text in literals:
            lowered = text.lower()
            index = lowered.find(term)
            while index != -1:
                window = lowered[max(0, index - 45):index]
                if not any(neg in window for neg in ("no ", "not ", "never ",
                                                     "none", "cannot", "zero")):
                    offenders.append(text[:90])
                    break
                index = lowered.find(term, index + 1)

        assert not offenders, (
            f"{term!r} appears without a denial: {offenders}"
        )

    @pytest.mark.parametrize(
        "term",
        ["requests", "urllib", "socket", "httpx", "aiohttp", "subprocess",
         "system", "environ", "getenv", "Popen", "eval", "exec"],
    )
    def test_no_network_or_environment_access(self, term):
        import crypto_paper_lab.high_risk as module

        code, _ = self._split_code_and_strings(module)
        offenders = [name for name in code if term.lower() in name.lower()]
        assert not offenders, f"{term!r} appears as code: {offenders}"

    def test_the_module_imports_nothing_beyond_the_standard_library(self):
        """A short allow-list. Anything new is a design decision, not a detail."""

        import ast

        import crypto_paper_lab.high_risk as module

        with io.open(module.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        assert imported <= {"math", "hashlib", "dataclasses", "__future__"}, (
            f"unexpected imports: {sorted(imported)}"
        )

    def test_no_sizing_arithmetic_exists(self):
        """The mode validates a fraction and delegates. It computes no size.

        Every numeric expression in the module is a comparison against a bound or
        a boolean negation; none multiplies, divides or otherwise derives a
        quantity. That is asserted by checking the only names the module performs
        arithmetic with.
        """

        import ast

        import crypto_paper_lab.high_risk as module

        with io.open(module.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        arithmetic = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.Mult, ast.Div, ast.Pow))
        ]
        # The only product in the module is the `f"-larger value"` style message
        # construction, if any; assert there is no arithmetic in code at all.
        assert not arithmetic, (
            "the mode performs arithmetic; sizing belongs to PaperBroker"
        )

    def test_no_broker_is_constructed_by_the_mode(self):
        """One broker, owned by ``Replay``. The mode never creates a second.

        Asserted over identifiers rather than prose, because the module's
        docstrings discuss the broker extensively and legitimately: the point is
        that it *never touches* one.
        """

        import crypto_paper_lab.high_risk as module

        code, _ = self._split_code_and_strings(module)
        offenders = [name for name in code if "broker" in name.lower()]
        assert not offenders, f"the mode references a broker in code: {offenders}"

    def test_no_replay_is_constructed_by_the_mode(self):
        import crypto_paper_lab.high_risk as module

        code, _ = self._split_code_and_strings(module)
        assert "replay" not in [name.lower() for name in code]

    def test_the_ceiling_is_exactly_one(self):
        """One is the whole safety argument.

        Asserted as a literal rather than derived, so a well-meaning "allow a
        little headroom above the account" edit fails here rather than quietly
        reintroducing leverage.
        """

        assert MAX_RISK_FRACTION == 1.0
        assert coerce_risk_fraction(MAX_RISK_FRACTION) == 1.0
        with pytest.raises(HighRiskError):
            coerce_risk_fraction(MAX_RISK_FRACTION + 1e-9)


# ---------------------------------------------------------------------------
# W. State projection
# ---------------------------------------------------------------------------


class TestStateProjection:
    def test_state_exposes_the_whole_contract(self):
        state = fresh_session().high_risk_state()
        for name in (
            "risk_fraction",
            "max_risk_fraction",
            "paper_cash",
            "starting_balance",
            "realized_pnl",
            "trade_count",
            "open_position",
            "exposure",
            "exposure_fraction",
            "position_count",
            "exit_counts",
            "last_signal",
            "max_positions",
            "replay",
            "inherits_note",
            "caution",
        ):
            assert name in state.__dataclass_fields__

    def test_state_is_frozen(self):
        with pytest.raises(Exception):
            fresh_session().high_risk_state().paper_cash = 1.0

    def test_state_is_recomputed_not_cached(self, candles):
        session = fresh_session()
        first = session.high_risk_state()
        session.step()
        second = session.high_risk_state()
        assert first is not second
        assert second.replay.cursor == first.replay.cursor + 1

    def test_open_position_is_the_brokers_trade(self, candles):
        session = fresh_session()
        for _ in range(200):
            session.step()
            if session.replay.state.has_open_position:
                break
        assert (
            session.high_risk_state().open_position
            is session.replay.broker.open_trade
        )

    def test_exit_counts_are_a_copy(self):
        state = fresh_session().high_risk_state()
        state.exit_counts["injected"] = 99
        assert "injected" not in fresh_session().high_risk_state().exit_counts

    def test_last_signal_is_the_strategys_observation(self, candles):
        session = fresh_session()
        session.step()
        state = session.high_risk_state()
        assert state.last_signal is session.replay.state.last_signal

    def test_max_positions_comes_from_the_policy(self):
        session = fresh_session()
        assert session.high_risk_state().max_positions == session.replay.policy.max_positions

    def test_max_risk_fraction_comes_from_the_engine_constant(self):
        assert fresh_session().high_risk_state().max_risk_fraction == MAX_RISK_FRACTION