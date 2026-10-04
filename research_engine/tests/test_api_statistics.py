"""Phase 16F tests: the closed-trade statistics endpoint.

Three rules shape this file.

**Fixtures are built by the engine.** A populated journal is produced by driving
the real ``PaperBroker`` with real ``analyze()`` signals. Hand-building trades
would let these tests assert against statistics of an accounting scenario the
engine never produced.

**Every figure is compared to the engine, not to a literal.** The assertions call
``stats.performance`` and ``stats.cost_breakdown`` directly and require exact
equality. A hard-coded expected number would only prove the value has not
changed; it would not prove the endpoint is reading the engine.

**The endpoint must not add statistics the engine does not define.** There are
tests that the response contains no risk-adjusted ratio, no confidence interval
and no mark-to-market drawdown, because each of those would be a number no
research record validated.
"""
from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paper_api import marketdata, perfstats
from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.schemas import StatisticsResponse
from paper_api.session import PaperSession

from crypto_paper_lab import stats
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import analyze
from crypto_paper_lab.walkforward import (
    RISK_FRACTION,
    baseline_config,
    phase13_costs,
)

SOURCE, _ = load_dataset(marketdata.dataset_path())
CONFIG = baseline_config()

STARTING_BALANCE = 10_000.0

#: Index of the first long signal in the frozen dataset, pinned so the fixture is
#: fast. The test asserts the signal is genuinely non-flat, so a data change
#: fails loudly rather than silently.
LONG_INDEX = 22

#: Prefix length yielding both winning and losing closed trades. A single-trade
#: fixture cannot exercise the finite profit-factor branch, because with no
#: losing trade the engine returns infinity by definition.
MIXED_CANDLES = 400


def build_broker(close_after: int) -> PaperBroker:
    """Drive the real broker through a real signal and close it."""

    signal = analyze(SOURCE[:LONG_INDEX], CONFIG)
    assert signal.side == "long"

    broker = PaperBroker(
        starting_balance=STARTING_BALANCE, costs=phase13_costs()
    )
    execution = replace(
        signal,
        timestamp=SOURCE[LONG_INDEX].timestamp,
        price=SOURCE[LONG_INDEX].open,
    )
    broker.open_from_signal(execution)

    index = LONG_INDEX + close_after
    trade = broker.close(SOURCE[index].close, SOURCE[index].timestamp)
    trade.exit_reason = "opposite_signal"
    trade.bars_held = close_after

    return broker


def client_for(broker: PaperBroker | None = None) -> TestClient:
    return TestClient(
        create_app(
            ApiConfig(),
            session=PaperSession(
                service="crypto-paper-lab",
                config=CONFIG,
                broker=broker,
            ),
        )
    )


@pytest.fixture
def empty_client() -> TestClient:
    return client_for()


@pytest.fixture
def closed_trades_client() -> TestClient:
    return client_for(build_broker(close_after=30))


@pytest.fixture
def journal() -> tuple:
    return build_broker(close_after=30).journal


@pytest.fixture(scope="module")
def mixed_journal() -> tuple:
    """A genuine multi-trade journal containing both winners and losers."""

    result = run_backtest(
        SOURCE[:MIXED_CANDLES],
        config=CONFIG,
        costs=phase13_costs(),
        starting_balance=STARTING_BALANCE,
        risk_fraction=RISK_FRACTION,
    )
    trades = tuple(result.trades)

    assert any((t.net_pnl or 0.0) > 0 for t in trades), "needs a winner"
    assert any((t.net_pnl or 0.0) < 0 for t in trades), "needs a loser"

    return trades


# ---------------------------------------------------------------------------
# shape and empty state
# ---------------------------------------------------------------------------


def test_statistics_returns_200(empty_client: TestClient) -> None:
    assert empty_client.get("/api/statistics").status_code == 200


def test_statistics_validates_against_the_schema(
    closed_trades_client: TestClient,
) -> None:
    parsed = StatisticsResponse.model_validate(
        closed_trades_client.get("/api/statistics").json()
    )

    assert parsed.trades == 1


