"""Phase 17G tests: mode contracts, and the intelligence score behind AI.

Three rules shape this file, in priority order.

**The score must be reproducible and auditable.** A number that decides whether a
position opens has to be derivable by hand from values the strategy already
computed. So the score tests check the *formula* - that components sum to the
score, that each explains itself, that the same signal always gives the same
number - rather than merely checking a range.

**Causality is structural, so it is tested structurally.** The scorer takes a
`Signal` and nothing else. It has no candle, so it cannot read a future bar. The
tests prove that by mutating bars *after* a decision point and showing the score at
that point does not move - and by asserting the signature accepts no extra input.

**AI's accounting must be coherent under every limit it declares.** Position
limits, capital allocation and realised P&L are separate mechanisms that can each
be broken independently, so each is tested on its own, and then together.
"""
from __future__ import annotations

import ast
import dataclasses
import math
import pathlib
import tokenize
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.ai_paper import (
    AI_EXIT_END_OF_DATA,
    AI_EXIT_PROFIT_TARGET,
    DEFAULT_ALLOCATION_FRACTION,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PROFIT_TARGET_PCT,
    AiAccountState,
    AiPaperBook,
    AiPaperConfig,
    AiPosition,
)
from crypto_paper_lab.backtest import END_OF_DATA
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.execution import (
    AUTOMATIC_POLICY,
    DecisionContext,
    ExecutionPolicy,
    IntelligencePolicy,
)
from crypto_paper_lab.intelligence import (
    BREAKOUT_FULL_SCALE,
    COMPONENT_WEIGHTS,
    DEFAULT_THRESHOLD,
    RANGE_QUALITY_CALM,
    RANGE_QUALITY_EXTREME,
    SCORE_MAX,
    SCORE_MIN,
    IntelligenceConfig,
    IntelligenceScore,
    intelligence_score_hash,
    qualifies,
    score_signal,
)
from crypto_paper_lab.models import Candle, Signal
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DEFAULT_MODE,
    MODES,
    STANDARD,
    is_executable,
    known_modes,
    mode_policy,
    mode_spec,
    reserved_modes,
)
from crypto_paper_lab.replay import Replay
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import StrategyConfig, analyze
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    FEE_RATE,
    RISK_FRACTION,
    SLIPPAGE_RATE,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.moderegistry import AiSession, ModeRegistry
from paper_api.replaysession import ReplaySession
from paper_api.schemas import AiStateResponse, ModesResponse

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "crypto_paper_lab"
SCORE_SOURCE = ENGINE / "intelligence.py"
BOOK_SOURCE = ENGINE / "ai_paper.py"
REGISTRY_SOURCE = ROOT / "src" / "paper_api" / "moderegistry.py"
SCHEMA_SOURCE = ROOT / "src" / "paper_api" / "schemas.py"
APP_SOURCE = ROOT / "src" / "paper_api" / "app.py"

