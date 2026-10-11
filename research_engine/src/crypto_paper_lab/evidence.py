"""Evidence records for news, economic events and sentiment.

Phase 47. This module defines *what a piece of evidence is* and *when it may be
used*. It fetches nothing, calls no provider, and holds no credentials.

The central discipline is that an evidence record must distinguish when a thing
was **published** from when this project **saw** it. Those two timestamps differ,
often by hours, and collapsing them is how stale news gets presented as current.

Three records live here:

* :class:`EvidenceItem` — a news report or similar claim.
* :class:`EconomicEvent` — a scheduled or unscheduled economic release.
* :class:`SentimentObservation` — a sentiment reading with explicit provenance.

None of them carries a score that implies a probability of profit. Sentiment in
particular is a *description of a reading*, not a forecast, and
:func:`assert_not_a_forecast` exists to keep it that way.

Nothing here invents a timestamp. A record with no publication time is
constructible but permanently unusable for freshness, and that is deliberate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable

__all__ = [
    "EvidenceError",
    "Freshness",
    "EventKind",
    "EvidenceItem",
    "EconomicEvent",
    "SentimentObservation",
    "EvidenceCluster",
    "assert_not_a_forecast",
    "EVIDENCE_KINDS",
    "FRESHNESS_THRESHOLDS",
]


class EvidenceError(ValueError):
    """Raised when an evidence record is malformed or internally contradictory."""


def _as_utc(moment: datetime, field_name: str) -> datetime:
    """Normalise to aware UTC, refusing naive input.

    A naive timestamp in an evidence record is ambiguous — it could be local,
    UTC, or a publisher's own convention — and ambiguity here would silently
    corrupt a freshness calculation. Refusing is the only safe option.
    """

    if moment.tzinfo is None:
        raise EvidenceError(
            f"{field_name} must be timezone-aware. A naive timestamp is "
            "ambiguous, and guessing its zone would corrupt the freshness "
            "calculation it feeds."
        )
    return moment.astimezone(timezone.utc)


class Freshness(str, Enum):
    """How current an item is relative to a stated reference time."""

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    UNDATED = "undated"


#: Age thresholds in hours. Deliberately explicit rather than tuned: these are
#: recording policy, not model parameters, and a reader should be able to see
#: and disagree with them.
FRESHNESS_THRESHOLDS = {
    Freshness.FRESH: 24.0,
    Freshness.STALE: 168.0,  # one week
}


class EventKind(str, Enum):
    """Scheduled versus unscheduled economic events."""

    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"


EVIDENCE_KINDS = (
    "news_article",
    "news_broadcast",
    "regulatory_notice",
    "exchange_notice",
    "central_bank_statement",
    "research_note",
    "aggregator_summary",
    "social_post",
)


@dataclass(frozen=True)
class EvidenceItem:
    """One piece of news or commentary, with its provenance kept intact.

    ``published_at`` is when the publisher says it was published.
    ``retrieved_at`` is when this project obtained it. They are separate fields
    because they are genuinely different facts, and a syndicated copy carries
    the *original* publication time while being retrieved much later.
    """

    evidence_id: str
    kind: str
    publisher: str
    canonical_url: str
    headline: str
    retrieved_at: datetime
    published_at: datetime | None = None
    instruments: tuple[str, ...] = ()
    summary: str | None = None
    licence_note: str | None = None
    attribution_required: bool = True
    cluster_id: str | None = None
    is_syndicated_copy: bool = False
    original_source_id: str | None = None
    source_credibility_note: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "kind", "publisher", "canonical_url", "headline"):
            if not str(getattr(self, name)).strip():
                raise EvidenceError(
                    f"{name} is required on an evidence record; an unattributed "
                    "item cannot be reviewed or cited."
                )

        if self.kind not in EVIDENCE_KINDS:
            raise EvidenceError(
                f"kind={self.kind!r} is not one of "
                + ", ".join(EVIDENCE_KINDS)
                + ". Declared explicitly so an aggregator is never mistaken for "
                "an original report."
            )

        if not str(self.canonical_url).startswith(("http://", "https://")):
            raise EvidenceError(
                f"canonical_url={self.canonical_url!r} is not an http(s) URL. A "
                "record that cannot be traced to a source cannot be cited."
            )

        object.__setattr__(
            self, "retrieved_at", _as_utc(self.retrieved_at, "retrieved_at")
        )
        if self.published_at is not None:
            object.__setattr__(
                self, "published_at", _as_utc(self.published_at, "published_at")
            )

        # A syndicated copy without its origin cannot be distinguished from an
        # original report, which is exactly the confusion this guards against.
        if self.is_syndicated_copy and not self.original_source_id:
            raise EvidenceError(
                "a syndicated copy must record original_source_id, or it is "
                "indistinguishable from original reporting"
            )

        if self.original_source_id and self.original_source_id == self.evidence_id:
            raise EvidenceError(
                "original_source_id must differ from evidence_id; a record "
                "cannot be its own source"
            )

    @property
    def age_hours(self) -> float | None:
        """Hours since publication, or ``None`` when undated.

        ``None`` is meaningful: an undated item cannot be aged, therefore cannot
        be shown to be fresh, therefore should not drive a decision.
        """

        if self.published_at is None:
            return None
        return (self.retrieved_at - self.published_at).total_seconds() / 3600.0

    def freshness(self, reference: datetime | None = None) -> Freshness:
        """Classify staleness at ``reference`` (defaults to retrieval time).

        Uses ``published_at`` when present, never ``retrieved_at``. Freshness
        means "how old is the claim", not "how long have we had it".
        """

        if self.published_at is None:
            return Freshness.UNDATED
        ref = _as_utc(
            reference or self.retrieved_at, "reference"
        )
        age = (ref - self.published_at).total_seconds() / 3600.0
        if age < 0:
            # Published in the future relative to reference: a clock-skew or
            # embargo problem, not something to silently accept.
            return Freshness.UNDATED
        if age <= FRESHNESS_THRESHOLDS[Freshness.FRESH]:
            return Freshness.FRESH
        if age <= FRESHNESS_THRESHOLDS[Freshness.STALE]:
            return Freshness.STALE
        return Freshness.EXPIRED

    def is_usable(self, reference: datetime | None = None) -> bool:
        """Whether this item may inform research at all.

        Expired or undated items are refused. A missing attribution is a
        licensing problem, not a formality, so it also refuses.
        """

        if self.attribution_required and not self.licence_note:
            return False
        return self.freshness(reference) in (Freshness.FRESH, Freshness.STALE)

    def as_record(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "publisher": self.publisher,
            "canonical_url": self.canonical_url,
            "headline": self.headline,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
            "retrieved_at": self.retrieved_at.isoformat(),
            "instruments": list(self.instruments),
            "summary": self.summary,
            "licence_note": self.licence_note,
            "attribution_required": self.attribution_required,
            "cluster_id": self.cluster_id,
            "is_syndicated_copy": self.is_syndicated_copy,
            "original_source_id": self.original_source_id,
            "source_credibility_note": self.source_credibility_note,
            "freshness": self.freshness().value,
        }


@dataclass(frozen=True)
class EconomicEvent:
    """A scheduled or unscheduled economic release.

    Actual, forecast and previous values are each optional and are ``None``
    unless genuinely supplied by the source. A release that has not happened has
    no actual; filling that field from context would be inventing a number that
    a reader could reasonably treat as data.
    """

    event_id: str
    name: str
    authority: str
    kind: EventKind
    scheduled_at: datetime | None
    retrieved_at: datetime
    timezone_note: str
    instruments: tuple[str, ...] = ()
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    unit: str | None = None
    revised: bool = False
    revision_note: str | None = None
    cancelled: bool = False
    postponement_note: str | None = None
    source_url: str | None = None
    values_source: str | None = None

    def __post_init__(self) -> None:
        for name in ("event_id", "name", "authority", "timezone_note"):
            if not str(getattr(self, name)).strip():
                raise EvidenceError(
                    f"{name} is required on an economic event; an unattributed "
                    "release cannot be cited."
                )

        if not isinstance(self.kind, EventKind):
            raise EvidenceError(
                f"kind must be an EventKind, got {type(self.kind).__name__}"
            )

        object.__setattr__(
            self, "retrieved_at", _as_utc(self.retrieved_at, "retrieved_at")
        )
        if self.scheduled_at is not None:
            object.__setattr__(
                self, "scheduled_at", _as_utc(self.scheduled_at, "scheduled_at")
            )

        # An unscheduled event has no announced time. Recording one would imply
        # a schedule that did not exist.
        if self.kind is EventKind.UNSCHEDULED and self.scheduled_at is not None:
            raise EvidenceError(
                "an unscheduled event must not carry scheduled_at; it implies "
                "an announced time that did not exist"
            )

        if self.cancelled and not self.postponement_note:
            raise EvidenceError(
                "a cancelled event must state why in postponement_note; a "
                "silent cancellation is indistinguishable from missing data"
            )

        if self.revised and not self.revision_note:
            raise EvidenceError(
                "a revised event must carry revision_note, so a reader can tell "
                "a revision from the original figure"
            )

        # A value may only be recorded when a source is named for it.
        if (self.actual is not None or self.forecast is not None) and not self.values_source:
            raise EvidenceError(
                "actual/forecast values require values_source. A number with no "
                "stated provenance is not evidence."
            )

    @property
    def has_occurred(self) -> bool:
        """True once the scheduled time has passed and no cancellation applies."""

        if self.kind is EventKind.UNSCHEDULED:
            return False
        if self.scheduled_at is None:
            return False
        if self.cancelled:
            return False
        return self.retrieved_at >= self.scheduled_at

    def as_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "authority": self.authority,
            "kind": self.kind.value,
            "scheduled_at": (
                self.scheduled_at.isoformat() if self.scheduled_at else None
            ),
            "retrieved_at": self.retrieved_at.isoformat(),
            "timezone_note": self.timezone_note,
            "instruments": list(self.instruments),
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "unit": self.unit,
            "revised": self.revised,
            "revision_note": self.revision_note,
            "cancelled": self.cancelled,
            "postponement_note": self.postponement_note,
            "source_url": self.source_url,
            "values_source": self.values_source,
            "has_occurred": self.has_occurred,
        }


@dataclass(frozen=True)
class SentimentObservation:
    """A sentiment reading, described rather than scored into a forecast.

    Deliberately has no ``probability`` or ``expected_return`` field. Sentiment
    sources publish indices with proprietary construction; this records *what
    was published and by whom*, not a number that could be misread as an edge.
    """

    observation_id: str
    instrument_id: str
    source_name: str
    observed_at: datetime
    retrieved_at: datetime
    value: float
    scale_min: float
    scale_max: float
    methodology_url: str | None = None
    methodology_note: str | None = None
    licence_note: str | None = None
    is_contrarian_index: bool = False

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "instrument_id", "source_name", "methodology_note"
        ):
            if not str(getattr(self, name)).strip():
                raise EvidenceError(
                    f"{name} is required on a sentiment observation. A reading "
                    "with no stated method is not interpretable."
                )

        object.__setattr__(
            self, "observed_at", _as_utc(self.observed_at, "observed_at")
        )
        object.__setattr__(
            self, "retrieved_at", _as_utc(self.retrieved_at, "retrieved_at")
        )

        if self.scale_min >= self.scale_max:
            raise EvidenceError(
                f"scale_min={self.scale_min} must be below scale_max="
                f"{self.scale_max}; an inverted scale cannot be interpreted"
            )

        if not (self.scale_min <= self.value <= self.scale_max):
            raise EvidenceError(
                f"value={self.value} lies outside the declared scale "
                f"[{self.scale_min}, {self.scale_max}]; refusing to record a "
                "reading whose scale contradicts its value"
            )

    @property
    def normalised(self) -> float:
        """Position within the scale, in ``[0, 1]``.

        A description of where a reading sits, **not** a probability. The
        distinction is documented in the Phase 47 sentiment-limits section.
        """

        span = self.scale_max - self.scale_min
        return (self.value - self.scale_min) / span

    def age_hours(self) -> float:
        return (self.retrieved_at - self.observed_at).total_seconds() / 3600.0

    def is_usable(self, reference: datetime | None = None, max_age_hours: float = 24.0) -> bool:
        ref = _as_utc(reference or self.retrieved_at, "reference")
        return 0 <= (ref - self.observed_at).total_seconds() / 3600.0 <= max_age_hours

    def as_record(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "instrument_id": self.instrument_id,
            "source_name": self.source_name,
            "observed_at": self.observed_at.isoformat(),
            "retrieved_at": self.retrieved_at.isoformat(),
            "value": self.value,
            "scale_min": self.scale_min,
            "scale_max": self.scale_max,
            "normalised": self.normalised,
            "methodology_url": self.methodology_url,
            "methodology_note": self.methodology_note,
            "licence_note": self.licence_note,
            "is_contrarian_index": self.is_contrarian_index,
            "usable": self.is_usable(),
        }


FORBIDDEN_FORECAST_FIELDS = (
    "probability",
    "win_rate",
    "expected_return",
    "edge",
    "confidence_score",
    "likely_up",
)


def assert_not_a_forecast(record: dict[str, Any]) -> None:
    """Refuse any record presenting sentiment as a forecast.

    The Phase 47 requirement is that sentiment not be treated as a probability
    of profitable trading. This is the enforcement point: a record carrying any
    of :data:`FORBIDDEN_FORECAST_FIELDS` is refused rather than reinterpreted.
    """

    present = [
        field
        for field in FORBIDDEN_FORECAST_FIELDS
        if field in record and record[field] is not None
    ]
    if present:
        raise EvidenceError(
            "record presents sentiment as a forecast; refusing field(s): "
            + ", ".join(present)
            + ". A sentiment reading describes a published measurement, not a "
            "probability of a profitable trade."
        )


@dataclass
class EvidenceCluster:
    """A set of items believed to cover the same underlying story.

    Clustering is a *claim*, not a fact: it is recorded so a reader can see that
    five articles were treated as one story rather than five independent
    confirmations. Counting clustered items as independent evidence would
    inflate apparent corroboration, which is a well-documented failure mode in
    news-driven analysis.
    """

    cluster_id: str
    representative_id: str
    members: list[str] = field(default_factory=list)
    conflicting_ids: list[str] = field(default_factory=list)
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not str(self.cluster_id).strip() or not str(self.representative_id).strip():
            raise EvidenceError(
                "cluster_id and representative_id are both required"
            )
        if self.representative_id in self.members:
            raise EvidenceError(
                "the representative must not also appear in members; a cluster "
                "is the representative *plus* its copies"
            )
        overlap = set(self.members) & set(self.conflicting_ids)
        if overlap:
            raise EvidenceError(
                "an item cannot be both a cluster member and a conflicting "
                f"report: {sorted(overlap)}"
            )

    @property
    def independent_count(self) -> int:
        """Distinct claims, which is the representative plus any conflicts.

        Not ``len(members) + 1``. Five syndicated copies of one wire story are
        one claim.
        """

        return 1 + len(self.conflicting_ids)

    def has_conflict(self) -> bool:
        return bool(self.conflicting_ids)

    def as_record(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "representative_id": self.representative_id,
            "members": list(self.members),
            "conflicting_ids": list(self.conflicting_ids),
            "rationale": self.rationale,
            "independent_count": self.independent_count,
            "has_conflict": self.has_conflict(),
        }


def conflicting_evidence(items: Iterable[EvidenceItem]) -> list[EvidenceCluster]:
    """Group items into clusters and report those holding a conflict.

    A convenience over :class:`EvidenceCluster`; grouping itself is a judgement
    call the caller supplies via ``cluster_id``.
    """

    grouped: dict[str, list[EvidenceItem]] = {}
    for item in items:
        if item.cluster_id:
            grouped.setdefault(item.cluster_id, []).append(item)

    clusters: list[EvidenceCluster] = []
    for cluster_id, members in grouped.items():
        # Deterministic representative: earliest published, then id. Not
        # "most popular" or "first retrieved", both of which would import a
        # provider's ranking into our reasoning.
        ordered = sorted(
            members,
            key=lambda i: (
                i.published_at or i.retrieved_at,
                i.evidence_id,
            ),
        )
        # A conflicting report is an *independent* claim, not a reproduction of
        # the representative, so it is listed in conflicting_ids rather than
        # members. Putting it in both would inflate independent_count while
        # claiming agreement.
        conflicting = [
            m.evidence_id
            for m in ordered[1:]
            if "conflict" in (m.source_credibility_note or "").lower()
        ]
        conflict_set = set(conflicting)
        clusters.append(
            EvidenceCluster(
                cluster_id=cluster_id,
                representative_id=ordered[0].evidence_id,
                members=[
                    m.evidence_id for m in ordered[1:]
                    if m.evidence_id not in conflict_set
                ],
                conflicting_ids=conflicting,
                rationale="grouped by declared cluster_id",
            )
        )
    return clusters


def evidence_age_band(age_hours: float | None) -> str:
    """Name an age band for reporting, without implying anything about importance."""

    if age_hours is None:
        return "undated"
    if age_hours < 0:
        return "future_dated"
    if age_hours <= FRESHNESS_THRESHOLDS[Freshness.FRESH]:
        return "fresh"
    if age_hours <= FRESHNESS_THRESHOLDS[Freshness.STALE]:
        return "stale"
    return "expired"


def staleness_window(reference: datetime, hours: float) -> datetime:
    """The oldest timestamp still considered current at ``reference``.

    Provided so a caller computes a cutoff explicitly rather than each
    implementing its own slightly different version.
    """

    return _as_utc(reference, "reference") - timedelta(hours=hours)