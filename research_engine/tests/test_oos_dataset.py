"""Tests for the Phase 10 out-of-sample dataset artifacts.

These tests are offline: they never touch the network. They validate the
artifacts that Phase 10 downloaded and normalised, and they pin the original
research dataset so any future modification is caught.

Every test skips cleanly when the artifacts are absent, so the suite still
passes in a checkout that has no ``data/oos`` content.
"""
import csv
import hashlib
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.strategy import StrategyConfig

OOS_DIR = Path("data/oos")
RAW_DIR = OOS_DIR / "raw"
MERGED = OOS_DIR / "binance_spot_BTCUSDT_1h_202601-202608.csv"
RESEARCH = Path("data") / "BTCUSDT_1h_Cleaned (1).csv"

#: Pinned in Phase 8/9. Any change means the research dataset was modified.
RESEARCH_SHA256 = (
    "201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b"
)

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08"]
EXPECTED_CANDLES = 5832          # 8 months of hourly candles in 2026
EXPECTED_FIRST = datetime(2026, 1, 1, 0, 0)
EXPECTED_LAST = datetime(2026, 8, 31, 23, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def need_merged() -> Path:
    if not MERGED.exists():
        pytest.skip("out-of-sample merged dataset not present")
    return MERGED


# ------------------------------------------------------- research dataset


def test_research_dataset_unchanged() -> None:
    if not RESEARCH.exists():
        pytest.skip("research dataset not present")
    assert sha256(RESEARCH) == RESEARCH_SHA256


def test_research_dataset_still_loads() -> None:
    if not RESEARCH.exists():
        pytest.skip("research dataset not present")
    candles = load_ohlcv_csv(RESEARCH)
    validate_dataset(candles)
    assert len(candles) == 17544
    assert candles[0].timestamp == datetime(2024, 1, 1, 0, 0)
    assert candles[-1].timestamp == datetime(2025, 12, 31, 23, 0)


# --------------------------------------------------------------- archives


@pytest.mark.parametrize("month", MONTHS)
def test_archive_matches_published_checksum(month: str) -> None:
    archive = RAW_DIR / f"BTCUSDT-1h-{month}.zip"
    checksum = Path(f"{archive}.CHECKSUM")
    if not archive.exists() or not checksum.exists():
        pytest.skip(f"archive for {month} not present")

    published = checksum.read_text(encoding="utf-8").split()[0].strip().lower()
    assert sha256(archive).lower() == published


@pytest.mark.parametrize("month", MONTHS)
def test_provenance_sidecar_exists(month: str) -> None:
    sidecar = RAW_DIR / f"BTCUSDT-1h-{month}.provenance.txt"
    if not (RAW_DIR / f"BTCUSDT-1h-{month}.zip").exists():
        pytest.skip(f"archive for {month} not present")
    assert sidecar.exists()
    text = sidecar.read_text(encoding="utf-8")
    assert "Checksum verified   : True" in text
    assert "BTC/USDT spot" in text


def test_unavailable_months_recorded() -> None:
    note = RAW_DIR / "UNAVAILABLE_MONTHS.txt"
    if not note.exists():
        pytest.skip("no download record present")
    text = note.read_text(encoding="utf-8")
    assert "2026-09" in text
    assert "404" in text


# ------------------------------------------------------------ merged data


def test_merged_dataset_candle_count() -> None:
    need_merged()
    candles = load_ohlcv_csv(MERGED)
    validate_dataset(candles)
    assert len(candles) == EXPECTED_CANDLES


def test_merged_dataset_date_range() -> None:
    need_merged()
    candles = load_ohlcv_csv(MERGED)
    assert candles[0].timestamp == EXPECTED_FIRST
    assert candles[-1].timestamp == EXPECTED_LAST


def test_merged_dataset_has_no_gaps() -> None:
    need_merged()
    candles = load_ohlcv_csv(MERGED)
    stamps = [c.timestamp for c in candles]
    for previous, current in zip(stamps, stamps[1:]):
        assert current - previous == timedelta(hours=1)


def test_merged_dataset_has_no_duplicates() -> None:
    need_merged()
    candles = load_ohlcv_csv(MERGED)
    counts = Counter(c.timestamp for c in candles)
    assert not [t for t, n in counts.items() if n > 1]


def test_merged_dataset_is_strictly_after_research_window() -> None:
    """The out-of-sample data must be genuinely unseen."""

    need_merged()
    candles = load_ohlcv_csv(MERGED)
    research_last = datetime(2025, 12, 31, 23, 0)
    assert candles[0].timestamp > research_last


def test_boundary_with_research_dataset_is_contiguous() -> None:
    if not (MERGED.exists() and RESEARCH.exists()):
        pytest.skip("datasets not both present")
    new_first = load_ohlcv_csv(MERGED)[0].timestamp
    research_last = load_ohlcv_csv(RESEARCH)[-1].timestamp
    assert new_first - research_last == timedelta(hours=1)


def test_merged_dataset_ohlc_is_valid() -> None:
    need_merged()
    for candle in load_ohlcv_csv(MERGED):
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high
        assert candle.volume >= 0
        assert min(candle.open, candle.high, candle.low, candle.close) > 0


def test_monthly_normalised_files_cover_the_whole_period() -> None:
    present = [
        OOS_DIR / f"binance_spot_BTCUSDT_1h_{m.replace('-', '')}.csv"
        for m in MONTHS
    ]
    if not any(p.exists() for p in present):
        pytest.skip("no normalised month files present")
    total = 0
    for path in present:
        if path.exists():
            total += sum(
                1 for _ in csv.DictReader(path.open(encoding="utf-8"))
            )
    assert total == EXPECTED_CANDLES


# ------------------------------------------------- configurations intact


def test_baseline_defaults_unchanged() -> None:
    config = StrategyConfig()
    assert config.lookback == 20
    assert config.fast_period == 5
    assert config.slow_period == 12
    assert config.breakout_buffer == 0.001
    assert config.retest_tolerance == 0.002
    assert config.min_breakout_distance == 0.0
    assert config.breakout_confirm_bars == 1
    assert config.max_holding_bars is None
    assert config.stop_loss_pct is None
    assert config.take_profit_pct is None
    assert config.allowed_sides is None


def test_a2_configuration_is_only_the_distance_filter() -> None:
    base = StrategyConfig()
    a2 = replace(base, min_breakout_distance=0.002)

    differing = {
        k for k in vars(a2) if getattr(base, k) != getattr(a2, k)
    }
    assert differing == {"min_breakout_distance"}
    assert a2.min_breakout_distance == 0.002


def test_baseline_still_reproduces_on_research_data() -> None:
    if not RESEARCH.exists():
        pytest.skip("research dataset not present")
    result = run_backtest(load_ohlcv_csv(RESEARCH))

    assert result.total_trades == 344
    # published figures are rounded to two decimals
    assert round(result.ending_balance, 2) == pytest.approx(9842.86, abs=1e-9)


def test_a2_still_reproduces_on_research_data() -> None:
    if not RESEARCH.exists():
        pytest.skip("research dataset not present")
    config = replace(StrategyConfig(), min_breakout_distance=0.002)
    result = run_backtest(load_ohlcv_csv(RESEARCH), config=config)

    assert result.total_trades == 284
    assert round(result.ending_balance, 2) == pytest.approx(9912.84, abs=1e-9)


def test_out_of_sample_data_does_not_affect_research_results() -> None:
    """The presence of OOS data must not change any in-sample figure."""

    if not RESEARCH.exists():
        pytest.skip("research dataset not present")

    result = run_backtest(load_ohlcv_csv(RESEARCH))
    assert result.total_trades == 344
    assert round(result.ending_balance, 2) == pytest.approx(9842.86, abs=1e-9)
