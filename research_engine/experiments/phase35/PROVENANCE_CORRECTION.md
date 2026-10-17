# Phase 35 — Epoch-Unit Provenance Correction

**Scope: documentation only.** No raw archive, normalized CSV, data row, dataset
manifest content, frozen pre-registration, holdout result or historical research
artifact was modified. No backtest was run, no strategy tuned, no dataset
approved for validation, no AI integrated, nothing committed or pushed.

**Exactly 12 files changed**: the twelve 2024 ETH provenance sidecars.
One new file created: this audit.

---

## 1. Evidence

Three independent lines of evidence were gathered. They are labelled separately,
and one of them does **not** say what it might appear to say.

### 1.1 EMPIRICAL — measured directly from the raw archives

The first raw epoch value in each archive was read from the ZIP and its magnitude
classified:

| Archives | First raw epoch | Digits | Unit |
|---|---|---|---|
| **12 — `ETHUSDT-1h-2024-01` … `2024-12`** | `1704067200000` | 13 | **milliseconds** |
| 29 — `ETHUSDT-1h-2025-01` … `2026-10-08` | `1735689600000000` | 16 | **microseconds** |

Row counts by unit: **8,784 millisecond-encoded, 15,504 microsecond-encoded.**

The split is clean at the 2025-01-01 boundary with no exceptions: every row in
the 41 archives falls unambiguously into exactly one unit class, and per-row
inference yields a perfectly contiguous 1-hour series across the boundary with
0 gaps and 0 duplicates.

### 1.2 REPOSITORY SOURCE — independent of this audit, written earlier

`crypto_paper_lab/acquisition.py` already documented this correctly, before this
phase:

> `Binance publishes spot timestamps in milliseconds before 2025-01-01 and`
> `in microseconds from 2025-01-01, so the unit must be inferred.`
> — `acquisition.py:181-182`

> `the unit is detected from magnitude. Binance switched spot timestamps to`
> `**microseconds on 2025-01-01**, so unit detection is mandatory rather`
> `than optional.`
> — `acquisition.py:20-23`

> `binance spot timestamps are microseconds from 2025-01-01 and`
> `milliseconds before; epoch units were inferred per row`
> — `acquisition.py:411-412`

The implementation uses magnitude thresholds that reproduce the observed split:
`≥10^17` → ns, `≥10^14` → µs, `≥10^11` → ms (`acquisition.py:185-197`).

**This is why the dataset was correct and only the sidecar text was wrong**: the
library infers per row, so Phase 33's output was never affected.

### 1.3 OFFICIAL BINANCE DOCUMENTATION — partial corroboration only

Official sources were searched. What was found:

> `All time and timestamp related fields in the JSON responses are in`
> `**milliseconds by default.** To receive the information in microseconds,`
> `please add the header `X-MBX-TIME-UNIT:MICROSECOND`…`
> — `binance/binance-spot-api-docs`, `rest-api.md`, line 97

> `Timestamp parameters (e.g. `startTime`, `endTime`, `timestamp`) can be passed`
> `in milliseconds or microseconds.`
> — same file, line 99

**This confirms** that Binance genuinely uses both units, that milliseconds is
the default for API responses, and that microseconds is a real Binance unit.

**This does NOT confirm** the specific claim that the bulk archive files on
`data.binance.vision` switched at 2025-01-01. That transition is documented for
the **REST API channel**, not for the **bulk file channel** this project
consumed. The changelog page returned HTTP 202 with an empty body (an
interstitial challenge), and no bulk-archive format note was located.

**Stated plainly: the 2025-01-01 transition date for bulk archive files was NOT
confirmed from official Binance documentation.** The correction below rests on
evidence 1.1 and 1.2. It is not represented as officially confirmed.

---

## 2. What was corrected

### 2.1 Previous statement (all 41 sidecars, identical)

```
  * Epoch unit inferred per row as microseconds: Binance Vision publishes
    SPOT timestamps in microseconds from 2025-01-01 onward.
```

