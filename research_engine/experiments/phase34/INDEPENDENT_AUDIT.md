# Phase 34 — Independent Phase 33 Data Audit

**Audit type: strictly read-only.** Nothing was downloaded, no dataset modified,
no existing file edited, no backtest run, no profitability evaluated, no
parameter changed, no AI provider integrated, nothing committed or pushed.

**Every Phase 33 "PASS" was recomputed from source.** Recorded PASS statements
were treated as claims to be tested, not as evidence.

**VERDICT: PARTIAL** — one genuine provenance-documentation defect found (§1.7).
The datasets themselves reconcile completely.

---

## 0. Summary

| Section | Checks | PASS | FAIL | UNVERIFIED |
|---|---|---|---|---|
| 1. ETH dataset | 21 | 20 | **1** | 0 |
| 2. Forex dataset | 12 | 11 | 0 | **1** |
| 3. Frozen research | 11 | 11 | 0 | 0 |
| 4. Research integrity | 11 | 11 | 0 | 0 |

**One FAIL:** the Phase 33 provenance sidecars record the wrong epoch unit for
the 12 archives from 2024 (§1.7). **The data is unaffected** — all 24,288 rows
reconcile numerically against the raw archives. This is a documentation defect,
not a data defect.

**One UNVERIFIED:** the forex filename says `20240101` but the first observation
is `2023-12-29` (§2.12). Content is correctly labelled in the manifest.

---

## 1. ETH/USDT dataset audit

Target: `research_engine/data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv`

### 1.1 Identity — PASS

