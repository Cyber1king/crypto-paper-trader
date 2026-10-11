"""Fail-closed research-integrity guards.

This module is the enforcement point for two concerns that were previously
documentation only:

1. **Evaluation-window reservation.** A reserved or consumed evaluation window
   must not be evaluated twice, and must not be evaluated outside its declared
   boundaries. A *consumed* window can never be reused. A *reserved* window may
   be evaluated exactly once, with metadata that matches its reservation
   byte for byte.

2. **Instrument identity.** A dataset for one instrument must never be silently
   labelled as another. ``StrategyConfig.asset`` is only a label -- nothing in the
   engine checked it. Evaluating a BTC-derived configuration against ETH data
   requires an explicit, recorded cross-asset authorization.

Design rules, all deliberate:

* **Fail closed.** A missing, unreadable or malformed registry raises. There is
  no permissive fallback and no "unknown means allowed" path.
* **Identity is the dataset hash, not a path.** A byte-identical copy has the
  same identity, so copying a file cannot evade a reservation.
* **Declare the range, or be refused.** If a dataset matches a reserved or
  consumed window, the run must declare an evaluation range matching that
  reservation. A caller cannot dodge the guard by passing ``evaluation_start
  =None`` and trading across the whole series.
* **No caller-supplied bypass.** There is deliberately no ``skip_guard`` flag on
  any function here.
* **A refusal is not persisted, by design.** This module records *outcomes*,
  not an attempt log: a successful consumption writes ``used``, ``used_on`` and
  ``used_preregistration_id``, and a refusal leaves the registry untouched. A
  refused attempt is therefore reported to the caller in the raised error but is
  not durable in the registry. An append-only attempt log was considered and not
  built; adding one would mean new on-disk state and a new failure surface for a
  guarantee the design does not otherwise depend on.

Nothing in this module performs a calculation, and nothing here may be used to
tune, select or compare strategies.
"""
from __future__ import annotations

import errno
import json
import time
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "ResearchGuardError",
    "CrossAssetAuthorization",
    "ResearchContext",
    "GuardDecision",
    "registry_path",
    "load_registry",
    "assert_evaluation_permitted",
    "assert_instrument_identity",
    "assert_no_registered_range",
    "assert_series_permitted",
    "consume_reservation",
    "candle_fingerprint",
    "note_overlap_check",
    "OVERLAP_CHECKED",
    "OVERLAP_SKIPPED",
    "OVERLAP_FAILED",
    "VOLUME_SEMANTICS",
    "MARKET_TYPES_SUPPORTED",
]

OVERLAP_CHECKED = "checked"
OVERLAP_SKIPPED = "skipped"
OVERLAP_FAILED = "failed"
_OVERLAP_STATES = frozenset({OVERLAP_CHECKED, OVERLAP_SKIPPED, OVERLAP_FAILED})

#: Volume semantics must be declared; an undeclared one is refused for research.
VOLUME_SEMANTICS = frozenset(
    {"central_base", "central_quote", "tick", "none"}
)

#: Market types with an implemented validator. Anything else stays blocked.
#:
#: ``forex_spot`` is deliberately absent: no session, holiday or DST validator
#: exists in this repository. Claiming otherwise would be false.
MARKET_TYPES_SUPPORTED = frozenset({"crypto_spot"})

_REGISTRY_ENV = "CRYPTO_PAPER_LAB_RESEARCH_REGISTRY"
_DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "data" / "research_registry.json"

#: Fields this module needs in order to make a *decision*. Structural validation
#: of the wider metadata record lives in :mod:`registry_schema` and runs once at
#: load time; duplicating the full field list here would let the two drift.
_REQUIRED_INSTRUMENT_FIELDS = ("instrument_id", "market_type", "timeframe",
                               "volume_semantics")


class ResearchGuardError(RuntimeError):
    """Raised when research-integrity rules refuse an operation.

    A ``RuntimeError`` rather than ``ValueError`` so it is never mistaken for
    ordinary data validation and silently caught by a broad ``except ValueError``.
    """


def registry_path() -> Path:
    """Location of the registry. Overridable for tests; absence still fails."""

    import os

    override = os.environ.get(_REGISTRY_ENV)
    return Path(override) if override else _DEFAULT_REGISTRY


