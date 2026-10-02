# Phase 10 — Summary

## Headline

Real, checksum-verified, genuinely unseen BTC/USDT 1h data was acquired for
**2026-01 through 2026-08** and passed every quality check. Out-of-sample
validation then ran validly on the unchanged Phase 8 harness for the two
frozen configurations. Both came out **marginally positive** — and neither
result is **statistically distinguishable from zero**.

**No configuration is demonstrated to be profitable.**

## 1. Archives downloaded

8 monthly archives from Binance Vision (BTC/USDT **spot**, klines, 1h),
342,903 bytes total, 5,832 rows. All preserved under `data/oos/raw/`.

Availability was probed with HTTP HEAD before downloading, not inferred from
the URL pattern: 2026-01…2026-08 returned **200**, 2026-09…2026-12 returned
**404**.

Each month's row count exactly equals its number of hours (744/672/744/720/
744/720/744/744 = 5,832), independently confirming completeness.

## 2. Checksums verified

**8 of 8 archives verified** against the published `.CHECKSUM` SHA-256,
**before any parsing**. Zero failures, zero rejections. Verification is
re-run on every execution of `extract_and_normalise.py`.

## 3. Months unavailable or rejected

**Unavailable: 4** — 2026-09, 2026-10, 2026-11, 2026-12 (HTTP 404). Binance
publishes a monthly archive on the first Monday of the following month; on
2026-10-01 that Monday (2026-10-05) had not yet arrived, so September's
archive was unpublished. No partial month was accepted and no data was
substituted.

**Rejected: 0.**

## 4. Final dataset

| Property | Value |
|---|---|
| File | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| Date range | **2026-01-01 00:00 → 2026-08-31 23:00** |
| Candle count | **5,832** |
| SHA-256 | `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437` |

## 5. Gaps, duplicates, boundary issues

**None.** 0 missing hours, 0 duplicate timestamps, 0 out-of-order rows, 0
invalid OHLC rows, 0 negative volumes, 0 non-hourly timestamps, 0 overlaps
with the research window.

Boundary: research ends 2025-12-31 23:00, new data begins 2026-01-01 00:00 —
**exactly one hour apart, contiguous**.

## 6. Did the dataset pass validation?

**Yes.** Four independent stages each passed:

1. Per-month `normalize_source(strict=True)` — 8/8 **ACCEPTED**
2. Merge scan — 0 duplicates, 0 gaps, boundary contiguous
3. Merged re-normalised through `normalize_source()` — **ACCEPTED**
4. Loaded via `load_ohlcv_csv()` + `validate_dataset()` — **PASS**

## 7. Was out-of-sample testing completed?

**Yes, validly.** The Phase 8 harness was used unmodified. Validation window
**2026-01-03 00:00 → 2026-08-31 23:00** (5,784 bars; 48 warm-up bars
excluded from trading). Account started flat at the boundary with the full
$10,000 in both cases. Fee 0.001, slippage 0.0005, `risk_fraction` 0.01,
next-candle-open execution — identical for both configurations. Neither was
tuned.

## 8. Baseline and A2 results

| Measure | A — baseline | B — A2 |
|---|---|---|
| Trades | 105 | 90 |
| Net P&L | **+$5.05** (+0.05%) | **+$14.07** (+0.14%) |
| Win rate | 34.29% | 36.67% |
| Profit factor | 1.0424 | 1.1330 |
| Max drawdown | 0.34% | 0.31% |
| Ending balance | $10,005.05 | $10,014.07 |
| Total costs | $31.52 | $27.04 |
| Gross P&L | +$36.57 | +$41.11 |
| Longs | 53, −$1.01 | 45, +$3.11 |
| Shorts | 52, +$6.05 | 45, +$10.95 |

**But the statistics do not support either result:**

| Configuration | Per-trade mean (net) | Std error | mean / SE | 95% CI |
|---|---|---|---|---|
| baseline | +0.0481 | 0.3657 | **0.13** | [−0.6688, +0.7649] |
| A2 | +0.1563 | 0.4181 | **0.37** | [−0.6632, +0.9758] |

