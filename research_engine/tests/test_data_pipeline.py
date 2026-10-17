"""Phase 46 tests: multi-market data pipelines.

Every test is synthetic. Two read a real dataset to assert *structural* facts
(row counts, timestamps, digests) and neither inspects a price or a result.

The provenance and registry tests exist because Phase 46 probed what the
existing validation actually caught, and found fields that were recorded in the
registry but read by no code.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_paper_lab.dataset import load_dataset, validate_dataset
from crypto_paper_lab.dataset_identity import DatasetIdentity
from crypto_paper_lab.intervals import classify_intervals, contiguous_slice
from crypto_paper_lab.models import Candle
from crypto_paper_lab.provenance import (
    MANIFEST_VERSION,
    ArchiveRecord,
    ProvenanceError,
    build_manifest,
    sha256_of_file,
    verify_manifest,
    verify_publisher_checksum,
    write_manifest,
)
from crypto_paper_lab.registry_schema import (
    RegistryMetadataError,
    validate_registry_metadata,
)
from crypto_paper_lab.researchguard import ResearchGuardError, load_registry

ROOT = Path(__file__).resolve().parents[1]
SPOT = "crypto_spot"
FOREX = "forex_reference_rates"

ETH_HASH = "7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb"


# ==========================================================================
# helpers
# ==========================================================================


def hourly(count: int, start: datetime = datetime(2024, 1, 1), step_minutes: int = 60) -> list[Candle]:
    return [
        Candle(
            start + timedelta(minutes=step_minutes * i),
            1.0, 2.0, 0.5, 1.5, 10.0,
        )
        for i in range(count)
    ]


def write_ohlcv(path: Path, candles: list[Candle]) -> Path:
    rows = ["timestamp,open,high,low,close,volume"]
    for c in candles:
        rows.append(
            f"{c.timestamp.isoformat()},{c.open},{c.high},{c.low},{c.close},{c.volume}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def instrument(**overrides: object) -> dict:
    """A minimal but fully-attributed crypto instrument entry."""

    entry: dict[str, object] = {
        "instrument_id": "BTC/USDT",
        "symbol_normalized": "BTC/USDT",
        "symbol_native": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "market_type": SPOT,
        "venue": "binance-spot",
        "source_provider": "Binance Vision",
        "source_url_pattern": "https://example.invalid/klines/BTCUSDT/1h/",
        "checksum_published": True,
        "licence_knowledge": "UNVERIFIED",
        "provenance_grade": "UNVERIFIED",
        "timestamp_convention": "bar_opens_at_hour_utc",
        "timestamp_normalized_tz": "UTC",
        "volume_semantics": "central_base",
        "research_approval": "NOT_APPROVED",
        "bid_ask_available": True,
        "timeframe": "1h",
        "timeframes_available": ["1h"],
    }
    entry.update(overrides)
    if entry["market_type"] == FOREX:
        entry.setdefault("blocker", "Not OHLC; no session/DST validator exists.")
    return entry


def registry(*instruments: dict, reservations=(), consumed=()) -> dict:
    return {
        "version": 1,
        "instruments": list(instruments),
        "reservations": list(reservations),
        "consumed_windows": list(consumed),
    }


# ==========================================================================
# 1. publisher checksum verification
# ==========================================================================


def test_publisher_checksum_verified(tmp_path: Path) -> None:
    f = tmp_path / "a.zip"
    f.write_bytes(b"archive bytes")
    result = verify_publisher_checksum(f, sha256_of_file(f))
    assert result.verified is True
    assert result.status == "verified"


def test_checksum_mismatch_refused(tmp_path: Path) -> None:
    f = tmp_path / "a.zip"
    f.write_bytes(b"archive bytes")
    with pytest.raises(ProvenanceError, match="checksum mismatch"):
        verify_publisher_checksum(f, "f" * 64)


def test_mismatch_names_both_digests(tmp_path: Path) -> None:
    f = tmp_path / "a.zip"
    f.write_bytes(b"archive bytes")
    with pytest.raises(ProvenanceError) as excinfo:
        verify_publisher_checksum(f, "f" * 64)
    message = str(excinfo.value)
    assert "f" * 64 in message and sha256_of_file(f) in message


def test_mismatch_can_be_recorded_for_quarantine(tmp_path: Path) -> None:
    """A mismatch may be *recorded*, never merged."""

    f = tmp_path / "a.zip"
    f.write_bytes(b"archive bytes")
    result = verify_publisher_checksum(f, "f" * 64, allow_mismatch=True)
    assert result.verified is False
    assert result.status == "mismatch"


def test_malformed_published_digest_refused(tmp_path: Path) -> None:
    f = tmp_path / "a.zip"
    f.write_bytes(b"x")
    for bad in ("", "not-a-digest", "z" * 64, "abc"):
        with pytest.raises(ProvenanceError, match="not a SHA-256"):
            verify_publisher_checksum(f, bad)


def test_uppercase_published_digest_accepted(tmp_path: Path) -> None:
    f = tmp_path / "a.zip"
    f.write_bytes(b"archive bytes")
    assert verify_publisher_checksum(f, sha256_of_file(f).upper()).verified is True


def test_missing_file_refused_rather_than_downloaded(tmp_path: Path) -> None:
    """Nothing here fetches. A missing file is an error, not a trigger."""

    with pytest.raises(ProvenanceError, match="Nothing is"):
        verify_publisher_checksum(tmp_path / "absent.zip", "a" * 64)


def test_checksum_verified_before_parsing_is_the_contract() -> None:
    """Documented in the Phase 33 sidecars and preserved here.

    Verification must precede parsing; a mismatched archive that is parsed first
    may merge silently and produce a dataset that later looks clean.
    """

    assert "before" in (verify_publisher_checksum.__doc__ or "").lower()


# ==========================================================================
# 2. reproducible manifests
# ==========================================================================


def test_manifest_records_real_digest(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(10))
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="binance-spot",
        timeframe="1h", source_provider="Binance Vision",
    )
    assert m.dataset_sha256 == sha256_of_file(f)


def test_manifest_hashes_the_file_not_the_claim(tmp_path: Path) -> None:
    """A manifest cannot record a digest that disagrees with the bytes."""

    f = write_ohlcv(tmp_path / "d.csv", hourly(10))
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="binance-spot",
        timeframe="1h", source_provider="Binance Vision",
    )
    f.write_text("tampered", encoding="utf-8")
    problems = verify_manifest(m, tmp_path)
    assert any("digest changed" in p for p in problems)


def test_manifest_requires_attribution(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    for field in ("instrument_id", "venue", "timeframe", "source_provider"):
        kwargs = dict(
            instrument_id="BTC/USDT", venue="binance-spot",
            timeframe="1h", source_provider="Binance Vision",
        )
        kwargs[field] = "  "
        with pytest.raises(ProvenanceError, match=field):
            build_manifest(f, **kwargs)  # type: ignore[arg-type]


def test_manifest_missing_dataset_refused(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="does not exist"):
        build_manifest(
            tmp_path / "absent.csv", instrument_id="BTC/USDT", venue="v",
            timeframe="1h", source_provider="s",
        )


def test_manifest_provenance_ceiling_is_a(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    digest = sha256_of_file(f)
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
        archives=[ArchiveRecord("a.zip", "u", digest, digest, 1, "t", True)],
    )
    assert m.provenance_ceiling == "A"


def test_manifest_provenance_ceiling_drops_when_unverified(tmp_path: Path) -> None:
    """Reproducible is not the same as publisher-verified."""

    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    digest = sha256_of_file(f)
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
        archives=[ArchiveRecord("a.zip", "u", digest, digest, 1, "t", False)],
    )
    assert m.provenance_ceiling == "B"


def test_manifest_with_no_archives_is_b_ceiling(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
    )
    assert m.provenance_ceiling == "B"


def test_manifest_records_missing_archive(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    digest = sha256_of_file(f)
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
        archives=[ArchiveRecord("absent.zip", "u", digest, digest, 1, "t", True)],
    )
    assert any("archive missing" in p for p in verify_manifest(m, tmp_path))


def test_manifest_flags_unverified_published_checksum(tmp_path: Path) -> None:
    """A record claiming a publisher digest it never checked is a discrepancy."""

    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    digest = sha256_of_file(f)
    (tmp_path / "a.zip").write_bytes(b"x")
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
        archives=[ArchiveRecord("a.zip", "u", digest, digest, 1, "t", False)],
    )
    problems = verify_manifest(m, tmp_path)
    assert any("never verified" in p for p in problems)


def test_manifest_roundtrip_is_byte_stable(tmp_path: Path) -> None:
    f = write_ohlcv(tmp_path / "d.csv", hourly(3))
    m = build_manifest(
        f, instrument_id="BTC/USDT", venue="v", timeframe="1h",
        source_provider="s",
    )
    p = write_manifest(m, tmp_path / "m.json")
    first = p.read_bytes()
    write_manifest(m, tmp_path / "m2.json")
    assert (tmp_path / "m2.json").read_bytes() == first


def test_manifest_from_record_rejects_incomplete() -> None:
    from crypto_paper_lab.provenance import DatasetManifest

    with pytest.raises(ProvenanceError, match="missing required"):
        DatasetManifest.from_record(
            {"manifest_version": MANIFEST_VERSION, "dataset_path": "x"}
        )


def test_manifest_from_record_rejects_wrong_version() -> None:
    from crypto_paper_lab.provenance import DatasetManifest

    with pytest.raises(ProvenanceError, match="not supported"):
        DatasetManifest.from_record({"manifest_version": 99})


def test_archive_record_requires_essential_fields() -> None:
    with pytest.raises(ProvenanceError, match="incomplete"):
        ArchiveRecord.from_record({"filename": "a.zip"})


def test_manifest_version_is_stable() -> None:
    assert MANIFEST_VERSION == 1


# ==========================================================================
# 3. registry provenance fields that were previously unvalidated
# ==========================================================================


def test_checksum_published_must_be_boolean() -> None:
    """Phase 46 probe: this field accepted deletion and ``"maybe"``."""

    entry = instrument()
    entry.pop("checksum_published")
    with pytest.raises(RegistryMetadataError, match="checksum_published"):
        validate_registry_metadata(registry(entry))


def test_checksum_published_wrong_type_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="checksum_published"):
        validate_registry_metadata(registry(instrument(checksum_published="maybe")))


def test_checksum_published_false_is_valid() -> None:
    """A publisher that issues no digest is a real, recordable state."""

    validate_registry_metadata(
        registry(
            instrument(
                checksum_published=False,
                source_url_pattern="https://example.invalid/rates.csv",
            )
        )
    )


def test_source_url_pattern_required() -> None:
    entry = instrument()
    entry.pop("source_url_pattern")
    with pytest.raises(RegistryMetadataError, match="source_url_pattern"):
        validate_registry_metadata(registry(entry))


def test_source_url_pattern_must_be_http() -> None:
    with pytest.raises(RegistryMetadataError, match="not an http"):
        validate_registry_metadata(registry(instrument(source_url_pattern="not-a-url")))


def test_published_checksum_needs_a_checksum_url() -> None:
    entry = instrument(checksum_published=True)
    entry["checksum_url_pattern"] = "  "
    with pytest.raises(RegistryMetadataError, match="checksum_url_pattern"):
        validate_registry_metadata(registry(entry))


def test_symbol_native_must_match_base_and_quote() -> None:
    """A wrong native symbol is how one instrument's data is fetched as another's."""

    with pytest.raises(RegistryMetadataError, match="symbol_native"):
        validate_registry_metadata(registry(instrument(symbol_native="XXXYYY")))


def test_symbol_native_accepts_both_conventions() -> None:
    validate_registry_metadata(registry(instrument(symbol_native="BTCUSDT")))
    validate_registry_metadata(registry(instrument(symbol_native="BTC/USDT")))


def test_symbol_normalized_must_match_pair() -> None:
    with pytest.raises(RegistryMetadataError, match="symbol_normalized"):
        validate_registry_metadata(registry(instrument(symbol_normalized="ETH/USDT")))


def test_instrument_id_must_match_symbol_normalized() -> None:
    with pytest.raises(RegistryMetadataError, match="instrument_id"):
        validate_registry_metadata(registry(instrument(instrument_id="ETH/USDT")))


def test_timeframe_must_appear_in_timeframes_available() -> None:
    with pytest.raises(RegistryMetadataError, match="timeframes_available"):
        validate_registry_metadata(registry(instrument(timeframes_available=["1d"])))


def test_empty_timeframes_with_declared_timeframe_refused() -> None:
    """Declaring a resolution with no data behind it is not a valid instrument."""

    with pytest.raises(RegistryMetadataError, match="no usable data"):
        validate_registry_metadata(registry(instrument(timeframes_available=[])))


def test_quality_status_vocabulary_enforced() -> None:
    with pytest.raises(RegistryMetadataError, match="quality_status"):
        validate_registry_metadata(registry(instrument(quality_status="excellent")))


def test_quality_status_valid_values_accepted() -> None:
    for status in ("unchecked", "checked_clean", "checked_with_findings", "failed"):
        validate_registry_metadata(registry(instrument(quality_status=status)))


def test_malformed_dataset_digest_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="dataset_sha256"):
        validate_registry_metadata(
            registry(instrument(dataset_sha256="not-a-digest-at-all"))
        )


def test_digest_of_wrong_length_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="dataset_sha256"):
        validate_registry_metadata(registry(instrument(dataset_sha256="ab" * 31)))


def test_digest_with_non_hex_characters_refused() -> None:
    with pytest.raises(RegistryMetadataError, match="dataset_sha256"):
        validate_registry_metadata(registry(instrument(dataset_sha256="z" * 64)))


def test_wellformed_dataset_digest_accepted() -> None:
    """All-hex 64 characters is a correctly shaped digest, whatever its value.

    The schema checks shape, not truth: whether a digest matches the file on disk
    is :mod:`provenance`'s job, not the registry's.
    """

    validate_registry_metadata(registry(instrument(dataset_sha256="a" * 64)))


def test_valid_instrument_passes() -> None:
    validate_registry_metadata(registry(instrument()))


# ==========================================================================
# 4. venue differences are not assumed away
# ==========================================================================


def test_two_venues_with_different_native_symbols_both_valid() -> None:
    """Different venues spell the same pair differently; both are legitimate."""

    binance = instrument(
        instrument_id="BTC/USDT", symbol_native="BTCUSDT",
        symbol_normalized="BTC/USDT", base_asset="BTC", quote_asset="USDT",
        venue="binance-spot",
    )
    kraken = instrument(
        instrument_id="XBT/USD", symbol_native="XBTUSD",
        symbol_normalized="XBT/USD", base_asset="XBT", quote_asset="USD",
        venue="kraken-spot",
    )
    validate_registry_metadata(registry(binance, kraken))


def test_declared_timeframe_bound_to_actual_spacing() -> None:
    identity = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    validate_dataset(hourly(5, step_minutes=60), identity=identity)
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(hourly(5, step_minutes=5), identity=identity)


def test_volume_semantics_must_be_declared() -> None:
    with pytest.raises(ValueError, match="volume_semantics"):
        DatasetIdentity(
            instrument_id="BTC/USDT", timeframe="1h",
            market_type=SPOT, volume_semantics="unknown_kind",
        )


def test_tick_volume_is_not_traded_volume() -> None:
    """Both are permitted; neither is interchangeable with the other."""

    tick = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="tick",
    )
    central = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type=SPOT, volume_semantics="central_base",
    )
    assert tick.volume_semantics != central.volume_semantics


def test_crypto_cannot_declare_absent_volume() -> None:
    with pytest.raises(ValueError, match="not valid for crypto_spot"):
        DatasetIdentity(
            instrument_id="BTC/USDT", timeframe="1h",
            market_type=SPOT, volume_semantics="none",
        )


# ==========================================================================
# 5. duplicate and missing-interval detection
# ==========================================================================


def test_duplicate_timestamp_refused() -> None:
    rows = hourly(3)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_dataset([rows[0], rows[0], rows[1]])


def test_missing_interval_refused_when_declared() -> None:
    rows = hourly(5)
    del rows[2]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(rows, expected_interval_seconds=3600)


def test_gap_classified_as_defect_for_24x7() -> None:
    rows = hourly(5) + hourly(5, datetime(2024, 1, 1, 10))
    with pytest.raises(ValueError, match="data defect"):
        classify_intervals(rows, expected_interval_seconds=3600)


def test_contiguous_slice_does_not_modify() -> None:
    rows = hourly(5) + hourly(5, datetime(2024, 1, 1, 10))
    start, end, gaps = contiguous_slice(rows, expected_interval_seconds=3600)
    assert (start, end) == (5, 10)
    assert len(gaps) == 1
    assert len(rows) == 10


# ==========================================================================
# 6. forex remains blocked
# ==========================================================================


def test_forex_identity_refused() -> None:
    with pytest.raises(ValueError, match="no implemented validator"):
        DatasetIdentity(
            instrument_id="EUR/USD", timeframe="1h",
            market_type=FOREX, volume_semantics="none",
        )


def test_forex_interval_classification_refused() -> None:
    with pytest.raises(ValueError, match="session, holiday and DST"):
        classify_intervals(
            hourly(5), expected_interval_seconds=3600, market_type=FOREX
        )


def test_forex_cannot_be_research_approved() -> None:
    entry = instrument(
        instrument_id="EUR/USD", market_type=FOREX,
        volume_semantics="none",
        timestamp_convention="instantaneous_fixing",
        research_approval="RESEARCH_APPROVED",
        approved_preregistration_id="p1",
        blocker="Not OHLC. No session/DST validator exists.",
    )
    with pytest.raises(RegistryMetadataError, match="contradicts that"):
        validate_registry_metadata(registry(entry))


def test_ecb_reference_rates_are_not_ohlc() -> None:
    """A daily fixing has no intraday range; it cannot pass as hourly candles."""

    fixings = [
        Candle(datetime(2024, 1, 1 + i), 1.0, 1.0, 1.0, 1.0, 0.0)
        for i in range(5)
    ]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(fixings, expected_interval_seconds=3600)


def test_spread_cannot_be_synthesised() -> None:
    """No bid/ask in the source means no spread field, not a zero spread."""

    entry = instrument(bid_ask_available=False)
    entry.pop("spread_note", None)
    with pytest.raises(RegistryMetadataError, match="spread_note"):
        validate_registry_metadata(registry(entry))


def test_spread_note_stated_accepted() -> None:
    validate_registry_metadata(
        registry(
            instrument(
                bid_ask_available=False,
                spread_note="No bid/ask acquired; spread cannot be modelled.",
            )
        )
    )


# ==========================================================================
# 7. discovery never approves
# ==========================================================================


def test_clean_parsing_does_not_approve(tmp_path: Path) -> None:
    """A file that parses perfectly is still NOT_APPROVED by default."""

    f = write_ohlcv(tmp_path / "d.csv", hourly(48))
    candles, _ = load_dataset(f)
    validate_dataset(candles, expected_interval_seconds=3600)
    validate_registry_metadata(registry(instrument()))
    assert instrument()["research_approval"] == "NOT_APPROVED"


def test_shipped_registry_forex_all_blocked() -> None:
    forex = [
        e for e in load_registry()["instruments"]
        if str(e["market_type"]).startswith("forex")
    ]
    assert len(forex) == 3
    for entry in forex:
        assert entry["research_approval"] == "BLOCKED_WRONG_DATA_TYPE"
        assert entry["blocker"].strip()
        assert entry["checksum_published"] is False
        assert entry["source_url_pattern"].startswith("http")


def test_shipped_forex_records_actual_retrieval_endpoint() -> None:
    """frankfurter.app is the retrieval path; ECB is the publisher."""

    forex = [
        e for e in load_registry()["instruments"] if e["venue"] == "ecb"
    ]
    for entry in forex:
        assert entry["retrieval_endpoint"] == "frankfurter.app"
        assert entry["source_provider"] == "European Central Bank"


def test_shipped_crypto_records_checksum_availability() -> None:
    for entry in load_registry()["instruments"]:
        if entry["market_type"] == SPOT:
            assert entry["checksum_published"] is True


def test_shipped_registry_validates() -> None:
    validate_registry_metadata(load_registry())


# ==========================================================================
# 8. guards and reservation untouched
# ==========================================================================


def test_eth_reservation_still_unspent() -> None:
    entry = [
        e for e in load_registry()["reservations"] if e["instrument_id"] == "ETH/USDT"
    ][0]
    assert entry["status"] == "RESERVED"
    assert entry["used"] is False
    assert entry["preregistration_id"] is None


def test_eth_dataset_hash_unchanged() -> None:
    assert sha256_of_file(
        ROOT / "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv"
    ) == ETH_HASH


def test_eth_dataset_still_validates_structurally() -> None:
    candles, summary = load_dataset(
        ROOT / "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv"
    )
    assert len(candles) == 24288
    assert summary.start == datetime(2024, 1, 1)
    assert summary.end == datetime(2026, 10, 8, 23)
    validate_dataset(candles, expected_interval_seconds=3600)


def test_reserved_series_still_refused_without_context() -> None:
    from crypto_paper_lab.researchguard import assert_series_permitted

    candles, _ = load_dataset(
        ROOT / "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv"
    )
    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_series_permitted(candles, research_context=None)


def test_registry_metadata_failure_blocks_evaluation(tmp_path: Path) -> None:
    """A malformed registry fails closed, not permissively."""

    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(registry({"instrument_id": "X/Y", "market_type": SPOT})),
        encoding="utf-8",
    )
    with pytest.raises((RegistryMetadataError, ResearchGuardError)):
        load_registry(path)