def _parse_ts(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ResearchGuardError(
            f"reservation field {field_name!r} is missing or not a string"
        )
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ResearchGuardError(
            f"reservation field {field_name!r} is not an ISO timestamp: {value!r}"
        ) from exc


@dataclass(frozen=True)
class CrossAssetAuthorization:
    """Explicit, recordable permission to evaluate dataset X under a config
    whose ``asset`` label names a different instrument.

    The BTC-derived configuration declares ``asset="BTC/USDT"``. Evaluating it
    against ETH data must not be achieved by silently relabelling ETH as BTC, so
    the mismatch is made explicit, justified and retained.
    """

    dataset_instrument: str
    config_asset: str
    justification: str
    approved_by: str
    approved_on: str

    def as_record(self) -> dict[str, str]:
        return {
            "dataset_instrument": self.dataset_instrument,
            "config_asset": self.config_asset,
            "justification": self.justification,
            "approved_by": self.approved_by,
            "approved_on": self.approved_on,
        }

    @staticmethod
    def from_record(record: Any) -> "CrossAssetAuthorization":
        if not isinstance(record, dict):
            raise ResearchGuardError(
                "cross-asset authorization must be a mapping"
            )
        missing = [
            f for f in ("dataset_instrument", "config_asset", "justification",
                        "approved_by", "approved_on")
            if not str(record.get(f, "")).strip()
        ]
        if missing:
            raise ResearchGuardError(
                "cross-asset authorization is incomplete; missing: "
                + ", ".join(sorted(missing))
            )
        return CrossAssetAuthorization(
            dataset_instrument=str(record["dataset_instrument"]),
            config_asset=str(record["config_asset"]),
            justification=str(record["justification"]),
            approved_by=str(record["approved_by"]),
            approved_on=str(record["approved_on"]),
        )


@dataclass
class GuardDecision:
    """Outcome of a guard call, suitable for recording in a results artifact."""

    permitted: bool
    reason: str
    dataset_sha256: str
    instrument_id: str
    timeframe: str
    evaluation_start: datetime | None
    evaluation_end: datetime | None
    reservation_id: str | None = None
    preregistration_id: str | None = None
    cross_asset: dict[str, str] | None = None

    #: Fingerprint of the actual candle series handed to the engine, when the
    #: series itself was checked. Empty when only metadata was validated.
    series_fingerprint: str = ""

    #: True when this decision permitted development use of an already-consumed
    #: window. Set so a later audit can separate mechanical replay from research.
    consumed_series_development_use: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "permitted": self.permitted,
            "reason": self.reason,
            "dataset_sha256": self.dataset_sha256,
            "instrument_id": self.instrument_id,
            "timeframe": self.timeframe,
            "evaluation_start": (
                self.evaluation_start.isoformat() if self.evaluation_start else None
            ),
            "evaluation_end": (
                self.evaluation_end.isoformat() if self.evaluation_end else None
            ),
            "reservation_id": self.reservation_id,
            "preregistration_id": self.preregistration_id,
            "cross_asset": self.cross_asset,
            "series_fingerprint": self.series_fingerprint,
            "consumed_series_development_use": self.consumed_series_development_use,
        }


@dataclass(frozen=True)
class ResearchContext:
    """Everything needed to identify and authorise one research evaluation.

    Bundled into a single object so every entry point accepts the same shape and
    no guard can be partially supplied. Constructing this is the explicit act of
    declaring "this run is an evaluation", which is what triggers enforcement.
    """

    dataset_sha256: str
    instrument_id: str
    timeframe: str
    evaluation_first: datetime
    evaluation_last: datetime
    preregistration_id: str
    config_asset: str | None = None
    cross_asset: "CrossAssetAuthorization | dict[str, Any] | None" = None
    registry_file: str | Path | None = None

    #: Spend the reservation when the run is permitted.
    #:
    #: Defaults to **False**. Phase 40 moved consumption out of the guard call
    #: and into :func:`consume_reservation`, which the caller invokes after a
    #: successful run. Spending inside the check meant a guard failure downstream,
    #: or a crash mid-run, consumed a window that produced no result. An
    #: evaluation spends a window; an attempt does not.
    mark_used: bool = False


def assert_no_registered_range(
    *,
    instrument_id: str,
    first: datetime,
    last: datetime,
    registry: dict[str, Any] | None = None,
    registry_file: str | Path | None = None,
    allow_consumed: bool = False,
) -> list[str]:
    """Refuse a time range that touches a registered window.

    This check is **hash-independent**, which matters: the engine receives
    ``Candle`` objects and is not otherwise told a file's digest, so a range check
    catches reuse of a spent window even when the caller does not declare
    identity. Passing ``allow_consumed=True`` is only meaningful for reading a
    historical record, never for evaluating.
    """

    reg = registry if registry is not None else load_registry(registry_file)
    hits: list[str] = []
    for kind in ("consumed_windows", "reservations"):
        for entry in reg[kind]:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("instrument_id", "")) != str(instrument_id):
                continue
            w_first = entry.get("evaluation_first")
            w_last = entry.get("evaluation_last")
            if not w_first or not w_last:
                continue
            a = _parse_ts(w_first, f"{kind}.evaluation_first")
            b = _parse_ts(w_last, f"{kind}.evaluation_last")
            if first <= b and a <= last:
                if kind == "consumed_windows" and not allow_consumed:
                    raise ResearchGuardError(
                        "requested range "
                        f"{first.isoformat()} .. {last.isoformat()} overlaps a "
                        "consumed evaluation window "
                        f"({a:%Y-%m-%d} .. {b:%Y-%m-%d}); consumed windows may "
                        "never be reused for evaluation"
                    )
                hits.append(f"{kind}:{entry.get('reservation_id') or entry.get('dataset_sha256')}")
    return hits