Every confidence interval spans zero, before *and* after costs. Costs consume
86.2% of baseline gross and 65.8% of A2 gross. Monthly results split four
positive / four negative.

This is **inconclusive**, not a demonstrated improvement.

## 9. Tests

`python -m pytest tests/ -q` → **138 passed, 0 failed** (was 106).

Added `tests/test_oos_dataset.py` (32 tests, all offline, all skip cleanly
when artifacts are absent): per-month checksum re-verification, provenance
sidecar presence, unavailable-month record, merged candle count / date range /
no gaps / no duplicates / OHLC validity / strict ordering after the research
window / boundary contiguity, monthly coverage summing to 5,832, pinned
research-dataset SHA-256, pinned baseline (344 trades, $9,842.86) and A2
(284 trades, $9,912.84) results, and an assertion that the two
configurations differ in exactly one field.

One test failure was **my own tolerance bug** — I compared against the
published 2-decimal figures at 1e-6 tolerance. Fixed to compare at the
published precision. No data or code was wrong.

No existing test was weakened or deleted.

## 10. Files created or modified

**Data (new):**
- `data/oos/raw/*.zip` (8), `*.zip.CHECKSUM` (8), `*.provenance.txt` (8),
  `UNAVAILABLE_MONTHS.txt`, `extracted/*.csv` (8)
- `data/oos/binance_spot_BTCUSDT_1h_2026{01..08}.csv` + `.report.txt` (16 files)
- `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` + `.report.txt`

**Code / tests (new):**
- `experiments/phase10/{extract_and_normalise,merge_and_check,write_provenance,oos_interpretation}.py`
- `experiments/phase10/RESULTS_*.txt` (4)
- `tests/test_oos_dataset.py`

**Docs (new):** `DOWNLOAD_REPORT.md`, `CHECKSUM_REPORT.md`,
`DATA_QUALITY_REPORT.md`, `PROVENANCE.md`, `OOS_RESULTS.md`, `SUMMARY.md`

**Modified:** `data/oos/README.md` — status updated from EMPTY to POPULATED
with figures; rules and usage preserved.

**Unmodified:** all strategy source files, the original dataset
(`201A3B15…BA016B` before and after), and every earlier phase report.

**No commit or push.**

## 11. Limitations

1. **The 2024–2025 dataset has no documented provenance.** Unchanged gap
   from Phase 9. Binance discloses archived files may be revised. Timestamp
   continuity across the boundary is established; *construction* continuity
   is not. Cross-boundary comparisons should be treated cautiously.
2. **Four months missing.** The window is Jan–Aug 2026, not a full year.
3. **Single window, single asset.** One out-of-sample observation cannot
   establish future performance.
4. **The sign is regime-dependent.** Both configurations were clearly
   negative on 2024–2025 (+106% uptrend) and marginally positive in 2026
   (−10.5% downtrend) **without any strategy change**. This is the third
   consecutive observation of regime sensitivity (2024 vs 2025 in Phase 8).
5. **Statistical power is low.** Per-trade σ ≈ 3.75–3.97 against means of
   0.05–0.16. Roughly 90–105 trades cannot resolve an effect this small.
6. **Spot only.** No futures or cross-venue comparison is possible.
7. **Licence.** Binance data is CC BY-NC-SA 4.0, non-commercial only.
8. **Not tested on this data:** stop-loss, take-profit, max-holding,
   confirmation, trend-strength or directional variants. Phase 6/7 explored
   them on 2024–2025 only.

## 12. Bottom line

The data pipeline worked exactly as designed: verify, preserve, normalise,
validate, and refuse to proceed otherwise. The acquisition is genuine.

The research conclusion is unchanged by it. Both configurations made a small
profit over eight months of unseen data, and **that profit is not
statistically distinguishable from zero**. The honest summary is that this
project has now tested 12+ configurations across 23,376 hourly candles and
still has **no evidence of a profitable trading rule**.

Nothing here authorises selecting, deploying, or trusting either
configuration.

Stopping here for approval. Not starting Phase 11.
