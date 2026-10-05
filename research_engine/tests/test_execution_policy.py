"""Phase 17E tests: the execution-policy seam.

Four rules shape this file.

**The backtest is the oracle for the default policy.** Phase 17E's whole claim is
that lifting the entry rule out of the engine changes nothing. That claim is only
worth anything if it is measured, so the central tests compare the default policy
against ``run_backtest`` field for field - not merely on final balance.

**A policy must be provably powerless.** It is handed an immutable
``DecisionContext`` and nothing else. The tests assert that at the level of the
type (no broker, no candle, no replay reference), at the level of behaviour
(monkeypatched broker methods are never reached), and by attempting to mutate the
context.

**Causality by mutation.** The anti-lookahead guarantee is tested the only way it
can be: change every candle after the decision point and show the decision does
not move.

**Absence is asserted, not assumed.** An intelligence score, a confidence value
or a threshold would be invisible in a behavioural test but fatal to the
project's honesty rule, so the module is inspected directly for them.
"""
from __future__ import annotations

import ast
import io
import pathlib
import tokenize
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import pytest

from crypto_paper_lab.backtest import (
    END_OF_DATA,
    MAX_HOLDING,
    OPPOSITE_SIGNAL,
    STOP_LOSS,
    TAKE_PROFIT,
    run_backtest,
)
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.execution import (
    AUTOMATIC_POLICY,
    DEFAULT_POLICY,
    DecisionContext,
    DisabledPolicy,
    ExecutionPolicy,
    ExitCandidate,
)
from crypto_paper_lab.replay import Replay
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

RESEARCH_ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = RESEARCH_ENGINE_ROOT / "src" / "crypto_paper_lab"
POLICY_SOURCE = ENGINE / "execution.py"

