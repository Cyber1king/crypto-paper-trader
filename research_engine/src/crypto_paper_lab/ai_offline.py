"""Stage 0: an offline, deterministic AI research provider.

This repository had the *shape* of an AI research subsystem -- a provider
Protocol, a prompt renderer, a redaction helper, a set of abstention reasons --
and nothing behind it. ``timeout_seconds`` was a parameter every implementation
was asked to honour, with no implementation to honour it.

This module supplies one: a fake provider that runs entirely in-process, makes
no network call, and exists so the surrounding machinery can be exercised and
tested without a key, a quota, or a connection.

Four constraints shaped the design, each of which is enforced rather than
documented:

**Honest timeouts.** ``future.result(timeout=...)`` returns at the deadline,
but Python cannot preempt a thread that is already running. Pretending
otherwise would be a lie in the safety-critical direction: a caller would
believe work had stopped while it was still in flight. So the deadline is
enforced, the record says ``work_abandoned=True``, and the late value is
discarded -- never returned, never parsed, never logged as an analysis. The
real bound on damage is that this provider never *writes* anything.

**Injection boundaries.** ``ProviderRequest`` already carries identifiers
rather than prose, which is the right instinct but not a boundary. Evidence
IDs are validated against a strict character class, so a caller cannot smuggle
"ignore previous instructions" through a field meant to hold a reference. The
question text is delimited and its embedded newlines escaped, so untrusted
content cannot forge structural markers.

**Budgets before work.** Limits are checked before the call is made, not
after the cost is incurred, and a refusal is recorded as a refusal rather than
raised as an error the caller might retry past.

**Structural non-influence.** This module imports the standard library and
:mod:`crypto_paper_lab.ai_research`, and nothing else. It does not import the
backtest engine, the strategy configuration, the research registry, or the
reservation guard, so "AI output cannot affect trading, configuration,
authorisation, registry state or research guards" is a property of the import
graph that a test can assert, rather than a promise in a comment.

Token counts are estimates from character length. That is honest about being an
estimate; it is not a substitute for a real tokenizer and must not be used for
billing.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Callable, Sequence

from .ai_research import (
    AbstentionReason,
    AnalysisState,
    AIResearchProvider,
    ProviderRequest,
    ProviderResponse,
    ResearchAnalysis,
    assert_no_probability_claims,
    redact_secrets,
)

__all__ = [
    "OFFLINE_PROVIDER_NAME",
    "OFFLINE_MODEL_NAME",
    "OFFLINE_LABEL",
    "AiBudget",
    "BudgetExceeded",
    "BudgetMeter",
    "OfflineAIStage0",
    "OfflineCallRecord",
    "OfflineCallStatus",
    "OfflineFakeProvider",
    "PromptInjectionRefused",
    "estimate_tokens",
    "safe_request",
]

#: Recorded in every audit entry so an offline result can never be mistaken for
#: a real provider's output at a later reading of the log.
OFFLINE_LABEL = "offline-simulated"

OFFLINE_PROVIDER_NAME = "offline-fake"
OFFLINE_MODEL_NAME = "offline-fake-stage0-v1"

#: Evidence and event IDs are *references*, not prose. Restricting them to a
#: character class is what stops an injection payload riding in a field the
#: prompt renderer assumes is inert.
_REFERENCE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")

#: Markers that have no legitimate place inside a research question. Their
#: presence is refused rather than stripped: a caller that sent one has a bug,
#: and quietly deleting it hides the bug while leaving the intent intact.
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "system:",
    "assistant:",
    "<|im_start|>",
    "<|im_end|>",
    "developer message",
    "you are now",
    "new instructions",
    "override your",
    "act as",
)

_UNTRUSTED_OPEN = "<<<UNTRUSTED_QUESTION>>>"
_UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_QUESTION>>>"


class PromptInjectionRefused(ValueError):
    """A request carried content that has no place in a research reference."""


class BudgetExceeded(RuntimeError):
    """A budget limit was reached. The call was refused, not truncated."""


class OfflineCallStatus(str, Enum):
    """Outcome of one Stage 0 call."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    TIMED_OUT = "timed_out"
    REFUSED = "refused"
    BUDGET_REFUSED = "budget_refused"
    FAILED = "failed"


def estimate_tokens(text: str) -> int:
    """A character-based token estimate.

    Deliberately crude and deliberately labelled an estimate. Roughly four
    characters per token is the common rule of thumb; it is used for budget
    *control*, where being approximately right is enough, and must not be
    mistaken for billing.
    """

    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