def candle_fingerprint(candles: Sequence[Any]) -> str:
    """Canonical SHA-256 over a candle *series*, independent of file format.

    File digests cannot help here: the engine is handed ``Candle`` objects and
    is never told which file they came from. This fingerprint closes that gap, so
    a series can be recognised as a protected dataset even when the caller
    supplies no identity at all.

    Canonical form is ``timestamp|open,high,low,close,volume`` per line, with
    floats via ``repr`` so the encoding round-trips exactly. Formatting a raw
    float is stable across platforms for IEEE-754 doubles.
    """

    import hashlib

    digest = hashlib.sha256()
    for candle in candles:
        digest.update(candle.timestamp.isoformat().encode("utf-8"))
        digest.update(b"|")
        for value in (candle.open, candle.high, candle.low, candle.close,
                      candle.volume):
            digest.update(repr(float(value)).encode("ascii"))
            digest.update(b",")
        digest.update(b"\n")
    return digest.hexdigest()


def consume_reservation(
    reservation_id: str,
    *,
    registry_file: str | Path | None = None,
    preregistration_id: str | None = None,
) -> None:
    """Spend a reservation *after* its evaluation has completed successfully.

    Kept separate from :func:`assert_evaluation_permitted` on purpose. If the
    guard both validated and spent in one call, a later failure inside the run
    would have consumed a window that produced no result -- and a crash mid-run
    would leave it spent with no record of what happened.

    So the sequence is: check (``mark_used=False``), run, then consume here. A
    failed run therefore leaves the window available, which is the correct
    behaviour: a window should be spent by an evaluation, not by an attempt.
    """

    reg = load_registry(registry_file)
    matches = [
        entry for entry in reg["reservations"]
        if isinstance(entry, dict)
        and str(entry.get("reservation_id")) == str(reservation_id)
    ]
    if not matches:
        raise ResearchGuardError(
            f"cannot spend reservation {reservation_id!r}: it is not in the "
            f"registry at {registry_file or registry_path()}"
        )

    # The preregistration actually used is the one the caller reports, so the
    # audit trail records what ran rather than what the registry happened to hold.
    _consume_reservations(
        matches,
        registry_file,
        reported_preregistration=(
            str(preregistration_id) if preregistration_id is not None else None
        ),
    )


