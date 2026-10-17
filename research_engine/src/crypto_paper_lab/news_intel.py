"""News and market-intelligence pipeline: ingestion, validation, advisory digest.

No live source is connected here, and none can be. A real connector needs
network access, credentials and source terms that this project has not verified
(Phase 47 recorded the official sources; Phase 53/54 corrected the licence
position). So this module does the part that can be done honestly and tested
offline: the schema, the validation, the deduplication, the staleness rules and
the injection boundary. A verified connector will slot in behind
:class:`NewsSource` and everything downstream keeps working.

Three rules shape the design.

**News is untrusted input.** A headline is text written by someone else. It is
classified, timestamped and reported -- never executed. :func:`scan_untrusted`
marks an item that carries instruction-like language so a consumer cannot pass
it onward as if it were a directive, and the digest records the flag rather
than acting on it.

**Nothing here predicts.** There is no sentiment score, no price forecast and
no "importance" number, because this project has no verified basis for any of
them. Sentiment arrives as an optional label the *caller* asserts about its own
data; this module validates the label's shape and never computes one.

**The digest is advisory.** :class:`NewsDigest` carries counts, freshness and
provenance. It contains no field that a strategy or execution policy could
consume, and :func:`news_intel_imports` exists so a test can prove it.
"""

from __future__ import annotations

import ast
import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "INSTRUCTION_MARKERS",
    "KNOWN_INSTRUMENTS",
    "NewsDigest",
    "NewsItem",
    "NewsRejected",
    "NewsSource",
    "SUPPORTED_MARKET_TYPES",
    "SYNTHETIC_PROVENANCE",
    "SyntheticNewsConnector",
    "FailingNewsConnector",
    "NewsUnavailable",
    "collect",
    "UntrustedClassification",
    "build_digest",
    "deduplicate",
    "news_intel_imports",
    "parse_item",
    "scan_untrusted",
    "split_by_freshness",
]


#: The only market type this pipeline accepts. Forex and derivatives are absent
#: because there is no validated feed or cost model for them here, and a feed
#: would imply a market the engine refuses.
SUPPORTED_MARKET_TYPES = frozenset({"crypto_spot"})

#: Instruments the registry recognises. Anything else is refused rather than
#: silently accepted, so a typo cannot become an unattributable item.
KNOWN_INSTRUMENTS = frozenset({"BTC/USDT", "ETH/USDT"})

#: Provenance values an item may declare. ``UNVERIFIED`` is allowed and marked:
#: a claim of sourcing is not the same as a verified licence, and the digest
#   carries the distinction rather than flattening it.
#: ``SYNTHETIC`` is material this project generated. It is a provenance
#: value in its own right so a demonstration can never be read as reporting.
KNOWN_PROVENANCE = frozenset(
    {"VERIFIED", "UNVERIFIED", "DERIVED", "SYNTHETIC"}
)

#: Language that indicates an item is trying to give instructions. Detection is
#: a flag for downstream consumers, never an automatic action.
INSTRUCTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disallow all previous",
    "disregard previous",
    "system:",
    "assistant:",
    "you must now",
    "new instructions",
    "execute the following",
    "place an order",
    "buy immediately",
    "sell immediately",
    "override the risk",
    "bypass the risk",
    "approve the research",
)

_REFERENCE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")

#: Maximum age before an item is reported stale. A hard ceiling: an item older
#: than this is not deleted, because deleting evidence is worse than labelling
#: it, but it stops being presented as current.
DEFAULT_MAX_AGE = timedelta(hours=24)


class NewsRejected(ValueError):
    """A record could not become a news item.

    Carries a machine-readable ``reason`` so a caller can distinguish a
    malformed record from an unsupported market without parsing prose.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class UntrustedClassification(str, Enum):
    """Whether an item's text looks like an instruction rather than reporting."""

    CLEAN = "CLEAN"
    SUSPICIOUS = "SUSPICIOUS"


