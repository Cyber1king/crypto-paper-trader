"""Read-only research-status projections for the dashboard.

Phase 49. The dashboard needs to show what the research layer actually knows —
instruments, provenance, governance, provider status — and the API had no route
for any of it. Adding one here rather than fetching in the browser keeps a
single authority: **Python decides, the dashboard displays.**

Three projections, all strictly read-only:

* :func:`instruments` — the instrument registry with its real blockers.
* :func:`governance` — reservations and consumed windows, straight from the
  registry.
* :func:`providers` — AI provider status, honestly reporting that none are
  integrated.

Design rules, all of which the tests enforce:

* **No writes.** Nothing here mutates the registry, and no route accepts a body.
* **No credentials, ever.** Provider status reports *whether* a provider is
  integrated. It never reports, requests or derives a key, token or account id.
* **No secrets in errors.** A registry that cannot be read yields an honest
  ``unavailable`` state, not a path or a stack trace.
* **No inference.** An instrument is not approved because it is listed, and a
  reservation is not evaluated because it exists.
"""
from __future__ import annotations

from crypto_paper_lab.ai_providers import provider_status_report

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crypto_paper_lab.researchguard import (
    ResearchGuardError,
    load_registry,
    registry_path,
)

__all__ = [
    "ResearchProjectionError",
    "instruments_projection",
    "governance_projection",
    "providers_projection",
    "evidence_projection",
    "INSTRUMENT_EDIT_STATUSES",
]


class ResearchProjectionError(RuntimeError):
    """The research registry could not be projected for display.

    Raised rather than swallowed: a dashboard that silently shows an empty
    instrument list when the registry is unreadable would misrepresent blocked
    instruments as absent ones.
    """


#: Statuses the dashboard may render for an instrument.
#:
#: Only four, and each means something specific. ``RESEARCH_CONSUMED`` is
#: distinct from blocked: a BTC window is spent, which is not the same as EUR/USD
#: being unusable.
INSTRUMENT_EDIT_STATUSES = (
    "NOT_APPROVED",
    "DATA_VERIFIED_NOT_RESEARCH_APPROVED",
    "PREREGISTERED_NOT_APPROVED",
    "RESEARCH_APPROVED",
    "RESEARCH_CONSUMED",
    "BLOCKED_WRONG_DATA_TYPE",
)


def _read_registry() -> dict[str, Any]:
    """Load the registry, converting any failure into an honest refusal."""

    try:
        return load_registry()
    except (ResearchGuardError, Exception) as exc:  # noqa: B014
        # The message names the condition, never the value of a secret, and the
        # caller turns this into an ``unavailable`` state.
        raise ResearchProjectionError(
            f"research registry is unavailable: {type(exc).__name__}"
        ) from exc


@dataclass(frozen=True)
class InstrumentView:
    """One instrument as the dashboard may display it.

    Carries the *blocker* rather than a bare status, because "EUR/USD is blocked"
    without a reason is not actionable and invites the reader to guess.
    """

    instrument_id: str
    market_type: str
    venue: str | None
    source_provider: str | None
    timeframe: str | None
    timeframes_available: tuple[str, ...]
    volume_semantics: str | None
    timestamp_convention: str | None
    provenance_grade: str | None
    licence_knowledge: str | None
    bid_ask_available: bool | None
    research_approval: str
    blocked: bool
    blocker: str | None
    evaluation_supported: bool

    def as_record(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "market_type": self.market_type,
            "venue": self.venue,
            "source_provider": self.source_provider,
            "timeframe": self.timeframe,
            "timeframes_available": list(self.timeframes_available),
            "volume_semantics": self.volume_semantics,
            "timestamp_convention": self.timestamp_convention,
            "provenance_grade": self.provenance_grade,
            "licence_knowledge": self.licence_knowledge,
            "bid_ask_available": self.bid_ask_available,
            "research_approval": self.research_approval,
            "blocked": self.blocked,
            "blocker": self.blocker,
            "evaluation_supported": self.evaluation_supported,
        }


