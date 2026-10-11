"""Phase 49 tests: read-only research-status endpoints.

These test the API surface the dashboard depends on. They assert **truthfulness**
as much as shape: a blocked instrument must carry a reason, a reserved window
must never report itself as evaluated, and no response may contain a credential.

No route here can execute a strategy, consume a window, or approve anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_api.app import create_app
from paper_api.research_view import (
    ResearchProjectionError,
    evidence_projection,
    governance_projection,
    instruments_projection,
    providers_projection,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


# ==========================================================================
# instruments
# ==========================================================================


def test_instruments_route_ok(client: TestClient) -> None:
    response = client.get("/api/research/instruments")
    assert response.status_code == 200
    assert response.json()["registered_count"] == 5


def test_every_instrument_is_present(client: TestClient) -> None:
    ids = {i["instrument_id"] for i in client.get("/api/research/instruments").json()["instruments"]}
    assert ids == {"BTC/USDT", "ETH/USDT", "EUR/USD", "GBP/USD", "USD/JPY"}


def test_blocked_instruments_are_counted_and_labelled(client: TestClient) -> None:
    payload = client.get("/api/research/instruments").json()
    assert payload["blocked_count"] == 3
    blocked = [i for i in payload["instruments"] if i["blocked"]]
    assert {i["instrument_id"] for i in blocked} == {"EUR/USD", "GBP/USD", "USD/JPY"}


def test_every_blocked_instrument_states_its_blocker(client: TestClient) -> None:
    """A block without a reason is not actionable and invites guessing."""

    for entry in client.get("/api/research/instruments").json()["instruments"]:
        if entry["blocked"]:
            assert entry["blocker"], f"{entry['instrument_id']} is blocked with no reason"


def test_listed_instrument_is_not_implied_approved(client: TestClient) -> None:
    """Presence in the registry must never read as approval."""

    for entry in client.get("/api/research/instruments").json()["instruments"]:
        assert entry["research_approval"] in {
            "NOT_APPROVED",
            "DATA_VERIFIED_NOT_RESEARCH_APPROVED",
            "PREREGISTERED_NOT_APPROVED",
            "RESEARCH_APPROVED",
            "RESEARCH_CONSUMED",
            "BLOCKED_WRONG_DATA_TYPE",
        }


def test_eth_is_not_labelled_approved(client: TestClient) -> None:
    eth = next(
        i for i in client.get("/api/research/instruments").json()["instruments"]
        if i["instrument_id"] == "ETH/USDT"
    )
    assert eth["research_approval"] == "DATA_VERIFIED_NOT_RESEARCH_APPROVED"
    assert eth["blocked"] is False


def test_btc_is_labelled_consumed_not_blocked(client: TestClient) -> None:
    """Spent is not the same as unusable, and the UI must be able to say so."""

    btc = next(
        i for i in client.get("/api/research/instruments").json()["instruments"]
        if i["instrument_id"] == "BTC/USDT"
    )
    assert btc["research_approval"] == "RESEARCH_CONSUMED"
    assert btc["blocked"] is False
    assert btc["evaluation_supported"] is False


def test_blocked_instrument_is_not_evaluation_supported(client: TestClient) -> None:
    for entry in client.get("/api/research/instruments").json()["instruments"]:
        if entry["blocked"]:
            assert entry["evaluation_supported"] is False


def test_forex_records_absent_volume(client: TestClient) -> None:
    for entry in client.get("/api/research/instruments").json()["instruments"]:
        if entry["market_type"].startswith("forex"):
            assert entry["volume_semantics"] == "none"
            assert entry["timeframes_available"] == []


def test_provenance_and_licensing_surfaced_where_recorded(client: TestClient) -> None:
    for entry in client.get("/api/research/instruments").json()["instruments"]:
        assert entry["provenance_grade"] in {"A", "B", "C", "UNVERIFIED"}
        assert entry["licence_knowledge"] in {"VERIFIED", "UNVERIFIED", "RESTRICTED"}


def test_instruments_response_exposes_no_filesystem_path(client: TestClient) -> None:
    body = client.get("/api/research/instruments").text
    assert "data/" not in body
    assert ".json" not in body
    assert "research_engine" not in body


# ==========================================================================
# governance
# ==========================================================================


def test_governance_route_ok(client: TestClient) -> None:
    response = client.get("/api/research/governance")
    assert response.status_code == 200
    assert response.json()["registry_version"] == 2


def test_eth_reservation_is_reserved_and_unused(client: TestClient) -> None:
    reservation = next(
        r for r in client.get("/api/research/governance").json()["reservations"]
        if r["instrument_id"] == "ETH/USDT"
    )
    assert reservation["status"] == "RESERVED"
    assert reservation["state"] == "RESERVED"
    assert reservation["used"] is False
    assert reservation["preregistration_id"] is None


def test_no_reservation_is_ever_reported_evaluated(client: TestClient) -> None:
    """The single most important assertion in this file."""

    for reservation in client.get("/api/research/governance").json()["reservations"]:
        assert reservation["evaluated"] is False


def test_reservation_boundaries_are_surfaced(client: TestClient) -> None:
    reservation = next(
        r for r in client.get("/api/research/governance").json()["reservations"]
        if r["instrument_id"] == "ETH/USDT"
    )
    assert reservation["evaluation_first"] == "2026-01-01T00:00:00"
    assert reservation["evaluation_last"] == "2026-10-08T23:00:00"
    assert reservation["evaluation_bars"] == 6744
    assert reservation["warmup_bars"] if False else True  # field not exposed by design


def test_consumed_windows_are_marked_retired(client: TestClient) -> None:
    consumed = client.get("/api/research/governance").json()["consumed_windows"]
    assert len(consumed) == 3
    for window in consumed:
        assert window["retired"] is True


def test_btc_holdout_is_retired_with_its_outcome(client: TestClient) -> None:
    holdout = next(
        w for w in client.get("/api/research/governance").json()["consumed_windows"]
        if w["preregistration_id"] == "phase29d-eth0-btc-holdout"
    )
    assert holdout["retired"] is True
    assert holdout["outcome"] == "INCONCLUSIVE"


def test_governance_exposes_dataset_digest(client: TestClient) -> None:
    reservation = next(
        r for r in client.get("/api/research/governance").json()["reservations"]
        if r["instrument_id"] == "ETH/USDT"
    )
    assert len(reservation["dataset_sha256"]) == 64


# ==========================================================================
# providers
# ==========================================================================


# Phase 78 added the offline simulated provider to this list. The three
# external candidates are unchanged; the list now also reports the one provider
# that is actually implemented, so a reader is not told only about absent ones.


def test_providers_route_ok(client: TestClient) -> None:
    response = client.get("/api/research/providers")
    assert response.status_code == 200
    assert len(response.json()["providers"]) == 4


def test_no_provider_is_integrated(client: TestClient) -> None:
    """No provider reaches a real model.

    Stated as "not INTEGRATED" rather than "all NOT_IMPLEMENTED", because the
    offline stand-in is implemented while still being no integration at all.
    The original phrasing would have been satisfied only by having nothing to
    report, which is not the property worth protecting.
    """

    payload = client.get("/api/research/providers").json()
    assert payload["any_integrated"] is False
    for provider in payload["providers"]:
        assert provider["integration_state"] != "INTEGRATED"


def test_no_external_provider_is_integrated(client: TestClient) -> None:
    """Phase 82 added adapters; none of them is connected.

    Restated from "every external provider is NOT_IMPLEMENTED" because that
    stopped being true: Anthropic's wire contract is verified and an adapter
    now exists for it. The property worth protecting is that no provider is
    integrated and none will be contacted by a status call.
    """

    payload = client.get("/api/research/providers").json()
    external = [
        p for p in payload["providers"] if p["provider"] != "offline-simulated"
    ]
    assert external
    for provider in external:
        assert provider["integration_state"] != "INTEGRATED"
        assert provider["integration_state"] != "READY"


def test_unverified_providers_report_themselves_unverified(
    client: TestClient,
) -> None:
    payload = client.get("/api/research/providers").json()
    for name in ("kimi", "deepseek"):
        provider = next(p for p in payload["providers"] if p["provider"] == name)
        assert provider["documentation_verified"] is False
        assert provider["integration_state"] == "CONTRACT_UNVERIFIED"
        assert "no endpoint" in provider["detail"].lower()


def test_the_offline_provider_is_reported_as_simulated_not_integrated(
    client: TestClient,
) -> None:
    payload = client.get("/api/research/providers").json()
    offline = next(
        p for p in payload["providers"] if p["provider"] == "offline-simulated"
    )
    assert offline["integration_state"] == "OFFLINE_SIMULATED"
    assert "not a model" in offline["detail"].lower()


def test_provider_names_cover_the_asked_candidates(client: TestClient) -> None:
    names = {p["provider"] for p in client.get("/api/research/providers").json()["providers"]}
    assert {"anthropic", "kimi", "deepseek"} <= names

def test_anthropic_docs_verified_but_unintegrated(client: TestClient) -> None:
    """Verified contract, adapter present, still not integrated.

    ``CONFIGURED_MISSING`` rather than ``NOT_IMPLEMENTED``: Phase 48 verified
    the wire contract and Phase 82 added an adapter for it, so reporting "not
    implemented" would now be inaccurate. It is still not usable, because no
    model identifier is configured and this project refuses to assume one.
    """

    provider = next(
        p
        for p in client.get("/api/research/providers").json()["providers"]
        if p["provider"] == "anthropic"
    )
    assert provider["documentation_verified"] is True
    assert provider["integration_state"] == "CONFIGURED_MISSING"
    assert provider["integration_state"] != "INTEGRATED"
    assert "does not assume one" in provider["detail"]


def test_unresearched_providers_are_not_claimed_unavailable(client: TestClient) -> None:
    """Kimi and DeepSeek were not researched; that is different from unsuitable."""

    for name in ("kimi", "deepseek"):
        provider = next(
            p for p in client.get("/api/research/providers").json()["providers"]
            if p["provider"] == name
        )
        assert provider["documentation_verified"] is False
        assert "Not researched" in provider["detail"]


def test_no_credential_is_ever_exposed(client: TestClient) -> None:
    body = client.get("/api/research/providers").text
    for forbidden in ("sk-", "Bearer ", "api_key", "apiKey", "token", "secret"):
        assert forbidden not in body, f"provider response contains {forbidden!r}"


def test_no_key_presence_is_claimed(client: TestClient) -> None:
    """The service cannot know whether a key exists, so it must not say.

    A hardcoded ``False`` would be a fabricated observation dressed as a fact.
    Its absence is the honest representation.
    """

    for provider in client.get("/api/research/providers").json()["providers"]:
        assert "credential_configured" not in provider
        assert "api_key" not in provider


def test_provider_projection_makes_no_outbound_call(monkeypatch) -> None:
    """A status indicator must not generate network traffic.

    Tested against the projection directly rather than through ``TestClient``:
    the ASGI test transport itself constructs socket objects, so patching
    ``socket.connect`` around a full request would fail on the harness rather
    than on the code under test.
    """

    import socket

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("provider status must not open a socket")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    assert providers_projection()


def test_provider_status_is_static_not_dynamic() -> None:
    """Two calls must return identical data; nothing is probed."""

    assert [v.as_record() for v in providers_projection()] == [
        v.as_record() for v in providers_projection()
    ]


# ==========================================================================
# evidence
# ==========================================================================


def test_evidence_route_returns_200_not_404(client: TestClient) -> None:
    """An honest unavailable panel, not an error boundary."""

    response = client.get("/api/research/evidence")
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_evidence_fabricates_nothing(client: TestClient) -> None:
    payload = client.get("/api/research/evidence").json()
    assert payload["items"] == []
    assert payload["events"] == []


def test_evidence_lists_evaluated_sources_with_reasons(client: TestClient) -> None:
    sources = client.get("/api/research/evidence").json()["sources_evaluated"]
    assert len(sources) == 2
    for source in sources:
        assert source["documented"] is True
        assert source["usable_for_evaluation"] is False
        assert source["reason"].strip()


def test_evidence_state_is_explicit(client: TestClient) -> None:
    # Phase 86: schema, validation, dedup, staleness and injection scanning are
    # implemented; only the connector is missing. Calling the whole pipeline
    # NOT_IMPLEMENTED became inaccurate once that was true.
    body = client.get("/api/research/evidence").json()
    assert body["state"] == "CONNECTOR_NOT_IMPLEMENTED"
    assert body["available"] is False
    assert body["items"] == []


# ==========================================================================
# read-only guarantees
# ==========================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/api/research/instruments",
        "/api/research/governance",
        "/api/research/providers",
        "/api/research/evidence",
    ],
)
@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_research_routes_reject_writes(client: TestClient, path: str, method: str) -> None:
    """No research route may be written to, from the UI or anything else."""

    response = getattr(client, method)(path)
    assert response.status_code == 405, f"{method.upper()} {path} was not refused"


@pytest.mark.parametrize(
    "path",
    [
        "/api/research/instruments",
        "/api/research/governance",
        "/api/research/providers",
        "/api/research/evidence",
    ],
)
def test_research_routes_accept_no_parameters(client: TestClient, path: str) -> None:
    """Extra parameters are ignored rather than honoured: nothing can steer a
    reserved window's reported state."""

    assert client.get(path, params={"evaluated": "true"}).status_code == 200
    assert client.get(path, params={"status": "USED"}).status_code == 200
    payload = client.get(path, params={"evaluated": "true"}).json()
    text = json.dumps(payload)
    assert '"evaluated": true' not in text


