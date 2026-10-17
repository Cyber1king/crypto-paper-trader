# Phase 57 — ECB Provenance Recovery Plan

**Date:** 2026-10-09
**Scope:** Step 5 — what would be required to identify the actual provider of
the stored daily reference rates.

> **No ECB-derived data is used for any new integration, and no synthetic OHLC
> is constructed.** This plan is a specification, not an execution.

---

## 1. Current state — what is known and what is not

| Fact | Status | Evidence |
|---|---|---|
| Forex data exists: daily reference fixings + raw JSON | **Verified** | `data/phase33/` |
| Schema is `date,pair,rate,rate_type,source` — **not OHLC** | **Verified** | file |
| Manifest states *"THIS IS NOT AN OHLC DATASET"* | **Verified** | manifest |
| Acquisition URL: `https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD` | **Verified** | manifest |
| The URL carries **no `providers=ecb` parameter** | **Verified** | manifest |
| Frankfurter's documented default is to **blend** across providers unless a provider filter is given | **Publisher-sourced** | Frankfurter docs |
| Raw JSON keys: `amount, base, start_date, end_date, rates` | **Verified** | file |
| The payload carries **no provider or attribution field** | **Verified** | file |
| CSV records `rate_type = ECB_reference_rate` | **Verified** | file |
| CSV records `source = European_Central_Bank_via_frankfurter.app` | **Verified** | file |

**The central gap.** The acquisition method did not pin the provider, and the
stored payload does not identify it. The `rate_type` label *asserts* ECB
reference rates; the acquisition method does not *establish* it.

**This cannot be resolved from the repository as it stands.** No amount of
inspection of the stored bytes recovers a field that was never recorded.

---

## 2. Why it matters

If the stored values are **blended** rather than pure ECB fixings, then:

1. They are **modified figures**, engaging the ECB's explicit condition that
   *"if the information is modified by the user … this must be stated
   explicitly."* That disclosure is currently absent from every forex artefact.
2. The `rate_type = ECB_reference_rate` label would be **inaccurate**.
3. Any future integration would inherit an undocumented transformation.

If the values are **pure ECB**, point 1 disappears and only the missing citation
in B2 remains.

**Either outcome is actionable. Only one of them is currently unknown.**

---

## 3. Evidence required

### 3.1 The exact request issued in Phase 33

- Retrieve the Phase 33 acquisition script and its invocation record.
- Confirm whether `providers=ecb` was passed, or any equivalent pin.
- Record the **retrieval timestamp** to pair with any response metadata.

### 3.2 The response schema actually returned

- Determine whether Frankfurter returns any provider attribution for an unpinned
  request (e.g. via `expand=providers`), and whether it was discarded.
- If attribution *was* returned and dropped, that is recoverable from the
  request/response contract even though the stored file lacks it.

### 3.3 A reproducible comparison

The decisive test: re-query the same window and pairs **with** `providers=ecb`,
and compare against the stored values.

| Outcome | Conclusion | Required action |
|---|---|---|
| **Exact match** | Stored values are ECB fixings | Correct the ambiguity in the manifest; add the ECB citation; B4 closes |
| **Any mismatch** | Stored values are blended | Add explicit modification disclosure to every forex artefact and to `licence_note`; relabel `rate_type` |
| **Comparison not runnable** | Unresolvable retrospectively | Leave **UNVERIFIED**; keep forex blocked |

---

## 4. Requirements for any NEW acquisition

If re-acquisition is authorised, the following are mandatory. They are stated so
that a repeat of the current ambiguity cannot occur.

### 4.1 Endpoint and provider pinning

- Endpoint: `https://api.frankfurter.app/v2/...` with an explicit
  **`providers=ecb`** parameter.
- Provider-scoped route preferred: `/v2/providers/ecb/rates`, which returns ECB
  values directly rather than through the default blended path.
- **The provider pin must appear in the recorded request string**, not only in
  code.

### 4.2 Provider identification

- Preserve any provider attribution the response returns. Do **not** discard it
  during normalisation.