@dataclass(frozen=True)
class ReservationView:
    """One evaluation window and its real state."""

    reservation_id: str
    instrument_id: str
    dataset_sha256: str
    timeframe: str
    warmup_first: str | None
    warmup_last: str | None
    evaluation_first: str | None
    evaluation_last: str | None
    evaluation_bars: int | None
    status: str
    used: bool
    preregistration_id: str | None
    note: str | None

    @property
    def state(self) -> str:
        """A single word the dashboard can render unambiguously.

        Deliberately derived, never stored: ``RESERVED``, ``USED``,
        ``CONSUMED`` or ``UNREGISTERED``. Deriving it here means a registry edit
        cannot leave a stale label behind.
        """

        if self.used or self.status.upper() == "USED":
            return "USED"
        if self.status.upper() == "RESERVED":
            return "RESERVED"
        return self.status.upper()

    @property
    def evaluated(self) -> bool:
        """Whether this window has produced a result.

        False for a reserved window regardless of anything else. The dashboard
        must never be able to render "evaluated" for ETH 2026.
        """

        return False

    def as_record(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "instrument_id": self.instrument_id,
            "dataset_sha256": self.dataset_sha256,
            "timeframe": self.timeframe,
            "warmup_first": self.warmup_first,
            "warmup_last": self.warmup_last,
            "evaluation_first": self.evaluation_first,
            "evaluation_last": self.evaluation_last,
            "evaluation_bars": self.evaluation_bars,
            "status": self.status,
            "state": self.state,
            "used": self.used,
            "preregistration_id": self.preregistration_id,
            "note": self.note,
            "evaluated": self.evaluated,
        }


@dataclass(frozen=True)
class ConsumedWindowView:
    """A window that has already been spent."""

    instrument_id: str
    dataset_sha256: str
    timeframe: str
    evaluation_first: str | None
    evaluation_last: str | None
    evaluation_bars: int | None
    consumed_on: str | None
    outcome: str | None
    preregistration_id: str | None
    note: str | None

    @property
    def retired(self) -> bool:
        """Always true. A consumed window is permanently retired."""

        return True

    def as_record(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "dataset_sha256": self.dataset_sha256,
            "timeframe": self.timeframe,
            "evaluation_first": self.evaluation_first,
            "evaluation_last": self.evaluation_last,
            "evaluation_bars": self.evaluation_bars,
            "consumed_on": self.consumed_on,
            "outcome": self.outcome,
            "preregistration_id": self.preregistration_id,
            "note": self.note,
            "retired": self.retired,
        }


@dataclass(frozen=True)
class ProviderView:
    """Status of one AI research provider.

    ``integration_state`` is the field that matters and the reason this module
    exists: it distinguishes *not implemented* from *configured but failing*,
    which a boolean would conflate.

    There is deliberately **no** field reporting whether a key is present. This
    module never reads the environment, so it could not answer honestly: a
    hardcoded ``False`` would be a fabricated observation rather than a fact.
    Absence of a key is a deployment detail, and the correct way to express it
    is to not claim to know it.
    """

    provider: str
    integration_state: str
    documentation_verified: bool
    detail: str

    def as_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "integration_state": self.integration_state,
            "documentation_verified": self.documentation_verified,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class GovernanceView:
    """Reservation and consumption state, as the backend sees it."""

    reservations: tuple[ReservationView, ...] = field(default_factory=tuple)
    consumed_windows: tuple[ConsumedWindowView, ...] = field(default_factory=tuple)
    registry_version: Any = None

    def as_record(self) -> dict[str, Any]:
        return {
            "reservations": [r.as_record() for r in self.reservations],
            "consumed_windows": [c.as_record() for c in self.consumed_windows],
            "registry_version": self.registry_version,
        }


