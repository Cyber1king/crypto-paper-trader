"""Phase 48 tests: provider-independent AI research layer.

Every test uses a **mock**. No provider is contacted, no network call is made,
and no credential exists in this repository.

One test asserts the absence of a live integration rather than its presence.
That asymmetry is deliberate: a mocked suite must never be reported as evidence
that a provider works.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crypto_paper_lab.ai_research import (
    PROBABILITY_CLAIM_TERMS,
    AIResearchProvider,
    AbstentionReason,
    AnalysisPipeline,
    AnalysisState,
    ProviderConfigurationError,
    ProviderRequest,
    ProviderResponse,
    ResearchAnalysis,
    assert_no_probability_claims,
    default_pipeline,
    redact_secrets,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
MODULE = Path(__file__).resolve().parents[1] / "src" / "crypto_paper_lab" / "ai_research.py"


def analysis(**overrides: object) -> ResearchAnalysis:
    fields: dict[str, object] = {
        "analysis_id": "a1",
        "instrument_id": "ETH/USDT",
        "timeframe": "1h",
        "market_type": "crypto_spot",
        "analysed_at": NOW,
        "state": AnalysisState.COMPLETE,
        "provider_name": "mock-provider",
        "evidence_ids": ("e1",),
        "price_context_summary": "Range with declining volume.",
        "observations": ("Volatility compressed.",),
    }
    fields.update(overrides)
    return ResearchAnalysis(**fields)  # type: ignore[arg-type]


# ==========================================================================
# no live integration exists
# ==========================================================================


def test_no_provider_client_in_module() -> None:
    """Phase 48 requirement: never report a live integration based on mocks."""

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "urllib.request",
                      "anthropic", "openai", "http.client"):
        assert forbidden not in source, f"{forbidden} present in ai_research.py"


def test_no_network_import_anywhere_in_package() -> None:
    """The whole engine must remain offline-capable."""

    package = MODULE.parent
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in (
                        "requests", "httpx", "urllib", "socket", "http"
                    ), f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] not in (
                    "requests", "httpx", "anthropic", "openai"
                ), f"{path.name} imports from {node.module}"


def test_no_credential_lookup_in_module() -> None:
    """Credentials would come from the environment; this module reads none."""

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in ("os.environ", "os.getenv", "getenv", "API_KEY", "api_key"):
        assert forbidden not in source, f"{forbidden} present in ai_research.py"


def test_no_secret_pattern_in_repository_tests() -> None:
    """This phase must not introduce a secret, not even a fake one in a fixture.

    Scans for *assignment-like* secret usage rather than bare substrings: this
    test file necessarily names the patterns it searches for, so a substring scan
    would match its own search literals and always fail.
    """

    tests_dir = Path(__file__).resolve().parent
    offenders: list[str] = []
    for path in tests_dir.glob("test_ai*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if value.startswith(("sk-", "Bearer ")) and len(value) > 8:
                    offenders.append(f"{path.name}: literal secret-shaped value")
            elif isinstance(node, ast.keyword) and node.arg in (
                "api_key", "apiKey", "token", "secret"
            ):
                offenders.append(f"{path.name}: keyword {node.arg}")

    assert offenders == [], f"secret-shaped fixtures: {offenders}"


def test_no_ai_import_in_execution_path() -> None:
    """AI must not be reachable from the trading engine."""

    package = MODULE.parent
    for name in ("backtest.py", "replay.py", "walkforward.py", "simulator.py",
                 "strategy.py", "researchguard.py"):
        path = package / name
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        assert "ai_research" not in source, f"{name} imports ai_research"


# ==========================================================================
# provider protocol
# ==========================================================================


class MockProvider:
    """A conformant mock, used to exercise the protocol."""

    name = "mock-provider"

    def is_configured(self) -> bool:
        return True

    def analyse(self, request: ProviderRequest, *, timeout_seconds: float = 30.0,
                max_retries: int = 2) -> ProviderResponse:
        return ProviderResponse(
            provider_name=self.name,
            model_name="mock-model-1",
            raw_text=json.dumps({"state": "abstained"}),
            retrieved_at=NOW,
        )


def test_mock_satisfies_protocol() -> None:
    """Confirms the protocol is implementable. It says nothing about a real provider."""

    assert isinstance(MockProvider(), AIResearchProvider)


def test_partial_implementation_does_not_satisfy_protocol() -> None:
    class Incomplete:
        name = "incomplete"

    assert not isinstance(Incomplete(), AIResearchProvider)


def test_protocol_is_not_implemented_by_this_module() -> None:
    """No concrete provider ships with the repository."""

    source = MODULE.read_text(encoding="utf-8")
    assert "class" in source
    for concrete in ("class AnthropicProvider", "class OpenAIProvider",
                     "class KimiProvider", "class DeepSeekProvider"):
        assert concrete not in source, f"{concrete} must not exist yet"


# ==========================================================================
# provider request and prompt
# ==========================================================================


def test_request_requires_positive_token_budget() -> None:
    with pytest.raises(ProviderConfigurationError, match="max_output_tokens"):
        ProviderRequest(
            instrument_id="ETH/USDT", timeframe="1h",
            market_type="crypto_spot", question="q", max_output_tokens=0,
        )


def test_request_requires_aware_as_of() -> None:
    with pytest.raises(ProviderConfigurationError, match="timezone-aware"):
        ProviderRequest(
            instrument_id="ETH/USDT", timeframe="1h",
            market_type="crypto_spot", question="q",
            as_of=datetime(2026, 10, 9, 12),
        )


def test_prompt_forbids_probability_claims() -> None:
    prompt = ProviderRequest(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", question="What changed?",
    ).to_prompt()
    assert "probabilities" in prompt.lower()
    assert "win rates" in prompt.lower()


def test_prompt_forbids_trading_recommendations() -> None:
    prompt = ProviderRequest(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", question="What changed?",
    ).to_prompt()
    assert "recommend" in prompt.lower()
    assert "sizing" in prompt.lower()


def test_prompt_states_abstention_is_permitted() -> None:
    prompt = ProviderRequest(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", question="What changed?",
    ).to_prompt()
    assert "abstain" in prompt.lower()
    assert "contradictory" in prompt.lower()


def test_prompt_includes_evidence_references() -> None:
    prompt = ProviderRequest(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", question="q",
        evidence_ids=("e1", "e2"), event_ids=("ev1",),
    ).to_prompt()
    assert "e1" in prompt and "e2" in prompt and "ev1" in prompt


def test_request_carries_no_market_data() -> None:
    """The provider is asked to reason about context, not handed engine internals."""

    request = ProviderRequest(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", question="q",
    )
    assert not hasattr(request, "candles")
    assert not hasattr(request, "prices")


# ==========================================================================
# provider response
# ==========================================================================


def test_response_requires_aware_timestamp() -> None:
    with pytest.raises(ProviderConfigurationError, match="timezone-aware"):
        ProviderResponse(
            provider_name="p", model_name=None, raw_text="{}",
            retrieved_at=datetime(2026, 10, 9, 12),
        )


def test_response_rejects_negative_latency() -> None:
    with pytest.raises(ProviderConfigurationError, match="latency_ms"):
        ProviderResponse(
            provider_name="p", model_name=None, raw_text="{}",
            retrieved_at=NOW, latency_ms=-1,
        )


def test_truncated_response_detected() -> None:
    """A truncated response is a partial opinion, not a shorter one."""

    response = ProviderResponse(
        provider_name="p", model_name=None, raw_text="{}",
        retrieved_at=NOW, finish_reason="length",
    )
    assert response.looks_truncated is True


def test_complete_response_not_truncated() -> None:
    response = ProviderResponse(
        provider_name="p", model_name=None, raw_text="{}",
        retrieved_at=NOW, finish_reason="stop",
    )
    assert response.looks_truncated is False


def test_response_defaults_to_redacted() -> None:
    """A caller must actively assert a payload was safe, not forget to check."""

    response = ProviderResponse(
        provider_name="p", model_name=None, raw_text="{}", retrieved_at=NOW,
    )
    assert response.redacted is True


# ==========================================================================
# analysis schema
# ==========================================================================


@pytest.mark.parametrize(
    "field", ["analysis_id", "instrument_id", "timeframe", "market_type", "provider_name"]
)
def test_required_fields_refused(field: str) -> None:
    defaults = {
        "analysis_id": "a1", "instrument_id": "ETH/USDT", "timeframe": "1h",
        "market_type": "crypto_spot", "analysed_at": NOW,
        "state": AnalysisState.COMPLETE, "provider_name": "mock",
        "evidence_ids": ("e1",),
    }
    with pytest.raises(ProviderConfigurationError, match=field):
        ResearchAnalysis(**{**defaults, field: ""})  # type: ignore[arg-type]


def test_naive_analysis_timestamp_refused() -> None:
    with pytest.raises(ProviderConfigurationError, match="timezone-aware"):
        analysis(analysed_at=datetime(2026, 10, 9, 12))


def test_complete_analysis_requires_evidence() -> None:
    """Analysis with no inputs is not research."""

    with pytest.raises(ProviderConfigurationError, match="at least one piece"):
        analysis(evidence_ids=(), event_ids=())


def test_complete_analysis_accepts_events_only() -> None:
    record = analysis(evidence_ids=(), event_ids=("ev1",))
    assert record.state is AnalysisState.COMPLETE


def test_abstention_requires_a_reason() -> None:
    with pytest.raises(ProviderConfigurationError, match="abstention_reason"):
        analysis(state=AnalysisState.ABSTAINED, abstention_reason=None)


def test_abstention_requires_detail() -> None:
    with pytest.raises(ProviderConfigurationError, match="abstention_detail"):
        analysis(
            state=AnalysisState.ABSTAINED,
            abstention_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
            abstention_detail="  ",
        )


def test_abstention_permitted_with_reason_and_detail() -> None:
    record = analysis(
        state=AnalysisState.ABSTAINED,
        abstention_reason=AbstentionReason.STALE_EVIDENCE,
        abstention_detail="All supplied evidence is older than one week.",
    )
    assert record.state is AnalysisState.ABSTAINED
    assert record.abstention_reason is AbstentionReason.STALE_EVIDENCE


def test_reason_on_a_complete_analysis_refused() -> None:
    with pytest.raises(ProviderConfigurationError, match="only be set"):
        analysis(abstention_reason=AbstentionReason.OUT_OF_SCOPE)


def test_model_name_is_optional() -> None:
    """A provider need not disclose its model; 'unknown' beats a guess."""

    assert analysis(model_name=None).model_name is None


# ==========================================================================
# abstention is a first-class outcome
# ==========================================================================


def test_every_abstention_reason_is_expressible() -> None:
    for reason in AbstentionReason:
        record = analysis(
            state=AnalysisState.ABSTAINED,
            abstention_reason=reason,
            abstention_detail="Recorded for audit.",
        )
        assert record.abstention_reason is reason


def test_abstention_reasons_cover_the_required_cases() -> None:
    values = {r.value for r in AbstentionReason}
    for required in ("insufficient_evidence", "stale_evidence",
                     "conflicting_evidence", "unsupported_instrument",
                     "unsupported_market", "unsupported_timeframe"):
        assert required in values


def test_out_of_scope_instrument_can_abstain() -> None:
    record = analysis(
        instrument_id="EUR/USD", market_type="forex_reference_rates",
        state=AnalysisState.ABSTAINED,
        abstention_reason=AbstentionReason.UNSUPPORTED_MARKET,
        abstention_detail="No session/DST validation exists for forex.",
    )
    assert record.abstention_reason is AbstentionReason.UNSUPPORTED_MARKET


# ==========================================================================
# no probability claims
# ==========================================================================


@pytest.mark.parametrize("term", PROBABILITY_CLAIM_TERMS)
def test_probability_terms_refused(term: str) -> None:
    with pytest.raises(ProviderConfigurationError, match="quantified forecast"):
        assert_no_probability_claims(f"There is a {term} here.")


def test_probability_claim_in_summary_refused() -> None:
    with pytest.raises(ProviderConfigurationError, match="quantified forecast"):
        analysis(price_context_summary="There is a 70% probability of a rise.")


def test_probability_claim_in_observation_refused() -> None:
    with pytest.raises(ProviderConfigurationError, match="quantified forecast"):
        analysis(observations=("Expected return looks attractive.",))


def test_probability_claim_in_abstention_refused() -> None:
    with pytest.raises(ProviderConfigurationError, match="quantified forecast"):
        analysis(
            state=AnalysisState.ABSTAINED,
            abstention_reason=AbstentionReason.OUT_OF_SCOPE,
            abstention_detail="The win rate here is not knowable.",
        )


def test_neutral_observations_accepted() -> None:
    record = analysis(
        price_context_summary="Consolidation continues; volume is declining.",
        observations=("No evidence of a catalyst in the supplied set.",),
        news_summary="Two reports describe the same announcement.",
    )
    assert record.state is AnalysisState.COMPLETE


# ==========================================================================
# advisory only
# ==========================================================================


def test_analysis_is_advisory_only() -> None:
    assert analysis().is_advisory_only is True


def test_analysis_record_declares_advisory_only() -> None:
    assert analysis().as_record()["advisory_only"] is True


def test_analysis_cannot_reference_a_reservation() -> None:
    """The AI layer has no vocabulary for consuming a research window."""

    record = analysis().as_record()
    for forbidden in ("reservation_id", "consume", "registry", "used_on"):
        assert forbidden not in record


def test_ai_research_does_not_import_researchguard() -> None:
    """The AI layer must have no path to the reservation machinery.

    Scanned structurally via the AST rather than by substring, so a passing
    prose mention in a docstring does not read as an import.
    """

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "researchguard" not in (node.module or ""), (
                f"ai_research imports {node.module}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "researchguard" not in alias.name, (
                    f"ai_research imports {alias.name}"
                )


# ==========================================================================
# pipeline ordering
# ==========================================================================


def test_pipeline_declares_eight_stages() -> None:
    assert len(default_pipeline().stages) == 8


def test_pipeline_ordering_is_sound() -> None:
    assert default_pipeline().ordering_is_sound() is True


def test_pipeline_validation_and_risk_are_ai_independent() -> None:
    pipeline = default_pipeline()
    assert "2_deterministic_validation" in pipeline.independent_of_ai
    assert "6_deterministic_policy_and_risk_checks" in pipeline.independent_of_ai


def test_pipeline_marks_ai_forbidden_stages() -> None:
    pipeline = default_pipeline()
    for stage in pipeline.forbidden_for_ai:
        assert stage != "5_ai_assisted_analysis"


def test_reordered_pipeline_is_detected() -> None:
    """A pipeline that puts AI before validation must not pass silently."""

    broken = AnalysisPipeline(stages=(
        "5_ai_assisted_analysis",
        "2_deterministic_validation",
        "1_data_ingestion",
    ))
    assert broken.ordering_is_sound() is False


# ==========================================================================
# serialisation
# ==========================================================================


def test_analysis_roundtrips_through_json() -> None:
    record = analysis().as_record()
    restored = ResearchAnalysis.from_record(json.loads(json.dumps(record)))
    assert restored.analysis_id == record["analysis_id"]
    assert restored.observations == ("Volatility compressed.",)


def test_analysis_json_is_deterministic() -> None:
    record = analysis()
    assert record.to_json() == record.to_json()


def test_from_record_refuses_missing_fields() -> None:
    with pytest.raises(ProviderConfigurationError, match="missing"):
        ResearchAnalysis.from_record({"analysis_id": "a1"})


def test_from_record_refuses_unknown_state() -> None:
    record = analysis().as_record()
    record["state"] = "confident"
    with pytest.raises(ProviderConfigurationError, match="not one of"):
        ResearchAnalysis.from_record(record)


def test_from_record_refuses_unknown_abstention_reason() -> None:
    record = analysis(
        state=AnalysisState.ABSTAINED,
        abstention_reason=AbstentionReason.OUT_OF_SCOPE,
        abstention_detail="x",
    ).as_record()
    record["abstention_reason"] = "vibes"
    with pytest.raises(ProviderConfigurationError, match="not a known reason"):
        ResearchAnalysis.from_record(record)


def test_from_record_refuses_non_mapping() -> None:
    with pytest.raises(ProviderConfigurationError, match="mapping"):
        ResearchAnalysis.from_record(["not", "a", "mapping"])  # type: ignore[arg-type]


# ==========================================================================
# redaction
# ==========================================================================


def test_secret_is_redacted() -> None:
    text, changed = redact_secrets("auth token=abc123xyz", ("abc123xyz",))
    assert "abc123xyz" not in text
    assert changed is True


def test_redaction_reports_no_change_when_absent() -> None:
    text, changed = redact_secrets("nothing sensitive", ("abc123xyz",))
    assert changed is False
    assert text == "nothing sensitive"


def test_redaction_marker_does_not_leak_length() -> None:
    text, _ = redact_secrets("k=short", ("short",))
    assert "[REDACTED]" in text
    assert "short" not in text


def test_empty_secret_ignored() -> None:
    text, changed = redact_secrets("some text", ("",))
    assert changed is False
    assert text == "some text"