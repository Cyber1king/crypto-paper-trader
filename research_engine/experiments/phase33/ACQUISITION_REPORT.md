# Phase 33 — Fresh Data Acquisition and Validation Readiness

**VERDICT: PARTIAL**

One of two required market groups was acquired in full with publisher checksum
verification. **BTC/USDT could not be acquired because no genuinely new data
exists**, and **forex was acquired only as daily official reference rates, not
the requested hourly OHLC.** Both gaps are documented rather than papered over.

**No backtest, optimisation, signal evaluation or performance calculation was run.
Nothing was merged into any frozen dataset. Nothing was committed or pushed.**

---

## 1. Acquisition status by instrument

| # | Instrument | Market | Requested | Acquired | Status |
|---|---|---|---|---|---|
| 1 | **ETH/USDT** | crypto spot | hourly OHLCV, UTC | hourly OHLCV, UTC, 2024-01-01 → 2026-10-08 | **ACQUIRED** |
| 2 | **BTC/USDT** | crypto spot | hourly OHLCV, UTC | — | **NOT ACQUIRED — no new data exists** |
| 3 | EUR/USD | forex | hourly OHLC | daily reference rate | **PARTIAL — wrong granularity** |
| 4 | GBP/USD | forex | hourly OHLC | daily reference rate | **PARTIAL — wrong granularity** |
| 5 | USD/JPY | forex | hourly OHLC | daily reference rate | **PARTIAL — wrong granularity** |

All three datasets carry the marker **`ACQUIRED - NOT YET APPROVED FOR
VALIDATION`** at the top of their manifests. Acquisition does not authorise
strategy testing.

---

## 2. ETH/USDT — acquired in full

### 2.1 What was obtained