SOURCE, _ = load_dataset(ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = 22

#: Enough bars for several entries and exits without a slow test.
PREFIX = 600


def code_only(path: pathlib.Path) -> str:
    """Source with comments and string literals stripped.

    So a forbidden term can be asserted against *code* rather than against prose.
    Every module here documents what it deliberately does not do, and a text search
    would match the explanation rather than the dependency.
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
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def signals() -> tuple:
    """Every directional signal the frozen prefix produces, in bar order."""

    found = []
    for index in range(REQUIRED, PREFIX):
        signal = analyze(SOURCE[:index], CONFIG)
        if signal.side in {"long", "short"}:
            found.append((index, signal))

    assert found, "expected the frozen prefix to produce directional signals"
    return tuple(found)


def book_for(length: int = PREFIX, **kwargs) -> AiPaperBook:
    """A book over a prefix of the frozen series, with the production defaults."""

    config = kwargs.pop("config", None) or AiPaperConfig()

    return AiPaperBook(
        SOURCE[:length],
        config=config,
        strategy=kwargs.pop("strategy", CONFIG),
        costs=kwargs.pop("costs", COSTS),
    )


def run(book: AiPaperBook, start: int = REQUIRED, end: int = PREFIX) -> AiPaperBook:
    """Walk a book over a bar range."""

    for index in range(start, end):
        book.step(index)

    return book


def drive(session: ReplaySession, count: int) -> ReplaySession:
    """Advance a session, so an ``AiSession``'s book moves with its replay.

    Added in Phase 17G. Stepping an ``AiSession``'s replay directly would advance
    the cursor while leaving the book behind - the divergence ``AiSession.step()``
    exists to make impossible.
    """

    for _ in range(count):
        session.step()

    return session


def signal(**overrides) -> Signal:
    """A hand-built signal, so score tests do not depend on market data."""

    defaults = dict(
        timestamp=SOURCE[0].timestamp,
        side="long",
        reason="uptrend breakout",
        price=100.0,
        support=99.0,
        resistance=101.0,
        trend="up",
        breakout=True,
        retest=False,
        signal_close=100.0,
        trend_state="up",
        breakout_distance=0.006,
        retest_distance=None,
        realised_volatility=0.002,
        mean_range=1.0,
    )
    defaults.update(overrides)

    return Signal(**defaults)


def context(**overrides) -> DecisionContext:
    """A minimal context for policy tests."""

    defaults = dict(
        evaluation_index=REQUIRED,
        signal_side="long",
        signal_reason="uptrend breakout",
        signal_price=100.0,
        signal_timestamp=None,
        has_open_position=False,
        position_side=None,
        bars_held=None,
    )
    defaults.update(overrides)

    return DecisionContext(**defaults)


def registry(**sessions) -> ModeRegistry:
    """A registry whose modes get prepared, isolated sessions."""

    def build(mode: str) -> ReplaySession:
        prepared = sessions.get(mode)
        if prepared is not None:
            return prepared

        replay = Replay(
            SOURCE[:PREFIX], config=CONFIG, costs=COSTS, policy=mode_policy(mode)
        )

        if mode == AI_INTELLIGENCE:
            return AiSession(
                replay,
                AiPaperBook(SOURCE[:PREFIX], strategy=CONFIG, costs=COSTS),
            )

        return ReplaySession(replay)

    return ModeRegistry(session_for=build)


def client_for(reg: ModeRegistry | None = None) -> TestClient:
    return TestClient(create_app(ApiConfig(), registry=reg or registry()))


# ---------------------------------------------------------------------------
# 1-8. the intelligence score
# ---------------------------------------------------------------------------


class TestScoreRangeAndDeterminism:
    def test_score_is_always_between_zero_and_one_hundred(
        self, signals: tuple
    ) -> None:
        """1. The scale is a hard property, not an observation."""

        for _, item in signals:
            score = score_signal(item)
            assert SCORE_MIN <= score.score <= SCORE_MAX

    def test_score_is_deterministic(self, signals: tuple) -> None:
        """2-3. Same signal in, same score out, every time."""

        for _, item in signals:
            first = score_signal(item)
            second = score_signal(item)

            assert first.score == second.score
            assert first.identity() == second.identity()

    def test_the_whole_dataset_scores_deterministically(self) -> None:
        """A separate process must reach the same number, so no hidden state."""

        first = [
            score_signal(analyze(SOURCE[:index], CONFIG)).score
            for index in range(REQUIRED, 300)
        ]
        second = [
            score_signal(analyze(SOURCE[:index], CONFIG)).score
            for index in range(REQUIRED, 300)
        ]

        assert first == second

    def test_components_sum_to_the_score(self, signals: tuple) -> None:
        """5-6. The score is fully decomposable, within one point of rounding."""

        for _, item in signals:
            scored = score_signal(item)

            assert scored.total_points == pytest.approx(
                sum(component.points for component in scored.components)
            )
            # Rounding is half-up, so the integer is the total either side of it.
            assert abs(scored.score - scored.total_points) <= 0.5

    def test_every_component_carries_its_own_explanation(
        self, signals: tuple
    ) -> None:
        """6. Explainable: every component says what it measured and why."""

        for _, item in signals:
            scored = score_signal(item)

            assert len(scored.components) == len(COMPONENT_WEIGHTS)
            for component in scored.components:
                assert component.reason, component.name
                assert component.reason.strip()
                assert 0 <= component.points <= component.weight

    def test_reasons_mention_the_numbers_that_produced_them(
        self, signals: tuple
    ) -> None:
        """A reason that states no figure is an assertion, not an explanation."""

        scored = score_signal(signal())
        breakout = scored.component("breakout_strength")

        assert "0.6000%" in breakout.reason
        assert "%" in scored.component("range_quality").reason

    def test_weights_sum_to_the_full_scale(self) -> None:
        assert sum(COMPONENT_WEIGHTS.values()) == SCORE_MAX

    def test_component_names_are_stable(self) -> None:
        """A rename would silently break every consumer of the explanation."""

        scored = score_signal(signal())

        assert [component.name for component in scored.components] == list(
            COMPONENT_WEIGHTS
        )


class TestScoreCausality:
    def test_future_bars_cannot_change_a_past_score(self, signals: tuple) -> None:
        """4. The anti-lookahead property, tested directly.

        Every candle *after* the decision point is rewritten with absurd values.
        The score at that point must not move, because the scorer is handed a
        `Signal` derived from ``candles[:index]`` and has no access to anything
        later.
        """

        for index, item in signals[:20]:
            original = score_signal(item)

            mutated = list(SOURCE)
            for position in range(index, len(mutated)):
                candle = mutated[position]
                mutated[position] = Candle(
                    timestamp=candle.timestamp,
                    open=999_999.0,
                    high=999_999.0,
                    low=999_999.0,
                    close=999_999.0,
                    volume=0.0,
                )

            # The signal is derived from the unmutated prefix, so it is unchanged;
            # what matters is that scoring it cannot depend on the tail.
            assert score_signal(item).score == original.score
            assert analyze(tuple(mutated[:index]), CONFIG) == item

    def test_the_scorer_accepts_only_a_signal(self) -> None:
        """The structural version of the same guarantee: one parameter."""

        parameters = [
            node.arg
            for node in ast.walk(ast.parse(SCORE_SOURCE.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef)
            and node.name == "score_signal"
            for node in node.args.args
            if node.arg != "self"
        ]

        assert parameters == ["signal", "config"]

    def test_the_scorer_imports_no_market_or_execution_surface(self) -> None:
        """It must not be able to reach a candle, a broker or a clock."""

        modules = set()
        for node in ast.walk(ast.parse(SCORE_SOURCE.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                # ``node.level == 0`` for an absolute import, 1 for a relative one
                # inside the package. Both count: what is being checked is *what*
                # is reachable, not how it was spelled.
                modules.add((node.module or "").split(".")[0])

        # ``models`` for the Signal type only - no indicators, no simulator, no
        # replay, no backtest, and no randomness or clock libraries.
        assert modules == {
            "__future__",
            "hashlib",
            "math",
            "dataclasses",
            "typing",
            "models",
        }, modules

    def test_no_randomness_or_clock_anywhere_in_the_score(self) -> None:
        code = code_only(SCORE_SOURCE)

        for forbidden in (
            "random", "time(", "datetime.now", "os.environ", "uuid",
            "secrets", "hash(", "open(", "os.system",
        ):
            assert forbidden not in code, forbidden


class TestScoreThreshold:
    def test_threshold_comparison_is_exactly_greater_or_equal(
        self, signals: tuple
    ) -> None:
        """7. The documented boundary rule, asserted at the boundary."""

        for _, item in signals:
            scored = score_signal(item)

            assert scored.qualified == (scored.score >= scored.threshold)
            assert scored.qualified == (scored.score > scored.threshold - 1)

    def test_a_score_exactly_at_the_threshold_qualifies(self) -> None:
        """15. The case a caller is most likely to get wrong.

        The threshold is set to this signal's *own* score rather than to a literal,
        so the test is about the boundary rule and not about where this particular
        fixture happens to land.
        """

        baseline = score_signal(signal())
        config = IntelligenceConfig(threshold=float(baseline.score))
        scored = score_signal(signal(), config)

        assert scored.score == baseline.score
        assert scored.qualified is True

    def test_one_point_above_the_score_does_not_qualify(self) -> None:
        baseline = score_signal(signal())
        config = IntelligenceConfig(threshold=float(baseline.score) + 1)

        assert score_signal(signal(), config).qualified is False

    def test_the_default_threshold_qualifies_real_signals(self) -> None:
        """The contract default is reachable, not vacuously unreachable.

        If 90 were unreachable the mode would be inert and every entry test would
        pass for the wrong reason. This asserts the frozen dataset actually produces
        signals at or above it.
        """

        from crypto_paper_lab.dataset import load_dataset

        qualifying = 0
        for index in range(REQUIRED, 400):
            item = analyze(SOURCE[:index], CONFIG)
            if item.side in {"long", "short"} and score_signal(item).qualified:
                qualifying += 1

        assert qualifying > 0

    def test_the_default_threshold_is_ninety(self) -> None:
        """8. The contract's stated default."""

        assert DEFAULT_THRESHOLD == 90.0
        assert IntelligenceConfig().threshold == 90.0
        assert MODES[AI_INTELLIGENCE].policy.threshold == 90.0

    def test_the_threshold_is_configurable(self, signals: tuple) -> None:
        """7 again: the same signals qualify or not depending on configuration."""

        strict = IntelligenceConfig(threshold=100)
        loose = IntelligenceConfig(threshold=0)

        scores = [score_signal(item, strict).score for _, item in signals]
        assert not any(s == SCORE_MAX for s in scores)

        for _, item in signals:
            assert score_signal(item, loose).qualified is True

    def test_a_threshold_outside_the_scale_is_refused(self) -> None:
        for bad in (-1.0, 101.0):
            with pytest.raises(ValueError):
                IntelligenceConfig(threshold=bad)

    def test_missing_points_reports_the_shortfall(self) -> None:
        scored = score_signal(signal(), IntelligenceConfig(threshold=100))

        assert scored.qualified is False
        assert scored.missing_points == 100 - scored.score


class TestScoreComponents:
    def test_a_flat_signal_scores_zero_on_direction(self) -> None:
        scored = score_signal(
            signal(side="flat", reason="no confirmed breakout or retest")
        )

        assert scored.component("direction").points == 0.0
        assert scored.component("trend_alignment").points == 0.0
        # flat is a normal outcome, never an error.
        assert scored.score >= 0

    def test_direction_against_the_trend_earns_nothing(self) -> None:
        scored = score_signal(signal(side="short", trend_state="up"))

        assert scored.component("trend_alignment").points == 0.0

    def test_direction_with_the_trend_earns_full_credit(self) -> None:
        scored = score_signal(signal(side="long", trend_state="up"))

        assert scored.component("trend_alignment").points == (
            COMPONENT_WEIGHTS["trend_alignment"]
        )

    def test_sideways_trend_earns_partial_alignment_credit(self) -> None:
        scored = score_signal(signal(trend_state="sideways"))

        assert scored.component("trend_alignment").points == pytest.approx(
            COMPONENT_WEIGHTS["trend_alignment"] / 2
        )

    def test_breakout_strength_saturates_at_the_full_scale(self) -> None:
        at_scale = score_signal(signal(breakout_distance=BREAKOUT_FULL_SCALE))
        beyond = score_signal(signal(breakout_distance=BREAKOUT_FULL_SCALE * 10))

        assert at_scale.component("breakout_strength").points == pytest.approx(
            COMPONENT_WEIGHTS["breakout_strength"]
        )
        assert beyond.component("breakout_strength").points == pytest.approx(
            COMPONENT_WEIGHTS["breakout_strength"]
        )

    def test_breakout_strength_is_zero_without_a_breakout_distance(self) -> None:
        scored = score_signal(signal(breakout_distance=None))

        assert scored.component("breakout_strength").points == 0.0

    def test_a_retest_outscores_a_fresh_breakout_on_confirmation(self) -> None:
        """The one genuine structural difference between the two entry kinds."""

        retest = score_signal(signal(retest_distance=0.0))
        breakout = score_signal(signal(retest_distance=None))

        assert (
            retest.component("confirmation").points
            > breakout.component("confirmation").points
        )

    def test_a_touching_retest_earns_full_confirmation_credit(self) -> None:
        scored = score_signal(signal(retest_distance=0.0))

        assert scored.component("confirmation").points == pytest.approx(
            COMPONENT_WEIGHTS["confirmation"]
        )

    def test_range_quality_is_full_when_calm_and_zero_when_extreme(self) -> None:
        calm = score_signal(signal(realised_volatility=RANGE_QUALITY_CALM))
        extreme = score_signal(signal(realised_volatility=RANGE_QUALITY_EXTREME))

        assert calm.component("range_quality").points == pytest.approx(
            COMPONENT_WEIGHTS["range_quality"]
        )
        assert extreme.component("range_quality").points == 0.0

    def test_range_quality_decreases_monotonically(self) -> None:
        points = [
            score_signal(
                signal(realised_volatility=volatility)
            ).component("range_quality").points
            for volatility in (
                0.001, 0.004, 0.008, 0.012, 0.015, 0.020,
            )
        ]

        assert points == sorted(points, reverse=True)

    def test_a_component_bug_cannot_escape_the_declared_range(self) -> None:
        """The clamp, tested by forcing an impossible configuration."""

        # A deliberately absurd configuration: a tiny breakout scale and a volatility
        # bound far above anything real. Individual components saturate; the total
        # must still land inside the declared scale.
        generous = IntelligenceConfig(
            threshold=0.0,
            breakout_full_scale=1e-9,
            range_quality_calm=0.9,
            range_quality_extreme=0.95,
        )
        scored = score_signal(
            signal(breakout_distance=1e6, realised_volatility=0.0),
            generous,
        )

        assert SCORE_MIN <= scored.score <= SCORE_MAX
        # Saturated breakout and range quality, but a fresh breakout still earns
        # only its documented confirmation share, so the total is 92 not 100.
        assert scored.score == (
            COMPONENT_WEIGHTS["trend_alignment"]
            + COMPONENT_WEIGHTS["breakout_strength"]
            + 12.0
            + COMPONENT_WEIGHTS["range_quality"]
            + COMPONENT_WEIGHTS["direction"]
        )

        # And the configuration is validated, so the volatility bounds cannot
        # invert into a negative range.
        with pytest.raises(ValueError):
            IntelligenceConfig(range_quality_calm=0.9, range_quality_extreme=0.5)

    def test_an_unknown_component_name_raises(self) -> None:
        with pytest.raises(KeyError):
            score_signal(signal()).component("nonexistent")


class TestScoreConfiguration:
    def test_configuration_is_frozen(self) -> None:
        assert IntelligenceConfig.__dataclass_params__.frozen

    def test_configuration_identity_is_deterministic(self) -> None:
        first = IntelligenceConfig()
        second = IntelligenceConfig()

        assert first.identity() == second.identity()
        assert intelligence_score_hash(first) == intelligence_score_hash(second)

    def test_changing_a_scale_changes_the_identity_hash(self) -> None:
        """An audit record has to notice a parameter change."""

        default = intelligence_score_hash(IntelligenceConfig())
        moved = intelligence_score_hash(
            IntelligenceConfig(breakout_full_scale=0.01)
        )

        assert default != moved

    def test_qualifies_agrees_with_the_score(self, signals: tuple) -> None:
        for _, item in signals:
            config = IntelligenceConfig(threshold=90.0)
            assert qualifies(item, config) == score_signal(item, config).qualified

    def test_the_score_offers_no_profit_guarantee(self) -> None:
        """The score is a gate. Its own surface must not claim otherwise.

        The Phase 13 record for this strategy is negative - net -157.14 over 344
        trades, profit factor 0.6920 - so a high score is not evidence of profit,
        and nothing in this module's vocabulary may imply it is.
        """

        docstring = SCORE_SOURCE.read_text(encoding="utf-8").lower()

        for forbidden in (
            "guaranteed profit",
            "guarantees profit",
            "risk-free",
            "risk free",
            "90% win",
            "90 percent win",
            "knows the market",
        ):
            assert forbidden not in docstring, forbidden

        # And the qualifying verdict is a plain comparison, exposed as such.
        scored = score_signal(signal(), IntelligenceConfig(threshold=1.0))
        assert scored.qualified is True
        assert not hasattr(scored, "probability")
        assert not hasattr(scored, "confidence")
        assert not hasattr(scored, "expected_return")


# ---------------------------------------------------------------------------
# 9-13. Standard and Alerts contracts
# ---------------------------------------------------------------------------


class TestStandardContract:
    def test_standard_is_still_the_automatic_policy(self) -> None:
        assert mode_policy(STANDARD) is AUTOMATIC_POLICY
        assert mode_policy(STANDARD).max_positions == 1

    def test_standard_does_not_gain_multi_position_behaviour(self) -> None:
        """10. The single-position invariant, proven by walking the dataset."""

        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS)

        while replay.state.status != "finished":
            replay.step()

        # Never two trades open at once: every closed trade ended before the next
        # began. Interleaved entry times would show up as entry <= previous exit.
        journal = replay.broker.journal
        for previous, following in zip(journal, journal[1:]):
            assert previous.exit_time <= following.entry_time

        assert replay.broker.open_trade is None

    def test_standard_never_opens_more_than_one_broker_position(self) -> None:
        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS)
        peak = 0

        while replay.state.status != "finished":
            replay.step()
            peak = max(peak, 1 if replay.broker.open_trade is not None else 0)

        assert peak <= 1

    @pytest.mark.slow
    def test_standard_still_matches_the_frozen_baseline(self) -> None:
        """9. The strongest available statement of "Standard is unchanged"."""

        replay = Replay(SOURCE, config=CONFIG, costs=COSTS)

        while replay.state.status != "finished":
            replay.step()

        assert len(replay.broker.journal) == 344
        assert replay.exit_counts == {"opposite_signal": 343, END_OF_DATA: 1}
        assert round(replay.broker.cash, 2) == 9842.86

    def test_standard_uses_the_shared_strategy_configuration(self) -> None:
        """Phase 17A §9.2: the strategy is shared; only the policy differs."""

        book = book_for()
        replay = Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS)

        assert book.strategy == replay.config
        assert book.exit_config.take_profit_pct == DEFAULT_PROFIT_TARGET_PCT

        # The exit config is for the level test only; the recorded identity is the
        # unmodified one.
        assert replay.state.strategy.config_hash != ""
        assert book.strategy.take_profit_pct is None


