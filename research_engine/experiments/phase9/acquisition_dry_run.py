"""Phase 9: end-to-end exercise of the acquisition workflow.

IMPORTANT: every fixture in this script is SYNTHETIC and invented. It exists
only to demonstrate that the acquisition and validation tooling behaves
correctly. Nothing here is real market data and nothing here is a research
result. No network access and no download occurs.

Run:
    python experiments/phase9/acquisition_dry_run.py
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.acquisition import (  # noqa: E402
    CANONICAL_COLUMNS,
    PROTECTED_DATASET,
    normalize_source,
    sha256_of,
    write_report,
)

TMP = Path(__file__).resolve().parent / "_synthetic_fixtures"
FIXTURE_START = datetime(2026, 1, 1, 0, 0)
RESEARCH_DATASET = Path("data") / PROTECTED_DATASET


def synth(count, start=FIXTURE_START, price=93_000.0, skip=()):
    rows = []
    for i in range(count):
        if i in skip:
            continue
        stamp = start + timedelta(hours=i)
        drift = price * (1 + 0.0004 * i)
        rows.append((stamp, drift, drift * 1.002, drift * 0.998,
                     drift * 1.0005, 400.0 + i))
    return rows


def write_binance(path, rows, unit="us", header=False):
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
            secs = int((stamp - datetime(1970, 1, 1)).total_seconds())
            open_time = secs * {"s": 1, "ms": 1000, "us": 1_000_000}[unit]
            w.writerow([open_time, f"{o:.2f}", f"{h:.2f}", f"{l:.2f}",
                        f"{c:.2f}", f"{v:.3f}", 0, 0, 0, 0, 0, 0])


def write_native(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CANONICAL_COLUMNS)
        for stamp, o, h, l, c, v in rows:
            w.writerow([stamp.strftime("%d-%m-%Y %H:%M"),
                        f"{o:.2f}", f"{h:.2f}", f"{l:.2f}",
                        f"{c:.2f}", f"{v:.3f}"])


def show(title, report):
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)
    for line in report.summary_lines():
        print(f"  {line}")


def main():
    print("=" * 78)
    print("PHASE 9 ACQUISITION DRY RUN - ALL FIXTURES ARE SYNTHETIC")
    print("=" * 78)
    print("No network access. No download. No real market data.")
    print("Purpose: prove the validation tool accepts good data and rejects bad.")

    if RESEARCH_DATASET.exists():
        before = sha256_of(RESEARCH_DATASET)
        print(f"\nresearch dataset sha256 BEFORE: {before}")
    else:
        before = None
        print("\nresearch dataset not present; protection check skipped")

    TMP.mkdir(parents=True, exist_ok=True)
    accepted_dir = Path("data") / "oos"
    out = accepted_dir / "SYNTHETIC_dryrun_NOT_REAL.csv"
    report_path = TMP / "report.txt"

    # 1. clean Binance-layout microsecond data
    src_ok = TMP / "synthetic_clean_us.csv"
    write_binance(src_ok, synth(720))
    r1 = normalize_source(src_ok, out)
    show("CASE 1  clean Binance-layout 1h (microsecond stamps) - expect ACCEPT",
         r1)

    # 2. millisecond stamps
    src_ms = TMP / "synthetic_clean_ms.csv"
    write_binance(src_ms, synth(240, start=datetime(2026, 4, 1)), unit="ms")
    r2 = normalize_source(src_ms, TMP / "ms_out.csv")
    show("CASE 2  millisecond stamps - expect ACCEPT (unit auto-detected)", r2)

    # 3. headered Binance layout
    src_hdr = TMP / "synthetic_header.csv"
    write_binance(src_hdr, synth(48, start=datetime(2026, 5, 1)), header=True)
    r3 = normalize_source(src_hdr, TMP / "hdr_out.csv")
    show("CASE 3  Binance layout with header row - expect ACCEPT", r3)

    # 4. missing candles
    src_gap = TMP / "synthetic_gap.csv"
    write_native(src_gap, synth(200, skip={50, 51, 52}))
    r4 = normalize_source(src_gap, TMP / "gap_out.csv")
    show("CASE 4  three missing hourly candles - expect REJECT", r4)

    # 5. duplicates
    dup_rows = synth(50)
    dup_rows = dup_rows + [dup_rows[10]]
    src_dupe = TMP / "synthetic_dupe.csv"
    write_native(src_dupe, dup_rows)
    r5 = normalize_source(src_dupe, TMP / "dupe_out.csv")
    show("CASE 5  duplicate timestamp - expect REJECT", r5)

    # 6. invalid OHLC
    bad_rows = synth(50)
    stamp, o, h, l, c, v = bad_rows[7]
    bad_rows[7] = (stamp, o, 50.0, 99_000.0, c, v)      # high < low
    src_bad = TMP / "synthetic_bad_ohlc.csv"
    write_native(src_bad, bad_rows)
    r6 = normalize_source(src_bad, TMP / "bad_out.csv")
    show("CASE 6  high below low - expect REJECT", r6)

    # 7. overlap with the research window
    src_overlap = TMP / "synthetic_overlap.csv"
    write_native(src_overlap, synth(10, start=datetime(2025, 12, 29)))
    r7 = normalize_source(src_overlap, TMP / "overlap_out.csv")
    show("CASE 7  overlaps 2024-2025 research window - expect REJECT", r7)

    # 8. malformed rows
    src_malformed = TMP / "synthetic_malformed.csv"
    src_malformed.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "01-06-2026 00:00,93000,94000,92000,93500,400\n"
        "01-06-2026 01:00,NOT_A_NUMBER,94000,92000,93500,400\n",
        encoding="utf-8",
    )
    r8 = normalize_source(src_malformed, TMP / "malformed_out.csv")
    show("CASE 8  non-numeric field - expect REJECT", r8)

    # 9. wrong column names
    src_wrong = TMP / "synthetic_wrongcols.csv"
    src_wrong.write_text(
        "when,op,hi,lo,cl,vol\n01-06-2026 00:00,93000,94000,92000,93500,400\n",
        encoding="utf-8",
    )
    r9 = normalize_source(src_wrong, TMP / "wrong_out.csv")
    show("CASE 9  unrecognised column names - expect REJECT", r9)

    # 10. protected dataset guard
    print()
    print("-" * 78)
    print("CASE 10 attempt to write the protected research dataset")
    print("-" * 78)
    try:
        normalize_source(src_ok, Path("data") / PROTECTED_DATASET)
        print("  FAILED - the guard did not fire")
    except Exception as exc:
        print(f"  correctly refused: {type(exc).__name__}: {exc}")

    write_report(r1, report_path)
    print(f"\nreport written to {report_path.as_posix()}")

    # cleanup any file the dry run produced in data/oos
    if out.exists():
        out.unlink()
        print(f"removed synthetic output {out.as_posix()} "
              "(data/oos left with README only)")

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for label, report, expected in (
        ("clean us", r1, True), ("clean ms", r2, True),
        ("headered", r3, True), ("gap", r4, False),
        ("duplicate", r5, False), ("bad OHLC", r6, False),
        ("overlap", r7, False), ("malformed", r8, False),
        ("wrong columns", r9, False),
    ):
        got = report.accepted
        print(f"  {label:14s} accepted={str(got):5s} "
              f"expected={str(expected):5s} {'OK' if got == expected else 'MISMATCH'}")

    if before is not None:
        after = sha256_of(RESEARCH_DATASET)
        print()
        print(f"research dataset sha256 AFTER : {after}")
        print(f"UNCHANGED: {before == after}")
        if before != after:
            print("WARNING: the protected dataset changed during the dry run")
            return 1

    print()
    print("Dry run complete. No data was acquired and none is claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
