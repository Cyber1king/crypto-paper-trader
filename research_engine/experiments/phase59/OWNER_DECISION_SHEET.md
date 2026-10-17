# Phase 59 — Owner Decision Sheet (B1–B9)

**Date:** 2026-10-09

> **Nothing selected. Nothing approved. No threshold invented. No identity
> assigned.** Every recommendation is a proposal awaiting the owner.

| Label | Meaning |
|---|---|
| ✅ **EVIDENCE VERIFIED** | Checked against the repository in this phase |
| 🟡 **RECOMMENDATION** | Proposal exists; owner has not decided |
| ⬜ **UNMET** | No decision or artefact exists |
| 🔒 **OWNER APPROVAL** | Requires a signature — **none exists** |

---

## B1 — Python package licence

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL**

**Evidence verified.** Root `package.json` declares `"license": "MIT"` for npm
package `"workspace"`. `pnpm-workspace.yaml` scopes it to `artifacts/*`, `lib/*`,
`lib/integrations/*`, `scripts`. **`research_engine` is not in that workspace.**
`research_engine/pyproject.toml` has **no** `license` field or classifier. **No
`LICENSE` file exists anywhere.** No SPDX headers.

**Scope:** `crypto-paper-lab` is a separate distributable; the root MIT does not
reach it. It is currently **unlicensed — all rights reserved by default**.

| Option | Scope | Consequence | Data |
|---|---|---|---|
| **A. No licence** | No copying, modification or redistribution | Blocks all reuse; safe default, likely unintentional | Unaffected |
| **B. MIT** | Any use incl. commercial; notice on redistribution; no patent grant | Consistent with JS tooling; widest reuse | Unaffected |
| **C. Apache-2.0** | As MIT + patent grant + NOTICE obligation | Adds patent clarity and a NOTICE file | Unaffected |
| **D. BSD-3-Clause** | As MIT + no-endorsement clause | Common for research code | Unaffected |
| **E. CC BY-NC-SA 4.0** | Non-commercial; **share-alike propagates** | Any derived work becomes non-commercial | Aligns code with data |

**Recommendation:** none — intended reuse is an owner preference. If consistency
with the JS tooling is the priority, **B**. Note E's share-alike compounds onto
every derived work.

**Exact input:** "I select option **[A/B/C/D/E]** for `crypto-paper-lab`,
effective **[date]**, approved by **[name]**" + copyright holder for B/C/D/E.

---

## B2 — ECB terms correction

**Status: 🟡 RECOMMENDATION · 🔒 OWNER APPROVAL — blocked on missing evidence**

**(a) Source terms — verified.** The registry asserts `CC BY-NC-SA 4.0`. ECB's
own policy grants **free use subject to conditions**: cite the ECB; **state
modifications explicitly**; give buyers of sold documents a "free of charge"
notice; no framing; authored Working/Occasional Papers need prior written
authorisation. The label asserts a share-alike obligation and an NC restriction
that **do not exist**, and omits two duties that **do**.

**Missing evidence:** 🟡 **no ECB licence documentation exists in the
repository.** The label has no URL, retrieval date or quoted source. Phase 53
fetched the page externally; it was never captured in-repo.

**(b) Provenance — NOT verified.** Whether the stored rates are ECB-published
observations is unresolved (B4). **This correction concerns terms, not
provenance, and must not be read as certifying the stored values.**

| Field | Before | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | *"…published under CC BY-NC-SA 4.0. Non-commercial use only, share-alike, attribution required. Commercial use is excluded."* | ECB conditions verbatim + URL + retrieval date 2026-09-09/10-09 + note that stored values may be provider-blended |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use is established; the description was wrong |

`licence_name` is free text; only `licence_knowledge` is schema-constrained.

**Recommendation:** approve, but **capture the ECB page in-repo first**.

**Exact input:** "I approve the B2 correction **[as written / as amended]**;
I also approve **[capturing the page / deferring]**; approved by **[name]**,
**[date]**."

---

## B3 — Binance registry status

**Status: ✅ EVIDENCE VERIFIED · 🔒 OWNER APPROVAL — signature only**

**Evidence verified.** 8 × `data/oos/raw/*.provenance.txt` state CC BY-NC-SA 4.0
+ Vision Dataset Terms at L46. `phase9/DATA_SOURCE_REVIEW.md` L39 records the
licence as *"Verified"*. Publisher terms v1.0 (26 Aug 2026) re-fetched in Phases
52/53/55, unchanged. Attribution present in both READMEs.

**Schema:** `LICENSE_KNOWLEDGE = {"VERIFIED","UNVERIFIED","RESTRICTED"}`
(`registry_schema.py` L89). `UNVERIFIED → VERIFIED` is **permitted**.

**Exact before → after** (BTC/USDT and ETH/USDT):

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
sidecars — less accurate than the repository it governs.

**Recommendation:** approve. **Exact input:** "I approve the B3 transition as
written; approved by **[name]**, **[date]**."

---

## B4 — ECB provenance

**Status: ⬜ UNMET — blocker stays open**