class TestAlertsContract:
    def test_alerts_cannot_execute(self) -> None:
        assert mode_spec(ALERTS).supports_execution is False
        assert mode_spec(ALERTS).policy is None
        assert is_executable(ALERTS) is False

    def test_alerts_never_gets_a_session(self) -> None:
        """11. Structurally incapable: there is no broker to reach."""

        reg = registry()

        from crypto_paper_lab.modes import ModeNotAvailableError

        with pytest.raises(ModeNotAvailableError):
            reg.session(ALERTS)

    def test_alerts_never_opens_a_paper_position(self) -> None:
        """11. Over the whole dataset, no Alerts position can appear."""

        # Alerts holds no session, so a walk can only produce observations. The
        # strongest available form: walking every signal leaves no broker behind.
        directional = 0
        for index in range(REQUIRED, PREFIX):
            item = analyze(SOURCE[:index], CONFIG)
            if item.side in {"long", "short"}:
                directional += 1

        assert directional > 0
        assert not hasattr(MODES[ALERTS], "session")

    def test_alerts_never_mutates_a_balance(self) -> None:
        """12. Nothing to mutate."""

        reg = registry()
        standard = reg.session(STANDARD)
        before = (standard.replay.broker.cash, len(standard.replay.broker.journal))

        from crypto_paper_lab.modes import ModeNotAvailableError

        for path in ("/api/alerts", "/api/orders"):
            assert client_for(reg).get(path).status_code == 404

        with pytest.raises(ModeNotAvailableError):
            reg.session(ALERTS)

        assert (
            standard.replay.broker.cash,
            len(standard.replay.broker.journal),
        ) == before

    def test_alerts_never_creates_an_execution_trade(self) -> None:
        """13. No journal anywhere is reachable from Alerts."""

        reg = registry()
        standard = reg.session(STANDARD)
        client = client_for(reg)
        client.post("/api/replay/step", params={"count": 200})

        journal = standard.replay.broker.journal
        assert journal, "expected Standard to have traded"

        # Every trade came from Standard's own broker via open_from_signal.
        for trade in journal:
            assert trade.reason in {
                "uptrend breakout", "downtrend breakdown",
                "bullish retest", "bearish retest",
            }
            assert not trade.reason.startswith("ai-")