def assert_series_permitted(
    candles: Sequence[Any],
    *,
    research_context: "ResearchContext | dict[str, Any] | None" = None,
    registry: dict[str, Any] | None = None,
    registry_file: str | Path | None = None,
    evaluation_first: datetime | None = None,
    evaluation_last: datetime | None = None,
    preregistration_id: str | None = None,
    config_asset: str | None = None,
    cross_asset: "CrossAssetAuthorization | dict[str, Any] | None" = None,
    mark_used: bool = False,
) -> GuardDecision:
    """Refuse *any* execution over a reserved window that lacks a valid context.

    This is the backstop for the omission bypass. ``assert_evaluation_permitted``
    only runs when a caller supplies a context; without this check a caller could
    simply omit one. Here the series itself is fingerprinted, so omitting the
    context is not a way to stay unchecked.

    Two series are distinguished deliberately:

    * A series matching a **reserved** window is refused unless a valid research
      context is supplied. That window has not been spent, so touching it
      casually is exactly the accident this project exists to prevent.
    * A series matching a **consumed** window is *permitted*, but the decision
      records ``consumed_series_development_use`` so a later audit can tell
      mechanical development apart from research validation. The engine, the
      dashboard and the existing test suite legitimately replay BTC data; making
      that impossible would break engineering work without adding protection to
      a window that is already spent.

    An unregistered series is permitted as ungoverned development data. That is
    a stated limit, not a claim of safety: nothing can identify data the registry
    has never seen.
    """

    if not len(candles):
        raise ResearchGuardError("cannot verify an empty series against the registry")

    reg = registry if registry is not None else load_registry(registry_file)
    fingerprint = candle_fingerprint(candles)
    first = candles[0].timestamp
    last = candles[-1].timestamp

    reserved = _series_matches(reg["reservations"], fingerprint)
    consumed = _series_matches(reg["consumed_windows"], fingerprint)

    # A caller holding only the evaluation bars of a reserved dataset produces a
    # different full-series fingerprint, so each reservation also registers the
    # fingerprint of its evaluation slice and its warm-up+evaluation span. Both
    # are matched exactly.
    if not reserved:
        reserved = _slice_matches(reg["reservations"], candles)
    if not consumed:
        consumed = _slice_matches(reg["consumed_windows"], candles)

    # Which registered window the per-bar index recognises, and how strongly.
    indexed = _indexed_window(candles)

    if not reserved:
        reserved = indexed is not None and _index_covers_reservation(
            reg["reservations"], indexed
        )
    if not consumed:
        consumed = indexed is not None and not _index_covers_reservation(
            reg["reservations"], indexed
        )

    if research_context is None:
        if reserved:
            raise ResearchGuardError(
                "this series is a reserved evaluation window and no "
                "research_context was supplied. Omitting the context does not "
                "make a run non-research: the series itself identifies it as "
                "protected, so the run is refused. Supply a valid "
                "ResearchContext, or use data that is not reserved."
            )
        if consumed:
            return GuardDecision(
                permitted=True,
                reason=(
                    f"series matches consumed window {indexed!r}; permitted as "
                    "development use of already-spent data, recorded so it "
                    "cannot be mistaken for research validation"
                ),
                dataset_sha256=fingerprint,
                instrument_id="",
                timeframe="",
                evaluation_start=first,
                evaluation_end=last,
                # Populated: this decision is the audit record for the call, so
                # it must identify the series it describes.
                series_fingerprint=fingerprint,
                consumed_series_development_use=True,
            )
        return GuardDecision(
            permitted=True,
            reason=(
                "series is not registered research data; permitted as "
                "unregistered development data, which is a stated limit rather "
                "than a verified-safe classification"
            ),
            dataset_sha256=fingerprint,
            instrument_id="",
            timeframe="",
            evaluation_start=first,
            evaluation_end=last,
            series_fingerprint=fingerprint,
        )

    # A context was declared, so the run is claiming to be an evaluation. Route
    # it through the full identity/reservation/preregistration checks.
    # Explicit arguments win over the context's declared range: ``run_window``
    # hands this call a per-window slice while the context describes the whole
    # evaluation, so the context range would be the wrong thing to compare.
    resolved_first = (
        evaluation_first
        if evaluation_first is not None
        else research_context.evaluation_first  # type: ignore[union-attr]
    )
    resolved_last = (
        evaluation_last
        if evaluation_last is not None
        else research_context.evaluation_last  # type: ignore[union-attr]
    )
    resolved_prereg = (
        preregistration_id
        if preregistration_id is not None
        else research_context.preregistration_id  # type: ignore[union-attr]
    )
    resolved_asset = (
        config_asset
        if config_asset is not None
        else research_context.config_asset  # type: ignore[union-attr]
    )
    resolved_cross = (
        cross_asset if cross_asset is not None
        else research_context.cross_asset  # type: ignore[union-attr]
    )
    resolved_mark_used = (
        mark_used if mark_used
        else bool(getattr(research_context, "mark_used", False))
    )

    decision = assert_evaluation_permitted(
        dataset_sha256=research_context.dataset_sha256,  # type: ignore[union-attr]
        instrument_id=research_context.instrument_id,  # type: ignore[union-attr]
        timeframe=research_context.timeframe,  # type: ignore[union-attr]
        evaluation_start=resolved_first,
        evaluation_end=resolved_last,
        preregistration_id=resolved_prereg,
        config_asset=resolved_asset,
        cross_asset=resolved_cross,
        registry=reg,
        registry_file=registry_file,
        mark_used=resolved_mark_used,
    )
    decision.series_fingerprint = fingerprint
    return decision


def _indexed_window(candles: Sequence[Any]) -> str | None:
    """Key of the registered window whose per-bar index covers this series.

    This is the partial-subset check. A series is matched when at least half its
    bars are registered against a protected window, with a floor of three bars so
    a one- or two-bar synthetic fixture cannot trip it.

    Threshold rather than any-hit, because a single coincidentally identical
    synthetic candle must not make an unrelated dataset look protected.

    Residual limit, stated rather than hidden: a deliberate exfiltration of under
    half a window's bars would pass. In practice that is inert -- the engine
    requires more than ``minimum_history`` (22) bars before any signal can exist,
    so a series too short to be matched cannot produce a trade either.
    """

    from .researchindex import is_indexed_series

    return is_indexed_series(candles)


def _index_covers_reservation(reservations: list[Any], key: str) -> bool:
    """True when ``key`` names a reservation rather than a consumed window."""

    return any(
        isinstance(entry, dict) and str(entry.get("reservation_id")) == key
        for entry in reservations
    )



def _series_matches(entries: list[Any], fingerprint: str) -> bool:
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("series_fingerprint", "")):
            if str(entry["series_fingerprint"]).lower() == fingerprint.lower():
                return True
    return False


