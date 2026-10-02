# Phase 9 — Acquisition Plan

This plan covers how additional BTC/USDT 1h candles dated after
2025-12-31 will be obtained and admitted. **Nothing has been downloaded.
Every step marked "operator" requires explicit authorisation from you.**

## Constraints

| Constraint | Rule |
|---|---|
| Downloads | Never performed by this project. Operator performs them. |
| Original dataset | `data/BTCUSDT_1h_Cleaned (1).csv` is read-only and protected by name. |
| New data location | `data/oos/` only. |
| Overlap | Any candle inside 2024-01-01 … 2025-12-31 is rejected. |
| Repair | No gap filling, no interpolation, no synthetic candles, ever. |
| Strategy | Baseline and A2 parameters frozen. No tuning on new data. |
| Licence | Binance data is CC BY-NC-SA 4.0; attribution required. |

## Step 1 — Authorise and download (operator)

Source: Binance Vision monthly spot klines (see `DATA_SOURCE_REVIEW.md`).

```
# Example only. DO NOT run without authorisation.
BASE=https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h
curl -sO "$BASE/BTCUSDT-1h-2026-01.zip"
curl -sO "$BASE/BTCUSDT-1h-2026-01.zip.CHECKSUM"
```

Repeat per month. Do **not** merge months before validation — keep each zip
separate so a rejected month is isolated.

## Step 2 — Verify the published checksum (operator)

Do this **before** parsing. A checksum mismatch means the archive was revised
or the transfer was corrupted, and the month must be re-fetched or the
revision noted.

```
sha256sum -c BTCUSDT-1h-2026-01.zip.CHECKSUM
```

Record the checksum value in the provenance sidecar.

## Step 3 — Extract and preserve the raw source

Unzip into a raw holding area, keeping the original extracted CSV untouched
and unmodified. The acquisition tool opens sources read-only and records the
source SHA-256 in every report, so the raw file is the evidence of what was
supplied.

## Step 4 — Validate and normalise

From the project root:

```python
from crypto_paper_lab.acquisition import normalize_source, write_report

report = normalize_source(
    source_path="raw/BTCUSDT-1h-2026-01.csv",
    output_path="data/oos/binance_spot_BTCUSDT_1h_202601.csv",
)
write_report(report, "data/oos/binance_spot_BTCUSDT_1h_202601.report.txt")

if not report.accepted:
    raise SystemExit("dataset rejected - read the report, do not use the data")
```

Accepted output uses the canonical layout `Date,Open,High,Low,Close,Volume`
with `dd-mm-yyyy HH:MM` stamps, so the existing loader reads it unchanged.

**Month boundaries are expected to produce rejections.** A monthly archive
starts at 00:00 on day 1, so a single month is internally contiguous and
should pass. If a month's first candle is not exactly on the hour, or the
month is short, the report will say so.

## Step 5 — Merge validated months (only after each passes individually)

Concatenating accepted monthly files should yield a contiguous series. Merge
into a **separate output**, never into the research dataset:

```
data/oos/binance_spot_BTCUSDT_1h_202601-202609.csv
```

Re-run `normalize_source` over the merged file to confirm zero missing hours,
zero duplicates and zero overlaps. If the merge introduces a gap at a month
boundary, the merged file is rejected — investigate the boundary rather than
filling it.

## Step 6 — Provenance sidecar

For every accepted file, write `<name>.provenance.txt` containing:

```
source        : Binance Vision (data.binance.vision)
url           : <exact URL per month>
interval      : 1h
market        : spot
symbol        : BTCUSDT
month(s)      : 2026-01 .. 2026-09
published sha : <value from .CHECKSUM>
local sha256  : <value reported by normalize_source>
download date : <YYYY-MM-DD>
licence       : CC BY-NC-SA 4.0 + Binance Vision Dataset Terms
processed by  : crypto_paper_lab.acquisition.normalize_source
notes         : <revision notices, gaps, anything unusual>
```

## Step 7 — Confirm unseen-ness

The validation window must begin strictly after 2025-12-31 23:00. The
acquisition tool rejects overlap, and the Phase 8 harness independently
re-checks it.

## Step 8 — Run the Phase 8 harness (unchanged parameters)

```
python experiments/phase8/validation_harness.py data/oos/binance_spot_BTCUSDT_1h_202601-202609.csv
```

The harness evaluates exactly two configurations — the original baseline and
A2 (`min_breakout_distance = 0.002`) — with identical balance, costs, sizing
and execution. It requires ≥48 warm-up bars, excludes warm-up bars from
trading, starts the account flat at the boundary, and reports the
end-of-window forced close.

## Step 9 — Report honestly

Record whatever the result is. A negative out-of-sample result for both
configurations is a legitimate and useful outcome. Do not adjust parameters
in response, and do not re-slice the validation window until a favourable
result appears.

## Sufficiency

| Validation bars | Approx. days | Typical trades (baseline rate ≈1 per 51 h) | Usability |
|---|---|---|---|
| 720 (30 d) | 30 | ~14 | Too few — inconclusive |
| 2,160 (90 d) | 90 | ~42 | Marginal |
| 4,320 (180 d) | 180 | ~85 | Reasonable |
| 8,640 (360 d) | 360 | ~170 | Comparable to one research year |

Rough guidance: **fewer than ~50 trades makes any comparison inconclusive**,
because the baseline profit factor is below 1.0 and single-trade P&L spans
roughly -6.92 to +27.33.

## Rollback

`data/oos/` holds only derived files plus provenance notes. Deleting that
directory returns the project to its Phase 8 state. The research dataset is
never a target of any write in this workflow.