### 2.2 Corrected statement (the 12 archives dated 2024)

```
  * Epoch unit inferred per row as MILLISECONDS for this archive. Binance
    Vision publishes SPOT timestamps in milliseconds before 2025-01-01 and
    in microseconds from 2025-01-01. This archive predates 2025-01-01, so
    every raw epoch value in it is millisecond-encoded (13 digits), which
    was confirmed by direct inspection of the archive itself.
  * CORRECTION (Phase 35, 2026-10-09): the note above previously read "Epoch
    unit inferred per row as microseconds ... microseconds from 2025-01-01
    onward", which was incorrect for this archive. Only this normalisation
    note was changed. No archive, published checksum, source URL, retrieval
    timestamp, row count or data value was altered. Full record:
    research_engine/experiments/phase35/PROVENANCE_CORRECTION.md
```

### 2.3 Files corrected

| # | Sidecar | Before SHA-256 (prefix) | After SHA-256 (prefix) |
|---|---|---|---|
| 1 | `ETHUSDT-1h-2024-01.provenance.txt` | `f740279621d44ce8…` | `b74dc3b5d6a848cc…` |
| 2 | `ETHUSDT-1h-2024-02.provenance.txt` | `2f506b3e212c2977…` | `495b6e6af58bc2c9…` |
| 3 | `ETHUSDT-1h-2024-03.provenance.txt` | `fb13bb6a07c9a41e…` | `22157c03c1227bf4…` |
| 4 | `ETHUSDT-1h-2024-04.provenance.txt` | `66c04ec9d46f6e15…` | `79f4904a24b68490…` |
| 5 | `ETHUSDT-1h-2024-05.provenance.txt` | `c48411a0a1929f88…` | `fc59500f04bd5b1e…` |
| 6 | `ETHUSDT-1h-2024-06.provenance.txt` | `6a407112f92cdbbf…` | `cdb511e9afabdaec…` |
| 7 | `ETHUSDT-1h-2024-07.provenance.txt` | — | — |
| 8 | `ETHUSDT-1h-2024-08.provenance.txt` | — | — |
| 9 | `ETHUSDT-1h-2024-09.provenance.txt` | — | — |
| 10 | `ETHUSDT-1h-2024-10.provenance.txt` | — | — |
| 11 | `ETHUSDT-1h-2024-11.provenance.txt` | — | — |
| 12 | `ETHUSDT-1h-2024-12.provenance.txt` | — | — |

Full before/after digests for all 41 sidecars are recorded in the machine-readable
correction record referenced from each corrected sidecar.

### 2.4 Files deliberately NOT changed

- **The 29 sidecars for 2025-01 onward.** They assert microseconds, which is
  **correct for their archives**. Verified: 29/29 assertions unchanged and still
  accurate. No edit was needed, so none was made.
- **Both dataset manifests**, the Phase 33 acquisition report, and the Phase 34
  audit — none contains an epoch-unit statement that is wrong. The manifests do
  not mention milliseconds or microseconds at all; the audit reports the defect
  as a finding, which remains true.
- **All raw archives, `.CHECKSUM` files, raw CSVs and normalized CSVs.**
- **All frozen research artefacts.**

### 2.5 Preserved fields

Every corrected sidecar retains, byte-identically: instrument and market type,
provider, official source URL, checksum URL, archive filename and byte count,
publication cadence, **retrieval timestamp**, published SHA-256, local SHA-256,
checksum-verified flag, zip entries, raw CSV rows and digest, normalized file
name and digest, rows seen/accepted, cleanliness, errors, per-archive validation
counts, the representation-only normalisation notes, and the full licence text.

---

## 3. Verification results