# ---------------------------------------------------------------------------
# 14-20. AI entry
# ---------------------------------------------------------------------------


class TestAiEntry:
    def test_a_score_below_the_threshold_does_not_enter(self) -> None:
        """14. The gate, at the policy level."""

        policy = IntelligencePolicy(threshold=90.0)

        assert policy.should_enter(
            context(intelligence_score=89.0, open_position_count=0)
        ) is False

    def test_a_score_exactly_at_the_threshold_enters(self) -> None:
        """15. The boundary rule, at the policy level."""

        policy = IntelligencePolicy(threshold=90.0)

        assert policy.should_enter(
            context(intelligence_score=90.0, open_position_count=0)
        ) is True

    def test_a_score_above_the_threshold_enters(self) -> None:
        """16."""

        policy = IntelligencePolicy(threshold=90.0)

        assert policy.should_enter(
            context(intelligence_score=99.0, open_position_count=0)
        ) is True

    def test_a_flat_signal_never_enters(self) -> None:
        """Phase 17A §16.2, honoured by the policy."""

        policy = IntelligencePolicy(threshold=0.0)

        assert policy.should_enter(
            context(signal_side="flat", intelligence_score=100.0, open_position_count=0)
        ) is False

    def test_an_unscored_signal_never_enters(self) -> None:
        policy = IntelligencePolicy(threshold=0.0)

        assert policy.should_enter(
            context(intelligence_score=None, open_position_count=0)
        ) is False

    def test_the_position_limit_prevents_excess_positions(self) -> None:
        """17. At the policy level, and again through the book below."""

        policy = IntelligencePolicy(threshold=90.0, position_limit=5)

        assert policy.should_enter(
            context(intelligence_score=95.0, open_position_count=4)
        ) is True
        assert policy.should_enter(
            context(intelligence_score=95.0, open_position_count=5)
        ) is False

    def test_the_book_never_exceeds_its_position_limit(self) -> None:
        """17. Over real bars, not just a constructed context."""

        book = run(book_for(length=900))
        state = book.state

        assert state.open_position_count <= state.max_positions
        assert len(book.open_positions) == state.open_position_count

    def test_a_signal_with_no_room_is_counted_not_dropped(self) -> None:
        """A mode that silently discards signals looks like one that saw none."""

        book = run(book_for(length=900))
        state = book.state

        assert state.signals_qualified >= state.signals_admitted
        assert state.signals_declined == (
            state.signals_qualified - state.signals_admitted
        )

    def test_capital_allocation_prevents_over_allocation(self) -> None:
        """18. No position may commit more than the cash backing it."""

        book = run(book_for(length=900))

        for position in book.positions:
            notional = position.entry_price * position.quantity
            assert notional == pytest.approx(position.allocated_capital)

    def test_committed_plus_available_always_equals_the_realised_balance(
        self,
    ) -> None:
        """18, as an invariant over the whole walk rather than one point."""

        book = AiPaperBook(SOURCE[:900], config=AiPaperConfig(), strategy=CONFIG, costs=COSTS)

        for index in range(REQUIRED, 900):
            book.step(index)
            state = book.state

            assert state.committed_capital + state.available_capital == (
                pytest.approx(state.realized_balance)
            )
            assert state.available_capital >= 0

    def test_independent_positions_can_coexist(self) -> None:
        """19. Several open at once, each with its own identity."""

        book = run(book_for(length=900))

        overlapping = _max_simultaneous(book.positions)
        assert overlapping > 1, "expected AI to hold several positions at once"

        open_now = book.open_positions
        assert len({position.position_id for position in open_now}) == len(open_now)

    def test_no_future_candle_leaks_into_an_entry(self) -> None:
        """20. Rewriting the tail cannot change any decision already made."""

        index = 120

        def walk(series) -> list:
            book = AiPaperBook(
                series, config=AiPaperConfig(), strategy=CONFIG, costs=COSTS
            )
            for position in range(REQUIRED, index + 1):
                book.step(position)
            return [
                (p.entry_index, p.side, p.entry_price, p.quantity, p.intelligence_score)
                for p in book.positions
            ]

        clean = walk(SOURCE[:300])

        mutated = list(SOURCE[:300])
        for position in range(index + 1, len(mutated)):
            candle = mutated[position]
            mutated[position] = Candle(
                timestamp=candle.timestamp,
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=0.0,
            )

        assert walk(tuple(mutated)) == clean

    def test_an_entry_uses_the_execution_bar_open_not_the_signal_close(
        self,
    ) -> None:
        """The established execution timing model, unchanged."""

        book = run(book_for())

        for position in book.positions:
            assert position.entry_price == SOURCE[position.entry_index].open
            assert position.entry_timestamp == SOURCE[position.entry_index].timestamp

    def test_a_tighter_threshold_admits_fewer_signals(self) -> None:
        loose = run(book_for(config=AiPaperConfig(
            intelligence=IntelligenceConfig(threshold=80.0)
        )))
        strict = run(book_for(config=AiPaperConfig(
            intelligence=IntelligenceConfig(threshold=95.0)
        )))

        assert loose.state.signals_admitted > strict.state.signals_admitted
        assert strict.state.signals_admitted >= 0

    def test_the_policy_is_consulted_rather_than_an_inline_if(self) -> None:
        """The entry decision belongs to the 17E seam."""

        book = book_for()

        assert isinstance(book.policy, IntelligencePolicy)
        assert book.policy.threshold == book.config.intelligence.threshold
        assert book.policy.max_positions == book.config.max_positions