@dataclass(frozen=True)
class NewsItem:
    """One validated piece of reporting.

    Frozen so that an item validated once cannot be edited into something that
    no longer passed validation.
    """

    item_id: str
    source: str
    published_at: datetime
    headline: str
    summary: str
    instruments: tuple[str, ...]
    market_types: tuple[str, ...]
    provenance: str
    #: Optional caller-asserted sentiment label. Never computed here.
    sentiment_label: str | None = None
    provenance_note: str = ""

    @property
    def fingerprint(self) -> str:
        """Stable identity for deduplication.

        Based on the normalised headline and source rather than the supplied
        id, because the same story re-published under a second id must still
        collapse to one item.
        """

        canonical = "|".join(
            (
                self.source.strip().lower(),
                re.sub(r"\W+", " ", self.headline.lower()).strip(),
            )
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_record(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "headline": self.headline,
            "summary": self.summary,
            "instruments": list(self.instruments),
            "market_types": list(self.market_types),
            "provenance": self.provenance,
            "provenance_note": self.provenance_note,
            "sentiment_label": self.sentiment_label,
        }


def parse_item(record: dict[str, Any]) -> NewsItem:
    """Validate one raw record into a :class:`NewsItem`, or refuse it.

    Every field is checked. The point of a validated schema here is that a
    malformed or out-of-scope record is refused at the boundary instead of
    reaching a consumer that would have to defend against it.
    """

    if not isinstance(record, dict):
        raise NewsRejected("malformed_record", "record was not an object")

    item_id = str(record.get("item_id", "")).strip()
    if not item_id or not _REFERENCE.match(item_id):
        raise NewsRejected("bad_item_id", repr(record.get("item_id")))

    source = str(record.get("source", "")).strip()
    if not source:
        raise NewsRejected("missing_source", item_id)

    published = record.get("published_at")
    if not isinstance(published, datetime):
        raise NewsRejected("bad_timestamp", item_id)
    if published.tzinfo is None:
        raise NewsRejected("naive_timestamp", item_id)
    published = published.astimezone(timezone.utc)

    headline = str(record.get("headline", "")).strip()
    if not headline:
        raise NewsRejected("empty_headline", item_id)

    summary = str(record.get("summary", "")).strip()

    instruments = record.get("instruments") or ()
    if not isinstance(instruments, Sequence) or isinstance(instruments, (str, bytes)):
        raise NewsRejected("bad_instruments", item_id)
    unknown = [i for i in instruments if i not in KNOWN_INSTRUMENTS]
    if unknown:
        raise NewsRejected("unknown_instrument", f"{item_id}: {unknown}")
    if not instruments:
        raise NewsRejected("missing_instrument", item_id)

    market_types = record.get("market_types") or ("crypto_spot",)
    if not isinstance(market_types, Sequence) or isinstance(market_types, (str, bytes)):
        raise NewsRejected("bad_market_types", item_id)
    blocked = [m for m in market_types if m not in SUPPORTED_MARKET_TYPES]
    if blocked:
        raise NewsRejected("unsupported_market", f"{item_id}: {blocked}")

    provenance = str(record.get("provenance", "")).strip()
    if provenance not in KNOWN_PROVENANCE:
        raise NewsRejected("bad_provenance", f"{item_id}: {provenance!r}")

    sentiment = record.get("sentiment_label")
    if sentiment is not None and not isinstance(sentiment, str):
        raise NewsRejected("bad_sentiment_label", item_id)

    return NewsItem(
        item_id=item_id,
        source=source,
        published_at=published,
        headline=headline,
        summary=summary,
        instruments=tuple(instruments),
        market_types=tuple(market_types),
        provenance=provenance,
        sentiment_label=sentiment,
        provenance_note=str(record.get("provenance_note", "")).strip(),
    )


def deduplicate(items: Iterable[NewsItem]) -> list[NewsItem]:
    """Collapse items that are the same reporting.

    Two records with the same id, or the same source and normalised headline,
    are one story. The earliest publication is kept, because a later copy of an
    older story is not newer information.
    """

    best: dict[str, NewsItem] = {}
    for item in items:
        key = item.fingerprint
        current = best.get(key)
        if current is None or item.published_at < current.published_at:
            best[key] = item
    return sorted(best.values(), key=lambda i: (i.published_at, i.item_id))


def split_by_freshness(
    items: Iterable[NewsItem],
    *,
    now: datetime,
    max_age: timedelta = DEFAULT_MAX_AGE,
) -> tuple[list[NewsItem], list[NewsItem]]:
    """Split into ``(fresh, stale)``.

    Nothing is discarded. A stale item is evidence too, and dropping it would
    make an apparent absence of news out of a recorder that simply stopped.
    """

    if now.tzinfo is None:
        raise NewsRejected("naive_timestamp", "now must be timezone-aware")
    cutoff = now - max_age
    fresh, stale = [], []
    for item in items:
        (fresh if item.published_at >= cutoff else stale).append(item)
    return fresh, stale


def scan_untrusted(item: NewsItem) -> UntrustedClassification:
    """Classify an item's text as reporting or as instruction-like.

    A flag only. The caller decides what to do; this function never acts, and
    never removes content, so the evidence survives either way.
    """

    haystack = f"{item.headline}\n{item.summary}".lower()
    for marker in INSTRUCTION_MARKERS:
        if marker in haystack:
            return UntrustedClassification.SUSPICIOUS
    return UntrustedClassification.CLEAN


class NewsSource(Protocol):
    """The seam a verified connector would implement.

    Nothing in this repository implements it, because every candidate needs
    network access and licence terms that are not settled here. The protocol
    exists so the pipeline is complete without pretending a feed exists.
    """

    name: str

    def fetch(self, *, since: datetime) -> list[dict[str, Any]]:
        """Return raw records published at or after ``since``.

        Implementations must return plain records; validation is this module's
        job, not theirs.
        """
        ...


#: Provenance value reserved for material this project generated itself.
#: Distinct from a claimed source: a reader must be able to tell generated
#: fixtures from reporting without reading the headline.
SYNTHETIC_PROVENANCE = "SYNTHETIC"


@dataclass(frozen=True)
class SyntheticNewsConnector:
    """A deterministic in-process source, for tests and demonstrations.

    Not a live connector and never one. It returns records it was constructed
    with, so a test can provoke exactly the conditions it needs -- a duplicate,
    a stale item, a malformed timestamp, an injected instruction -- without a
    network and without inventing reporting.

    Every item it emits is stamped ``SYNTHETIC`` so a demonstration cannot be
    mistaken for a feed. It refuses to be labelled anything else.
    """

    name: str
    records: tuple[dict[str, Any], ...] = ()

    def fetch(self, *, since: datetime) -> list[dict[str, Any]]:
        """Return records at or after ``since``, tagged synthetic.

        Raises on a naive ``since`` rather than assuming a timezone: a
        connector that quietly accepted an ambiguous window would report a
        completeness it cannot justify.
        """

        if since.tzinfo is None:
            raise NewsRejected("naive_timestamp", f"{self.name} requires an aware since")
        out = []
        for record in self.records:
            published = record.get("published_at")
            # A record whose timestamp is not a datetime is passed on rather
            # than dropped: dropping it here would hide a malformed record,
            # and the pipeline reports rejected counts. Silence would read as
            # "this source had nothing", which is a different and wrong claim.
            if not isinstance(published, datetime) or published >= since:
                out.append({**record, "provenance": SYNTHETIC_PROVENANCE})
        return out


class FailingNewsConnector:
    """A source that cannot answer.

    Failure is a first-class outcome: the pipeline must be able to show that a
    source failed without inventing an empty result that reads as "no news".
    """

    def __init__(self, name: str, reason: str = "source unavailable") -> None:
        self.name = name
        self._reason = reason

    def fetch(self, *, since: datetime) -> list[dict[str, Any]]:
        raise NewsUnavailable(self.name, self._reason)


class NewsUnavailable(RuntimeError):
    """A named source could not answer."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


def collect(connector: Any, *, since: datetime, now: datetime) -> tuple[list[NewsItem], int]:
    """Fetch and validate through one connector.

    Returns ``(items, rejected_count)``. A record that fails validation is
    counted, not raised, so one malformed item cannot hide the rest of a
    batch -- but it is never silently folded in either.
    """

    accepted: list[NewsItem] = []
    rejected = 0
    for record in connector.fetch(since=since):
        try:
            accepted.append(parse_item(record))
        except NewsRejected:
            rejected += 1
    return accepted, rejected


@dataclass(frozen=True)
class NewsDigest:
    """An advisory summary. Contains nothing an execution path can consume."""

    generated_at: datetime
    fresh_count: int
    stale_count: int
    sources: tuple[str, ...]
    instruments: tuple[str, ...]
    unverified_count: int
    suspicious_count: int
    conflicting_sources: int
    #: Explicitly advisory. Present so a consumer cannot mistake the digest
    #: for a decision by naming it what it is.
    advisory_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "fresh_count": self.fresh_count,
            "stale_count": self.stale_count,
            "sources": list(self.sources),
            "instruments": list(self.instruments),
            "unverified_count": self.unverified_count,
            "suspicious_count": self.suspicious_count,
            "conflicting_sources": self.conflicting_sources,
            "advisory_only": self.advisory_only,
        }


def build_digest(
    items: Iterable[NewsItem],
    *,
    now: datetime,
    max_age: timedelta = DEFAULT_MAX_AGE,
) -> NewsDigest:
    """Summarise a batch. Counts and provenance only -- no scores, no advice."""

    deduped = deduplicate(items)
    fresh, stale = split_by_freshness(deduped, now=now, max_age=max_age)
    return NewsDigest(
        generated_at=now,
        fresh_count=len(fresh),
        stale_count=len(stale),
        sources=tuple(sorted({i.source for i in deduped})),
        instruments=tuple(sorted({x for i in deduped for x in i.instruments})),
        unverified_count=sum(1 for i in deduped if i.provenance == "UNVERIFIED"),
        suspicious_count=sum(
            1 for i in deduped if scan_untrusted(i) is UntrustedClassification.SUSPICIOUS
        ),
        conflicting_sources=_conflicting_sources(deduped),
    )


def _conflicting_sources(items: Sequence[NewsItem]) -> int:
    """Count instruments reported by more than one distinct source.

    This is a count of disagreement, not a resolution of it. The pipeline does
    not decide which report is right.
    """

    by_instrument: dict[str, set[str]] = {}
    for item in items:
        for instrument in item.instruments:
            by_instrument.setdefault(instrument, set()).add(item.source)
    return sum(1 for sources in by_instrument.values() if len(sources) > 1)


def news_intel_imports() -> set[str]:
    """Top-level imports of this module, for the architecture test."""

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found