| Property | Value |
|---|---|
| Instrument | ETH/USDT, crypto **spot** (not futures, not perpetual) |
| Provider | Binance Vision (`data.binance.vision`) |
| Granularity | 1 hour, UTC |
| Normalised path | `research_engine/data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| **SHA-256** | **`7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb`** |
| Bytes | 1,426,206 |
| Rows (excl header) | **24,288** |
| Range (UTC) | `2024-01-01 00:00` → `2026-10-08 23:00` |
| Calendar span | **1,012 days** (requirement was ≥ 90) |
| Columns | `Date,Open,High,Low,Close,Volume` |
| Line endings | LF only |
| Price min / max | 1385.05 / 4956.78 |
| Total volume | 455,799,115.28838 |
| Archives | **41** (33 monthly 2024-01…2026-09 + 8 daily 2026-10-01…08) |
| Raw shards retained | yes, `raw_ethusdt_1h/` |

Yearly coverage: 2024 = 8,784 rows, 2025 = 8,760 rows, 2026 = 6,744 rows.

### 2.2 Checksum evidence — the strong part

**All 41 archives were verified against the publisher's own published
`.CHECKSUM` digest, and the verification happened BEFORE any archive was
parsed.** A mismatch would have aborted the download and left the archive
unparsed; the acquisition script was written to refuse to normalise if any
archive was unverified.

- Archives downloaded: **41/41**
- Published digest == local digest: **41/41**
- Parse failures: 0
- Normalisation via the repository's own `normalize_source(strict=True)`, **unmodified**: 41/41 clean, 24,288/24,288 rows accepted, 0 errors

This establishes the archives match what Binance published. It is the same
mechanism Phase 29 used for BTC/USDT.

### 2.3 Strict data-quality results — 20/20 passed

| Check | Result |
|---|---|
| All shards share the canonical header | PASS |
| Total rows | PASS — 24,288 |
| First / last timestamp as expected | PASS |
| Span ≥ 90 consecutive calendar days | PASS — 1,012 |
| Every timestamp on an exact UTC hour | PASS |
| Strictly increasing, zero duplicates | PASS — 0 duplicates |
| No missing hourly intervals | PASS — **0 gaps** |
| Row count equals span × 24 arithmetic | PASS — 24,288 == 1012 × 24 |
| All values finite and parseable | PASS |
| No invalid OHLC relationships | PASS |
| No negative volume | PASS |
| All prices strictly positive | PASS |
| Repository `validate_dataset()` (unmodified) | PASS |
| LF line endings, trailing newline | PASS |
| No pre-existing ETH dataset in the repository | PASS — first non-BTC asset |

Per-archive validation: 0 invalid rows, 0 duplicate timestamps, 0 out-of-order
rows, 0 missing hours, 0 overlaps across all 41 archives.

### 2.4 Overlap and prior use — read this carefully

**No ETH/USDT data existed in this repository before Phase 33.** This is the
first acquisition of any non-BTC instrument by this project.

**However, the ETH date range overlaps the BTC/USDT ranges already held.** That
is deliberate and is **not** contamination:

- the instrument differs — ETH prices were never observed by any prior phase;
- the purpose is cross-asset evidence on a date-matched period;
- no ETH observation influenced any prior research result.

**This dataset is NOT a fresh out-of-sample window for the BTC strategy and must
never be described as one.** Any claim that it independently validates BTC
strategy behaviour would be false.

---

## 3. BTC/USDT — NOT ACQUIRED

**No genuinely new BTC/USDT data exists.** This is a source-coverage fact, not a
failure of effort.

Probes performed against Binance Vision:

| Target | Result |
|---|---|
| monthly `BTCUSDT-1h-2026-10.zip` | **HTTP 404** |
| daily `BTCUSDT-1h-2026-10-09.zip` | **HTTP 404** |
| daily `BTCUSDT-1h-2026-10-10.zip` | **HTTP 404** |
| daily `BTCUSDT-1h-2026-10-11.zip` | **HTTP 404** |
| daily `BTCUSDT-1h-2026-10-08.zip` | HTTP 200 — **already held by Phase 29** |

The newest available data ends at `2026-10-08`, which Phase 29 already acquired,
checksum-verified and consumed as the Phase 30B holdout.

**Decision: no BTC/USDT archive was downloaded.** Re-downloading data already
held would add no information, and presenting a copy of consumed data as a "new
acquisition" would be misleading. The 2026-10 monthly archive is expected to
publish on the first Monday of November 2026.

**Consequence for the roadmap.** Phase 32 roadmap item R1 required fresh data
before any evaluation. R1 is **partially satisfied**: cross-asset evidence now
exists (ETH), but no new *unseen BTC* window does. Unseen BTC data becomes
available only from 2026-10-09 onward once Binance publishes.

---

## 4. Forex — acquired as daily reference rates only

### 4.1 What was obtained

| Property | Value |
|---|---|
| Instruments | EUR/USD, GBP/USD, USD/JPY |
| **Origin of data** | **European Central Bank** euro foreign exchange reference rates |
| Served by | `frankfurter.app` |
| Granularity | **DAILY reference fixing — not hourly** |
| Normalised path | `research_engine/data/phase33/ecb_reference_rates_daily_20240101_20261008.csv` |
| **SHA-256** | **`030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753`** |
| Bytes | 182,738 |
| Rows | 2,127 (709 dates × 3 pairs) |
| Schema | `date,pair,rate,rate_type,source` |
| Range | `2023-12-29` → `2026-10-08` (1,015 calendar days) |

### 4.2 This is NOT an OHLC dataset — stated prominently

There is **no open, no high, no low, no close, no volume and no bid/ask**. A
daily reference rate is a single official fixing published by a central bank
after the fact — it is not a traded bar.

The dataset is stored under a deliberately distinct filename and a deliberately
distinct schema so it **cannot** be loaded or mistaken for an OHLC series by the
project's canonical loader. It cannot be resampled into hourly bars without
inventing data.

### 4.3 Checksum limitation — no publisher authenticity evidence

**The ECB publishes no per-file checksums or signatures, and neither does
frankfurter.app.** The SHA-256 values recorded in the manifest therefore
establish **local integrity only** — they let this project detect later
corruption of its own copy. They **do not** establish independent source
authenticity.

This dataset is explicitly **not** described as independently verified or
checksum-verified against the publisher. That is a material downgrade from the
ETH/USDT dataset, where publisher digests exist and were matched 41/41.

### 4.4 Trading-calendar semantics — 12/12 checks passed

Absent dates are **expected, not data-quality gaps**:

| Property | Result |
|---|---|
| Weekend observations | **0** — ECB publishes on TARGET business days only |
| Weekday absences (ECB/TARGET holidays) | **16** — listed in the manifest, incl. 2024-03-29, 2024-12-25, 2025-04-18, 2026-04-03 |
| All three pairs share an identical calendar | PASS — no pair advantaged by coverage |
| Every observation a distinct date | PASS |
| All rates strictly positive, non-null | PASS |
| No missing rate within any pair | PASS |

**No continuity requirement was applied across closures**, per the mission's
instruction not to require continuous forex bars across market closures.

### 4.5 Sources considered and rejected — with reasons

| Source | What it offered | Why not used |
|---|---|---|
| **Yahoo Finance chart endpoint** | Genuine hourly OHLCV for all three pairs (530 bars each) | **Unofficial, unsupported endpoint.** No published checksums, no clear redistribution or licence terms, and the forex "volume" is of unstated provenance. Rejected on provenance and licensing grounds. |
| **Dukascopy datafeed** | Confirmed reachable; real binary tick data (`.bi5`, LZMA) | **Not acquired.** Converting ticks to hourly OHLC would require this project to author and own an aggregation whose methodology (tick aggregation rules, session handling, DST) becomes part of the dataset's provenance, and whose "volume" would be **tick count, not exchange volume**. Judged out of scope for an acquisition phase. Recorded as an open item rather than silently performed. |
| **Stooq** | Intended free CSV | Returned an HTML interstitial instead of CSV on every attempt. Not usable. |

**No bid/ask data was obtained from any source. No spread, quote or mid-price
has been synthesised, interpolated or inferred anywhere.**

### 4.6 Forex limitations

- Not OHLC — no intraday or session analysis, no volatility-from-high-low.
- No volume of any kind. Tick volume, central volume and volume profile are all
  absent, and none may be inferred.
- No bid/ask and no spread, so FX execution-cost realism is impossible here.
- Single daily fixing, published retrospectively — not an actionable real-time price.
- Precision is not uniform: EUR/USD and GBP/USD to 5 significant decimals, USD/JPY to 3.
- Local checksums only; no publisher authenticity evidence.
- Cannot be compared directly against the ETH/BTC OHLC datasets.

---

## 5. Licensing and attribution

| Dataset | Licence | Commercial use | Attribution |
|---|---|---|---|
| ETH/USDT (Binance Vision) | CC BY-NC-SA 4.0 + Binance Vision Dataset Terms | **Excluded** | Required on redistribution |
| Forex (ECB) | ECB free reuse for non-commercial purposes, with attribution | Excluded | **Required: "Source: European Central Bank, euro foreign exchange reference rates, retrieved via frankfurter.app, 2026-10-09"** |

This project is non-commercial research. Commercial redistribution is outside
both licence terms and has not been assessed beyond that statement.

**No credentials, API keys, passwords or private tokens were used, stored or
reported anywhere.** All sources were public and unauthenticated.

---

## 6. Datasets requiring additional verification before evaluation

| # | Dataset | Outstanding requirement |
|---|---|---|
| 1 | **ETH/USDT 1h** | Preregistration naming sha256 `7507c100…`; explicit confirmation that a BTC→ETH instrument change is within scope (`StrategyConfig.asset` is `"BTC/USDT"` and Phase 32 recorded cross-asset behaviour as **NOT ESTABLISHED**); acknowledgement that overlapping dates do **not** create an independent BTC sample |
| 2 | **ETH/USDT 1h** | Fresh unseen BTC data still absent. Untouched BTC periods begin 2026-10-09 once published. |
| 3 | **Forex daily rates** | Decide explicitly that a daily fixing is the intended input, accepting it cannot substitute for OHLC |
| 4 | **Forex daily rates** | If any alignment to hourly bars is ever attempted, an FX session calendar and DST rules must be established first |
| 5 | **Forex hourly OHLC** | **Still required and not obtained.** Needs a source with published checksums and a clear licence. Dukascopy tick aggregation remains an open option with the methodology caveats in §4.5. |
| 6 | **All datasets** | A preregistration before any evaluation, modelled on `phase29/PREREGISTRATION.md` |

---

## 7. Separation of acquisition from evaluation

| Requirement | Status |
|---|---|
| New directory `research_engine/data/phase33/` | Created; nothing else written there |
| New report `research_engine/experiments/phase33/ACQUISITION_REPORT.md` | This file |
| No merge into the frozen primary dataset | Held — no existing dataset touched |
| No merge into historical datasets | Held |
| Distinct filenames and checksums for raw vs normalised | Held — `.zip` / `.zip.CHECKSUM` / raw `.csv` / `.normalized.csv` / merged file, each hashed separately |
| Every dataset marked `ACQUIRED - NOT YET APPROVED FOR VALIDATION` | Held — marker is line 1 of both manifests |
| No backtest, optimisation, signal or performance calculation | Held — none run |
| Existing validators used unmodified | Held — `normalize_source`, `validate_dataset`, `load_dataset` all used as-is |

Repository validators used, none modified:

- `crypto_paper_lab.acquisition.normalize_source(strict=True)` — 41/41 clean
- `crypto_paper_lab.dataset.validate_dataset` — passed on the merged ETH file
- `crypto_paper_lab.dataset.load_dataset` — 24,288 candles loaded

---

## 8. Deliverables created

```
research_engine/data/phase33/
  binance_spot_ETHUSDT_1h_202401-202610.csv        1,426,206 B   24,288 rows
  ecb_reference_rates_daily_20240101_20261008.csv    182,738 B    2,127 rows
  MANIFEST_ETHUSDT_1h_202401_202610.txt                12,552 B
  MANIFEST_FOREX_ECB_daily_reference_rates.txt          8,858 B
  provenance/                                        41 sidecars
  raw_ethusdt_1h/                            41 zips + 41 CHECKSUMs + 82 csvs
  raw_forex_ecb_daily/                                3 raw JSON
  _acquisition_log.json                               53,302 B
  _eth_merge_meta.json                                 5,731 B
  _forex_meta.json                                     3,605 B

