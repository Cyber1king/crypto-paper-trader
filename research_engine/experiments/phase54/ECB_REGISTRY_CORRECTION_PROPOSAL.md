# Phase 54 — ECB Registry Correction Proposal

**Date:** 2026-10-09
**Status:** **PROPOSAL ONLY — NOT APPLIED. Not legally approved. No registry state
was changed.**

---

## 1. Independent verification of the evidence (not Phase 53's word for it)

The instruction was to verify the source evidence **already available in the
repository**, and not to treat Phase 53's statement as proof. Done literally,
that produced the phase's most important finding.

### 1.1 What the repository actually contains

```
$ git grep -In "ECB" -- "*.md" "*.txt" | grep -Ei "licen|copyright|CC BY|terms|attribut|reproduc"
  (no results)
```

**There is no ECB licence documentation anywhere in the tracked repository.**

The `CC BY-NC-SA 4.0` label exists in exactly one place —
`research_registry.json` — and it is not accompanied by any citation, URL,
retrieval date, or quoted source text.

Contrast Binance, where the terms are quoted in eight provenance sidecars and
four Phase 9/10 reports. The ECB label was **asserted without recorded
evidence**.

**[V]** The registry `licence_note` for all three forex instruments reads:

> *"ECB reference rates are published under CC BY-NC-SA 4.0. Non-commercial use
> only, share-alike, attribution required. Commercial use is excluded."*

**[V]** `research_registry.json` is itself untracked and was created in Phase 45.
No earlier phase recorded an ECB licence determination.

### 1.2 What Phase 53 retrieved (external, not re-verified here)

Phase 53 fetched the ECB's *Disclaimer & copyright* page on **2026-10-09** and
recorded: free use subject to conditions — cite the ECB as source, **state
modifications explicitly**, give buyers of sold documents a "free of charge"
notice, no framing; ECB Working/Occasional Papers need prior written
authorisation. It also recorded that ECB reference rates are *"published for
information purposes only"* and that *"using the rates for transaction purposes
is strongly discouraged."*

**[V]** Phase 54 did **not** re-fetch that page. Repeating it would not have been
independent verification of the *repository* evidence, which is nil. What Phase
54 adds is the finding that the repository contains nothing to verify against.

**[P]** The correction below should therefore be accompanied by capturing the ECB
page into the repository as a durable, dated citation — so that the next auditor
does not face the same empty search this phase did.

### 1.3 Conclusion on evidence quality

| Question | Answer |
|---|---|
| Is the current label sourced in-repo? | **No** |
| Is the current label contradicted by the publisher's own current text? | **Yes** (per Phase 53's dated retrieval) |
| Is the right to *use* ECB rates for non-commercial research established? | **Yes** — ECB permits free use subject to conditions |
| Are the stored values unmodified ECB fixings? | **Unresolved** (§4) |

The label is **unsupported and apparently inaccurate**. The underlying right to
use the data is not in doubt.

---

## 2. The proposed correction

### 2.1 `licence_name`

| | Value |
|---|---|
| **Existing** | `"CC BY-NC-SA 4.0"` |
| **Proposed** | `"ECB website copyright policy (free use with conditions)"` |

Rationale: a free-text descriptive label naming the actual instrument. It does
not claim a Creative Commons grant the ECB does not make.

### 2.2 `licence_note`

| | Value |
|---|---|
| **Existing** | *"ECB reference rates are published under CC BY-NC-SA 4.0. Non-commercial use only, share-alike, attribution required. Commercial use is excluded."* |
| **Proposed** | *(below)* |

```
ECB euro foreign exchange reference rates are published under the ECB's
website copyright policy: free use of the information obtained directly from
the ECB website is permitted subject to conditions - cite the ECB as the
source; state explicitly any modification of the information; where the
information is incorporated into documents that are sold, inform buyers that
it is available free of charge from the ECB website; do not frame the site
on business sites. Reproduction of ECB-authored works such as Working Papers
and Occasional Papers in a different publication requires the ECB's prior
written authorisation. Not CC BY-NC-SA 4.0: no share-alike obligation and no
non-commercial restriction arise from the ECB copyright terms.
Source: https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html
Retrieved: 2026-10-09 (Phase 53). The ECB Data Portal (data.ecb.europa.eu)
terms were not separately verified. Values in this repository were retrieved
via frankfurter.app without a providers=ecb pin and may be provider-blended;
their transformation status is unconfirmed - see phase54/ECB_REGISTRY_CORRECTION_PROPOSAL.md.
```

### 2.3 `licence_knowledge`

**[V]** `registry_schema.py` L89 constrains this field to
`{VERIFIED, UNVERIFIED, RESTRICTED}`.

| | Value |
|---|---|
| **Existing** | `"VERIFIED"` |
| **Proposed** | **No change** — remain `"VERIFIED"` |

