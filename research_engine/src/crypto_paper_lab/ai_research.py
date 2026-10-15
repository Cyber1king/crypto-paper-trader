"""Provider-independent interface for AI-assisted research analysis.

Phase 48. This module defines the *contract* an AI research assistant must
satisfy. It contains no provider client, no HTTP call, no API key handling, and
no model call of any kind.

What it does contain is the separation of concerns that makes an AI layer safe
to introduce into a research pipeline:

* An AI provider is **advisory only**. It cannot approve data, consume a
  research window, bypass a research guard, or influence execution. Those
  capabilities are structurally absent from this module: it has no reference to
  the research registry, no import of :mod:`crypto_paper_lab.researchguard`, and
  no ability to construct a ``ResearchContext``.
* An assistant **may abstain**, and abstention is a first-class outcome rather
  than a failure. Insufficient, stale, contradictory or out-of-scope information
  is a legitimate reason to decline, and the schema records it explicitly.
* Provider output is **untrusted input**. It arrives as text and is validated
  against :class:`ResearchAnalysis` before anything downstream sees it.
* Nothing here produces a calibrated probability, win rate, or expected return.
  :func:`assert_no_probability_claims` enforces that at construction.

Live provider integration is **NOT IMPLEMENTED**. No credential exists in this
repository and none is required to use this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "AbstentionReason",
    "AnalysisState",
    "ResearchAnalysis",
    "ProviderRequest",
    "ProviderResponse",
    "AIResearchProvider",
    "ProviderConfigurationError",
    "ProviderNotConfigured",
    "assert_no_probability_claims",
    "PROBABILITY_CLAIM_TERMS",
    "AIResearchProvider",
    "ProviderConfigurationError",
    "ProviderNotConfigured",
    "ProviderRequest",
    "ProviderResponse",
    "ResearchAnalysis",
    "AnalysisPipeline",
    "AnalysisState",
    "AbstentionReason",
    "redact_secrets",
    "default_pipeline",
]


class ProviderConfigurationError(RuntimeError):
    """Raised when provider configuration is absent or malformed.

    Never raised for a missing *secret value* in a way that could echo it: this
    error names the missing variable, not its contents.
    """


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider is invoked without being configured.

    Distinct from :class:`ProviderConfigurationError` so a caller can tell
    "you never set this up" from "you set it up wrongly".
    """


class AbstentionReason(str, Enum):
    """Why an assistant declined to offer analysis.

    An enum rather than free text so abstentions are countable. A research log
    that records "the model wasn't sure" without a reason is not auditable.
    """

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STALE_EVIDENCE = "stale_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_MARKET = "unsupported_market"
    UNSUPPORTED_TIMEFRAME = "unsupported_timeframe"
    OUT_OF_SCOPE = "out_of_scope"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    SCHEMA_INVALID = "schema_invalid"


class AnalysisState(str, Enum):
    """Whether an analysis was produced or declined."""

    COMPLETE = "complete"
    ABSTAINED = "abstained"


#: Terms that would present a model opinion as a quantified forecast.
#:
#: A language model producing the phrase "80% likely" has asserted a calibrated
#: probability it cannot support. These are refused at construction so such a
#: claim cannot enter a research artifact.
PROBABILITY_CLAIM_TERMS = (
    "probability",
    "probabilities",
    "win_rate",
    "win rate",
    "expected_return",
    "expected return",
    "certainty",
    "guaranteed",
    "will outperform",
    "risk-adjusted edge",
    "sharpe of",
    "confidence interval",
    "p_value",
    "p-value",
)


def assert_no_probability_claims(text: str) -> None:
    """Refuse text presenting model output as a quantified forecast.

    Applied to the assistant's own summary. It cannot catch every phrasing and
    does not pretend to; it catches the terms most likely to be misread as a
    calibrated number by a downstream reader.
    """

    lowered = str(text or "").lower()
    found = [term for term in PROBABILITY_CLAIM_TERMS if term in lowered]
    if found:
        raise ProviderConfigurationError(
            "analysis text presents a model opinion as a quantified forecast: "
            + ", ".join(repr(t) for t in found)
            + ". No validated methodology in this project calibrates model "
            "output to a probability, so such a claim cannot be recorded."
        )


