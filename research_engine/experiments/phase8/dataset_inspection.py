"""Phase 8 step 1: dataset inspection and search for genuinely unseen data.

Reports exactly what OHLCV data exists in the repository, its range,
quality, and whether ANY candle exists after the Phase 7 period.
"""
import csv
import hashlib
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from crypto_paper_lab.data import _parse_timestamp, load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset

PHASE7_END = datetime(2025, 12, 31, 23, 0)
DATA_DIR = Path("data")

print("=" * 100)
print("PHASE 8 - DATASET INVENTORY")
print("=" * 100)

files = sorted(p for p in DATA_DIR.rglob("*") if p.is_file())
print(f"\nFiles under {DATA_DIR}/ : {len(files)}")
for p in files:
    size = p.stat().st_size
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    print(f"  {p.as_posix():45s} {size:>10d} bytes  sha256:{digest}")

usable = []
for p in files:
    if p.stat().st_size < 100:
        print(f"\n  SKIP {p.name}: file is effectively empty "
              f"({p.stat().st_size} bytes) - no usable candles")
        continue
    usable.append(p)

print()
print("=" * 100)
print("PER-FILE QUALITY INSPECTION")
print("=" * 100)

summary_rows = []
for p in usable:
    print(f"\n--- {p.as_posix()} ---")
    try:
        candles = load_ohlcv_csv(p)
    except Exception as exc:  # noqa: BLE001
        print(f"  LOAD FAILED: {type(exc).__name__}: {exc}")
        continue

    print(f"  candles        : {len(candles)}")
    print(f"  first          : {candles[0].timestamp}")
    print(f"  last           : {candles[-1].timestamp}")
    print(f"  naive datetimes: {candles[0].timestamp.tzinfo is None}")

    # ordering / duplicates
    ts = [c.timestamp for c in candles]
    dupes = [t for t, n in Counter(ts).items() if n > 1]
    non_increasing = sum(1 for a, b in zip(ts, ts[1:]) if b <= a)
    print(f"  duplicates     : {len(dupes)}")
    print(f"  non-increasing : {non_increasing}")

    # gaps
    gaps = []
    for a, b in zip(ts, ts[1:]):
        delta = b - a
        if delta != timedelta(hours=1):
            gaps.append((a, b, delta))
    total_missing = sum(
        int((delta - timedelta(hours=1)).total_seconds() // 3600)
        for _, _, delta in gaps
    )
    print(f"  irregular gaps : {len(gaps)}")
    print(f"  missing hours  : {total_missing}")
    for a, b, delta in gaps[:10]:
        print(f"      {a} -> {b}  ({delta})")

    # OHLC integrity
    bad_high_low = sum(1 for c in candles if c.high < c.low)
    bad_open = sum(1 for c in candles if not (c.low <= c.open <= c.high))
    bad_close = sum(1 for c in candles if not (c.low <= c.close <= c.high))
    neg_vol = sum(1 for c in candles if c.volume < 0)
    nonpos_price = sum(1 for c in candles if min(c.open, c.high, c.low, c.close) <= 0)
    zeros = sum(1 for c in candles if c.close == 0)
    print(f"  high<low       : {bad_high_low}")
    print(f"  open out range : {bad_open}")
    print(f"  close out range: {bad_close}")
    print(f"  negative volume: {neg_vol}")
    print(f"  nonpos price   : {nonpos_price}")
    print(f"  zero close     : {zeros}")

    # validation helper
    try:
        validate_dataset(candles)
        print("  validate_dataset: PASS")
    except ValueError as exc:
        print(f"  validate_dataset: FAIL -> {exc}")

    # price extremes
    hi = max(c.high for c in candles)
    lo = min(c.low for c in candles)
    print(f"  price range    : {lo:.2f} .. {hi:.2f}")

    # candles after the Phase 7 window
    after = [c for c in candles if c.timestamp > PHASE7_END]
    print(f"  candles AFTER {PHASE7_END}: {len(after)}")

    summary_rows.append({
        "file": p.as_posix(),
        "n": len(candles),
        "first": candles[0].timestamp,
        "last": candles[-1].timestamp,
        "after_phase7": len(after),
        "missing_hours": total_missing,
        "gaps": len(gaps),
        "dupes": len(dupes),
        "validate": "PASS",
    })

print()
print("=" * 100)
print("SEARCH FOR UNSEEN DATA - VERDICT")
print("=" * 100)
total_after = sum(r["after_phase7"] for r in summary_rows)
if not summary_rows:
    print("  No usable OHLCV dataset found.")
elif total_after == 0:
    print("  Usable datasets found: " + ", ".join(r["file"] for r in summary_rows))
    print()
    print("  >>> NO CANDLES EXIST AFTER 2025-12-31 23:00 IN THIS REPOSITORY.")
    print("  >>> There is NO genuinely unseen post-Phase-7 data available.")
else:
    print(f"  Found {total_after} candles after the Phase 7 window.")
    for r in summary_rows:
        print(f"    {r['file']}: {r['after_phase7']} candles after {PHASE7_END}")

print()
print("=" * 100)
print("HEADER / FORMAT DETAIL of the primary dataset")
print("=" * 100)
for p in usable:
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        first = next(reader)
        second = next(reader)
    print(f"  {p.name}")
    print(f"    header : {header}")
    print(f"    row 1  : {first}")
    print(f"    row 2  : {second}")