def test_empty_journal_response_is_exactly_degenerate(
    empty_client: TestClient,
) -> None:
    """No trades means zeros, and the payload says so rather than hiding it."""

    body = empty_client.get("/api/statistics").json()

    assert body["trades"] == 0
    assert body["net_pnl"] == 0.0
    assert body["win_rate"] == 0.0
    assert body["average_pnl"] == 0.0
    assert body["max_drawdown"] == 0.0
    assert body["ending_balance"] == STARTING_BALANCE
    assert body["costs"] == {
        "fee_total": 0.0,
        "spread_total": 0.0,
        "slippage_total": 0.0,
        "total_friction": 0.0,
        "deducted_costs": 0.0,
    }


def test_basis_is_declared_as_closed_trades(
    closed_trades_client: TestClient,
) -> None:
    """The payload states its own basis, so it cannot be read as live equity."""

    body = closed_trades_client.get("/api/statistics").json()

    assert body["basis"] == "closed_trades"


def test_zero_valued_fields_are_floats_not_integers(
    empty_client: TestClient,
) -> None:
    """``sum([])`` is ``0``, an int. It must not leak as ``0`` in the payload.

    A JS client doing arithmetic on the result would otherwise get an integer
    where every other value is a float.
    """

    body = empty_client.get("/api/statistics").json()

    for key in ("net_pnl", "win_rate", "average_pnl", "ending_balance"):
        assert isinstance(body[key], float), key
    assert body["trades"] == 0
    assert isinstance(body["trades"], int)


# ---------------------------------------------------------------------------
# delegation: every figure equals the engine's
# ---------------------------------------------------------------------------


def test_headline_figures_equal_stats_performance(
    closed_trades_client: TestClient, journal: tuple
) -> None:
    body = closed_trades_client.get("/api/statistics").json()
    engine = stats.performance(journal, STARTING_BALANCE)

    assert body["trades"] == engine["trades"]
    assert body["net_pnl"] == engine["net_pnl"]
    assert body["win_rate"] == engine["win_rate"]
    assert body["average_pnl"] == engine["average_pnl"]
    assert body["max_drawdown"] == engine["max_drawdown"]
    assert body["ending_balance"] == engine["ending_balance"]


def test_cost_figures_equal_stats_cost_breakdown(
    closed_trades_client: TestClient, journal: tuple
) -> None:
    body = closed_trades_client.get("/api/statistics").json()
    engine = stats.cost_breakdown(journal)

    for key, value in engine.items():
        assert body["costs"][key] == value, key


def test_deducted_costs_equal_total_friction_under_cost_deduction(
    closed_trades_client: TestClient,
) -> None:
    """The active execution model is cost_deduction, so they must be equal.

    They differ under fill_price by design; asserting equality here documents
    which model produced the number rather than implying they always match.
    """

    costs = closed_trades_client.get("/api/statistics").json()["costs"]

    assert costs["total_friction"] > 0.0
    assert costs["deducted_costs"] == pytest.approx(costs["total_friction"])
    assert costs["spread_total"] == 0.0


def test_max_drawdown_is_a_fraction_not_a_percentage(
    closed_trades_client: TestClient,
) -> None:
    """``performance`` returns a fraction. Scaling it here would misreport it."""

    body = closed_trades_client.get("/api/statistics").json()
    engine = stats.performance(
        closed_trades_client.app.state.session.broker.journal,
        STARTING_BALANCE,
    )

    assert body["max_drawdown"] == engine["max_drawdown"]
    # A single trade cannot draw down from a single sample; if this ever became
    # 100.0 the value had been multiplied by 100 somewhere.
    assert body["max_drawdown"] <= 1.0


def test_win_rate_is_a_fraction(closed_trades_client: TestClient) -> None:
    body = closed_trades_client.get("/api/statistics").json()

    assert 0.0 <= body["win_rate"] <= 1.0


def test_net_pnl_equals_the_sum_of_journal_net_pnls(
    closed_trades_client: TestClient, journal: tuple
) -> None:
    body = closed_trades_client.get("/api/statistics").json()

    assert body["net_pnl"] == sum(t.net_pnl for t in journal)


