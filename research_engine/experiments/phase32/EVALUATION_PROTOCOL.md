# Phase 32 — Proposed AI Evaluation Protocol

**Status: PROPOSAL ONLY. No experiment has been run. No threshold in this
document is an acceptance criterion** — every one is a placeholder to be fixed
by preregistration before any test executes.

This document specifies how a future system could compare four configurations
fairly. It is a design, not a result. **No profitability is claimed or implied.**

---

## 1. The binding constraint: no unused validation data exists

**VERIFIED FACT.** `RESEARCH_CHECKPOINT.md:417-428` records that no genuinely
unused validation data remains: 2026-01…08 was consumed by Phases 10–11,
2024–2025 was used from Phase 5 onward, and no other asset or timeframe was ever
acquired.

**VERIFIED FACT.** Phase 29 acquired 2026-09…10; Phase 30 consumed it. Phase 30
records "This holdout is now spent" (`phase30/SUMMARY.md:343`).

**Consequence.** As of Phase 32 there is **no unseen data anywhere**. Any
evaluation in §3 is impossible until fresh data is acquired. That is why §2
precedes the comparison design rather than following it.

**The spent Phase 30B holdout must never be reused as fresh validation.** It is
the only fully protocol-compliant out-of-sample observation this project has, and
reusing it would destroy the only such evidence while producing a number that
looks authoritative. It may be read as a historical record. It may not be used to
validate, select, tune or compare anything.

---

## 2. Data partition plan

Three partitions, established **before** any analysis, with no overlap:

| Partition | Purpose | Rule |
|---|---|---|
| **Development** | Hypothesis formation, feature engineering, prompt design, debugging | May be inspected freely. Results here are **not** evidence |
| **Validation** | Single-shot confirmation of a **preregistered** hypothesis | Opened **once**. Every use logged |
| **Test (untouched)** | Final confirmation after any change prompted by validation | May never be opened before the project ends |

**The project's own precedent.** `RESEARCH_STATE.json:400` classifies pooling
consumed data to enlarge the sample as **manufactured validation**. Partitioning
exists to prevent exactly that.

**Rules that must be preregistered, not decided later**

| Rule | What must be fixed in advance |
|---|---|
| Partition boundaries | Exact timestamps, with SHA-256 of each partition file |
| Minimum sample size | Derived from the project's own floor: *"fewer than ~50 trades makes any comparison inconclusive"* (`phase9/ACQUISITION_PLAN.md:135-146`) |
| Metric definitions | Exact formulas and basis, fixed before results |
| Decision rule | All branches written out in advance |
| Number of tests | Pre-declared, to control multiple comparisons |
| Abstention policy | What "insufficient evidence" means operationally |

---

## 3. The four configurations

Per the mission. Each is evaluated **identically**: same data partitions, same
costs, same warm-up, same engine, same evaluation windows.

| ID | Configuration | Purpose |
|---|---|---|
| **C0** | Baseline, no AI | Control. Reproduces the frozen engine |
| **C1** | Baseline + news/event filter | Does *any* external evidence add value? |
| **C2** | Baseline + one AI provider | Per-provider attribution |
| **C3** | Combined multi-AI analysis | Does combination beat single providers? |

**Execution rule — non-negotiable.** The AI layer may influence entries **only**
through `should_enter` on the existing `ExecutionPolicy` seam
(`execution.py:20-26`). It may not alter the engine, costs, sizing or windows.
Using C1–C3 in the *same* run as C0 would make attribution impossible; each
configuration is a **separate** run over identical inputs.

---

## 4. Leakage controls

The repository already provides most of this and it must be reused, not
reinvented. Each control below is **VERIFIED FACT** with its existing location.

| # | Leakage risk | Existing control | Must be reused because |
|---|---|---|---|
| L1 | Training data overlapping evaluation | `WindowSpec.__post_init__` rejects `train_end >= eval_start` (`walkforward.py:169-191`) | Already proven in Phase 13 |
| L2 | Overlapping evaluation windows | `resolve_windows` rejects overlapping evaluations (`:333-410`) | Prevents double-counting |
| L3 | Premature or stray trades | `run_window` rejects entries before and exits after the boundary (`:513-535`) | Window integrity |
| L4 | State carried between windows | `assert_no_state_carry` compares trade **object identity** (`:555-582`) | Catches reuse a value check would miss |
| L5 | Indicator warm-up approximation | `WARMUP_RULE = "full_preceding_series"` (`:75`) | Whole preceding series, no fixed prefix |
| L6 | Boundary force-closes discarded | `BOUNDARY_POLICY = "retain_boundary_force_closes"` (`:78`) | Prevents flattering the result |
| L7 | Config mutated mid-run | Config hash re-checked (`:632-636`) | Stops silent parameter change |
| L8 | Costs mutated mid-run | Cost hash re-checked (`:638-642`) | Stops silent cost change |
| L9 | Dataset changed mid-run | `(len, first_ts, last_ts)` fingerprint (`:644-648`) | Stops silent data change |
| L10 | Dataset tampering | `validate_dataset_integrity` verifies SHA-256, count, spacing (`:257-316`) | Proven in Phase 29C |
| L11 | Dirty working tree | `assert_clean_working_tree` (`:660-687`) | Reproducibility |
| L12 | Calendar-year reset | `yearly.py` banned (`:25-26`) | Resets warm-up; not walk-forward |

