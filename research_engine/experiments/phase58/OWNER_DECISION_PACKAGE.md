# Phase 58 — Owner Decision Package

**Date:** 2026-10-09
**Scope:** Steps 6–7 — every outstanding decision, with evidence status.

> **No licence selected. No legal conclusion adopted. No threshold invented. No
> approval recorded.** Every "recommendation" below is a proposal awaiting the
> owner; none has been converted into a decision.

## Status vocabulary

| Label | Meaning |
|---|---|
| ✅ **EVIDENCE VERIFIED** | Checked against the repository in this phase |
| 🟡 **RECOMMENDATION** | A proposal exists; owner has not decided |
| ⬜ **UNMET** | No decision or artefact exists |
| 🔒 **OWNER APPROVAL** | Requires a signature — **none exists** |

---

## B1 — Python package licence

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL**

**Evidence verified:** root `package.json` declares `"license": "MIT"` for npm
package `"workspace"`; `pnpm-workspace.yaml` scopes that to `artifacts/*`,
`lib/*`, `lib/integrations/*`, `scripts`; **`research_engine` is not in that
workspace**; `research_engine/pyproject.toml` has **no** `license` field or
classifier; **no `LICENSE` file exists anywhere**; no SPDX headers.

**Scope statement:** the Python package `crypto-paper-lab` is a separate
distributable. The root MIT does **not** reach it. It is currently
**unlicensed — all rights reserved by default**.

| Option | Scope | Consequence | Data unaffected? |
|---|---|---|---|
| **A. No licence** | No one may copy, modify or redistribute | Blocks all third-party reuse; safe default, likely unintentional | Yes |
| **B. MIT** | Any use incl. commercial; notice on redistribution; no patent grant | Consistent with the JS tooling; widest reuse | Yes |
| **C. Apache-2.0** | As MIT + explicit patent grant + NOTICE obligation | Adds patent clarity and a NOTICE file | Yes |
| **D. BSD-3-Clause** | As MIT + no-endorsement clause | Common for research code | Yes |
| **E. CC BY-NC-SA 4.0** | Non-commercial; **share-alike propagates to derivatives** | Any derived work becomes non-commercial | Aligns code with data terms |

**Recommendation:** none. The deciding factor — intended reuse — is an owner
preference not derivable from the repository. If consistency with the JS tooling
is the priority, **B** is the conventional match. Option E's share-alike has a
compounding effect worth considering before choosing it.

**Exact owner input:** "I select option **[A/B/C/D/E]** for `crypto-paper-lab`,
effective **[date]**, approved by **[name]**", plus the copyright holder to name
in the header for B/C/D/E.

---

## B2 — ECB terms correction

**Status: 🟡 RECOMMENDATION · 🔒 OWNER APPROVAL — blocked on missing evidence**

**Two distinct things, kept separate:**

**(a) Source terms — verified.** The registry asserts `CC BY-NC-SA 4.0`. ECB's
own copyright policy grants **free use subject to conditions**: cite the ECB;
**state modifications explicitly**; give buyers of sold documents a "free of
charge" notice; no framing; authored Working/Occasional Papers need prior written
authorisation. The label asserts a share-alike obligation and a non-commercial
restriction that **do not exist**, and omits two duties that **do**.

**Missing evidence:** 🟡 **no ECB licence documentation exists in the repository.**
The label has no URL, retrieval date or quoted source — it was asserted without
recorded evidence. Phase 53 fetched the ECB page externally; it was never
captured in-repo.

**(b) Data provenance — NOT verified.** Whether the stored rates are actually
ECB-published observations is unresolved (B4). **This correction is about terms,
not provenance, and must not be read as certifying the stored values.**

| Field | Before | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | *"…published under CC BY-NC-SA 4.0. Non-commercial use only, share-alike, attribution required. Commercial use is excluded."* | ECB conditions verbatim + source URL + retrieval date 2026-10-09 + note that stored values may be provider-blended |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use is established; the description was wrong |

`licence_name` is free text; only `licence_knowledge` is schema-constrained. The
change is schema-valid.

**Recommendation:** approve the correction, **but capture the ECB page in-repo
first** — otherwise one unsourced label is swapped for another.

**Exact owner input:** "I approve the B2 correction **[as written / as
amended]**; I also approve **[capturing the ECB page / deferring]**; approved by
**[name]**, **[date]**."

---

## B3 — Binance registry state

**Status: ✅ EVIDENCE VERIFIED · 🔒 OWNER APPROVAL — nothing but a signature**

**Evidence verified:** 8 × `data/oos/raw/*.provenance.txt` state CC BY-NC-SA 4.0
+ Vision Dataset Terms at L46; `phase9/DATA_SOURCE_REVIEW.md` L39 records the
licence as *"Verified"*; publisher terms v1.0 (26 Aug 2026) re-fetched in Phases
52/53/55, unchanged; attribution present in both READMEs.

**Schema:** `LICENSE_KNOWLEDGE = {"VERIFIED","UNVERIFIED","RESTRICTED"}`
(`registry_schema.py` L89). `UNVERIFIED → VERIFIED` is **permitted**.

