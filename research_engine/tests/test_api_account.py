"""Phase 16E tests: account, position and trade-history endpoints.

Two rules shape this file.

**Fixtures are built by the engine, never by hand.** A populated position or
journal is produced by driving the real ``PaperBroker`` with a real
``analyze()`` signal. Constructing a ``PaperTrade`` by hand would let a test
assert against fields the engine never populates, which is exactly the mistake
this endpoint must not make.

**The API must not mutate.** The broker's cash, journal and open position are
snapshotted, every endpoint is called repeatedly, and the snapshot is compared
afterwards. Reading state must not change it.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paper_api import marketdata
from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.schemas import (
    AccountResponse,
    OpenPositionResponse,
    TradesResponse,
)
from paper_api.session import PaperSession

from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import analyze
from crypto_paper_lab.walkforward import baseline_config, phase13_costs

SOURCE, _ = load_dataset(marketdata.dataset_path())
CONFIG = baseline_config()

#: Indices of the first long and short signals in the frozen dataset, found by
#: scanning. Pinned so the fixtures are fast; the tests assert the signal is
#: genuinely non-flat, so a data change would fail loudly rather than silently.
LONG_INDEX = 22
SHORT_INDEX = 60


def build_broker(close_after: int | None) -> PaperBroker:
    """Drive the real broker through a real signal.

    ``close_after`` is the number of bars to hold before closing; ``None``
    leaves the position open.
    """

    assert analyze(SOURCE[:LONG_INDEX], CONFIG).side == "long"

    broker = PaperBroker(
        starting_balance=10_000.0, costs=phase13_costs()
    )
    signal = analyze(SOURCE[:LONG_INDEX], CONFIG)
    execution = replace(
        signal,
        timestamp=SOURCE[LONG_INDEX].timestamp,
        price=SOURCE[LONG_INDEX].open,
    )
    broker.open_from_signal(execution)

    if close_after is not None:
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
def open_position_client() -> TestClient:
    return client_for(build_broker(close_after=None))


@pytest.fixture
def closed_trades_client() -> TestClient:
    return client_for(build_broker(close_after=30))


# ---------------------------------------------------------------------------
# account
# ---------------------------------------------------------------------------


def test_account_returns_200(empty_client: TestClient) -> None:
    assert empty_client.get("/api/account").status_code == 200


def test_account_validates_against_the_schema(
    empty_client: TestClient,
) -> None:
    parsed = AccountResponse.model_validate(
        empty_client.get("/api/account").json()
    )

    assert parsed.starting_balance == 10_000.0
    assert parsed.trade_count == 0


def test_account_values_come_from_the_broker() -> None:
    broker = build_broker(close_after=30)
    client = client_for(broker)
    payload = client.get("/api/account").json()

    assert payload["starting_balance"] == broker.starting_balance
    assert payload["balance"] == broker.cash
    assert payload["trade_count"] == len(broker.journal)
    assert payload["realized_pnl"] == (
        broker.cash - broker.starting_balance
    )


@pytest.mark.parametrize(
    "invented",
    [
        "available_balance",
        "reserved_capital",
        "equity",
        "unrealized_pnl",
        "margin",
        "buying_power",
        "free_collateral",
        "leverage",
        "notional",
    ],
)
def test_account_has_no_invented_fields(
    empty_client: TestClient, invented: str
) -> None:
    assert invented not in empty_client.get("/api/account").json()


def test_account_is_deterministic(empty_client: TestClient) -> None:
    first = empty_client.get("/api/account").content
    second = empty_client.get("/api/account").content
    third = empty_client.get("/api/account").content

    assert first == second == third


def test_account_after_a_trade_reflects_the_engine(
    closed_trades_client: TestClient,
) -> None:
    payload = closed_trades_client.get("/api/account").json()

    assert payload["trade_count"] == 1
    assert payload["balance"] > payload["starting_balance"]
    assert payload["realized_pnl"] == pytest.approx(
        payload["balance"] - payload["starting_balance"]
    )


# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------


def test_empty_position_response(empty_client: TestClient) -> None:
    response = empty_client.get("/api/position")

    assert response.status_code == 200
    assert response.json() == {"has_position": False, "position": None}


def test_populated_position_serialises_engine_state() -> None:
    broker = build_broker(close_after=None)
    client = client_for(broker)
    trade = broker.open_trade

    assert trade is not None
    payload = client.get("/api/position").json()

    assert payload["has_position"] is True
    position = payload["position"]

    assert position["side"] == trade.side
    assert position["quantity"] == trade.quantity
    assert position["entry_price"] == trade.entry_price
    assert position["reason"] == trade.reason
    assert position["raw_entry_price"] == trade.raw_entry_price
    assert position["support_at_entry"] == trade.support_at_entry
    assert position["resistance_at_entry"] == trade.resistance_at_entry
    assert position["signal_close"] == trade.signal_close
    assert position["entry_time"] == f"{trade.entry_time.isoformat()}Z"


def test_position_entry_time_is_utc(
    open_position_client: TestClient,
) -> None:
    position = open_position_client.get("/api/position").json()["position"]

    assert position["entry_time"].endswith("Z")


@pytest.mark.parametrize(
    "invented",
    [
        "mark_price",
        "current_price",
        "unrealized_pnl",
        "current_value",
        "market_value",
        "equity",
        "notional",
        "leverage",
        "margin",
        "pnl",
        "net_pnl",
        "total_friction",
    ],
)
def test_position_has_no_invented_valuation(
    open_position_client: TestClient, invented: str
) -> None:
    position = open_position_client.get("/api/position").json()["position"]

    assert invented not in position


@pytest.mark.parametrize(
    "deferred", ["costs", "fee_total", "slippage_total", "spread_total",
                 "bars_held"]
)
def test_position_omits_values_the_broker_has_not_computed(
    open_position_client: TestClient, deferred: str
) -> None:
    """These are ``0.0`` dataclass defaults until ``close()`` runs.

    Reporting them would claim an open trade cost nothing and was held zero
    bars, neither of which is known.
    """

    position = open_position_client.get("/api/position").json()["position"]

    assert deferred not in position


def test_open_position_validates_against_the_schema(
    open_position_client: TestClient,
) -> None:
    parsed = OpenPositionResponse.model_validate(
        open_position_client.get("/api/position").json()
    )

    assert parsed.has_position is True
    assert parsed.position is not None
    assert parsed.position.side in ("long", "short")


def test_position_is_deterministic(open_position_client: TestClient) -> None:
    first = open_position_client.get("/api/position").content
    second = open_position_client.get("/api/position").content

    assert first == second


# ---------------------------------------------------------------------------
# trades
# ---------------------------------------------------------------------------


def test_empty_journal_response(empty_client: TestClient) -> None:
    response = empty_client.get("/api/trades")

    assert response.status_code == 200
    assert response.json() == {"trades": [], "trade_count": 0}


def test_controlled_journal_serialisation() -> None:
    broker = build_broker(close_after=30)
    client = client_for(broker)
    trade = broker.journal[0]

    payload = client.get("/api/trades").json()

    assert payload["trade_count"] == 1
    entry = payload["trades"][0]

    assert entry["side"] == trade.side
    assert entry["entry_price"] == trade.entry_price
    assert entry["exit_price"] == trade.exit_price
    assert entry["quantity"] == trade.quantity
    assert entry["exit_reason"] == trade.exit_reason
    assert entry["bars_held"] == trade.bars_held
    assert entry["costs"] == trade.costs
    assert entry["fee_total"] == trade.fee_total
    assert entry["slippage_total"] == trade.slippage_total
    assert entry["spread_total"] == trade.spread_total
    assert entry["pnl"] == trade.pnl
    assert entry["net_pnl"] == trade.net_pnl
    assert entry["total_friction"] == trade.total_friction


def test_trade_net_pnl_is_the_engines_own_property(
    closed_trades_client: TestClient,
) -> None:
    entry = closed_trades_client.get("/api/trades").json()["trades"][0]

    # The engine defines net_pnl = pnl - costs. Confirm we serialise that
    # rather than recomputing something else.
    assert entry["net_pnl"] == pytest.approx(
        entry["pnl"] - entry["costs"]
    )
    assert entry["total_friction"] == pytest.approx(
        entry["fee_total"] + entry["spread_total"] + entry["slippage_total"]
    )


def test_closed_trade_costs_are_populated_not_defaults() -> None:
    """Guards the reason the open position omits them."""

    broker = build_broker(close_after=30)
    trade = broker.journal[0]

    assert trade.fee_total > 0.0
    assert trade.slippage_total > 0.0
    assert trade.costs > 0.0


def test_trades_are_in_journal_order() -> None:
    """Broker journal order, chronological by entry. Not re-sorted here."""

    broker = PaperBroker(10_000.0, costs=phase13_costs())
    config = CONFIG
    for index in (LONG_INDEX, SHORT_INDEX):
        signal = analyze(SOURCE[:index], config)
        broker.open_from_signal(
            replace(
                signal,
                timestamp=SOURCE[index].timestamp,
                price=SOURCE[index].open,
            )
        )
        close_index = index + 20
        trade = broker.close(
            SOURCE[close_index].close, SOURCE[close_index].timestamp
        )
        trade.exit_reason = "opposite_signal"
        trade.bars_held = 20

    payload = client_for(broker).get("/api/trades").json()

    assert payload["trade_count"] == 2
    assert [t["entry_time"] for t in payload["trades"]] == sorted(
        t["entry_time"] for t in payload["trades"]
    )
    assert [t["entry_time"] for t in payload["trades"]] == [
        f"{broker.journal[0].entry_time.isoformat()}Z",
        f"{broker.journal[1].entry_time.isoformat()}Z",
    ]


def test_no_trades_are_fabricated(empty_client: TestClient) -> None:
    """An untouched session must never report a trade."""

    payload = empty_client.get("/api/trades").json()

    assert payload["trades"] == []
    assert payload["trade_count"] == 0


def test_trades_validates_against_the_schema(
    closed_trades_client: TestClient,
) -> None:
    parsed = TradesResponse.model_validate(
        closed_trades_client.get("/api/trades").json()
    )

    assert parsed.trade_count == 1
    assert len(parsed.trades) == 1


def test_trades_are_deterministic(closed_trades_client: TestClient) -> None:
    first = closed_trades_client.get("/api/trades").content
    second = closed_trades_client.get("/api/trades").content
    third = closed_trades_client.get("/api/trades").content

    assert first == second == third


def test_trades_expose_no_paths_or_secrets(
    closed_trades_client: TestClient,
) -> None:
    raw = closed_trades_client.get("/api/trades").text

    for leak in (
        "research_engine",
        ".csv",
        "C:\\",
        "/Users/",
        "site-packages",
        "api_key",
        "secret",
    ):
        assert leak not in raw, leak


# ---------------------------------------------------------------------------
# state mutation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/api/account", "/api/position", "/api/trades"]
)
def test_endpoints_do_not_mutate_broker_state(path: str) -> None:
    broker = build_broker(close_after=30)
    client = client_for(broker)

    def snapshot():
        trade = broker.open_trade
        return (
            broker.cash,
            len(broker.journal),
            None if trade is None else (
                trade.side, trade.entry_price, trade.quantity
            ),
            [t.net_pnl for t in broker.journal],
        )

    before = snapshot()

    for _ in range(5):
        assert client.get(path).status_code == 200

    assert snapshot() == before
    assert broker.cash == before[0]
    assert len(broker.journal) == before[1]


def test_reading_all_endpoints_leaves_the_session_untouched() -> None:
    broker = build_broker(close_after=None)
    client = client_for(broker)
    session_before = client.get("/api/session").content

    for path in ("/api/account", "/api/position", "/api/trades"):
        client.get(path)

    assert client.get("/api/session").content == session_before


def test_trade_count_never_changes_from_reading() -> None:
    broker = build_broker(close_after=30)
    client = client_for(broker)

    for _ in range(3):
        client.get("/api/trades")
        client.get("/api/account")

    assert client.get("/api/account").json()["trade_count"] == 1
    assert len(broker.journal) == 1


# ---------------------------------------------------------------------------
# cross-cutting
# ---------------------------------------------------------------------------


def test_earlier_endpoints_are_unchanged(
    closed_trades_client: TestClient,
) -> None:
    assert closed_trades_client.get("/healthz").json() == {
        "status": "ok",
        "service": "crypto-paper-lab",
    }
    assert closed_trades_client.get("/api/session").status_code == 200
    assert closed_trades_client.get("/api/market", params={"limit": 2}).json()[
        "metadata"
    ]["dataset_candles"] == 17_544
    assert closed_trades_client.get("/api/signal").status_code == 200


def test_reads_do_not_open_a_position() -> None:
    """Reading the signal endpoint must not trade."""

    broker = build_broker(close_after=None)
    client = client_for(broker)
    signal = client.get("/api/signal").json()

    assert signal["signal"] in ("long", "short", "flat")
    # Still exactly the one position the fixture opened, untouched.
    assert client.get("/api/position").json()["has_position"] is True
    assert len(broker.journal) == 0


@pytest.mark.parametrize("path", ["/api/account", "/api/position", "/api/trades"])
def test_endpoints_are_read_only(
    closed_trades_client: TestClient, path: str
) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(closed_trades_client, method)(path).status_code == 405


def test_no_order_or_execution_surface(closed_trades_client: TestClient) -> None:
    """No order submission, and no route that *looks* like one.

    ``/api/replay`` was on this list while it was deferred. Phase 17D added it as
    a read-only control surface, so it now belongs with ``/api/session`` rather
    than here. What must stay absent is anything that submits, fills or closes an
    order.
    """

    for path in (
        "/orders", "/api/order", "/api/execute",
        "/api/position/close", "/api/position/open",
"/api/alerts", "/api/daily",
   ):
        assert closed_trades_client.get(path).status_code == 404, path

    # Phase 26B removed ``/api/high-risk`` from this list. It is a *mode contract*
    # - a read of High-Risk's own paper state plus its one validated size setting -
    # not an order surface: nothing on it submits, fills or closes anything, and
    # High-Risk's entries come from the shared ``/api/replay/step`` route exactly as
    # every other automatic mode's do. Its own absence-from-other-endpoints test
    # lives in test_high_risk.py.


def test_high_risk_exposes_no_order_surface(closed_trades_client: TestClient) -> None:
    """The property that matters now that ``/api/high-risk`` exists.

    A mode-specific route is fine; a mode-specific **verb that trades** is not.
    High-Risk must offer no way to open, close or size a position directly - the
    strategy does that, and sizing has only one input the user may set.
    """

    for path in (
        "/api/high-risk/step",
        "/api/high-risk/start",
        "/api/high-risk/pause",
        "/api/high-risk/reset",
        "/api/high-risk/action",
        "/api/high-risk/execute",
        "/api/high-risk/order",
    ):
        for method in ("get", "post"):
            assert getattr(closed_trades_client, method)(path).status_code in (
                404,
                405,
            ), f"{method.upper()} {path} must not exist"


def _code_only(path) -> str:
    """Source text with comments and string literals removed.

    A guard that greps raw text matches its own explanatory prose, which makes
    it useless. Scanning only executable tokens keeps it honest.
    """

    import io
    import tokenize

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


def test_api_does_not_duplicate_engine_accounting() -> None:
    """No cost or P&L arithmetic may be re-derived anywhere in the API.

    Reading a rate through (``self._costs.fee_rate``) is legitimate
    pass-through; *computing with* one is not, so the tokens below are
    arithmetic-shaped rather than bare names.
    """

    import pathlib

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent
    forbidden_anywhere = (
        "fee_rate *",
        "* fee_rate",
        "fee_rate )",
        "slippage_rate *",
        "* slippage_rate",
        "spread_rate *",
        "cost_breakdown",
        "closed_net_pnls",
        "total_friction(",
        "sum(",
        "* quantity",
        "quantity *",
    )

    for path in sorted(package.glob("*.py")):
        code = _code_only(path)
        # The engine's own cost breakdown is a legitimate delegation and a
        # hand-rolled one is the thing being forbidden, so the call is removed
        # before scanning rather than the token being dropped from the list.
        code = code.replace("stats . cost_breakdown", "")
        for token in forbidden_anywhere:
            assert token not in code, f"{path.name} contains {token!r}"


def test_route_layer_performs_no_accounting_arithmetic() -> None:
    """``app.py`` may only copy. The one legitimate subtraction lives in
    ``session.py``, where it mirrors ``BacktestResult.net_pnl``."""

    import pathlib

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent
    code = _code_only(package / "app.py")

    for token in ("- starting_balance", "entry_price *", "exit_price -"):
        assert token not in code, f"app.py contains {token!r}"

    session_code = _code_only(package / "session.py")

    # Exactly one subtraction, the engine's own definition, so /api/session
    # and /api/account cannot drift apart.
    assert session_code.count("- starting_balance") == 1


def test_session_and_account_agree_by_construction() -> None:
    """The shared ``account`` property backs both endpoints."""

    broker = build_broker(close_after=30)
    client = client_for(broker)

    session_account = client.get("/api/session").json()["account"]
    account = client.get("/api/account").json()

    assert session_account == account


def test_realized_pnl_uses_the_engine_definition() -> None:
    """``realized_pnl`` must equal ``BacktestResult.net_pnl``."""

    broker = build_broker(close_after=30)
    client = client_for(broker)
    account = client.get("/api/account").json()

    assert account["realized_pnl"] == pytest.approx(broker.cash - 10_000.0)
    assert account["realized_pnl"] == pytest.approx(
        broker.journal[0].net_pnl
    )


def test_cors_wildcard_absent(closed_trades_client: TestClient) -> None:
    for path in ("/api/account", "/api/position", "/api/trades"):
        response = closed_trades_client.get(
            path, headers={"Origin": "http://evil.test"}
        )
        assert "access-control-allow-origin" not in response.headers


def test_schema_rejects_unknown_account_field() -> None:
    with pytest.raises(ValidationError):
        AccountResponse.model_validate(
            {
                "starting_balance": 1.0,
                "balance": 1.0,
                "realized_pnl": 0.0,
                "trade_count": 0,
                "margin": 100.0,
            }
        )