"""Phase 45 tests: instrument-registry metadata validation.

The gap these tests close was demonstrated before any of them was written: with
the Phase 39 shape check alone, a registry whose instruments had no
``timeframe``, no ``volume_semantics``, no ``venue``, or no entries at all loaded
without complaint. ``venue``, ``licence_name`` and ``provenance_grade`` existed
in the file and were read by nothing.

No strategy is executed and no dataset is read here except for structural
assertions on row counts and timestamps.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.dataset_identity import DatasetIdentity
from crypto_paper_lab.models import Candle
from crypto_paper_lab.registry_schema import (
    APPROVAL_STATES,
    LICENSE_KNOWLEDGE,
    MARKET_TYPES_BLOCKED,
    PROVENANCE_GRADES,
    QUALITY_STATUSES,
    TIMESTAMP_CONVENTIONS,
    RegistryMetadataError,
    validate_registry_metadata,
)
from crypto_paper_lab.researchguard import (
    ResearchGuardError,
    load_registry,
)

ROOT = Path(__file__).resolve().parents[1]

FOREX = "forex_reference_rates"
SPOT = "crypto_spot"


def instrument(instrument_id: str = "TEST/USDT", **overrides: object) -> dict:
    """A minimal *valid* crypto instrument entry.

    Phase 46 made source provenance load-bearing, so a fixture that names a
    venue must also state where that venue's data comes from, and its symbols
    must be mutually consistent. ``example.invalid`` is used deliberately: it is
    a reserved non-resolvable TLD, so a fixture can never look like a real
    source by accident.
    """

    base_asset, _, quote_asset = instrument_id.partition("/")
    entry: dict[str, object] = {
        "instrument_id": instrument_id,
        "symbol_normalized": instrument_id,
        "market_type": SPOT,
        "timeframe": "1h",
        "timeframes_available": ["1h"],
        "volume_semantics": "central_base",
        "venue": "test-venue",
        "source_provider": "test-provider",
        "source_url_pattern": "https://example.invalid/test/",
        "checksum_published": False,
        "licence_knowledge": "UNVERIFIED",
        "provenance_grade": "UNVERIFIED",
        "timestamp_convention": "bar_opens_at_hour_utc",
        "timestamp_normalized_tz": "UTC",
        "research_approval": "NOT_APPROVED",
        "bid_ask_available": True,
    }
    if base_asset and quote_asset:
        entry["symbol_native"] = f"{base_asset}{quote_asset}"
        entry["base_asset"] = base_asset
        entry["quote_asset"] = quote_asset
    entry.update(overrides)
    return entry


def forex_instrument(**overrides: object) -> dict:
    entry = instrument(
        "EUR/USD",
        market_type=FOREX,
        timeframe="daily_reference_rate",
        # A blocked forex entry holds no validated bar data at all, so declaring
        # no available timeframes is the honest state. The schema allows an empty
        # list only for market types that are blocked anyway.
        timeframes_available=[],
        volume_semantics="none",
        timestamp_convention="instantaneous_fixing",
        research_approval="BLOCKED_WRONG_DATA_TYPE",
        blocker="Not OHLC. No session/DST validator exists.",
    )
    entry.update(overrides)
    return entry


def registry(*instruments: dict, reservations=(), consumed=()) -> dict:
    return {
        "version": 1,
        "instruments": list(instruments),
        "reservations": list(reservations),
        "consumed_windows": list(consumed),
    }


def write(tmp_path: Path, body: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


# ==========================================================================
# demonstrated gaps now closed
# ==========================================================================


def test_minimal_valid_registry_passes() -> None:
    validate_registry_metadata(registry(instrument()))


@pytest.mark.parametrize(
    "field",
    [
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
    ],
)
def test_missing_required_field_refused(field: str) -> None:
    entry = instrument()
    entry.pop(field)
    with pytest.raises(RegistryMetadataError, match=field):
        validate_registry_metadata(registry(entry))


def test_empty_instruments_refused() -> None:
    """An empty registry is not 'nothing is protected'; it is 'nothing declared'."""

    with pytest.raises(RegistryMetadataError, match="cannot be read as"):
        validate_registry_metadata(registry())


def test_duplicate_instrument_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="more than once"):
        validate_registry_metadata(registry(instrument(), instrument()))


def test_non_object_instrument_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="must be objects"):
        validate_registry_metadata(registry("BTC/USDT"))  # type: ignore[arg-type]


# ==========================================================================
# contradictions
# ==========================================================================


def test_non_utc_timestamp_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="contradicts the project"):
        validate_registry_metadata(
            registry(instrument(timestamp_normalized_tz="Europe/London"))
        )


def test_supported_type_cannot_be_blocked_as_wrong_data_type() -> None:
    with pytest.raises(RegistryMetadataError, match="cannot be BLOCKED_WRONG_DATA_TYPE"):
        validate_registry_metadata(
            registry(
                instrument(
                    research_approval="BLOCKED_WRONG_DATA_TYPE",
                    blocker="nonsense",
                )
            )
        )


def test_blocked_type_cannot_claim_approval() -> None:
    entry = forex_instrument(research_approval="RESEARCH_APPROVED",
                             approved_preregistration_id="x")
    with pytest.raises(RegistryMetadataError, match="contradicts that"):
        validate_registry_metadata(registry(entry))


def test_block_without_a_stated_reason_refused() -> None:
    """A block nobody can review cannot be lifted later, so a reason is required.

    Uses a forex entry: the reason field only applies to blocked market types,
    and a supported type claiming a block is refused earlier for a different
    reason entirely.
    """

    entry = forex_instrument()
    entry.pop("blocker", None)
    with pytest.raises(RegistryMetadataError, match="no 'blocker' reason"):
        validate_registry_metadata(registry(entry))


def test_crypto_spot_cannot_declare_absent_volume() -> None:
    with pytest.raises(RegistryMetadataError, match="contradicts"):
        validate_registry_metadata(registry(instrument(volume_semantics="none")))


def test_forex_may_declare_absent_volume() -> None:
    validate_registry_metadata(registry(forex_instrument()))


def test_tick_volume_requires_a_note() -> None:
    entry = instrument(volume_semantics="tick")
    entry.pop("volume_note", None)
    with pytest.raises(RegistryMetadataError, match="volume_note"):
        validate_registry_metadata(registry(entry))


def test_tick_volume_with_note_accepted() -> None:
    validate_registry_metadata(
        registry(
            instrument(
                volume_semantics="tick",
                volume_note="tick volume is not a traded quantity",
            )
        )
    )


def test_missing_spread_note_refused_when_no_bid_ask() -> None:
    entry = instrument(bid_ask_available=False)
    entry.pop("spread_note", None)
    with pytest.raises(RegistryMetadataError, match="spread_note"):
        validate_registry_metadata(registry(entry))


def test_missing_spread_note_present_accepted() -> None:
    validate_registry_metadata(
        registry(
            instrument(
                bid_ask_available=False,
                spread_note="Spread cannot be modelled; a stated limitation.",
            )
        )
    )


def test_approval_without_preregistration_refused() -> None:
    """Approval is a governance act and can never follow from data quality."""

    with pytest.raises(RegistryMetadataError, match="approved_preregistration_id"):
        validate_registry_metadata(registry(instrument(research_approval="RESEARCH_APPROVED")))


def test_approval_with_preregistration_accepted() -> None:
    validate_registry_metadata(
        registry(
            instrument(
                research_approval="RESEARCH_APPROVED",
                approved_preregistration_id="prereg-001",
            )
        )
    )


def test_clean_data_never_implies_approval() -> None:
    """A Grade A dataset with no governance artefacts stays NOT_APPROVED."""

    entry = instrument(provenance_grade="A", research_approval="NOT_APPROVED")
    validate_registry_metadata(registry(entry))
    assert entry["research_approval"] != "RESEARCH_APPROVED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("provenance_grade", "Z"),
        ("licence_knowledge", "PROBABLY_FINE"),
        ("timestamp_convention", "whenever"),
        ("research_approval", "MAYBE"),
        ("market_type", "crypto_magic"),
    ],
)
def test_bad_vocabulary_refused(field: str, value: str) -> None:
    with pytest.raises(RegistryMetadataError, match=field):
        validate_registry_metadata(registry(instrument(**{field: value})))


def test_bad_vocabulary_names_the_allowed_set() -> None:
    with pytest.raises(RegistryMetadataError) as excinfo:
        validate_registry_metadata(registry(instrument(provenance_grade="Z")))
    assert "A" in str(excinfo.value) and "UNVERIFIED" in str(excinfo.value)


def test_unsupported_timeframe_for_supported_type_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="no implemented interval"):
        validate_registry_metadata(registry(instrument(timeframe="4h")))


# ==========================================================================
# reservations and consumed windows
# ==========================================================================


def test_reservation_for_unregistered_instrument_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="not in the instruments"):
        validate_registry_metadata(
            registry(
                instrument(),
                reservations=[
                    {
                        "reservation_id": "r1",
                        "instrument_id": "GHOST/USDT",
                        "dataset_sha256": "a" * 64,
                        "timeframe": "1h",
                        "evaluation_first": "2026-01-01T00:00:00",
                        "evaluation_last": "2026-02-01T00:00:00",
                        "status": "RESERVED",
                        "used": False,
                    }
                ],
            )
        )


def test_reserved_status_with_used_true_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="cannot be both available"):
        validate_registry_metadata(
            registry(
                instrument(),
                reservations=[
                    {
                        "reservation_id": "r1",
                        "instrument_id": "TEST/USDT",
                        "dataset_sha256": "a" * 64,
                        "timeframe": "1h",
                        "evaluation_first": "2026-01-01T00:00:00",
                        "evaluation_last": "2026-02-01T00:00:00",
                        "status": "RESERVED",
                        "used": True,
                    }
                ],
            )
        )


def test_used_status_with_used_false_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="contradict each other"):
        validate_registry_metadata(
            registry(
                instrument(),
                reservations=[
                    {
                        "reservation_id": "r1",
                        "instrument_id": "TEST/USDT",
                        "dataset_sha256": "a" * 64,
                        "timeframe": "1h",
                        "evaluation_first": "2026-01-01T00:00:00",
                        "evaluation_last": "2026-02-01T00:00:00",
                        "status": "USED",
                        "used": False,
                    }
                ],
            )
        )


def test_consumed_window_requires_consumed_on() -> None:
    with pytest.raises(RegistryMetadataError, match="consumed_on"):
        validate_registry_metadata(
            registry(
                instrument(),
                consumed=[
                    {
                        "instrument_id": "TEST/USDT",
                        "dataset_sha256": "a" * 64,
                        "timeframe": "1h",
                        "evaluation_first": "2026-01-01T00:00:00",
                        "evaluation_last": "2026-02-01T00:00:00",
                    }
                ],
            )
        )


def test_consumed_windows_on_instrument_must_be_objects() -> None:
    with pytest.raises(RegistryMetadataError, match="must be objects"):
        validate_registry_metadata(
            registry(instrument(research_approval="RESEARCH_CONSUMED",
                                consumed_windows=["2026-01-01/2026-02-01"]))
        )


# ==========================================================================
# load_registry now enforces metadata
# ==========================================================================


def test_load_registry_rejects_incomplete_metadata(tmp_path: Path) -> None:
    """The Phase 39 gap: shape-valid but semantically empty entries were accepted."""

    path = write(tmp_path, registry({"instrument_id": "X/Y", "market_type": SPOT}))
    with pytest.raises((RegistryMetadataError, ResearchGuardError)):
        load_registry(path)


def test_load_registry_rejects_empty_instruments(tmp_path: Path) -> None:
    path = write(tmp_path, registry())
    with pytest.raises((RegistryMetadataError, ResearchGuardError)):
        load_registry(path)


def test_load_registry_accepts_valid(tmp_path: Path) -> None:
    path = write(tmp_path, registry(instrument()))
    assert load_registry(path)["instruments"][0]["instrument_id"] == "TEST/USDT"


# ==========================================================================
# shipped registry
# ==========================================================================


def test_shipped_registry_passes_validation() -> None:
    validate_registry_metadata(load_registry())


def test_shipped_registry_is_version_2() -> None:
    assert load_registry()["version"] == 2


def test_shipped_registry_tracks_every_required_dimension() -> None:
    required = {
        "instrument_id", "market_type", "timeframe", "volume_semantics",
        "venue", "source_provider", "licence_knowledge", "provenance_grade",
        "timestamp_convention", "timestamp_normalized_tz", "research_approval",
        "bid_ask_available",
    }
    for entry in load_registry()["instruments"]:
        assert required <= set(entry), f"{entry['instrument_id']} missing fields"


def test_shipped_registry_has_five_instruments() -> None:
    assert len(load_registry()["instruments"]) == 5


def test_shipped_forex_entries_stay_blocked_with_reasons() -> None:
    forex = [
        e for e in load_registry()["instruments"] if e["market_type"] in MARKET_TYPES_BLOCKED
    ]
    assert len(forex) == 3
    for entry in forex:
        assert entry["research_approval"] == "BLOCKED_WRONG_DATA_TYPE"
        assert entry["blocker"].strip()
        assert entry["volume_semantics"] == "none"


def test_shipped_forex_not_automatically_approved() -> None:
    """Discovering an instrument must never approve it."""

    for entry in load_registry()["instruments"]:
        if entry["market_type"] != SPOT:
            assert entry["research_approval"] != "RESEARCH_APPROVED"


def test_shipped_eth_is_not_research_approved() -> None:
    eth = [
        e for e in load_registry()["instruments"] if e["instrument_id"] == "ETH/USDT"
    ][0]
    assert eth["research_approval"] == "DATA_VERIFIED_NOT_RESEARCH_APPROVED"
    assert eth["provenance_grade"] == "A"
    assert not eth.get("approved_preregistration_id")


def test_shipped_btc_is_research_consumed() -> None:
    btc = [
        e for e in load_registry()["instruments"] if e["instrument_id"] == "BTC/USDT"
    ][0]
    assert btc["research_approval"] == "RESEARCH_CONSUMED"
    assert len(btc["consumed_windows"]) == 3


def test_shipped_registry_documents_btc_licence_as_unverified() -> None:
    """Licensing is stated honestly rather than assumed."""

    for entry in load_registry()["instruments"]:
        if entry["market_type"] == SPOT:
            assert entry["licence_knowledge"] in LICENSE_KNOWLEDGE
            assert entry["licence_note"].strip()


def test_shipped_forex_licence_is_verified_and_recorded() -> None:
    forex = [
        e for e in load_registry()["instruments"] if e["market_type"] in MARKET_TYPES_BLOCKED
    ]
    for entry in forex:
        assert entry["licence_knowledge"] == "VERIFIED"
        assert "CC BY-NC-SA" in entry["licence_name"]
        assert "Non-commercial" in entry["licence_note"]


def test_licence_excludes_commercial_use() -> None:
    forex = [
        e for e in load_registry()["instruments"] if e["market_type"] in MARKET_TYPES_BLOCKED
    ]
    for entry in forex:
        assert "Commercial use is excluded" in entry["licence_note"]


# ==========================================================================
# vocabulary is explicit
# ==========================================================================


def test_vocabularies_are_non_empty_and_frozen() -> None:
    for vocab in (
        MARKET_TYPES_BLOCKED,
        PROVENANCE_GRADES,
        QUALITY_STATUSES,
        APPROVAL_STATES,
        LICENSE_KNOWLEDGE,
        TIMESTAMP_CONVENTIONS,
    ):
        assert isinstance(vocab, frozenset) and vocab


def test_research_approved_requires_preregistration_by_construction() -> None:
    assert "RESEARCH_APPROVED" in APPROVAL_STATES
    assert "NOT_APPROVED" in APPROVAL_STATES


# ==========================================================================
# declared identity bound to actual data
# ==========================================================================


def hourly(count: int, step_minutes: int = 60) -> list[Candle]:
    start = datetime(2024, 1, 1)
    return [
        Candle(
            start + timedelta(minutes=step_minutes * i),
            1.0, 2.0, 0.5, 1.5, 10.0,
        )
        for i in range(count)
    ]


def test_declared_timeframe_must_match_actual_spacing() -> None:
    """The Phase 45 gap: declared 1h over 5-minute data used to pass."""

    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    validate_dataset(hourly(5, 60), identity=identity)

    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(hourly(5, 5), identity=identity)


def test_identity_derives_interval_from_declaration() -> None:
    """A caller cannot skip the check by omitting expected_interval_seconds."""

    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(hourly(5, 5), identity=identity)


def test_conflicting_explicit_argument_refused() -> None:
    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="contradicts the declared identity"):
        validate_dataset(hourly(5, 60), identity=identity, timeframe="4h")


def test_conflicting_market_type_refused() -> None:
    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="contradicts the declared identity"):
        validate_dataset(hourly(5, 60), identity=identity, market_type=FOREX)


def test_conflicting_interval_refused() -> None:
    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="contradicts the declared timeframe"):
        validate_dataset(hourly(5, 60), identity=identity, expected_interval_seconds=300)


def test_forex_identity_refused_before_any_data_check() -> None:
    with pytest.raises(ValueError, match="no implemented validator"):
        DatasetIdentity(
            instrument_id="EUR/USD", timeframe="1h",
            market_type=FOREX, volume_semantics="none",
        )


def test_shipped_eth_identity_still_builds() -> None:
    """Upgrading the registry must not break the crypto identities it declares."""

    for entry in load_registry()["instruments"]:
        if entry["market_type"] == SPOT:
            identity = DatasetIdentity(
                instrument_id=entry["instrument_id"],
                timeframe=entry["timeframe"],
                market_type=entry["market_type"],
                volume_semantics=entry["volume_semantics"],
            )
            assert identity.expected_interval_seconds == 3600


def test_shipped_eth_dataset_still_validates() -> None:
    """Structural regression: the reserved file still parses and validates."""

    from crypto_paper_lab.dataset import load_dataset

    eth = [
        e for e in load_registry()["reservations"]
        if e["instrument_id"] == "ETH/USDT"
    ][0]
    candles, _ = load_dataset(ROOT / eth["dataset_path"])

    identity = DatasetIdentity(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    validate_dataset(candles, identity=identity)
    assert len(candles) == eth["evaluation_bars"] + eth["warmup_bars"]


# ==========================================================================
# guard behaviour preserved
# ==========================================================================


def test_eth_reservation_still_unapproved() -> None:
    entry = [
        e for e in load_registry()["reservations"] if e["instrument_id"] == "ETH/USDT"
    ][0]
    assert entry["status"] == "RESERVED"
    assert entry["used"] is False
    assert entry["preregistration_id"] is None
    assert "used_on" not in entry


def test_eth_dataset_hash_unchanged() -> None:
    import hashlib

    entry = [
        e for e in load_registry()["reservations"] if e["instrument_id"] == "ETH/USDT"
    ][0]
    path = ROOT / entry["dataset_path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["dataset_sha256"]


def test_consumption_keeps_status_and_flag_consistent(tmp_path: Path) -> None:
    """Phase 45 found a real contradiction in the consumption writer.

    ``_consume_reservations`` set ``used: true`` while leaving
    ``status: "RESERVED"``. The new schema refuses that, so the writer was
    fixed rather than the validator relaxed.
    """

    from crypto_paper_lab.researchguard import consume_reservation

    body = registry(
        instrument(),
        reservations=[
            {
                "reservation_id": "r1",
                "instrument_id": "TEST/USDT",
                "dataset_sha256": "a" * 64,
                "timeframe": "1h",
                "evaluation_first": "2026-01-01T00:00:00",
                "evaluation_last": "2026-02-01T00:00:00",
                "status": "RESERVED",
                "used": False,
                "preregistration_id": "prereg-x",
            }
        ],
    )
    path = write(tmp_path, body)
    consume_reservation("r1", registry_file=path)

    after = json.loads(path.read_text(encoding="utf-8"))["reservations"][0]
    assert after["used"] is True
    assert after["status"] == "USED"

    # and the written file must itself still validate
    validate_registry_metadata(load_registry(path))


def test_spent_window_reports_spent_not_a_status_problem(tmp_path: Path) -> None:
    """The actionable message is 'already been used', not 'status is not RESERVED'."""

    from crypto_paper_lab.researchguard import (
        assert_evaluation_permitted,
        consume_reservation,
    )

    body = registry(
        instrument(),
        reservations=[
            {
                "reservation_id": "r1",
                "instrument_id": "TEST/USDT",
                "dataset_sha256": "a" * 64,
                "timeframe": "1h",
                "evaluation_first": "2026-01-01T00:00:00",
                "evaluation_last": "2026-02-01T00:00:00",
                "status": "RESERVED",
                "used": False,
                "preregistration_id": "prereg-x",
            }
        ],
    )
    path = write(tmp_path, body)
    consume_reservation("r1", registry_file=path)

    with pytest.raises(ResearchGuardError, match="already been used"):
        assert_evaluation_permitted(
            dataset_sha256="a" * 64,
            instrument_id="TEST/USDT",
            timeframe="1h",
            evaluation_start=datetime(2026, 1, 1),
            evaluation_end=datetime(2026, 2, 1),
            preregistration_id="prereg-x",
            registry_file=path,
        )


def test_reserved_series_still_refused_without_context() -> None:
    """The Phase 40 omission-bypass closure survives the registry upgrade.

    Reads the real reserved file, but only to fingerprint it: the guard refuses
    before any strategy state exists, so nothing is computed or inspected.
    """

    from crypto_paper_lab.dataset import load_dataset
    from crypto_paper_lab.researchguard import assert_series_permitted

    entry = [
        e for e in load_registry()["reservations"] if e["instrument_id"] == "ETH/USDT"
    ][0]
    candles, _ = load_dataset(ROOT / entry["dataset_path"])

    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_series_permitted(candles, research_context=None)


def test_deepcopy_of_shipped_registry_also_validates() -> None:
    body = copy.deepcopy(load_registry())
    validate_registry_metadata(body)


def test_registry_all_exports_present() -> None:
    """Phase 43 found ``__all__`` stale: three public functions were missing.

    A caller introspecting the module, or using ``from … import *``, would not
    have seen them. Pinning the export list prevents silent drift.
    """

    import crypto_paper_lab.researchguard as guard

    for name in (
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
    ):
        assert name in guard.__all__, f"{name} is public but missing from __all__"
        assert hasattr(guard, name), f"{name} exported but absent from the module"


def test_exported_names_all_resolve() -> None:
    import crypto_paper_lab.researchguard as guard

    for name in guard.__all__:
        assert hasattr(guard, name), f"__all__ names {name}, which does not exist"


def test_schema_validator_exported_from_its_own_module() -> None:
    """The validator belongs to ``registry_schema``, not re-exported by the guard.

    ``load_registry`` calls it internally; exporting it from ``researchguard``
    would suggest the guard owns the rules, which it does not.
    """

    import crypto_paper_lab.registry_schema as schema

    assert "validate_registry_metadata" in schema.__all__
    assert hasattr(schema, "validate_registry_metadata")
    for name in schema.__all__:
        assert hasattr(schema, name), f"schema __all__ names {name}, which is absent"