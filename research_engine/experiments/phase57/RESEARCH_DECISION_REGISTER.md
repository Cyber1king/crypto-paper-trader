# Phase 57 — Research Decision Register (B5–B9)

**Date:** 2026-10-09
**Scope:** Step 6 — the research decisions, prepared for owner review.

> **All items are OPEN. No recommendation has been converted into an approval.
> No threshold has been chosen to improve an apparent result. No reserved-period
> figure appears in this document, because none has been computed.**

---

## B5 — Minimum trade count

**Status:** `OPEN — OWNER DECISION REQUIRED`
**Evidence:** BTC holdout produced **20 trades from 912 bars**, recorded as
mechanically clustered. ETH evaluation window is **6,744 bars** (17,544 warm-up
excluded). No ETH trade count exists.

### Recommended decision **structure**

| Element | Recommendation | Rationale |
|---|---|---|
| Use an **absolute floor** | **Yes** | Simple, explicit, auditable |
| Pair it with a **registered clustering caveat** | **Yes** | Trade count is not a count of independent observations; without the caveat the floor is misread as an independence claim |
| Make the floor **derived from bar count** rather than from prior BTC trades | **Yes** | A count derived from the *development* asset risks importing BTC's specific trade frequency as if it were a requirement for ETH |
| Derive it from the **reserved window's bar count** | **Yes** | 6,744 bars is known before evaluation; a rate-per-bar estimate from BTC development data (not the reserved window) gives a defensible order of magnitude |

**Why this structure.** It makes the floor a function of quantities fixed before
evaluation, rather than of anything observed in ETH 2026. It also refuses to
pretend that a trade count carries independence information it does not.

**The number itself is not recommended.** It is a judgement about tolerance for
an underpowered study, and it cannot be derived from anything available.

### Options left open

| Option | Trade-off |
|---|---|
| No minimum | Never blocks; any outcome interpretable; highest false-signal risk |
| Absolute floor only | Simple; ignores clustering |
| **Floor + clustering caveat (recommended structure)** | Gates the obvious case; prevents over-reading the remainder |
| No floor; interval determines adequacy | Most conservative; likely permanent `INCONCLUSIVE` |

### Consequences
- **Too high** ⇒ `INCONCLUSIVE` near-certain. That is an honest reading of a
  6,744-bar clustered sample.
- **Too low** ⇒ noise read as signal.
- There is no value that is *correct*.

### Exact owner input required
> "Minimum trade count = **[N]**, derived as **[method]**. Adequacy rule =
> **[1/2/3/4]**. Below N the verdict is `INCONCLUSIVE` regardless of sign."

---

## B6 — Uncertainty analysis

**Status:** `OPEN — OWNER DECISION REQUIRED` (four parameters)
**Evidence:** Phase 30 used a per-trade 95% CI, recorded as optimistic given
clustering. Trades are serially dependent.

### Methods compared