def _optional(value: Any) -> Any:
    """Convert a missing registry value to ``None`` rather than echoing ""."""

    text = str(value or "").strip()
    return text or None


def instruments_projection() -> list[InstrumentView]:
    """Project the instrument registry for display.

    Raises :class:`ResearchProjectionError` when the registry cannot be read,
    so an unreadable registry is never rendered as an empty instrument list.
    """

    registry = _read_registry()
    views: list[InstrumentView] = []

    for entry in registry["instruments"]:
        if not isinstance(entry, dict):
            continue
        approval = _optional(entry.get("research_approval")) or "NOT_APPROVED"
        blocked = approval == "BLOCKED_WRONG_DATA_TYPE"
        available = entry.get("timeframes_available")

        views.append(
            InstrumentView(
                instrument_id=str(entry.get("instrument_id", "")),
                market_type=str(entry.get("market_type", "")),
                venue=_optional(entry.get("venue")),
                source_provider=_optional(entry.get("source_provider")),
                timeframe=_optional(entry.get("timeframe")),
                timeframes_available=tuple(available) if isinstance(available, list) else (),
                volume_semantics=_optional(entry.get("volume_semantics")),
                timestamp_convention=_optional(entry.get("timestamp_convention")),
                provenance_grade=_optional(entry.get("provenance_grade")),
                licence_knowledge=_optional(entry.get("licence_knowledge")),
                bid_ask_available=(
                    entry.get("bid_ask_available")
                    if isinstance(entry.get("bid_ask_available"), bool)
                    else None
                ),
                research_approval=approval,
                blocked=blocked,
                # A block without a stated reason is not actionable, so the
                # dashboard must never invent one.
                blocker=_optional(entry.get("blocker")),
                # Whether an evaluation could be run, which is NOT the same as
                # approval. Only a supported market type with usable timeframes.
                evaluation_supported=(
                    not blocked
                    and approval != "RESEARCH_CONSUMED"
                    and isinstance(available, list)
                    and bool(available)
                ),
            )
        )

    return views


def governance_projection() -> GovernanceView:
    """Project reservation and consumed-window state."""

    registry = _read_registry()

    reservations = tuple(
        ReservationView(
            reservation_id=str(entry.get("reservation_id", "")),
            instrument_id=str(entry.get("instrument_id", "")),
            dataset_sha256=str(entry.get("dataset_sha256", "")),
            timeframe=str(entry.get("timeframe", "")),
            warmup_first=_optional(entry.get("warmup_first")),
            warmup_last=_optional(entry.get("warmup_last")),
            evaluation_first=_optional(entry.get("evaluation_first")),
            evaluation_last=_optional(entry.get("evaluation_last")),
            evaluation_bars=(
                int(entry["evaluation_bars"])
                if isinstance(entry.get("evaluation_bars"), int)
                else None
            ),
            status=str(entry.get("status", "")),
            used=bool(entry.get("used", False)),
            preregistration_id=_optional(entry.get("preregistration_id")),
            note=_optional(entry.get("note")),
        )
        for entry in registry["reservations"]
        if isinstance(entry, dict)
    )

    consumed = tuple(
        ConsumedWindowView(
            instrument_id=str(entry.get("instrument_id", "")),
            dataset_sha256=str(entry.get("dataset_sha256", "")),
            timeframe=str(entry.get("timeframe", "")),
            evaluation_first=_optional(entry.get("evaluation_first")),
            evaluation_last=_optional(entry.get("evaluation_last")),
            evaluation_bars=(
                int(entry["evaluation_bars"])
                if isinstance(entry.get("evaluation_bars"), int)
                else None
            ),
            consumed_on=_optional(entry.get("consumed_on")),
            outcome=_optional(entry.get("outcome")),
            preregistration_id=_optional(entry.get("preregistration_id")),
            note=_optional(entry.get("note")),
        )
        for entry in registry["consumed_windows"]
        if isinstance(entry, dict)
    )

    return GovernanceView(
        reservations=reservations,
        consumed_windows=consumed,
        registry_version=registry.get("version"),
    )