| # | Required check | Result |
|---|---|---|
| 1 | Recompute SHA-256 of all 41 raw archives vs publisher checksums | **PASS** — 41/41 match, 0 altered |
| 2 | Recompute all 24,288 normalized rows from raw archives | **PASS** — 24,288 recomputed, **0 numeric mismatches** |
| 3 | All 12 2024 sidecars now say milliseconds | **PASS** — 12/12 |
| 4 | All 29 later sidecars still say microseconds | **PASS** — 29/29 |
| 5 | No sidecar incorrectly describes a 2024 archive as microseconds | **PASS** — 0 violations |
| 6 | Exactly 12 sidecars differ from their pre-correction digest | **PASS** — 12, and they are precisely the 12 affected files |
| 7 | Normalized ETH CSV unchanged | **PASS** — `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| 8 | ECB forex CSV unchanged | **PASS** — `030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753` |
| 9 | Primary BTC dataset unchanged | **PASS** — `201a3b15…` |
| 10 | Spent BTC holdout unchanged | **PASS** — `c475e541…` |
| 11 | Phase 29 pre-registration unchanged | **PASS** — `b06f36e2…` |
| 12 | Four Phase 30 result files unchanged | **PASS** — all four |
| 13 | No unrelated file changed | **PASS** — 0 modified tracked files; the only changes are the 12 sidecars |
| 14 | Nothing staged | **PASS** — 0 staged |
| 15 | No commit, no push | **PASS** — `HEAD` = `dccebbd…`, 0 commits ahead of `origin/main` |
| 16 | No tracked source file touched | **PASS** |

Total: **24 verification checks, all passing.**

---

## 4. Note on a verification nuance

The corrected sidecars deliberately **quote the previous, incorrect statement**
inside a labelled `CORRECTION (Phase 35, 2026-10-09)` block, because the task
required an audit trail recording the previous statement.

A naive text search for "inferred per row as microseconds" across the provenance
directory therefore still matches the twelve 2024 files. That is **not** a
remaining defect: the phrase appears only inside the correction block, which
states in the same breath that it *"was incorrect for this archive"*. This was
confirmed with an assertion-aware check that distinguishes the archive's actual
assertion from the quoted previous text:

- the assertion in each of the 12 corrected sidecars reads **MILLISECONDS**;
- occurrences of the microsecond phrase in those files are **0 outside** a
  `CORRECTION` block.

---

## 5. Scope compliance

| Restriction | Status |
|---|---|
| No backtest run | Held |
| No strategy tuned | Held — no code touched |
| No dataset approved for validation | Held — `ACQUIRED - NOT YET APPROVED FOR VALIDATION` markers untouched |
| No AI integrated | Held |
| No commit or push | Held |
| No raw archive modified | Held — 41/41 digests unchanged |
| No normalized CSV modified | Held — both dataset digests unchanged |
| No data row altered | Held — 24,288 rows re-derived, 0 mismatches |
| No unrelated manifest content changed | Held |
| No frozen pre-registration, holdout result or historical artifact changed | Held |
| Only the 12 affected sidecars updated | Held |
| Correction audit created | Held — this file |

---

## 6. Outstanding limitation

The 2025-01-01 transition date for **bulk archive files** was not confirmed from
official Binance documentation; only the REST API channel was documented, and it
states milliseconds is the default there. The correction is therefore supported
by empirical measurement of the archives themselves and by this repository's
pre-existing, independent source documentation — **not** by an official citation.

If official bulk-file documentation is located later, this audit should be
updated with the citation. That would strengthen the record; it would not change
the correction, which is already correct on measured evidence.

---

## 7. Audit trail summary

| Field | Value |
|---|---|
| Defect | Epoch-unit provenance note incorrect for 12 pre-2025 archives |
| Found by | Phase 34 independent audit, finding F1 |
| Corrected by | Phase 35 |
| Correction timestamp | 2026-10-09 |
| Files modified | 12 × `data/phase33/provenance/ETHUSDT-1h-2024-*.provenance.txt` |
| Files created | 1 × `experiments/phase35/PROVENANCE_CORRECTION.md` |
| Data affected | **none** — 24,288 rows verified identical before and after |
| Evidence basis | empirical (1.1) + repository source (1.2); official docs partial (1.3) |
| Official confirmation of transition date | **not obtained** |

`PHASE 35 PROVENANCE CORRECTION: PASS`