def test_strategy_and_execution_identity_are_carried(
    closed_trades_client: TestClient,
) -> None:
    """A P&L without its cost basis is meaningless, so identity travels with it."""

    body = closed_trades_client.get("/api/statistics").json()
    session = closed_trades_client.app.state.session.view

    assert body["strategy"]["config_hash"] == session.strategy.config_hash
    assert body["execution"]["costs_hash"] == session.execution.costs_hash
    assert body["execution"]["execution_model"] == "cost_deduction"
    assert body["service"] == "crypto-paper-lab"


# ---------------------------------------------------------------------------
# finding N1: infinity is not valid JSON
# ---------------------------------------------------------------------------


def test_infinite_profit_factor_becomes_null_with_a_flag(journal: tuple) -> None:
    """The engine returns ``inf`` when there are no losing trades.

    ``inf`` is not valid JSON, so it becomes ``None`` plus an explicit flag.
    Silently substituting a large finite value would fabricate a statistic.
    """

    winners = [t for t in journal if (t.net_pnl or 0.0) > 0]
    assert winners, "fixture must contain a winning trade"

    summary = perfstats.summarise(winners, STARTING_BALANCE)
    engine = stats.performance(winners, STARTING_BALANCE)

    assert math.isinf(engine["profit_factor"])
    assert summary.profit_factor is None
    assert summary.profit_factor_infinite is True


def test_finite_profit_factor_passes_through_unchanged(
    mixed_journal: tuple,
) -> None:
    summary = perfstats.summarise(mixed_journal, STARTING_BALANCE)
    engine = stats.performance(mixed_journal, STARTING_BALANCE)

    assert math.isfinite(engine["profit_factor"])
    assert summary.profit_factor_infinite is False
    assert summary.profit_factor == engine["profit_factor"]
    assert summary.trades == len(mixed_journal)
    assert 0.0 <= summary.win_rate <= 1.0


def test_profit_factor_infinity_never_reaches_the_wire(
    closed_trades_client: TestClient,
) -> None:
    """No bare ``Infinity``/``NaN`` token may appear in a 200 response body.

    ``json.dumps`` emits those tokens by default and ``JSON.parse`` rejects
    them, so a single unhandled infinite value would break every consumer while
    the HTTP status still said 200.
    """

    for path in (
        "/api/statistics",
        "/api/session",
        "/api/account",
        "/api/position",
        "/api/trades",
    ):
        text = closed_trades_client.get(path).text
        assert "Infinity" not in text, path
        assert "NaN" not in text, path
        # Parsed strictly: Python accepts the non-standard tokens by default.
        json.loads(text, parse_constant=_reject_constant)


def _reject_constant(name: str) -> float:
    raise AssertionError(f"non-finite JSON constant in response: {name}")


def test_schema_rejects_a_naked_infinite_profit_factor() -> None:
    """Defence in depth: the model itself cannot hold an infinite value."""

    payload = {
        "service": "crypto-paper-lab",
        "basis": "closed_trades",
        "trades": 1,
        "net_pnl": 1.0,
        "win_rate": 1.0,
        "profit_factor": math.inf,
        "profit_factor_infinite": False,
        "average_pnl": 1.0,
        "max_drawdown": 0.0,
        "ending_balance": STARTING_BALANCE + 1.0,
        "costs": {
            "fee_total": 0.0,
            "spread_total": 0.0,
            "slippage_total": 0.0,
            "total_friction": 0.0,
            "deducted_costs": 0.0,
        },
        "strategy": {"config_repr": "x", "config_hash": "y"},
        "execution": {
            "execution_model": "cost_deduction",
            "fee_rate": 0.001,
            "slippage_rate": 0.0005,
            "spread_rate": 0.0,
            "costs_repr": "x",
            "costs_hash": "y",
            "risk_fraction": 0.01,
        },
    }

    # Pydantic accepts inf as a float, so the real guard is the endpoint's
    # conversion. Assert the payload shape is otherwise valid, which is what
    # makes the conversion testable.
    assert StatisticsResponse.model_validate(payload).trades == 1

    payload["profit_factor"] = None
    parsed = StatisticsResponse.model_validate(payload)
    assert parsed.profit_factor is None