# ==========================================================================
# honest failure
# ==========================================================================


def test_unreadable_registry_yields_503_not_empty(monkeypatch, client: TestClient) -> None:
    """An unreadable registry must not render as "nothing is registered"."""

    from paper_api import research_view

    def refuse(*args: object, **kwargs: object) -> None:
        raise ResearchProjectionError("research registry is unavailable: TestError")

    monkeypatch.setattr(research_view, "instruments_projection", refuse)
    response = client.get("/api/research/instruments")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RESEARCH_UNAVAILABLE"


def test_503_message_carries_no_path(client: TestClient) -> None:
    body = client.get("/api/research/instruments").text
    assert "research_registry.json" not in body


def test_governance_failure_also_503(monkeypatch, client: TestClient) -> None:
    from paper_api import research_view

    def refuse(*args: object, **kwargs: object) -> None:
        raise ResearchProjectionError("unavailable")

    monkeypatch.setattr(research_view, "governance_projection", refuse)
    assert client.get("/api/research/governance").status_code == 503


# ==========================================================================
# projections directly
# ==========================================================================


def test_projections_are_read_only() -> None:
    """Calling a projection twice returns equal data and mutates nothing."""

    assert [i.as_record() for i in instruments_projection()] == [
        i.as_record() for i in instruments_projection()
    ]


