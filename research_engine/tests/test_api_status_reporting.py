"""Phase 78: API and dashboard status must reflect the implementation.

A status endpoint that overstates capability is worse than one that is absent,
because a reader has no reason to disbelieve it. These tests check that what the
API reports matches what the engine can actually do.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.costs import MARKET_COST_PROFILES
from crypto_paper_lab.walkforward import DATASET_SHA256, phase13_costs
from crypto_paper_lab.modes import AI_INTELLIGENCE, MODES
@pytest.fixture(scope="module")
def client() -> TestClient:
    from paper_api.app import app

    return TestClient(app)


# 1. market endpoint reports market type
def test_market_endpoint_states_its_market_type(client: TestClient) -> None:
    body = client.get("/api/market").json()
    assert body["metadata"]["market_type"] == "crypto_spot"


def test_market_type_is_one_the_engine_implements(client: TestClient) -> None:
    body = client.get("/api/market").json()
    assert body["metadata"]["market_type"] in MARKET_COST_PROFILES


def test_market_endpoint_still_reports_dataset_identity(client: TestClient) -> None:
    meta = client.get("/api/market").json()["metadata"]
    assert meta["dataset_sha256"] == DATASET_SHA256
    assert meta["dataset_candles"] > 0


def test_market_metadata_does_not_disclose_a_filesystem_path(client: TestClient) -> None:
    body = client.get("/api/market").json()["metadata"]
    assert "/" not in body["source"]
    assert "\\" not in body["source"]


# 2. cost-profile status is reported wherever costs are reported
def test_execution_identity_names_its_market(client: TestClient) -> None:
    body = client.get("/api/session").json()
    assert body["execution"]["market_type"] == "crypto_spot"


def test_reported_market_matches_the_costs_in_force(client: TestClient) -> None:
    body = client.get("/api/session").json()
    assert body["execution"]["market_type"] == phase13_costs().market_type


def test_zero_spread_is_described_as_a_cost_deduction_artefact(client: TestClient) -> None:
    body = client.get("/api/session").json()
    assert body["execution"]["spread_rate"] == 0.0
    assert body["execution"]["execution_model"] == "cost_deduction"


# 3. paper-mode identity
def test_modes_endpoint_reports_all_six(client: TestClient) -> None:
    body = client.get("/api/modes").json()
    assert {m["mode"] for m in body["modes"]} == set(MODES)


def test_modes_report_execution_capability(client: TestClient) -> None:
    body = client.get("/api/modes").json()
    alerts = next(m for m in body["modes"] if m["mode"] == "alerts")
    assert alerts["supports_execution"] is False
    for mode in body["modes"]:
        if mode["mode"] != "alerts":
            assert mode["supports_execution"] is True


def test_ai_intelligence_label_does_not_claim_a_model(client: TestClient) -> None:
    body = client.get("/api/modes").json()
    ai = next(m for m in body["modes"] if m["mode"] == AI_INTELLIGENCE)
    assert "no model" in ai["label"].lower()


def test_no_mode_label_promises_a_return(client: TestClient) -> None:
    body = client.get("/api/modes").json()
    banned = ("risk-free", "will profit", "assured", "live trading", "real money")
    for mode in body["modes"]:
        text = f"{mode['label']} {mode['note']}".lower()
        for word in banned:
            assert word not in text, f"{mode['mode']} mentions {word!r}"


# 4. AI simulation status
def test_providers_route_makes_no_call_and_reports_states(client: TestClient) -> None:
    response = client.get("/api/research/providers")
    assert response.status_code == 200
    assert response.json()["any_integrated"] is False


def test_no_provider_is_reported_as_integrated(client: TestClient) -> None:
    body = client.get("/api/research/providers").json()
    assert all(p["integration_state"] != "INTEGRATED" for p in body["providers"])


def test_the_offline_provider_is_labelled_simulated(client: TestClient) -> None:
    body = client.get("/api/research/providers").json()
    offline = next(
        p for p in body["providers"] if p["provider"] == "offline-simulated"
    )
    assert offline["integration_state"] == "OFFLINE_SIMULATED"


def test_provider_status_never_reports_whether_a_key_is_present(client: TestClient) -> None:
    """The service does not read the environment, so it must not claim to."""

    body = client.get("/api/research/providers").json()
    for provider in body["providers"]:
        assert "credential_configured" not in provider
        assert "api_key" not in provider


def test_evidence_route_reports_honestly_rather_than_fabricating(
    client: TestClient,
) -> None:
    body = client.get("/api/research/evidence").json()
    assert body["available"] is False
    assert body["items"] == []


# 5. health stays operational and side-effect free
def test_healthz_is_ok(client: TestClient) -> None:
    """The health route is ``/healthz``, deliberately outside the ``/api`` prefix."""

    assert client.get("/healthz").status_code == 200


def test_healthz_does_not_initiate_a_research_run(client: TestClient) -> None:
    """Health must not evaluate anything. Proven by leaving state untouched."""

    before = client.get("/api/session").json()
    assert client.get("/healthz").status_code == 200
    after = client.get("/api/session").json()
    assert before == after


# 6. malformed input fails safely
@pytest.mark.parametrize(
    "path",
    [
        "/api/market?limit=0",
        "/api/market?limit=-5",
        "/api/market?limit=notanumber",
        "/api/market?start=not-a-date",
        "/api/replay?mode=nonsense",
        "/api/replay?mode=../../etc/passwd",
    ],
)
def test_malformed_requests_do_not_return_500(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code < 500, f"{path} produced {response.status_code}"


def test_an_unknown_mode_is_rejected_not_silently_defaulted(client: TestClient) -> None:
    """Rejected by validation (422), not quietly served as Standard.

    The point of the assertion is that the request is refused; the exact
    status is FastAPI's choice and is not what makes this safe.
    """

    response = client.get("/api/replay?mode=does_not_exist")
    assert response.status_code in (404, 422)


def test_error_bodies_do_not_leak_internals(client: TestClient) -> None:
    response = client.get("/api/replay?mode=does_not_exist")
    assert response.status_code in (404, 422)
    text = response.text.lower()
    for leak in ("traceback", "c:\\", "/src/", "site-packages", "api_key"):
        assert leak not in text, f"error body leaked {leak!r}"


# 7. no live-trading surface exists
def test_there_is_no_order_placement_route(client: TestClient) -> None:
    paths = {r.path for r in client.app.routes if hasattr(r, "path")}
    for banned in ("/api/order", "/api/trade/submit", "/api/withdraw", "/api/deposit"):
        assert banned not in paths

# 10. news / evidence pipeline readiness (Phase 86)
def test_evidence_route_reports_no_news_rather_than_inventing_it(
    client: TestClient,
) -> None:
    body = client.get("/api/research/evidence").json()
    assert body["available"] is False
    assert body["items"] == []
    assert body["events"] == []


def test_evidence_route_separates_built_from_missing(client: TestClient) -> None:
    """The panel must be able to say what exists without claiming news."""

    pipeline = client.get("/api/research/evidence").json()["pipeline"]
    assert pipeline["schema_implemented"] is True
    assert pipeline["validation_implemented"] is True
    assert pipeline["deduplication_implemented"] is True
    assert pipeline["staleness_rules_implemented"] is True
    assert pipeline["injection_scan_implemented"] is True
    assert pipeline["connector_implemented"] is False
    assert pipeline["advisory_only"] is True


def test_evidence_state_names_the_missing_piece_not_the_whole_pipeline(
    client: TestClient,
) -> None:
    assert client.get("/api/research/evidence").json()["state"] == (
        "CONNECTOR_NOT_IMPLEMENTED"
    )


def test_evidence_response_keeps_its_original_fields(client: TestClient) -> None:
    """Backward compatibility: the pre-existing fields are all still present."""

    body = client.get("/api/research/evidence").json()
    for field in ("available", "state", "items", "events", "detail"):
        assert field in body


def test_no_news_payload_field_exists_to_be_filled_later(client: TestClient) -> None:
    """No fabricated news shape is exposed while nothing is retrieved."""

    body = client.get("/api/research/evidence").json()
    assert "digest" not in body
    assert body["items"] == []


def test_health_does_not_expose_news_or_provider_activity(client: TestClient) -> None:
    body = client.get("/healthz").json()
    for forbidden in ("news", "provider", "ai", "items"):
        assert forbidden not in body


def test_no_route_exposes_a_live_news_connector(client: TestClient) -> None:
    paths = {r.path for r in client.app.routes if hasattr(r, "path")}
    assert not [p for p in paths if "news" in p or "feed" in p]