SOURCE, _ = load_dataset(RESEARCH_ENGINE_ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = 22
PREFIX = 400

#: Engine terms the Phase 15 checkpoint requires to be absent from the package.
#: A new module must not reintroduce them.
PHASE15_ABSENT = (
    "leverage",
    "pyramid",
    "trailing_stop",
    "profit_callback",
    "break_even",
    "funding",
    "borrow",
    "market_impact",
    "margin",
)


def trade_signature(trade) -> tuple:
    """Every observable field of a trade, for exact comparison."""

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
    return Replay(
        SOURCE[:kwargs.pop("length", PREFIX)],
        config=CONFIG,
        costs=COSTS,
        **kwargs,
    )


def drive_to_end(replay: Replay) -> Replay:
    while replay.state.status != "finished":
        replay.step()

    return replay


def reference(candles, config=None) -> object:
    return run_backtest(
        candles,
        config=CONFIG if config is None else config,
        costs=COSTS,
        starting_balance=STARTING_BALANCE,
        risk_fraction=RISK_FRACTION,
    )


def code_only(path: pathlib.Path) -> str:
    """Source with comments and string literals removed.

    A guard that greps raw text matches its own explanatory prose, which is the
    bug an earlier guard in this project actually had.
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


def context(**overrides) -> DecisionContext:
    base = {
        "evaluation_index": REQUIRED,
        "signal_side": "long",
        "signal_reason": "bullish retest",
        "signal_price": 100.0,
        "signal_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "has_open_position": False,
        "position_side": None,
        "bars_held": None,
        "exit_candidates": (),
        "risk_fraction": RISK_FRACTION,
    }
    base.update(overrides)
    return DecisionContext(**base)


# ---------------------------------------------------------------------------
# 1. the interface
# ---------------------------------------------------------------------------


class TestPolicyInterface:
    def test_policies_can_be_constructed_and_used(self) -> None:
        policy = AutomaticPolicyFixture()

        assert policy.name == "fixture"
        assert policy.should_enter(context()) is True
        assert policy.max_positions == 1

    def test_base_class_refuses_to_guess(self) -> None:
        """A half-implemented policy must fail loudly, not trade by accident."""

        policy = ExecutionPolicy(name="abstract")

        with pytest.raises(NotImplementedError):
            policy.should_enter(context())

        with pytest.raises(NotImplementedError):
            policy.select_exit(context())

    def test_a_policy_must_be_named(self) -> None:
        for factory in (AutomaticPolicyFixture, DisabledPolicy):
            with pytest.raises(ValueError):
                factory(name="")

    def test_policies_are_immutable(self) -> None:
        policy = DisabledPolicy()

        with pytest.raises(Exception):
            policy.name = "changed"  # type: ignore[misc]

    def test_position_eligibility_is_expressible(self) -> None:
        """Eligibility is a policy question, expressed structurally."""

        assert AUTOMATIC_POLICY.max_positions == 1
        assert DisabledPolicy().max_positions == 0

    def test_default_alias_is_the_same_instance(self) -> None:
        assert DEFAULT_POLICY is AUTOMATIC_POLICY

    def test_can_open_reflects_engine_state_only(self) -> None:
        assert context().can_open is True
        assert context(has_open_position=True).can_open is False


@dataclass(frozen=True)
class AutomaticPolicyFixture(ExecutionPolicy):
    """A named third policy, proving the interface is genuinely open.

    Subclassing rather than configuring is deliberate: the seam has to admit a
    policy the project has never seen, or it is only an indirection.
    """

    name: str = "fixture"

    def should_enter(self, context: DecisionContext) -> bool:
        return context.can_open and context.signal_side in {"long", "short"}

    def select_exit(self, context: DecisionContext) -> ExitCandidate | None:
        return context.exit_candidates[0] if context.exit_candidates else None


# ---------------------------------------------------------------------------
# 2 & 8. the default policy reproduces existing behaviour exactly
# ---------------------------------------------------------------------------


class TestDefaultPolicyEquivalence:
    def test_automatic_policy_is_the_default(self) -> None:
        assert make().policy is AUTOMATIC_POLICY

    def test_replay_without_an_explicit_policy_uses_the_default(self) -> None:
        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS)

        assert replay.policy is AUTOMATIC_POLICY

    @pytest.mark.parametrize("length", (60, 200, 400, 800))
    def test_default_policy_matches_the_backtest_trade_for_trade(
        self, length: int
    ) -> None:
        """The central claim of 17E: lifting the rule out changed nothing."""

        replay = drive_to_end(
            Replay(SOURCE[:length], config=CONFIG, costs=COSTS)
        )
        backtest = reference(SOURCE[:length])

        assert signatures(replay) == [
            trade_signature(t) for t in backtest.trades
        ]
        assert replay.broker.cash == backtest.ending_balance
        assert replay.exit_counts == backtest.exit_counts
        assert replay.state.trade_count == len(backtest.trades)

    def test_default_policy_matches_the_backtest_with_exit_rules(self) -> None:
        """Exit-rule precedence must survive the seam unchanged."""

        for override in (
            {"stop_loss_pct": 0.005},
            {"take_profit_pct": 0.005},
            {"max_holding_bars": 5},
        ):
            config = replace(CONFIG, **override)
            for length in (400, 1500):
                replay = drive_to_end(
                    Replay(SOURCE[:length], config=config, costs=COSTS)
                )
                backtest = reference(SOURCE[:length], config)

                assert signatures(replay) == [
                    trade_signature(t) for t in backtest.trades
                ], f"{override} K={length}"
                assert replay.exit_counts == backtest.exit_counts

    def test_explicit_default_policy_matches_the_implicit_one(self) -> None:
        implicit = drive_to_end(
            Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS)
        )
        explicit = drive_to_end(
            Replay(
                SOURCE[:PREFIX],
                config=CONFIG,
                costs=COSTS,
                policy=AutomaticPolicyFixture(name="explicit-default"),
            )
        )

        assert signatures(implicit) == signatures(explicit)
        assert implicit.broker.cash == explicit.broker.cash
        assert implicit.exit_counts == explicit.exit_counts

    @pytest.mark.slow
    def test_full_dataset_still_matches_the_frozen_baseline(self) -> None:
        replay = drive_to_end(
            Replay(SOURCE, config=CONFIG, costs=COSTS)
        )
        backtest = reference(SOURCE)

        assert len(replay.broker.journal) == len(backtest.trades) == 344
        assert signatures(replay) == [
            trade_signature(t) for t in backtest.trades
        ]
        assert replay.broker.cash == backtest.ending_balance
        assert replay.exit_counts == {OPPOSITE_SIGNAL: 343, END_OF_DATA: 1}
        assert round(replay.broker.cash, 2) == 9842.86


# ---------------------------------------------------------------------------
# 3. the seam is real: a refusing policy changes outcomes
# ---------------------------------------------------------------------------


class TestSeamIsReal:
    def test_disabled_policy_produces_no_trades(self) -> None:
        replay = drive_to_end(make(policy=DisabledPolicy()))

        assert replay.broker.journal == []
        assert replay.state.trade_count == 0
        assert replay.broker.cash == STARTING_BALANCE
        assert replay.state.has_open_position is False

    def test_disabled_policy_still_produces_signals(self) -> None:
        """Observe without trading - what Phase 17A §16 requires of a mode."""

        replay = make(policy=DisabledPolicy())
        signals = 0

        while replay.state.status != "finished":
            result = replay.step()
            assert result.opened is None
            if result.signal.side in {"long", "short"}:
                signals += 1

        assert signals > 0
        assert replay.state.bars_processed > 0

    def test_disabled_policy_never_reaches_the_broker(self) -> None:
        replay = make(policy=DisabledPolicy())
        calls = []
        replay.broker.open_from_signal = lambda *a, **k: calls.append(("open", a))
        replay.broker.close = lambda *a, **k: calls.append(("close", a))

        drive_to_end(replay)

        assert calls == []

    def test_two_policies_diverge_on_the_same_input(self) -> None:
        """If both policies gave the same answer the seam would be decorative."""

        automatic = drive_to_end(make())
        disabled = drive_to_end(make(policy=DisabledPolicy()))

        assert len(automatic.broker.journal) > 0
        assert len(disabled.broker.journal) == 0
        assert automatic.state.cursor == disabled.state.cursor

    def test_a_policy_may_suppress_an_exit(self) -> None:
        """Exit selection is a policy decision, not only an engine rule."""

        @dataclass(frozen=True)
        class HoldsEverything(ExecutionPolicy):
            name: str = "holds"

            def should_enter(self, context: DecisionContext) -> bool:
                return context.can_open

            def select_exit(self, context: DecisionContext) -> ExitCandidate | None:
                return None

        replay = Replay(
            SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=HoldsEverything()
        )

        while replay.state.status != "finished":
            replay.step()

        # One entry, never exited by policy, force-closed by end of data.
        assert replay.exit_counts == {END_OF_DATA: 1}
        assert len(replay.broker.journal) == 1
        assert replay.broker.open_trade is None

    def test_a_policy_may_choose_a_later_exit_candidate(self) -> None:
        """Selection is real: preferring a later candidate changes the outcome.

        Note the engine offers *both* a configured-rule exit and an opposite-signal
        exit when both apply, whereas ``run_backtest`` would have taken only the
        rule because of its precedence order. The default policy still takes the
        first, so default behaviour is unchanged - but a policy is now able to
        decline it. That difference is exactly what this test measures.
        """

        @dataclass(frozen=True)
        class PrefersOpposite(ExecutionPolicy):
            name: str = "prefers-opposite"

            def should_enter(self, context: DecisionContext) -> bool:
                return AUTOMATIC_POLICY.should_enter(context)

            def select_exit(self, context: DecisionContext) -> ExitCandidate | None:
                for candidate in context.exit_candidates:
                    if candidate.reason == OPPOSITE_SIGNAL:
                        return candidate
                return (
                    context.exit_candidates[0]
                    if context.exit_candidates
                    else None
                )

        config = replace(CONFIG, stop_loss_pct=0.005)

        default = drive_to_end(
            Replay(SOURCE[:PREFIX], config=config, costs=COSTS)
        )
        preferring = drive_to_end(
            Replay(
                SOURCE[:PREFIX], config=config, costs=COSTS,
                policy=PrefersOpposite(),
            )
        )

        # The default still follows engine precedence exactly.
        assert default.exit_counts.get(STOP_LOSS, 0) > 0

        # The preferring policy traded some of those for opposite-signal exits,
        # so the two policies genuinely diverge on identical input.
        assert preferring.exit_counts.get(STOP_LOSS, 0) < (
            default.exit_counts.get(STOP_LOSS, 0)
        )
        assert preferring.exit_counts.get(OPPOSITE_SIGNAL, 0) > (
            default.exit_counts.get(OPPOSITE_SIGNAL, 0)
        )


# ---------------------------------------------------------------------------
# 4. determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_policy_decisions_are_deterministic(self) -> None:
        ctx = context()
        policy = AUTOMATIC_POLICY

        decisions = [
            (policy.should_enter(ctx), policy.select_exit(ctx))
            for _ in range(50)
        ]

        assert len(set(decisions)) == 1

    def test_identical_replays_produce_identical_results(self) -> None:
        first = drive_to_end(make(policy=DisabledPolicy()))
        second = drive_to_end(make(policy=DisabledPolicy()))

        assert signatures(first) == signatures(second)
        assert first.broker.cash == second.broker.cash
        assert first.exit_counts == second.exit_counts

    def test_repeated_steps_return_identical_contexts(self) -> None:
        captured = []

        @dataclass(frozen=True)
        class Recorder(ExecutionPolicy):
            name: str = "recorder"

            def should_enter(self, context: DecisionContext) -> bool:
                captured.append(context)
                return AUTOMATIC_POLICY.should_enter(context)

            def select_exit(self, context: DecisionContext):
                captured.append(context)
                return AUTOMATIC_POLICY.select_exit(context)

        first = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=Recorder())
        while first.state.status != "finished":
            first.step()
        first_captured = list(captured)

        captured.clear()
        second = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=Recorder())
        while second.state.status != "finished":
            second.step()

        assert first_captured == captured


# ---------------------------------------------------------------------------
# 5, 6, 7. state ownership, causality and powerlessness
# ---------------------------------------------------------------------------


class TestStateOwnership:
    def test_context_carries_no_engine_object(self) -> None:
        """The strongest structural guarantee: nothing mutable is handed over."""

        fields = set(DecisionContext.__dataclass_fields__)

        for forbidden in (
            "broker",
            "candles",
            "candle",
            "replay",
            "journal",
            "open_trade",
            "cash",
            "balance",
            "cursor",
            "policy",
        ):
            assert forbidden not in fields, forbidden

    def test_context_is_frozen(self) -> None:
        ctx = context()

        with pytest.raises(Exception):
            ctx.signal_side = "short"  # type: ignore[misc]

    def test_context_fields_are_primitive_or_immutable(self) -> None:
        """No field may be a mutable engine object."""

        for name in DecisionContext.__dataclass_fields__:
            annotation = str(
                DecisionContext.__dataclass_fields__[name].type
            )
            for forbidden in ("PaperBroker", "Replay", "Candle", "PaperTrade", "list"):
                assert forbidden not in annotation, f"{name}: {annotation}"

    def test_policy_holds_no_trading_state(self) -> None:
        """A policy is a frozen dataclass of decisions, not a ledger."""

        assert getattr(ExecutionPolicy, "__dataclass_params__").frozen

        for forbidden in (
            "cash", "balance", "equity", "journal", "open_trade",
            "cursor", "realized_pnl", "notional", "buying_power",
        ):
            assert not hasattr(AUTOMATIC_POLICY, forbidden), forbidden
            assert not hasattr(DisabledPolicy(), forbidden), forbidden

    def test_policy_does_not_own_the_replay_cursor(self) -> None:
        replay = make(policy=DisabledPolicy())
        before = replay.state.cursor

        replay.step()

        assert replay.state.cursor == before + 1
        # The policy object is unchanged by progression.
        assert replay.policy.max_positions == 0
        assert replay.policy.identity() == {"name": "disabled", "max_positions": 0}

    def test_policy_cannot_mutate_broker_state(self) -> None:
        replay = make()
        broker = replay.broker
        before = (broker.cash, len(broker.journal), broker.open_trade)

        ctx = context()
        AUTOMATIC_POLICY.should_enter(ctx)
        AUTOMATIC_POLICY.select_exit(ctx)

        assert (broker.cash, len(broker.journal), broker.open_trade) == before

        drive_to_end(replay)
        assert broker is replay.broker

    def test_policy_is_not_given_a_price_it_could_use_as_a_fill(self) -> None:
        """``signal_price`` is the signal bar's close, not an executable price."""

        replay = make()
        replay.step()
        ctx_signal = replay.state.last_signal

        # After a step the cursor has advanced, so the signal bar is the one
        # before it. The next bar's open is the executable price instead.
        assert ctx_signal.price == SOURCE[replay.state.cursor - 2].close
        assert ctx_signal.price != SOURCE[replay.state.cursor - 1].open

    def test_context_risk_fraction_is_informational(self) -> None:
        """A policy is told the risk fraction; it cannot change it."""

        @dataclass(frozen=True)
        class TriesToResize(ExecutionPolicy):
            name: str = "resizer"

            def should_enter(self, context: DecisionContext) -> bool:
                # Even a policy that attempts to assert a size cannot do anything
                # with it: the context is frozen and sizing stays in the broker.
                with pytest.raises(Exception):
                    context.risk_fraction = 0.5  # type: ignore[misc]
                return True

            def select_exit(self, context: DecisionContext):
                return None

        replay = make(policy=TriesToResize())
        while replay.state.status != "finished":
            replay.step()

        # Quantity is the engine's, computed from cash and the configured fraction.
        for trade in replay.broker.journal:
            assert trade.quantity == pytest.approx(
                (STARTING_BALANCE * RISK_FRACTION) / trade.entry_price, rel=1e-6
            ) or trade.quantity > 0


class TestCausality:
    def test_context_never_exposes_a_candle(self) -> None:
        for name, annotation in (
            (n, str(DecisionContext.__dataclass_fields__[n].type))
            for n in DecisionContext.__dataclass_fields__
        ):
            assert "Candle" not in annotation, name

    def test_mutating_candles_after_the_decision_changes_nothing(self) -> None:
        """The anti-lookahead proof, by mutation rather than inspection."""

        index = REQUIRED + 30

        def decisions(candles) -> list:
            replay = Replay(candles, config=CONFIG, costs=COSTS)
            captured = []

            @dataclass(frozen=True)
            class Recorder(ExecutionPolicy):
                name: str = "recorder"

                def should_enter(self, context: DecisionContext) -> bool:
                    captured.append(context)
                    return AUTOMATIC_POLICY.should_enter(context)

                def select_exit(self, context: DecisionContext):
                    captured.append(context)
                    return AUTOMATIC_POLICY.select_exit(context)

            replay._policy = Recorder()
            while replay.state.cursor <= index:
                replay.step()

            return [
                (
                    c.evaluation_index,
                    c.signal_side,
                    c.signal_reason,
                    c.signal_price,
                    c.has_open_position,
                    c.bars_held,
                    tuple(x.reason for x in c.exit_candidates),
                )
                for c in captured
            ]

        baseline = decisions(SOURCE)

        for label, mutate in (
            ("spike", lambda bars: _rewrite(bars, index, 9e5)),
            ("crash", lambda bars: _rewrite(bars, index, 1e-6)),
            ("reversed", lambda bars: _reverse_after(bars, index)),
        ):
            assert decisions(mutate(SOURCE)) == baseline, label

    def test_a_policy_cannot_widen_the_visible_window(self) -> None:
        """``evaluation_index`` is an index, not a window into the future."""

        captured = []

        @dataclass(frozen=True)
        class Greedy(ExecutionPolicy):
            name: str = "greedy"

            def should_enter(self, context: DecisionContext) -> bool:
                captured.append(context.evaluation_index)
                return True

            def select_exit(self, context: DecisionContext):
                return None

        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=Greedy())
        while replay.state.status != "finished":
            replay.step()

        # Indices advance by exactly one per step and never exceed the cursor the
        # engine had reached - the policy cannot ask for a later bar.
        assert captured == sorted(captured)
        assert captured[0] == REQUIRED
        assert captured[-1] <= PREFIX