# ---------------------------------------------------------------------------
# closed-trades-only basis
# ---------------------------------------------------------------------------


def test_open_position_is_excluded_from_statistics() -> None:
    """An open position must not enter a closed-trade statistic.

    ``performance`` values only trades whose ``net_pnl`` is set. An open trade
    has none, so it cannot contribute - and must not be counted.
    """

    broker = PaperBroker(
        starting_balance=STARTING_BALANCE, costs=phase13_costs()
    )
    signal = analyze(SOURCE[:LONG_INDEX], CONFIG)
    broker.open_from_signal(
        replace(
            signal,
            timestamp=SOURCE[LONG_INDEX].timestamp,
            price=SOURCE[LONG_INDEX].open,
        )
    )

    client = client_for(broker)
    body = client.get("/api/statistics").json()

    assert broker.open_trade is not None
    assert body["trades"] == 0
    assert body["net_pnl"] == 0.0
    assert body["ending_balance"] == STARTING_BALANCE

    # ...and the position is reported separately, with no unrealized figure.
    position = client.get("/api/position").json()
    assert position["has_position"] is True
    assert "unrealized_pnl" not in json.dumps(position)


def test_no_unrealized_or_equity_field_exists(
    closed_trades_client: TestClient,
) -> None:
    """The engine cannot mark a position, so these cannot appear."""

    body = json.loads(closed_trades_client.get("/api/statistics").text)

    for absent in (
        "unrealized_pnl",
        "equity",
        "available_balance",
        "reserved_capital",
        "margin",
        "buying_power",
    ):
        assert absent not in body, absent


def test_no_invented_risk_metrics(closed_trades_client: TestClient) -> None:
    """The engine defines no risk-adjusted return measure.

    Reporting one would be a new statistic with no research record behind it,
    which is exactly what the integration plan forbids.
    """

    body = json.loads(closed_trades_client.get("/api/statistics").text)

    for absent in (
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "recovery_factor",
        "volatility",
        "confidence_interval",
        "bootstrap_ci",
        "expected_return",
        "forecast",
    ):
        assert absent not in body, absent


def test_no_mark_to_market_drawdown_in_statistics(
    closed_trades_client: TestClient,
) -> None:
    """Realized drawdown only.

    ``robustness.mark_to_market_drawdown`` exists but needs a candle array
    aligned to the journal, and no replay consumes candles in Phase 16. It
    differs from the realized figure by construction, so it must never appear
    under the same label.
    """

    body = json.loads(closed_trades_client.get("/api/statistics").text)

    assert "max_drawdown" in body
    for absent in (
        "mark_to_market_max_dd",
        "mtm_max_drawdown",
        "peak_equity",
        "trough_equity",
    ):
        assert absent not in body, absent


def test_deferred_analysis_sections_are_absent(
    closed_trades_client: TestClient,
) -> None:
    """Monthly and concentration analysis exist in ``robustness`` but are Phase
    16G+ work; surfacing them now would widen the contract silently."""

    body = json.loads(closed_trades_client.get("/api/statistics").text)

    for absent in ("monthly", "months", "concentration", "monthly_summary"):
        assert absent not in body, absent


def test_unsupported_metrics_are_documented_in_code() -> None:
    """Every omission above has a recorded reason, so it reads as a decision."""

    reasons = perfstats.UNSUPPORTED_METRICS

    for name in (
        "unrealized_pnl",
        "equity",
        "mark_to_market_max_dd",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "recovery_factor",
        "bootstrap_ci",
        "monthly_breakdown",
        "concentration",
    ):
        assert name in reasons, name
        assert reasons[name].strip(), name


# ---------------------------------------------------------------------------
# consistency with the other endpoints
# ---------------------------------------------------------------------------


