# Phase 61 — B6: Four Uncertainty Parameters

**Status: `OWNER DECISION REQUIRED` — all four parameters UNSET.**

**Canonical parameter names are preserved verbatim** from the project record
(`phase57/RESEARCH_DECISION_REGISTER.md`, carried through
`phase58/OWNER_DECISION_REGISTER.md`, `phase59/OWNER_DECISION_SHEET.md`,
`phase60/OWNER_DECISION_REGISTER.md`):

1. **Block length**
2. **Iteration count**
3. **Basis for block length**
4. **Confidence level**

No values are set, modified or implied here.

---

## 1. Proposed methodology (already in the project record)

**[R] Block bootstrap over time-ordered trade blocks** as primary, with the
Phase 30 **per-trade 95% CI** reported alongside **for continuity only** and
explicitly labelled as resting on a violated independence assumption.

**[V] Supporting rationale already recorded:** Phase 30's per-trade CI was
documented as optimistic given clustering; the block bootstrap respects serial
dependence; cluster-robust standard errors were considered but **clusters are
not formally identified** in this system.

---

## 2. The four parameters

### 2.1 Block length

**Definition:** the number of consecutive trades treated as one resampling unit.

**Purpose:** absorb serial dependence between trades. A block must be at least as
long as the dependence scale, or the bootstrap understates uncertainty.

**Candidate methodologies already supported by project documentation:**

| Candidate | Source | Note |
|---|---|---|
| Tie to the strategy's typical holding horizon | `phase55/OWNER_DECISION_GATE.md` B6 option 1 | *"Principled; requires deciding the horizon first"* |
| A fixed number of bars | same, option 2 | *"Simple; arbitrary"* |
| Estimate from serial autocorrelation of returns | same, option 3 | *"discouraged … adds a degree of freedom"* |

**Required inputs/evidence:** the strategy's typical holding horizon (derivable
from BTC development data, **not** from ETH 2026); or an explicit owner
judgement.

**Risk of choosing late:** block length directly controls interval width. Chosen
after seeing results, it becomes a lever that can widen an inconvenient
interval.

**Must be fixed:** at preregistration freeze (B10 #2), before evaluation.

### 2.2 Iteration count

**Definition:** the number of resamples drawn.

**Purpose:** determine Monte-Carlo stability of the interval.

**Candidate range supported by documentation:** none recorded. **[V] No project
document specifies a value or range.** Recorded as **UNRESOLVED** — no range is
invented here.

**Required inputs/evidence:** a general principle — iterations should exceed the
block count by a wide margin — is standard statistical practice but is **not
documented in this repository**, so it is flagged as requiring owner judgement
rather than asserted as a project rule.

**Risk of choosing late:** too few iterations gives an unstable interval that
could flip the verdict on re-computation.

**Must be fixed:** at preregistration freeze.

### 2.3 Basis for block length

**Definition:** the stated justification from which the block length is derived.

**Purpose:** make the derivation auditable and pre-commit it, so the value cannot
be re-derived later to suit the result.

**Permitted bases already documented** (`phase55/OWNER_DECISION_GATE.md` B6,
carried forward):

1. Typical holding horizon
2. A fixed choice justified in advance
3. BTC development-period autocorrelation (**2024–2025 only**)

**Hard constraint, already documented:** the basis **must not** use the reserved
ETH 2026 window. That would be leakage — the parameter would be fitted to the
data it is meant to characterise.

**Risk of choosing late:** the largest of the four. A basis chosen after results
are visible is a researcher degree of freedom.

**Must be fixed:** at preregistration freeze, **earliest** of the four.

### 2.4 Confidence level

**Definition:** the coverage the reported interval targets (e.g. 90%, 95%).

**Purpose:** set how much uncertainty the verdict tolerates.

**Required inputs/evidence:** none recorded in the repository. **UNRESOLVED** —
no value is proposed.

**Interaction that must be considered:** the confidence level and the B7
decision bar are **not independent**. A tighter interval or a wider level
changes whether the same result clears the same bar. Both should be fixed
together, or a bar can be cleared or missed by moving one of them.

**Risk of choosing late:** directly determines whether a result clears the bar.

**Must be fixed:** at preregistration freeze, **jointly with B7**.

---

## 3. Assumptions of the block bootstrap — stated plainly

| Assumption | Status |
|---|---|
| Blocks internally dependent, mutually independent | **Approximation.** Trade clustering is not formally characterised in this system |
| Block length exceeds the dependence scale | **Must be chosen to ensure this**, and cannot be verified from the reserved window |
| Enough blocks for a stable interval | **At risk.** Few trades + long blocks → few blocks → unreliable interval |
| Stationarity within the window | Weak; a 2026 stretch is one regime |

**The bootstrap does not fix a small effective sample.** A wide interval is the
honest output of limited data, not a defect of method.

**If too few blocks exist for a stable interval, the correct response is
`INCONCLUSIVE` — not a narrower method chosen afterwards.**

---

## 4. Limitations

- The method assumes a dependence structure that this project has **not**
  quantified. Block length absorbs it empirically rather than modelling it.
- Results are sensitive to parameters 1 and 2 — which is exactly why they must be
  pre-committed.
- The Phase 30 continuity interval rests on a **known-violated** assumption and
  must always be labelled as such.

---

## 5. Fields left unset

| # | Parameter | Value |
|---|---|---|
| 1 | **Block length** | **OPEN — OWNER DECISION REQUIRED** |
| 2 | **Iteration count** | **OPEN — OWNER DECISION REQUIRED** |
| 3 | **Basis for block length** | **OPEN — OWNER DECISION REQUIRED** |
| 4 | **Confidence level** | **OPEN — OWNER DECISION REQUIRED** |

---

## 6. Exact owner decision required

> **"Block bootstrap is the primary uncertainty method. Block length = [N];
> iteration count = [N]; basis for block length = [typical holding horizon /
> fixed choice justified in advance / BTC development-period autocorrelation];
> confidence level = [N]%. The Phase 30 per-trade CI is reported for continuity
> only and labelled as resting on a violated assumption. No parameter may be
> derived from the reserved ETH 2026 window."**

**Not to be done by OpenCode:** setting any value, estimating a range the
repository does not document, or deriving any parameter from ETH 2026 data.