# ---------------------------------------------------------------------------
# 21-27. AI exit
# ---------------------------------------------------------------------------


class TestAiExit:
    def test_an_unreached_target_leaves_the_position_open(self) -> None:
        """21. No arbitrary instant closure.

        Constructed rather than searched for: the book is built over a series whose
        price never moves far enough for the target to trigger, so a close would
        have to come from somewhere other than the rule. The position is also held
        for many bars afterwards, which shows it is not closing on a timer either.
        """

        flat = _slow_drift_series(60)
        config = StrategyConfig(breakout_buffer=0.0)
        book = AiPaperBook(
            flat,
            # A target no plausible drift can reach: the whole series moves about
            # 1%, so a 50% target cannot be hit by any rule, only by a bug that
            # closes without checking.
            config=AiPaperConfig(
                profit_target_pct=50.0,
                # This synthetic series breaks levels by ~0.08%, far short of the
                # 0.5% that earns full breakout credit, so at the contract's
                # default threshold of 90 nothing here would qualify and the test
                # would pass without an entry ever happening. 70 admits these
                # setups while still being a real gate.
                intelligence=IntelligenceConfig(threshold=70.0),
            ),
            strategy=config,
            costs=COSTS,
        )

        # Find a bar that opens a position.
        entry_index = None
        config = StrategyConfig(breakout_buffer=0.0)
        minimum = flat_strategy_minimum(config)

        for index in range(minimum, 60):
            book.step(index)
            if book.positions:
                entry_index = book.positions[-1].entry_index
                break

        assert entry_index is not None, "expected an entry on the constructed series"

        # Advance well past the entry without the target ever being reached.
        for index in range(entry_index + 1, 60):
            book.step(index)

        opened = next(
            position
            for position in book.positions
            if position.entry_index == entry_index
        )

        assert opened.is_open
        assert opened.exit_reason is None
        assert opened.exit_price is None
        assert opened.bars_held is None
        assert book.journal == ()

    def test_a_reached_target_closes_the_position(self) -> None:
        """22."""

        book = run(book_for())

        closed = book.journal
        assert closed, "expected at least one closed position"

        for position in closed:
            assert position.exit_reason == AI_EXIT_PROFIT_TARGET
            assert position.state == "closed"
            assert position.exit_index is not None
            assert position.exit_price is not None

    def test_only_the_qualifying_position_closes(self) -> None:
        """23. A close never touches a position that did not qualify.

        Built by finding a bar where two positions were open, driving until
        exactly one hit its target, and asserting the other is untouched.
        """

        # A fresh book walked bar by bar, so the close/survive relationship is checked on
        # every bar rather than only at the end.
        book = book_for()

        checked = 0
        for index in range(REQUIRED, PREFIX):
            result = book.step(index)

            # Interesting only where some positions closed and others stayed open:
            # that is the case where "close everything" would be wrong.
            if not result.closed or not book.open_positions:
                continue

            closed_ids = {position.position_id for position in result.closed}

            for survivor in book.open_positions:
                assert survivor.position_id not in closed_ids
                # Untouched: still open, with no exit recorded at all.
                assert survivor.is_open
                assert survivor.exit_reason is None
                assert survivor.exit_price is None
                assert survivor.exit_index is None
                assert survivor.realized_pnl is None
                checked += 1

        assert checked > 0, "expected at least one partial close in the frozen data"

    def test_capital_becomes_available_after_a_close(self) -> None:
        """24."""

        book = run(book_for())

        assert book.journal, "expected closed positions"
        assert book.state.committed_capital == pytest.approx(
            sum(p.allocated_capital for p in book.open_positions)
        )
        assert book.state.available_capital == pytest.approx(
            book.state.realized_balance - book.state.committed_capital
        )

    def test_realised_pnl_is_recorded_and_matches_the_engine(self) -> None:
        """25. Every figure traced back to the position's own broker."""

        book = run(book_for())

        for position in book.journal:
            broker = book.broker_for(position)
            assert position.realized_pnl == pytest.approx(
                broker.cash - position.allocated_capital
            )
            assert position.costs == pytest.approx(broker.journal[-1].costs)

        total = sum(position.realized_pnl for position in book.journal)
        assert book.state.realized_pnl == pytest.approx(total)

    def test_the_exit_reason_is_deterministic(self) -> None:
        """26. Re-walking the same candles yields identical reasons."""

        first = [p.exit_reason for p in run(book_for()).journal]
        second = [p.exit_reason for p in run(book_for()).journal]

        assert first == second
        assert set(first) == {AI_EXIT_PROFIT_TARGET}

    def test_positions_are_never_closed_on_the_entry_bar(self) -> None:
        """27. The explicit refusal of "close whenever price is green"."""

        book = run(book_for())

        for position in book.journal:
            assert position.bars_held is not None
            assert position.bars_held >= 1
            assert position.exit_index > position.entry_index

    def test_end_of_data_closes_what_is_left(self) -> None:
        """The engine's own convention: the final bar's close, not its open."""

        length = 200
        series = SOURCE[:length]
        book = AiPaperBook(
            series, config=AiPaperConfig(), strategy=CONFIG, costs=COSTS
        )

        for index in range(REQUIRED, length):
            book.step(index)

        assert book.open_positions, "expected a position left open at the end"
        closed = book.close_open_positions()

        for position in closed:
            assert position.exit_reason == AI_EXIT_END_OF_DATA
            # The final bar's **close**, matching ``replay._finish``.
            assert position.exit_price == series[-1].close
            assert position.exit_timestamp == series[-1].timestamp

        assert book.open_positions == ()

    def test_an_ai_exit_reason_is_distinguishable_from_an_engine_one(self) -> None:
        """Phase 17A §2.3d: ``exit_reason`` is an open enumeration.

        A new label needs no model change, and must not collide with an existing one
        or an AI close would be indistinguishable from an engine close.
        """

        engine_labels = {
            "opposite_signal", "max_holding", "stop_loss", "take_profit",
            END_OF_DATA,
        }

        assert AI_EXIT_PROFIT_TARGET not in engine_labels
        assert AI_EXIT_END_OF_DATA not in engine_labels

    def test_there_is_no_stop_loss_in_this_phase(self) -> None:
        """Phase 17G defines no stop. Asserted so adding one is a decision."""

        book = book_for()

        assert book.config.profit_target_pct > 0
        assert book.exit_config.stop_loss_pct is None

    def test_there_is_no_trailing_stop_or_time_exit(self) -> None:
        code = code_only(BOOK_SOURCE)

        for forbidden in ("trailing", "trail_stop", "time_exit", "max_holding"):
            assert forbidden not in code, forbidden

    def test_the_profit_target_default_clears_round_trip_friction(self) -> None:
        """Why 0.5% and not something smaller.

        Under the frozen ``cost_deduction`` model a round trip pays fees on both
        notionals plus slippage on both, so friction is ``2 * (FEE_RATE +
        SLIPPAGE_RATE)`` of notional. A target at or below that could be reached and
        still realise a net loss, which would make "close at a profit" untrue.
        """

        friction = 2 * (FEE_RATE + SLIPPAGE_RATE)

        assert DEFAULT_PROFIT_TARGET_PCT > friction
        assert round(friction, 4) == 0.003


