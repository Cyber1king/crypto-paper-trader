"""Instrument-registry metadata validation (Phase 45).

Phase 39 created the registry with a shape check: the four top-level sections
must exist and be lists. That was enough to keep the file parseable, and it is
all ``load_registry`` verified before Phase 45.

Probing showed what that missed. A registry whose instrument entries had no
``timeframe``, no ``volume_semantics``, no ``venue``, or not even any
instruments at all, was accepted without complaint. A forex entry could declare
a nonsense timeframe and be accepted. A reservation with no ``instrument_id``
was accepted.

Those fields existed in the file and were read by nothing. ``venue``,
``licence_name``, ``provenance_grade`` and friends were pure documentation:
nothing checked them, so a contradiction between them and the rest of the entry
went unnoticed.

This module makes the metadata load-bearing:

* Every instrument must declare identity, market type, timeframe, volume
  semantics, venue, source, licensing and provenance grade.
* Contradictions are refused, not normalised -- for example a forex instrument
  claiming ``timestamp_normalized_tz`` other than ``UTC``, or a crypto spot
  entry with no data but a ``research_approved`` claim.
* Unsupported market types stay blocked, with the reason recorded in the entry
  rather than inferred at read time.

Deliberately strict, deliberately small. It validates *metadata coherence*, not
data quality: whether a dataset's prices are sane is
:mod:`crypto_paper_lab.dataset`'s job, and this module does not read candles.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "RegistryMetadataError",
    "validate_registry_metadata",
    "MARKET_TYPES_BLOCKED",
    "PROVENANCE_GRADES",
    "QUALITY_STATUSES",
    "APPROVAL_STATES",
    "LICENSE_KNOWLEDGE",
    "TIMESTAMP_CONVENTIONS",
]

#: Market types recognised but **blocked**. Present so a forex pair can be
#: described accurately in the registry, while still being unable to reach
#: evaluation. An unlisted market type is a malformed entry, not a blocked one.
MARKET_TYPES_BLOCKED = frozenset(
    {
        "forex_reference_rates",
        "forex_spot",
        "crypto_perpetual",
        "crypto_futures",
    }
)

#: Market types with an implemented validator in this repository.
MARKET_TYPES_SUPPORTED = frozenset({"crypto_spot"})

#: Provenance evidence grade. ``A`` requires independently re-derived values,
#: which is the only grade this repository has actually reached.
PROVENANCE_GRADES = frozenset({"A", "B", "C", "UNVERIFIED"})

#: Data-quality status of a *dataset*, never of an instrument. An instrument can
#: have several datasets in different states, so this belongs to the dataset.
QUALITY_STATUSES = frozenset(
    {"unchecked", "checked_clean", "checked_with_findings", "failed"}
)

#: Research-approval states. ``RESEARCH_APPROVED`` is deliberately hard to reach:
#: it additionally requires an approved preregistration id.
APPROVAL_STATES = frozenset(
    {
        "NOT_APPROVED",
        "DATA_VERIFIED_NOT_RESEARCH_APPROVED",
        "PREREGISTERED_NOT_APPROVED",
        "RESEARCH_APPROVED",
        "RESEARCH_CONSUMED",
        "BLOCKED_WRONG_DATA_TYPE",
    }
)

#: Licence states this repository can state with confidence. Anything else must
#: be recorded as ``UNVERIFIED`` rather than guessed, because licensing decides
#: whether redistribution is permitted at all.
LICENSE_KNOWLEDGE = frozenset({"VERIFIED", "UNVERIFIED", "RESTRICTED"})

#: Bar-boundary conventions. Kept explicit because a bar that opens at HH:00
#: and a bar that closes at HH:00 produce identical-looking timestamps with
#: different meanings.
TIMESTAMP_CONVENTIONS = frozenset(
    {
        "bar_opens_at_hour_utc",
        "bar_closes_at_hour_utc",
        "instantaneous_fixing",
    }
)

_REQUIRED_INSTRUMENT_FIELDS = (
    "instrument_id",
    "market_type",
    "timeframe",
    "volume_semantics",
    "venue",
    "source_provider",
    "licence_knowledge",
    "provenance_grade",
    "timestamp_convention",
    "timestamp_normalized_tz",
    "research_approval",
)

_RESERVATION_REQUIRED = (
    "reservation_id",
    "instrument_id",
    "dataset_sha256",
    "timeframe",
    "evaluation_first",
    "evaluation_last",
    "status",
    "used",
)

_CONSUMED_REQUIRED = (
    "instrument_id",
    "dataset_sha256",
    "timeframe",
    "evaluation_first",
    "evaluation_last",
    "consumed_on",
)

_SUPPORTED_MARKET_TYPES = MARKET_TYPES_SUPPORTED
_SUPPORTED_VOLUME = frozenset({"central_base", "central_quote", "tick", "none"})


class RegistryMetadataError(ValueError):
    """Malformed or self-contradictory registry metadata.

    ``ValueError`` because it reports bad *data*, unlike
    :class:`~crypto_paper_lab.researchguard.ResearchGuardError`, which reports a
    refused operation.
    """


def _require(entry: dict[str, Any], fields: tuple[str, ...], where: str) -> None:
    missing = [
        name
        for name in fields
        if name not in entry
        or entry[name] is None
        or not str(entry[name]).strip()
    ]
    if missing:
        raise RegistryMetadataError(
            f"{where} is missing required field(s): {', '.join(sorted(missing))}"
        )


def _one_of(
    value: Any, allowed: frozenset[str], field: str, where: str
) -> None:
    if str(value) not in allowed:
        raise RegistryMetadataError(
            f"{where}: {field}={value!r} is not one of "
            + ", ".join(sorted(allowed))
            + ". Refused rather than approximated."
        )


def _validate_source_provenance(entry: dict[str, Any], where: str) -> None:
    """Check the provenance fields that exist but were never validated.

    Phase 46 probed what the Phase 45 schema actually caught: ``checksum_published``
    could be deleted or set to ``"maybe"``, ``source_url_pattern`` could be
    ``"not-a-url"`` or absent, and ``symbol_native`` could contradict
    ``base_asset``/``quote_asset``. All were accepted.

    Each is a claim about where prices came from. An unvalidated claim is
    decoration, which is precisely the failure mode Phase 45 set out to remove.
    """

    # checksum_published is a boolean claim about the publisher. Absent means
    # unknown; unknown must not be recorded as either true or false.
    published = entry.get("checksum_published")
    if not isinstance(published, bool):
        raise RegistryMetadataError(
            f"{where}: checksum_published must be true or false, got "
            f"{published!r}. Whether the publisher issues digests is a fact "
            "about the source, not an optional field."
        )

    pattern = str(entry.get("source_url_pattern", "") or "").strip()
    if not pattern:
        raise RegistryMetadataError(
            f"{where}: source_url_pattern is required so a reader can reproduce "
            "the acquisition. Refusing a dataset whose origin cannot be "
            "reconstructed."
        )
    if not pattern.startswith(("http://", "https://")):
        raise RegistryMetadataError(
            f"{where}: source_url_pattern={pattern!r} is not an http(s) URL. "
            "Refused rather than recorded as an unreproducible origin."
        )

    # A venue that publishes digests should state where they live.
    if published and not str(
        entry.get("checksum_url_pattern", pattern) or ""
    ).strip():
        raise RegistryMetadataError(
            f"{where}: checksum_published is true but no checksum_url_pattern "
            "is recorded, so verification could not be reproduced."
        )

    # Symbol coherence: the venue's native spelling must be derivable from the
    # declared pair, or one of the three fields is wrong.
    base = str(entry.get("base_asset", "") or "").strip()
    quote = str(entry.get("quote_asset", "") or "").strip()
    native = str(entry.get("symbol_native", "") or "").strip()
    normalized = str(entry.get("symbol_normalized", "") or "").strip()
    ident = str(entry.get("instrument_id", "") or "").strip()

    if base and quote and native:
        compact = f"{base}{quote}"
        if native != compact and native != f"{base}/{quote}":
            raise RegistryMetadataError(
                f"{where}: symbol_native={native!r} does not correspond to "
                f"base_asset={base!r} and quote_asset={quote!r} (expected "
                f"{compact!r} or {base + '/' + quote!r}). At least one of the "
                "three symbol fields is wrong, and a wrong native symbol is how "
                "one instrument's data gets fetched under another's name."
            )

    if base and quote and normalized and normalized != f"{base}/{quote}":
        raise RegistryMetadataError(
            f"{where}: symbol_normalized={normalized!r} contradicts "
            f"base_asset={base!r}/quote_asset={quote!r}."
        )

    if ident and normalized and ident != normalized:
        raise RegistryMetadataError(
            f"{where}: instrument_id={ident!r} contradicts "
            f"symbol_normalized={normalized!r}. Identity must be one value, or a "
            "reservation bound to it is ambiguous."
        )

    # A declared timeframe must appear in the availability list; otherwise the
    # entry claims to hold data at a resolution the source does not serve.
    available = entry.get("timeframes_available")
    if isinstance(available, list):
        timeframe = str(entry.get("timeframe", "") or "").strip()
        if timeframe and available and timeframe not in available:
            raise RegistryMetadataError(
                f"{where}: timeframe={timeframe!r} is not in "
                f"timeframes_available={available!r}. The entry claims to "
                "validate at a resolution the source does not provide."
            )
        if timeframe and not available and market_type_is_supported(entry):
            raise RegistryMetadataError(
                f"{where}: timeframes_available is empty while timeframe="
                f"{timeframe!r} is declared, which means the instrument has no "
                "usable data. Refused rather than recorded as valid."
            )

    if entry.get("quality_status") is not None:
        status = str(entry["quality_status"]).strip()
        if status not in QUALITY_STATUSES:
            raise RegistryMetadataError(
                f"{where}: quality_status={status!r} is not one of "
                + ", ".join(sorted(QUALITY_STATUSES))
            )

    # A digest recorded on the instrument must at least be shaped like one.
    digest = str(entry.get("dataset_sha256", "") or "").strip()
    if digest and (
        len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest.lower())
    ):
        raise RegistryMetadataError(
            f"{where}: dataset_sha256={digest!r} is not a SHA-256 hex digest."
        )


def market_type_is_supported(entry: dict[str, Any]) -> bool:
    return str(entry.get("market_type", "")) in _SUPPORTED_MARKET_TYPES


def _validate_instrument(entry: dict[str, Any]) -> None:
    ident = str(entry.get("instrument_id", "<unnamed>"))
    where = f"instrument {ident!r}"

    _require(entry, _REQUIRED_INSTRUMENT_FIELDS, where)

    market_type = str(entry["market_type"])
    _one_of(
        market_type,
        _SUPPORTED_MARKET_TYPES | MARKET_TYPES_BLOCKED,
        "market_type",
        where,
    )

    _one_of(entry["volume_semantics"], _SUPPORTED_VOLUME, "volume_semantics", where)
    _one_of(entry["provenance_grade"], PROVENANCE_GRADES, "provenance_grade", where)
    _one_of(entry["licence_knowledge"], LICENSE_KNOWLEDGE, "licence_knowledge", where)
    _one_of(
        entry["timestamp_convention"],
        TIMESTAMP_CONVENTIONS,
        "timestamp_convention",
        where,
    )
    _one_of(
        entry["research_approval"],
        APPROVAL_STATES,
        "research_approval",
        where,
    )

    # Normalised timestamps are UTC by construction; anything else is a
    # contradiction rather than a variation.
    if str(entry["timestamp_normalized_tz"]).upper() != "UTC":
        raise RegistryMetadataError(
            f"{where}: timestamp_normalized_tz="
            f"{entry['timestamp_normalized_tz']!r} contradicts the project "
            "convention of storing every timestamp as UTC. Refused rather than "
            "converted, because a silent conversion would change the data."
        )

    supported = market_type in _SUPPORTED_MARKET_TYPES

    if supported and str(entry["timeframe"]) not in ("1h",):
        raise RegistryMetadataError(
            f"{where}: timeframe={entry['timeframe']!r} has no implemented "
            "interval validator. Only '1h' is implemented for "
            f"{market_type}; refused rather than approximated."
        )

    # Contradiction: a supported market type cannot be blocked for wrong data
    # type, and a blocked type cannot be research-approved.
    if supported and str(entry["research_approval"]) == "BLOCKED_WRONG_DATA_TYPE":
        raise RegistryMetadataError(
            f"{where}: market_type={market_type!r} is supported, so "
            "research_approval cannot be BLOCKED_WRONG_DATA_TYPE. "
            "Contradictory metadata is refused."
        )

    if not supported:
        approval = str(entry["research_approval"])
        if approval not in ("BLOCKED_WRONG_DATA_TYPE", "NOT_APPROVED"):
            raise RegistryMetadataError(
                f"{where}: market_type={market_type!r} is blocked, so "
                f"research_approval={approval!r} contradicts that. A blocked "
                "market type may not claim approval or consumption."
            )
        if approval == "BLOCKED_WRONG_DATA_TYPE":
            blocker = str(entry.get("blocker", "")).strip()
            if not blocker:
                raise RegistryMetadataError(
                    f"{where}: research_approval is BLOCKED_WRONG_DATA_TYPE "
                    "but no 'blocker' reason is recorded. A block without a "
                    "stated reason cannot be reviewed or lifted."
                )

    if str(entry["volume_semantics"]) == "none" and supported:
        raise RegistryMetadataError(
            f"{where}: volume_semantics='none' contradicts "
            f"market_type={market_type!r}. A crypto venue publishes volume, so "
            "'none' would misreport an unpopulated field. Absence is honest for "
            "sources that genuinely have none, such as reference fixings."
        )

    if str(entry["volume_semantics"]) == "tick":
        if not str(entry.get("volume_note", "")).strip():
            raise RegistryMetadataError(
                f"{where}: volume_semantics='tick' requires a 'volume_note' "
                "stating that tick volume is not a traded quantity. Recorded "
                "explicitly so it is never compared against centralised volume."
            )

    if str(entry["bid_ask_available"]) in ("false", "False", "0", "no"):
        if supported and str(entry["market_type"]) == "crypto_spot":
            if not str(entry.get("spread_note", "")).strip():
                raise RegistryMetadataError(
                    f"{where}: bid_ask_available is false, so a 'spread_note' "
                    "must record that spread cannot be modelled. Without it a "
                    "backtest could silently ignore costs it cannot see."
                )

    # Research approval is a governance act, not a data-quality property. A
    # clean dataset must never imply approval.
    if str(entry["research_approval"]) == "RESEARCH_APPROVED":
        prereg = str(entry.get("approved_preregistration_id", "")).strip()
        if not prereg:
            raise RegistryMetadataError(
                f"{where}: research_approval is RESEARCH_APPROVED but no "
                "'approved_preregistration_id' is recorded. Approval requires a "
                "frozen preregistration; it can never follow from data quality "
                "alone."
            )

    # Provenance applies to every instrument, not only consumed ones: a claim
    # about where prices came from matters before any window is spent.
    _validate_source_provenance(entry, where)

    # Consumed means spent. Approval and consumption cannot both hold.
    if str(entry["research_approval"]) == "RESEARCH_CONSUMED":
        if entry.get("consumed_windows"):
            for window in entry["consumed_windows"]:
                if not isinstance(window, dict):
                    raise RegistryMetadataError(
                        f"{where}: consumed_windows entries must be objects, "
                        f"found {type(window).__name__}"
                    )
                _require(
                    window,
                    ("evaluation_first", "evaluation_last"),
                    f"{where} consumed window",
                )


def _validate_reservation(entry: dict[str, Any], instruments: set[str]) -> None:
    rid = str(entry.get("reservation_id", "<unnamed>"))
    where = f"reservation {rid!r}"
    _require(entry, _RESERVATION_REQUIRED, where)

    if str(entry["instrument_id"]) not in instruments:
        raise RegistryMetadataError(
            f"{where} names instrument {entry['instrument_id']!r}, which is "
            "not in the instruments section. A reservation for an unregistered "
            "instrument cannot be enforced."
        )

    status = str(entry["status"]).upper()
    if status not in ("RESERVED", "USED"):
        raise RegistryMetadataError(
            f"{where}: status={entry['status']!r} is not one of RESERVED, USED"
        )
    if status == "RESERVED" and entry.get("used"):
        raise RegistryMetadataError(
            f"{where}: status is RESERVED but 'used' is true. A window cannot "
            "be both available and spent."
        )
    if status == "USED" and not entry.get("used"):
        raise RegistryMetadataError(
            f"{where}: status is USED but 'used' is false. The two fields "
            "contradict each other."
        )


def _validate_consumed(entry: dict[str, Any], instruments: set[str]) -> None:
    ident = str(entry.get("instrument_id", "<unnamed>"))
    where = f"consumed window for {ident!r}"
    _require(entry, _CONSUMED_REQUIRED, where)

    if str(entry["instrument_id"]) not in instruments:
        raise RegistryMetadataError(
            f"{where} names an instrument absent from the instruments section."
        )


def validate_registry_metadata(registry: dict[str, Any]) -> None:
    """Validate instrument, reservation and consumed-window metadata.

    Raises :class:`RegistryMetadataError` on the first problem found, naming the
    entry and the field. Strict on purpose: a registry that cannot be reviewed
    is worse than one that is refused.

    Does not verify file digests or read datasets. It checks that the metadata
    is coherent and complete, which is what this module is for.
    """

    instruments = registry.get("instruments")
    if not isinstance(instruments, list):
        raise RegistryMetadataError("instruments must be a list")

    if not instruments:
        raise RegistryMetadataError(
            "instruments section is empty. An empty registry cannot be read as "
            "'nothing is protected' -- it means nothing is *declared*, which is "
            "a different and more dangerous state."
        )

    seen: set[str] = set()
    for entry in instruments:
        if not isinstance(entry, dict):
            raise RegistryMetadataError(
                f"instrument entries must be objects, found "
                f"{type(entry).__name__}"
            )
        ident = str(entry.get("instrument_id", "")).strip()
        if not ident:
            raise RegistryMetadataError("instrument entry has no instrument_id")
        if ident in seen:
            raise RegistryMetadataError(
                f"instrument {ident!r} appears more than once. Identity must be "
                "unique or a reservation could bind to the wrong entry."
            )
        seen.add(ident)
        _validate_instrument(entry)

    for entry in registry.get("reservations", []):
        if not isinstance(entry, dict):
            raise RegistryMetadataError(
                f"reservation entries must be objects, found "
                f"{type(entry).__name__}"
            )
        _validate_reservation(entry, seen)

    for entry in registry.get("consumed_windows", []):
        if not isinstance(entry, dict):
            raise RegistryMetadataError(
                f"consumed window entries must be objects, found "
                f"{type(entry).__name__}"
            )
        _validate_consumed(entry, seen)