**Exact before → after** (both BTC/USDT and ETH/USDT):

```
BEFORE  licence_knowledge : "UNVERIFIED"
        licence_name      : null
        licence_note      : "Same provider and same unestablished
                            redistribution terms as BTC/USDT."   [ETH]

AFTER   licence_knowledge : "VERIFIED"
        licence_name      : "CC BY-NC-SA 4.0"
        licence_note      : cites Binance Vision Dataset Terms v1.0 (26 Aug 2026)
                            s3.1 and s4.5; attribution to Binance Vision required
                            on redistribution; derivatives remain CC BY-NC-SA 4.0;
                            commercial use excluded without a separate written
                            enterprise agreement (s3.4)
```

**Why approve:** the registry currently contradicts Phase 9, Phase 10 and eight
sidecars — it is *less* accurate than the repository it governs, and implies
redistribution terms are unestablished when they are not.

**Recommendation:** approve. **Exact owner input:** "I approve the B3 transition
as written; approved by **[name]**, **[date]**."

---

## B4 — ECB provenance

**Status: ⬜ UNMET — blocker remains open**

**Evidence verified:** acquisition URL
`https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD` carries **no
`providers=ecb` pin**; Frankfurter's documented default is to **blend**; stored
raw JSON keys are `amount, base, start_date, end_date, rates` with **no provider
field**; CSV asserts `rate_type = ECB_reference_rate`.

**Consequence:** the stored values are **not confirmed ECB observations**. If
blended, they are modified figures and ECB's explicit modification-disclosure
condition is engaged — a disclosure currently absent from every forex artefact.

**Reproducible plan** (full specification in `phase57/ECB_PROVENANCE_PLAN.md`):
1. Retrieve the Phase 33 acquisition script; confirm the request actually issued.
2. Re-query with `providers=ecb`; compare against stored values.
3. **Exact match** → values are ECB fixings. **Any mismatch** → blended; add
   modification disclosure and relabel.
4. **Not runnable** → remain UNVERIFIED; keep forex blocked.

**Requirements for any new acquisition:** explicit provider pin; preserve
provider attribution; record request URL, retrieval timestamp, endpoint version;
daily rates with ECB business-day conventions and **no gap filling**; SHA-256 per
file; retained raw responses; independent re-retrieval must reproduce.

**Recommendation:** defer — forex is blocked on data quality regardless, so
resolving licensing unblocks nothing.

**Exact owner input:** "Defer B4" **or** "authorise re-acquisition and
comparison".

---

## B5 — Minimum trade count

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL**

**Evidence:** BTC holdout 20 trades / 912 bars, recorded as mechanically
clustered. ETH window 6,744 bars (17,544 warm-up excluded). No ETH trade count.

**Recommended structure** (the number stays open):
- An **absolute floor**, derived from quantities fixed **before** evaluation —
  preferably the reserved window's bar count scaled by a rate-per-bar estimate
  from **BTC development data**, not from the ETH reserved window.
- Paired with a **registered clustering caveat**, since trade count is not a
  count of independent observations.

**Trade-offs:** too high → `INCONCLUSIVE` near-certain (honest for this sample);
too low → noise read as signal. No value is *correct*.

**Exact owner input:** "Minimum trade count = **[N]**, derived as **[method]**;
adequacy rule = **[1/2/3/4]**; below N the verdict is `INCONCLUSIVE`."

---

## B6 — Uncertainty parameters

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL — four parameters**

**Recommended method:** block bootstrap over time-ordered trade blocks. Reported
alongside the Phase 30 per-trade CI **for continuity only**, labelled as resting
on a violated assumption.

**Assumptions:** blocks internally dependent and mutually independent (an
approximation — trade clustering is not characterised); block length must exceed
the dependence scale (unverifiable from the reserved window); enough blocks for a
stable interval (**at risk** — few trades + long blocks → few blocks); weak
stationarity within the window.

**Limitations:** the bootstrap does not fix a small effective sample. A wide
interval is the honest output of limited data. **If too few blocks exist, the
correct response is `INCONCLUSIVE`, not a narrower method.**

| # | Parameter | Value |
|---|---|---|
| 1 | Block length | ⬜ **OPEN — OWNER DECISION REQUIRED** |
| 2 | Iteration count | ⬜ **OPEN — OWNER DECISION REQUIRED** |
| 3 | Basis for block length | ⬜ **OPEN — OWNER DECISION REQUIRED** |
| 4 | Confidence level | ⬜ **OPEN — OWNER DECISION REQUIRED** |

**Constraint:** parameter 3 **must not** use the reserved ETH window. Legitimate:
typical holding horizon; a fixed choice justified in advance; BTC
development-period autocorrelation (2024–2025 only).

---

## B7 — Decision rule

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL — no threshold derived from prior results**

| Verdict | Condition |
|---|---|
| **Promising** | Estimate **and** interval both clear the pre-set bar, sample adequacy met |
| **Inconclusive** | Adequacy not met, **or** interval spans the bar |
| **Against the hypothesis** | Estimate fails the bar with adequate sample |