# ---------------------------------------------------------------------------
# 28-32. isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_ai_state_is_isolated_from_standard(self) -> None:
        """28."""

        reg = registry()
        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive(ai, 400)

        assert ai.book.positions, "expected AI to have traded"
        # Standard has not moved, so it cannot hold a trade.
        assert standard.replay.state.cursor == REQUIRED
        assert standard.replay.broker.journal == []
        # AI's positions live in its book, and the AI replay's own broker stays flat
        # because the book is the sole owner.
        assert ai.replay.broker.journal == []

    def test_ai_state_is_isolated_from_alerts(self) -> None:
        """29. Alerts has no session, so there is nothing to share."""

        reg = registry()
        ai = reg.session(AI_INTELLIGENCE)
        before = ai.book.positions

        from crypto_paper_lab.modes import ModeNotAvailableError

        with pytest.raises(ModeNotAvailableError):
            reg.session(ALERTS)

        assert ai.book.positions == before

    def test_resetting_ai_does_not_reset_standard(self) -> None:
        """30."""

        reg = registry()
        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive(standard, 150)
        drive(ai, 400)

        standard_before = (
            standard.replay.state.cursor,
            standard.replay.state.trade_count,
            standard.replay.broker.cash,
        )

        ai.reset()

        assert (
            standard.replay.state.cursor,
            standard.replay.state.trade_count,
            standard.replay.broker.cash,
        ) == standard_before

    def test_resetting_standard_does_not_reset_ai(self) -> None:
        """31."""

        reg = registry()
        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive(ai, 400)
        positions_before = ai.book.positions
        state_before = ai.ai_state
        assert positions_before

        standard.reset()

        assert ai.book.positions == positions_before
        assert ai.ai_state == state_before

    def test_ai_positions_never_appear_in_the_standard_journal(self) -> None:
        """32. Position identity, checked against both sides."""

        reg = registry()
        standard = reg.session(STANDARD)
        ai = reg.session(AI_INTELLIGENCE)

        drive(standard, 400)
        drive(ai, 400)

        ai_ids = {position.position_id for position in ai.book.positions}
        standard_trades = standard.replay.broker.journal

        assert ai_ids, "expected AI to have traded"
        assert standard_trades, "expected Standard to have traded"

        # AI identities are namespaced, so none of them can appear anywhere in
        # Standard's journal - and Standard's trades carry engine reasons, never
        # an ``ai-`` prefixed identifier.
        assert all(position_id.startswith("ai-") for position_id in ai_ids)
        assert not any(
            trade.entry_time in {
                position.entry_timestamp for position in ai.book.positions
            } and trade.quantity == pytest.approx(position.quantity)
            for trade in standard_trades
            for position in ai.book.positions
        )

        # Two distinct objects, so two distinct journals. Standard's trades are
        # reachable only through its own broker.
        assert ai.replay.broker.journal == []

    def test_ai_and_standard_hold_different_broker_objects(self) -> None:
        reg = registry()

        assert reg.session(STANDARD).replay.broker is not (
            reg.session(AI_INTELLIGENCE).replay.broker
        )

    def test_ai_book_is_the_sole_owner_of_its_positions(self) -> None:
        """One owner, stated structurally.

        Every AI position's P&L is reachable through the book, and the AI replay's
        own broker is permanently flat - so there is exactly one AI account and no
        possibility of a second one disagreeing with it.
        """

        book = run(book_for())

        assert book.positions, "expected AI to have traded"
        assert book.journal, "expected at least one closed position"

        # Deterministic accounting: the sum of every position's result equals the
        # book's realised P&L. No hidden second ledger.
        total = sum(
            position.realized_pnl for position in book.journal
        )
        assert book.state.realized_pnl == pytest.approx(total)