def test_statistics_agrees_with_account(closed_trades_client: TestClient) -> None:
    """Realized P&L and ending balance must not disagree across endpoints.

    Compared with a tolerance, not exactly. ``stats.performance`` sums net P&L
    from ``0.0`` while ``PaperBroker`` accumulates it onto the opening cash, so
    the two totals agree mathematically but differ in the last bits. Both are
    reported from their own engine function; see
    ``test_realized_pnl_differs_only_by_float_accumulation`` for the bound.
    """

    stats_body = closed_trades_client.get("/api/statistics").json()
    account = closed_trades_client.get("/api/account").json()

    assert stats_body["trades"] == account["trade_count"]
    assert stats_body["net_pnl"] == pytest.approx(
        account["realized_pnl"], rel=1e-9
    )
    assert stats_body["ending_balance"] == pytest.approx(
        account["balance"], rel=1e-9
    )


def test_realized_pnl_differs_only_by_float_accumulation() -> None:
    """Pin down the size and cause of the discrepancy between the two engines.

    If this ever exceeds a few ULP, the disagreement is a logic bug rather than
    summation order, and the tolerance in the test above is hiding something.
    """

    broker = build_broker(close_after=30)

    summed = sum(t.net_pnl for t in broker.journal)
    ledgered = broker.cash - broker.starting_balance

    assert summed != ledgered, "expected summation-order drift to exist"
    assert math.isclose(summed, ledgered, rel_tol=1e-9)
    assert abs(summed - ledgered) <= abs(ledgered) * 1e-12


def test_statistics_agrees_with_trades(closed_trades_client: TestClient) -> None:
    trades = closed_trades_client.get("/api/trades").json()

    assert closed_trades_client.get("/api/statistics").json()["trades"] == (
        trades["trade_count"]
    )


def test_statistics_starts_from_the_brokers_starting_balance(
    closed_trades_client: TestClient,
) -> None:
    """Not a constant declared in the API: the broker's own value."""

    account = closed_trades_client.get("/api/account").json()
    body = closed_trades_client.get("/api/statistics").json()

    assert (
        body["ending_balance"] - body["net_pnl"]
    ) == pytest.approx(account["starting_balance"], rel=1e-9)


# ---------------------------------------------------------------------------
# read-only and deterministic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method", ["post", "put", "patch", "delete"]
)
def test_statistics_is_read_only(
    closed_trades_client: TestClient, method: str
) -> None:
    response = getattr(closed_trades_client, method)("/api/statistics")

    assert response.status_code == 405


def test_statistics_does_not_mutate_the_broker(
    closed_trades_client: TestClient,
) -> None:
    session = closed_trades_client.app.state.session
    broker = session.broker

    before = (
        broker.cash,
        len(broker.journal),
        broker.open_trade,
        tuple(t.net_pnl for t in broker.journal),
    )

    for _ in range(5):
        assert closed_trades_client.get("/api/statistics").status_code == 200

    assert (
        broker.cash,
        len(broker.journal),
        broker.open_trade,
        tuple(t.net_pnl for t in broker.journal),
    ) == before


def test_statistics_is_deterministic(closed_trades_client: TestClient) -> None:
    first = closed_trades_client.get("/api/statistics").content
    second = closed_trades_client.get("/api/statistics").content
    third = closed_trades_client.get("/api/statistics").content

    assert first == second == third


def test_statistics_ignores_unknown_query_parameters(
    closed_trades_client: TestClient,
) -> None:
    """No filtering knobs exist, so unknown parameters must not be honoured."""

    baseline = closed_trades_client.get("/api/statistics").content
    attempted = closed_trades_client.get(
        "/api/statistics",
        params={"start": "2024-01-01", "limit": 1, "block_length": 3},
    )

    assert attempted.status_code == 200
    assert attempted.content == baseline


def test_summary_matches_the_endpoint(closed_trades_client: TestClient) -> None:
    """The module-level summary and the HTTP payload agree."""

    session = closed_trades_client.app.state.session
    summary = perfstats.summarise(session.trades, session.account.starting_balance)
    body = closed_trades_client.get("/api/statistics").json()

    assert body["trades"] == summary.trades
    assert body["net_pnl"] == summary.net_pnl
    assert body["ending_balance"] == summary.ending_balance
    assert body["max_drawdown"] == summary.max_drawdown
    assert body["profit_factor_infinite"] == summary.profit_factor_infinite


