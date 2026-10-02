# Phase 9 — Summary

## Headline

**No new historical data was acquired. No download was performed.** The
project is now *ready* to receive and validate an out-of-sample dataset the
moment one is supplied, but out-of-sample validation has **not** begun and
no claim about future performance is made or implied.

## 1. What was inspected

All 15 source modules, 11 test files, both existing data files, and all
Phase 5–8 reports and experiment scripts. Full test suite run. Baseline and
Phase 7 A2 configurations re-verified: **all figures match exactly**.

| Check | Result |
|---|---|
| `pytest tests/ -q` | **106 passed**, 0 failed |
| Baseline (344 trades, -157.14, 31.686%, 0.6920, 1.74%, 9842.86) | **exact match** |
| A2 (284 trades, -87.16, 33.451%, 0.7957, 1.08%, 9912.84) | **exact match** |
| Original dataset SHA-256 | `201A3B15…BA016B`, unchanged |

## 2. Data sources reviewed

| Source | Verified | Verdict |
|---|---|---|
| **Binance Vision** (`data.binance.vision`) | BTC/USDT spot 1h bulk monthly+daily zips; URL pattern; epoch µs from 2025-01-01 / ms before; 12 kline columns; no account; `.CHECKSUM` SHA-256 per file; CC BY-NC-SA 4.0 with non-commercial research explicitly permitted; archive revisions disclosed | **Recommended** |
| **Coinbase Exchange** | 1h granularity; no key; **BTC-USD not BTC/USDT**; 300 candles/request; `[time,low,high,open,close,volume]` in epoch seconds; **no bulk archive**; docs warn data may be incomplete | Usable, inferior |
| **Kraken** | `/0/public/OHLC`, `interval=60`, no key; **XBTUSD not BTC/USDT**; 720 candles/request; no checksums documented; docs state limited lookback depth | Poor fit |

All claims come from vendor documentation read 2026-10-01. **I downloaded
nothing**, so I have not verified that any specific 2026 archive exists, nor
its real contents or checksum. The repository documents **no** data source —
only an empty `MARKET_DATA_API_KEY` placeholder.

## 3. Was any new data acquired?

**No.** No file was downloaded, no account was used, no market data was
fetched. `data/oos/` contains only a README.

## 4. Tools created

**`src/crypto_paper_lab/acquisition.py`** — strict acquisition/validation library:

- Reads three source layouts: Binance klines (headerless **and** headered),
  the project native layout, and ISO-8601.
- **Auto-detects epoch units** (s/ms/µs/ns) — necessary because Binance spot
  switched to microseconds on 2025-01-01.
- Detects required columns, numeric fields, hour alignment, chronological
  ordering, duplicate timestamps, missing hourly intervals, invalid OHLC
  relationships, non-positive prices, negative volume, and overlap with the
  2024–2025 research window.
- **Rejects rather than repairs.** In the default `strict=True` mode a single
  problem means no output file is written at all.
- Never fills gaps, interpolates prices, or synthesises candles.
- Records source SHA-256, output SHA-256, dropped extra columns, and notes.
- Normalises to the project's existing CSV layout so the current loader reads
  it unchanged.
- Refuses to write the protected research dataset.

**`data/oos/README.md`** — destination conventions, filename pattern,
provenance sidecar requirement, and usage.

**`experiments/phase9/acquisition_dry_run.py`** — end-to-end demonstration
with synthetic fixtures only.

## 5. How the original dataset was protected

1. **Named guard** — `normalize_source()` raises `AcquisitionError` when the
   output filename is `BTCUSDT_1h_Cleaned (1).csv`.
2. **No implicit writes** — only the caller-supplied `output_path` is written.
3. **Read-only source** — sources opened `"r"`; tests assert source SHA-256
   unchanged after normalisation and that the real dataset's SHA-256 is
   unchanged across a full run.
4. **Separate destination** — new data goes to `data/oos/`.

Empirically confirmed: SHA-256 identical before and after the dry run.

## 6. Tests added