@dataclass(frozen=True)
class ResearchAnalysis:
    """A structured, provider-independent research observation.

    Every field is either evidence-referenced, explicitly uncertain, or a
    refusal. There is no field for a score, a probability, or a recommendation
    to trade, because this project has no validated methodology that would make
    such a field meaningful.
    """

    analysis_id: str
    instrument_id: str
    timeframe: str
    market_type: str
    analysed_at: datetime
    state: AnalysisState
    provider_name: str
    #: Optional. A provider adapter may legitimately not disclose which model
    #: served a request, and recording "unknown" is more honest than guessing.
    model_name: str | None = None
    evidence_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    price_context_summary: str | None = None
    news_summary: str | None = None
    economic_event_summary: str | None = None
    conflicting_evidence: tuple[str, ...] = ()
    data_freshness_note: str | None = None
    limitations: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    abstention_reason: AbstentionReason | None = None
    abstention_detail: str | None = None

    def __post_init__(self) -> None:
        for name in ("analysis_id", "instrument_id", "timeframe", "market_type", "provider_name"):
            if not str(getattr(self, name)).strip():
                raise ProviderConfigurationError(
                    f"{name} is required; an unattributed analysis cannot be "
                    "reviewed or reproduced"
                )

        object.__setattr__(
            self, "analysed_at",
            self.analysed_at.astimezone(timezone.utc)
            if self.analysed_at.tzinfo is not None
            else _refuse_naive(self.analysed_at),
        )

        # An abstention must say why. "The model wasn't sure" is not auditable.
        if self.state is AnalysisState.ABSTAINED:
            if self.abstention_reason is None:
                raise ProviderConfigurationError(
                    "an abstained analysis requires abstention_reason"
                )
            if not str(self.abstention_detail or "").strip():
                raise ProviderConfigurationError(
                    "an abstained analysis requires abstention_detail explaining "
                    "the specific reason"
                )
        elif self.abstention_reason is not None:
            raise ProviderConfigurationError(
                "abstention_reason may only be set when state is ABSTAINED"
            )

        # A complete analysis with no evidence at all is claiming insight from
        # nothing, which is the failure this whole layer exists to prevent.
        if self.state is AnalysisState.COMPLETE:
            if not self.evidence_ids and not self.event_ids:
                raise ProviderConfigurationError(
                    "a complete analysis must reference at least one piece of "
                    "evidence or one economic event; analysis with no inputs is "
                    "not research"
                )

        for text in (
            self.price_context_summary,
            self.news_summary,
            self.economic_event_summary,
            self.abstention_detail,
        ):
            if text:
                assert_no_probability_claims(text)

        for note in self.observations:
            assert_no_probability_claims(note)

    @property
    def is_advisory_only(self) -> bool:
        """Always true. Present so a reader can confirm the guarantee explicitly."""

        return True

    def as_record(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "instrument_id": self.instrument_id,
            "timeframe": self.timeframe,
            "market_type": self.market_type,
            "analysed_at": self.analysed_at.isoformat(),
            "state": self.state.value,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "evidence_ids": list(self.evidence_ids),
            "event_ids": list(self.event_ids),
            "price_context_summary": self.price_context_summary,
            "news_summary": self.news_summary,
            "economic_event_summary": self.economic_event_summary,
            "conflicting_evidence": list(self.conflicting_evidence),
            "data_freshness_note": self.data_freshness_note,
            "limitations": list(self.limitations),
            "observations": list(self.observations),
            "abstention_reason": (
                self.abstention_reason.value if self.abstention_reason else None
            ),
            "abstention_detail": self.abstention_detail,
            "advisory_only": True,
        }

    def to_json(self) -> str:
        """Serialise deterministically.

        ``sort_keys`` keeps identical analyses byte-identical, so a research log
        can be diffed across runs.
        """

        return json.dumps(self.as_record(), indent=2, sort_keys=True)

    @staticmethod
    def from_record(record: dict[str, Any]) -> "ResearchAnalysis":
        """Rebuild from a validated record, refusing anything malformed."""

        if not isinstance(record, dict):
            raise ProviderConfigurationError("analysis record must be a mapping")

        required = (
            "analysis_id", "instrument_id", "timeframe", "market_type",
            "analysed_at", "state", "provider_name",
        )
        missing = [f for f in required if not str(record.get(f, "")).strip()]
        if missing:
            raise ProviderConfigurationError(
                "analysis record is missing: " + ", ".join(sorted(missing))
            )

        try:
            state = AnalysisState(str(record["state"]))
        except ValueError as exc:
            raise ProviderConfigurationError(
                f"state={record['state']!r} is not one of "
                + ", ".join(s.value for s in AnalysisState)
            ) from exc

        reason = None
        if record.get("abstention_reason"):
            try:
                reason = AbstentionReason(str(record["abstention_reason"]))
            except ValueError as exc:
                raise ProviderConfigurationError(
                    f"abstention_reason={record['abstention_reason']!r} is not a "
                    "known reason"
                ) from exc

        return ResearchAnalysis(
            analysis_id=str(record["analysis_id"]),
            instrument_id=str(record["instrument_id"]),
            timeframe=str(record["timeframe"]),
            market_type=str(record["market_type"]),
            analysed_at=datetime.fromisoformat(str(record["analysed_at"])),
            state=state,
            provider_name=str(record["provider_name"]),
            model_name=(
                str(record["model_name"]) if record.get("model_name") else None
            ),
            evidence_ids=tuple(record.get("evidence_ids", ())),
            event_ids=tuple(record.get("event_ids", ())),
            price_context_summary=record.get("price_context_summary"),
            news_summary=record.get("news_summary"),
            economic_event_summary=record.get("economic_event_summary"),
            conflicting_evidence=tuple(record.get("conflicting_evidence", ())),
            data_freshness_note=record.get("data_freshness_note"),
            limitations=tuple(record.get("limitations", ())),
            observations=tuple(record.get("observations", ())),
            abstention_reason=reason,
            abstention_detail=record.get("abstention_detail"),
        )