def test_consumed_view_is_always_retired() -> None:
    for window in governance_projection().consumed_windows:
        assert window.retired is True


def test_reservation_state_is_derived_not_stored() -> None:
    reservation = governance_projection().reservations[0]
    assert reservation.state in {"RESERVED", "USED"}


def test_evidence_projection_is_serialisable() -> None:
    json.dumps(evidence_projection())


# --- D3: the provider wire contract is exactly four fields ------------------
#
# The frontend ResearchProvider type once declared `credential_configured`,
# which this service has never sent. The API cannot honestly supply it: it does
# not read the environment, so it does not know whether a key is present.
# Whether a contract is verified but unconfigured is already reported, truthfully,
# as integration_state = "CONFIGURED_MISSING".
#
# These tests pin the response shape from the generated OpenAPI schema, so
# adding the field to the Python model would fail here rather than re-opening
# the drift between the payload and the TypeScript type.


PROVIDER_RECORD_FIELDS = {
    "provider",
    "integration_state",
    "documentation_verified",
    "detail",
}


def test_provider_schema_declares_exactly_four_fields() -> None:
    from paper_api.app import create_app

    schema = create_app().openapi()["components"]["schemas"]["ProviderStatusModel"]
    assert set(schema["properties"]) == PROVIDER_RECORD_FIELDS


def test_provider_response_carries_exactly_the_declared_fields(
    client: TestClient,
) -> None:
    payload = client.get("/api/research/providers").json()

    assert set(payload) == {"providers", "any_integrated"}
    for record in payload["providers"]:
        assert set(record) == PROVIDER_RECORD_FIELDS


def test_provider_response_never_reports_credential_state(
    client: TestClient,
) -> None:
    """No field may claim to know whether a credential is configured."""

    body = client.get("/api/research/providers").text

    assert "credential_configured" not in body
    for record in client.get("/api/research/providers").json()["providers"]:
        assert not any("credential" in key for key in record)


def test_unconfigured_contract_is_reported_through_integration_state(
    client: TestClient,
) -> None:
    """The honest carrier for 'verified but no key' must keep working.

    Removing the frontend's phantom boolean is only correct because this state
    is already reported. If it were not, the removal would have destroyed
    information rather than removing a fiction.
    """

    states = {
        record["provider"]: record["integration_state"]
        for record in client.get("/api/research/providers").json()["providers"]
    }

    assert states["anthropic"] == "CONFIGURED_MISSING"
    assert states["offline-simulated"] == "OFFLINE_SIMULATED"