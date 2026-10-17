# Phase 56 — Owner Decision Register

**Date:** 2026-10-09
**Covers:** Part 5 — B5 through B11.

**Every item is OPEN. No recommendation has been converted into an approval. No
threshold has been chosen to improve an apparent result.**

---

## B5 — Minimum trade count

**Status:** `OPEN — OWNER DECISION REQUIRED`
**Evidence:** BTC holdout produced **20 trades from 912 bars**, recorded as
mechanically clustered. ETH window is **6,744 bars**. No ETH trade count exists
and none was computed.

**Options**

| # | Approach | Advantage | Disadvantage |
|---|---|---|---|
| 1 | No minimum | Never blocks a result | Any outcome interpretable, however thin; highest false-signal risk |
| 2 | Absolute floor at a chosen count | Simple, explicit | Ignores clustering entirely |
| 3 | **Floor + registered clustering caveat** | Gates the obvious case; prevents over-reading the remainder | Still a raw count, which is not an independent-sample count |
| 4 | No count floor; adequacy determined by interval width | Puts all weight on the bootstrap | Most conservative; with a clustered sample the interval may be too wide to ever clear the bar, making `INCONCLUSIVE` near-certain |

**Trade-off summary.** A high floor protects against noise but will probably
return `INCONCLUSIVE`. A low floor risks reading noise as signal. There is no
value that is *correct* — the choice expresses tolerance for an underpowered
study.

**Where a recommendation is justified:** option **3** as the *structure* — a
floor plus an explicit clustering caveat — because it is the only option that
addresses the dependence problem rather than assuming it away. **The number
itself is not recommended**, since it cannot be derived from anything available.

**Exact owner input required**
> "Set the minimum trade count to **[N]**. Adequacy rule: **[1/2/3/4]**.
> Below N the verdict is `INCONCLUSIVE` regardless of sign."

---

## B6 — Uncertainty analysis

**Status:** `OPEN — OWNER DECISION REQUIRED` (parameters)
**Evidence:** Phase 30 used a per-trade 95% CI, recorded as optimistic given
clustering. Trades are serially dependent.

**Approaches compared**

