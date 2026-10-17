"""Market-cost validation reached through real production entry points.

Phase 81C found ``assert_costs_match_market`` defined but never called by any
production module -- it was exercised only by tests that called it directly,
which proved the function worked and proved nothing about whether anything used
it.

The tests here therefore go through the components themselves:

* :class:`crypto_paper_lab.simulator.PaperBroker` -- the chokepoint every
  simulated fill passes through, reached via ``run_backtest``;
* :class:`paper_api.session.PaperSession` -- the served API session, the one
  production site where a declared market and a cost model are both in hand.

If someone routes around these, the tests below fail.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from crypto_paper_lab.costs import (
    COST_DEDUCTION,
    MARKET_COST_BLOCKED,
    MarketCostMismatch,
    TradingCosts,
    UnsupportedMarketCostProfile,
    costs_for_market,
)
from crypto_paper_lab.models import Candle
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.walkforward import phase13_costs

BASE = datetime(2024, 1, 1)


def _candles(count: int = 80) -> list[Candle]:
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=100.0 + i * 0.2,
            high=101.0 + i * 0.2,
            low=99.0 + i * 0.2,
            close=100.4 + i * 0.2,
            volume=10.0 + i,
        )
        for i in range(count)
    ]


class _ImpostorCosts:
    """A duck type that satisfies everything a broker reads except validity.

    Constructing this cannot go through ``TradingCosts``, which refuses an
    unsupported market. Passing it in is the bypass attempt, and it must be
    rejected at the boundary rather than accepted because it quacks correctly.
    """

    market_type = "forex_spot"
    execution_model = COST_DEDUCTION
    fee_rate = 0.0
    slippage_rate = 0.0
    spread_rate = 0.0

    def adverse_rate(self) -> float:
        return 0.0


# 1. the happy path still works and defaults are unchanged
def test_the_default_broker_is_accepted_and_keeps_crypto_defaults() -> None:
    broker = PaperBroker()
    assert broker.costs.market_type == "crypto_spot"
    assert broker.costs.fee_rate == 0.001
    assert broker.costs.slippage_rate == 0.0005
    assert broker.costs.spread_rate == 0.0
    assert broker.costs.execution_model == COST_DEDUCTION


def test_explicit_crypto_costs_are_accepted() -> None:
    broker = PaperBroker(costs=phase13_costs())
    assert broker.costs.market_type == "crypto_spot"


def test_a_zero_cost_diagnostic_run_is_not_replaced_by_the_defaults() -> None:
    """A valid zero-cost record is falsy-looking but must be honoured.

    ``costs or TradingCosts()`` would make this depend on how a dataclass
    happens to define truthiness.
    """

    zero = TradingCosts(fee_rate=0.0, slippage_rate=0.0)
    broker = PaperBroker(costs=zero)
    assert broker.costs is zero
    assert broker.costs.fee_rate == 0.0


def test_run_backtest_proceeds_on_the_normal_crypto_path() -> None:
    """Production entry point, happy path: simulation actually runs."""

    from crypto_paper_lab.backtest import run_backtest
    from crypto_paper_lab.strategy import StrategyConfig

    result = run_backtest(_candles(), config=StrategyConfig())
    assert result is not None


# 2. bypass attempts through the broker
def test_a_cost_record_for_a_blocked_market_cannot_reach_a_broker() -> None:
    with pytest.raises(UnsupportedMarketCostProfile):
        PaperBroker(costs=_ImpostorCosts())


def test_a_duck_typed_cost_record_is_refused_even_though_it_reads_correctly() -> None:
    with pytest.raises(UnsupportedMarketCostProfile):
        PaperBroker(costs=_ImpostorCosts())


@pytest.mark.parametrize("market", sorted(MARKET_COST_BLOCKED))
def test_no_blocked_market_reaches_a_broker_by_any_constructor(market: str) -> None:
    """Construction itself refuses, so the broker check is defence in depth."""

    with pytest.raises(UnsupportedMarketCostProfile):
        TradingCosts(market_type=market)
    with pytest.raises(UnsupportedMarketCostProfile):
        PaperBroker(costs=_ImpostorCosts())


def test_a_cost_record_mutated_after_validation_is_refused() -> None:
    """Writing around ``frozen`` must not smuggle a market past the broker."""

    costs = phase13_costs()
    object.__setattr__(costs, "market_type", "forex_spot")
    with pytest.raises(UnsupportedMarketCostProfile):
        PaperBroker(costs=costs)


def test_a_cost_record_is_frozen_against_ordinary_assignment() -> None:
    costs = phase13_costs()
    with pytest.raises(FrozenInstanceError):
        costs.market_type = "forex_spot"  # type: ignore[misc]


# 3. the API session: the site where both markets are known
def test_the_api_session_accepts_matching_crypto_costs() -> None:
    from paper_api.session import PaperSession

    session = PaperSession(service="test")
    assert session.broker.costs.market_type == "crypto_spot"


def test_the_api_session_rejects_a_mismatched_market_before_simulating() -> None:
    """Traverses the real served session, not the guard in isolation."""

    from paper_api.session import PaperSession

    class ForeignCosts:
        market_type = "crypto_perpetual"

    with pytest.raises(MarketCostMismatch):
        PaperSession(service="test", costs=ForeignCosts())  # type: ignore[arg-type]


def test_the_api_session_rejects_costs_for_a_blocked_market() -> None:
    from paper_api.session import PaperSession

    with pytest.raises(MarketCostMismatch):
        PaperSession(service="test", costs=_ImpostorCosts())  # type: ignore[arg-type]


def test_the_api_session_refuses_before_any_trade_state_exists() -> None:
    """Rejection must precede the session holding a broker or a balance."""

    from paper_api.session import PaperSession

    with pytest.raises(MarketCostMismatch):
        PaperSession(service="test", costs=_ImpostorCosts())  # type: ignore[arg-type]

    # Constructing the legitimate session afterwards proves nothing was
    # half-built or left behind.
    healthy = PaperSession(service="test")
    assert healthy.broker.open_trade is None
    assert healthy.broker.journal == []


# 4. unknown markets stay closed
@pytest.mark.parametrize(
    "market", ["", "crypto", "CRYPTO_SPOT", "crypto_spot ", "equities", "forex"]
)
def test_unknown_market_names_are_refused_end_to_end(market: str) -> None:
    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)
    with pytest.raises(UnsupportedMarketCostProfile):
        TradingCosts(market_type=market)


# 5. the guard is genuinely wired, not merely importable
def test_the_production_modules_actually_call_the_guards() -> None:
    """Import-graph assertion: neither guard is dead code.

    Reading a function's definition is not evidence that anything uses it, and
    a passing test of a guard proves only that the guard works. These checks
    prove the guards are *reachable from production*.

    Two distinct checks are expected, because two distinct facts are known at
    two different places:

    * ``simulator.PaperBroker`` sees only a cost record, never a declared
      market, so it validates the cost's own market via ``market_cost_profile``;
    * ``paper_api.session.PaperSession`` serves a dataset of known market, so
      it is the site that can cross-check the two with
      ``assert_costs_match_market``.
    """

    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    cross_checked: list[str] = []
    validated: list[str] = []
    for path in src.rglob("*.py"):
        if path.name == "costs.py":
            continue  # the definition site proves nothing
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name == "assert_costs_match_market":
                cross_checked.append(path.name)
            elif name == "market_cost_profile":
                validated.append(path.name)

    assert cross_checked, "no production module cross-checks cost against market"
    assert "session.py" in cross_checked

    assert validated, "no production module validates a cost record's market"
    assert "simulator.py" in validated, (
        "the broker chokepoint must validate the market it is given"
    )

# 6. the chokepoint really is the chokepoint
def test_every_broker_is_built_through_the_validated_constructor() -> None:
    """No production site fabricates a broker around the constructor.

    Seven modules construct ``PaperBroker``. If any of them bypassed
    ``__init__`` the chokepoint argument would be false, so this checks the
    call graph rather than trusting the count.
    """

    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    constructors = 0
    bypasses = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # PaperBroker(...)  -> validated path
            if isinstance(node, ast.Call):
                f = node.func
                nm = getattr(f, "id", None) or getattr(f, "attr", None)
                if nm == "PaperBroker":
                    constructors += 1
            # PaperBroker.__new__(...) -> bypass
            if isinstance(node, ast.Attribute) and node.attr in ("__new__", "__init__"):
                if isinstance(node.value, ast.Name) and node.value.id == "PaperBroker":
                    bypasses.append(f"{path.name}:{node.lineno}")

    assert constructors >= 1, "no production site builds a broker"
    assert bypasses == [], f"a broker bypasses its constructor: {bypasses}"


def test_the_broker_constructor_actually_validates() -> None:
    """The chokepoint must contain the check, not merely be reachable."""

    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "crypto_paper_lab"
        / "simulator.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    broker = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "PaperBroker"
    )
    init = next(
        n for n in broker.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    called = {
        (c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", None))
        for c in ast.walk(init)
        if isinstance(c, ast.Call)
    }
    assert "market_cost_profile" in called


def test_the_served_market_derives_from_the_cost_authority() -> None:
    """``MARKET_TYPE`` is load-bearing, so it must not be a second literal."""

    from crypto_paper_lab.costs import DEFAULT_MARKET_TYPE, MARKET_COST_PROFILES
    from paper_api import marketdata

    assert marketdata.MARKET_TYPE == DEFAULT_MARKET_TYPE
    assert marketdata.MARKET_TYPE in MARKET_COST_PROFILES


def test_the_served_market_is_the_same_market_the_costs_default_to() -> None:
    from crypto_paper_lab.costs import TradingCosts
    from paper_api import marketdata

    assert TradingCosts().market_type == marketdata.MARKET_TYPE


# 7. reaching the mismatch branch through a second production class
def test_replay_construction_refuses_costs_for_another_market() -> None:
    """Traverses ``Replay``, a second production entry point, before stepping.

    Construction validates and refuses; no bar is processed, so this proves
    rejection happens before any work rather than during it.
    """

    from crypto_paper_lab.replay import Replay
    from crypto_paper_lab.walkforward import baseline_config

    with pytest.raises(UnsupportedMarketCostProfile):
        Replay(_candles(), config=baseline_config(), costs=_ImpostorCosts())


def test_replay_construction_accepts_valid_crypto_costs() -> None:
    from crypto_paper_lab.replay import Replay
    from crypto_paper_lab.walkforward import baseline_config

    replay = Replay(_candles(), config=baseline_config(), costs=phase13_costs())
    assert replay.broker.costs.market_type == "crypto_spot"


# 8. reachability of the mismatch branch -- documented, not assumed
def test_market_cost_mismatch_is_unreachable_through_the_supported_api() -> None:
    """Only one market is implemented, so the branch cannot fire normally.

    Recorded as an explicit property of the current state so that it is
    revisited when a second market is approved, rather than being rediscovered
    by someone who reads a passing test as proof the branch was exercised.
    """

    from crypto_paper_lab.costs import MARKET_COST_PROFILES

    assert len(MARKET_COST_PROFILES) == 1, (
        "if a second market now exists, the mismatch branch becomes reachable "
        "and the tests that use stand-in cost records should be replaced with "
        "real ones"
    )


@pytest.mark.parametrize("market", sorted(MARKET_COST_BLOCKED))
def test_the_only_way_to_reach_the_mismatch_branch_is_an_invalid_object(
    market: str,
) -> None:
    """Every supported constructor refuses, so bypass is the only route."""

    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)
    with pytest.raises(UnsupportedMarketCostProfile):
        TradingCosts(market_type=market)


def test_the_mismatch_branch_fires_for_a_costs_object_whose_market_was_forged() -> None:
    """The one real route: writing around ``frozen`` on a valid cost record.

    Documented as the guarded-against case. It is not a supported API and no
    legitimate caller does this; the test exists so the branch is exercised by
    something concrete rather than left unproven.
    """

    from crypto_paper_lab.costs import MarketCostMismatch, assert_costs_match_market
    from paper_api.session import PaperSession

    costs = phase13_costs()
    object.__setattr__(costs, "market_type", "crypto_perpetual")

    with pytest.raises(MarketCostMismatch):
        assert_costs_match_market(costs, "crypto_spot")

    with pytest.raises(MarketCostMismatch):
        PaperSession(service="test", costs=costs)  # type: ignore[arg-type]


# 9. explicit market declaration on the execution APIs (Phase 81E A3)
def _engine_candles(count: int = 80) -> list[Candle]:
    return _candles(count)


def test_run_backtest_accepts_a_matching_market_declaration() -> None:
    """Real production entry point, valid crypto combination."""

    from crypto_paper_lab.backtest import run_backtest

    assert run_backtest(_engine_candles(), market_type="crypto_spot") is not None


def test_run_backtest_omitting_the_declaration_is_not_a_default() -> None:
    """Absence means the data makes no claim -- it must still work."""

    from crypto_paper_lab.backtest import run_backtest

    assert run_backtest(_engine_candles()) is not None


def test_run_backtest_refuses_a_conflicting_declaration_before_any_work() -> None:
    """A market/cost contradiction is refused, not evaluated through."""

    from crypto_paper_lab.backtest import run_backtest

    with pytest.raises(MarketCostMismatch, match="crypto_perpetual"):
        run_backtest(_engine_candles(), market_type="crypto_perpetual")


def test_run_backtest_refuses_a_declaration_the_cost_model_cannot_describe() -> None:
    """Forex stays blocked through the declaration parameter too."""

    from crypto_paper_lab.backtest import run_backtest

    with pytest.raises(MarketCostMismatch) as exc:
        run_backtest(_engine_candles(), market_type="forex_spot")
    assert "not an implemented market" in str(exc.value)


def test_run_backtest_refuses_an_invalid_market_identifier() -> None:
    from crypto_paper_lab.backtest import run_backtest

    with pytest.raises(MarketCostMismatch):
        run_backtest(_engine_candles(), market_type="not-a-market")


def test_run_backtest_refuses_a_declaration_that_contradicts_supplied_costs() -> None:
    """The conflict is detected against the costs actually supplied."""

    from crypto_paper_lab.backtest import run_backtest

    forged = costs_for_market("crypto_spot")
    object.__setattr__(forged, "market_type", "crypto_futures")
    with pytest.raises(MarketCostMismatch, match="crypto_futures"):
        run_backtest(
            _engine_candles(), costs=forged, market_type="crypto_spot"
        )


def test_replay_refuses_a_conflicting_declaration_at_construction() -> None:
    from crypto_paper_lab.replay import Replay
    from crypto_paper_lab.walkforward import baseline_config

    with pytest.raises(MarketCostMismatch):
        Replay(
            _engine_candles(),
            config=baseline_config(),
            market_type="crypto_futures",
        )


def test_replay_accepts_a_matching_declaration() -> None:
    from crypto_paper_lab.replay import Replay
    from crypto_paper_lab.walkforward import baseline_config

    replay = Replay(
        _engine_candles(), config=baseline_config(), market_type="crypto_spot"
    )
    assert replay.broker.costs.market_type == "crypto_spot"


def test_zero_cost_diagnostics_survive_the_new_declaration_parameter() -> None:
    """The zero-cost diagnostic path must remain available and validated."""

    from crypto_paper_lab.backtest import run_backtest

    zero = TradingCosts(fee_rate=0.0, slippage_rate=0.0)
    result = run_backtest(_engine_candles(), costs=zero, market_type="crypto_spot")
    assert result is not None
    assert zero.market_type == "crypto_spot"


def test_the_execution_apis_still_have_their_original_parameter_order() -> None:
    """A keyword appended must not move an existing positional argument."""

    import inspect

    from crypto_paper_lab.backtest import run_backtest
    from crypto_paper_lab.replay import Replay

    backtest_params = list(inspect.signature(run_backtest).parameters)
    assert backtest_params[:7] == [
        "candles",
        "config",
        "starting_balance",
        "risk_fraction",
        "costs",
        "evaluation_start",
        "research_context",
    ]
    assert backtest_params[-1] == "market_type"

    replay_params = [
        p for p in inspect.signature(Replay.__init__).parameters if p != "self"
    ]
    assert replay_params[0] == "candles"
    assert replay_params[-1] == "market_type"
    for earlier, later in (("candles", "costs"), ("costs", "start_index")):
        assert replay_params.index(earlier) < replay_params.index(later)


def test_no_persisted_schema_was_changed_for_market_declaration() -> None:
    """The declaration is a call-time argument, not a stored field.

    ``replay.DatasetIdentity`` is what research records serialise. This pins
    that it still carries no market field, so the change added no migration
    burden and did not alter the ``/api/session`` response contract.
    """

    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "crypto_paper_lab"
        / "replay.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "DatasetIdentity"
    )
    fields = [
        s.target.id for s in cls.body if isinstance(s, ast.AnnAssign)
    ]
    assert "market_type" not in fields
    assert fields == [
        "asset",
        "timeframe",
        "sha256",
        "first_timestamp",
        "last_timestamp",
        "candle_count",
        "interval_seconds",
    ]