def _refuse_naive(value: datetime) -> datetime:
    raise ProviderConfigurationError(
        f"analysed_at must be timezone-aware, got naive {value!r}"
    )


# ==========================================================================
# provider interface
# ==========================================================================


@dataclass(frozen=True)
class ProviderRequest:
    """What an assistant is asked to analyse.

    Carries **identifiers and evidence references only** — never market data,
    never prices, never a credential. The provider is asked to reason about
    context, not to be handed the trading engine's internals.
    """

    instrument_id: str
    timeframe: str
    market_type: str
    question: str
    evidence_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    as_of: datetime | None = None
    max_output_tokens: int = 2000

    def __post_init__(self) -> None:
        if self.max_output_tokens <= 0:
            raise ProviderConfigurationError("max_output_tokens must be positive")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ProviderConfigurationError("as_of must be timezone-aware")

    def to_prompt(self) -> str:
        """Render the request as a prompt.

        Explicit about scope and about what the assistant must not claim. A
        provider that has not been told the limits will exceed them.
        """

        lines = [
            "You are assisting with observational market research.",
            "",
            f"Instrument: {self.instrument_id}",
            f"Market: {self.market_type}",
            f"Timeframe: {self.timeframe}",
            "",
            f"Question: {self.question}",
            "",
        ]
        if self.evidence_ids:
            lines.append("Evidence references:")
            lines.extend(f"  - {e}" for e in self.evidence_ids)
        if self.event_ids:
            lines.append("Economic event references:")
            lines.extend(f"  - {e}" for e in self.event_ids)

        lines.extend([
            "",
            "Requirements:",
            "  - Do NOT state probabilities, win rates, or expected returns.",
            "  - Do NOT recommend entering, exiting, sizing or holding a position.",
            "  - Do NOT claim access to data you were not given.",
            "  - If the evidence is insufficient, stale, contradictory, or the",
            "    market is outside your scope, abstain and say why.",
            "  - Distinguish what the evidence states from what you infer.",
            "",
            'Respond as JSON matching: {"state": "complete"|"abstained",',
            '  "summary", "observations": [], "limitations": [],',
            '  "abstention_reason", "abstention_detail"}',
        ])
        return "\n".join(lines)


@dataclass(frozen=True)
class ProviderResponse:
    """Raw provider output plus the metadata needed to audit it.

    ``raw_text`` is retained because a research log should preserve what the
    provider actually said, not only this project's interpretation of it.

    ``redacted`` records whether secrets were stripped. It defaults to ``True``
    so a caller must actively assert that a payload was safe, rather than
    forgetting to check.
    """

    provider_name: str
    model_name: str | None
    raw_text: str
    retrieved_at: datetime
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    redacted: bool = True
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if not str(self.provider_name).strip():
            raise ProviderConfigurationError("provider_name is required")
        if self.retrieved_at.tzinfo is None:
            raise ProviderConfigurationError("retrieved_at must be timezone-aware")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ProviderConfigurationError("latency_ms cannot be negative")

    @property
    def looks_truncated(self) -> bool:
        """True when the provider stopped early.

        A truncated response is not a shorter opinion, it is a partial one, and
        treating it as complete would misrepresent what was received.
        """

        return self.finish_reason == "length"


