"""Phase 39 research-integrity guard tests.

These tests exercise the *policy* only. They deliberately never run a strategy
over ETH 2026, so no ETH 2026 performance is produced or inspected here. Where a
backtest is used to prove the gate fires, it is refused by the guard before the
engine does any work.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.acquisition import AcquisitionReport, normalize_source
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.models import Candle
from crypto_paper_lab.researchguard import (
    MARKET_TYPES_SUPPORTED,
    OVERLAP_CHECKED,
    consume_reservation,
    OVERLAP_FAILED,
    OVERLAP_SKIPPED,
    VOLUME_SEMANTICS,
    CrossAssetAuthorization,
    ResearchContext,
    ResearchGuardError,
    assert_evaluation_permitted,
    assert_instrument_identity,
    assert_no_registered_range,
    load_registry,
    note_overlap_check,
)

SPOT = "crypto_spot"
ETH_HASH = "a" * 64
BTC_HASH = "b" * 64
ETH_FIRST = datetime(2026, 1, 1, 0, 0)
ETH_LAST = datetime(2026, 10, 8, 23, 0)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _instrument(
    instrument_id: str,
    market_type: str = SPOT,
    timeframe: str = "1h",
    volume_semantics: str = "central_base",
    **overrides: object,
) -> dict:
    """A minimal *valid* instrument entry.

    Phase 45 made registry metadata load-bearing: ``load_registry`` now refuses
    entries missing provenance, licensing or approval fields. Every field below
    is therefore required, and deliberately minimal rather than realistic --
    these are test fixtures, and inventing fake licence terms for them would be
    worse than an explicit ``UNVERIFIED``.
    """

    entry: dict[str, object] = {
        "instrument_id": instrument_id,
        "market_type": market_type,
        "timeframe": timeframe,
        "volume_semantics": volume_semantics,
        "venue": "test-venue",
        "source_provider": "test-provider",
        "licence_knowledge": "UNVERIFIED",
        "provenance_grade": "UNVERIFIED",
        "timestamp_convention": "bar_opens_at_hour_utc",
        "timestamp_normalized_tz": "UTC",
        "research_approval": "NOT_APPROVED",
        # Declared rather than omitted: a missing key is not the same as a
        # stated "false", and the schema checks these fields explicitly.
        "bid_ask_available": True,
        # Phase 46 made source provenance load-bearing. A fixture claiming a
        # venue must also state where that venue's data comes from; a fake URL
        # would be worse than an explicitly reserved test host.
        "symbol_normalized": instrument_id,
        "source_url_pattern": "https://example.invalid/test/",
        "checksum_published": False,
    }
    base_asset, _, quote_asset = instrument_id.partition("/")
    if base_asset and quote_asset:
        entry["symbol_native"] = f"{base_asset}{quote_asset}"
        entry["base_asset"] = base_asset
        entry["quote_asset"] = quote_asset
    entry["timeframes_available"] = [timeframe] if timeframe != "daily_reference_rate" else []
    if volume_semantics == "tick":
        entry["volume_note"] = "tick volume is not a traded quantity"
    if market_type != SPOT:
        entry["blocker"] = "test fixture: blocked market type"
        entry["research_approval"] = "BLOCKED_WRONG_DATA_TYPE"
    entry.update(overrides)
    return entry


def _reservation(**overrides: object) -> dict:
    entry = {
        "reservation_id": "ETH-2026-RESERVATION",
        "instrument_id": "ETH/USDT",
        "dataset_sha256": ETH_HASH,
        "timeframe": "1h",
        "evaluation_first": ETH_FIRST.isoformat(),
        "evaluation_last": ETH_LAST.isoformat(),
        "status": "RESERVED",
        "used": False,
        "preregistration_id": "phase39-test",
    }
    entry.update(overrides)
    return entry


def registry(
    *,
    reservations: list[dict] | None = None,
    consumed: list[dict] | None = None,
    instruments: list[dict] | None = None,
) -> dict:
    return {
        "version": 1,
        "instruments": instruments
        if instruments is not None
        else [_instrument("BTC/USDT"), _instrument("ETH/USDT")],
        "reservations": reservations if reservations is not None else [_reservation()],
        "consumed_windows": consumed or [],
    }


def write_registry(tmp_path: Path, data: dict, name: str = "registry.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def auth(dataset_instrument: str = "ETH/USDT", config_asset: str = "BTC/USDT",
         **overrides: str) -> CrossAssetAuthorization:
    fields = {
        "dataset_instrument": dataset_instrument,
        "config_asset": config_asset,
        "justification": "BTC-derived config carried onto ETH data",
        "approved_by": "phase39-test",
        "approved_on": "2026-10-09",
    }
    fields.update(overrides)
    return CrossAssetAuthorization(**fields)  # type: ignore[arg-type]


def hourly(count: int, start: datetime) -> list[Candle]:
    return [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0,
        )
        for i in range(count)
    ]


def permitted(reg: dict, **overrides: object):
    kwargs: dict[str, object] = dict(
        dataset_sha256=ETH_HASH,
        instrument_id="ETH/USDT",
        timeframe="1h",
        evaluation_start=ETH_FIRST,
        evaluation_end=ETH_LAST,
        preregistration_id="phase39-test",
        registry=reg,
    )
    kwargs.update(overrides)
    return assert_evaluation_permitted(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# fail-closed registry loading
# --------------------------------------------------------------------------


def test_missing_registry_refuses(tmp_path: Path) -> None:
    with pytest.raises(ResearchGuardError, match="not found"):
        load_registry(tmp_path / "absent.json")


def test_malformed_registry_refuses(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ResearchGuardError, match="not valid JSON"):
        load_registry(path)


def test_registry_missing_required_section_refuses(tmp_path: Path) -> None:
    path = write_registry(tmp_path, {"version": 1, "instruments": []})
    with pytest.raises(ResearchGuardError, match="reservations"):
        load_registry(path)


def test_registry_section_of_wrong_type_refuses(tmp_path: Path) -> None:
    path = write_registry(tmp_path, {**registry(), "reservations": "nope"})
    with pytest.raises(ResearchGuardError, match="must be a list"):
        load_registry(path)


def test_registry_top_level_not_object_refuses(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ResearchGuardError, match="JSON object"):
        load_registry(path)


# --------------------------------------------------------------------------
# instrument identity
# --------------------------------------------------------------------------


def test_identity_ok() -> None:
    decision = assert_instrument_identity(
        dataset_sha256=ETH_HASH, instrument_id="ETH/USDT",
        timeframe="1h", registry=registry(),
    )
    assert decision.permitted is True


def test_unregistered_instrument_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="not registered"):
        assert_instrument_identity(
            dataset_sha256=ETH_HASH, instrument_id="SOL/USDT",
            timeframe="1h", registry=registry(),
        )


def test_forex_instrument_refuses() -> None:
    """forex has no session/DST validator here, so it is refused, not approximated."""

    reg = registry(instruments=[_instrument("EUR/USD", market_type="forex_reference_rates")])
    with pytest.raises(ResearchGuardError, match="no implemented validator"):
        assert_instrument_identity(
            dataset_sha256=ETH_HASH, instrument_id="EUR/USD",
            timeframe="1h", registry=reg,
        )
    assert "forex" not in "".join(MARKET_TYPES_SUPPORTED)


def test_forex_spot_is_absent_from_supported_types() -> None:
    assert "forex_spot" not in MARKET_TYPES_SUPPORTED


def test_incomplete_instrument_metadata_refuses() -> None:
    reg = registry(instruments=[{"instrument_id": "ETH/USDT", "market_type": SPOT}])
    with pytest.raises(ResearchGuardError, match="incomplete metadata"):
        assert_instrument_identity(
            dataset_sha256=ETH_HASH, instrument_id="ETH/USDT",
            timeframe="1h", registry=reg,
        )


def test_unknown_volume_semantics_refuses() -> None:
    reg = registry(instruments=[_instrument("ETH/USDT", volume_semantics="vibes")])
    with pytest.raises(ResearchGuardError, match="volume_semantics"):
        assert_instrument_identity(
            dataset_sha256=ETH_HASH, instrument_id="ETH/USDT",
            timeframe="1h", registry=reg,
        )


def test_volume_semantics_vocabulary_is_explicit() -> None:
    assert "none" in VOLUME_SEMANTICS  # forex declares absence, never a guess


def test_timeframe_mismatch_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="timeframe mismatch"):
        assert_instrument_identity(
            dataset_sha256=ETH_HASH, instrument_id="ETH/USDT",
            timeframe="4h", registry=registry(),
        )


def test_unregistered_dataset_hash_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="not registered against"):
        assert_instrument_identity(
            dataset_sha256="c" * 64, instrument_id="ETH/USDT",
            timeframe="1h", registry=registry(),
        )


def test_blank_dataset_sha_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="dataset_sha256 is required"):
        assert_instrument_identity(
            dataset_sha256="", instrument_id="ETH/USDT",
            timeframe="1h", registry=registry(),
        )


def test_byte_identical_copy_shares_identity() -> None:
    """Identity is the hash, not the path, so copying cannot evade a reservation."""

    reg = registry()
    assert_instrument_identity(
        dataset_sha256=ETH_HASH.upper(), instrument_id="ETH/USDT",
        timeframe="1h", registry=reg,
    )


# --------------------------------------------------------------------------
# evaluation permission
# --------------------------------------------------------------------------


def test_reserved_window_permitted() -> None:
    assert permitted(registry()).permitted is True


def test_consumed_window_refuses_reuse() -> None:
    reg = registry(
        reservations=[],
        consumed=[{
            "instrument_id": "ETH/USDT",
            "dataset_sha256": ETH_HASH,
            "timeframe": "1h",
            "evaluation_first": ETH_FIRST.isoformat(),
            "evaluation_last": ETH_LAST.isoformat(),
            "consumed_on": "2026-10-09",
        }],
    )
    with pytest.raises(ResearchGuardError, match="already been consumed"):
        permitted(reg)


def test_unregistered_dataset_refuses_evaluation() -> None:
    with pytest.raises(ResearchGuardError):
        permitted(registry(), dataset_sha256="c" * 64)


def test_malformed_sha_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="dataset_sha256 is required"):
        permitted(registry(), dataset_sha256="   ")


def test_missing_preregistration_on_run_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="requires a preregistration_id"):
        permitted(registry(), preregistration_id="")


def test_wrong_preregistration_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="preregistration mismatch"):
        permitted(registry(), preregistration_id="someone-elses-prereg")


def test_unregistered_preregistration_refuses() -> None:
    """The shipped ETH reservation has no preregistration, so it is not runnable."""

    reg = registry(reservations=[_reservation(preregistration_id=None)])
    with pytest.raises(ResearchGuardError, match="no registered preregistration_id"):
        permitted(reg)


def test_reservation_wrong_status_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="only RESERVED"):
        permitted(registry(reservations=[_reservation(status="APPROVED")]))


def test_reservation_without_id_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="missing reservation_id"):
        permitted(registry(reservations=[_reservation(reservation_id="")]))


def test_omitting_evaluation_range_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="must declare evaluation_start"):
        permitted(registry(), evaluation_start=None, evaluation_end=None)


def test_narrowed_evaluation_range_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="requires evaluation range"):
        permitted(registry(), evaluation_end=datetime(2026, 6, 1))


def test_range_starting_before_reservation_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="requires evaluation range"):
        permitted(registry(), evaluation_start=datetime(2025, 12, 1))


def test_range_overrunning_reservation_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="requires evaluation range"):
        permitted(registry(), evaluation_end=datetime(2026, 12, 31, 23))


def test_warmup_only_window_does_not_grant_evaluation() -> None:
    """Trading only inside warm-up is not the reserved evaluation window."""

    with pytest.raises(ResearchGuardError):
        permitted(
            registry(),
            evaluation_start=datetime(2025, 6, 1),
            evaluation_end=datetime(2025, 6, 2),
        )


def test_already_used_reservation_refuses_second_use() -> None:
    with pytest.raises(ResearchGuardError, match="already been used"):
        permitted(registry(reservations=[_reservation(used=True)]))


# --------------------------------------------------------------------------
# one-time consumption must be durable
# --------------------------------------------------------------------------


def test_permitted_run_marks_reservation_used(tmp_path: Path) -> None:
    path = write_registry(tmp_path, registry())
    permitted(registry(), registry_file=path, mark_used=True)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["reservations"][0]["used"] is True
    assert on_disk["reservations"][0]["used_on"]

    # the same window can no longer be run
    with pytest.raises(ResearchGuardError, match="already been used"):
        permitted(registry(), registry_file=path)


def test_consumption_without_a_registry_file_refuses() -> None:
    """One-time protection that cannot be recorded must not be claimed."""

    with pytest.raises(ResearchGuardError, match="no registry_file was supplied"):
        permitted(registry(), mark_used=True)


def test_mark_used_false_leaves_registry_untouched(tmp_path: Path) -> None:
    path = write_registry(tmp_path, registry())
    before = path.read_text(encoding="utf-8")
    permitted(registry(), registry_file=path, mark_used=False)
    assert path.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# cross-asset authorization (BTC config on ETH data)
# --------------------------------------------------------------------------


def test_asset_mismatch_refused_without_authorization() -> None:
    with pytest.raises(ResearchGuardError, match="instrument transfer refused"):
        permitted(registry(), config_asset="BTC/USDT")


def test_asset_mismatch_allowed_with_explicit_authorization() -> None:
    decision = permitted(registry(), config_asset="BTC/USDT", cross_asset=auth())
    assert decision.permitted is True
    assert decision.cross_asset is not None
    assert decision.cross_asset["dataset_instrument"] == "ETH/USDT"
    assert decision.cross_asset["config_asset"] == "BTC/USDT"


def test_authorization_for_wrong_pair_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="does not describe this run"):
        permitted(
            registry(), config_asset="BTC/USDT",
            cross_asset=auth(dataset_instrument="SOL/USDT"),
        )


def test_authorization_with_wrong_config_asset_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="does not describe this run"):
        permitted(
            registry(), config_asset="BTC/USDT",
            cross_asset=auth(config_asset="SOL/USDT"),
        )


def test_incomplete_authorization_record_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="incomplete"):
        permitted(
            registry(), config_asset="BTC/USDT",
            cross_asset={"dataset_instrument": "ETH/USDT"},
        )


def test_malformed_authorization_type_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="must be a mapping"):
        permitted(registry(), config_asset="BTC/USDT", cross_asset="BTC->ETH")


def test_authorization_accepts_a_plain_record() -> None:
    decision = permitted(
        registry(), config_asset="BTC/USDT", cross_asset=auth().as_record()
    )
    assert decision.permitted is True


def test_same_asset_needs_no_authorization() -> None:
    assert permitted(registry(), config_asset="ETH/USDT").permitted is True


def test_mismatch_is_refused_before_the_window_is_consulted() -> None:
    """Identity precedes range, so a mislabelled run cannot reach a window at all."""

    with pytest.raises(ResearchGuardError):
        permitted(
            registry(),
            config_asset="BTC/USDT",
            cross_asset=auth(dataset_instrument="ETH/USDT", config_asset="BTC/USDT"),
            preregistration_id="wrong",
        )


# --------------------------------------------------------------------------
# hash-independent range checks
# --------------------------------------------------------------------------


def test_range_overlap_with_consumed_window_refuses() -> None:
    reg = registry(consumed=[{
        "instrument_id": "BTC/USDT",
        "dataset_sha256": BTC_HASH,
        "timeframe": "1h",
        "consumed_on": "2026-10-09",
        "evaluation_first": "2026-09-01T00:00:00",
        "evaluation_last": "2026-10-08T23:00:00",
    }])
    with pytest.raises(ResearchGuardError, match="consumed evaluation window"):
        assert_no_registered_range(
            instrument_id="BTC/USDT",
            first=datetime(2026, 10, 1), last=datetime(2026, 10, 9),
            registry=reg,
        )


def test_range_disjoint_from_consumed_window_is_fine() -> None:
    reg = registry(consumed=[{
        "instrument_id": "BTC/USDT",
        "dataset_sha256": BTC_HASH,
        "timeframe": "1h",
        "consumed_on": "2026-10-09",
        "evaluation_first": "2026-09-01T00:00:00",
        "evaluation_last": "2026-10-08T23:00:00",
    }])
    assert assert_no_registered_range(
        instrument_id="BTC/USDT",
        first=datetime(2025, 1, 1), last=datetime(2025, 12, 31),
        registry=reg,
    ) == []


def test_range_matching_another_instrument_is_ignored() -> None:
    reg = registry(reservations=[], consumed=[{
        "instrument_id": "BTC/USDT",
        "dataset_sha256": BTC_HASH,
        "timeframe": "1h",
        "consumed_on": "2026-10-09",
        "evaluation_first": "2026-01-01T00:00:00",
        "evaluation_last": "2026-12-31T23:00:00",
    }])
    assert assert_no_registered_range(
        instrument_id="ETH/USDT",
        first=datetime(2026, 2, 1), last=datetime(2026, 3, 1),
        registry=reg,
    ) == []


def test_malformed_window_timestamp_refuses() -> None:
    reg = registry(consumed=[{
        "instrument_id": "BTC/USDT",
        "dataset_sha256": BTC_HASH,
        "timeframe": "1h",
        "consumed_on": "2026-10-09",
        "evaluation_first": "not-a-timestamp",
        "evaluation_last": "2026-12-31T23:00:00",
    }])
    with pytest.raises(ResearchGuardError, match="ISO timestamp"):
        assert_no_registered_range(
            instrument_id="BTC/USDT",
            first=datetime(2026, 2, 1), last=datetime(2026, 3, 1),
            registry=reg,
        )


# --------------------------------------------------------------------------
# overlap-check status must never be implied
# --------------------------------------------------------------------------


def test_overlap_checked_accepted() -> None:
    assert note_overlap_check(OVERLAP_CHECKED) == OVERLAP_CHECKED


def test_overlap_skipped_is_a_valid_state() -> None:
    assert note_overlap_check(OVERLAP_SKIPPED) == OVERLAP_SKIPPED


def test_overlap_failed_is_a_valid_state() -> None:
    assert note_overlap_check(OVERLAP_FAILED) == OVERLAP_FAILED


def test_unstated_overlap_status_refuses() -> None:
    with pytest.raises(ResearchGuardError, match="'unknown' is not a permitted state"):
        note_overlap_check("")


def test_unknown_overlap_status_refuses() -> None:
    with pytest.raises(ResearchGuardError):
        note_overlap_check("probably_fine")


def test_none_overlap_status_refuses() -> None:
    with pytest.raises(ResearchGuardError):
        note_overlap_check(None)


def test_acquisition_report_defaults_to_not_verified() -> None:
    """A report that never states the outcome is non-compliant, not a pass."""

    assert AcquisitionReport().overlap_check == OVERLAP_FAILED


def test_acquisition_records_skipped_not_empty_pass(tmp_path) -> None:
    """The Phase 33 defect: an empty overlap list must not imply a clean check."""

    src = tmp_path / "s.csv"
    src.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2025-12-30T00:00:00,1,2,0.5,1.5,10\n"
        "2025-12-30T01:00:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    report = normalize_source(
        src, tmp_path / "out.csv", allow_overlap_with_research=True
    )

    assert report.overlapping_rows == []
    assert report.overlap_check == OVERLAP_SKIPPED
    assert any("NOT verified" in n for n in report.notes)


def test_acquisition_records_checked_when_not_bypassed(tmp_path) -> None:
    # Outside RESEARCH_FIRST..RESEARCH_LAST, so the overlap check can be clean.
    src = tmp_path / "s.csv"
    src.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-06-01T00:00:00,1,2,0.5,1.5,10\n"
        "2023-06-01T01:00:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    report = normalize_source(src, tmp_path / "out.csv")

    assert report.overlap_check == OVERLAP_CHECKED
    assert report.overlapping_rows == []
    assert any("overlap check: checked" in n for n in report.notes)


def test_acquisition_detects_real_overlap(tmp_path) -> None:
    """Rows inside the research window are reported as overlaps, not ignored."""

    src = tmp_path / "s.csv"
    src.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2025-06-01T00:00:00,1,2,0.5,1.5,10\n"
        "2025-06-01T01:00:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    report = normalize_source(src, tmp_path / "out.csv")

    assert report.overlap_check == OVERLAP_CHECKED
    assert report.overlapping_rows, "in-window rows must be reported as overlaps"
    assert not report.accepted


# --------------------------------------------------------------------------
# dataset validation
# --------------------------------------------------------------------------


def test_nan_price_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset([Candle(rows[0].timestamp, float("nan"), 1.0, 0.5, 1.0, 1.0)] + rows[1:])


def test_infinite_price_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset([Candle(rows[0].timestamp, float("inf"), 1.0, 0.5, 1.0, 1.0)] + rows[1:])


def test_zero_price_refuses() -> None:
    """A zero price satisfies every ordering comparison, so it needs its own check."""

    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="non-positive"):
        validate_dataset([Candle(rows[0].timestamp, 0.0, 1.0, 0.0, 0.5, 1.0)] + rows[1:])


def test_negative_price_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="non-positive"):
        validate_dataset([Candle(rows[0].timestamp, -1.0, 1.0, -2.0, 0.5, 1.0)] + rows[1:])


def test_negative_volume_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="negative volume"):
        validate_dataset([Candle(rows[0].timestamp, 1.0, 2.0, 0.5, 1.5, -1.0)] + rows[1:])


def test_open_above_high_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="above its high"):
        validate_dataset([Candle(rows[0].timestamp, 5.0, 2.0, 0.5, 1.5, 1.0)] + rows[1:])


def test_close_below_low_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="below its low"):
        validate_dataset([Candle(rows[0].timestamp, 1.0, 2.0, 0.5, 0.1, 1.0)] + rows[1:])


def test_inverted_high_low_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError):
        validate_dataset([Candle(rows[0].timestamp, 1.0, 0.5, 2.0, 1.5, 1.0)] + rows[1:])


def test_duplicate_timestamp_refuses() -> None:
    rows = hourly(3, ETH_FIRST)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_dataset([rows[0], rows[0], rows[1]])


def test_interval_gap_refuses_when_interval_declared() -> None:
    rows = hourly(5, ETH_FIRST)
    del rows[2]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(rows, expected_interval_seconds=3600)


def test_uniform_hourly_passes_when_interval_declared() -> None:
    validate_dataset(hourly(5, ETH_FIRST), expected_interval_seconds=3600)


def test_daily_series_is_fine_when_no_interval_declared() -> None:
    """Omitting the interval must not wrongly refuse a legitimate daily series."""

    rows = [
        Candle(ETH_FIRST + timedelta(days=i), 1.0, 2.0, 0.5, 1.5, 0.0)
        for i in range(5)
    ]
    validate_dataset(rows)


def test_ecb_reference_rates_fail_hourly_ohlc_validation() -> None:
    """Daily reference rates are not OHLCV and must not pass as hourly candles."""

    rows = [
        Candle(datetime(2026, 1, 1 + i), 1.0, 1.0, 1.0, 1.0, 0.0)
        for i in range(3)
    ]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(rows, expected_interval_seconds=3600)


def test_forex_market_type_refuses_in_validator() -> None:
    with pytest.raises(ValueError, match="no implemented validator"):
        validate_dataset(hourly(3, ETH_FIRST), market_type="forex_reference_rates")


def test_partial_identity_declaration_refuses() -> None:
    with pytest.raises(ValueError, match="must be supplied together"):
        validate_dataset(hourly(3, ETH_FIRST), instrument_id="ETH/USDT")


def test_empty_identity_refuses() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        validate_dataset(hourly(3, ETH_FIRST), instrument_id="  ", timeframe="1h")


def test_declared_identity_accepted() -> None:
    validate_dataset(hourly(3, ETH_FIRST), instrument_id="ETH/USDT", timeframe="1h")


def test_empty_dataset_refuses() -> None:
    with pytest.raises(ValueError, match="no candles"):
        validate_dataset([])


def test_single_candle_dataset_accepted() -> None:
    validate_dataset(hourly(1, ETH_FIRST))


# --------------------------------------------------------------------------
# backtest integration
# --------------------------------------------------------------------------


def test_development_run_without_context_is_unaffected() -> None:
    """Unregistered synthetic data stays usable without any context.

    Phase 40 note: this previously used timestamps inside the ETH reserved
    window, which Phase 39's guard could not see and Phase 40's now refuses. The
    date was moved out of the reserved range rather than the assertion relaxed;
    the reserved-range case is covered by
    ``test_reserved_window_range_refused_without_context``.
    """

    assert run_backtest(hourly(60, datetime(2023, 3, 1, 0, 0))) is not None


def test_reserved_dates_alone_do_not_refuse_synthetic_data() -> None:
    """Sharing the reserved *dates* is not enough; content identity is what counts.

    Phase 40 initially refused any series overlapping the reserved date range.
    That was wrong: synthetic fixtures legitimately use arbitrary dates, and
    refusing them protects nothing while breaking the existing suite. The check
    is now an exact per-bar content match against the registered index.

    This test pins the corrected behaviour so the date-range approach does not
    creep back in.
    """

    assert run_backtest(hourly(60, ETH_FIRST)) is not None


def test_no_bypass_flag_exists() -> None:
    """There must be no supported way to switch the guard off once declared."""

    import inspect

    params = set(inspect.signature(run_backtest).parameters)
    for forbidden in (
        "skip_guard", "no_guard", "ignore_guard", "unsafe", "allow_reserved",
        "bypass_guard", "force", "disable_guard",
    ):
        assert forbidden not in params


# A wholly synthetic 2023 window, so no engine run here ever touches data that
# is reserved or consumed for real research. ETH 2026 is exercised at the guard
# level only, and is refused there on every path.
SYNTH_HASH = "e" * 64
SYNTH_FIRST = datetime(2023, 6, 1, 0, 0)
SYNTH_LAST = datetime(2023, 6, 30, 23, 0)
MIN_HISTORY = 22


def synth_registry(tmp_path: Path, **kw: object) -> Path:
    return write_registry(tmp_path, registry(
        instruments=kw.pop("instruments", [_instrument("SYNTH/TEST")]),  # type: ignore[arg-type]
        reservations=[{
            "reservation_id": "SYNTH-RESERVATION",
            "instrument_id": "SYNTH/TEST",
            "dataset_sha256": SYNTH_HASH,
            "timeframe": "1h",
            "evaluation_first": SYNTH_FIRST.isoformat(),
            "evaluation_last": SYNTH_LAST.isoformat(),
            "status": "RESERVED",
            "used": False,
            "preregistration_id": "phase39-synth",
        }],
        **kw,  # type: ignore[arg-type]
    ))


def synth_candles() -> list[Candle]:
    start = SYNTH_FIRST - timedelta(hours=MIN_HISTORY)
    total = MIN_HISTORY + int((SYNTH_LAST - SYNTH_FIRST).total_seconds() // 3600) + 1
    return hourly(total, start)


def synth_context(path: Path, rows: list[Candle], **kw: object) -> ResearchContext:
    fields: dict[str, object] = dict(
        dataset_sha256=SYNTH_HASH,
        instrument_id="SYNTH/TEST",
        timeframe="1h",
        evaluation_first=rows[MIN_HISTORY].timestamp,
        evaluation_last=rows[-1].timestamp,
        preregistration_id="phase39-synth",
        registry_file=path,
    )
    fields.update(kw)
    return ResearchContext(**fields)  # type: ignore[arg-type]


def test_synthetic_series_reaches_the_reserved_boundary() -> None:
    rows = synth_candles()
    assert rows[MIN_HISTORY].timestamp == SYNTH_FIRST
    assert rows[-1].timestamp == SYNTH_LAST


def test_guarded_run_on_reserved_window_is_permitted(tmp_path: Path) -> None:
    path = synth_registry(tmp_path)
    rows = synth_candles()

    run_backtest(
        rows,
        evaluation_start=MIN_HISTORY,
        research_context=synth_context(path, rows),
    )

    # Phase 40: the run does NOT spend the reservation. Consumption is a separate,
    # explicit step so a failed run cannot consume a window.
    assert json.loads(path.read_text(encoding="utf-8"))["reservations"][0]["used"] is False


def test_reservation_is_spent_only_by_explicit_consumption(tmp_path: Path) -> None:
    """A completed run leaves the window available until the caller spends it."""

    path = synth_registry(tmp_path)
    rows = synth_candles()

    run_backtest(
        rows,
        evaluation_start=MIN_HISTORY,
        research_context=synth_context(path, rows),
    )
    consume_reservation("SYNTH-RESERVATION", registry_file=path)

    assert json.loads(path.read_text(encoding="utf-8"))["reservations"][0]["used"] is True

    with pytest.raises(ResearchGuardError, match="already been used"):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=synth_context(path, rows),
        )


def test_failed_run_does_not_consume_the_reservation(tmp_path: Path) -> None:
    """An attempt that produces nothing must not spend the window."""

    path = synth_registry(tmp_path)
    rows = synth_candles()

    with pytest.raises(ResearchGuardError):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=synth_context(path, rows, preregistration_id="wrong"),
        )

    assert json.loads(path.read_text(encoding="utf-8"))["reservations"][0]["used"] is False


def test_consuming_an_unknown_reservation_refuses(tmp_path: Path) -> None:
    path = synth_registry(tmp_path)
    with pytest.raises(ResearchGuardError, match="not in the registry"):
        consume_reservation("NO-SUCH-RESERVATION", registry_file=path)


def test_consumption_of_unknown_reservation_refuses(tmp_path: Path) -> None:
    """A reservation id absent from the registry may not be spent."""

    path = synth_registry(tmp_path)
    with pytest.raises(ResearchGuardError, match="not in the registry"):
        consume_reservation("NOT-REGISTERED", registry_file=path)


def test_spent_window_cannot_be_rerun_through_the_engine(tmp_path: Path) -> None:
    path = synth_registry(tmp_path)
    rows = synth_candles()

    run_backtest(
        rows,
        evaluation_start=MIN_HISTORY,
        research_context=synth_context(path, rows),
    )
    consume_reservation("SYNTH-RESERVATION", registry_file=path)

    with pytest.raises(ResearchGuardError, match="already been used"):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=synth_context(path, rows),
        )


def test_engine_never_trades_during_warmup(tmp_path: Path) -> None:
    """Warm-up bars feed indicators only; no trade may be opened before the boundary."""

    path = synth_registry(tmp_path)
    rows = synth_candles()

    result = run_backtest(
        rows,
        evaluation_start=MIN_HISTORY,
        research_context=synth_context(path, rows),
    )

    boundary = rows[MIN_HISTORY].timestamp
    for trade in result.trades:
        assert trade.entry_time is None or trade.entry_time >= boundary


def test_backtest_refuses_spent_holdout(tmp_path: Path) -> None:
    """The Phase 29 holdout must be unusable as an evaluation window.

    The refusal comes from ``assert_series_permitted`` first, since the consumed
    range overlaps the default ETH reservation by date. Either refusal is a
    correct outcome; what matters is that the run does not proceed.
    """

    path = write_registry(tmp_path, registry(
        reservations=[],
        consumed=[{
            "instrument_id": "BTC/USDT",
            "dataset_sha256": BTC_HASH,
            "timeframe": "1h",
            "consumed_on": "2026-10-09",
            "evaluation_first": "2026-01-01T00:00:00",
            "evaluation_last": "2026-12-31T23:00:00",
        }],
    ))
    rows = hourly(MIN_HISTORY + 60, datetime(2026, 1, 1, 0, 0))
    with pytest.raises(ResearchGuardError):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=ResearchContext(
                dataset_sha256=BTC_HASH,
                instrument_id="BTC/USDT",
                timeframe="1h",
                evaluation_first=rows[MIN_HISTORY].timestamp,
                evaluation_last=rows[-1].timestamp,
                preregistration_id="phase29",
                registry_file=path,
            ),
        )


def test_consumed_window_refused_even_outside_any_reserved_range(
    tmp_path: Path,
) -> None:
    """Isolate the consumed-window refusal from the range check.

    Uses a window in 2019, which touches neither the ETH reservation nor any
    other registered range, so the refusal can only come from the consumed entry.
    """

    path = write_registry(tmp_path, registry(
        reservations=[],
        consumed=[{
            "instrument_id": "BTC/USDT",
            "dataset_sha256": BTC_HASH,
            "timeframe": "1h",
            "consumed_on": "2026-10-09",
            "evaluation_first": "2019-01-01T00:00:00",
            "evaluation_last": "2019-12-31T23:00:00",
        }],
    ))
    rows = hourly(MIN_HISTORY + 60, datetime(2019, 6, 1, 0, 0))
    with pytest.raises(ResearchGuardError, match="already been consumed"):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=ResearchContext(
                dataset_sha256=BTC_HASH,
                instrument_id="BTC/USDT",
                timeframe="1h",
                evaluation_first=rows[MIN_HISTORY].timestamp,
                evaluation_last=rows[-1].timestamp,
                preregistration_id="phase29",
                registry_file=path,
            ),
        )


def test_guarded_run_must_declare_evaluation_start(tmp_path: Path) -> None:
    path = synth_registry(tmp_path)
    rows = synth_candles()
    with pytest.raises(ValueError, match="must declare evaluation_start"):
        run_backtest(
            rows,
            research_context=synth_context(path, rows),
        )


def test_guarded_run_refuses_btc_config_on_eth_data(tmp_path: Path) -> None:
    """The BTC/USDT config label may not be carried onto other data silently."""

    path = synth_registry(tmp_path)
    rows = synth_candles()
    with pytest.raises(ResearchGuardError, match="instrument transfer refused"):
        run_backtest(
            rows,
            evaluation_start=MIN_HISTORY,
            research_context=synth_context(path, rows, config_asset="BTC/USDT"),
        )


def test_guarded_run_allows_authorized_cross_asset(tmp_path: Path) -> None:
    path = synth_registry(tmp_path, instruments=[
        _instrument("SYNTH/TEST"), _instrument("BTC/USDT"),
    ])
    rows = synth_candles()

    run_backtest(
        rows,
        evaluation_start=MIN_HISTORY,
        research_context=synth_context(
            path, rows,
            config_asset="BTC/USDT",
            cross_asset=auth(dataset_instrument="SYNTH/TEST",
                             config_asset="BTC/USDT"),
        ),
    )


# --------------------------------------------------------------------------
# shipped registry
# --------------------------------------------------------------------------


def test_shipped_registry_loads() -> None:
    reg = load_registry()
    assert reg["instruments"] and reg["reservations"] and reg["consumed_windows"]


def test_shipped_registry_keeps_eth_unapproved() -> None:
    """Phase 39 must not silently approve the ETH 2026 window."""

    eth = [
        r for r in load_registry()["reservations"] if r["instrument_id"] == "ETH/USDT"
    ]
    assert len(eth) == 1
    reservation = eth[0]
    assert reservation["status"] == "RESERVED"
    assert reservation["used"] is False
    assert not reservation.get("preregistration_id"), (
        "ETH must stay unapproved: no preregistration may exist yet"
    )

    with pytest.raises(ResearchGuardError, match="no registered preregistration_id"):
        assert_evaluation_permitted(
            dataset_sha256=reservation["dataset_sha256"],
            instrument_id="ETH/USDT",
            timeframe="1h",
            evaluation_start=ETH_FIRST,
            evaluation_end=ETH_LAST,
            preregistration_id="anything",
            registry=load_registry(),
        )


def test_shipped_registry_reservation_matches_eth_file() -> None:
    """The reservation must point at the real ETH dataset, byte for byte."""

    reservation = load_registry()["reservations"][0]
    path = REPO_ROOT / reservation["dataset_path"]
    assert path.exists(), f"reserved dataset missing: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == reservation["dataset_sha256"]


def test_shipped_registry_records_spent_btc_holdout() -> None:
    consumed = load_registry()["consumed_windows"]
    holdout = [
        c for c in consumed if c.get("preregistration_id") == "phase29d-eth0-btc-holdout"
    ]
    assert len(holdout) == 1

    path = REPO_ROOT / holdout[0]["dataset_path"]
    assert path.exists(), f"consumed holdout missing: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == holdout[0]["dataset_sha256"]

    with pytest.raises(ResearchGuardError, match="already been consumed"):
        assert_evaluation_permitted(
            dataset_sha256=holdout[0]["dataset_sha256"],
            instrument_id="BTC/USDT",
            timeframe="1h",
            evaluation_start=ETH_FIRST,
            evaluation_end=ETH_LAST,
            preregistration_id="anything",
            registry=load_registry(),
        )


def test_shipped_registry_marks_forex_blocked() -> None:
    forex = [
        i for i in load_registry()["instruments"]
        if str(i["market_type"]).startswith("forex")
    ]
    assert len(forex) == 3
    for entry in forex:
        assert entry["volume_semantics"] == "none"
        with pytest.raises(ResearchGuardError, match="no implemented validator"):
            assert_instrument_identity(
                dataset_sha256="d" * 64,
                instrument_id=entry["instrument_id"],
                timeframe=entry["timeframe"],
                registry=load_registry(),
            )