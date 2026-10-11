"""Phase 41 tests: multi-market data validation.

Synthetic fixtures throughout. The two tests that read a real dataset
(``test_real_datasets_still_validate``) assert *structural* properties only --
row counts, spacing, timezone naivety -- and never inspect a price, signal,
trade or result.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import load_dataset, validate_dataset
from crypto_paper_lab.dataset_identity import (
    MARKET_TYPES_SUPPORTED,
    VOLUME_SEMANTICS,
    DatasetIdentity,
    identity_for_registry_entry,
)
from crypto_paper_lab.intervals import (
    classify_intervals,
    contiguous_slice,
    expected_bar_count,
)
from crypto_paper_lab.models import Candle
from crypto_paper_lab.researchguard import load_registry

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2024, 1, 1)


def hourly(count: int, start: datetime = START, price: float = 100.0) -> list[Candle]:
    return [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price + 0.5,
            volume=10.0,
        )
        for i in range(count)
    ]


def write_csv(path: Path, rows: list[str], header: str | None = None) -> Path:
    head = header or "timestamp,open,high,low,close,volume"
    path.write_text(head + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def row(ts: str, o: str, h: str, l: str, c: str, v: str = "10") -> str:
    return f"{ts},{o},{h},{l},{c},{v}"


# ==========================================================================
# schema and required fields
# ==========================================================================


def test_missing_required_column_refused(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("timestamp,open,high,close,volume\n2024-01-01T00:00:00,1,2,1.5,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="open, high, low, close"):
        load_ohlcv_csv(p)


def test_missing_timestamp_column_refused(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("open,high,low,close,volume\n1,2,0.5,1.5,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="timestamp or date"):
        load_ohlcv_csv(p)


def test_headerless_file_refused(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no header"):
        load_ohlcv_csv(p)


def test_empty_data_rows_refused(tmp_path: Path) -> None:
    p = write_csv(tmp_path / "x.csv", [])
    with pytest.raises(ValueError, match="no candles"):
        load_ohlcv_csv(p)


def test_date_column_alias_accepted(tmp_path: Path) -> None:
    p = write_csv(
        tmp_path / "x.csv",
        [row("01-01-2024 00:00", "1", "2", "0.5", "1.5")],
        header="date,open,high,low,close,volume",
    )
    candles = load_ohlcv_csv(p)
    assert candles[0].timestamp == datetime(2024, 1, 1)


# ==========================================================================
# timestamp handling and UTC convention
# ==========================================================================


def test_z_suffix_normalised_to_naive_utc(tmp_path: Path) -> None:
    """``Z`` previously produced an aware datetime; everything else is naive."""

    p = write_csv(tmp_path / "z.csv", [row("2024-01-01T00:00:00Z", "1", "2", "0.5", "1.5")])
    candles = load_ohlcv_csv(p)
    assert candles[0].timestamp.tzinfo is None
    assert candles[0].timestamp == datetime(2024, 1, 1)


def test_offset_timestamp_converted_to_utc(tmp_path: Path) -> None:
    """08:00+02:00 is 06:00 UTC, not 08:00."""

    p = write_csv(
        tmp_path / "off.csv",
        [row("2024-01-01T08:00:00+02:00", "1", "2", "0.5", "1.5")],
    )
    candles = load_ohlcv_csv(p)
    assert candles[0].timestamp == datetime(2024, 1, 1, 6, 0)
    assert candles[0].timestamp.tzinfo is None


def test_naive_iso_unchanged(tmp_path: Path) -> None:
    p = write_csv(tmp_path / "n.csv", [row("2024-01-01T00:00:00", "1", "2", "0.5", "1.5")])
    assert load_ohlcv_csv(p)[0].timestamp == datetime(2024, 1, 1)


def test_mixed_aware_and_naive_refused_clearly() -> None:
    """Previously a TypeError from the comparison; now an actionable refusal."""

    rows = hourly(3)
    aware = Candle(
        datetime(2024, 1, 1, 3, tzinfo=timezone.utc), 1.0, 2.0, 0.5, 1.5, 1.0
    )
    with pytest.raises(ValueError, match="mixes timezone-aware and naive"):
        validate_dataset([rows[0], rows[1], aware])


def test_all_aware_accepted_when_consistent() -> None:
    rows = [
        Candle(datetime(2024, 1, 1, i, tzinfo=timezone.utc), 1.0, 2.0, 0.5, 1.5, 1.0)
        for i in range(3)
    ]
    validate_dataset(rows)


# ==========================================================================
# price and OHLC validity
# ==========================================================================


def test_all_zero_price_row_refused() -> None:
    rows = hourly(3)
    zeros = [Candle(c.timestamp, 0.0, 0.0, 0.0, 0.0, 0.0) for c in rows]
    with pytest.raises(ValueError, match="non-positive"):
        validate_dataset(zeros)


def test_nan_price_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, float("nan"), 2.0, 0.5, 1.5, 1.0)
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset(rows)


def test_infinite_price_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, float("inf"), 2.0, 0.5, 1.5, 1.0)
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset(rows)


def test_nan_volume_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 1.0, 2.0, 0.5, 1.5, float("nan"))
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset(rows)


def test_negative_price_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, -1.0, 2.0, -3.0, 1.5, 1.0)
    with pytest.raises(ValueError, match="non-positive"):
        validate_dataset(rows)


def test_negative_volume_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 1.0, 2.0, 0.5, 1.5, -1.0)
    with pytest.raises(ValueError, match="negative volume"):
        validate_dataset(rows)


def test_open_above_high_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 5.0, 2.0, 0.5, 1.5, 1.0)
    with pytest.raises(ValueError, match="above its high"):
        validate_dataset(rows)


def test_close_below_low_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 1.0, 2.0, 0.5, 0.1, 1.0)
    with pytest.raises(ValueError, match="below its low"):
        validate_dataset(rows)


def test_inverted_high_low_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 1.0, 0.5, 2.0, 1.5, 1.0)
    with pytest.raises(ValueError):
        validate_dataset(rows)


def test_zero_high_with_positive_low_refused() -> None:
    rows = hourly(3)
    rows[1] = Candle(rows[1].timestamp, 0.0, 0.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="non-positive"):
        validate_dataset(rows)


def test_empty_series_refused() -> None:
    with pytest.raises(ValueError, match="no candles"):
        validate_dataset([])


# ==========================================================================
# ordering and duplicates
# ==========================================================================


def test_duplicate_timestamp_refused() -> None:
    rows = hourly(3)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_dataset([rows[0], rows[0], rows[1]])


def test_out_of_order_refused() -> None:
    rows = hourly(3)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_dataset([rows[0], rows[2], rows[1]])


def test_single_bar_accepted() -> None:
    validate_dataset(hourly(1))


# ==========================================================================
# interval spacing and gap classification
# ==========================================================================


def test_uniform_hourly_accepted() -> None:
    validate_dataset(hourly(10), expected_interval_seconds=3600)


def test_missing_hour_refused_when_interval_declared() -> None:
    rows = hourly(5)
    del rows[2]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(rows, expected_interval_seconds=3600)


def test_interval_mismatch_reported_with_both_values() -> None:
    rows = hourly(5)
    del rows[2]
    with pytest.raises(ValueError) as excinfo:
        validate_dataset(rows, expected_interval_seconds=3600)
    message = str(excinfo.value)
    assert "3600s" in message and "7200s" in message


def test_gap_classified_as_defect_not_closure() -> None:
    """24x7 crypto has no legitimate closure, so a gap is always a defect."""

    rows = hourly(5) + hourly(5, datetime(2024, 1, 1, 10))
    with pytest.raises(ValueError, match="data defect"):
        classify_intervals(rows, expected_interval_seconds=3600)


def test_gaps_can_be_listed_for_repair() -> None:
    rows = hourly(5) + hourly(5, datetime(2024, 1, 1, 10))
    gaps = classify_intervals(rows, expected_interval_seconds=3600, allow_gaps=True)
    assert len(gaps) == 1
    assert gaps[0].missing_bars == 5
    record = gaps[0].as_record()
    assert record["missing_bars"] == 5
    assert json.loads(json.dumps(record))


def test_contiguous_slice_reports_without_modifying() -> None:
    rows = hourly(5) + hourly(5, datetime(2024, 1, 1, 10))
    start, end, gaps = contiguous_slice(rows, expected_interval_seconds=3600)
    assert (start, end) == (5, 10)
    assert len(gaps) == 1
    assert len(rows) == 10, "input must not be modified"


def test_no_gaps_returns_full_span() -> None:
    assert contiguous_slice(hourly(10), expected_interval_seconds=3600)[:2] == (0, 10)


def test_expected_bar_count() -> None:
    assert expected_bar_count(
        datetime(2024, 1, 1), datetime(2024, 1, 1, 9), expected_interval_seconds=3600
    ) == 10


def test_non_positive_interval_refused() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        classify_intervals(hourly(3), expected_interval_seconds=0)


def test_gap_classification_refuses_forex() -> None:
    with pytest.raises(ValueError, match="session, holiday and DST"):
        classify_intervals(
            hourly(3), expected_interval_seconds=3600, market_type="forex_reference_rates"
        )


# ==========================================================================
# declared identity
# ==========================================================================


def test_identity_requires_all_fields() -> None:
    for bad in (
        {"instrument_id": "", "timeframe": "1h", "market_type": "crypto_spot", "volume_semantics": "central_base"},
        {"instrument_id": "BTC/USDT", "timeframe": "", "market_type": "crypto_spot", "volume_semantics": "central_base"},
        {"instrument_id": "BTC/USDT", "timeframe": "1h", "market_type": "", "volume_semantics": "central_base"},
        {"instrument_id": "BTC/USDT", "timeframe": "1h", "market_type": "crypto_spot", "volume_semantics": ""},
    ):
        with pytest.raises(ValueError, match="must be a non-empty string"):
            DatasetIdentity(**bad)


def test_identity_refuses_undeclared_volume_semantics() -> None:
    with pytest.raises(ValueError, match="volume_semantics"):
        DatasetIdentity(
            instrument_id="BTC/USDT", timeframe="1h",
            market_type="crypto_spot", volume_semantics="some_volume",
        )


def test_identity_refuses_forex_market_type() -> None:
    with pytest.raises(ValueError, match="no implemented validator"):
        DatasetIdentity(
            instrument_id="EUR/USD", timeframe="1h",
            market_type="forex_reference_rates", volume_semantics="none",
        )


def test_forex_absent_from_supported_market_types() -> None:
    assert "forex_reference_rates" not in MARKET_TYPES_SUPPORTED
    assert "forex_spot" not in MARKET_TYPES_SUPPORTED


def test_crypto_spot_cannot_declare_absent_volume() -> None:
    """A crypto venue publishes volume; 'none' would misreport a missing field."""

    with pytest.raises(ValueError, match="not valid for crypto_spot"):
        DatasetIdentity(
            instrument_id="BTC/USDT", timeframe="1h",
            market_type="crypto_spot", volume_semantics="none",
        )


def test_none_is_valid_vocabulary_for_absence() -> None:
    assert "none" in VOLUME_SEMANTICS


def test_identity_refuses_unvalidatable_timeframe() -> None:
    with pytest.raises(ValueError, match="cannot be validated here"):
        DatasetIdentity(
            instrument_id="BTC/USDT", timeframe="4h",
            market_type="crypto_spot", volume_semantics="central_base",
        )


def test_btc_label_cannot_silently_load_eth_dataset() -> None:
    """The Phase 41 core requirement: a label mismatch is refused."""

    eth = DatasetIdentity(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="Relabelling the data"):
        eth.assert_compatible_with_config("BTC/USDT")


def test_matching_label_accepted() -> None:
    btc = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type="crypto_spot", volume_semantics="central_base",
    )
    btc.assert_compatible_with_config("BTC/USDT")


def test_cross_asset_error_points_to_authorization() -> None:
    eth = DatasetIdentity(
        instrument_id="ETH/USDT", timeframe="1h",
        market_type="crypto_spot", volume_semantics="central_base",
    )
    with pytest.raises(ValueError, match="CrossAssetAuthorization"):
        eth.assert_compatible_with_config("BTC/USDT")


def test_identity_from_registry_entry_refuses_incomplete() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        identity_for_registry_entry({"instrument_id": "BTC/USDT"})


def test_identity_round_trips_to_record() -> None:
    ident = DatasetIdentity(
        instrument_id="BTC/USDT", timeframe="1h",
        market_type="crypto_spot", volume_semantics="central_base",
    )
    record = ident.as_record()
    assert json.loads(json.dumps(record))
    assert record["instrument_id"] == "BTC/USDT"
    assert ident.expected_interval_seconds == 3600


def test_shipped_registry_crypto_identities_are_valid() -> None:
    crypto = [
        e for e in load_registry()["instruments"]
        if e["market_type"] == "crypto_spot"
    ]
    assert len(crypto) == 2
    for entry in crypto:
        identity_for_registry_entry(entry)


def test_shipped_registry_forex_identities_are_refused() -> None:
    """Forex entries exist as documentation but cannot yield a valid identity."""

    forex = [
        e for e in load_registry()["instruments"]
        if str(e["market_type"]).startswith("forex")
    ]
    assert len(forex) == 3
    for entry in forex:
        with pytest.raises(ValueError, match="no implemented validator"):
            identity_for_registry_entry(entry)
        assert entry["volume_semantics"] == "none"


def test_validate_dataset_partial_identity_refused() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        validate_dataset(hourly(3), instrument_id="BTC/USDT")


def test_validate_dataset_declared_identity_accepted() -> None:
    validate_dataset(
        hourly(3), instrument_id="BTC/USDT", timeframe="1h",
        market_type="crypto_spot",
    )


def test_validate_dataset_refuses_forex_market_type() -> None:
    with pytest.raises(ValueError, match="no implemented validator"):
        validate_dataset(hourly(3), market_type="forex_reference_rates")


# ==========================================================================
# regression: real datasets still parse and validate
# ==========================================================================


@pytest.mark.parametrize(
    "rel",
    [
        "data/BTCUSDT_1h_Cleaned (1).csv",
        "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv",
        "data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv",
    ],
)
def test_real_datasets_still_validate(rel: str) -> None:
    """Structural only: counts, spacing, timezone. No price or result inspected."""

    candles, summary = load_dataset(ROOT / rel)

    assert len(candles) == summary.candles
    assert candles[0].timestamp == summary.start
    assert candles[-1].timestamp == summary.end
    assert all(c.timestamp.tzinfo is None for c in candles)
    assert summary.start < summary.end

    validate_dataset(candles, expected_interval_seconds=3600)
    assert classify_intervals(candles, expected_interval_seconds=3600) == []


def test_eth_dataset_row_count_unchanged() -> None:
    candles, _ = load_dataset(
        ROOT / "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv"
    )
    assert len(candles) == 24288
    assert candles[0].timestamp == datetime(2024, 1, 1)
    assert candles[-1].timestamp == datetime(2026, 10, 8, 23)


def test_matching_identity_is_accepted() -> None:
    """A declaration whose spacing matches the data must be accepted.

    The guard tests in test_registry_schema.py only cover the refusal and
    contradiction paths, so an implementation that rejected *every* identity
    would still satisfy all of them. This is the positive case that keeps the
    ``identity=`` argument from degenerating into a blanket refusal.

    Synthetic fixtures only; no dataset file is read.
    """

    identity = DatasetIdentity(
        instrument_id="BTC/USDT",
        timeframe="1h",
        market_type="crypto_spot",
        volume_semantics="central_base",
    )

    # Accepted on its own...
    validate_dataset(hourly(5), identity=identity)

    # ...and when the caller restates the same values explicitly. Restating a
    # value that agrees with the declaration must not be treated as a conflict.
    validate_dataset(hourly(5), identity=identity, market_type="crypto_spot")
    validate_dataset(hourly(5), identity=identity, timeframe="1h")
    validate_dataset(hourly(5), identity=identity, expected_interval_seconds=3600)

    # The interval really is being enforced: 5-minute spacing under a 1h
    # declaration is refused, so acceptance above is not vacuous.
    five_minute = [
        Candle(START + timedelta(minutes=5 * i), 1.0, 2.0, 0.5, 1.5, 10.0)
        for i in range(5)
    ]
    with pytest.raises(ValueError, match="non-uniform interval"):
        validate_dataset(five_minute, identity=identity)