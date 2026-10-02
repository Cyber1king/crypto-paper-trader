# Phase 10 — Data Quality Report

Combined dataset: `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv`
SHA-256: `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437`

## 1. Month coverage

| Measure | Value |
|---|---|
| Months requested (2026 onward) | 12 |
| Months probed | 12 (HTTP HEAD) |
| Months available (HTTP 200) | **8** |
| Months successfully downloaded | **8** |
| Months with verified checksums | **8** |
| Months rejected | **0** |
| Months unavailable (HTTP 404) | **4** — 2026-09, 2026-10, 2026-11, 2026-12 |

## 2. Combined dataset

| Measure | Value |
|---|---|
| First timestamp | 2026-01-01 00:00 |
| Last timestamp | 2026-08-31 23:00 |
| Total candles | **5,832** |
| Expected candles for 2026-01..2026-08 | 5,832 ✅ |
| Elapsed span | 243 days |
| Missing hours | **0** |
| Duplicate timestamps | **0** |
| Out-of-order rows | **0** |
| Invalid OHLC rows | **0** |
| Non-positive prices | **0** |
| Negative volume | **0** |
| Misaligned (non-hourly) timestamps | **0** |
| Rows overlapping the 2024–2025 research window | **0** |
| Price range | 57,800.19 – 97,924.49 |
| Total volume | 4,535,110.80693 |

## 3. Boundary continuity with the research dataset

| Check | Result |
|---|---|
| Last research candle | 2025-12-31 23:00 |
| First new candle | 2026-01-01 00:00 |
| Delta | exactly 1 hour |
| Contiguous? | **Yes** |
| Unseen check (new starts strictly after research) | **PASSED** |

The two datasets are timestamp-continuous. Note the standing caveat that the
provenance of the 2024–2025 file is undocumented, so *timestamp* continuity
is established while *construction* continuity is not.

## 4. Validation chain

Each stage re-validated independently rather than trusting the previous one:

| Stage | Method | Result |
|---|---|---|
| Per-month | `normalize_source()` in strict mode, 8 files | 8/8 **ACCEPTED** |
| Merged | duplicate + gap + boundary scan | 0 duplicates, 0 gaps, boundary contiguous |
| Merged re-normalised | `normalize_source()` on the merged file | **ACCEPTED**, 5,832 rows |
| Merged loaded | `load_ohlcv_csv()` + `validate_dataset()` | **PASS** |

Reports retained at `data/oos/*.report.txt`.

## 5. Normalisation applied

Representation only. No market value was altered.

| Change | Detail |
|---|---|
| Epoch → `dd-mm-yyyy HH:MM` | Binance open time converted to project canonical format |
| Epoch unit inference | Detected as **microseconds** on real data (raw value `1767225600000000` = 16 digits). Consistent with Binance's documented switch to microseconds for spot on 2025-01-01 |
| Column subset | 12 Binance columns → 6 canonical columns |
| Numeric re-serialisation | Canonical output formatting |

Six trailing columns were ignored. The source files carry **no header row**,
so their names cannot be read from the file; they are positional only:
close time, quote asset volume, number of trades, taker buy base asset
volume, taker buy quote asset volume, ignore. This is recorded in every
provenance sidecar rather than silently dropped.

**No gap was filled. No price was interpolated. No candle was synthesised.**

## 6. Volume validation

Volume is present and non-negative on every row (5,832/5,832). Total
4,535,110.80693 base units. Volume is carried through as a data column; the
current strategy does not consume it.

## 7. SHA-256 verification

All 8 archives verified against published `.CHECKSUM` values **before
parsing**. 8/8 passed, 0 failures. Full detail in `CHECKSUM_REPORT.md`.

## 8. Quality verdict

**PASSED.** The combined dataset is complete, contiguous, internally
consistent, free of duplicates and gaps, correctly aligned to whole hours,
strictly later than the research window, and loadable by the project's own
loader with `validate_dataset()` passing.

## 9. Caveats

1. **Cross-source continuity is unverified.** The 2024–2025 file's origin is
   undocumented. Binance discloses that archived files may be revised, so the
   2026 data may not be constructed identically to the older file even
   though timestamps join seamlessly.
2. **Four months are missing** (2026-09 onward). The validation window is
   January–August 2026, not a full year.
3. **The dataset covers a strong downtrend.** BTC fell from 87,809 to 78,581
   (−10.5%) over the acquired period, with a low of 57,800. This differs
   materially from the research window (+106.1%).
4. Spot-only. No futures or other pairs were fetched, so no cross-venue
   comparison is possible from this data.
5. Binance data is CC BY-NC-SA 4.0, non-commercial only.
