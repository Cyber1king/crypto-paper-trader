# Phase 55 — Owner Decision Gate

**Date:** 2026-10-09
**Purpose:** a decision-ready table for the five evaluation gates.

**No threshold is proposed, implied or calibrated anywhere in this document.**
No performance figure from the reserved window appears, because none has been
computed. Every numeric field is marked `OPEN — OWNER DECISION REQUIRED`.

---

## Gate summary

| Gate | Subject | Status | Blocking? |
|---|---|---|---|
| **B5** | Minimum trade count | **OPEN** | **Yes** |
| **B6** | Uncertainty method and parameters | Method settled; **parameters OPEN** | **Yes** |
| **B7** | Result interpretation and decision rule | **OPEN** | **Yes** |
| **B8** | Authorized cross-asset approver | **OPEN** | **Yes** |
| **B11** | Explicit evaluation authorization | **OPEN** | **Yes** |

All five require a human. None can be resolved by analysis of existing records.

---

## B5 — Minimum trade count

**Current status.** `OPEN — OWNER DECISION REQUIRED`. No value set.

**Evidence available.**

| Fact | Source |
|---|---|
| BTC holdout: **20 trades** from 912 bars | `phase30/RESULTS_holdout.json` |
| Trades are **mechanically clustered, not independent** | Phase 30 recorded statement |
| Holdout verdict `INCONCLUSIVE` | Phase 30 |
| ETH evaluation window: **6,744 bars**; warm-up 17,544; start index 17,544 | reservation entry |
| Any ETH trade count | **Does not exist and was not computed** |

**Options.**

| Option | Definition | Consequence |
|---|---|---|
| 1 | No minimum; report whatever trades occur | Any result is interpretable, however thin. Highest false-signal risk |
| 2 | Absolute floor at a count you choose | Simple; ignores clustering |
| 3 | **Floor plus a registered clustering caveat** (recommended framing) | Count floor gates the obvious case; the caveat prevents over-reading the remainder |
| 4 | No count floor; require the interval to determine adequacy | Puts all weight on the bootstrap; most conservative |

**Risks.** Too high ⇒ `INCONCLUSIVE` almost certainly. Too low ⇒ noise read as
signal. **The value cannot be derived from data** — it expresses your tolerance
for an underpowered study. Choosing it *after* seeing the ETH trade count would
make it outcome-dependent, which is precisely what the protocol exists to
prevent.

**Exact decision required.**
> "Set the minimum trade count to **[value]**, with **[option 2/3/4]** as the
> adequacy rule. Below this, the verdict is `INCONCLUSIVE` regardless of sign."

---

## B6 — Uncertainty method and parameters

**Current status.** Method **proposed and settled**; block length and iteration
count **OPEN — OWNER DECISION REQUIRED**.

**Evidence available.** Phase 30 used a **per-trade 95% CI** of the mean,
recorded as optimistic given clustering. The block bootstrap respects serial
dependence; the per-trade interval does not.

**Method proposal (no approval needed beyond the parameters).** Primary =
**block bootstrap over time-ordered blocks**. Also reported = per-trade 95% CI,
retained **for continuity with Phase 30 only**.

**Options for block length.**

| Option | Definition | Consequence |
|---|---|---|
| 1 | Tie to the strategy's typical holding horizon | Principled; requires deciding the horizon first |
| 2 | Fixed small number of bars | Simple; arbitrary |
| 3 | Estimate from serial autocorrelation of returns | Data-driven — **discouraged**, because it uses data before the evaluation window, but it is *pre*-evaluation data so it is not leakage; still adds a degree of freedom |

**Risks.** Block length materially changes the interval width. Choosing it after
seeing results is a researcher degree of freedom. Option 3 is defensible only
because it uses **development-period** data (BTC 2024–2025), never the reserved
window — using ETH 2026 to set it would be leakage.

**Exact decision required.**
> "Adopt the block bootstrap as primary. Block length = **[value]**, iterations =
> **[value]**. Block length derived from **[holding horizon / fixed choice /
> BTC development-period autocorrelation]**."

---

## B7 — Result interpretation and decision rule

**Current status.** `OPEN — OWNER DECISION REQUIRED`. Three-branch structure
proposed; the threshold is not set.

**Evidence available.** No profitability threshold has ever been established.
BTC 2024–2025 and the BTC holdout were both non-distinguishable from zero.

**Options.**

| Option | Rule | Consequence |
|---|---|---|
| 1 | **Three-branch**: `SUPPORTED` / `NOT SUPPORTED` / `INCONCLUSIVE` (recommended) | `INCONCLUSIVE` is preserved as a legitimate outcome |
| 2 | Two-branch: pass / fail | Would force the BTC holdout's actual `INCONCLUSIVE` into "fail", destroying the distinction |
| 3 | Continuous reporting with no verdict | Maximum honesty, minimum interpretability |