# ---------------------------------------------------------------------------
# Injection boundary
# ---------------------------------------------------------------------------


def _check_reference(value: str, field_name: str) -> str:
    if not _REFERENCE_ID.match(value):
        raise PromptInjectionRefused(
            f"{field_name} {value!r} is not a plain reference identifier"
        )
    return value


def safe_request(request: ProviderRequest) -> ProviderRequest:
    """Return a request whose fields are safe to render into a prompt.

    Structural markers inside ``question`` are neutralised rather than removed,
    so the change is visible to a reader instead of silently altering what was
    asked.
    """

    for evidence_id in request.evidence_ids:
        _check_reference(evidence_id, "evidence_id")
    for event_id in request.event_ids:
        _check_reference(event_id, "event_id")

    question = request.question
    lowered = question.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lowered:
            raise PromptInjectionRefused(
                f"question contains the structural marker {marker!r}"
            )

    if "\x00" in question:
        raise PromptInjectionRefused("question contains a null byte")

    # Defensive re-delimiting: even with markers rejected, a caller could
    # supply the closing delimiter itself.
    if _UNTRUSTED_OPEN in question or _UNTRUSTED_CLOSE in question:
        raise PromptInjectionRefused("question contains a trust delimiter")

    return ProviderRequest(
        instrument_id=_check_reference(request.instrument_id, "instrument_id"),
        timeframe=_check_reference(request.timeframe, "timeframe"),
        market_type=_check_reference(request.market_type, "market_type"),
        question=question.replace("\n", " "),
        evidence_ids=tuple(request.evidence_ids),
        event_ids=tuple(request.event_ids),
        as_of=request.as_of,
        max_output_tokens=request.max_output_tokens,
    )


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AiBudget:
    """Limits applied *before* a call is made."""

    max_calls: int = 20
    max_input_tokens: int = 20_000
    max_output_tokens: int = 8_000
    max_latency_ms: int = 30_000

    def __post_init__(self) -> None:
        for name in (
            "max_calls",
            "max_input_tokens",
            "max_output_tokens",
            "max_latency_ms",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass
class BudgetMeter:
    """Running consumption against an :class:`AiBudget`."""

    budget: AiBudget = field(default_factory=AiBudget)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    #: Serialises check-and-consume. A budget read and written without one is
    #: not a limit: concurrent callers all read the same headroom and all admit.
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def _limit_reason(
        self, *, input_tokens: int, output_tokens: int, latency_ms: int
    ) -> str | None:
        """Which limit this request would break. Pure; assumes the lock."""

        if self.calls + 1 > self.budget.max_calls:
            return "max_calls"
        if self.input_tokens + input_tokens > self.budget.max_input_tokens:
            return "max_input_tokens"
        if self.output_tokens + output_tokens > self.budget.max_output_tokens:
            return "max_output_tokens"
        if latency_ms > self.budget.max_latency_ms:
            return "max_latency_ms"
        return None

    def would_exceed(
        self, *, input_tokens: int, output_tokens: int, latency_ms: int
    ) -> str | None:
        """Advisory: which limit this request would break if admitted.

        Reported for inspection only. Do **not** gate a dispatch on this and
        charge separately -- see :meth:`reserve` for why that is not a limit.
        """

        with self._lock:
            return self._limit_reason(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )

    def reserve(
        self, *, input_tokens: int, output_tokens: int, latency_ms: int
    ) -> str | None:
        """Atomically check the budget and consume one call slot.

        Returns ``None`` if the call is admitted, or the name of the limit that
        refused it. The check and the consumption happen in one critical
        section; splitting them is what let six concurrent callers each observe
        one remaining slot under a two-call budget and all dispatch.

        The slot is consumed before the provider is contacted, so a provider
        that faults or overruns is still counted -- a budget that only counted
        successes would not bound the case a caller is least likely to be
        watching. Refusals consume nothing, because nothing was attempted.

        The critical section covers only the arithmetic above. No provider work
        happens under this lock, so the reservation never serialises a slow
        call behind another.
        """

        with self._lock:
            reason = self._limit_reason(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
            if reason is not None:
                return reason
            self.calls += 1
            return None

    def begin_call(self) -> None:
        """Count one dispatch to the provider.

        Retained for callers that reserve elsewhere. Prefer :meth:`reserve`,
        which makes the check and the count a single operation.
        """

        with self._lock:
            self.calls += 1

    def charge(
        self, *, input_tokens: int, output_tokens: int, latency_ms: int = 0
    ) -> None:
        """Record measured usage for a call that was already reserved.

        Token accounting is separate from the call count because a failed call
        has no measured token usage; inventing one would make the ledger
        fiction.
        """

        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "max_calls": self.budget.max_calls,
            "max_input_tokens": self.budget.max_input_tokens,
            "max_output_tokens": self.budget.max_output_tokens,
        }


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OfflineCallRecord:
    """One auditable Stage 0 call.

    ``work_abandoned`` is the field that matters most. When a call times out,
    the deadline was honoured but the underlying work was not stopped, and a
    log that omits this would let a later reader assume the work had ceased.
    """

    call_id: str
    status: OfflineCallStatus
    provider_name: str
    model_name: str | None
    instrument_id: str
    timeframe: str
    market_type: str
    started_at: datetime
    finished_at: datetime
    latency_ms: int
    deadline_seconds: float
    work_abandoned: bool
    input_tokens: int | None
    output_tokens: int | None
    analysis_id: str | None
    redaction_applied: bool
    failure_detail: str | None
    offline_label: str = OFFLINE_LABEL

    @property
    def is_offline(self) -> bool:
        return self.offline_label == OFFLINE_LABEL

    def as_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "status": self.status.value,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "instrument_id": self.instrument_id,
            "timeframe": self.timeframe,
            "market_type": self.market_type,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "latency_ms": self.latency_ms,
            "deadline_seconds": self.deadline_seconds,
            "work_abandoned": self.work_abandoned,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "analysis_id": self.analysis_id,
            "redaction_applied": self.redaction_applied,
            "failure_detail": self.failure_detail,
            "offline_label": self.offline_label,
        }