Rationale: the *right to use* these rates for non-commercial research is
established by the publisher's own text. What was wrong was the *description*,
not the confidence. Downgrading to `UNVERIFIED` would understate what is known
about the terms while implying the data itself is unusable.

**[P]** A reviewer who weighs the in-repo evidence gap more heavily may prefer
`UNVERIFIED` until the ECB page is captured into the repository. That is a
legitimate alternative position and is recorded here rather than decided.

---

## 3. Why the difference matters

| | CC BY-NC-SA 4.0 (current label) | ECB policy (actual) |
|---|---|---|
| Commercial use | Prohibited | Not prohibited by the copyright clause |
| Share-alike | Required | Not required |
| Attribution | Required | Required |
| **Modification disclosure** | Not required | **Explicitly required** |
| **Resale notice** | n/a | **Required for sold documents** |
| Framing restriction | n/a | Required for business links |
| Authored works | n/a | Prior written authorisation |

The current label errs in **both directions**. It imposes an obligation that does
not exist (share-alike) and a prohibition that does not exist (non-commercial),
while omitting two duties that do (modification disclosure, resale notice).

This is not pedantry: the registry is the machine-readable surface a future
integration consults. A system that read the current note would believe it must
apply share-alike — while failing to implement the modification-disclosure duty
that actually binds.

---

## 4. Additional finding: the stored values may be modified

**[V]** The Phase 33 manifest records the acquisition URLs as:

```
https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD
https://api.frankfurter.app/2024-01-01..2026-10-08?from=GBP&to=USD
https://api.frankfurter.app/2024-01-01..2026-10-08?from=USD&to=JPY
```

**[V]** **No `providers=ecb` parameter is present.**

**[V]** Frankfurter's documented default behaviour is to **blend** rates across
providers unless a provider filter is supplied.

**[V]** The stored raw JSON payload has keys `amount, base, start_date,
end_date, rates` and contains **no provider or attribution field**, so the
provenance of each individual value cannot be recovered from the stored file.

**[V]** The normalised CSV carries `rate_type = ECB_reference_rate` and
`source = European_Central_Bank_via_frankfurter.app`.

**[U] Unresolved.** Whether these are unmodified ECB fixings or blended
cross-provider values **cannot be determined from the repository**. The
`rate_type` label asserts ECB reference rates; the acquisition method does not
guarantee it.

**Consequence if blended:** ECB's condition *"if the information is modified by
the user … this must be stated explicitly"* is engaged, and the series is a
derived figure rather than an ECB fixing. That disclosure is currently absent
from every forex artifact.

**[P] [H]** Resolving this requires either re-acquisition with `providers=ecb`
and comparison, or inspection of the Phase 33 acquisition code. Neither is
performed in this phase; acquisition is out of scope.

---

## 5. Required governed transition

**[V]** `licence_name` is **free text** — the schema constrains only
`licence_knowledge` (L307). The proposed correction is therefore schema-valid.

**[V]** The registry is currently untracked (`?? research_engine/data/research_registry.json`)
and was authored in Phase 45.

**Transition requirements**

| # | Requirement |
|---|---|
| 1 | Capture the ECB page as a dated in-repo citation so the label is sourced (closes §1.1) |
| 2 | Named approver and date for the change |
| 3 | Re-run `validate_registry()` after editing; the correction must pass schema validation |
| 4 | Apply to all three instruments consistently — EUR/USD, GBP/USD, USD/JPY |
| 5 | Record the decision in a research record, not only in the registry |
| 6 | Do not alter `licence_knowledge`, reservation, or any research field while doing so |

**[V]** No registry write was performed in this phase. No governed state was
changed. Nothing was staged, committed or pushed.

---

## 6. Standing constraints

**[V]** The ECB publishes these rates *"for information purposes only"* and
discourages their use for transactions.

**[V]** Forex remains blocked on **data quality** — daily reference fixings are
not OHLC, and the manifest states the dataset cannot be loaded by the canonical
OHLC loader. No session, holiday or DST modelling exists.

**No ECB rate was used in this phase. No new integration was begun. No
reference rate was converted into synthetic OHLC.** Correcting the licence label
would not unblock forex; the blocking constraint is elsewhere.

---

## 7. Human approval required

| # | Decision |
|---|---|
| **H4.1** | Approve the `licence_name` and `licence_note` correction as written, or amend it |
| **H4.2** | Confirm `licence_knowledge` stays `VERIFIED`, or downgrade to `UNVERIFIED` pending captured evidence |
| **H4.3** | Decide whether to re-acquire ECB data with a `providers=ecb` pin, or defer while forex stays blocked |
| **H4.4** | Name the approver and date for the registry change |

**Until approved, the registry continues to carry a licence label that its own
publisher's text does not support.**