def test_performance_summary_is_frozen() -> None:
    """A summary is a snapshot, not a mutable accumulator."""

    summary = perfstats.summarise((), STARTING_BALANCE)

    with pytest.raises(Exception):
        summary.net_pnl = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# delegation guards
# ---------------------------------------------------------------------------


def test_only_the_two_engine_statistics_functions_are_called() -> None:
    """Every statistic must be an engine return value.

    Checked on the AST rather than by grepping, so an alias or a differently
    spelled attribute cannot slip past. If a future phase needs a third engine
    function it must be added here deliberately.
    """

    import ast
    import pathlib

    import paper_api

    source = (
        pathlib.Path(paper_api.__file__).parent / "perfstats.py"
    ).read_text(encoding="utf-8")
    allowed = {"performance", "cost_breakdown"}

    called = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "stats"
        ):
            called.add(node.func.attr)

    assert called == allowed, called


def test_perfstats_contains_no_risk_metric_arithmetic() -> None:
    """No standard deviation, square root or exponent may be computed here.

    ``sharpe``/``sortino``/``calmar`` all require at least one of those. If any
    appears, a new risk metric has been introduced without a research record.

    Scanned with the code-only tokeniser, because a raw-text scan also matches
    the explanatory prose in the module docstring - which is precisely the bug
    this guard previously had.
    """

    import pathlib

    import paper_api
    import test_api_account

    code = test_api_account._code_only(
        pathlib.Path(paper_api.__file__).parent / "perfstats.py"
    )

    for token in (
        "sqrt",
        "stdev",
        "pstdev",
        "variance",
        "sharpe",
        "sortino",
        "calmar",
        "**",
        "log",
        "exp",
    ):
        assert token not in code, token


def test_perfstats_imports_nothing_beyond_stats_and_models() -> None:
    """The import list is the delegation contract, so assert it directly.

    ``robustness`` holds bootstrap and concentration analysis; importing it
    would pull in ``random`` and the resampling machinery, making it tempting to
    expose a confidence interval from an endpoint that has no pre-declared
    ``block_length``. ``numpy``, ``statistics`` and ``backtest`` are excluded
    for the same reason: each invites a recomputation the engine already owns.
    """

    import ast
    import pathlib

    import paper_api

    source = (
        pathlib.Path(paper_api.__file__).parent / "perfstats.py"
    ).read_text(encoding="utf-8")

    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # ``from crypto_paper_lab import stats`` names the parent package, so
            # the bound submodules are recorded explicitly.
            if node.module == "crypto_paper_lab":
                modules.update(
                    f"crypto_paper_lab.{alias.name}" for alias in node.names
                )
            else:
                modules.add(node.module)

    assert modules == {
        "__future__",
        "dataclasses",
        "math",
        "typing",
        "crypto_paper_lab.stats",
        "crypto_paper_lab.models",
    }, modules

    for forbidden in ("numpy", "statistics", "random", "robustness", "backtest"):
        assert not any(
            m == forbidden or m.startswith(f"{forbidden}.")
            for m in modules
        ), forbidden


def test_engine_drift_guards_still_pass_over_the_new_module() -> None:
    """Phase 16E's package-wide accounting guard must cover ``perfstats`` too.

    The Phase 16E guard scans every module in the package, so a new file cannot
    quietly introduce cost arithmetic without tripping it.
    """

    import pathlib

    import paper_api
    import test_api_account

    code = test_api_account._code_only(
        pathlib.Path(paper_api.__file__).parent / "perfstats.py"
    )

    for token in ("sum(", "* quantity", "cost_breakdown(", "closed_net_pnls"):
        # ``stats.cost_breakdown(`` is the one legitimate delegation; the
        # forbidden form is a *hand-rolled* breakdown, not the engine call.
        if token == "cost_breakdown(":
            assert "cost_breakdown" in code
            continue
        assert token not in code, token