# ---------------------------------------------------------------------------
# The provider
# ---------------------------------------------------------------------------


class OfflineFakeProvider:
    """A deterministic provider that never leaves the process.

    Behaviour is scripted rather than random so that a test can provoke exactly
    the conditions it needs to cover -- a timeout, a provider fault, an
    abstention -- instead of waiting for one to occur by chance.
    """

    name = OFFLINE_PROVIDER_NAME

    def __init__(
        self,
        *,
        delay_seconds: float = 0.0,
        raise_error: BaseException | None = None,
        force_abstain: bool = False,
        truncate: bool = False,
    ) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        self._delay = delay_seconds
        self._raise = raise_error
        self._force_abstain = force_abstain
        self._truncate = truncate
        self.calls: list[str] = []

    def is_configured(self) -> bool:
        """True: this provider needs no key, no quota and no network."""

        return True

    def analyse(
        self,
        request: ProviderRequest,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> ProviderResponse:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        started = time.perf_counter()
        self.calls.append(request.instrument_id)

        if self._delay:
            # Deliberately uninterruptible: this is the late-work case the
            # runner must handle without trusting it.
            time.sleep(self._delay)

        if self._raise is not None:
            raise self._raise

        text = self._render(request)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return ProviderResponse(
            provider_name=OFFLINE_PROVIDER_NAME,
            model_name=OFFLINE_MODEL_NAME,
            raw_text=text,
            retrieved_at=datetime.now(timezone.utc),
            latency_ms=elapsed_ms,
            input_tokens=estimate_tokens(request.to_prompt()),
            output_tokens=estimate_tokens(text),
            redacted=True,
            finish_reason="length" if self._truncate else "stop",
        )

    @staticmethod
    def _render(request: ProviderRequest) -> str:
        """Deterministic JSON. Identical request in, identical bytes out."""

        if request.evidence_ids:
            summary = (
                f"Reviewed {len(request.evidence_ids)} evidence reference(s) for "
                f"{request.instrument_id} on the {request.timeframe} timeframe."
            )
            observations = (
                "The referenced evidence is the only material offered for review.",
                "No market data was supplied to this provider, and none was assumed.",
            )
        else:
            summary = f"No evidence was supplied for {request.instrument_id}."
            observations = ("The question cannot be assessed without evidence.",)

        payload = {
            "state": "abstained" if not request.evidence_ids else "complete",
            "summary": summary,
            "observations": list(observations),
            "limitations": [
                "Generated offline by a deterministic stand-in; not model output.",
                "No network access and no external data were used.",
            ],
            "abstention_reason": (
                None if request.evidence_ids else "insufficient_evidence"
            ),
            "abstention_detail": (
                None if request.evidence_ids else "No evidence references supplied."
            ),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def deterministic_digest(self, request: ProviderRequest) -> str:
        """Stable identity for a request, useful for asserting reproducibility."""

        canonical = json.dumps(
            {
                "instrument_id": request.instrument_id,
                "timeframe": request.timeframe,
                "market_type": request.market_type,
                "question": request.question,
                "evidence_ids": list(request.evidence_ids),
                "event_ids": list(request.event_ids),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Stage 0
# ---------------------------------------------------------------------------


@dataclass
class OfflineAIStage0:
    """The offline Stage 0 entry point.

    Every exit -- success, abstention, refusal, timeout, fault -- produces both
    an analysis and an audit record. There is no path that returns an analysis
    without leaving a trace, and no path that returns a fabricated success.
    """

    provider: OfflineFakeProvider = field(default_factory=OfflineFakeProvider)
    budget: AiBudget = field(default_factory=AiBudget)
    meter: BudgetMeter = field(default_factory=BudgetMeter)
    secrets: tuple[str, ...] = ()
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    log: list[OfflineCallRecord] = field(default_factory=list)

    def _next_call_id(self) -> str:
        """A unique, monotonic id.

        Deriving this from ``len(log)`` is not safe: two calls finishing at the
        same moment read the same length and are issued the same id, which is
        exactly when an ambiguous audit entry does the most damage.
        """

        with self._lock:
            self._call_sequence += 1
            return f"call-{self._call_sequence:04d}"

    #: Serialises id allocation and log appends so concurrent callers cannot
    #: collide or interleave. Callers may drive one stage from several threads.
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )
    _call_sequence: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        # The meter is constructed from the budget unless one was injected.
        if self.meter.budget != self.budget:
            self.meter = BudgetMeter(budget=self.budget)

    # -- helpers ---------------------------------------------------------

    def _abstention(
        self,
        request: ProviderRequest,
        reason: AbstentionReason,
        detail: str,
        *,
        provider_name: str,
        model_name: str | None,
        analysis_id: str,
    ) -> ResearchAnalysis:
        now = self.now_fn()
        return ResearchAnalysis(
            analysis_id=analysis_id,
            instrument_id=request.instrument_id,
            timeframe=request.timeframe,
            market_type=request.market_type,
            analysed_at=now,
            state=AnalysisState.ABSTAINED,
            provider_name=provider_name,
            model_name=model_name,
            evidence_ids=tuple(request.evidence_ids),
            event_ids=tuple(request.event_ids),
            limitations=(detail, f"{OFFLINE_LABEL}: {OFFLINE_PROVIDER_NAME}"),
            abstention_reason=reason,
            abstention_detail=detail,
        )

    def _analysis_id(self, request: ProviderRequest) -> str:
        """A stable id for this request under this provider.

        Prefers a provider-supplied digest so the offline fake keeps its exact
        identifier, and falls back to hashing the request itself for any other
        provider. Hard-coding the fake's method here would have made this
        stage unusable for a real adapter, which is the coupling that invites
        a second, parallel runner.
        """

        supplied = getattr(self.provider, "deterministic_digest", None)
        if callable(supplied):
            digest = supplied(request)
        else:
            import hashlib
            import json

            canonical = json.dumps(
                {
                    "provider": self.provider.name,
                    "instrument_id": request.instrument_id,
                    "timeframe": request.timeframe,
                    "market_type": request.market_type,
                    "question": request.question,
                    "evidence_ids": list(request.evidence_ids),
                    "event_ids": list(request.event_ids),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"offline-{digest[:16]}"

    def _redact(self, detail: str | None) -> tuple[str | None, bool]:
        if detail is None:
            return None, False
        cleaned, changed = redact_secrets(detail, self.secrets)
        return cleaned, changed

    def _record(
        self,
        *,
        request: ProviderRequest,
        status: OfflineCallStatus,
        started: datetime,
        finished: datetime,
        latency_ms: int,
        deadline_seconds: float,
        work_abandoned: bool,
        input_tokens: int | None,
        output_tokens: int | None,
        analysis_id: str | None,
        failure_detail: str | None,
        redaction_applied: bool,
    ) -> OfflineCallRecord:
        detail, redacted = self._redact(failure_detail)
        record = OfflineCallRecord(
            call_id=self._next_call_id(),
            status=status,
            provider_name=self.provider.name,
            model_name=OFFLINE_MODEL_NAME,
            instrument_id=request.instrument_id,
            timeframe=request.timeframe,
            market_type=request.market_type,
            started_at=started,
            finished_at=finished,
            latency_ms=latency_ms,
            deadline_seconds=deadline_seconds,
            work_abandoned=work_abandoned,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            analysis_id=analysis_id,
            redaction_applied=redaction_applied,
            failure_detail=detail,
        )
        with self._lock:
            self.log.append(record)
        return record

    # -- the call -------------------------------------------------------

    def run(
        self,
        request: ProviderRequest,
        *,
        timeout_seconds: float = 30.0,
    ) -> tuple[ResearchAnalysis, OfflineCallRecord]:
        """Run one Stage 0 analysis. Never raises for provider-side failure.

        Configuration errors from the caller still raise: a bad timeout is the
        caller's bug and must not be laundered into an abstention that looks
        like the model declining.
        """

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        started = self.now_fn()
        analysis_id = self._analysis_id(request)
        provider_name = self.provider.name

        try:
            safe = safe_request(request)
        except PromptInjectionRefused as exc:
            analysis = self._abstention(
                request,
                AbstentionReason.OUT_OF_SCOPE,
                f"refused: {exc}",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=request,
                status=OfflineCallStatus.REFUSED,
                started=started,
                finished=self.now_fn(),
                latency_ms=0,
                deadline_seconds=timeout_seconds,
                work_abandoned=False,
                input_tokens=None,
                output_tokens=None,
                analysis_id=analysis_id,
                failure_detail=str(exc),
                redaction_applied=False,
            )
            return analysis, record

        prompt = safe.to_prompt()
        estimated_input = estimate_tokens(prompt)
        # One critical section decides admission and consumes the slot. The
        # lock is released before the provider is contacted, so slow provider
        # work never serialises behind another caller's reservation.
        exceeded = self.meter.reserve(
            input_tokens=estimated_input,
            output_tokens=safe.max_output_tokens,
            latency_ms=int(timeout_seconds * 1000),
        )
        if exceeded is not None:
            analysis = self._abstention(
                safe,
                AbstentionReason.PROVIDER_UNAVAILABLE,
                f"budget refused: {exceeded}",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=safe,
                status=OfflineCallStatus.BUDGET_REFUSED,
                started=started,
                finished=self.now_fn(),
                latency_ms=0,
                deadline_seconds=timeout_seconds,
                work_abandoned=False,
                input_tokens=estimated_input,
                output_tokens=None,
                analysis_id=analysis_id,
                failure_detail=f"budget limit reached: {exceeded}",
                redaction_applied=False,
            )
            return analysis, record

        wall_start = time.perf_counter()
        late: list[ProviderResponse] = []
        response: ProviderResponse | None = None
        timed_out = False
        provider_error: BaseException | None = None

        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="offline-ai"
        )
        try:
            future = executor.submit(
                self.provider.analyse, safe, timeout_seconds=timeout_seconds
            )
            try:
                response = future.result(timeout=timeout_seconds)
            except FutureTimeout:
                timed_out = True
                # The deadline is honoured. The work is not stopped, so it is
                # recorded as abandoned and any value it eventually produces is
                # discarded here rather than read below.
                future.add_done_callback(lambda f: late.append(f))
            except Exception as exc:  # noqa: BLE001 - deliberate boundary
                # A provider fault is a *failure*, not an abstention and not a
                # crash. Letting it escape would let a caller mistake an outage
                # for the model declining to answer.
                provider_error: BaseException | None = exc
                future.add_done_callback(lambda f: late.append(f))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        latency_ms = int((time.perf_counter() - wall_start) * 1000)

        if timed_out:
            analysis = self._abstention(
                safe,
                AbstentionReason.PROVIDER_UNAVAILABLE,
                f"offline provider exceeded {timeout_seconds}s deadline; "
                "work abandoned and any late result discarded",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=safe,
                status=OfflineCallStatus.TIMED_OUT,
                started=started,
                finished=self.now_fn(),
                latency_ms=latency_ms,
                deadline_seconds=timeout_seconds,
                work_abandoned=True,
                input_tokens=estimated_input,
                output_tokens=None,
                analysis_id=analysis_id,
                failure_detail=f"deadline {timeout_seconds}s exceeded",
                redaction_applied=False,
            )
            return analysis, record

        if provider_error is not None:
            detail = f"{type(provider_error).__name__}: {provider_error}"
            analysis = self._abstention(
                safe,
                AbstentionReason.PROVIDER_UNAVAILABLE,
                "offline provider failed; the failure is recorded, not inferred",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=safe,
                status=OfflineCallStatus.FAILED,
                started=started,
                finished=self.now_fn(),
                latency_ms=latency_ms,
                deadline_seconds=timeout_seconds,
                # The provider returned an error; it did not overrun. Nothing
                # was abandoned, and recording otherwise would misdescribe a
                # finished call as one still in flight.
                work_abandoned=False,
                input_tokens=estimated_input,
                output_tokens=None,
                analysis_id=analysis_id,
                failure_detail=detail,
                redaction_applied=True,
            )
            return analysis, record

        if response is None:
            analysis = self._abstention(
                safe,
                AbstentionReason.PROVIDER_UNAVAILABLE,
                "offline provider produced no response",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=safe,
                status=OfflineCallStatus.FAILED,
                started=started,
                finished=self.now_fn(),
                latency_ms=latency_ms,
                deadline_seconds=timeout_seconds,
                work_abandoned=False,
                input_tokens=estimated_input,
                output_tokens=None,
                analysis_id=analysis_id,
                failure_detail="no response",
                redaction_applied=False,
            )
            return analysis, record

        try:
            analysis = self._to_analysis(response, safe, analysis_id)
        except ValueError as exc:
            analysis = self._abstention(
                safe,
                AbstentionReason.SCHEMA_INVALID,
                f"offline response rejected: {exc}",
                provider_name=provider_name,
                model_name=OFFLINE_MODEL_NAME,
                analysis_id=analysis_id,
            )
            record = self._record(
                request=safe,
                status=OfflineCallStatus.FAILED,
                started=started,
                finished=self.now_fn(),
                latency_ms=latency_ms,
                deadline_seconds=timeout_seconds,
                work_abandoned=False,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                analysis_id=analysis_id,
                failure_detail=str(exc),
                redaction_applied=response.redacted,
            )
            return analysis, record

        self.meter.charge(
            input_tokens=response.input_tokens or 0,
            output_tokens=response.output_tokens or 0,
            latency_ms=latency_ms,
        )
        record = self._record(
            request=safe,
            status=(
                OfflineCallStatus.COMPLETED
                if analysis.state is AnalysisState.COMPLETE
                else OfflineCallStatus.ABSTAINED
            ),
            started=started,
            finished=self.now_fn(),
            latency_ms=latency_ms,
            deadline_seconds=timeout_seconds,
            work_abandoned=False,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            analysis_id=analysis.analysis_id,
            failure_detail=(
                None
                if analysis.state is AnalysisState.COMPLETE
                else analysis.abstention_detail
            ),
            redaction_applied=response.redacted,
        )
        return analysis, record

    def _to_analysis(
        self,
        response: ProviderResponse,
        request: ProviderRequest,
        analysis_id: str,
    ) -> ResearchAnalysis:
        """Parse and validate. A malformed response is refused, not repaired."""

        if response.looks_truncated:
            raise ValueError("offline response was truncated")

        try:
            payload = json.loads(response.raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"response was not JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("response was not a JSON object")

        state = payload.get("state")
        if state not in ("complete", "abstained"):
            raise ValueError(f"unknown state {state!r}")

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary must be a non-empty string")

        # An injection payload that reached the model could otherwise smuggle
        # a probability claim through the summary. This is the last line.
        assert_no_probability_claims(summary)

        observations = payload.get("observations") or []
        limitations = payload.get("limitations") or []
        if not isinstance(observations, list) or not isinstance(limitations, list):
            raise ValueError("observations and limitations must be lists")
        for item in tuple(observations) + tuple(limitations):
            if not isinstance(item, str):
                raise ValueError("observations and limitations must be strings")
            assert_no_probability_claims(item)

        reason = payload.get("abstention_reason")
        if state == "abstained" and reason is None:
            raise ValueError("abstained response requires an abstention_reason")

        limitations = list(limitations)
        limitations.append(f"{OFFLINE_LABEL}: {response.provider_name}")

        return ResearchAnalysis(
            analysis_id=analysis_id,
            instrument_id=request.instrument_id,
            timeframe=request.timeframe,
            market_type=request.market_type,
            analysed_at=self.now_fn(),
            state=AnalysisState.COMPLETE
            if state == "complete"
            else AnalysisState.ABSTAINED,
            provider_name=response.provider_name,
            model_name=response.model_name,
            evidence_ids=tuple(request.evidence_ids),
            event_ids=tuple(request.event_ids),
            observations=tuple(observations),
            limitations=tuple(limitations),
            abstention_reason=AbstentionReason(reason) if reason else None,
            abstention_detail=payload.get("abstention_detail"),
        )