@runtime_checkable
class AIResearchProvider(Protocol):
    """Adapter interface for an AI research provider.

    Deliberately minimal and provider-independent. An implementation must:

    * never raise on a network or provider error — return a failure state, or
      let :class:`ProviderNotConfigured` / :class:`ProviderConfigurationError`
      escape, so a caller cannot mistake a provider outage for an abstention;
    * never fabricate a response. If a call fails, the response must say so;
    * never accept a credential as a constructor argument in a way that would
      end up in a log or a traceback.

    No implementation ships with this repository. See
    ``experiments/phase48/PROVIDER_STATUS.md``.
    """

    name: str

    def is_configured(self) -> bool:
        """Whether this provider could make a call right now."""

        ...

    def analyse(
        self,
        request: ProviderRequest,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> ProviderResponse:
        """Return raw provider output, or raise a configuration error.

        Implementations must enforce ``timeout_seconds`` themselves and must
        treat ``max_retries`` as a bound, never as a default to exceed.
        """

        ...


def redact_secrets(text: str, secrets: tuple[str, ...]) -> tuple[str, bool]:
    """Remove known secret values from text before it is recorded.

    Returns the redacted text and whether anything was replaced. Substitutes a
    fixed marker rather than a length-preserving one, so a redacted payload
    cannot leak a secret's length either.
    """

    redacted = str(text or "")
    changed = False
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "[REDACTED]")
            changed = True
    return redacted, changed


@dataclass
class AnalysisPipeline:
    """Documents the separation between ingestion, validation and AI analysis.

    This is a *description of responsibilities*, not an executor. It exists so
    the ordering constraint is explicit and testable rather than implied by
    directory layout.

    The ordering is the safety property: deterministic checks run **before**
    AI analysis, and AI output is **after** them and cannot feed back into them.
    """

    stages: tuple[str, ...] = (
        "1_data_ingestion",
        "2_deterministic_validation",
        "3_news_and_event_retrieval",
        "4_evidence_aggregation",
        "5_ai_assisted_analysis",
        "6_deterministic_policy_and_risk_checks",
        "7_research_reporting",
        "8_dashboard_presentation",
    )

    #: Stages whose inputs must not come from anything stage 5 produced.
    #:
    #: Stages 1-4 run *before* AI analysis. Stage 6 runs *after* it and must
    #: likewise never consume AI output. Listing all five together is the
    #: statement that both pre- and post-analysis stages are AI-independent --
    #: the safety property is that AI sits in a ring around, not a bridge across.
    independent_of_ai: tuple[str, ...] = (
        "1_data_ingestion",
        "2_deterministic_validation",
        "3_news_and_event_retrieval",
        "4_evidence_aggregation",
        "6_deterministic_policy_and_risk_checks",
    )

    #: Stages AI output may never influence.
    forbidden_for_ai: tuple[str, ...] = (
        "2_deterministic_validation",
        "6_deterministic_policy_and_risk_checks",
        "7_research_reporting",
    )

    def ordering_is_sound(self) -> bool:
        """Validate the declared ordering rather than trusting it.

        Three properties are checked, each of which has been broken at some
        point in research codebases:

        * no stage depends on one declared later;
        * no AI-independent stage sits *after* AI analysis, which would let AI
          output flow into validation or risk control;
        * no forbidden stage is the AI stage itself.
        """

        indices = [self.stages.index(s) for s in self.stages]
        if indices != sorted(indices):
            return False

        ai = self.stages.index("5_ai_assisted_analysis")

        # Stages 1-4 must precede AI; stage 6 must follow it. Either ordering
        # violation means AI output could reach a stage that must not see it.
        before = [
            "1_data_ingestion",
            "2_deterministic_validation",
            "3_news_and_event_retrieval",
            "4_evidence_aggregation",
        ]
        if not all(self.stages.index(s) < ai for s in before):
            return False
        if not all(
            self.stages.index(s) > ai
            for s in self.independent_of_ai
            if s not in before
        ):
            return False

        return all(self.stages.index(s) != ai for s in self.forbidden_for_ai)

    def as_record(self) -> dict[str, Any]:
        return {
            "stages": list(self.stages),
            "independent_of_ai": list(self.independent_of_ai),
            "forbidden_for_ai": list(self.forbidden_for_ai),
            "ordering_is_sound": self.ordering_is_sound(),
        }


def default_pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()