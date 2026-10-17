# Phase 62 — B4: ECB Provenance Decision

**Status: `OWNER DECISION REQUIRED` — provenance remains unresolved.**
**Recommendation given; not selected.**

---

## 1. Verified position

**[V] The Phase 62 ECB capture does not change this.** Copyright terms govern
*use*, never *provenance*. No amount of licence evidence can establish which
provider supplied the stored values.

| Fact | Evidence |
|---|---|
| Acquisition URL had **no `providers=ecb` pin** | `data/phase33/MANIFEST_FOREX_ECB_daily_reference_rates.txt` |
| Frankfurter's documented default is to **blend** across providers | publisher documentation |
| Raw JSON keys `amount, base, start_date, end_date, rates` — **no provider field** | `data/phase33/raw_forex_ecb_daily/ecb_*.json` |
| CSV asserts `rate_type = ECB_reference_rate` | `data/phase33/ecb_reference_rates_daily_*.csv` |
| Manifest: *"THIS IS NOT AN OHLC DATASET"* | manifest L8 |

**The `rate_type` column asserts ECB reference rates; the acquisition method does
not establish it.** Historical provider identity is **not recoverable from
repository contents**.

---

## 2. Option A — Defer the existing dataset

### What remains blocked

| Use | Status |
|---|---|
| Any new integration consuming ECB rates | **Blocked** |
| Any claim that the stored values are ECB observations | **Blocked** |
| Synthetic OHLC from reference rates | **Blocked — and prohibited outright** |
| Forex research | **Blocked on data quality independently** |

### Files and historical records that remain unchanged

`ecb_reference_rates_daily_20240101_20261008.csv`,
`MANIFEST_FOREX_ECB_daily_reference_rates.txt`, `_forex_meta.json`,
`raw_forex_ecb_daily/*.json`, and the registry entries.

**Option A changes nothing.** It records that the dataset is quarantined pending
evidence.

### Evidence that would justify reconsideration

| # | Evidence | Would establish |
|---|---|---|
| 1 | Phase 33 acquisition script showing the request actually issued | Whether a pin was applied |
| 2 | Frankfurter response schema for an unpinned request | Whether attribution was returned and discarded |
| 3 | A pinned re-query compared against stored values | Equivalence or divergence |

### Consequences for research readiness

**None.** Forex is blocked on **data quality** independently: daily reference
fixings contain no high/low and no volume, the manifest records that the dataset
cannot be loaded by the canonical OHLC loader, and no session/holiday/DST
modelling exists. **Resolving licensing would not unblock forex.**

---

## 3. Option B — Reacquire attributable data

### Provider identity and provenance requirements

| Requirement | Detail |
|---|---|
| **Explicit provider pin** | `providers=ecb`, or the provider-scoped route `/v2/providers/ecb/rates` |
| **Preserve attribution** | Provider keys returned by the API must be stored, never discarded during normalisation |
| **Per-observation attribution** | A sidecar recording the provider for each value |
| **Inadmissible rule** | A rate that cannot be attributed to a provider is **not** admissible as an ECB reference rate |

### Original source URL and retrieval metadata

| Field | Requirement |
|---|---|
| Full request URL incl. query | Recorded verbatim, pin visible |
| Retrieval timestamp | UTC, ISO 8601 |
| Endpoint version | `/v2` recorded explicitly |
| Provider filter | Requested value **and** returned provider list |
| Tooling identifier | Acquisition script name / git SHA |

### Licence/terms evidence and attribution

| Requirement | Status |
|---|---|
| ECB copyright terms | ✅ **Now captured** (`evidence/`, SHA-256 `424859b8…`) |
| Data Portal terms | ❌ **Not captured** — must be, before bulk-export use |
| Attribution requirement | Known: *"the ECB must be cited as the source"* |
| Modification disclosure | Known: applies **if** values are blended |

### Reproducibility, completeness, integrity

| Check | Requirement |
|---|---|
| Independent re-retrieval | A second retrieval at a different time must reproduce the same values |
| Cross-check | Compare against the ECB's own published series |
| Discrepancy handling | A difference is itself a **finding**, recorded — not reconciled away |
| Checksums | SHA-256 per raw and normalised file, plus a manifest row each |
| Retention | Raw responses kept unmodified so the comparison can be repeated |
| **Timestamp convention** | ECB publishes on working days ~16:00 CET except TARGET closing days. **Weekend/holiday gaps are expected and must NOT be filled** — the opposite of an hourly OHLC series |

### Daily reference rates must stay distinct from OHLC

**[V]** The manifest's `date,pair,rate,rate_type,source` schema exists
specifically to prevent rate/candle confusion, and states the dataset
**cannot be loaded by the canonical OHLC loader**. Any reacquisition must
preserve that schema.

**No synthetic OHLC may be constructed.** Reference rates contain no high/low and
no volume; deriving candles would fabricate data the publisher never supplied.

---

## 4. Cost and limitations

| | Option A | Option B |
|---|---|---|
| Effort | None | Acquisition + comparison + documentation |
| Risk of mis-stating provenance | None | Managed by honest reporting of an inconclusive comparison |
| Residual uncertainty | **Permanent** if deferred | **Bounded and known** |
| Operational benefit | None needed | **None** — forex blocked on data quality regardless |
| Reversibility | N/A | Existing dataset retained; new artefact alongside |

**A hard limit on Option B.** It cannot *retroactively* prove what a past HTTP
response contained. A comparison of a **new** retrieval against **stored** values
shows equivalence, not history. If Frankfurter's blend happened to equal the ECB
series for these pairs, the comparison **cannot distinguish** "unpinned but
identical" from "unpinned and blended".

---

## 5. Recommendation

**Option A — defer.**

| Reason | Basis |
|---|---|
| Forex is blocked on data quality regardless | **[V]** daily fixings are not OHLC; no session/holiday/DST modelling |
| The provenance question is **not on the critical path** | No research depends on these rates |
| Option B has a **hard ceiling** on what it can prove | A comparison cannot recover history |
| Option B risks *apparent* resolution | A matching comparison might be read as vindication when it proves less |
| Option B consumes owner attention that B5–B8 need | The research gates are the actual blockers |

**Reconsider if and when** a concrete forex research proposal appears that needs
these rates — at which point Option B's cost becomes justified and the question
becomes operationally relevant rather than merely tidy.

**This is a recommendation. The owner selects.**

---

## 6. Exact owner decision required

> **"I select Option [A — defer / B — authorise re-acquisition and comparison]."**
>
> If B: **"[Named person] is authorised to perform the acquisition and
> comparison, retaining the existing dataset unmodified and producing a
> manifest with request URLs, retrieval timestamps, provider attribution,
> per-file SHA-256, and an explicit comparison result — including where the
> result is inconclusive. Approved by [name], [date]."**

**Not to be done by OpenCode:** acquiring data, altering the existing dataset,
describing the stored values as ECB-sourced, or synthesising OHLC.