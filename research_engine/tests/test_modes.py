"""Phase 17F tests: mode isolation.

Three rules shape this file.

**Isolation is asserted structurally, not by convention.** Two modes must hold
distinct brokers, journals and cursors *as objects*, because two modes that share
an object cannot be isolated no matter how carefully the routes behave. The tests
compare identities (``is not``) rather than merely equal values.

**Switching is proven not to disturb.** The scenario from the brief - start
Standard, advance it, visit another mode, return - is executed literally, and
Standard is asserted byte-identical on return. A "current mode" variable would
fail this; a per-request parameter cannot.

**The placeholders must stay placeholders.** AI Intelligence and Alerts are the
whole point of the phase, and the risk is that a future edit wires one of them to
real trading by accident. So the tests assert they *cannot* execute, rather than
merely that they currently do not.
"""
from __future__ import annotations

import ast
import json
import pathlib
import tokenize
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.ai_paper import (
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PROFIT_TARGET_PCT,
    AiPaperBook,
)
from crypto_paper_lab.intelligence import DEFAULT_THRESHOLD
from crypto_paper_lab.strategy import analyze
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.execution import (
    AUTOMATIC_POLICY,
    DecisionContext,
    IntelligencePolicy,
)
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DEFAULT_MODE,
    MODES,
    STANDARD,
    ModeError,
    ModeNotAvailableError,
    ModeSpec,
    UnknownModeError,
    is_executable,
    known_modes,
    mode_policy,
    mode_spec,
    reserved_modes,
)
from crypto_paper_lab.replay import Replay
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.moderegistry import AiSession, ModeRegistry
from paper_api.replaysession import ReplaySession
from paper_api.schemas import ModesResponse, ReplayStateResponse

RESEARCH_ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = RESEARCH_ENGINE_ROOT / "src" / "crypto_paper_lab"
MODES_SOURCE = ENGINE / "modes.py"
REGISTRY_SOURCE = (
    RESEARCH_ENGINE_ROOT / "src" / "paper_api" / "moderegistry.py"
)