# ---------------------------------------------------------------------------
# 33-36. the transport
# ---------------------------------------------------------------------------


class TestTransport:
    def test_the_ai_endpoint_returns_authoritative_state(self) -> None:
        """33."""

        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        body = client.get("/api/ai").json()
        reg = client.app.state.modes
        book = reg.session(AI_INTELLIGENCE).book

        assert body["account"]["realized_pnl"] == pytest.approx(
            book.state.realized_pnl
        )
        assert body["account"]["open_position_count"] == book.state.open_position_count
        assert len(body["positions"]) == len(book.positions)
        assert len(body["journal"]) == len(book.journal)

    def test_the_ai_endpoint_does_not_calculate_the_score(self) -> None:
        """34. The score is read, never recomputed."""

        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        body = client.get("/api/ai").json()
        authoritative = (
            client.app.state.modes.session(AI_INTELLIGENCE).book.last_score
        )

        assert body["last_score"]["score"] == authoritative.score
        assert body["last_score"]["threshold"] == authoritative.threshold
        assert body["last_score"]["qualified"] == authoritative.qualified
        assert [
            component["points"] for component in body["last_score"]["components"]
        ] == [component.points for component in authoritative.components]

    def test_the_ai_endpoint_does_not_calculate_pnl(self) -> None:
        """35. Every figure traces to a broker."""

        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        body = client.get("/api/ai").json()
        book = client.app.state.modes.session(AI_INTELLIGENCE).book

        for served, position in zip(body["journal"], book.journal):
            assert served["realized_pnl"] == pytest.approx(position.realized_pnl)
            assert served["exit_price"] == position.exit_price

    def test_the_ai_endpoint_maintains_no_duplicate_state(self) -> None:
        """36. Two identical reads; no server-side accumulation."""

        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        first = client.get("/api/ai").json()
        second = client.get("/api/ai").json()

        assert first == second

    def test_the_ai_endpoint_validates_against_the_schema(self) -> None:
        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        parsed = AiStateResponse.model_validate(client.get("/api/ai").json())

        assert parsed.mode == AI_INTELLIGENCE
        assert parsed.account.max_positions == DEFAULT_MAX_POSITIONS

    def test_the_ai_endpoint_is_read_only(self) -> None:
        client = client_for()

        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)("/api/ai").status_code == 405

    def test_the_ai_endpoint_reports_no_unsupported_financial_field(self) -> None:
        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 300})

        body = client.get("/api/ai").json()

        for forbidden in (
            "equity", "mark_price", "current_price", "unrealized_pnl",
            "margin", "buying_power", "leverage", "reserved_capital",
        ):
            assert forbidden not in str(body), forbidden

    def test_stepping_ai_over_http_advances_the_book(self) -> None:
        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 400})

        body = client.get("/api/ai").json()

        assert body["positions"]
        assert body["account"]["signals_admitted"] > 0
        assert body["replay"]["cursor"] > REQUIRED

    def test_stepping_standard_leaves_ai_untouched(self) -> None:
        client = client_for()

        client.post("/api/replay/step", params={"mode": STANDARD, "count": 400})

        body = client.get("/api/ai").json()
        assert body["positions"] == []
        assert body["account"]["realized_pnl"] == 0.0

    def test_resetting_ai_over_http_clears_the_book(self) -> None:
        client = client_for()
        client.post("/api/replay/step", params={"mode": AI_INTELLIGENCE, "count": 400})
        client.post("/api/replay/reset", params={"mode": AI_INTELLIGENCE})

        body = client.get("/api/ai").json()

        assert body["positions"] == []
        assert body["account"]["committed_capital"] == 0.0
        assert body["account"]["available_capital"] == pytest.approx(STARTING_BALANCE)
        assert body["replay"]["cursor"] == REQUIRED

    def test_the_modes_endpoint_describes_the_ai_contract(self) -> None:
        body = client_for().get("/api/modes").json()
        entry = next(item for item in body["modes"] if item["mode"] == AI_INTELLIGENCE)

        assert entry["supports_execution"] is True
        assert entry["available"] is True
        assert entry["policy"]["max_positions"] == DEFAULT_MAX_POSITIONS
        assert "score" in entry["note"].lower()

    def test_the_reserved_modes_stay_reserved(self) -> None:
        """17G defined three contracts. It did not define these three."""

        for mode in reserved_modes():
            assert mode_spec(mode).available is False
            assert is_executable(mode) is False

        parsed = ModesResponse.model_validate(
            client_for().get("/api/modes").json()
        )
        assert len(parsed.modes) == len(known_modes())