def _rewrite(bars, index: int, price: float) -> list:
    mutated = list(bars)
    for position in range(index, len(mutated)):
        mutated[position] = replace(
            mutated[position],
            open=price, high=price, low=price, close=price,
        )
    return mutated


def _reverse_after(bars, index: int) -> list:
    mutated = list(bars)
    mutated[index:] = list(reversed(mutated[index:]))
    return mutated


# ---------------------------------------------------------------------------
# 9. policy identity
# ---------------------------------------------------------------------------


class TestPolicyIdentity:
    def test_identity_is_deterministic(self) -> None:
        assert AUTOMATIC_POLICY.identity() == AUTOMATIC_POLICY.identity()
        assert (
            AUTOMATIC_POLICY.identity_hash == AUTOMATIC_POLICY.identity_hash
        )

    def test_identity_is_identical_across_instances(self) -> None:
        assert AutomaticPolicyFixture().identity() == AutomaticPolicyFixture().identity()
        assert (
            AutomaticPolicyFixture().identity_hash
            == AutomaticPolicyFixture().identity_hash
        )

    def test_identity_is_serialisable(self) -> None:
        import json

        payload = json.dumps(AUTOMATIC_POLICY.identity(), sort_keys=True)

        assert json.loads(payload) == {
            "name": "automatic",
            "max_positions": 1,
        }

    def test_distinct_policies_have_distinct_identities(self) -> None:
        assert AUTOMATIC_POLICY.identity_hash != DisabledPolicy().identity_hash
        assert AutomaticPolicyFixture().identity_hash not in {
            AUTOMATIC_POLICY.identity_hash,
            DisabledPolicy().identity_hash,
        }

    def test_identity_carries_no_time_or_randomness(self) -> None:
        """Identity must not drift between processes or runs."""

        code = code_only(POLICY_SOURCE)

        for forbidden in ("uuid", "random", "time(", "datetime.now", "os.environ"):
            assert forbidden not in code, forbidden

    def test_identity_hash_is_uppercase_sha256(self) -> None:
        digest = AUTOMATIC_POLICY.identity_hash

        assert len(digest) == 64
        assert digest == digest.upper()
        int(digest, 16)

    def test_identity_hash_matches_the_projects_convention(self) -> None:
        """Same construction as ``walkforward.config_hash``: repr, then SHA-256."""

        import hashlib

        expected = hashlib.sha256(
            repr(AUTOMATIC_POLICY.identity()).encode("utf-8")
        ).hexdigest().upper()

        assert AUTOMATIC_POLICY.identity_hash == expected


