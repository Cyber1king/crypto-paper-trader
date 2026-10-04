"""Phase 16B tests for the paper-session state API.

The recurring question in this file is *where does each number come from?*
Every account figure is asserted against the research engine's own constants
and the broker's own attributes, so a future change that introduces a second
accounting model inside the API layer fails here.

There is deliberately no test asserting profitability, signal quality or trade
behaviour. Phase 16B performs no execution, so those questions do not arise.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.schemas import SessionResponse
from paper_api.session import (
    MODE_PAPER,
    STATE_IDLE,
    UNSUPPORTED_FIELDS,
    PaperSession,
)
from paper_api.app import SERVICE_NAME

# Authoritative engine values, imported so the tests state their provenance.
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.walkforward import (
    EXECUTION_MODEL,
    FEE_RATE,
    RISK_FRACTION,
    SLIPPAGE_RATE,
    SPREAD_RATE,
    STARTING_BALANCE,
    baseline_config,
    config_hash,
    phase13_costs,
)


@pytest.fixture
def session() -> PaperSession:
    return PaperSession(service=SERVICE_NAME)


@pytest.fixture
def client(session: PaperSession) -> TestClient:
    return TestClient(create_app(ApiConfig(), session=session))


# ---------------------------------------------------------------------------
# 1-2. status and schema
# ---------------------------------------------------------------------------


def test_session_returns_200(client: TestClient) -> None:
    assert client.get("/api/session").status_code == 200


def test_session_validates_against_the_pydantic_schema(
    client: TestClient,
) -> None:
    payload = client.get("/api/session").json()

    parsed = SessionResponse.model_validate(payload)

    assert parsed.service == SERVICE_NAME
    assert parsed.mode == MODE_PAPER
    assert parsed.state == STATE_IDLE


def test_session_schema_rejects_unknown_fields() -> None:
    """An unexpected key must not pass silently."""

    with pytest.raises(ValidationError):
        SessionResponse.model_validate(
            {
                "service": "crypto-paper-lab",
                "session_id": "x",
                "mode": "paper",
                "state": "idle",
                "active": False,
                "account": {
                    "starting_balance": 10000.0,
                    "balance": 10000.0,
                    "realized_pnl": 0.0,
                    "trade_count": 0,
                },
                "strategy": {"config_repr": "", "config_hash": ""},
                "execution": {},
                "has_open_position": False,
                "leverage": 10,
            }
        )


def test_open_position_is_always_null_in_this_phase(
    client: TestClient,
) -> None:
    """No position can exist yet, and absence is reported explicitly."""

    payload = client.get("/api/session").json()

    assert payload["open_position"] is None
    assert payload["has_open_position"] is False


# ---------------------------------------------------------------------------
# 3-4. balances come from the engine, never from the dashboard mock
# ---------------------------------------------------------------------------


def test_starting_balance_matches_the_engine_default(
    client: TestClient,
) -> None:
    payload = client.get("/api/session").json()

    assert payload["account"]["starting_balance"] == STARTING_BALANCE
    assert payload["account"]["starting_balance"] == 10_000.0


def test_starting_balance_matches_a_fresh_broker() -> None:
    """Cross-check against the broker's own default, not just the constant."""

    session = PaperSession(service=SERVICE_NAME)

    assert session.view.account.starting_balance == (
        PaperBroker().starting_balance
    )


def test_dashboard_mock_balance_is_not_used(client: TestClient) -> None:
    """The React mock starts at 100,000. That fiction must not appear."""

    raw = client.get("/api/session").text
    starting_balance = client.get("/api/session").json()["account"][
        "starting_balance"
    ]

    assert "100000" not in raw
    assert starting_balance == STARTING_BALANCE
    assert starting_balance != 100_000


def test_balance_and_realized_pnl_are_zero_at_rest(
    client: TestClient,
) -> None:
    account = client.get("/api/session").json()["account"]

    assert account["balance"] == STARTING_BALANCE
    assert account["realized_pnl"] == 0.0
    assert account["trade_count"] == 0


def test_account_figures_are_read_from_the_broker(session: PaperSession) -> None:
    """The view must reflect broker state, not a cached copy."""

    assert session.view.account.balance == session.broker.cash
    assert (
        session.view.account.starting_balance
        == session.broker.starting_balance
    )
    assert session.view.account.trade_count == len(session.broker.journal)


def test_realized_pnl_matches_the_engine_definition(session: PaperSession) -> None:
    """Same formula the engine uses for BacktestResult.net_pnl."""

    broker = session.broker

    assert session.view.account.realized_pnl == (
        broker.cash - broker.starting_balance
    )


def test_available_and_reserved_are_absent(client: TestClient) -> None:
    """The engine has no margin concept, so no value may be invented."""

    account = client.get("/api/session").json()["account"]

    assert "available_balance" not in account
    assert "reserved_capital" not in account
    assert "equity" not in account
    assert "unrealized_pnl" not in account


def test_undocumented_session_fields_are_absent(client: TestClient) -> None:
    """Nothing beyond the declared schema."""

    payload = client.get("/api/session").json()

    assert set(payload) == {
        "service",
        "session_id",
        "mode",
        "state",
        "active",
        "account",
        "strategy",
        "execution",
        "has_open_position",
        "open_position",
    }


def test_every_unsupported_field_is_really_absent(client: TestClient) -> None:
    """The documented omissions must match the wire format."""

    raw = client.get("/api/session").text

    for name in UNSUPPORTED_FIELDS:
        assert f'"{name}"' not in raw, name