| # | Method | Assumes | Strengths | Limitations |
|---|---|---|---|---|
| 1 | **Block bootstrap** over time-ordered blocks | Blocks are internally dependent; blocks independent | Respects serial dependence; works with few observations; no normality assumption | Sensitive to block length; intervals unstable with very few blocks |
| 2 | Stationary bootstrap | Weak stationarity | Less block-length sensitive | Harder to explain; still needs a parameter |
| 3 | Cluster-robust standard error (by trade cluster) | Clusters independent | Natural if clusters are identifiable | Clusters are **not** formally identified in this system |
| 4 | Per-trade CI (Phase 30's method) | Trades independent | Simple, comparable to prior work | **Known-invalid assumption** — trades are clustered; interval is too narrow |
| 5 | Moving-block bootstrap on returns rather than trades | — | Longer resampling units | Measures return uncertainty, not per-trade expectancy |

**Method assessment:** **1 (block bootstrap over trade blocks)** is the
defensible primary. Method 4 remains reportable **only** for continuity with
Phase 30, clearly labelled as assumption-violating. Method 3 would be preferable
if clusters were formally identified — **they are not**, which is why it is not
recommended.

**Parameters requiring owner approval — none invented here:**

| Parameter | Status |
|---|---|
| Block length | **`OPEN — OWNER DECISION REQUIRED`** |
| Iteration count | **`OPEN — OWNER DECISION REQUIRED`** |
| Basis for block length | **`OPEN — OWNER DECISION REQUIRED`** |
| Confidence level | **`OPEN — OWNER DECISION REQUIRED`** |

**Constraints on the basis.** It **must not** be derived from the reserved ETH
window — that would be leakage. Legitimate bases: the strategy's typical holding
horizon, or a fixed choice justified in advance, or BTC development-period
autocorrelation (2024–2025 only).

**Exact owner input required**
> "Primary method: block bootstrap. Block length **[N]**, iterations **[N]**,
> confidence **[level]**. Basis for block length: **[holding horizon / fixed
> choice / BTC development-period autocorrelation]**."

---

## B7 — Result interpretation

**Status:** `OPEN — OWNER DECISION REQUIRED`
**Evidence:** no profitability threshold has ever been established. BTC 2024–2025
and the holdout were both non-distinguishable from zero.

### Proposed framework — three verdicts

| Verdict | Condition | Meaning |
|---|---|---|
| **Potentially useful** | Point estimate **and** interval both clear the pre-set bar, **and** sample adequacy met | Evidence worth following up — **not** evidence of a profitable strategy |
| **Inconclusive** | Sample adequacy not met, **or** interval spans the bar | The study could not answer the question |
| **Against the hypothesis** | Estimate fails the bar with adequate sample | The registered hypothesis is not supported |

**Three branches, not two.** The BTC holdout produced `INCONCLUSIVE` with 20
trades. A two-branch rule would classify that as failure and misrepresent the
evidence.

**Inputs the rule must account for:**

| Factor | Effect on interpretation |
|---|---|
| Zero-spread costs (§3 of the draft) | Biases **in favour** of the strategy; a "potentially useful" verdict must state that real costs are unmodelled |
| Block-bootstrap interval | Governs whether the bar is cleared |
| Trade clustering | Effective sample below raw count; registered caveat required |
| Single window, single regime | No robustness across sub-periods; limits any generalisation claim |
| Multiple testing | One registered comparison; disclosed degrees of freedom listed in §8 of the draft |
| No fitted parameters | The claim is BTC→ETH **transfer**, not strategy efficacy |

**What no verdict may assert:** guaranteed profitability, generalisation beyond
this window, live-trading suitability, or performance in other assets.

**Exact owner input required**
> "Adopt the three-verdict framework. `Potentially useful` requires
> **[estimate AND interval clear [bar]]**, with sample adequacy met.
> Confidence level **[level]**."

---

## B8 — Cross-asset approver

**Status:** `OPEN — OWNER DECISION REQUIRED` — **no approver invented**
**Evidence:** `StrategyConfig.asset` is **only a label**; the engine never
checked it. `CrossAssetAuthorization` exists and `from_record()` rejects an
incomplete record. No authorization exists for ETH.

**Required record**

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — **not** a tuning opportunity |
| `approver` | **`OPEN — OWNER DECISION REQUIRED`** |
| `date` | **`OPEN — OWNER DECISION REQUIRED`** |

**The authorization role.** Someone who can accept the research claim that BTC
development carries over to ETH, having read the frozen preregistration. This is
a **research judgement, not a code fact** — which is precisely why it cannot be
automated or assumed. Naming an approver who has not read the preregistration
would defeat the control.

**Options:** (1) a named individual; (2) a named role, e.g. repository owner;
(3) defer until B5–B7 close. **No naming is proposed** — inventing an approver
would fabricate an approval.

**No ordering hazard:** the guard refuses to run without a complete record, so
this cannot be skipped.

**Exact owner input required**
> "The authorized cross-asset approver is **[name or role]**, dated **[date]**,
> having read the frozen preregistration."

---

## B9 — Option A confirmation

**Status:** `OPEN — AWAITING OWNER APPROVAL`

**Recommendation: Option A** — a single preregistered ETH evaluation window,
executable today with no code change.

**Rationale, restated accurately.** The strategy has **no fitted parameters**:
`walkforward.py` exposes `config_hash`, which *records* a configuration rather
than deriving one, and the README excludes optimisation frameworks. Walk-forward's
warrant is fit-on-train, test-on-validation. **There is no fitting procedure to
generalise.** Segmenting the reserved window would produce *segmented
out-of-sample evaluation* — a robustness check across sub-periods — which is
real but strictly smaller than what the name implies.

**Describing segmentation as train/test generalisation would misstate the
method.** A preregistration that called it "walk-forward" would imply a
generalisation guarantee that was never tested.

**Comparison**

| | Option A | Option B (segmented) |
|---|---|---|
| Code change | **None** | `validate_dataset_integrity` modification |
| Frozen BTC risk | None | Introduces change into the integrity-checking layer |
| Claim supported | Transfer, one window | Transfer, across segments |
| Claim **not** supported | Robustness across regimes | Generalisation of a fitted model (none exists) |
| Post-hoc risk | Low — one result | **Higher** — segment selection |
| Irreversibility | Consumed once | Consumed once, more ways to waste it |

**Option B remains the right long-term direction**, on separate data, as its own
phase. It is not recommended *for the reserved window*.

**Exact owner input required**
> "Confirm Option A" **or** "direct Option B".

---

## B10 — Preregistration freeze

**Status:** `OPEN — BLOCKED on B5–B8 and B11`
**Not frozen. No ID assigned or reserved.**

### Prerequisites — all required

| # | Prerequisite | State |
|---|---|---|
| 1 | B5 minimum trade count and adequacy rule | **OPEN** |
| 2 | B6 block length, iterations, basis | **OPEN** |
| 3 | B7 decision rule and bar | **OPEN** |
| 4 | B8 cross-asset approver and date | **OPEN** |
| 5 | `config_hash` recorded | At freeze |
| 6 | `costs_hash` recorded | At freeze |
| 7 | `dataset_fingerprint` recorded | At freeze |
| 8 | Evaluation window and warm-up split confirmed against the reservation | Verified already: 17,544 / 6,744, index 17,544 |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | Blocked on B8 |
| 10 | `assert_clean_working_tree()` passes | At freeze |
| 11 | Reservation updated with the preregistration ID | At freeze |
| 12 | **B11 separate authorisation** | **OPEN** |

**Nothing about the freeze requires further analysis.** Once B5–B8 close it is a
mechanical step.

**Exact owner input required**
> "All twelve prerequisites satisfied — authorise freeze and assign ID
> **[id]**." *(An ID is not proposed here; the naming convention is the owner's.)*

---

## B11 — Evaluation authorization

**Status:** `OPEN — EXPLICIT AUTHORISATION CLOSED. NOT GRANTED.**

**This gate stays closed throughout Phase 56.**

### Conditions that must ALL hold before it can be granted

| # | Condition | State |
|---|---|---|
| 1 | Preregistration frozen with an assigned ID | **OPEN** |
| 2 | B5–B8 closed and recorded | **OPEN** |
| 3 | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | **OPEN** |
| 4 | `CrossAssetAuthorization` complete and validated | **OPEN** |
| 5 | Reservation carries the preregistration ID | **OPEN** |
| 6 | `assert_clean_working_tree()` passes | **OPEN** |
| 7 | B1–B4 governance items resolved or explicitly waived | **OPEN** |
| 8 | Named evaluator and date | **OPEN** |
| 9 | Explicit statement that **one** evaluation is authorised, to be consumed **immediately after the run and before any result is read** | **OPEN** |

**Why condition 9 is specific.** The dangerous moment is not the first run — it
is after a disappointing result, when re-running a variant becomes tempting.
`RESERVED` does not prevent that; only a pre-committed consumption protocol
does.

**Exact owner input required**
> "I authorise exactly one evaluation of the reserved ETH window under
> preregistration **[id]**, by **[evaluator]**, on **[date]**, to be consumed
> immediately after the run and before any result is read."

---

## Status table

| ID | Subject | Status | Owner input needed |
|---|---|---|---|
| **B1** | Python package licence | OPEN | Choose A–E |
| **B2** | ECB registry correction | Ready for approval | Sign-off; decide on capturing ECB page |
| **B3** | Binance `licence_knowledge` | Ready for approval | Sign-off |
| **B4** | ECB provenance | OPEN | Defer or authorise re-acquisition |
| **B5** | Minimum trade count | **OPEN** | Number + adequacy rule |
| **B6** | Uncertainty parameters | **OPEN** | Block length, iterations, basis, level |
| **B7** | Decision rule | **OPEN** | Framework + bar |
| **B8** | Cross-asset approver | **OPEN** | Name + date |
| **B9** | Option A | **OPEN** | Confirm or direct B |
| **B10** | Preregistration freeze | **OPEN** | 12 prerequisites, then ID |
| **B11** | Evaluation authorisation | **CLOSED** | 9 conditions, then authorisation |

**B5 → B6 → B7 → B8 → B10 → B11, in that order. Nothing may be evaluated until
every one is closed.**

**No decision in this register has been made, approved or implied.**