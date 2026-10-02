"""Phase 10 step 2: merge accepted months and run continuity checks.

Combines only accepted normalised months into a separate 2026 dataset.
Never modifies the original 2024-2025 dataset. Reports duplicates, missing
hours and the boundary against the research dataset instead of repairing
anything.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.acquisition import (  # noqa: E402
    CANONICAL_COLUMNS,
    normalize_source,
    sha256_of,
    write_report,
)
from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.dataset import validate_dataset  # noqa: E402

OOS = Path("data/oos")
RESEARCH = Path("data") / "BTCUSDT_1h_Cleaned (1).csv"
MERGED = OOS / "binance_spot_BTCUSDT_1h_202601-202608.csv"
MONTHS = ["202601", "202602", "202603", "202604",
          "202605", "202606", "202607", "202608"]
HOUR = timedelta(hours=1)


def parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%d-%m-%Y %H:%M")


def main() -> int:
    print("=" * 96)
    print("PHASE 10 STEP 2 - MERGE AND CONTINUITY CHECKS")
    print("=" * 96)

    research_sha_before = sha256_of(RESEARCH) if RESEARCH.exists() else None
    if research_sha_before:
        print(f"research dataset sha256 BEFORE : {research_sha_before}")

    # ---- read accepted months -------------------------------------------
    rows = []
    for tag in MONTHS:
        path = OOS / f"binance_spot_BTCUSDT_1h_{tag}.csv"
        if not path.exists():
            print(f"  MISSING normalised month file: {path}")
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            import csv
            reader = csv.reader(fh)
            header = next(reader)
            assert header == list(CANONICAL_COLUMNS), header
            count = 0
            for cells in reader:
                rows.append((parse(cells[0]),
                             float(cells[1]), float(cells[2]),
                             float(cells[3]), float(cells[4]),
                             float(cells[5])))
                count += 1
        print(f"  read {path.name}: {count} candles")

    print(f"\nmerged rows before sort : {len(rows)}")
    rows.sort(key=lambda r: r[0])
    print("sorted by timestamp")

    # ---- duplicates ------------------------------------------------------
    seen = {}
    dupes = []
    for stamp, *_ in rows:
        if stamp in seen:
            dupes.append(stamp)
        else:
            seen[stamp] = True
    print(f"duplicate timestamps   : {len(dupes)}")
    for stamp in dupes[:10]:
        print(f"    duplicate: {stamp}")

    # ---- missing hours ---------------------------------------------------
    unique = sorted(seen)
    gaps = []
    for previous, current in zip(unique, unique[1:]):
        delta = current - previous
        if delta != HOUR:
            missing = int((delta - HOUR).total_seconds() // 3600)
            gaps.append((previous, current, missing))
    total_missing = sum(g[2] for g in gaps)
    print(f"missing intervals      : {len(gaps)}")
    print(f"missing hours total    : {total_missing}")
    for previous, current, missing in gaps[:10]:
        print(f"    gap: {previous} -> {current} ({missing} hours absent)")

    # ---- boundary with the research dataset ------------------------------
    print()
    research_last = None
    if RESEARCH.exists():
        research = load_ohlcv_csv(RESEARCH)
        validate_dataset(research)
        research_last = research[-1].timestamp
        print(f"research dataset last candle : {research_last}")
        print(f"new data first candle        : {unique[0]}")
        delta = unique[0] - research_last
        print(f"boundary delta               : {delta}")
        if delta == HOUR:
            print("BOUNDARY: contiguous (exactly one hour apart)")
        elif delta > HOUR:
            print(f"BOUNDARY: {int((delta - HOUR).total_seconds() // 3600)} "
                  "hour(s) MISSING at the boundary")
        else:
            print("BOUNDARY: OVERLAP or out-of-order")
        if unique[0] <= research_last:
            print("UNSEEN-CHECK: FAILED - new data is not strictly after research data")
        else:
            print("UNSEEN-CHECK: PASSED - new data starts strictly after research data")

    # ---- write merged file ----------------------------------------------
    if dupes or gaps:
        print()
        print("RESULT: duplicates and/or gaps found - merged dataset NOT written")
        return 1

    import csv
    with MERGED.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CANONICAL_COLUMNS)
        for stamp, o, h, l, c, v in rows:
            writer.writerow([stamp.strftime("%d-%m-%Y %H:%M"), o, h, l, c, v])

    print()
    print(f"merged dataset written : {MERGED.as_posix()}")
    print(f"merged candles         : {len(rows)}")
    print(f"first / last           : {unique[0]} -> {unique[-1]}")

    # ---- re-validate the merged file through the Phase 9 utility ---------
    revalidated = OOS / "_revalidate_input.csv"
    revalidated.write_bytes(MERGED.read_bytes())
    report = normalize_source(revalidated, OOS / "_revalidate_output.csv")
    print()
    print("re-validation of the merged dataset via normalize_source():")
    for line in report.summary_lines():
        print(f"  {line}")
    report_path = OOS / f"{MERGED.name}.report.txt"
    write_report(report, report_path)
    revalidated.unlink(missing_ok=True)
    (OOS / "_revalidate_output.csv").unlink(missing_ok=True)

    # ---- load through the project loader ---------------------------------
    candles = load_ohlcv_csv(MERGED)
    validate_dataset(candles)
    print()
    print(f"load_ohlcv_csv + validate_dataset : PASS ({len(candles)} candles)")
    print(f"merged sha256 : {sha256_of(MERGED)}")
    print(f"report        : {report_path.as_posix()}")

    if research_sha_before:
        after = sha256_of(RESEARCH)
        print()
        print(f"research dataset sha256 AFTER : {after}")
        print(f"research dataset UNCHANGED   : {after == research_sha_before}")

    return 0 if report.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