**VERIFIED FACT — total: eleven guards, all raising rather than warning**
(`RESEARCH_CHECKPOINT.md:199-204`).

### New controls required for an evidence-driven system

| # | Risk | Required control |
|---|---|---|
| **L13** | **Future news leaking backwards** | Hard filter `published_at <= decision_time`, enforced in ingestion, not at query time |
| **L14** | **Backfill libraries with false `published_at`** | Cross-check against an independent timestamp where possible; exclude the item if it cannot be verified |
| **L15** | **Calendar revised after the fact** | Store `revision`; a revision must invalidate derived claims and force recomputation from raw |
| **L16** | **Prompt/provider drift** | Pin model id and prompt hash; log both; re-run invalidates comparability |
| **L17** | **Syndication inflating corroboration** | Deduplicate on content hash; one wire story = one event |
| **L18** | **Provider training on the eval window** | **[VERIFY]** each provider's training-use terms before use; if material, restrict to providers with verified terms or treat as a documented limitation |
| **L19** | **Selection across many AI configurations** | Pre-declare the number of comparisons; treat the family as one test |
| **L20** | **Caching masking a failure** | Cache hits labelled; failure counts reported separately |

**L13 is the single most important new control.** Candle-level leakage is already
handled by the seam (`execution.py:46-49`); evidence-level leakage is **not**, and
must be enforced at ingestion.

### Survivorship and data-selection bias

**VERIFIED FACT — already documented as unclosed.** The 2024–2025 dataset has no
documented provenance; construction continuity with 2026 is not established
(`phase10/SUMMARY.md:150-153`), and `RESEARCH_CHECKPOINT.md:391` keeps this as an
open gap.

Controls: new partitions must come from a source with **documented provenance
and a stable manifest**, as Phase 29 established for Binance Vision. Existing
partitions may not be described as provenance-verified.

**Survivorship.** Instruments must be fixed **before** the study, with a
preregistered rule for assets that cease to trade. Selecting only pairs that
survived to the end of the window would bias any crypto-to-forex comparison.

---

## 5. Metrics

### 5.1 Financial (existing implementations, reused)

| Metric | Source | Note |
|---|---|---|
| Net P&L after costs | `stats.performance()` | `stats.py:131-151` |
| Gross P&L before costs | `models.py:109-128` | Needed because costs did not create the Phase 30B loss |
| Total friction | `stats.py:7-27` | The correct gross→net bridge |
| Win rate, profit factor, average P&L | `stats.py:131-151` | |
| Max drawdown, closed-trade | `stats.py:113-129` | **Basis must be stated** — mark-to-market differs by 12–16% (`phase11/SUMMARY.md:294-301`) |
| Ending balance | `stats.py:150` | |
| Exit-reason counts | `backtest.py:190-192` | |
| Monthly breakdown | `robustness.monthly_breakdown` | Entry-month assignment |

**VERIFIED FACT — required new reporting.** Phase 31 established that
`friction / gross P&L` is meaningless when gross is negative, and that
`stats.performance()` computes `profit_factor` from **net** P&L despite naming
its locals `gross_profit`/`gross_loss` (`stats.py:102-111`). Any future protocol
must report **both bases explicitly**. Not doing so repeats a documented
misreading risk.

### 5.2 Trade count and exposure

| Metric | Status |
|---|---|
| Trade count | Available (`stats.py:132`) |
| Exposure / percent time in market | **Does not exist.** The repository deliberately refuses to fabricate it (`windowstats.py:8-12`). Phase 31 derived 850/864 from recorded timestamps only. A proper exposure metric needs its own preregistered definition |

### 5.3 Uncertainty and prediction quality

**For any probabilistic output**, which no existing component produces:
calibration (predicted vs realised, binned), reliability/discrimination,
resolution (spread of forecasts), and **abstention rate**.

**VERIFIED FACT — do not report a p-value on trades.** The one-position-at-a-time
design means trades are not independent; `RESEARCH_STATE.json:402` records that a
p-value is not defensible, and Phase 14C deliberately reported no p-value
(`phase14/SUMMARY.md:410-413`). Any inference must respect the clustering the
project has already documented.

### 5.4 Incremental benefit against cost, latency and complexity

**Required**, because an AI layer has a running cost the baseline does not.