- Record the provider key(s) per observation in a sidecar, even when a single
  provider is used.
- If a rate cannot be attributed to a provider, it is **not** admissible as an
  ECB reference rate.

### 4.3 Retrieval metadata

| Field | Requirement |
|---|---|
| Full request URL incl. query | Recorded verbatim |
| Retrieval timestamp | UTC, ISO 8601, second precision |
| Endpoint version | `/v2` recorded explicitly |
| Provider filter | Value recorded, and the **response** provider list recorded |
| Tooling version | Acquisition script identifier / git SHA |

### 4.4 Timestamp conventions

- ECB publishes on **working days at ~16:00 CET**, except TARGET closing days.
- The dataset must record, per observation: the **rate date** and the
  **business-day convention** used.
- **Weekend and holiday gaps are expected and must not be filled.** A gap in a
  daily reference-rate series is correct, not a defect — the opposite of the
  hourly-OHLC case.
- Store timestamps as dates with an explicit **UTC-anchored business calendar**
  note. ECB reference rates are not intraday observations.

### 4.5 Checksums and integrity

| Artefact | Requirement |
|---|---|
| Raw response | SHA-256 recorded per file, alongside the request URL |
| Normalised CSV | SHA-256 recorded, derived-from chain documented |
| Manifest | One row per file: source URL, request parameters, retrieval timestamp, raw SHA-256, normalised SHA-256 |
| Provenance sidecar | Per file, stating provider identification and any transformation |
| Re-verification | Raw response retained **unmodified** so the comparison can be repeated |

### 4.6 Independent verification

- A **second, independent retrieval** at a different time must reproduce the same
  values for the same dates.
- Values must be checked against the ECB's own published series where available
  (ECB Data Portal / CSV export) — noting that Data Portal terms are themselves
  **unverified** and must be captured separately under B2.
- Any discrepancy between the Frankfurter ECB path and the ECB's own series is
  itself a finding and must be recorded, not reconciled away.

### 4.7 Constraints that still apply regardless

- **Never construct OHLC from reference rates.** Daily reference fixings contain
  no high/low and no volume. Synthesising candles would fabricate data the
  publisher never supplied.
- Forex remains blocked on **data quality** independently of provenance: no
  genuine OHLC, and no session / holiday / DST modelling.
- **Do not silently replace existing data.** Any re-acquisition produces a *new*
  artefact with its own provenance. The existing file is retained unchanged, and
  the old/new comparison is recorded as the evidence.

---

## 5. Decision paths

| # | Path | Preconditions | Outcome |
|---|---|---|---|
| **1** | **Defer** (recommended) | None | Forex stays blocked on data quality. B4 remains open. Zero risk |
| 2 | Inspect the Phase 33 acquisition code | Code archaeology only, no acquisition | May resolve the question cheaply if the code records the request |
| 3 | Re-acquire with a provider pin | Explicit authorisation | Produces definitive evidence; **new** artefact, existing data retained |
| 4 | Leave UNVERIFIED permanently | — | Correct and honest if provenance is unrecoverable |

**Path 1 is recommended** because forex is blocked on data quality regardless, so
resolving licensing would not unblock anything. Paths 2 and 3 are worth taking
only if forex integration is genuinely intended later.

---

## 6. Guarantee boundary

**Nothing in this plan can retroactively establish what a past HTTP response
contained.** Path 3 compares a *new* retrieval against the *stored* values; it
does not prove what the original response said. If Frankfurter's default blend
happened to equal the ECB series for these pairs, a comparison cannot
distinguish "unpinned but identical" from "unpinned and blended".

That residual uncertainty is inherent. It is why the current state is recorded
as **UNVERIFIED** rather than resolved by inference.

---

## 7. Status

**B4 remains `OPEN`.** The evidence gap is precisely specified, the plan is
reproducible, and no historical provenance has been fabricated.

**No ECB rate was used. No integration begun. No synthetic OHLC constructed. No
existing data replaced.**