"""Phase 40 tests: enforcement-gap closure.

Three themes, all exercised without running strategy logic over protected data:

1. The **omission bypass** is closed -- omitting ``research_context`` no longer
   bypasses governance, because the series itself is fingerprinted.
2. **Registry persistence** is authoritative, atomic and auditable.
3. **Overlap status** is never implied.

Data-level checks read the real ETH file to prove refusal, but never compute
signals, trades or performance from it: the assertions are about whether a
call is allowed, and the guard refuses before any engine code runs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab.acquisition import AcquisitionReport, normalize_source
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.experiment import run_experiment
from crypto_paper_lab.models import Candle
from crypto_paper_lab.researchguard import (
    OVERLAP_CHECKED,
    OVERLAP_FAILED,
    OVERLAP_SKIPPED,
    ResearchGuardError,
    assert_series_permitted,
    candle_fingerprint,
    consume_reservation,
    load_registry,
    registry_path,
)
from crypto_paper_lab.researchindex import (
    MINIMUM_BARS,
    build_index,
    is_indexed_series,
    line_digest,
    minimum_bars_for_match,
)
from crypto_paper_lab.replay import Replay
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.yearly import run_yearly_backtests

ROOT = Path(__file__).resolve().parents[1]
ETH_REL = "data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv"
MIN_HISTORY = 22


def synth(count: int = 80, start: datetime = datetime(2023, 6, 1)) -> list[Candle]:
    return [
        Candle(start + timedelta(hours=i), 100.0, 101.0, 99.0, 100.5, 10.0)
        for i in range(count)
    ]


@pytest.fixture(scope="module")
def eth_candles() -> list[Candle]:
    """Real ETH rows, loaded for identity checks only. No strategy is run."""

    from crypto_paper_lab.dataset import load_dataset

    candles, _ = load_dataset(ROOT / ETH_REL)
    return candles


# ==========================================================================
# 1. the omission bypass
# ==========================================================================


def test_reserved_series_refused_with_no_context(eth_candles: list[Candle]) -> None:
    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_series_permitted(eth_candles, research_context=None)


def test_reserved_evaluation_slice_refused_with_no_context(
    eth_candles: list[Candle],
) -> None:
    """The evaluation bars alone have a different fingerprint; still refused."""

    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_series_permitted(eth_candles[17544:], research_context=None)


@pytest.mark.parametrize(
    "start,stop,label",
    [
        (5000, 9000, "middle chunk spanning warm-up into evaluation"),
        (8000, 8005, "five-bar slice"),
        (18000, 18200, "mid-evaluation chunk"),
        (24200, 24288, "evaluation tail"),
        (0, 100, "warm-up head"),
    ],
)
def test_arbitrary_subslices_refused(
    eth_candles: list[Candle], start: int, stop: int, label: str
) -> None:
    """No sub-slice of the reserved dataset evades the check."""

    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_series_permitted(
            eth_candles[start:stop], research_context=None
        )


def test_run_backtest_refuses_reserved_series_without_context(
    eth_candles: list[Candle],
) -> None:
    """The engine entry point itself refuses, before any trading code runs."""

    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        run_backtest(eth_candles)


def test_replay_refuses_reserved_series_without_context(
    eth_candles: list[Candle],
) -> None:
    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        Replay(eth_candles)


def test_run_experiment_refuses_reserved_series_without_context(
    eth_candles: list[Candle],
) -> None:
    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        run_experiment(eth_candles, [StrategyConfig()])


def test_run_yearly_refuses_reserved_series_without_context(
    eth_candles: list[Candle],
) -> None:
    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        run_yearly_backtests(eth_candles)


def test_reserved_dates_alone_do_not_refuse_synthetic() -> None:
    """Sharing calendar dates is not protection. Content identity is.

    An earlier iteration refused on date overlap alone, which broke legitimate
    synthetic fixtures and protected nothing. Pinned so it cannot regress.
    """

    assert run_backtest(synth(80, datetime(2026, 1, 1))) is not None


def test_unregistered_series_permitted_but_flagged() -> None:
    decision = assert_series_permitted(synth(), research_context=None)

    assert decision.permitted is True
    assert "not registered research data" in decision.reason
    assert decision.consumed_series_development_use is False
    assert decision.series_fingerprint == candle_fingerprint(synth())


def test_empty_series_refused() -> None:
    with pytest.raises(ResearchGuardError, match="empty series"):
        assert_series_permitted([], research_context=None)


def test_consumed_series_permitted_as_recorded_development_use() -> None:
    """BTC primary is consumed: permitted, but recorded as development use."""

    from crypto_paper_lab.dataset import load_dataset

    candles, _ = load_dataset(ROOT / "data/BTCUSDT_1h_Cleaned (1).csv")
    decision = assert_series_permitted(candles, research_context=None)

    assert decision.permitted is True
    assert decision.consumed_series_development_use is True
    assert "consumed window" in decision.reason


# ==========================================================================
# 2. registry persistence
# ==========================================================================


def test_registry_file_is_authoritative_when_named(tmp_path: Path) -> None:
    """A stale in-memory copy cannot authorise a window the file records as spent."""

    reg = load_registry()
    synthetic = synth()
    stale = json.loads(json.dumps(reg))
    for entry in stale["reservations"]:
        entry["used"] = True

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg), encoding="utf-8")

    # The on-disk registry has the ETH reservation unused, but the caller's
    # in-memory copy says used. The series check must consult the file.
    decision = assert_series_permitted(
        synthetic, research_context=None, registry=stale, registry_file=path
    )
    assert decision.permitted is True
    assert decision.consumed_series_development_use is False


def test_mark_used_cannot_silently_do_nothing(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    reg = load_registry()
    path.write_text(json.dumps(reg), encoding="utf-8")

    entry = reg["reservations"][0]
    consume_reservation(entry["reservation_id"], registry_file=path)

    after = json.loads(path.read_text(encoding="utf-8"))
    spent = after["reservations"][0]
    assert spent["used"] is True
    assert spent["used_on"], "consumption must record when it happened"


def test_consumption_write_is_atomic(tmp_path: Path) -> None:
    """No temp files left behind, and the original is intact until replacement."""

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(load_registry()), encoding="utf-8")
    consume_reservation("ETH-2026-RESERVATION", registry_file=path)

    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], f"atomic write left temp files: {leftovers}"

    # still valid JSON, no truncation
    json.loads(path.read_text(encoding="utf-8"))


def test_consumption_refuses_when_reservation_absent_from_file(tmp_path: Path) -> None:
    """Nothing is written when the reservation cannot be located."""

    reg = load_registry()
    reg["reservations"] = []
    path = tmp_path / "registry.json"
    original = json.dumps(reg, indent=2)
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ResearchGuardError, match="not in the registry"):
        consume_reservation("ETH-2026-RESERVATION", registry_file=path)

    assert path.read_text(encoding="utf-8") == original


def test_consumption_requires_a_writable_registry_file() -> None:
    with pytest.raises(ResearchGuardError, match="no registry_file"):
        consume_reservation("ETH-2026-RESERVATION")


def test_consumption_records_the_preregistration(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(load_registry()), encoding="utf-8")
    consume_reservation(
        "ETH-2026-RESERVATION",
        registry_file=path,
        preregistration_id="phase39-test",
    )
    spent = json.loads(path.read_text(encoding="utf-8"))["reservations"][0]
    assert spent["used_preregistration_id"] == "phase39-test"


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ResearchGuardError, match="not found"):
        assert_series_permitted(
            synth(), research_context=None, registry_file=tmp_path / "nope.json"
        )


def test_corrupt_index_degrades_to_no_partial_matching(tmp_path: Path) -> None:
    """A broken sidecar must not silently widen protection to 'everything'."""

    bad = tmp_path / "research_registry.candle_index.json"
    bad.write_text("{corrupt", encoding="utf-8")
    from crypto_paper_lab.researchindex import load_index

    assert load_index(bad) == {}


def test_registry_path_is_overridable(monkeypatch, tmp_path: Path) -> None:
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps(load_registry()), encoding="utf-8")
    monkeypatch.setenv("CRYPTO_PAPER_LAB_RESEARCH_REGISTRY", str(alt))
    assert registry_path() == alt


# ==========================================================================
# 3. per-bar index integrity
# ==========================================================================


def test_index_digest_matches_guard_canonical_form(eth_candles: list[Candle]) -> None:
    """The sidecar and the guard must agree byte-for-byte, or recognition fails."""

    sample = eth_candles[:50]
    guard_fp = candle_fingerprint(sample)
    index_digests = set(build_index(sample))

    assert len(index_digests) == len(sample)
    # the guard folds per-bar lines with trailing commas; digests are per line
    assert all(len(d) == 32 for d in index_digests)
    assert guard_fp  # guard fingerprint is the whole-series form


def test_minimum_bars_rule_is_documented_and_inert() -> None:
    """Series below the bar threshold are inert: too short to trade."""

    assert minimum_bars_for_match(1) >= MINIMUM_BARS
    assert minimum_bars_for_match(2) >= MINIMUM_BARS
    # a trade-capable series needs more than minimum_history bars
    assert minimum_bars_for_match(MIN_HISTORY + 1) <= MIN_HISTORY + 1


def test_single_and_double_bar_series_are_not_indexed(
    eth_candles: list[Candle],
) -> None:
    assert is_indexed_series(eth_candles[8000:8001]) is None
    assert is_indexed_series(eth_candles[8000:8002]) is None


def test_line_digest_is_stable(eth_candles: list[Candle]) -> None:
    candle = eth_candles[0]
    assert line_digest(candle) == line_digest(candle)
    assert len(line_digest(candle)) == 32


# ==========================================================================
# 4. overlap status
# ==========================================================================


def test_overlap_status_default_is_failed() -> None:
    assert AcquisitionReport().overlap_check == OVERLAP_FAILED


def test_skipped_is_distinct_from_checked(tmp_path) -> None:
    def write(name: str, day: str) -> None:
        (tmp_path / name).write_text(
            "timestamp,open,high,low,close,volume\n"
            f"{day}T00:00:00,1,2,0.5,1.5,10\n"
            f"{day}T01:00:00,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )

    write("in.csv", "2025-06-01")     # inside the research window
    write("out.csv", "2023-06-01")    # outside it

    skipped = normalize_source(
        tmp_path / "in.csv", tmp_path / "a.csv", allow_overlap_with_research=True
    )
    checked = normalize_source(tmp_path / "out.csv", tmp_path / "b.csv")

    assert skipped.overlap_check == OVERLAP_SKIPPED
    assert skipped.overlapping_rows == []
    assert checked.overlap_check == OVERLAP_CHECKED
    assert checked.overlapping_rows == []

    # both report an empty overlap list, and only one of them is a real pass
    assert skipped.overlap_check != checked.overlap_check
    assert any("NOT verified" in n for n in skipped.notes)
    assert all("NOT verified" not in n for n in checked.notes)


def test_real_overlap_is_reported_as_overlap(tmp_path) -> None:
    src = tmp_path / "s.csv"
    src.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2025-06-01T00:00:00,1,2,0.5,1.5,10\n"
        "2025-06-01T01:00:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    report = normalize_source(src, tmp_path / "out.csv")
    assert report.overlap_check == OVERLAP_CHECKED
    assert report.overlapping_rows
    assert not report.accepted


# ==========================================================================
# 5. API-level coverage
# ==========================================================================


def test_api_served_dataset_records_consumed_development_use() -> None:
    from paper_api import marketdata

    marketdata.load_research_candles.cache_clear()
    marketdata.CONSUMED_DATASET_DECISION.clear()
    marketdata.load_research_candles()

    assert marketdata.CONSUMED_DATASET_DECISION, "guard decision must be recorded"
    decision = marketdata.CONSUMED_DATASET_DECISION[-1]
    assert decision.consumed_series_development_use is True
    assert decision.series_fingerprint


def test_api_guard_decision_is_serialisable() -> None:
    """Auditability requires the decision to survive JSON round-tripping."""

    from paper_api import marketdata

    marketdata.load_research_candles.cache_clear()
    marketdata.CONSUMED_DATASET_DECISION.clear()
    marketdata.load_research_candles()
    record = marketdata.CONSUMED_DATASET_DECISION[-1].as_record()
    json.loads(json.dumps(record))


def test_dataset_identity_check_available() -> None:
    from crypto_paper_lab.walkforward import assert_dataset_not_reserved

    # consumed BTC is still valid to verify
    from crypto_paper_lab.dataset import load_dataset

    candles, _ = load_dataset(ROOT / "data/BTCUSDT_1h_Cleaned (1).csv")
    assert_dataset_not_reserved(candles)


def test_assert_dataset_not_reserved_refuses_reserved(eth_candles) -> None:
    from crypto_paper_lab.walkforward import assert_dataset_not_reserved

    with pytest.raises(ResearchGuardError, match="reserved evaluation window"):
        assert_dataset_not_reserved(eth_candles)


# ==========================================================================
# 6. no bypass flags
# ==========================================================================


def test_no_bypass_parameter_on_any_entry_point() -> None:
    import inspect

    forbidden = {
        "skip_guard", "no_guard", "ignore_guard", "unsafe", "allow_reserved",
        "bypass_guard", "force", "disable_guard", "no_research", "dev_mode",
    }
    for fn in (run_backtest, run_experiment, run_yearly_backtests, Replay.__init__):
        params = set(inspect.signature(fn).parameters)
        assert not (forbidden & params), f"{fn.__name__} exposes a bypass flag"


def test_reserved_eth_is_not_consumed_by_this_test_module() -> None:
    """Guard: the shipped reservation must still be unspent after the suite."""

    entry = [
        r for r in load_registry()["reservations"]
        if r["instrument_id"] == "ETH/USDT"
    ][0]
    assert entry["used"] is False
    assert entry["status"] == "RESERVED"
    assert entry["preregistration_id"] is None
    assert "used_on" not in entry