`tests/test_acquisition.py` — **27 tests**, all fixtures synthetic in
`tmp_path`, covering every case the task listed: valid data, missing candles,
duplicates, invalid OHLC, malformed input, wrong column names, research-window
overlap, original-dataset preservation, correct normalised output, and
rejection of invalid data (each asserting no file is written).

Suite total: **79 → 106 passing, 0 failures.** No existing test weakened or
deleted.

## 7. Bugs found and fixed

Four, two of them substantive:

| Bug | Severity |
|---|---|
| First data row of a **headerless** Binance file was consumed while probing for a header | **High** — would silently drop one candle from every recommended source format, shifting all timestamps and manufacturing a false "missing hour" |
| `detect_format` rejected headered Binance files | Medium — legitimate layout unusable |
| `accepted` conflated "written" with "usable" | Medium — `strict=False` wrote a file yet reported `accepted=False` |
| `summary_lines()` omitted errors | Low — console could show `REJECTED` with no visible reason |

All fixed and covered by tests. The first was caught by a test asserting
`candle_count == 50` on a 50-row file.

## 8. Limitations and unresolved issues

1. **The existing dataset has no documented provenance.** Whether "Cleaned"
   means gaps were filled or outliers trimmed is unknown, and it is unknown
   which venue produced the candles. A new dataset from a different venue may
   not be continuous at the boundary. Unresolvable from inside the repo.
2. **Binance discloses that archived files may be revised** after
   publication, with a changelog of corrections. A 2026 archive therefore
   cannot be assumed consistent with a 2024–2025 file of unknown origin.
3. **Source verification is documentation-only.** No archive existence,
   content, or checksum was confirmed, because downloading requires
   authorisation.
4. **Vendor `.CHECKSUM` files are not fetched or verified by this project** —
   it downloads nothing. The operator verifies them and records the values in
   a provenance sidecar.
5. Several plausible sources (CryptoCompare, CoinGecko, Kaiko, Tardis) were
   **not** assessed.
6. Terms, endpoints, and layouts change; re-verify at acquisition time.
7. Binance data is **non-commercial only** — fine for this project, but it
   would block any commercial use.
8. No data means **no validation has occurred**. Nothing in this phase
   says anything about whether the baseline or A2 works.

## 9. Is the project ready to accept a new dataset?

**Yes.** Verified end to end: format detection, epoch-unit inference,
validation, rejection, normalisation, checksum recording, protected-dataset
guard, and report generation all work and are covered by 27 tests plus a
9-case dry run.

## 10. What is required before genuine out-of-sample validation can begin

1. **Explicit authorisation to download.** Nothing has been fetched.
2. **Download** Binance Vision monthly spot `BTCUSDT/1h` archives for
   2026-01 onward.
3. **Verify each `.CHECKSUM`** before parsing.
4. **Preserve raw extracted CSVs** plus a provenance sidecar per file.
5. **Run `normalize_source()`** per month; only proceed where
   `report.accepted` is true.
6. **Merge accepted months** into one file in `data/oos/` and re-validate for
   gaps at month boundaries.
7. **Confirm unseen-ness** — the first eligible bar must be strictly after
   2025-12-31 23:00.
8. **Run the Phase 8 harness unchanged** on baseline and A2.
9. **Report the result as it comes**, including a negative one, with no
   parameter adjustment afterwards.

**Sufficiency:** roughly **50+ validation trades** are needed before any
comparison is meaningful (≈85 trades ≈ 6 months; ≈170 trades ≈ 12 months).
Fewer than that is inconclusive.

## 11. Conclusion

The tooling is ready and trustworthy, and the original dataset is verified
clean and provably protected. **The missing ingredient is data, not code.**
No new market data was obtained, no out-of-sample validation has occurred,
and no statement is made or implied about whether the baseline strategy or
the Phase 7 A2 filter would work on unseen candles. A2 remains an in-sample
observation on 2024–2025 data and nothing more.

Nothing was downloaded, no dataset was modified, no strategy parameter was
changed, and nothing was committed or pushed.
