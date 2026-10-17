# Phase 56 — Licensing and Provenance

**Date:** 2026-10-09
**Covers:** Part 4 — B1, B2, B3, B4.

**No licence was selected. No governed registry state was changed. No legal
approval is claimed or implied.**

---

## B1 — Python package licence

**Status: `OPEN — OWNER DECISION REQUIRED`**

### Verified facts

| Fact | Evidence |
|---|---|
| Root `package.json`: `"name": "workspace"`, `"license": "MIT"` | file |
| `pnpm-workspace.yaml` scopes the workspace to `artifacts/*`, `lib/*`, `lib/integrations/*`, `scripts` | file |
| **`research_engine` is not in that workspace** | file |
| `research_engine/pyproject.toml` (`crypto-paper-lab` 0.1.0) has **no** `license` field, no licence classifier | file |
| **No `LICENSE` file anywhere in the repository** | tracked-file search |
| `research_engine/README.md` states *"Tooling — no licence granted"* | Phase 53 edit |
| No SPDX headers anywhere | grep |

**Accurate position:** the JavaScript tooling carries an MIT declaration; the
Python research engine is **unlicensed — all rights reserved by default**.

### Option comparison

| Option | Scope granted | Consequence for this repo | Consequence for data |
|---|---|---|---|
| **A. No licence (status quo)** | Nobody may lawfully copy, modify or redistribute the Python code | Blocks all third-party reuse. Safe default, but almost certainly unintentional given the repo is otherwise permissive | Unaffected |
| **B. MIT** | Any use, including commercial; redistribution permitted with notice; no patent grant | Consistent with the JS tooling; widest reuse; simplest | Unaffected — code licence cannot alter CC BY-NC-SA on data |
| **C. Apache-2.0** | As MIT, plus an explicit patent grant and a NOTICE obligation | Consistent; adds patent clarity and a NOTICE file to maintain | Unaffected |
| **D. BSD-3-Clause** | As MIT, plus a no-endorsement clause | Consistent; common for research code | Unaffected |
| **E. CC BY-NC-SA 4.0 on code** | Non-commercial only; **share-alike propagates to derivatives** | Would make any derived work non-commercial. Conflicts with keeping tooling permissive and separate from data terms | Aligns code and data terms, at the cost of barring commercial reuse of the code |

### Considerations

- **The choice is a grant of rights, not a technical finding.** It depends on
  whether the owner wants reuse, and on what kind. No evidence in the repository
  answers that.
- **Scope boundary is unaffected either way.** A code licence never changes the
  Binance Vision terms on derived data, nor the ECB's terms on rates.
- **E has a compounding effect** most owners would not intend: share-alike would
  attach a non-commercial restriction to anything built from this code.
- **Consistency argument:** MIT, Apache-2.0 and BSD-3 are all defensible; the
  repo's JS side already declares MIT.

**No option is recommended as a default here, because the deciding factor —
intended reuse — is an owner preference not derivable from the repository.**
If consistency with the existing JS tooling is the priority, B is the
conventional match.

**Decision required:** choose A/B/C/D/E and name the approver.

---

## B2 — ECB registry correction

**Status: `READY FOR APPROVAL` — analysis complete**

### What is verified

| Fact | Status |
|---|---|
| Registry asserts `CC BY-NC-SA 4.0` for EUR/USD, GBP/USD, USD/JPY | **Verified** — `research_registry.json` |
| **No ECB licence documentation exists in the repository** | **Verified** — `git grep` across `*.md`/`*.txt` returns nothing |
| The label carries no URL, retrieval date or quoted source | **Verified** |
| ECB's own terms grant free use with conditions: cite ECB, **state modifications**, resale notice, no framing | **Publisher-sourced, retrieved 2026-10-09** (Phase 53) |
| The label asserts share-alike and non-commercial terms the ECB does not impose | **Verified** by comparison |
| The label omits modification-disclosure and resale duties the ECB does impose | **Verified** |

### What is NOT verified

| Question | Status |
|---|---|
| Are the stored rates ECB-published observations? | **UNVERIFIED — see B4** |
| Do the ECB **Data Portal** terms differ from the website terms? | **Unverified** — not separately checked |

**The distinction this section must not blur:** ECB's *terms* are established;
the *provenance of the stored values* is not. The registry label describes terms,
so it can be corrected on term evidence alone. It must not be read as certifying
that the stored numbers are ECB fixings.

### Proposed metadata changes

| Field | Existing | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | *"ECB reference rates are published under CC BY-NC-SA 4.0. Non-commercial use only, share-alike, attribution required. Commercial use is excluded."* | ECB conditions verbatim, with source URL, retrieval date 2026-10-09, and an explicit note that stored values may be provider-blended |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use is established; only the description was wrong |

**[V]** `licence_name` is free text; the schema constrains only
`licence_knowledge` (`registry_schema.py` L307), so the change is schema-valid.

**Gap to close before applying:** capture the ECB page into the repository as a
dated citation, so the replacement is sourced rather than merely asserted —
otherwise one unsourced label is swapped for another.

