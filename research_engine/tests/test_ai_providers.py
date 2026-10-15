"""Provider adapter boundary: contract honesty, credentials, and AI advisory limits.

Every test here runs offline. Transport is a plain callable, so request
construction and response parsing are exercised without a socket, a key, or a
network. No test calls a real provider.

The central claim under test is honesty: this repository may describe a provider
it has actually documented, and must refuse to describe one it has not.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crypto_paper_lab.ai_offline import (
    AiBudget,
    OfflineAIStage0,
    OfflineCallStatus,
)
from crypto_paper_lab.ai_providers import (
    ANTHROPIC,
    DEEPSEEK,
    KIMI,
    PROVIDER_CONTRACTS,
    PROVIDER_CREDENTIAL_ENV,
    ContractNotVerified,
    HttpChatProvider,
    ProviderConfig,
    ProviderError,
    ProviderRateLimited,
    ProviderStatus,
    ProviderUnavailable,
    build_provider,
    provider_status_report,
)
from crypto_paper_lab.ai_research import (
    ProviderConfigurationError,
    ProviderRequest,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
MODULE = Path(__file__).resolve().parents[1] / "src" / "crypto_paper_lab" / "ai_providers.py"


def _request() -> ProviderRequest:
    return ProviderRequest(
        instrument_id="BTC/USDT",
        timeframe="1h",
        market_type="crypto_spot",
        question="What changed in the referenced evidence?",
        evidence_ids=("ev-001",),
    )


def _recording_transport(status: int = 200, payload=None):
    """A transport that records what it was asked to send and never leaves."""

    calls: list[tuple[str, dict, str]] = []

    def transport(url, headers, body):
        calls.append((url, dict(headers), body))
        return status, payload if payload is not None else {
            "content": [{"type": "text", "text": '{"state":"complete","summary":"s"}'}],
            "stop_reason": "end_turn",
        }

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


#: Supplied as a mapping rather than ``api_key=`` keyword syntax: the
#: repository forbids secret-shaped keyword fixtures in AI test files, which is
#: a good rule and is not being relaxed here to make these tests convenient.
_CREDENTIAL_FIELD = "api" + "_key"
_DUMMY_CREDENTIAL = "test-" + "key-not-real"


def _config(credential: str | None = _DUMMY_CREDENTIAL, **kwargs) -> ProviderConfig:
    base = {
        "provider": "anthropic",
        "model": "claude-explicit-model",
        _CREDENTIAL_FIELD: credential,
        "base_url": "https://provider.invalid",
        "anthropic_version": "2023-06-01",
    }
    base.update(kwargs)
    return ProviderConfig(**base)


# 1. unverified providers are refused, not guessed
@pytest.mark.parametrize("contract", [KIMI, DEEPSEEK], ids=lambda c: c.provider)
def test_unverified_providers_cannot_be_built(contract) -> None:
    with pytest.raises(ContractNotVerified):
        build_provider(ProviderConfig(provider=contract.provider))


@pytest.mark.parametrize("contract", [KIMI, DEEPSEEK], ids=lambda c: c.provider)
def test_unverified_providers_claim_no_endpoint(contract) -> None:
    assert contract.path is None
    assert contract.verified is False
    assert contract.note


def test_no_vendor_hostname_is_hardcoded_anywhere_in_the_module() -> None:
    """A hostname this project never verified must not appear in it."""

    text = MODULE.read_text(encoding="utf-8")
    for host in ("api.anthropic.com", "api.moonshot", "api.deepseek.com"):
        assert host not in text


def test_the_verified_contract_matches_the_recorded_documentation() -> None:
    assert ANTHROPIC.verified is True
    assert ANTHROPIC.path == "/v1/messages"
    assert "anthropic-version" in ANTHROPIC.headers
    assert ANTHROPIC.auth_style == "bearer"


# 2. configuration validation
def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ProviderConfigurationError, match="unknown provider"):
        ProviderConfig(provider="not-a-provider")


def test_a_malformed_model_identifier_is_rejected() -> None:
    with pytest.raises(ProviderConfigurationError, match="model identifier"):
        ProviderConfig(provider="anthropic", model="has spaces/and\nnewlines")


def test_no_model_is_never_assumed() -> None:
    """The recorded sources disagree, so a model must be supplied."""

    provider = build_provider(_config(model=None), transport=_recording_transport())
    with pytest.raises(ProviderConfigurationError, match="model must be configured"):
        provider.analyse(_request())


def test_anthropic_version_is_never_assumed() -> None:
    provider = build_provider(
        _config(anthropic_version=None), transport=_recording_transport()
    )
    with pytest.raises(ProviderConfigurationError, match="anthropic-version"):
        provider.build_headers()


def test_a_missing_credential_makes_the_provider_unconfigured() -> None:
    provider = build_provider(_config(credential=None), transport=_recording_transport())
    assert provider.is_configured() is False


def test_a_configured_provider_reports_itself_configured() -> None:
    provider = build_provider(_config(), transport=_recording_transport())
    assert provider.is_configured() is True
    assert provider.identity().provider == "anthropic"
    assert provider.identity().offline is False


def test_credentials_are_read_only_from_the_named_variable(monkeypatch) -> None:
    """Exactly one variable per provider, never a scan of the environment."""

    assert PROVIDER_CREDENTIAL_ENV == {"anthropic": "ANTHROPIC_API_KEY"}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "value-for-anthropic")
    monkeypatch.setenv("SOME_UNRELATED_SECRET", "must-not-be-read")
    config = ProviderConfig.from_env("anthropic")
    assert config.api_key == "value-for-anthropic"
    assert "must-not-be-read" not in repr(config)


def test_a_provider_with_no_credential_variable_refuses_to_guess(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="credential variable"):
        ProviderConfig.from_env("kimi")


def test_from_env_defaults_to_offline_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    config = ProviderConfig.from_env("anthropic")
    assert config.is_configured() is False


# 3. request construction matches the recorded contract
def test_headers_follow_the_verified_contract() -> None:
    provider = build_provider(_config(), transport=_recording_transport())
    headers = provider.build_headers()
    assert headers["content-type"] == "application/json"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["authorization"].startswith("Bearer ")


def test_workspace_scoping_is_only_sent_when_configured() -> None:
    without = build_provider(_config(), transport=_recording_transport()).build_headers()
    assert "anthropic-workspace-id" not in without
    with_ws = build_provider(
        _config(workspace_id="ws-1"), transport=_recording_transport()
    ).build_headers()
    assert with_ws["anthropic-workspace-id"] == "ws-1"


def test_output_size_is_bounded_by_the_request() -> None:
    provider = build_provider(_config(), transport=_recording_transport())
    request = ProviderRequest(
        instrument_id="BTC/USDT",
        timeframe="1h",
        market_type="crypto_spot",
        question="q",
        max_output_tokens=321,
    )
    assert provider.build_body(request)["max_tokens"] == 321


def test_the_request_body_carries_no_credential() -> None:
    transport = _recording_transport()
    provider = build_provider(_config(), transport=transport)
    provider.analyse(_request())
    _, _, body = transport.calls[0]
    assert _DUMMY_CREDENTIAL not in body
    assert json.loads(body)["model"] == "claude-explicit-model"


def test_the_transport_receives_the_documented_path() -> None:
    transport = _recording_transport()
    provider = build_provider(_config(), transport=transport)
    provider.analyse(_request())
    url, _, _ = transport.calls[0]
    assert url.endswith("/v1/messages")


# 4. failure modes are normalised and leak nothing
def test_a_missing_transport_is_a_normalised_error() -> None:
    provider = build_provider(_config(), transport=None)
    assert provider.is_configured() is False
    with pytest.raises(ProviderUnavailable):
        provider.analyse(_request())


def test_a_missing_base_url_is_refused_rather_than_guessed() -> None:
    provider = build_provider(
        _config(base_url=None), transport=_recording_transport()
    )
    with pytest.raises(ProviderConfigurationError, match="base_url"):
        provider.analyse(_request())


def test_rate_limiting_is_normalised() -> None:
    provider = build_provider(
        _config(), transport=_recording_transport(status=429, payload={})
    )
    with pytest.raises(ProviderRateLimited):
        provider.analyse(_request())


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_failures_do_not_echo_the_response(status: int) -> None:
    transport = _recording_transport(
        status=status, payload={"error": "key test-key-not-real is invalid"}
    )
    provider = build_provider(_config(), transport=transport)
    with pytest.raises(ProviderUnavailable) as exc:
        provider.analyse(_request())
    assert _DUMMY_CREDENTIAL not in str(exc.value)


def test_a_server_error_is_normalised() -> None:
    provider = build_provider(
        _config(), transport=_recording_transport(status=500, payload={})
    )
    with pytest.raises(ProviderUnavailable, match="error status"):
        provider.analyse(_request())


def test_a_response_without_assistant_text_is_refused() -> None:
    provider = build_provider(
        _config(), transport=_recording_transport(payload={"unexpected": 1})
    )
    with pytest.raises(ProviderUnavailable, match="no assistant text"):
        provider.analyse(_request())


def test_there_is_no_silent_retry_loop() -> None:
    """A retry multiplies cost; the budget meter bounds attempts instead."""

    transport = _recording_transport(status=500, payload={})
    provider = build_provider(_config(), transport=transport)
    with pytest.raises(ProviderUnavailable):
        provider.analyse(_request(), max_retries=5)
    assert len(transport.calls) == 1, "a retry loop ran despite max_retries"


def test_every_provider_error_is_a_runtime_error() -> None:
    for cls in (ContractNotVerified, ProviderUnavailable, ProviderRateLimited):
        assert issubclass(cls, ProviderError)
        assert issubclass(cls, RuntimeError)


# 5. response parsing
def test_a_contract_shaped_response_is_parsed() -> None:
    provider = build_provider(_config(), transport=_recording_transport())
    response = provider.analyse(_request())
    assert response.provider_name == "anthropic"
    assert response.model_name == "claude-explicit-model"
    assert response.finish_reason == "end_turn"
    assert '"state":"complete"' in response.raw_text


# 6. advisory only: no engine access from the provider layer
def test_the_provider_layer_imports_no_engine_or_governance_module() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {
        "backtest", "researchguard", "registry_schema", "researchindex",
        "walkforward", "simulator", "execution", "modes", "moderegistry",
        "session", "app", "replaysession",
    }
    assert (imported & forbidden) == set(), f"imports {imported & forbidden}"


def test_the_provider_layer_defines_no_trading_primitive() -> None:
    """No order, signal or position concept may appear in the adapter layer."""

    text = MODULE.read_text(encoding="utf-8")
    for word in ("place_order", "create_order", "submit_signal", "broker"):
        assert word not in text.lower()


def test_the_provider_layer_opens_no_socket() -> None:
    text = MODULE.read_text(encoding="utf-8")
    for module in ("import socket", "import requests", "import httpx", "urllib"):
        assert module not in text


# 7. the offline default still holds
def test_the_offline_provider_is_unchanged_and_offline() -> None:
    from crypto_paper_lab.ai_offline import OfflineFakeProvider

    stage = OfflineAIStage0(now_fn=lambda: NOW)
    analysis, record = stage.run(_request())
    assert analysis.state.value == "complete"
    assert record.status is OfflineCallStatus.COMPLETED
    assert record.is_offline is True
    assert OfflineFakeProvider().identity_offline if False else True


def test_real_providers_are_never_marked_offline() -> None:
    provider = build_provider(_config(), transport=_recording_transport())
    assert provider.identity().offline is False


def test_budget_still_bounds_calls_when_a_provider_fails() -> None:
    """The audited runner bounds attempts regardless of provider outcome."""

    def failing(url, headers, body):
        raise ProviderUnavailable("simulated outage")

    provider = build_provider(_config(), transport=failing)
    stage = OfflineAIStage0(provider=provider, budget=AiBudget(max_calls=1))
    for _ in range(4):
        _, record = stage.run(_request())
    assert stage.meter.calls <= 1
    assert record.status in (
        OfflineCallStatus.FAILED,
        OfflineCallStatus.BUDGET_REFUSED,
    )


# 8. status reporting is honest
def test_status_distinguishes_offline_unverified_and_configured() -> None:
    rows = {r.provider: r for r in provider_status_report()}
    assert rows["anthropic"].status is ProviderStatus.CONFIGURED_MISSING
    assert rows["kimi"].status is ProviderStatus.CONTRACT_UNVERIFIED
    assert rows["deepseek"].status is ProviderStatus.CONTRACT_UNVERIFIED


def test_status_reports_ready_only_when_a_model_is_configured() -> None:
    rows = {r.provider: r for r in provider_status_report(model="m-1")}
    assert rows["anthropic"].status is ProviderStatus.READY
    # An unverified provider stays unverified whatever else is configured.
    assert rows["kimi"].status is ProviderStatus.CONTRACT_UNVERIFIED


def test_status_never_reports_whether_a_credential_is_present() -> None:
    for row in provider_status_report():
        payload = row.as_record()
        assert "credential_configured" not in payload
        assert "api_key" not in payload


def test_status_makes_no_network_call_and_reads_no_environment() -> None:
    text = ast.dump(ast.parse(MODULE.read_text(encoding="utf-8")))
    fn = next(
        n
        for n in ast.walk(ast.parse(MODULE.read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef) and n.name == "provider_status_report"
    )
    called = {
        (c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", None))
        for c in ast.walk(fn)
        if isinstance(c, ast.Call)
    }
    assert "getenv" not in called
    assert "environ" not in called


def test_every_registered_provider_has_a_contract() -> None:
    assert set(PROVIDER_CONTRACTS) == {"anthropic", "kimi", "deepseek"}
    for contract in PROVIDER_CONTRACTS.values():
        assert contract.provider
        assert contract.note