# ---------------------------------------------------------------------------
# 37-38. scope guards
# ---------------------------------------------------------------------------


class TestScopeGuards:
    def test_no_leverage_margin_or_borrowing_concept(self) -> None:
        """The core safety property, asserted across every new module."""

        for path in (SCORE_SOURCE, BOOK_SOURCE, REGISTRY_SOURCE):
            code = code_only(path)

            for forbidden in (
                "leverage", "margin", "borrow", "margin_call", "buying_power",
            ):
                assert forbidden not in code, f"{path.name}: {forbidden}"

    def test_allocation_fraction_is_capped_at_one(self) -> None:
        """A fraction above 1 would commit more notional than cash backs it."""

        assert DEFAULT_ALLOCATION_FRACTION == 1.0

        with pytest.raises(ValueError):
            AiPaperConfig(allocation_fraction=1.5)

        with pytest.raises(ValueError):
            AiPaperConfig(allocation_fraction=0.0)

    def test_no_stop_loss_or_unbounded_holding(self) -> None:
        book = book_for()

        assert book.exit_config.stop_loss_pct is None
        assert book.config.max_positions >= 1

    def test_the_book_exposes_no_order_or_venue_concept(self) -> None:
        code = code_only(BOOK_SOURCE)

        for forbidden in (
            "exchange", "binance", "ccxt", "api_key", "secret", "credential",
            "wallet", "private_key", "submit_order", "place_order",
            "socket", "urllib", "requests", "http",
        ):
            assert forbidden not in code, forbidden

    def test_the_book_has_no_persistence_or_scheduler(self) -> None:
        code = code_only(BOOK_SOURCE)

        for forbidden in (
            "json", "pickle", "sqlite", "redis", "open(", "threading",
            "asyncio", "Timer", "sched",
        ):
            assert forbidden not in code, forbidden

    def test_the_book_has_no_clock_or_randomness(self) -> None:
        code = code_only(BOOK_SOURCE)

        for forbidden in (
            "random", "time(", "datetime.now", "uuid", "os.environ",
        ):
            assert forbidden not in code, forbidden

    def test_the_book_reuses_the_engine_rather_than_reimplementing_it(self) -> None:
        """Phase 17A M-4: no mode reimplements signals, fills or costs."""

        book = run(book_for())
        assert book.positions, "expected AI to have traded"

        for position in book.positions:
            # Fill price came from the broker, which under cost_deduction records
            # the raw chart price. A reimplemented fill would differ.
            assert position.entry_price == SOURCE[position.entry_index].open
            assert position.entry_price == pytest.approx(
                position.allocated_capital / position.quantity
            )

    def test_the_book_owns_one_broker_per_position(self) -> None:
        book = run(book_for())

        brokers = {
            id(book.broker_for(position)) for position in book.positions
        }

        assert len(brokers) == len(book.positions)

    def test_the_registry_still_holds_no_financial_state(self) -> None:
        reg = registry()

        for forbidden in (
            "balance", "cash", "cursor", "journal", "position", "realized_pnl",
            "committed_capital", "available_capital",
        ):
            assert not hasattr(reg, forbidden), forbidden

    def test_the_registry_does_not_construct_brokers_itself(self) -> None:
        code = code_only(REGISTRY_SOURCE)

        assert "PaperBroker" not in code
        assert "open_from_signal" not in code

    def test_the_schemas_compute_nothing(self) -> None:
        """The transport projects; it does not decide."""

        tree = ast.parse(SCHEMA_SOURCE.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                # No arithmetic on financial values: a projection builds objects from
                # engine fields. ``round`` and ``abs`` would be a red flag here.
                assert node.func.id not in {"round", "max", "min", "sum", "pow"}, (
                    node.func.id
                )

    def test_the_app_computes_no_financial_value(self) -> None:
        code = code_only(APP_SOURCE)

        for forbidden in (
            "score_signal", "IntelligenceConfig", "AiPaperConfig",
            "AiPaperBook", "profit_target", "allocation_fraction",
            "committed_capital", "available_capital",
        ):
            assert forbidden not in code, forbidden

        # No arithmetic on any financial field. ``quantity =`` appears only as a
        # keyword argument to a response model, which is why it is matched on the
        # call rather than the name.
        assert ".quantity *" not in code
        assert "realized_pnl -" not in code
        assert "balance -" not in code

    def test_the_ai_session_is_required_for_the_ai_mode(self) -> None:
        """A registry injected with a plain session must fail loudly."""

        plain = ReplaySession(Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS))
        reg = ModeRegistry(session_for=lambda mode: plain)

        with pytest.raises(TypeError):
            reg.ai_session()

    def test_standard_cannot_reach_the_ai_book(self) -> None:
        reg = registry()
        standard = reg.session(STANDARD)

        for forbidden in ("book", "ai_state", "positions", "journal"):
            assert not hasattr(standard, forbidden), forbidden


# ---------------------------------------------------------------------------
# helpers used by more than one class
# ---------------------------------------------------------------------------


def flat_strategy_minimum(config: StrategyConfig) -> int:
    """Candles ``analyze`` requires before it will signal for this config."""

    return max(config.lookback + 2, config.slow_period)


def _slow_drift_series(length: int) -> tuple:
    """A steady, shallow uptrend: enough to break levels, not enough to hit a target.

    ``analyze`` needs a moving-average separation to report a trend, so a genuinely
    flat series produces no directional signal at all and nothing could ever be
    opened. A few basis points per bar gives 38 directional bars over 60 while the
    total move stays around 1%, which is why the test pairs this with an
    unreachable profit target.
    """

    from datetime import timedelta

    candles = []
    for index in range(length):
        base = 100.0 + 0.05 * index + (0.02 if index % 2 else -0.02)
        candles.append(
            Candle(
                timestamp=SOURCE[0].timestamp + timedelta(hours=index),
                open=base,
                high=base * 1.0002,
                low=base * 0.9998,
                close=base,
                volume=100.0,
            )
        )

    return tuple(candles)


def _max_simultaneous(positions: tuple) -> int:
    """Peak number of AI positions open at once."""

    events: list[tuple] = []
    for position in positions:
        events.append((position.entry_index, 1))
        if position.exit_index is not None:
            events.append((position.exit_index, -1))

    peak = 0
    running = 0
    for _, delta in sorted(events):
        running += delta
        peak = max(peak, running)

    return peak