# ---------------------------------------------------------------------------
# 5. no real-money or exchange surface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "leverage",
        "margin",
        "available_balance",
        "reserved_capital",
        "equity",
        "funding",
        "borrow",
        "wallet",
        "api_key",
        "apiKey",
        "secret",
        "token",
        "credential",
        "exchange",
        "venue",
        "order",
        "withdraw",
        "deposit",
        "live",
    ],
)
def test_no_real_money_or_exchange_fields(client: TestClient, field: str) -> None:
    assert field not in client.get("/api/session").text


def test_mode_is_paper_and_has_no_alternative(client: TestClient) -> None:
    assert client.get("/api/session").json()["mode"] == "paper"


def test_mode_cannot_be_anything_else() -> None:
    """The schema admits no live or real mode."""

    with pytest.raises(ValidationError):
        SessionResponse.model_validate(
            {"service": "x", "session_id": "y", "mode": "live"}
        )


def test_session_id_is_not_derived_from_environment(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("MARKET_DATA_API_KEY", "leak-me")
    monkeypatch.setenv("DATABASE_URL", "postgres://leak")

    raw = client.get("/api/session").text

    assert "leak" not in raw
    assert "postgres" not in raw


def test_no_filesystem_path_is_exposed(client: TestClient) -> None:
    raw = client.get("/api/session").text

    assert "\\\\" not in raw
    assert "/Users/" not in raw
    assert "site-packages" not in raw


# ---------------------------------------------------------------------------
# 6. determinism
# ---------------------------------------------------------------------------


def test_repeated_session_calls_are_deterministic(
    client: TestClient,
) -> None:
    first = client.get("/api/session")
    second = client.get("/api/session")
    third = client.get("/api/session")

    assert first.content == second.content == third.content


def test_determinism_holds_across_separate_clients(
    session: PaperSession,
) -> None:
    """A shared session must serialise identically for any consumer."""

    a = TestClient(create_app(ApiConfig(), session=session)).get(
        "/api/session"
    )
    b = TestClient(create_app(ApiConfig(), session=session)).get(
        "/api/session"
    )

    assert a.content == b.content


def test_session_id_is_stable_within_a_session(session: PaperSession) -> None:
    assert session.session_id == session.session_id
    assert session.view.session_id == session.view.session_id


def test_each_session_gets_its_own_id() -> None:
    a = PaperSession(service=SERVICE_NAME)
    b = PaperSession(service=SERVICE_NAME)

    assert a.session_id != b.session_id


# ---------------------------------------------------------------------------
# 7. /healthz is unchanged
# ---------------------------------------------------------------------------


def test_healthz_still_returns_the_exact_phase16a_payload(
    client: TestClient,
) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "crypto-paper-lab",
    }


def test_adding_session_did_not_change_healthz_bytes(
    client: TestClient,
) -> None:
    before = client.get("/healthz").content
    client.get("/api/session")
    after = client.get("/healthz").content

    assert before == after


def test_healthz_stays_deterministic(client: TestClient) -> None:
    assert client.get("/healthz").content == client.get("/healthz").content


# ---------------------------------------------------------------------------
# strategy and execution identity
# ---------------------------------------------------------------------------


def test_strategy_identity_matches_the_frozen_baseline(
    client: TestClient,
) -> None:
    strategy = client.get("/api/session").json()["strategy"]

    assert strategy["config_repr"] == repr(baseline_config())
    assert strategy["config_hash"] == config_hash(baseline_config())


def test_execution_identity_matches_the_frozen_costs(
    client: TestClient,
) -> None:
    execution = client.get("/api/session").json()["execution"]

    assert execution["execution_model"] == EXECUTION_MODEL
    assert execution["fee_rate"] == FEE_RATE
    assert execution["slippage_rate"] == SLIPPAGE_RATE
    assert execution["spread_rate"] == SPREAD_RATE
    assert execution["risk_fraction"] == RISK_FRACTION
    assert execution["costs_repr"] == repr(phase13_costs())


def test_spread_is_zero_under_the_cost_deduction_model(
    client: TestClient,
) -> None:
    execution = client.get("/api/session").json()["execution"]

    assert execution["execution_model"] == "cost_deduction"
    assert execution["spread_rate"] == 0.0


def test_risk_fraction_is_not_leverage(client: TestClient) -> None:
    """0.01 is the fraction of cash committed, not a multiplier."""

    execution = client.get("/api/session").json()["execution"]

    assert execution["risk_fraction"] == 0.01
    assert "leverage" not in client.get("/api/session").text


def test_session_defaults_to_the_authoritative_costs(
    session: PaperSession,
) -> None:
    assert session.broker.costs == phase13_costs()


# ---------------------------------------------------------------------------
# read-only guarantees
# ---------------------------------------------------------------------------


def test_getting_session_does_not_mutate_the_broker(session: PaperSession) -> None:
    cash = session.broker.cash
    journal = list(session.broker.journal)

    session.view
    session.view

    assert session.broker.cash == cash
    assert session.broker.journal == journal


def test_no_order_or_execution_route_exists(client: TestClient) -> None:
    for path in ("/orders", "/api/orders", "/api/execute", "/api/trade"):
        assert client.post(path).status_code == 404, path


def test_cors_wildcard_still_absent(client: TestClient) -> None:
    response = client.get("/api/session", headers={"Origin": "http://evil.test"})

    assert "access-control-allow-origin" not in response.headers