**Evidence verified.** Acquisition URL
`https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD` carries **no
`providers=ecb` pin**; Frankfurter's documented default is to **blend**; stored
raw JSON has **no provider field**; CSV asserts `rate_type = ECB_reference_rate`.

**Consequence:** the stored values are **not confirmed ECB observations**. If
blended, they are modified figures and ECB's explicit modification-disclosure
condition is engaged — a disclosure absent from every forex artefact.

**Reproducible plan:**
1. Retrieve the Phase 33 acquisition script; confirm the request actually issued.
2. Re-query with `providers=ecb`; compare against stored values.
3. **Exact match** → ECB fixings. **Any mismatch** → blended; add disclosure and relabel.
4. **Not runnable** → remain UNVERIFIED; keep forex blocked.

**New-acquisition requirements:** explicit provider pin; preserve provider
attribution; record request URL, retrieval timestamp, endpoint version; daily
rates with ECB business-day conventions and **no gap filling**; SHA-256 per file;
retained raw responses; independent re-retrieval must reproduce.

**Recommendation:** defer — forex is blocked on data quality regardless.

**Exact input:** "Defer B4" **or** "authorise re-acquisition and comparison".

---

## B5 — Minimum trade count

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL**

**Evidence.** BTC holdout 20 trades / 912 bars, recorded as mechanically
clustered. ETH window 6,744 bars (17,544 warm-up excluded). No ETH count exists.

**Recommended structure** (number stays open): an **absolute floor** derived from
quantities fixed **before** evaluation — preferably the reserved window's bar
count scaled by a rate-per-bar estimate from **BTC development data**, never the
ETH reserved window — paired with a **registered clustering caveat**.

**Trade-offs:** too high → `INCONCLUSIVE` near-certain (honest here); too low →
noise read as signal. No value is *correct*.

**Exact input:** "Minimum trade count = **[N]**, derived as **[method]**;
adequacy rule = **[1/2/3/4]**; below N the verdict is `INCONCLUSIVE`."

---

## B6 — Uncertainty parameters

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL — four parameters**

**Recommended method:** block bootstrap over time-ordered trade blocks, reported
alongside the Phase 30 per-trade CI **for continuity only** (labelled as resting
on a violated assumption).

**Assumptions:** blocks internally dependent and mutually independent (an
approximation — clustering is not characterised); block length must exceed the
dependence scale (unverifiable from the reserved window); enough blocks for a
stable interval (**at risk**); weak stationarity within the window.

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
holding horizon; a fixed choice justified in advance; BTC development-period
autocorrelation (2024–2025 only).

---

## B7 — Result interpretation

**Status: ⬜ UNMET · 🔒 OWNER APPROVAL — no threshold derived from prior results**

| Verdict | Condition |
|---|---|
| **Promising** | Estimate **and** interval both clear the bar, sample adequacy met |
| **Inconclusive** | Adequacy not met, **or** interval spans the bar |
| **Against the hypothesis** | Estimate fails the bar with adequate sample |

Three branches: the BTC holdout produced `INCONCLUSIVE`, which a two-branch rule
would misreport as failure.

**Factors:** **costs** — zero spread biases *in favour*, and a strategy whose
edge is comparable to spread is eliminated by real costs while appearing viable
here; **uncertainty** — the interval governs clearance; **sample** — clustering
and 6,744 bars; **multiple testing** — one registered comparison, so disclosure
substitutes for correction.

**No verdict may assert:** guaranteed profitability, generalisation beyond this
window, live-trading suitability, performance elsewhere.

**Exact input:** "Adopt the three-verdict framework; `Promising` requires
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

**Exact input:** "The authorized cross-asset approver is **[name/role]**,
dated **[date]**, having read the frozen preregistration."

---

## B9 — Option A

**Status: 🟡 RECOMMENDATION · 🔒 OWNER APPROVAL — confirmation open**

**Recommendation:** Option A — a single preregistered ETH evaluation, executable
today with no code change.

**Why segmentation is not train/test generalisation:** the strategy has **no
fitted parameters**. `walkforward.py` exposes `config_hash`, which *records* a
configuration rather than deriving one; the README excludes optimisation
frameworks. Walk-forward's warrant is fit-on-train / test-on-validation — with
no fitting procedure **there is nothing to generalise**. Segmenting yields
*segmented out-of-sample evaluation*: real, but strictly smaller. Calling it
"walk-forward generalisation" would imply a guarantee never tested and never
possible.

| | Option A | Option B |
|---|---|---|
| Code change | **None** | Modifies the integrity-checking layer |
| Frozen BTC risk | None | Changes validation |
| Claim supported | Transfer, one window | Transfer, across segments |
| Claim **not** supported | Robustness across regimes | Generalisation of a fitted model — none exists |
| Post-hoc risk | Low | **Higher** — segment selection |
| Irreversibility | Consumed once | Consumed once, more ways to waste it |

**Option B remains correct long-term**, on separate data, as its own phase.

**Exact input:** "Confirm Option A" **or** "direct Option B (scope and phase)".