**Decision required:** approve the wording; decide whether to capture the page
first; name the approver and date.

---

## B3 — Binance licence status

**Status: `READY FOR APPROVAL` — evidence already durable in-repository**

### Evidence rechecked against actual files

| Evidence | Location |
|---|---|
| CC BY-NC-SA 4.0 + Vision Dataset Terms stated | 8 × `data/oos/raw/*.provenance.txt`, each at L46 |
| Permitted/prohibited uses stated | same sidecars |
| Licence split (tooling vs data) recorded | `experiments/phase9/DATA_SOURCE_REVIEW.md` L39 — *"Verified"* |
| Publisher terms v1.0, 26 Aug 2026 | re-fetched Phase 52/53/55, unchanged |

### Recommended transition

| Field | Existing | Recommended |
|---|---|---|
| `licence_knowledge` | `"UNVERIFIED"` | `"VERIFIED"` |
| `licence_name` | `null` | `"CC BY-NC-SA 4.0"` |
| `licence_note` | *"Same provider and same unestablished redistribution terms as BTC/USDT."* | Cite Vision Dataset Terms v1.0 §3.1 and §4.5 |

### Schema compatibility

**[V]** `LICENSE_KNOWLEDGE = frozenset({"VERIFIED", "UNVERIFIED", "RESTRICTED"})`
(`registry_schema.py` L89). `UNVERIFIED → VERIFIED` is a permitted value.

**[V]** The evidence standard in the schema's own comment (L86–88): *"Licence
states this repository can state with confidence. Anything else must be recorded
as `UNVERIFIED` rather than guessed."* The Binance evidence is eight sidecars
plus four reports plus the publisher's current text — it comfortably clears that
bar.

**[V]** The current `UNVERIFIED` marker is a **regression below the
repository's own documentation**, not prudence: Phase 9 already recorded the
licence as verified.

**Not changed.** This is a governed state transition and no project rule
authorises an agent to apply it unilaterally.

**Decision required:** approve the transition; name the approver and date.

---

## B4 — ECB provenance

**Status: `OPEN — BLOCKER REMAINS`**

### The finding

| Fact | Evidence |
|---|---|
| Forex data exists: daily reference fixings + raw JSON | `data/phase33/` |
| Schema is `date,pair,rate,rate_type,source` — **not OHLC** | file |
| Acquisition URL: `…/2024-01-01..2026-10-08?from=EUR&to=USD` — **no `providers=ecb`** | manifest |
| Frankfurter's documented default is to **blend** across providers | publisher docs |
| Raw JSON keys: `amount, base, start_date, end_date, rates` — **no provider field** | file |
| `rate_type` asserts `ECB_reference_rate` | file |

**The stored values cannot be confirmed as ECB-published observations.** The
acquisition endpoint did not pin the provider, and the payload carries no
provider identification. A blended series would be a **modified** figure,
engaging ECB's explicit condition that modifications be stated.

### Evidence required to resolve

1. The **exact request** issued in Phase 33 — if it omitted `providers=ecb`, the
   default blend applies.
2. **Frankfurter's response schema** for that call — whether any provider
   attribution was returned and discarded.
3. A **reproducible comparison**: re-query with `providers=ecb` and compare
   against stored values. Identical values → unmodified ECB. Differences →
   blended, and a disclosure obligation applies.
4. The acquisition **timestamp**, to pair with the response.

### Proposed plan (reproducible; nothing is asserted as historical fact)

```
Step 1  Re-query Frankfurter with providers=ecb for the same window and pairs.
Step 2  Compare returned values against data/phase33/ecb_reference_rates_*.csv.
          exact match  -> stored values are ECB fixings
          any mismatch -> stored values are blended; disclosure obligation engaged
Step 3  Inspect the Phase 33 acquisition script for the request actually issued.
Step 4  If blended: add an explicit modification disclosure to the forex
        artifacts and to the registry licence_note.
Step 5  If unresolvable: leave UNVERIFIED, and do not use the data for any new
        integration.
```

**Step 5 is the current state.** No historical provenance is fabricated, and no
data is silently substituted.

### Why this is not urgent

Forex is blocked on **data quality** independently of licensing: daily reference
fixings are not OHLC, the manifest states the dataset cannot load via the
canonical loader, and no session/holiday/DST modelling exists. **Resolving
licensing would not unblock forex.**

**No ECB rate was used in this phase. No synthetic OHLC was constructed. No
integration begun.**

**Decision required:** defer (recommended), or authorise the re-acquisition and
comparison in Step 1–2.

---

## Summary

| ID | Status | Blocked on | Urgency |
|---|---|---|---|
| **B1** | OPEN | Owner licence choice | Before any public release |
| **B2** | Ready for approval | Owner sign-off; capturing the ECB page would close the sourcing gap | Before forex integration |
| **B3** | Ready for approval | Owner sign-off only | Before public release |
| **B4** | OPEN | Re-acquisition + comparison | Low — forex blocked on data quality regardless |

**No licence was selected. No registry state changed. No legal conclusion
asserted.**