SOURCE, _ = load_dataset(RESEARCH_ENGINE_ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = 22
PREFIX = 400

#: Phase 17A names four product modes. Two still have no contract: ``manual`` has
#: none at all ("the operator decides" is not an automatic policy), and
#: ``high_risk``'s qualification rules are open question Q6, which the architecture
#: requires to be pre-registered as research before implementation.
#:
#: ``daily_target`` left this tuple in Phase 24B. Its contract was already fully
#: specified in architecture section 10 and its open questions Q4 and Q5 were
#: measurement and presentation calls rather than research, so it became an
#: implemented mode. ``ALERTS`` likewise stopped being reserved in 17G.
RESERVED_FROM_ARCHITECTURE = ("manual", "high_risk")

#: Modes the architecture named and that are now implemented and executable.
IMPLEMENTED_FROM_ARCHITECTURE = ("daily_target",)


def code_only(path: pathlib.Path) -> str:
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


def trade_signature(trade) -> tuple:
    return (
        trade.side, trade.entry_time, trade.entry_price, trade.quantity,
        trade.exit_time, trade.exit_price, trade.exit_reason, trade.bars_held,
        trade.costs, trade.fee_total, trade.slippage_total, trade.spread_total,
        trade.pnl, trade.net_pnl, trade.total_friction,
    )


def signatures(replay: Replay) -> list:
    return [trade_signature(t) for t in replay.broker.journal]


def make_replay(policy=None, length: int = PREFIX) -> Replay:
    return Replay(
        SOURCE[:length],
        config=CONFIG,
        costs=COSTS,
        **({} if policy is None else {"policy": policy}),
    )


def drive_to_end(replay: Replay) -> Replay:
    while replay.state.status != "finished":
        replay.step()

    return replay


def drive_session_to_end(session: ReplaySession) -> ReplaySession:
    """Drive a session to completion, so an ``AiSession``'s book advances too.

    Added in Phase 17G. Driving an ``AiSession``'s replay directly would advance the
    cursor while leaving the book behind, which is exactly the divergence
    ``AiSession.step()`` exists to prevent.
    """

    while session.snapshot().status != "finished":
        session.step()

    return session


def _directional_signal_indexes(replay: Replay) -> set:
    """Every bar whose signal was directional, i.e. entry-eligible for any mode.

    This is the correct superset to test AI's entries against, and the distinction
    matters. Standard's *actual* entries are not a superset of AI's: Standard holds
    exactly one position, so it is blocked from entering while a trade is open,
    whereas AI has several slots and stays flat more often. AI therefore enters on
    bars Standard skips.

    What must hold is that both modes draw from the **same signal stream** - AI adds
    a score gate on top of ``analyze``, it does not invent its own trigger. That is
    the property worth asserting, and it is why the shared ``StrategyConfig`` is
    itself worth a test.
    """

    return {
        index
        for index in range(REQUIRED, len(replay._candles))
        if analyze(replay._candles[:index], CONFIG).side in {"long", "short"}
    }


def registry(**sessions) -> ModeRegistry:
    """A registry whose modes get prepared, isolated sessions.

    Built through the public injection point rather than by reaching into the
    registry, so the tests exercise the same seam production code uses.

    Updated in Phase 17G: AI Intelligence is served by an :class:`AiSession`
    rather than a bare ``ReplaySession``, because its contract permits several
    concurrent paper positions and the book that owns them is part of the session.
    Building a plain session for it would no longer be the production shape.
    """

    def build(mode: str) -> ReplaySession:
        prepared = sessions.get(mode)
        if prepared is not None:
            return prepared

        replay = Replay(
            SOURCE[:PREFIX],
            config=CONFIG,
            costs=COSTS,
            policy=mode_policy(mode),
        )

        if mode == AI_INTELLIGENCE:
            return AiSession(
                replay,
                AiPaperBook(
                    SOURCE[:PREFIX],
                    strategy=CONFIG,
                    costs=COSTS,
                ),
            )

        return ReplaySession(replay)

    return ModeRegistry(session_for=build)


def client_for(reg: ModeRegistry | None = None) -> TestClient:
    return TestClient(create_app(ApiConfig(), registry=reg or registry()))


# ---------------------------------------------------------------------------
# 1-4. mode identities and explicit failure
# ---------------------------------------------------------------------------


class TestModeIdentities:
    def test_standard_mode_exists(self) -> None:
        assert STANDARD in known_modes()
        assert mode_spec(STANDARD).available is True
        assert mode_spec(STANDARD).supports_execution is True

    def test_ai_intelligence_mode_exists_as_an_explicit_identity(self) -> None:
        spec = mode_spec(AI_INTELLIGENCE)

        assert spec.mode == AI_INTELLIGENCE
        assert spec.available is True
        assert spec.supports_execution is True
        # Phase 17F asserted the note deferred to 17G. 17G defines the contract, so
        # the note must now describe it rather than promise it.
        assert "17G" not in spec.note
        assert "score" in spec.note.lower()
        # A note that omits the caveat would let a client read the score as a
        # forecast, which is the one claim it must never support.
        assert "heuristic" in spec.note.lower()
        assert "probability" in spec.note.lower()

    def test_alerts_mode_exists_as_an_explicit_identity(self) -> None:
        spec = mode_spec(ALERTS)

        assert spec.mode == ALERTS
        assert spec.available is True
        assert spec.supports_execution is False
        assert spec.note

    def test_unsupported_mode_fails_explicitly(self) -> None:
        with pytest.raises(UnknownModeError) as info:
            mode_spec("does_not_exist")

        assert info.value.code == "INVALID_MODE"
        # Never a silent fallback.
        assert "standard" not in str(info.value).lower().split("known modes")[-1] \
            .split(",")[0]

    def test_unknown_mode_lists_the_known_ones(self) -> None:
        with pytest.raises(UnknownModeError) as info:
            mode_spec("nope")

        for mode in known_modes():
            assert mode in str(info.value)

    def test_the_architectures_own_mode_names_are_recognised(self) -> None:
        """Every name 17A introduced is still recognised, implemented or not.

        This is the property the reservation was for: a typo must fail as *unknown*
        rather than becoming a silent new mode. It deliberately does not assert
        *which* modes are reserved, because that set changes as contracts land - it
        did for ``alerts`` in 17G and for ``daily_target`` in 24B.
        """

        for mode in RESERVED_FROM_ARCHITECTURE + IMPLEMENTED_FROM_ARCHITECTURE:
            assert mode in known_modes(), mode
            assert isinstance(MODES[mode], ModeSpec)

    def test_the_modes_still_without_a_contract_are_reserved(self) -> None:
        """``manual`` and ``high_risk`` stay reserved until they have contracts."""

        for mode in RESERVED_FROM_ARCHITECTURE:
            assert mode in reserved_modes(), mode
            with pytest.raises(ModeNotAvailableError):
                mode_policy(mode)

    def test_reserving_the_names_prevents_a_typo_becoming_a_new_mode(self) -> None:
        """A near-miss is unknown, not a silent new mode and not Standard.

        ``daily-target`` stays a near-miss for every mode, including the ones that
        are implemented: an unrecognised name must never resolve.
        """

        for near_miss in ("daily-target", "standard-mode", "alert"):
            with pytest.raises(UnknownModeError):
                mode_spec(near_miss)

        # The exact reserved name is recognised rather than unknown, and is refused
        # where a policy or session is required.
        for mode in RESERVED_FROM_ARCHITECTURE:
            assert mode_spec(mode).available is False, mode
            with pytest.raises(ModeNotAvailableError):
                mode_policy(mode)

    def test_default_mode_is_standard(self) -> None:
        assert DEFAULT_MODE == STANDARD

    def test_mode_error_codes_differ_by_cause(self) -> None:
        assert UnknownModeError.code != ModeNotAvailableError.code
        assert issubclass(UnknownModeError, ModeError)
        assert issubclass(ModeNotAvailableError, ModeError)


# ---------------------------------------------------------------------------
# 5-7. mode -> policy mapping
# ---------------------------------------------------------------------------


class TestModePolicyMapping:
    def test_standard_maps_to_the_automatic_policy(self) -> None:
        assert mode_policy(STANDARD) is AUTOMATIC_POLICY

    def test_ai_intelligence_does_not_map_to_automatic(self) -> None:
        """**Updated in Phase 17G.**

        17F asserted this and went further: the policy had to be a
        ``DisabledPolicy``, because the mode had no contract yet. That was the
        right constraint then. The part that must survive is that AI *gates* -
        it does not trade every eligible signal the way Standard does, so mapping
        it to ``AutomaticPolicy`` would silently turn the mode into a second
        Standard.
        """

        policy = mode_policy(AI_INTELLIGENCE)

        assert policy is not AUTOMATIC_POLICY
        assert isinstance(policy, IntelligencePolicy)
        # Still a gate, not an open door: it requires a score and a free slot.
        assert policy.threshold == DEFAULT_THRESHOLD
        assert policy.max_positions == DEFAULT_MAX_POSITIONS
        assert policy.should_enter.__self__ is policy  # bound, not class-level

    def test_ai_intelligence_refuses_an_unscored_signal(self) -> None:
        """A signal with no score cannot trade.

        This is 17F's ``cannot_enter`` test, kept in the form that still holds.
        Its context has no ``intelligence_score``, so the policy must refuse.
        Treating an absent score as a pass would make the mode trade every signal
        whenever scoring was skipped - exactly the accident the threshold exists
        to prevent.
        """

        ctx = DecisionContext(
            evaluation_index=REQUIRED,
            signal_side="long",
            signal_reason="bullish retest",
            signal_price=100.0,
            signal_timestamp=None,
            has_open_position=False,
            position_side=None,
            bars_held=None,
        )

        assert ctx.intelligence_score is None
        assert mode_policy(AI_INTELLIGENCE).should_enter(ctx) is False

    def test_alerts_has_no_policy_because_it_cannot_execute(self) -> None:
        assert mode_spec(ALERTS).policy is None

        with pytest.raises(ModeNotAvailableError) as info:
            mode_policy(ALERTS)

        assert info.value.code == "MODE_NOT_AVAILABLE"

    def test_the_executing_modes_are_exactly_the_implemented_ones(self) -> None:
        """Executability follows an implemented contract, not a hard-coded list.

        Written as a membership test over ``MODES`` so it keeps describing the
        architecture - "available **and** declared to execute" - rather than pinning
        today's mode names. That is why it survived ``daily_target`` being implemented
        in Phase 24B without an edit here.
        """

        for mode in known_modes():
            spec = MODES[mode]
            expected = spec.available and spec.supports_execution

            assert is_executable(mode) is expected, mode

        # Spot-check the two that matter most, so a passing loop cannot hide a mode
        # that became brokerless.
        assert is_executable(STANDARD) is True
        assert is_executable(ALERTS) is False

    def test_the_mapping_is_exhaustive_over_known_modes(self) -> None:
        for mode in known_modes():
            assert mode in MODES
            assert isinstance(MODES[mode], ModeSpec)


# ---------------------------------------------------------------------------
# 8-13. isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_each_executable_mode_gets_a_distinct_replay(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        assert standard is not ai
        assert standard.replay is not ai.replay

    def test_each_executable_mode_gets_a_distinct_broker(self) -> None:
        reg = registry()

        assert reg.session(STANDARD).replay.broker is not reg.session(
            AI_INTELLIGENCE
        ).replay.broker

    def test_the_same_mode_always_returns_the_same_session(self) -> None:
        reg = registry()

        assert reg.session(STANDARD) is reg.session(STANDARD)

    def test_alerts_gets_no_session_at_all(self) -> None:
        """Brokerless by architecture, not brokerless-by-refusal-to-trade."""

        reg = registry()

        with pytest.raises(ModeNotAvailableError):
            reg.session(ALERTS)

        assert reg.has_session(ALERTS) is False

    def test_balances_are_isolated(self) -> None:
        """Standard's balance moves; AI's does not.

        **Updated in Phase 17G.** 17F asserted both modes' *replay* balances, and
        AI's stayed at its starting figure because the mode never traded. That is
        no longer the whole story: AI now trades into its own book. So this asserts
        the invariant that actually matters and survives - Standard's activity
        cannot move a single figure of AI's, whichever object owns it.
        """

        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        for _ in range(120):
            standard.step()

        ai_state = ai.ai_state

        # Standard traded; AI did not, over these 120 bars, and its book is
        # untouched by anything Standard did.
        assert ai_state.realized_pnl == 0.0
        assert ai_state.realized_balance == ai_state.starting_capital
        assert ai_state.available_capital == ai_state.starting_capital
        assert ai_state.open_position_count == 0
        # Distinct brokers, as before.
        assert standard.replay.broker is not ai.replay.broker

    def test_positions_are_isolated(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        while not standard.replay.state.has_open_position:
            standard.step()

        assert standard.replay.state.has_open_position is True
        # Standard's open trade is Standard's alone: it appears nowhere in AI's
        # book, which owns its positions itself.
        assert ai.ai_state.open_position_count == 0
        assert ai.book.positions == ()

    def test_journals_are_isolated(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive_to_end(standard.replay)

        assert len(standard.replay.broker.journal) > 0
        # AI's journal is its book's, and Standard's trades are not in it.
        assert all(
            position.position_id.startswith("ai-")
            for position in ai.book.journal
        )
        assert standard.replay.broker.journal is not ai.replay.broker.journal

    def test_cursors_are_isolated(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        for _ in range(50):
            standard.step()

        assert standard.replay.state.cursor == REQUIRED + 50
        assert ai.replay.state.cursor == REQUIRED

    def test_replay_ids_are_isolated(self) -> None:
        reg = registry()

        assert reg.session(STANDARD).replay.replay_id != (
            reg.session(AI_INTELLIGENCE).replay.replay_id
        )


# ---------------------------------------------------------------------------
# 14-16. reset, switching, and default equivalence
# ---------------------------------------------------------------------------


class TestResetAndSwitching:
    def test_reset_affects_only_the_selected_mode(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive_to_end(standard.replay)
        assert standard.replay.state.trade_count > 0

        ai_before = ai.replay.state.cursor

        standard.reset()

        assert standard.replay.state.trade_count == 0
        assert standard.replay.state.cursor == REQUIRED
        # The other mode did not move at all.
        assert ai.replay.state.cursor == ai_before
        assert ai.replay.state.trade_count == 0

    def test_resetting_ai_does_not_reset_standard(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        for _ in range(80):
            standard.step()
        standard_cursor = standard.replay.state.cursor
        standard_trades = standard.replay.state.trade_count

        ai.reset()

        assert standard.replay.state.cursor == standard_cursor
        assert standard.replay.state.trade_count == standard_trades
        # AI is back to a clean pool with nothing committed.
        assert ai.ai_state.available_capital == STARTING_BALANCE
        assert ai.ai_state.open_position_count == 0

    def test_resetting_standard_does_not_reset_ai(self) -> None:
        """The reverse direction, and the one 17F did not cover.

        17F reset AI and checked Standard survived. Resetting Standard must equally
        leave AI's positions and capital alone, because no broker of one is
        reachable from the other.
        """

        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        for _ in range(200):
            ai.step()

        ai_positions = ai.book.positions
        ai_account = ai.ai_state
        assert ai_positions, "expected AI to have traded over 200 bars"

        standard.reset()

        assert ai.book.positions == ai_positions
        assert ai.ai_state == ai_account

    def test_switching_modes_leaves_standard_exactly_where_it_was(self) -> None:
        """The brief's scenario, run literally."""

        reg = registry()

        standard = reg.session(STANDARD)
        for _ in range(60):
            standard.step()

        before = standard.snapshot()
        journal_before = [trade_signature(t) for t in standard.replay.broker.journal]

        # "Select" the other mode. There is no switch to perform - selecting is
        # asking for a different object.
        ai = reg.session(AI_INTELLIGENCE)
        assert ai.replay.state.cursor == REQUIRED

        # Return to Standard.
        again = reg.session(STANDARD)
        after = again.snapshot()

        assert again is standard
        assert again.replay.state.cursor == before.cursor
        assert [trade_signature(t) for t in standard.replay.broker.journal] == (
            journal_before
        )
        assert replace(after, replay_id="x") == replace(before, replay_id="x")

    def test_switching_never_closes_a_position(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        while not standard.replay.state.has_open_position:
            standard.step()

        position = standard.replay.broker.open_trade

        reg.session(AI_INTELLIGENCE)
        reg.session(STANDARD)

        assert standard.replay.broker.open_trade is position

    def test_no_capital_is_transferred_between_modes(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive_to_end(standard.replay)

        assert standard.replay.broker.cash != STARTING_BALANCE
        # AI's pool is its own and is unaffected by Standard's P&L. Its realised
        # balance moves only with its own book, and it started where the engine
        # starts, so running Standard to the end cannot have changed it.
        ai_state = ai.ai_state
        assert ai_state.starting_capital == STARTING_BALANCE
        assert ai_state.committed_capital == 0.0
        assert ai_state.available_capital == STARTING_BALANCE

    def test_standard_mode_is_behaviourally_identical_to_the_frozen_replay(
        self,
    ) -> None:
        """16. The default must be exactly what it was before modes existed."""

        reg = registry()
        standard = reg.session(STANDARD)
        drive_to_end(standard.replay)

        reference = run_backtest(
            SOURCE[:PREFIX],
            config=CONFIG,
            costs=COSTS,
            starting_balance=STARTING_BALANCE,
            risk_fraction=RISK_FRACTION,
        )

        assert signatures(standard.replay) == [
            trade_signature(t) for t in reference.trades
        ]
        assert standard.replay.broker.cash == reference.ending_balance
        assert standard.replay.exit_counts == reference.exit_counts


# ---------------------------------------------------------------------------
# 17-18. the placeholders must stay placeholders
# ---------------------------------------------------------------------------


class TestPlaceholderSafety:
    def test_ai_intelligence_does_not_reproduce_standard_trades(self) -> None:
        """**Updated in Phase 17G.** The property, not the placeholder.

        17F asserted AI produced *no* trades, which was true while its policy was
        ``DisabledPolicy``. The property that mattered is that AI must not trade
        *like Standard*, and that survives 17G in a stronger form: AI's trades come
        from a score-gated policy over its own position book, so they are a strict
        subset of what Standard would take and never the same journal.
        """

        reg = registry()
        ai = reg.session(AI_INTELLIGENCE)

        drive_session_to_end(ai)

        ai_positions = ai.book.positions
        assert ai_positions, "expected AI to have opened at least one position"

        standard = reg.session(STANDARD)
        drive_session_to_end(standard)

        # Standard's journal is entirely its own; AI's positions entirely AI's.
        assert all(
            position.position_id.startswith("ai-") for position in ai_positions
        )
        assert ai.replay.broker.journal == []

        # The property that matters is **the signal stream, not the trade list**.
        # Every AI entry must sit on a bar where the shared strategy produced a
        # directional signal - AI adds a score gate on top of ``analyze``, it does
        # not invent a trigger of its own.
        #
        # Note this is deliberately *not* a subset relation against Standard's own
        # entries: Standard holds one position, so it is blocked from entering while
        # a trade is open, whereas AI has five slots and stays flat more often. AI
        # therefore enters on bars Standard skips, and asserting otherwise would be
        # asserting a falsehood.
        ai_entry_indexes = {position.entry_index for position in ai_positions}

        assert ai_entry_indexes, "expected at least one AI entry"
        assert ai_entry_indexes.issubset(
            _directional_signal_indexes(standard.replay)
        )

        # And the shared strategy identity is what makes that true by construction
        # rather than by luck.
        assert ai.replay.state.strategy.config_hash == (
            standard.replay.state.strategy.config_hash
        )

    def test_ai_intelligence_still_produces_signals(self) -> None:
        """Observable, and now also tradable - on its own terms."""

        ai = registry().session(AI_INTELLIGENCE)
        seen = 0

        while ai.replay.state.status != "finished":
            result = ai.replay.step()
            if result.signal.side in {"long", "short"}:
                seen += 1

        assert seen > 0

    def test_alerts_cannot_mutate_account_or_broker_state(self) -> None:
        """18. It has no broker, so there is nothing to mutate."""

        reg = registry()

        with pytest.raises(ModeNotAvailableError):
            reg.session(ALERTS)

        # And nothing else in the registry was disturbed by the refusal.
        assert reg.session(STANDARD).replay.state.cursor == REQUIRED

    def test_alerts_spec_advertises_no_execution(self) -> None:
        spec = mode_spec(ALERTS)

        assert spec.supports_execution is False
        assert spec.identity()["policy"] is None


# ---------------------------------------------------------------------------
# 19. mode identity determinism
# ---------------------------------------------------------------------------


class TestModeIdentityDeterminism:
    def test_identity_is_deterministic(self) -> None:
        for mode in known_modes():
            assert MODES[mode].identity() == MODES[mode].identity()

    def test_identity_is_serialisable(self) -> None:
        for mode in known_modes():
            assert json.loads(json.dumps(MODES[mode].identity())) == (
                MODES[mode].identity()
            )

    def test_identity_carries_no_trading_state(self) -> None:
        """A shared mode singleton must stay safe to share."""

        fields = set(ModeSpec.__dataclass_fields__)

        for forbidden in (
            "balance", "cash", "cursor", "journal", "position", "open_trade",
            "realized_pnl", "equity", "broker", "replay", "notional",
        ):
            assert forbidden not in fields, forbidden

    def test_modes_module_has_no_time_or_randomness(self) -> None:
        code = code_only(MODES_SOURCE)

        for forbidden in ("uuid", "random", "time(", "datetime.now", "os.environ"):
            assert forbidden not in code, forbidden

    def test_modes_are_frozen(self) -> None:
        assert ModeSpec.__dataclass_params__.frozen

        with pytest.raises(Exception):
            mode_spec(STANDARD).available = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 21-22. registry holds no financial state; no lookahead introduced
# ---------------------------------------------------------------------------


class TestRegistryPurity:
    def test_registry_stores_no_financial_attribute(self) -> None:
        """21. No aggregate figure exists here that could drift from a broker."""

        reg = registry()

        for forbidden in (
            "balance", "cash", "cursor", "journal", "position", "realized_pnl",
            "equity", "total_trades", "committed_capital", "available_capital",
        ):
            assert not hasattr(reg, forbidden), forbidden

    def test_registry_only_holds_sessions(self) -> None:
        reg = registry()
        reg.session(STANDARD)
        reg.session(AI_INTELLIGENCE)

        for name, value in vars(reg).items():
            if name.startswith("_"):
                continue
            # Only the session cache and the factory; nothing financial.
            assert isinstance(value, (dict, type(None))) or callable(value), name

    def test_registry_state_comes_from_the_selected_replay(self) -> None:
        reg = registry()

        standard = reg.session(STANDARD)
        for _ in range(70):
            standard.step()

        assert reg.session(STANDARD).snapshot().cursor == (
            standard.replay.state.cursor
        )

    def test_modes_do_not_introduce_future_data(self) -> None:
        """22. Every mode sees the same immutable candle tuple, read-only."""

        reg = registry()

        before = [
            (c.timestamp, c.open, c.high, c.low, c.close, c.volume)
            for c in SOURCE[:PREFIX]
        ]
        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)
        for _ in range(80):
            standard.step()
        # Driven through the session, so the AI book advances too.
        drive_session_to_end(ai)

        after = [
            (c.timestamp, c.open, c.high, c.low, c.close, c.volume)
            for c in SOURCE[:PREFIX]
        ]

        assert after == before
        # Both modes replay the identical frozen series.
        assert standard.replay.state.dataset.sha256 == (
            ai.replay.state.dataset.sha256
        )
        # The AI book read the same series and left it byte-identical.
        assert isinstance(ai.book._candles, tuple)
        assert [
            (c.timestamp, c.open, c.high, c.low, c.close, c.volume)
            for c in ai.book._candles
        ] == before

    def test_both_modes_read_the_same_immutable_input(self) -> None:
        """Shared input is not shared state.

        Content equality plus immutability is the real guarantee. Object identity
        is asserted separately against the production registry, where the cached
        series genuinely is one tuple; a test that builds its own replay per mode
        cannot claim that.
        """

        reg = registry()
        standard = reg.session(STANDARD).replay
        ai = reg.session(AI_INTELLIGENCE).replay

        assert standard._candles == ai._candles
        # Immutable, so no mode can write to what it reads.
        assert isinstance(standard._candles, tuple)
        assert getattr(
            type(standard._candles[0]), "__dataclass_params__"
        ).frozen
        # Phase 17G: the AI book reads the same series too. One immutable input,
        # three independent consumers.
        assert reg.session(AI_INTELLIGENCE).book._candles == standard._candles
        assert MODES[STANDARD].policy is not MODES[AI_INTELLIGENCE].policy


# ---------------------------------------------------------------------------
# 20. transport
# ---------------------------------------------------------------------------


class TestTransport:
    def test_modes_endpoint_lists_every_mode(self) -> None:
        response = client_for().get("/api/modes")

        assert response.status_code == 200
        body = response.json()
        assert body["default_mode"] == STANDARD
        listed = {entry["mode"] for entry in body["modes"]}
        assert listed == set(known_modes())

    def test_modes_endpoint_validates_against_the_schema(self) -> None:
        parsed = ModesResponse.model_validate(
            client_for().get("/api/modes").json()
        )

        assert len(parsed.modes) == len(known_modes())

    def test_modes_endpoint_exposes_no_trading_state(self) -> None:
        body = client_for().get("/api/modes").json()

        for entry in body["modes"]:
            for forbidden in (
                "balance", "cash", "cursor", "journal", "position",
                "realized_pnl", "equity",
            ):
                assert forbidden not in entry, forbidden

    def test_modes_endpoint_advertises_alerts_cannot_execute(self) -> None:
        body = client_for().get("/api/modes").json()
        alerts = next(e for e in body["modes"] if e["mode"] == ALERTS)

        assert alerts["supports_execution"] is False

    def test_default_replay_response_is_standard(self) -> None:
        body = client_for().get("/api/replay").json()

        assert body["mode"] == STANDARD

    def test_mode_is_echoed_for_each_mode(self) -> None:
        client = client_for()

        for mode in (STANDARD, AI_INTELLIGENCE):
            body = client.get("/api/replay", params={"mode": mode}).json()
            assert body["mode"] == mode

    def test_unknown_mode_is_rejected_with_422(self) -> None:
        response = client_for().get("/api/replay", params={"mode": "nope"})

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_MODE"

    def test_a_still_reserved_mode_is_rejected_with_409(self) -> None:
        """``manual`` is the exemplar: named in 17A, still without a contract.

        Was asserted against ``daily_target`` until Phase 24B implemented it. The
        reservation property is unchanged - a recognised name with no contract is
        refused with ``MODE_NOT_AVAILABLE``, not served as Standard and not reported
        as unknown - so the test follows a mode that is still reserved rather than
        tracking one that stopped being.
        """

        for mode in RESERVED_FROM_ARCHITECTURE:
            response = client_for().get("/api/replay", params={"mode": mode})

            assert response.status_code == 409, mode
            assert response.json()["detail"]["code"] == "MODE_NOT_AVAILABLE", mode

    def test_alerts_is_rejected_with_409(self) -> None:
        response = client_for().get("/api/replay", params={"mode": ALERTS})

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "MODE_NOT_AVAILABLE"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/replay/start",
            "/api/replay/pause",
            "/api/replay/step",
            "/api/replay/reset",
        ],
    )
    def test_mutating_routes_refuse_a_brokerless_mode(self, path: str) -> None:
        response = client_for().post(path, params={"mode": ALERTS})

        assert response.status_code == 409

    def test_advancing_one_mode_leaves_the_other_untouched(self) -> None:
        """**Updated in Phase 17G.** AI now advances its own book too."""

        client = client_for()

        client.post("/api/replay/step", params={"mode": STANDARD, "count": 40})
        standard = client.get("/api/replay", params={"mode": STANDARD}).json()
        ai = client.get("/api/replay", params={"mode": AI_INTELLIGENCE}).json()
        ai_account = client.get("/api/ai").json()["account"]

        assert standard["cursor"] == REQUIRED + 40
        assert standard["trade_count"] > 0
        assert ai["cursor"] == REQUIRED
        # AI's pool is untouched: no positions, no realised P&L, all capital free.
        assert ai_account["open_position_count"] == 0
        assert ai_account["realized_pnl"] == 0.0
        assert ai_account["committed_capital"] == 0.0

    def test_ai_mode_over_http_trades_into_its_own_book(self) -> None:
        """**Updated in Phase 17G.** Was ``cannot_trade``; 17G defines the contract.

        The response to ``/api/replay`` still reports the *replay*, whose broker the
        AI policy keeps permanently flat. AI's trades are in its book, read from
        ``/api/ai``. That split is deliberate: ``ReplayStateResponse`` stays a
        faithful projection of ``ReplayState``.
        """

        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 400})

        replay = client.get("/api/replay", params={"mode": AI_INTELLIGENCE}).json()
        ai = client.get("/api/ai").json()

        assert replay["status"] == "finished"
        # The AI replay's own broker is inert by design.
        assert replay["trade_count"] == 0
        assert replay["balance"] == STARTING_BALANCE
        # AI's book is where its trades live.
        assert ai["positions"], "expected AI to have opened positions"
        assert ai["account"]["signals_admitted"] > 0
        # Capital is conserved: committed plus free equals the realised balance.
        account = ai["account"]
        assert account["committed_capital"] + account["available_capital"] == (
            pytest.approx(account["realized_balance"])
        )

    def test_reset_over_http_is_mode_scoped(self) -> None:
        client = client_for()

        client.post("/api/replay/step", params={"mode": STANDARD, "count": 400})
        client.post("/api/replay/reset", params={"mode": STANDARD})

        standard = client.get("/api/replay", params={"mode": STANDARD}).json()
        ai = client.get("/api/replay", params={"mode": AI_INTELLIGENCE}).json()

        assert standard["cursor"] == REQUIRED
        assert standard["trade_count"] == 0
        assert ai["cursor"] == REQUIRED
        assert client.get("/api/ai").json()["account"]["open_position_count"] == 0

    def test_phase16_account_routes_describe_standard(self) -> None:
        """No mode parameter there, so they must agree with default /api/replay."""

        client = client_for()
        client.post("/api/replay/step", params={"count": 90})

        account = client.get("/api/account").json()
        replay = client.get("/api/replay").json()

        assert account["balance"] == replay["balance"]
        assert account["trade_count"] == replay["trade_count"]
        assert replay["mode"] == STANDARD

    def test_mode_state_comes_from_the_selected_replay(self) -> None:
        """20. Mutate a mode's replay directly; the response must follow."""

        reg = registry()
        client = TestClient(create_app(ApiConfig(), registry=reg))

        standard = reg.session(STANDARD)
        for _ in range(55):
            standard.step()

        body = client.get("/api/replay", params={"mode": STANDARD}).json()

        assert body["cursor"] == standard.replay.state.cursor
        assert body["balance"] == standard.replay.broker.cash

    def test_replay_response_validates_against_the_schema(self) -> None:
        parsed = ReplayStateResponse.model_validate(
            client_for().get("/api/replay").json()
        )

        assert parsed.mode == STANDARD

    def test_an_injected_replay_stands_for_standard_only(self) -> None:
        """A test that injects a replay must not leak it into other modes."""

        injected = ReplaySession(Replay(SOURCE[:PREFIX], config=baseline_config()))
        client = TestClient(create_app(ApiConfig(), replay=injected))

        assert client.get("/api/replay", params={"mode": STANDARD}).json()[
            "balance"
        ] == injected.replay.broker.cash

        # Asking for AI must build a separate session, not reuse the injection.
        ai = client.get("/api/replay", params={"mode": AI_INTELLIGENCE}).json()
        assert ai["trade_count"] == 0
        assert ai["balance"] == injected.replay.broker.starting_balance
        assert ai["replay_id"] != injected.replay.replay_id
        # And AI's pool is its own, not a view of the injected broker.
        assert client.get("/api/ai").json()["account"]["starting_capital"] == (
            STARTING_BALANCE
        )

        # Standard is unaffected by what the AI route did.
        assert client.get("/api/replay", params={"mode": STANDARD}).json()[
            "cursor"
        ] == injected.replay.state.cursor

    def test_modes_endpoint_is_read_only(self) -> None:
        client = client_for()

        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)("/api/modes").status_code == 405

    def test_ai_endpoint_is_read_only(self) -> None:
        client = client_for()

        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)("/api/ai").status_code == 405


# ---------------------------------------------------------------------------
# scope guards
# ---------------------------------------------------------------------------


class TestScopeGuards:
    def test_no_opaque_or_learned_model_concept(self) -> None:
        """**Updated in Phase 17G**, narrowly.

        17F forbade ``score``, ``threshold`` and ``intelligence`` in ``modes.py``
        because Phase 17G had not defined them and a value invented before it was
        defined would be fabricated. 17G defines them - in
        ``crypto_paper_lab.intelligence``, with a documented formula - so those
        three words are now legitimate configuration.

        What must remain absent is the class of thing the guard was really about: a
        model whose number nobody can reproduce. A learned or remote model would
        make the score unauditable, so it is still forbidden, and so is any claim
        that the score is a probability or a forecast.
        """

        code = code_only(MODES_SOURCE)

        for forbidden in (
            "confidence", "predict", "forecast", "probability", "model",
            "neural", "classif", "feature", "tensor", "training", "learn",
            "guarantee", "risk-free",
        ):
            assert forbidden not in code, forbidden

    def test_standard_still_holds_exactly_one_position(self) -> None:
        """**Updated in Phase 17G**, narrowly.

        17F asserted *no* policy may permit more than one position, because none
        could. 17G introduces the first policy that can - AI Intelligence, served
        by a position book - and the invariant that survives is the narrower and
        more important one: **Standard must remain single-position**, because its
        frozen 344-trade baseline depends on ``PaperBroker``'s one-trade rule.
        """

        assert MODES[STANDARD].policy.max_positions == 1

    def test_only_ai_intelligence_gained_multi_position(self) -> None:
        for mode in known_modes():
            policy = MODES[mode].policy
            if policy is None or mode == AI_INTELLIGENCE:
                continue
            assert policy.max_positions <= 1, mode

    def test_ai_position_limit_is_configurable_not_compiled_in(self) -> None:
        """The limit must be a documented default, not a constant in logic."""

        assert MODES[AI_INTELLIGENCE].policy.max_positions == DEFAULT_MAX_POSITIONS

        tighter = IntelligencePolicy(threshold=90.0, position_limit=1)
        assert tighter.max_positions == 1
        assert tighter.identity()["max_positions"] == 1

    def test_no_manual_close_or_close_all(self) -> None:
        for path in (MODES_SOURCE, REGISTRY_SOURCE):
            code = code_only(path)
            for forbidden in ("close_all", "close_position", "force_close"):
                assert forbidden not in code, forbidden

    def test_registry_imports_nothing_unexpected(self) -> None:
        modules = set()
        for node in ast.walk(
            ast.parse(REGISTRY_SOURCE.read_text(encoding="utf-8"))
        ):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])

        assert modules <= {
            "__future__", "crypto_paper_lab", "paper_api",
        }, modules

    def test_modes_module_imports_only_the_seam(self) -> None:
        modules = set()
        for node in ast.walk(
            ast.parse(MODES_SOURCE.read_text(encoding="utf-8"))
        ):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])

        assert modules == {"__future__", "dataclasses", "typing"}, modules

    def test_no_live_exchange_or_credential_capability(self) -> None:
        for path in (MODES_SOURCE, REGISTRY_SOURCE):
            code = code_only(path)
            for forbidden in (
                "exchange", "binance", "ccxt", "socket", "urllib",
                "requests", "api_key", "secret", "credential", "wallet",
                "authorize",
            ):
                assert forbidden not in code, f"{path.name}: {forbidden}"

    def test_no_persistence_or_scheduler(self) -> None:
        for path in (MODES_SOURCE, REGISTRY_SOURCE):
            code = code_only(path)
            for forbidden in (
                "json", "pickle", "sqlite", "redis", "open(", "threading",
                "asyncio", "Timer", "sched",
            ):
                assert forbidden not in code, f"{path.name}: {forbidden}"

    def test_no_authentication_or_multi_user_concept(self) -> None:
        for path in (MODES_SOURCE, REGISTRY_SOURCE):
            code = code_only(path)
            for forbidden in (
                "token", "jwt", "cookie", "session_key", "login", "user_id",
                "account_id",
            ):
                assert forbidden not in code, f"{path.name}: {forbidden}"

    def test_registry_creates_brokers_only_through_the_engine(self) -> None:
        """A mode must not construct a broker itself."""

        code = code_only(REGISTRY_SOURCE)

        assert "PaperBroker" not in code
        assert "open_from_signal" not in code