Three branches, not two: the BTC holdout produced `INCONCLUSIVE`, which a
two-branch rule would misreport as failure.

**Factors accounted for:** **costs** — zero spread biases *in favour*, and a
strategy whose edge is comparable to spread is eliminated by real costs while
appearing viable here; **uncertainty** — the interval governs clearance;
**sample** — clustering and 6,744 bars; **multiple testing** — one registered
comparison, so disclosure substitutes for correction.

**No verdict may assert:** guaranteed profitability, generalisation beyond this
window, live-trading suitability, performance elsewhere.

**Exact owner input:** "Adopt the three-verdict framework; `Promising` requires
**[estimate AND interval clear [bar]]** with adequacy met; confidence
**[level]**."

---

## B8 — Approver

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL — no identity invented**

**Required role:** someone who can accept the **research claim** that BTC
development carries over to ETH, **having read the frozen preregistration**. A
research judgement, not a code fact — which is why it cannot be automated or
inferred from repository ownership.

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — **not** a tuning opportunity |
| `approver` | ⬜ **OPEN — OWNER DECISION REQUIRED** |
| `date` | ⬜ **OPEN — OWNER DECISION REQUIRED** |

**Exact owner input:** "The authorized cross-asset approver is **[name/role]**,
dated **[date]**, having read the frozen preregistration."

---

## B9 — Option A

**Status: 🟡 RECOMMENDATION · 🔒 OWNER APPROVAL — confirmation open**

**Recommendation:** Option A — a single preregistered ETH evaluation, executable
today with no code change.

**Why segmentation is not train/test generalisation here:** the strategy has
**no fitted parameters**. `walkforward.py` exposes `config_hash`, which
*records* a configuration rather than deriving one, and the README excludes
optimisation frameworks. Walk-forward's warrant is fit-on-train /
test-on-validation; with no fitting procedure **there is nothing to generalise**.
Segmenting yields *segmented out-of-sample evaluation* — a real but strictly
smaller claim. Calling it "walk-forward generalisation" would imply a guarantee
never tested and never possible.

| | Option A | Option B |
|---|---|---|
| Code change | **None** | Modifies the integrity-checking layer |
| Frozen BTC risk | None | Introduces change into validation |
| Claim supported | Transfer, one window | Transfer, across segments |
| Claim **not** supported | Robustness across regimes | Generalisation of a fitted model — none exists |
| Post-hoc risk | Low | **Higher** — segment selection |
| Irreversibility | Consumed once | Consumed once, more ways to waste it |

**Option B remains correct long-term**, on separate data, as its own phase.

**Exact owner input:** "Confirm Option A" **or** "direct Option B (scope and
phase)".

---

## B10 — Preregistration freeze: 12 prerequisites

| # | Prerequisite | Status |
|---|---|---|
| 1 | B5 minimum trade count + adequacy rule | ⬜ UNMET |
| 2 | B6 four parameters | ⬜ UNMET |
| 3 | B7 decision rule and bar | ⬜ UNMET |
| 4 | B8 cross-asset approver and date | ⬜ UNMET |
| 5 | `config_hash` recorded | ⬜ UNMET |
| 6 | `costs_hash` recorded | ⬜ UNMET |
| 7 | `dataset_fingerprint` recorded | ⬜ UNMET |
| 8 | Window and warm-up split confirmed | ✅ **EVIDENCE VERIFIED** — 17,544 / 6,744, index 17544; matches reservation |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | ⬜ UNMET — blocked on #4 |
| 10 | `assert_clean_working_tree()` passes | ⬜ UNMET — tree intentionally dirty |
| 11 | Reservation updated with the preregistration ID | ⬜ UNMET |
| 12 | B11 authorisation obtained | ⬜ UNMET |

**Verified complete: 1 of 12.** Items 5–7 and 11 exist as *concepts* in the
draft; a draft describing a hash is not a recorded hash.

---

## B11 — Evaluation authorisation: 9 conditions

**STATUS: CLOSED. NOT GRANTED.**

| # | Condition | Status |
|---|---|---|
| 1 | Preregistration frozen with an assigned ID | ⬜ UNMET |
| 2 | B5–B8 closed and recorded | ⬜ UNMET |
| 3 | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | ⬜ UNMET |
| 4 | `CrossAssetAuthorization` complete and validated | ⬜ UNMET |
| 5 | Reservation carries the preregistration ID | ⬜ UNMET |
| 6 | `assert_clean_working_tree()` passes | ⬜ UNMET |
| 7 | B1–B4 resolved or explicitly waived | ⬜ UNMET |
| 8 | Named evaluator and date | ⬜ UNMET |
| 9 | Explicit one-evaluation authorisation, consumed **immediately after the run and before any result is read** | ⬜ UNMET |

**Verified complete: 0 of 9.** **Freezing does not authorise running.**

---

## Decision order

```
B1 B2 B3 B4  ─┐
B5 trade count ┼─► B10 FREEZE ─► B8 record ─► B11 AUTHORISE ─► EVALUATE
B6 parameters  │
B7 decision    ┘
```

B5, B6 and B7 must close **before** the freeze: each is a number that must not
depend on a result not yet in existence.