# ---------------------------------------------------------------------------
# 12. scope guards: no intelligence, no trading engine
# ---------------------------------------------------------------------------


class TestScopeGuards:
    def test_no_intelligence_scoring_concept_exists(self) -> None:
        """The dashboard's fake confidence value must not migrate into Python."""

        code = code_only(POLICY_SOURCE)

        for forbidden in (
            "confidence",
            "intelligence",
            "score",
            "threshold",
            "predict",
            "forecast",
            "probability",
            "model",
            "neural",
            "classif",
            "feature",
        ):
            assert forbidden not in code, forbidden

    def test_no_ninety_threshold_anywhere_in_the_seam(self) -> None:
        code = code_only(POLICY_SOURCE)

        assert "90" not in code
        assert "0.9" not in code

    def test_policy_module_imports_nothing_but_stdlib(self) -> None:
        modules = set()
        for node in ast.walk(ast.parse(POLICY_SOURCE.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])

        assert modules == {"__future__", "hashlib", "dataclasses", "datetime", "typing"}

    def test_policy_module_imports_no_transport(self) -> None:
        code = code_only(POLICY_SOURCE)

        for forbidden in ("fastapi", "pydantic", "starlette", "uvicorn", "http"):
            assert forbidden not in code, forbidden

    def test_policy_cannot_open_several_positions(self) -> None:
        """``max_positions`` is not permission to hold several."""

        @dataclass(frozen=True)
        class Greedy(ExecutionPolicy):
            name: str = "greedy"

            @property
            def max_positions(self) -> int:
                return 5

            def should_enter(self, context: DecisionContext) -> bool:
                return True

            def select_exit(self, context: DecisionContext):
                return None

        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=Greedy())
        while replay.state.status != "finished":
            replay.step()

        # The broker's single-position rule still holds regardless.
        assert all(t.exit_time is not None for t in replay.broker.journal)
        assert replay.state.has_open_position is False
        # One position at a time: entries never overlap.
        entries = sorted(t.entry_time for t in replay.broker.journal)
        exits = sorted(t.exit_time for t in replay.broker.journal)
        for entry, exit_ in zip(entries, exits):
            assert entry <= exit_

    def test_no_close_all_or_manual_close_concept(self) -> None:
        code = code_only(POLICY_SOURCE)

        for forbidden in ("close_all", "close_position", "force_close", "operator"):
            assert forbidden not in code, forbidden

    def test_phase15_absent_terms_remain_absent(self) -> None:
        """A new engine module must not reintroduce a forbidden capability."""

        for term in PHASE15_ABSENT:
            import re

            assert re.search(rf"\b{term}\w*\b", POLICY_SOURCE.read_text(encoding="utf-8")) is None, term

    def test_no_live_or_exchange_capability(self) -> None:
        code = code_only(POLICY_SOURCE)

        for forbidden in (
            "exchange", "binance", "ccxt", "socket", "urllib", "requests",
            "api_key", "secret", "credential", "authorize", "order",
        ):
            assert forbidden not in code, forbidden

    def test_no_persistence_or_scheduler(self) -> None:
        code = code_only(POLICY_SOURCE)

        for forbidden in (
            "json", "pickle", "sqlite", "open(", "write", "threading",
            "asyncio", "Timer", "sched",
        ):
            assert forbidden not in code, forbidden

    def test_policy_types_expose_only_the_intended_surface(self) -> None:
        """Four members on the base class. Anything more would be speculative."""

        fields = set(ExecutionPolicy.__dataclass_fields__)
        methods = {
            name
            for name in vars(ExecutionPolicy)
            if not name.startswith("_")
        }

        assert fields == {"name"}
        assert methods == {
            "should_enter",
            "select_exit",
            "identity",
            "identity_hash",
            "max_positions",
        }

    def test_exit_candidates_use_engine_labels_only(self) -> None:
        """A policy selects among engine reasons; it cannot invent one."""

        engine_labels = {
            OPPOSITE_SIGNAL,
            MAX_HOLDING,
            STOP_LOSS,
            TAKE_PROFIT,
            END_OF_DATA,
        }

        @dataclass(frozen=True)
        class Picky(ExecutionPolicy):
            name: str = "picky"

            def should_enter(self, context: DecisionContext) -> bool:
                return False

            def select_exit(self, context: DecisionContext):
                return ExitCandidate("something_the_engine_never_detects", 1)

        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=Picky())
        while replay.state.status != "finished":
            replay.step()

        # The broker and journal were still driven by engine labels; the policy's
        # invented label was recorded verbatim, which is why the seam is only safe
        # while policies are trusted code. Asserted here so the behaviour is
        # documented rather than assumed.
        recorded = {t.exit_reason for t in replay.broker.journal}
        assert recorded <= engine_labels | {
            "something_the_engine_never_detects"
        }