| Property | Recomputed | Manifest | Verdict |
|---|---|---|---|
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` | same | **PASS** |
| Bytes | 1,426,206 | 1,426,206 | **PASS** |
| Header | `Date,Open,High,Low,Close,Volume` | same | **PASS** |
| Data rows | 24,288 | 24,288 | **PASS** |
| First timestamp | 2024-01-01 00:00 | same | **PASS** |
| Last timestamp | 2026-10-08 23:00 | same | **PASS** |
| Calendar span | 1,012 days | 1,012 days | **PASS** |

Byte-level: **0 CR bytes present** (LF-only confirmed), file ends with a newline.

### 1.2 The 1,012-day / 24,288-row claim — PASS

This was recomputed rather than accepted:

```
span_days  = (2026-10-08) - (2024-01-01) + 1 = 1012
expected   = 1012 x 24                     = 24,288
actual rows                            = 24,288   -> arithmetically consistent
elapsed hours between first and last   = 24,287   = 24,288 rows - 1
```

**All three independent counts agree.** The claim is mathematically sound.

### 1.3 Timestamps, ordering, duplicates, gaps — PASS

| Check | Recomputed |
|---|---|
| Duplicate timestamps | **0** |
| Non-increasing pairs | **0** |
| Intervals ≠ 1 hour | **0** |
| Timestamps not on an exact hour | **0** |

### 1.4 Value integrity — PASS

| Check | Recomputed |
|---|---|
| Rows with ≠ 6 columns | 0 |
| Non-finite / unparseable | 0 |
| Invalid OHLC relationships | 0 |
| Non-positive prices | 0 |
| Negative volume | 0 |
| Zero-volume bars | 0 |

Independently recomputed extremes: `min(low) = 1385.05`, `max(high) = 4956.78`,
`min(volume) = 821.477`, `max(volume) = 508838.4049`. These match the Phase 33
report exactly.

Yearly coverage: 2024 = 8,784 rows, 2025 = 8,760 rows, 2026 = 6,744 rows.

### 1.5 Publisher checksum re-verification — PASS

All **41 archives** were re-hashed from disk and compared against the publisher's
`.CHECKSUM` files, independently of the acquisition log:

| Check | Result |
|---|---|
| Archives present | 41 |
| Local digest == published `.CHECKSUM` | **41/41** |
| `.CHECKSUM` file == value recorded in acquisition log | **41/41** |
| Archive bytes altered since acquisition | **0** |

### 1.6 Full chain reconciliation — PASS

Every row was **independently re-derived from the raw ZIP archives** — decoding
epochs, formatting timestamps and selecting OHLCV columns — without using the
repository's acquisition library for the derivation, then compared numerically
against the merged CSV.

| Check | Result |
|---|---|
| Rows independently re-derived from ZIPs | **24,288** |
| Merged CSV rows | **24,288** |
| **Numeric mismatches** | **0** |
| Distinct timestamps across archives == merged set | **true** |
| Merged rows not traceable to any archive | **0** |
| Archive rows missing from merged | **0** |
| Provenance sidecars present | **41/41** |
| Sidecar digest mismatches | **0** |

**Verdict: the merged dataset is exactly the union of the 41 verified archives,
value for value. No row is invented, altered or lost.**

### 1.7 FAIL — provenance sidecars record the wrong epoch unit for 2024

This is the audit's principal finding.

**What the data actually is.** Independent inspection of the raw epoch values:

| Archives | First raw epoch | Digits | Unit |
|---|---|---|---|
| **12 archives, `ETHUSDT-1h-2024-01` … `2024-12`** | `1704067200000` | 13 | **MILLISECONDS** |
| 29 archives, `ETHUSDT-1h-2025-01` … `2026-10-08` | `1735689600000000` | 16 | **MICROSECONDS** |

Row counts: **8,784 rows are millisecond-encoded, 15,504 are microsecond-encoded.**
Binance Vision changed the spot klines timestamp unit at 2025-01-01.

**What the Phase 33 documentation says.** All 41 provenance sidecars — including
the 12 for 2024 — carry the identical normalisation note:

> `* Epoch unit inferred per row as microseconds: Binance Vision publishes`
> `  SPOT timestamps in microseconds from 2025-01-01 onward.`

Searching every Phase 33 artefact for "millisecond" returns **zero matches** in
the manifest, the sidecars and the acquisition report.

**Why this is a real defect.** The note asserts the unit is microseconds for the
2024 archives, which is false. The trailing clause "from 2025-01-01 onward"
implies a change without ever stating what the earlier unit is. An independent
auditor who followed the documented method would decode the 2024 rows as
microseconds and produce timestamps around **1970** — which is exactly what this
audit produced on its first attempt.

**Impact on the data: none.** The repository's `normalize_source` infers the unit
per row, so the dataset is correct — §1.6 proves 0 numeric mismatches. The defect
is confined to the human-readable provenance text.

**Limitation.** I verified the unit empirically from epoch magnitude, not from an
official Binance specification retrieved during this audit; I did not fetch
documentation, per the read-only constraint. The empirical evidence is
unambiguous (13-digit vs 16-digit epochs, clean split at 2025-01-01, and a
per-row unit inference that yields a perfectly contiguous 1-hour series).

**Not repaired.** Per instruction, this phase documents and does not fix.

### 1.8 Recorded reconciliation — PASS

The `_eth_merge_meta.json` audit trail and the manifest agree with recomputation
on sha256, byte size, row count, first/last timestamp, calendar span and all 20
recorded quality checks. Price range is **not** a manifest field (it appears only
in the Phase 33 report); verified correct as `1385.05 / 4956.78`.

---

## 2. Forex reference-rate dataset audit

Target: `research_engine/data/phase33/ecb_reference_rates_daily_20240101_20261008.csv`
SHA-256 `030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753`, 182,738 B, 2,127 rows.

### 2.1 Pair coverage and date uniqueness — PASS

| Check | Result |
|---|---|
| Pairs present | EURUSD, GBPUSD, USDJPY — **709 each** |
| Distinct dates | **709** |
| Pairs containing duplicate dates | **0** |
| Row count = dates × 3 | **2,127 = 709 × 3** |
| All three pairs share an identical calendar | **true** |

No pair is advantaged or disadvantaged by differing coverage.

### 2.2 Rate validity — PASS

0 unparseable rates, 0 non-positive rates, 0 NaN. Every row self-labels:
`rate_type = ECB_reference_rate`, `source = European_Central_Bank_via_frankfurter.app`.

### 2.3 Weekday / weekend handling — PASS

| Check | Result |
|---|---|
| Weekend observations | **0** |
| Weekday distribution | Mon 141, Tue 145, Wed 142, Thu 141, Fri 140 |
| Calendar span | 1,015 days |
| Absent days | 306 (weekends + ECB/TARGET holidays) |

Absence is consistent with the ECB TARGET business-day schedule, not a data
quality gap. All 306 absences are accounted for as weekends or holidays.

### 2.4 Schema cannot be mistaken for hourly OHLCV — PASS

Header is `date,pair,rate,rate_type,source`.

- **No column named open, high, low, close or volume.**
- Every row has exactly 5 fields.
- Every row carries `rate_type = ECB_reference_rate`, so the nature of the data
  travels with each observation rather than only in external documentation.
- The filename and directory differ from the OHLC convention used by every
  canonical dataset in the repository.

**Additionally**, `validate_dataset` / `load_ohlcv_csv` in the repository expect
six canonical OHLCV columns; this five-column, differently-named file cannot be
loaded as OHLC without deliberate conversion.

### 2.5 Local-checksum limitation preserved — PASS

The manifest carries the limitation in bold-caps and in its own section:

> `*** CHECKSUM LIMITATION - READ ***`
> `The ECB publishes NO per-file checksums or signatures for these series, and`
> `frankfurter.app publishes none either. The SHA-256 values recorded below`
> `establish LOCAL INTEGRITY ONLY … They do NOT establish independent source`
> `authenticity.`

The dataset is nowhere described as independently verified or publisher-checksum
verified. This downgrade from the ETH dataset is stated explicitly and correctly.

### 2.6 UNVERIFIED — filename start date precedes first observation

The filename encodes `20240101`, but the first observation is **`2023-12-29`**.

Cause: the API was queried for `2024-01-01..2026-10-08` and returned the preceding
business day as the base observation, which is correct API behaviour rather than
an error. The manifest records the true range (`2023-12-29` → `2026-10-08`).

**Impact: cosmetic.** The content is correctly labelled everywhere it matters, and
no reader would be misled about the coverage window. Recorded as UNVERIFIED rather
than FAIL because it is a naming inconsistency, not a data defect. Not repaired.

---

## 3. Frozen research protection — PASS (11/11)

Every recorded digest re-verified against the file on disk:

| Artefact | Result |
|---|---|
| `BTCUSDT_1h_Cleaned (1).csv` | **OK** `201a3b15…` |
| BTC holdout `…202609-202610.csv` | **OK** `c475e541…` |
| Phase 29 `PREREGISTRATION.md` | **OK** `b06f36e2…` |
| Phase 30 `RESULTS_holdout.json` | **OK** `4d69a2e2…` |
| Phase 30 `RESULTS_holdout.txt` | **OK** `fd3f7741…` |
| Phase 30 `RESULTS_trades.csv` | **OK** `174d5587…` |
| Phase 30 `SUMMARY.md` | **OK** `9e3171b0…` |

| Check | Result |
|---|---|
| Modified tracked files | **0** |
| Deleted tracked files | **0** |
| Staged files | **0** |
| HEAD | `dccebbd53ee8365474345506db9099b13356b53c` — unchanged |
| Commits ahead of `origin/main` | **0** — no commit, no push |
| Untracked | 259 (carried forward unchanged from Phase 33) |

**The spent BTC holdout, the primary research dataset, the frozen pre-registration
and all four Phase 30 result artefacts are byte-identical to their recorded values.**

---

## 4. Research integrity — PASS (11/11)

| Check | Verdict | Evidence |
|---|---|---|
| ETH is a genuinely new instrument | **PASS** | Zero ETH files exist anywhere in `data/` outside `phase33/` |
| ETH is **not** presented as fresh BTC out-of-sample | **PASS** | Manifest §4: "This dataset is NOT a fresh out-of-sample window for the BTC strategy and must never be described as one." |
| ETH/BTC date overlap is disclosed, not concealed | **PASS** | Manifest §4 states the overlap and explains why it is not contamination |
| Cross-asset behaviour flagged as NOT ESTABLISHED | **PASS** | Manifest §7 requires explicit confirmation that a BTC→ETH change is in scope; cites Phase 32 |
| ECB rates described as fixings, not executable prices | **PASS** | Manifest: "a daily reference rate is a single official fixing published by a central bank after the fact — it is not a traded bar" |
| No synthetic spreads or quotes introduced | **PASS** | All 2,127 rows have exactly 5 fields; the string "bid" appears nowhere in the dataset |
| No forex volume introduced | **PASS** | No volume column exists in the schema |
| ETH volume is genuine source volume | **PASS** | Re-derived numerically from all 41 archives, 0 mismatches |
| Both datasets marked NOT YET APPROVED | **PASS** | `ACQUIRED - NOT YET APPROVED FOR VALIDATION` is line 1 of both manifests |
| No backtest or evaluation performed | **PASS** | Report §7; no strategy call exists in the acquisition path |
| Fresh-data requirement recorded | **PASS** | Manifest §7 item 3: "the only untouched periods are 2026-10-09 onward, once published" |

**The spent BTC holdout has not been reused.** Its digest is unchanged and the
ETH manifest explicitly requires new unseen data before any evaluation.

---

## 5. Findings

### Defects requiring correction

**F1 — Phase 33 provenance sidecars record an incorrect epoch unit for 2024.**
All 41 sidecars state the unit is microseconds; the 12 archives covering
2024-01…2024-12 are in **milliseconds**. No Phase 33 document mentions
milliseconds. A reader following the documented method cannot re-derive the 2024
rows. **Data unaffected** — proven by 0 numeric mismatches across 24,288 rows.
Recommended correction, not applied here: state both units and the 2025-01-01
transition explicitly in the manifest and sidecars.

### Cosmetic observation

**F2 — forex filename encodes `20240101` but data starts `2023-12-29`.**
Manifest states the true range. No impact on interpretation.

### Confirmed strengths

- The ETH dataset reconciles **completely**: 41/41 publisher checksums, 24,288/24,288
  rows re-derived independently, 0 numeric mismatches, 0 gaps, 0 duplicates.
- The 1,012-day / 24,288-row claim is arithmetically consistent on three
  independent counts.
- Forex semantic limitations are documented in the data itself, not only in prose.
- The no-publisher-authenticity limitation is stated prominently and correctly.
- Every frozen research artefact is byte-identical.
- Research-integrity framing is accurate throughout.

---

## 6. Audit limitations

| # | Limitation |
|---|---|
| L1 | The epoch-unit finding is **empirical**, from epoch magnitude and per-row inference. Official Binance documentation was not retrieved, per the read-only constraint. The evidence is unambiguous but is inference, not citation. |
| L2 | I did **not** re-run `normalize_source`. The audit re-derived rows with independent code and compared numerically, which is a stronger check than re-running the same library. |
| L3 | The ECB source could not be independently authenticated — no publisher checksums exist. Only local integrity is verifiable, as the manifest itself states. |
| L4 | Whether Binance Vision's underlying prices are *correct* is outside scope. The audit proves the files match what Binance published, not that the published prices are accurate. |
| L5 | The 16 ECB/TARGET holiday dates were taken from the Phase 33 manifest; I verified the count and the absence pattern but did not independently confirm each against the ECB holiday calendar. |
| L6 | No backtest, performance measure or profitability statement was made or implied. |

---

## 7. Restrictions honoured

- No data downloaded.
- No dataset modified, renamed, moved or deleted.
- No existing file edited.
- No backtest, strategy call or performance calculation.
- No profitability evaluated.
- No strategy parameter or code changed.
- No AI provider integrated or contacted.
- Nothing committed, staged or pushed.
- Only one new file created:
  `research_engine/experiments/phase34/INDEPENDENT_AUDIT.md`

---

**Audit outcome.** The acquired data is sound: the ETH dataset reconciles value
for value against 41 publisher-checksummed archives with zero defects, and the
forex dataset is honestly labelled and cannot be mistaken for OHLCV. One genuine
provenance-documentation defect was found (§1.7, F1) and one cosmetic naming
observation (§2.6, F2). Neither affects data integrity. No evaluation was
performed and none is warranted until F1 is corrected and the pre-evaluation
requirements in both manifests are satisfied.

`PHASE 34 INDEPENDENT DATA AUDIT: PARTIAL`