#: Provider status, stated once and from verified fact.
#:
#: Phase 48 verified Anthropic's documentation and researched neither Kimi nor
#: DeepSeek. All three are NOT INTEGRATED. ``credential_configured`` is False
#: because no credential exists in this repository -- and this module never
#: inspects the environment to discover otherwise.
#: Provider status is sourced from the adapter registry rather than written out
#: here, so the API cannot report a state the code does not hold. Anthropic's
#: wire contract was verified in Phase 48 and an adapter now exists for it, so
#: calling it NOT_IMPLEMENTED would be inaccurate; Kimi and DeepSeek remain
#: unverified and say so.
_PROVIDER_STATUS = (
    ProviderView(
        provider="offline-simulated",
        integration_state="OFFLINE_SIMULATED",
        documentation_verified=True,
        detail=(
            "A deterministic in-process stand-in exists so the research "
            "plumbing can be exercised and tested without a key, a quota or a "
            "connection. It is not a model: it never leaves the process, makes "
            "no network call, and its output is labelled offline-simulated in "
            "every record it produces. It cannot influence trading, costs, "
            "configuration or governance state."
        ),
    ),
) + tuple(
    ProviderView(
        provider=row.provider,
        integration_state=row.status.value,
        documentation_verified=row.contract_verified,
        detail=row.detail,
    )
    for row in provider_status_report()
)


def providers_projection() -> list[ProviderView]:
    """Report provider integration status honestly.

    Returns a static, verified-from-source list. It performs **no** provider
    call, no health check, and no credential lookup — a status indicator must not
    generate network traffic or depend on a secret being present.
    """

    return list(_PROVIDER_STATUS)


def evidence_projection() -> dict[str, Any]:
    """Report that evidence ingestion is not implemented.

    Returned as a real response rather than a 404 so the dashboard can render an
    honest "unavailable" panel instead of an error boundary. No evidence is
    fabricated to fill it.
    """

    return {
        "available": False,
        "state": "CONNECTOR_NOT_IMPLEMENTED",
        "items": [],
        "events": [],
        # Separates what is built from what is missing, so the panel can say
        # "the pipeline exists, the source does not" rather than implying no
        # work has happened. Reports no news, because none is retrieved and
        # none is fabricated to fill the shape.
        "pipeline": {
            "schema_implemented": True,
            "validation_implemented": True,
            "deduplication_implemented": True,
            "staleness_rules_implemented": True,
            "injection_scan_implemented": True,
            "connector_implemented": False,
            "advisory_only": True,
            "detail": (
                "Ingestion, validation, deduplication, staleness and "
                "untrusted-text scanning are implemented and tested offline. "
                "No connector is implemented: every candidate source needs "
                "network access and licence terms this project has not "
                "verified."
            ),
        },
        "detail": (
            "No news or economic-calendar source is integrated. Phase 47 "
            "verified two official sources (ECB reference rates, BLS release "
            "schedule) and recorded their licensing terms, but no ingestion "
            "adapter exists. No evidence is displayed because none is "
            "retrieved."
        ),
        "sources_evaluated": [
            {
                "publisher": "European Central Bank",
                "kind": "forex_reference_rates",
                "documented": True,
                "usable_for_evaluation": False,
                "reason": (
                    "Daily reference fixings, not OHLC. The ECB states the "
                    "rates are for information only and discourages "
                    "transactional use."
                ),
            },
            {
                "publisher": "U.S. Bureau of Labor Statistics",
                "kind": "economic_release_calendar",
                "documented": True,
                "usable_for_evaluation": False,
                "reason": (
                    "Schedule is HTML; parsing it would be scraping. The BLS "
                    "JSON API covers series values, not the release schedule."
                ),
            },
        ],
    }