research_engine/experiments/phase33/
  ACQUISITION_REPORT.md                            (this file)
```

No existing file was modified, renamed, moved or deleted.

---

## 9. Summary of why this is PARTIAL and not PASS

| Requested | Outcome |
|---|---|
| ETH/USDT hourly OHLCV | **Met in full**, with 41/41 publisher checksum verification and 20/20 quality checks |
| BTC/USDT hourly OHLCV | **Not met** — no genuinely new BTC data is published; newest available is already held |
| EUR/USD, GBP/USD, USD/JPY hourly OHLC with volume/bid-ask | **Not met** — daily official reference rates only; no OHLC, no volume, no bid/ask |
| ≥ 90 consecutive calendar days | **Met** — 1,012 days crypto, 1,015 days forex |
| Provenance and checksums | **Met for crypto** (publisher digests matched); **partially met for forex** (local checksums only, no publisher authenticity evidence) |
| Quality validation | **Met** — 20/20 crypto, 12/12 forex |
| Overlap and prior-use checks | **Met** and documented honestly, including the BTC date overlap |
| No evaluation performed | **Met** |

Two of five requested instruments were not obtained as specified, for reasons
that are documented rather than worked around. No synthetic, interpolated or
substituted data was created.

`PHASE 33 DATA ACQUISITION: PARTIAL`