def _slice_matches(entries: list[Any], candles: Sequence[Any]) -> bool:
    """True when these exact candles equal a registered evaluation slice.

    Deliberately an *exact* content match rather than a date-range overlap. A
    range overlap would refuse any unrelated dataset that merely shares calendar
    dates, which is both wrong and unusable: synthetic fixtures legitimately use
    arbitrary dates. Content identity is the honest test for "these are the
    reserved bars".
    """

    if not len(candles):
        return False
    fingerprint = candle_fingerprint(candles)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        registered = str(entry.get("evaluation_fingerprint", ""))
        if registered and registered.lower() == fingerprint.lower():
            return True
    return False


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load the registry. Missing or malformed registry raises -- fail closed."""

    target = Path(path) if path is not None else registry_path()
    if not target.exists():
        raise ResearchGuardError(
            f"research registry not found at {target}. Refusing to evaluate: "
            "an absent registry cannot be read as 'nothing is protected'."
        )
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ResearchGuardError(
            f"research registry at {target} could not be read: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchGuardError(
            f"research registry at {target} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ResearchGuardError(
            "research registry must be a JSON object at the top level"
        )
    for key in ("version", "instruments", "reservations", "consumed_windows"):
        if key not in data:
            raise ResearchGuardError(
                f"research registry is missing required section {key!r}"
            )
    for key in ("instruments", "reservations", "consumed_windows"):
        if not isinstance(data[key], list):
            raise ResearchGuardError(
                f"research registry section {key!r} must be a list"
            )

    # Phase 45. Shape is not enough: entries missing identity, licensing or
    # provenance fields were previously accepted silently, which made those
    # fields documentation rather than declarations. Metadata coherence is
    # validated here so a malformed entry cannot reach the guard logic below.
    from .registry_schema import validate_registry_metadata

    validate_registry_metadata(data)
    return data


def _instrument_entry(registry: dict[str, Any], instrument_id: str) -> dict[str, Any]:
    for entry in registry["instruments"]:
        if isinstance(entry, dict) and entry.get("instrument_id") == instrument_id:
            return entry
    raise ResearchGuardError(
        f"instrument {instrument_id!r} is not registered; unknown instruments "
        "may not be evaluated"
    )


def _validate_instrument(entry: dict[str, Any], instrument_id: str) -> None:
    # Completeness and coherence are enforced once, centrally, by
    # registry_schema.validate_registry_metadata at load time. Repeating the
    # check here would duplicate the field list and let the two drift apart, so
    # this asserts the contract instead of re-deriving it.
    missing = [f for f in _REQUIRED_INSTRUMENT_FIELDS
               if not str(entry.get(f, "")).strip()]
    if missing:
        raise ResearchGuardError(
            f"instrument {instrument_id!r} has incomplete metadata; missing: "
            + ", ".join(sorted(missing))
        )
    market_type = str(entry["market_type"])
    if market_type not in MARKET_TYPES_SUPPORTED:
        raise ResearchGuardError(
            f"instrument {instrument_id!r} has market_type {market_type!r}, which "
            "has no implemented validator in this repository. Supported: "
            + ", ".join(sorted(MARKET_TYPES_SUPPORTED))
            + ". This is refused rather than approximated."
        )
    if str(entry["volume_semantics"]) not in VOLUME_SEMANTICS:
        raise ResearchGuardError(
            f"instrument {instrument_id!r} declares volume_semantics "
            f"{entry['volume_semantics']!r}, which is not one of "
            + ", ".join(sorted(VOLUME_SEMANTICS))
        )


def note_overlap_check(status: Any, context: str = "overlap") -> str:
    """Validate and return an explicit overlap-check status.

    An empty list of overlapping rows is ambiguous: it may mean *checked and
    clean* or *never checked*. This forces the distinction to be stated.
    """

    if status not in _OVERLAP_STATES:
        raise ResearchGuardError(
            f"{context} check status must be one of "
            + ", ".join(sorted(_OVERLAP_STATES))
            + f"; got {status!r}. 'unknown' is not a permitted state."
        )
    return status


def assert_instrument_identity(
    *,
    dataset_sha256: str,
    instrument_id: str,
    timeframe: str,
    config_asset: str | None = None,
    cross_asset: CrossAssetAuthorization | dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    registry_file: str | Path | None = None,
) -> GuardDecision:
    """Refuse a dataset whose identity does not match how it is being used.

    When ``config_asset`` differs from the dataset's registered instrument, an
    explicit :class:`CrossAssetAuthorization` is required. The mismatch is never
    resolved by relabelling the data.
    """

    if not dataset_sha256 or not str(dataset_sha256).strip():
        raise ResearchGuardError("dataset_sha256 is required for identity checking")
    reg = registry if registry is not None else load_registry(registry_file)
    entry = _instrument_entry(reg, str(instrument_id))
    _validate_instrument(entry, str(instrument_id))

    declared_tf = str(entry["timeframe"])
    if timeframe and str(timeframe) != declared_tf:
        raise ResearchGuardError(
            f"timeframe mismatch: dataset {instrument_id} is declared {declared_tf!r} "
            f"but the run declares {timeframe!r}"
        )

    known_hashes = {
        str(e.get("dataset_sha256", "")).lower()
        for e in reg["reservations"] + reg["consumed_windows"]
        if isinstance(e, dict)
    }
    if str(dataset_sha256).lower() not in known_hashes:
        raise ResearchGuardError(
            f"dataset_sha256 {dataset_sha256} is not registered against any "
            f"reservation or consumed window for {instrument_id}. Unknown data "
            "may not be evaluated."
        )

    record = None
    if config_asset is not None and str(config_asset).strip():
        if str(config_asset) != str(instrument_id):
            auth = (cross_asset if isinstance(cross_asset, CrossAssetAuthorization)
                    else CrossAssetAuthorization.from_record(cross_asset)
                    if cross_asset is not None else None)
            if auth is None:
                raise ResearchGuardError(
                    f"instrument transfer refused: dataset is {instrument_id!r} but "
                    f"the strategy configuration declares asset={config_asset!r}. "
                    "A CrossAssetAuthorization is required; relabelling the data "
                    "or the config is not permitted."
                )
            if auth.dataset_instrument != str(instrument_id) or \
                    auth.config_asset != str(config_asset):
                raise ResearchGuardError(
                    "cross-asset authorization does not describe this run "
                    f"(dataset_instrument={auth.dataset_instrument!r}, "
                    f"config_asset={auth.config_asset!r})"
                )
            record = auth.as_record()

    return GuardDecision(
        permitted=True,
        reason="instrument identity verified",
        dataset_sha256=str(dataset_sha256),
        instrument_id=str(instrument_id),
        timeframe=declared_tf,
        evaluation_start=None,
        evaluation_end=None,
        cross_asset=record,
    )


def _matching_windows(
    registry: dict[str, Any], dataset_sha256: str, instrument_id: str
) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for kind in ("consumed_windows", "reservations"):
        for entry in registry[kind]:
            if not isinstance(entry, dict):
                raise ResearchGuardError(
                    f"registry section {kind!r} contains a non-object entry"
                )
            if (str(entry.get("dataset_sha256", "")).lower()
                    == str(dataset_sha256).lower()
                    and str(entry.get("instrument_id", "")) == str(instrument_id)):
                out.append((kind, entry))
    return out


#: Suffix of the inter-process lock file guarding registry writes.
#: Suffix of the sidecar file carrying the OS-native advisory lock.
_REGISTRY_LOCK_SUFFIX = ".lock"

#: Bytes of the lock file that are actually locked. One byte is enough to carry
#: the lock; the file itself may be zero length.
_REGISTRY_LOCK_BYTES = 1


def _acquire_fd_lock(fd: int, lock_path: Path) -> None:
    """Take an exclusive, non-blocking advisory lock on ``fd``.

    Uses the operating system's own advisory locking rather than a sentinel
    file, because the OS releases the lock when the process ends -- including
    when it is killed. A sentinel approach has to *guess* whether a lock is
    abandoned, and that guess is unreliable: on Windows a terminated pid still
    resolves in the process table, so a crashed holder's sentinel would look
    live forever.
    """

    import os

    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, _REGISTRY_LOCK_BYTES)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise ResearchGuardError(
            f"refusing to record consumption: the registry at {lock_path} is "
            "locked by another process. Consumption cannot be serialised "
            f"safely ({type(exc).__name__}: {exc}). Nothing was written."
        ) from exc


@contextmanager
def _registry_lock(target: Path):
    """Serialise the registry read-modify-write across processes.

    The lock is an OS-native advisory lock held on an open descriptor for the
    duration of the critical section. Closing the descriptor releases it, and the
    OS releases it too if the process dies -- so a crashed writer cannot leave an
    orphaned lock behind, and there is no staleness threshold, no ceiling, and no
    pid-reuse ambiguity to reason about.

    The sidecar file itself is left in place after release. That is intentional:
    deleting it would race with another process that has already opened it. An
    unlocked sidecar is harmless -- it carries no state.

    Failure is closed. If the sidecar cannot be opened, or the lock cannot be
    taken, the caller refuses rather than proceeding unprotected.
    """

    import os

    lock_path = target.with_name(target.name + _REGISTRY_LOCK_SUFFIX)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
    except OSError as exc:
        raise ResearchGuardError(
            f"refusing to record consumption: could not open the lock file "
            f"{lock_path} ({type(exc).__name__}: {exc}). Consumption cannot be "
            "serialised safely, so nothing was written."
        ) from exc

    try:
        _acquire_fd_lock(fd, lock_path)
    except BaseException:
        os.close(fd)
        raise

    try:
        yield
    finally:
        # Closing releases the advisory lock on both POSIX (flock) and
        # Windows (msvcrt.locking).
        os.close(fd)


def _consume_reservations(
    reservations: list[dict[str, Any]],
    registry_file: str | Path | None,
    reported_preregistration: str | None = None,
) -> None:
    """Record that a reserved window has now been used, durably.

    Without this, "evaluated once only" is not a real guarantee: the ``used``
    flag would never change and the same window could be run repeatedly. Because
    the flag has to survive the process, refusing to evaluate when there is no
    file to record into is the fail-closed outcome -- silently skipping the
    record would trade a real guarantee for convenience.

    The file is re-read from disk before editing so a concurrently supplied
    in-memory registry cannot clobber it, and it is replaced atomically.
    """

    import os
    import tempfile

    if registry_file is None:
        raise ResearchGuardError(
            "refusing to evaluate: a reserved window may be evaluated once, so "
            "its consumption must be recorded, but no registry_file was supplied "
            "to record it into. Skipping the record would make the one-time "
            "guarantee unenforceable."
        )

    target = Path(registry_file)

    # Everything that reads, decides or writes the registry happens under the
    # inter-process lock. The decision about whether a reservation is already
    # spent MUST happen after the lock is held and after the re-read, otherwise
    # two processes could both observe ``used=false`` and both record a spend.
    with _registry_lock(target):
        on_disk = load_registry(target)  # re-read: never write a stale copy
        now = datetime.now().isoformat(timespec="seconds")

        wanted = {str(r.get("reservation_id")) for r in reservations}
        by_id = {str(r.get("reservation_id")): r for r in reservations}

        # A reservation is spent once. Re-spending it would silently overwrite
        # ``used_on`` and ``used_preregistration_id`` -- the only record of when
        # the window was spent and under which preregistration. That is
        # audit-trail corruption, not a no-op, so it is refused before anything
        # is mutated. The check runs against ``on_disk`` (freshly re-read, under
        # the lock) and precedes every write, so a refusal leaves the registry
        # byte-for-byte unchanged.
        already_spent = sorted(
            str(entry.get("reservation_id"))
            for entry in on_disk["reservations"]
            if isinstance(entry, dict)
            and str(entry.get("reservation_id")) in wanted
            and entry.get("used")
        )
        if already_spent:
            raise ResearchGuardError(
                "refusing to record consumption: reservation(s) "
                f"{already_spent} are already spent (used=true). A reservation may "
                "be spent only once, and re-spending it would overwrite the record "
                "of when and under which preregistration the window was evaluated. "
                "Nothing was written."
            )

        touched: list[str] = []
        for entry in on_disk["reservations"]:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("reservation_id")) in wanted:
                entry["used"] = True
                # Status must move with the flag. Leaving it RESERVED while
                # ``used`` is true is a self-contradiction, and Phase 45's schema
                # validation refuses one -- so the writer has to keep them
                # consistent.
                entry["status"] = "USED"
                entry["used_on"] = now
                # Take the preregistration from the caller's entry, which
                # reflects what actually ran. Falling back to the on-disk value is
                # right when the caller did not say, and the registry value is
                # then the one that was checked against the run.
                reported = reported_preregistration
                if not reported:
                    reported = str(
                        by_id.get("used_preregistration_id")
                        or by_id.get("preregistration_id")
                        or ""
                    )
                entry["used_preregistration_id"] = reported or None
                touched.append(str(entry.get("reservation_id")))

        if len(touched) != len(wanted):
            raise ResearchGuardError(
                "refusing to record consumption: reservation "
                f"{sorted(wanted - set(touched))} could not be found in the "
                f"registry file at {target}. Nothing was written."
            )

        tmp_name = None
        try:
            handle, tmp_name = tempfile.mkstemp(
                dir=str(target.parent), prefix=target.name, suffix=".tmp"
            )
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(on_disk, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_name, target)
            tmp_name = None
        except BaseException:
            if tmp_name is not None:
                Path(tmp_name).unlink(missing_ok=True)
            raise

    # Mirror the change onto the caller's registry object. Without this a caller
    # holding an in-memory registry could re-run the same window inside this
    # process, because their copy would still read used=False.
    for entry in reservations:
        entry["used"] = True
        entry["status"] = "USED"
        entry["used_on"] = now

    


def assert_evaluation_permitted(
    *,
    dataset_sha256: str,
    instrument_id: str,
    timeframe: str,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
    preregistration_id: str | None = None,
    cross_asset: CrossAssetAuthorization | dict[str, Any] | None = None,
    config_asset: str | None = None,
    registry: dict[str, Any] | None = None,
    registry_file: str | Path | None = None,
    mark_used: bool = False,
) -> GuardDecision:
    """Fail-closed check that an evaluation window may be run.

    * A **consumed** window is refused outright, always.
    * A **reserved** window is refused unless every declared field matches the
      reservation exactly, a preregistration id is supplied and registered, and
      the window has not already been used.
    * A dataset with no registry entry is refused, because an unregistered
      dataset cannot be shown to be safe to evaluate.
    """

    if not str(dataset_sha256 or "").strip():
        raise ResearchGuardError("dataset_sha256 is required")
    if not str(instrument_id or "").strip():
        raise ResearchGuardError("instrument_id is required")
    if not str(timeframe or "").strip():
        raise ResearchGuardError("timeframe is required")

    reg = registry if registry is not None else load_registry(registry_file)

    # When a registry file is named, it is the authority for the decision. A
    # caller must not be able to re-run a window the file already records as
    # spent by passing a stale in-memory copy instead. This applies whether or
    # not the run consumes the reservation, because the spent check itself must
    # never read a stale copy.
    if registry_file is not None:
        reg = load_registry(registry_file)

    entry = _instrument_entry(reg, str(instrument_id))
    _validate_instrument(entry, str(instrument_id))
    if str(timeframe) != str(entry["timeframe"]):
        raise ResearchGuardError(
            f"timeframe mismatch for {instrument_id}: registry says "
            f"{entry['timeframe']!r}, run declares {timeframe!r}"
        )

    identity = assert_instrument_identity(
        dataset_sha256=dataset_sha256,
        instrument_id=instrument_id,
        timeframe=timeframe,
        config_asset=config_asset,
        cross_asset=cross_asset,
        registry=reg,
    )

    matches = _matching_windows(reg, dataset_sha256, instrument_id)
    if not matches:
        raise ResearchGuardError(
            f"no reservation or consumed window is registered for dataset "
            f"{dataset_sha256} ({instrument_id}); unregistered data may not be "
            "evaluated"
        )

    consumed = [e for kind, e in matches if kind == "consumed_windows"]
    for window in consumed:
        raise ResearchGuardError(
            "evaluation window has already been consumed and may never be "
            f"reused: {window.get('consumed_on', 'unknown')} "
            f"{window.get('evaluation_first')} .. {window.get('evaluation_last')}"
        )

    reservations = [e for kind, e in matches if kind == "reservations"]
    for res in reservations:
        rid = res.get("reservation_id")
        if not str(rid or "").strip():
            raise ResearchGuardError(
                "reservation entry is missing reservation_id; malformed "
                "reservation metadata is refused"
            )
        first = _parse_ts(res.get("evaluation_first"), "evaluation_first")
        last = _parse_ts(res.get("evaluation_last"), "evaluation_last")
        if str(res.get("dataset_sha256", "")).lower() != str(dataset_sha256).lower():
            raise ResearchGuardError(
                f"reservation {rid} dataset hash does not match the run"
            )
        if str(res.get("timeframe", "")) != str(timeframe):
            raise ResearchGuardError(
                f"reservation {rid} timeframe does not match the run"
            )
        if evaluation_start is None or evaluation_end is None:
            raise ResearchGuardError(
                f"dataset {dataset_sha256} is reserved for {first:%Y-%m-%d}.."
                f"{last:%Y-%m-%d}; the run must declare evaluation_start and "
                "evaluation_end. Omitting them would evaluate the reserved "
                "window as part of a larger series."
            )
        if evaluation_start != first or evaluation_end != last:
            raise ResearchGuardError(
                f"reservation {rid} requires evaluation range "
                f"{first.isoformat()} .. {last.isoformat()}, but the run "
                f"declared {evaluation_start.isoformat()} .. "
                f"{evaluation_end.isoformat()}"
            )
        # Order matters: a spent window is reported as spent, not as a status
        # problem. Checked here, before the status check below, so the caller
        # gets an actionable message.
        # Checking ``used`` first gives the caller the actionable message, since
        # "already been used" says what to do while "status is not RESERVED" does
        # not. Phase 45 added the USED status, which made the ordering matter.
        if res.get("used") or str(res.get("status", "")).upper() == "USED":
            raise ResearchGuardError(
                f"reservation {rid} has already been used; a reserved window "
                "may be evaluated once only"
            )
        if str(res.get("status", "")).upper() != "RESERVED":
            raise ResearchGuardError(
                f"reservation {rid} has status {res.get('status')!r}; only "
                "RESERVED may be evaluated"
            )

        registered_pre = str(res.get("preregistration_id", "") or "").strip()
        if not registered_pre:
            raise ResearchGuardError(
                f"reservation {rid} has no registered preregistration_id; "
                "evaluation is refused until one is frozen"
            )
        if not str(preregistration_id or "").strip():
            raise ResearchGuardError(
                f"reservation {rid} requires a preregistration_id on the run"
            )
        if str(preregistration_id) != registered_pre:
            raise ResearchGuardError(
                f"preregistration mismatch: reservation {rid} is bound to "
                f"{registered_pre!r}, the run supplied {preregistration_id!r}"
            )

    if mark_used:
        _consume_reservations(reservations, registry_file)

    return GuardDecision(
        permitted=True,
        reason="evaluation permitted by reservation",
        dataset_sha256=str(dataset_sha256),
        instrument_id=str(instrument_id),
        timeframe=str(timeframe),
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
        reservation_id=str(reservations[0].get("reservation_id")),
        preregistration_id=str(preregistration_id),
        cross_asset=identity.cross_asset,
    )
