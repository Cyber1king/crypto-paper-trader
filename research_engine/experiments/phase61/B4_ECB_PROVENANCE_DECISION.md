# Phase 61 — B4: ECB Provenance Decision Brief

**Status: `OWNER DECISION REQUIRED` — blocker remains open.**
**The existing dataset's provider attribution is unresolved and stays
unresolved** unless new evidence establishes it.

---

## 1. Verified facts

| Fact | Evidence |
|---|---|
| Acquisition URL: `https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD` (and GBP, USD/JPY) | `data/phase33/MANIFEST_FOREX_ECB_daily_reference_rates.txt` |
| **No `providers=ecb` parameter** in any of the three URLs | same |
| Frankfurter's documented default is to **blend** across providers unless a provider filter is supplied | Frankfurter documentation (external, not retained) |
| Raw JSON keys: `amount, base, start_date, end_date, rates` — **no provider or attribution field** | `data/phase33/raw_forex_ecb_daily/ecb_EURUSD_*.json` |
| CSV asserts `rate_type = ECB_reference_rate` | `data/phase33/ecb_reference_rates_daily_*.csv` |
| CSV asserts `source = European_Central_Bank_via_frankfurter.app` | same |
| Manifest opens: *"THIS IS NOT AN OHLC DATASET"* | manifest L8 |

---

## 2. The unresolved question

**Are the stored values unmodified ECB reference fixings, or provider-blended
figures?**

Because the acquisition did not pin the provider and the payload records no
provider, **this cannot be determined from the repository.** The `rate_type`
column *asserts* ECB reference rates; the acquisition method does not
*establish* it.

**Consequence if blended:** the values are modified figures, and the ECB's
explicit condition — *"if the information is modified by the user … this must be
stated explicitly"* — is engaged. **No such disclosure exists in any forex
artefact.**

---

## 3. Option A — Defer

**Action:** take no further action. Keep the ECB dataset out of any new
integration.

| | |
|---|---|
| **Benefits** | Zero risk of fabricating or corrupting provenance. Zero cost. Forex is blocked on data quality regardless, so nothing is lost operationally |
| **Limitations** | The question stays unanswered. If a future ECB integration is wanted, this work must be redone |
| **Documentary requirements** | None — this is a decision to *not* act |
| **Data-quality implications** | None. Daily reference fixings are **not OHLC**; the manifest records that the dataset cannot be loaded by the canonical OHLC loader |
| **What stays unresolved** | Whether the stored values are ECB fixings. **Permanently, if deferred indefinitely** |

---

## 4. Option B — Reacquire with verifiable attribution

**Action:** re-query with an explicit provider pin and compare against the
stored values. **This produces a new artefact; it does not replace the
existing data.**

### Steps

| # | Step | Purpose |
|---|---|---|
| 1 | Retrieve the Phase 33 acquisition script | Confirm the request actually issued |
| 2 | Re-query `…?providers=ecb&from=…&to=…` | Obtain pinned ECB values |
| 3 | Compare against `ecb_reference_rates_daily_*.csv` | **Exact match → unmodified ECB. Any mismatch → blended** |
| 4 | Inspect the Frankfurter response schema | Determine whether provider attribution was returned and discarded |
| 5 | Record the outcome | Add modification disclosure and relabel `rate_type` if blended |

### Requirements for any new acquisition

- **Explicit provider pin** in the recorded request URL (`providers=ecb`, or the
  provider-scoped route `/v2/providers/ecb/rates`)
- **Preserve provider attribution** returned by the API; never discard it
  during normalisation
- Record: full request URL, retrieval timestamp (UTC), endpoint version,
  provider filter value, response provider list, tooling identifier
- **Timestamp convention:** ECB publishes on working days ~16:00 CET except
  TARGET closing days. Weekend/holiday gaps are **expected and must not be
  filled** — the opposite of an hourly-OHLC series
- **Checksums:** SHA-256 for raw and normalised files, plus a manifest row per
  file (source URL, request parameters, retrieval timestamp, both digests)
- Retain raw responses unmodified so the comparison can be repeated
- **Independent verification:** a second retrieval at a different time must
  reproduce the same values; compare against the ECB's own series where
  available

| | |
|---|---|
| **Benefits** | Resolves the question with evidence; produces a defensible provenance chain |
| **Limitations** | Cannot *retroactively* prove what a past HTTP response contained — a comparison of a **new** retrieval against **stored** values shows equivalence, not history. If the blend happened to equal the ECB series for these pairs, the comparison cannot distinguish "unpinned but identical" from "unpinned and blended" |
| **Data-quality implications** | None improved. Daily fixings remain **not OHLC** |
| **What stays unresolved** | The **original** acquisition's provider attribution, permanently, if the comparison is inconclusive |

---

## 5. Comparison

| | Option A: Defer | Option B: Reacquire + compare |
|---|---|---|
| Resolves the question | No | Probably |
| Risk of fabricating provenance | None | None, if honest reporting |
| Cost | Zero | Acquisition + comparison effort |
| Operational benefit | None needed — forex blocked anyway | None needed |
| Residual uncertainty | Permanent | Bounded, and known |
| Modifies existing data | No | **No** — new artefact alongside |

---

## 6. Constraints observed in this phase

- **No new dataset was downloaded.**
- **No historical data was altered.**
- **No registry classification was modified.**
- **No reference rate was converted into synthetic OHLC.** The manifest's
  `date,pair,rate,rate_type,source` schema exists precisely to prevent that
  confusion, and it is retained.

---

## 7. What stays unresolved either way

**[V]** The identity of the provider that actually supplied each stored value in
2024–2026 **cannot be established retrospectively from repository contents**,
because no provider field was recorded at acquisition time.

This is an **evidence gap, not a defect to be repaired by inference.**

---

## 8. Exact owner decision required

> **"I select Option [A — defer / B — authorise re-acquisition and comparison]."
> If B: "[named person] is authorised to perform steps 1–5, retaining the
> existing dataset unmodified. Approved by [name], [date]."**

**Not to be done by OpenCode:** acquiring data, altering the existing dataset,
describing the stored values as ECB-sourced, or choosing an option.