| # | Method | Assumptions | Strengths | Limitations |
|---|---|---|---|---|
| 1 | **Block bootstrap** over time-ordered trade blocks | Blocks internally dependent; blocks mutually independent | Respects serial dependence; works with few observations; no normality assumption | Block-length sensitive; unstable with very few blocks |
| 2 | Stationary bootstrap | Weak stationarity | Less block-length sensitive | Harder to explain; still parameterised |
| 3 | Cluster-robust SE | Clusters independent | Natural if clusters identifiable | **Clusters are not formally identified in this system** |
| 4 | Per-trade CI (Phase 30's method) | Trades independent | Simple; comparable to prior work | **Assumption known to be violated**; interval too narrow |
| 5 | Moving-block bootstrap on returns | — | Longer resampling units | Measures return uncertainty, not per-trade expectancy |

### Recommended method and its assumptions

**Block bootstrap over trade blocks (method 1)** as primary. Method 4 is
reported **alongside only for continuity with Phase 30**, explicitly labelled as
resting on a violated assumption. Method 3 would be preferable if clusters were
formally identified — **they are not**, which is why it is not recommended.

**Assumptions stated plainly:**

| Assumption | Status |
|---|---|
| Blocks are internally dependent, mutually independent | **Approximation.** Trade clustering is not fully characterised; block length absorbs it empirically |
| Block length exceeds the dependence scale | **Must be chosen to ensure this** — and cannot be verified from the reserved window |
| Enough blocks for a stable interval | **At risk.** With few trades and a long block length, the block count can fall to a handful, making the interval unreliable |
| Stationarity within the window | Weak; a 2026 stretch is one regime |

**Limitations.** The block bootstrap does not fix a small effective sample. A
wide interval is the honest output of limited data, not a defect of method. If
too few blocks exist for a stable interval, **the correct response is
`INCONCLUSIVE`, not a narrower method.**

### Four unresolved parameters — values deliberately left open

| # | Parameter | Status | Constraint |
|---|---|---|---|
| 1 | **Block length** | `OPEN — OWNER DECISION REQUIRED` | **Must not** be derived from the reserved ETH window |
| 2 | **Iteration count** | `OPEN — OWNER DECISION REQUIRED` | Should exceed block count by a wide margin |
| 3 | **Basis for block length** | `OPEN — OWNER DECISION REQUIRED` | Holding horizon / fixed choice justified in advance / BTC development-period autocorrelation (2024–2025 only) |
| 4 | **Confidence level** | `OPEN — OWNER DECISION REQUIRED` | Must be consistent with B7's bar |

**Legitimate bases for parameter 3.** Typical holding horizon; a fixed choice
justified in advance; BTC development-period autocorrelation. **BTC 2024–2025 is
permissible — it is development data, not the reserved window.**

### Exact owner input required
> "Block bootstrap primary. Block length = **[N]**, iterations = **[N]**,
> confidence = **[level]**. Basis = **[holding horizon / fixed choice / BTC
> development-period autocorrelation]**."

---

## B7 — Decision rule

**Status:** `OPEN — OWNER DECISION REQUIRED`
**Evidence:** no profitability threshold has ever been established. BTC 2024–2025
and the holdout were both non-distinguishable from zero. **No threshold is
derived from prior results here.**

### Proposed three-verdict framework

| Verdict | Condition | Interpretation |
|---|---|---|
| **Promising** | Point estimate **and** interval both clear the pre-set bar, **and** sample adequacy met | Worth follow-up. **Not** evidence of a profitable strategy |
| **Inconclusive** | Sample adequacy not met, **or** interval spans the bar | The study could not answer the question |
| **Against the hypothesis** | Estimate fails the bar with an adequate sample | The registered hypothesis is not supported |

**Three branches, not two.** The BTC holdout produced `INCONCLUSIVE` with 20
trades; a two-branch rule would classify that as failure and misrepresent the
evidence.

### Inputs the rule must account for

| Factor | Effect on interpretation |
|---|---|
| **Transaction costs** — zero spread assumed | Biases **in favour** of the strategy. Any "promising" verdict must state that real bid–ask costs are unmodelled. A strategy whose edge is comparable to spread is **eliminated by real costs and would appear viable here** |
| **Uncertainty** — block bootstrap interval | Governs whether the bar is cleared; a wide interval is the honest output of limited data |
| **Sample limitations** — clustering, 6,744 bars | Effective sample below raw trade count; registered caveat mandatory |
| **Multiple testing** — one registered comparison | Disclosed degrees of freedom in §8 of the draft; no correction applied, so **disclosure substitutes for correction** |
| **No fitted parameters** | The claim is BTC→ETH **transfer**, not strategy efficacy |
| **Single window, single regime** | No robustness across sub-periods |

### What no verdict may assert
Guaranteed profitability · generalisation beyond this window · live-trading
suitability · performance in other assets · that "promising" implies a working
strategy.

### No significance level
This is a preregistered single comparison with a pre-set rule, not a hypothesis
test with an α. Stating a p-value would misrepresent the design.

### Exact owner input required
> "Adopt the three-verdict framework. `Promising` requires
> **[estimate AND interval clear [bar]]** with sample adequacy met. Confidence
> level = **[level]**."

---

## B8 — Cross-asset approver

**Status:** `OPEN — OWNER DECISION REQUIRED` — **no approver invented**
**Evidence:** `StrategyConfig.asset` is **only a label**; the engine never
checked it. `CrossAssetAuthorization` exists; `from_record()` rejects an
incomplete record. No authorization exists for ETH.

### The required authorization role

Someone who can accept the **research claim** that BTC development carries over
to ETH, **having read the frozen preregistration**. This is a research
judgement, not a code fact — which is exactly why it cannot be automated,
delegated to an agent, or assumed from repository ownership.

Naming an approver who has not read the preregistration would defeat the control
entirely: the record would exist, but the review it documents would not.

### Required record

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — **not** a tuning opportunity |
| `approver` | **`OPEN — OWNER DECISION REQUIRED`** |
| `date` | **`OPEN — OWNER DECISION REQUIRED`** |

### Options
(1) a named individual · (2) a named role, e.g. repository owner · (3) defer
until B5–B7 close.

**No naming is proposed.** Inventing an approver would fabricate an approval.

### No ordering hazard
The guard refuses to run without a complete record, so this cannot be skipped.

### Exact owner input required
> "The authorized cross-asset approver is **[name or role]**, dated **[date]**,
> having read the frozen preregistration."

---

## B9 — Option A confirmation

**Status:** `OPEN — AWAITING OWNER APPROVAL`
**Recommendation:** Option A — a single preregistered ETH evaluation window,
executable today with no code change.

### Why segmentation is **not** train/test generalisation here

The strategy has **no fitted parameters**. `walkforward.py` exposes
`config_hash`, which *records* a configuration; it does not *derive* one. The
README excludes optimisation frameworks.

Walk-forward's warrant is: **fit on train, test on validation, and thereby
measure generalisation of the fitting procedure.** With no fitting procedure,
**there is nothing to generalise.**

Segmenting the reserved window would produce **segmented out-of-sample
evaluation** — a robustness check across sub-periods. That is a genuine benefit,
but a strictly smaller claim. Describing it as "walk-forward generalisation"
would imply a guarantee that was never tested and never could be.

### Comparison

| | Option A | Option B (segmented) |
|---|---|---|
| Code change | **None** | `validate_dataset_integrity` modification |
| Frozen BTC risk | None | Changes the integrity-checking layer |
| Claim supported | Transfer, one window | Transfer, across segments |
| Claim **not** supported | Robustness across regimes | Generalisation of a fitted model — none exists |
| Post-hoc risk | Low — one result | **Higher** — segment selection |
| Irreversibility | Consumed once | Consumed once, more ways to waste it |

### Why A for the reserved window
Option B does not buy what its name implies, while adding multiplicity risk to
evidence consumed irreversibly. Option A executes today with every safeguard
intact. The cross-asset transfer question is best answered **once**, cleanly.

**Option B remains correct long-term**, on separate data, as its own phase.

### Exact owner input required
> "Confirm Option A" **or** "direct Option B (specify scope and phase)".

---

## Status

| ID | Status | Owner input |
|---|---|---|
| **B5** | OPEN | Number + derivation method + adequacy rule |
| **B6** | OPEN | Four parameters |
| **B7** | OPEN | Framework + bar + confidence level |
| **B8** | OPEN | Approver identity + date |
| **B9** | OPEN | Confirm or direct |

**No decision in this register has been made, approved or implied.**