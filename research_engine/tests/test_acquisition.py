"""Tests for Phase 9 acquisition and dataset-validation functionality.

All fixtures are SYNTHETIC and written to temporary directories. No fixture
in this file is real market data, and none is presented as such.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.acquisition import (
    CANONICAL_COLUMNS,
    CANONICAL_DATE_FORMAT,
    PROTECTED_DATASET,
    AcquisitionError,
    detect_format,
    epoch_to_datetime,
    normalize_source,
    sha256_of,
    write_report,
)
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset

BASE = datetime(2026, 1, 1, 0, 0)


def hourly(count: int, start: datetime = BASE, price: float = 100.0):
    return [
        (
            start + timedelta(hours=i),
            price,
            price + 2,
            price - 2,
            price + 1,
            10.0 + i,
        )
        for i in range(count)
    ]


def write_binance(path: Path, rows, unit="us", header=False, columns=12):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        if header:
            w.writerow([
                "Open time", "Open", "High", "Low", "Close", "Volume",
                "Close time", "Quote asset volume", "Number of trades",
                "Taker buy base asset volume",
                "Taker buy quote asset volume", "Ignore",
            ])
        for stamp, o, h, l, c, v in rows:
            if unit == "us":
                open_ms = int((stamp - datetime(1970, 1, 1)).total_seconds()) * 1_000_000
            elif unit == "ms":
                open_ms = int((stamp - datetime(1970, 1, 1)).total_seconds()) * 1000
            else:
                open_ms = int((stamp - datetime(1970, 1, 1)).total_seconds())
            cells = [open_ms, o, h, l, c, v]
            while len(cells) < columns:
                cells.append(0)
            w.writerow(cells)


def write_native(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CANONICAL_COLUMNS)
        for stamp, o, h, l, c, v in rows:
            w.writerow([
                stamp.strftime(CANONICAL_DATE_FORMAT), o, h, l, c, v,
            ])


# --------------------------------------------------------- epoch detection


def test_epoch_unit_detection() -> None:
    seconds = int((BASE - datetime(1970, 1, 1)).total_seconds())
    assert epoch_to_datetime(seconds) == BASE
    assert epoch_to_datetime(seconds * 1000) == BASE
    assert epoch_to_datetime(seconds * 1_000_000) == BASE
    assert epoch_to_datetime(seconds * 1_000_000_000) == BASE


def test_binance_microsecond_timestamps_parse() -> None:
    """Spot data switched to microseconds on 2025-01-01."""

    stamp = datetime(2026, 3, 15, 7, 0)
    assert epoch_to_datetime(int(stamp.timestamp()) * 1_000_000) == stamp


# ------------------------------------------------------------ format detect


def test_detect_format(tmp_path) -> None:
    b = tmp_path / "b.csv"
    write_binance(b, hourly(3))
    assert detect_format(b) == "binance_klines"

    n = tmp_path / "n.csv"
    write_native(n, hourly(3))
    assert detect_format(n) == "project_native"

    i = tmp_path / "i.csv"
    with i.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        w.writerow(["2026-01-01T00:00:00+00:00", 1, 2, 0.5, 1.5, 3])
    assert detect_format(i) == "iso"


def test_detect_format_rejects_unknown(tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("alpha,beta,gamma\n1,2,3\n", encoding="utf-8")
    with pytest.raises(AcquisitionError):
        detect_format(bad)


def test_detect_format_rejects_empty(tmp_path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(AcquisitionError):
        detect_format(empty)


# ------------------------------------------------------------ happy path


def test_valid_binance_data_is_normalized(tmp_path) -> None:
    src = tmp_path / "src.csv"
    out = tmp_path / "oos" / "out.csv"
    write_binance(src, hourly(50), unit="us")

    report = normalize_source(src, out)

    assert report.accepted
    assert report.source_format == "binance_klines"
    assert report.candle_count == 50
    assert report.first_timestamp == BASE
    assert report.last_timestamp == BASE + timedelta(hours=49)
    assert out.exists()

    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == list(CANONICAL_COLUMNS)
    assert rows[1][0] == "01-01-2026 00:00"

    # output must be loadable by the project's own loader
    candles = load_ohlcv_csv(out)
    validate_dataset(candles)
    assert len(candles) == 50


def test_valid_native_data_round_trips(tmp_path) -> None:
    src = tmp_path / "native.csv"
    out = tmp_path / "oos.csv"
    write_native(src, hourly(30))

    report = normalize_source(src, out)

    assert report.accepted
    assert report.candle_count == 30
    candles = load_ohlcv_csv(out)
    validate_dataset(candles)
    assert candles[0].timestamp == BASE


def test_extra_columns_are_reported_not_dropped_silently(tmp_path) -> None:
    src = tmp_path / "wide.csv"
    out = tmp_path / "oos.csv"
    write_binance(src, hourly(10), unit="us", header=True)

    report = normalize_source(src, out)

    assert report.accepted
    assert "Close time" in report.extra_columns


# ------------------------------------------------------------- rejection


def test_missing_candles_are_detected_and_rejected(tmp_path) -> None:
    rows = hourly(10)
    del rows[4]                       # punch a hole
    src = tmp_path / "gap.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert len(report.missing_hours) == 1
    assert report.missing_hours[0][0] == BASE + timedelta(hours=3)
    assert report.missing_hours[0][1] == BASE + timedelta(hours=5)
    assert not out.exists(), "nothing may be written when data is rejected"


def test_duplicate_timestamps_are_detected_and_rejected(tmp_path) -> None:
    rows = hourly(10)
    rows.append(rows[3])               # exact duplicate
    src = tmp_path / "dupe.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert report.duplicate_timestamps
    assert not out.exists()


def test_invalid_ohlc_relationship_is_rejected(tmp_path) -> None:
    rows = hourly(10)
    stamp, o, h, l, c, v = rows[2]
    rows[2] = (stamp, o, 50.0, 90.0, c, v)      # high below low
    src = tmp_path / "bad_ohlc.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert any("high is below low" in reason for _, reason in report.invalid_rows)
    assert not out.exists()


def test_open_outside_range_is_rejected(tmp_path) -> None:
    rows = hourly(10)
    stamp, o, h, l, c, v = rows[1]
    rows[1] = (stamp, 500.0, h, l, c, v)
    src = tmp_path / "bad_open.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert any(
        "open outside" in reason for _, reason in report.invalid_rows
    )


def test_negative_volume_is_rejected(tmp_path) -> None:
    rows = hourly(10)
    stamp, o, h, l, c, _ = rows[5]
    rows[5] = (stamp, o, h, l, c, -1.0)
    src = tmp_path / "neg_vol.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert any(
        "negative volume" in reason for _, reason in report.invalid_rows
    )


def test_non_positive_price_is_rejected(tmp_path) -> None:
    rows = hourly(10)
    stamp, o, h, l, c, v = rows[3]
    rows[3] = (stamp, 0.0, h, l, c, v)
    src = tmp_path / "zero.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert any(
        "non-positive price" in reason for _, reason in report.invalid_rows
    )


def test_malformed_row_is_rejected(tmp_path) -> None:
    src = tmp_path / "malformed.csv"
    out = tmp_path / "oos.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        fh.write("Date,Open,High,Low,Close,Volume\n")
        fh.write("01-01-2026 00:00,100,102,98,101,10\n")
        fh.write("01-01-2026 01:00,not-a-number,102,98,101,10\n")
        fh.write("01-01-2026 02:00,100,102,98,101,10\n")

    report = normalize_source(src, out)

    assert not report.accepted
    assert report.errors
    assert "structural parse failure" in report.errors[0]
    assert not out.exists()


def test_short_row_is_rejected(tmp_path) -> None:
    src = tmp_path / "short.csv"
    out = tmp_path / "oos.csv"
    src.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "01-01-2026 00:00,100,102,98\n",
        encoding="utf-8",
    )

    report = normalize_source(src, out)

    assert not report.accepted
    assert not out.exists()


def test_incorrect_column_names_are_rejected(tmp_path) -> None:
    src = tmp_path / "wrongcols.csv"
    out = tmp_path / "oos.csv"
    src.write_text(
        "when,op,hi,lo,cl,vol\n01-01-2026 00:00,100,102,98,101,10\n",
        encoding="utf-8",
    )

    report = normalize_source(src, out)

    assert not report.accepted
    assert report.errors


def test_misaligned_timestamp_is_rejected(tmp_path) -> None:
    src = tmp_path / "misaligned.csv"
    out = tmp_path / "oos.csv"
    src.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "01-01-2026 00:30,100,102,98,101,10\n"
        "01-01-2026 01:30,100,102,98,101,10\n",
        encoding="utf-8",
    )

    report = normalize_source(src, out)

    assert not report.accepted
    assert any(
        "whole hour" in reason for _, reason in report.invalid_rows
    )


def test_out_of_order_rows_are_detected(tmp_path) -> None:
    rows = hourly(6)
    rows[2], rows[3] = rows[3], rows[2]
    src = tmp_path / "unordered.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert report.out_of_order_rows


# ------------------------------------------------------- research overlap


def test_overlap_with_research_window_is_rejected(tmp_path) -> None:
    rows = hourly(5, start=datetime(2025, 12, 30, 0, 0))
    src = tmp_path / "overlap.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)

    assert not report.accepted
    assert report.overlapping_rows
    assert not out.exists()


def test_overlap_can_be_allowed_explicitly(tmp_path) -> None:
    rows = hourly(5, start=datetime(2025, 12, 30, 0, 0))
    src = tmp_path / "overlap2.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(
        src, out, allow_overlap_with_research=True
    )

    assert report.accepted
    assert out.exists()


def test_non_strict_mode_writes_but_still_reports(tmp_path) -> None:
    rows = hourly(10)
    del rows[4]
    src = tmp_path / "gap2.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out, strict=False)

    # written, but explicitly NOT accepted
    assert report.written is True
    assert report.accepted is False
    assert not report.is_clean
    assert report.missing_hours
    assert out.exists()


# ------------------------------------------------------ dataset protection


def test_refuses_to_write_the_protected_dataset(tmp_path) -> None:
    src = tmp_path / "src.csv"
    write_native(src, hourly(5))
    bad_out = tmp_path / PROTECTED_DATASET

    with pytest.raises(AcquisitionError, match="protected dataset"):
        normalize_source(src, bad_out)


def test_refuses_identical_source_and_output(tmp_path) -> None:
    src = tmp_path / "same.csv"
    write_native(src, hourly(5))

    with pytest.raises(AcquisitionError, match="must differ"):
        normalize_source(src, src)


def test_source_file_is_never_modified(tmp_path) -> None:
    src = tmp_path / "src.csv"
    write_native(src, hourly(20))
    before = sha256_of(src)

    normalize_source(src, tmp_path / "oos.csv")

    assert sha256_of(src) == before


def test_original_research_dataset_is_untouched(tmp_path) -> None:
    """The real 2024-2025 dataset must not change during acquisition."""

    original = Path("data") / PROTECTED_DATASET
    if not original.exists():
        pytest.skip("research dataset not present in this checkout")

    before = sha256_of(original)

    src = tmp_path / "src.csv"
    write_native(src, hourly(20))
    normalize_source(src, tmp_path / "oos.csv")

    assert sha256_of(original) == before


# ------------------------------------------------------------- reporting


def test_write_report_produces_readable_output(tmp_path) -> None:
    rows = hourly(10)
    del rows[4]
    src = tmp_path / "g.csv"
    out = tmp_path / "oos.csv"
    write_native(src, rows)

    report = normalize_source(src, out)
    target = tmp_path / "report.txt"
    write_report(report, target)
    text = target.read_text(encoding="utf-8")

    assert "REJECTED" in text
    assert "MISSING HOURLY INTERVALS" in text
    assert "VERDICT" in text
    assert str(report.source_sha256) in text