| Quantity | How measured |
|---|---|
| Incremental net P&L vs C0 | Same partitions, same costs |
| Provider API cost per run | Token counts × verified pricing — **[VERIFY]** pricing before use |
| Latency added per decision | Measured, reported; must not silently delay replay |
| Abstention rate | Count and reason |
| Additional failure modes | Timeouts, 429s, schema failures, cost overruns |
| Complexity cost | New code, new data dependencies, new failure surface |

**Principle to preregister.** A configuration that improves net P&L by less than
its added monetary cost and operational risk should be rejected — but the
comparison basis must be fixed in advance, not chosen after seeing numbers.

### 5.5 Performance across market conditions

**VERIFIED FACT — the regime question is open.** The 2024–2025 → 2026 sign flip
with an unchanged strategy is unresolved (`phase11/SUMMARY.md:389-390`), and
Phase 15 lists "why the 2024–2025 and 2026 signs differ" as **not established**.

Any condition segmentation must use **pre-declared, computable-from-candles-only**
rules, never rules fitted to outcomes. Phase 14C's warning applies directly:
*"scanning even a dozen features will surface at least one apparently
interesting pattern purely by chance"* (`phase14/SUMMARY.md:417-423`).

---

## 6. Multiple comparisons and overfitting

**VERIFIED FACT — the project has already been bitten.** Phases 5–7 searched 12+
configurations on 2024–2025 and selected A2 from that search
(`RESEARCH_STATE.json:169`, `:289`), permanently contaminating A2 for every later
overlapping window.

Adding 3 AI configurations × multiple providers × prompt variants × thresholds
would multiply an already-too-large search space.

**Required controls**

| # | Control |
|---|---|
| M1 | Preregister the **number** of comparisons before running |
| M2 | Treat the whole family as **one** test; report it as such |
| M3 | Preregister the decision rule with **all branches written out** in advance |
| M4 | No configuration may be selected on validation data |
| M5 | A change prompted by validation results requires a fresh untouched test partition |
| M6 | Report every configuration, including unpromising ones. No cherry-picking |
| M7 | Record prompt changes as experiments; each version is a new configuration |

**VERIFIED FACT — existing precedent for a favourable result being reported
symmetrically**: `phase10/OOS_RESULTS.md:126` states "A negative result at this
scale would have been reported the same way." That standard must be maintained.

---

## 7. Preregistration requirement

**No future test may begin without a preregistration document** modelled on
`experiments/phase29/PREREGISTRATION.md` (662 lines, SHA-256
`b06f36e2…17cc`), which was written and frozen **before** any holdout backtest
and which declared INCONCLUSIVE before a single number existed.

A future preregistration must fix, at minimum:

| # | Item |
|---|---|
| P1 | Data partitions with timestamps and SHA-256 of each |
| P2 | Exact configuration, costs, balance, risk fraction, warm-up, evaluation start |
| P3 | Exact metric definitions, **including PF basis and drawdown basis** |
| P4 | The exact single invocation, per configuration |
| P5 | Decision rule with every branch pre-written |
| P6 | Interpretation rules, including the INCONCLUSIVE declaration |
| P7 | Ablations to be reported |
| P8 | Mandatory report contents |
| P9 | The **absence of unused validation data**, and the plan to obtain it |
| P10 | Provider model ids, prompt hashes, pricing assumptions — all **[VERIFY]** items resolved |

**Acceptance thresholds are deliberately absent from this document.** Inventing
them now, before any data or result exists, would encode a preference. They must
be chosen and frozen in a preregistration, informed by the effect sizes the
existing reports already document as unresolved.

---

## 8. Reporting requirements

Any future report must contain, at minimum:

1. Dataset path, SHA-256, row count, UTC range, re-verified at run time.
2. Exact Git commit and working-tree status.
3. Full configuration repr and exact invocation per configuration.
4. Per-trade table: times, side, prices, gross, costs, net, exit reason.
5. **All** pre-specified metrics, including unfavourable ones and undefined-vs-zero distinctions.
6. Exit-reason counts and boundary force-closes.
7. Gross **and** net profit factor, clearly distinguished.
8. Abstention counts and reasons, if any AI component ran.
9. Provider cost, latency and failure counts.
10. An explicit statement of uncertainty and sample limitations beside every aggregate.
11. Confirmation that no parameter was changed after seeing results.
12. An explicit INCONCLUSIVE statement unless a preregistered decision rule says otherwise.

---

## 9. What this protocol does not do

- It does not assert that any AI configuration will outperform the baseline.
- It does not assert that any provider has the capability or pricing assumed.
- It does not set acceptance thresholds.
- It does not use the spent Phase 30B holdout.
- It does not claim the baseline is profitable. It is not: gross P&L was −6.32 on
  the holdout and −133.86 across six walk-forward windows.
- It does not permit reuse of validation data after it has influenced any decision.

**Standing conclusion, unchanged:** no reliable profitability has been
established for this strategy (`RESEARCH_STATE.json:14`). This protocol is
designed to test that conclusion properly, not to assume its reversal.