**The bar itself — options.**

| Option | Definition | Consequence |
|---|---|---|
| a | Point estimate alone clears the bar | Simplest; ignores uncertainty |
| b | **Point estimate AND interval both clear the bar** (recommended) | Strictest; conservative |
| c | Interval lower bound alone | Ignores point estimate |
| d | A pre-specified economic floor (e.g. minimum return after costs) | Requires choosing a number |

**Rationale for three branches.** The BTC holdout produced `INCONCLUSIVE` with
20 trades. A two-branch rule would classify it as a failure, which misrepresents
the evidence. Under the clustered 6,744-bar ETH sample, `INCONCLUSIVE` is a
*likely* outcome; a rule that cannot express it will report a false certainty.

**Risks.** A strict rule makes `INCONCLUSIVE` near-certain, which some owners
find unsatisfying. That is the honest reading of this evidence base, not a
defect to engineer around.

**Exact decision required.**
> "Adopt **[1/2/3]**-branch rule with **[a/b/c/d]** as the `SUPPORTED`
> condition. Set the bar to **[value]**. Stopping rules fixed as: one
> evaluation, consume before interpreting, no threshold substitution, no variant
> rescue, publish failures."

---

## B8 — Authorized cross-asset approver

**Current status.** `OPEN — OWNER DECISION REQUIRED`. No approver named.

**Evidence available.**

| Fact | Source |
|---|---|
| `StrategyConfig.asset` is **only a label**; the engine never checked it | `researchguard.py` L13–15 |
| Frozen config declares `asset="BTC/USDT"` | `strategy.py` / `walkforward.baseline_config()` |
| `CrossAssetAuthorization` **exists** with `config_asset`, `dataset_instrument`, `justification` | `researchguard.py` L122 |
| `from_record()` **rejects** an incomplete record | `researchguard.py` L147–162 |
| No cross-asset authorization exists for ETH | registry `research_note` |

**The record that will be created.**

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — **not** a tuning opportunity |
| `approver` | **`OPEN — OWNER DECISION REQUIRED`** |
| `date` | **`OPEN — OWNER DECISION REQUIRED`** |

**Options.**

| Option | Description |
|---|---|
| 1 | A named individual |
| 2 | A named role (e.g. repository owner) |
| 3 | Deferred until B5–B7 are closed |

**Risks.** This is the decision that most requires a person. It asserts that
BTC development carries over to ETH — a **research claim, not a code fact**.
Naming an approver who has not read the preregistration defeats the purpose.

There is no ordering hazard: the guard refuses to run without a complete
authorization record, so this cannot be skipped.

**Exact decision required.**
> "Name **[individual/role]** as the authorized cross-asset approver, on
> **[date]**, having read the frozen preregistration."

---

## B11 — Explicit evaluation authorization

**Current status.** `OPEN — OWNER DECISION REQUIRED`. No authorization exists.

**Evidence available.**

| Fact | Source |
|---|---|
| Reservation `ETH-2026-RESERVATION`: `RESERVED` / `used: false` / `preregistration_id: null` | registry |
| Its own note: *"NOT protected against evaluation until a preregistration is frozen and the guard is exercised"* | reservation |
| `run_backtest` never consumes; single-use is a protocol obligation | `backtest.py` L180 |
| Consumption is now duplicate-safe (Phase 55 F1 fix) | `researchguard.py` |
| The guard refuses a consumed window | `assert_evaluation_permitted` |

**Options.**

| Option | Description |
|---|---|
| 1 | Authorize once, now — **not recommended**, since B5–B8 are open |
| 2 | **Authorize conditionally**, after B5–B8 close and the preregistration freezes (recommended) |
| 3 | Withhold entirely until governance items B1–B4 settle |

**Risks.** The dangerous moment is not the first run — it is the moment after a
disappointing result, when re-running with a variant becomes tempting. Anything
that leaves the window evaluable more than once is a live invitation to that.
`RESERVED` does not prevent it; only protocol discipline does.

**Exact decision required.**
> "I authorize exactly one evaluation of the reserved ETH window, under
> preregistration **[id]**, to be executed at **[time]** and consumed
> immediately after the run and before any result is read. **[Approver name,
> date.]**"

---

## Dependency order

```
B5  minimum trade count ─┐
B6  block parameters ────┼──► preregistration freeze ──► B8 approver ──► B11 authorize ──► EVALUATE
B7  decision rule ───────┘                                    │
                                                             └──► cross-asset record
```

**B5, B6 and B7 must all close before the freeze**, because each is a number
whose value must not depend on a result that does not yet exist. B11 is last and
must be separate — freezing does not authorise running.

**Nothing in this document authorises an evaluation.**