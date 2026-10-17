# Phase 54 — ETH Evaluation Readiness

**Date:** 2026-10-09
**Reviews:** Phase 53's Option A recommendation (a single preregistered ETH
evaluation) against the actual code.

**Nothing was implemented. No evaluation was run. The reserved window was not
touched.**

---

## 1. Does segmentation provide train/test generalisation here?

**No — and this is the decisive point.**

**[V]** The strategy has **no fitted parameters**. `StrategyConfig` fields
(`lookback=20`, `fast_period=5`, `slow_period=12`, `breakout_buffer`,
`retest_tolerance`, `min_breakout_distance`, `trend_strength_min`,
`breakout_confirm_bars`) are **fixed constants**, defined in `strategy.py` and
frozen in `walkforward.baseline_config()` / `a2_config()`.

**[V]** No optimisation framework exists. `walkforward.py` contains
`resolve_windows`, `run_window`, `assert_no_state_carry` and `config_hash` — but
nothing that estimates parameters from a training slice. `config_hash` *records*
a configuration; it does not *derive* one.

**[V]** `research_engine/README.md` states the project "intentionally avoids …
optimization frameworks".

**Consequence.** Walk-forward's standard warrant is: fit on train, test on
validation, and thereby measure generalisation of the *fitting procedure*. With
no fitting procedure, there is nothing to generalise. Segmenting the reserved
window would produce **segmented out-of-sample evaluation** — a robustness
check across sub-periods — which is a genuine but strictly smaller claim.

Calling it "walk-forward" overstates it. **The preregistration must describe the
method accurately**, or a later reader will infer a generalisation guarantee that
was never tested.

### 1.1 What segmentation does buy, honestly

| Benefit | Real? |
|---|---|
| Evidence the result is not confined to one stretch of 2026 | **Yes** — genuinely useful |
| Regime diversity (trend / range / high / low volatility) | **Yes** |
| More independent observations | **Partly** — trades are mechanically clustered (Phase 30), so counting does not equal independence |
| Train/test generalisation of a fitted model | **No — no model is fitted** |

### 1.2 And what it costs

**[V]** The reserved window is 6,744 evaluation bars. Fragmenting it means each
segment is small.

**[V]** The BTC holdout produced **20 trades from 912 bars**. Comparable-sized
segments would produce very few trades — too few to support inference, before
even accounting for clustering.

**[V]** The reservation is consumed once and cannot be restored. A mis-designed
segmentation spends the evidence permanently, with more degrees of freedom
available to go wrong than a single run.

**[V] Multiplicity.** Evaluating N segments and reporting the best is
selection on outcome. It requires a pre-specified aggregation rule — otherwise
Option B is *more* exposed to post-hoc reasoning than Option A.

---

## 2. Can Option A execute with existing code, without weakening safeguards?

**[V] Yes. Option A requires no code change at all.**

`run_backtest` already accepts a research context:

```python
run_backtest(candles, config, costs, ...,
             research_context: object | None = None)
```

The guard is wired in unconditionally (`backtest.py` L155–181):

```python
_guard_decision = assert_series_permitted(
    candles, research_context=..., registry_file=...,
    evaluation_first=candles[evaluation_start].timestamp if ... else None,
    evaluation_last=..., preregistration_id=...,
    config_asset=..., cross_asset=..., mark_used=False)
```

**[V] Safeguards that are preserved, not weakened:**

| Safeguard | Source | Status |
|---|---|---|
| Series fingerprinting on the candles **actually handed to the engine** | `backtest.py` L142–144 | Active — copying or renaming the file does not evade the guard |
| Evaluation range must be declared | L183–187 — raises if a research context is supplied without `evaluation_start` | Active |
| Fail-closed on missing/malformed registry | `researchguard.py` L19–20 | Active |
| No `skip_guard` flag anywhere | `researchguard.py` L27–28 | Active |
| Cross-asset authorization required when `config_asset` ≠ dataset instrument | `researchguard.py` L122–162 | Active; `from_record()` rejects incomplete records |
| Consumption requires an explicit writable `registry_file` | `test_research_gaps.py` L247–249 | Active — refuses without one |
| Every attempt recorded, including refusals | `researchguard.py` L29–30 | Active |

**[V]** No safeguard is removed, relaxed or bypassed by choosing Option A. Option
A is simply the existing, already-guarded path.

**[V]** By contrast, Option B requires modifying `validate_dataset_integrity`
(`walkforward.py` L320–328), which is the module that enforces BTC dataset
integrity — introducing change into the integrity-checking layer itself.

---

## 3. How the reserved window is protected

**[V]** Identity is the **dataset SHA-256, not the path**
(`researchguard.py` L21–22). A byte-identical copy cannot evade the reservation.

**[V]** The reservation declares `evaluation_first` / `evaluation_last`. The guard
requires the run's declared range to match it — a caller cannot pass
`evaluation_start=None` and trade the whole series (L23–26).

**[V]** `consume_reservation()` requires an explicit `registry_file` and raises
`ResearchGuardError` without one.

**[V]** Current state, verified before and after this phase:

```
status             : RESERVED
used               : False
preregistration_id : None
dataset_sha256     : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
```

**[V]** The reservation's own note is candid: *"Declared intent only. **NOT
protected against evaluation** until a preregistration is frozen and the guard is
exercised."* `RESERVED` is a marker, not a lock.

---

## 4. How configuration, costs, execution and metrics get frozen

**[V]** `walkforward.py` provides three freezing primitives:

| Primitive | Line | Freezes |
|---|---|---|
| `config_hash(config)` | L450 | The exact `StrategyConfig` |
| `costs_hash(costs)` | L456 | The exact `TradingCosts` |
| `dataset_fingerprint(candles)` | L462 | `(count, first, last)` of the series |

**[V]** `assert_clean_working_tree()` (L693) fails if the repository is dirty at
evaluation time.

**[V]** Frozen values to record in the preregistration:

| Item | Value (from source) |
|---|---|
| Config | The frozen `baseline_config()` values; `asset="BTC/USDT"` (a label only) |
| Costs | `phase13_costs()` — fee `0.001`, slippage `0.0005`, spread **`0.0`**, `cost_deduction` |
| Balance / risk | `STARTING_BALANCE = 10000.0`, `RISK_FRACTION = 0.01` |
| Execution | Signals on closed bars; fill at **next bar open**; no intrabar fills assumed |
| Exits | `opposite_signal`, or `end_of_data` close at the final bar. `max_holding`, `stop_loss`, `take_profit` are **disabled** (`None`) |
| Metrics | Win rate, net P&L, average P&L, profit factor — declared in advance |

**[V]** Recording `config_hash` and `costs_hash` before evaluation means any later
change to parameters or costs is detectable as a hash mismatch, not as a quiet
edit.

---

## 5. Checks preventing reuse and leakage

| Risk | Control | Verified |
|---|---|---|
| Re-evaluating the spent BTC holdout | `consumed_windows` records it; guard refuses a consumed window | **[V]** |
| Re-evaluating a consumed ETH window | `consume_reservation` sets `used` + `used_preregistration_id`; guard refuses | **[V]** |
| Trading the warm-up bars | Reservation separates warm-up (17,544 bars) from evaluation (6,744, start index 17,544); `evaluation_start` must be declared | **[V]** |
| Trading the whole series by omitting the range | `run_backtest` raises if a context is supplied without `evaluation_start` | **[V]** |
| Copying the dataset to a new path to evade the guard | Identity is the SHA-256, not the path | **[V]** |
| Silently changing parameters mid-evaluation | `config_hash` / `costs_hash`; `assert_clean_working_tree()` | **[V]** |
| Unlabelled cross-asset transfer | `CrossAssetAuthorization` requires `config_asset`, `dataset_instrument`, `justification` | **[V]** |
| A guard failure or crash silently spending the window | Guard runs before the engine; consumption is the caller's explicit post-run decision | **[V]** |

---

## 6. Application-level safeguards, not security boundaries

This distinction matters and is easy to gloss over. **None of the following is a
security control.** All are application-level conventions enforced by cooperative
code in a repository anyone with write access can edit.

**[V] Single-use protection is caller-dependent.** `run_backtest` passes
`mark_used=False` **unconditionally** (L180). `assert_series_permitted` never
consumes. Consumption happens only if the caller invokes
`consume_reservation()` after the run. The rationale is documented (L146–150):
consumption is the caller's explicit decision so a guard failure or crash cannot
silently spend a window.

*Implication:* **a reserved window can be evaluated repeatedly** if the caller
simply never calls `consume_reservation()`. Nothing in `run_backtest` prevents
this. Single-use is a **protocol obligation**, discharged by discipline, not an
enforced invariant. There is deliberately no `skip_guard` flag — but the
converse is equally true: no `force_use` flag either, and no automatic spend.

**[V] The registry is a plain JSON file.** It has no signature, no integrity
protection and no access control. A process with filesystem write access can
edit `status`, `used`, or any `licence_knowledge` value directly. The guard
validates schema and internal consistency — **not** authorship or immutability.

**[V] Hashes detect change, not tampering.** `dataset_fingerprint` and the
SHA-256 identity checks would notice a modified dataset; they would not notice a
modified registry.

**[V] `assert_clean_working_tree()` is a courtesy check.** It reads git state. It
is bypassed by running outside a repository.

**Therefore:** these controls protect against *accident*, and against an honest
engineer under time pressure. They do not resist a determined actor with write
access. Phase 41's own scoping applies: no enforcement here is a security
boundary. Genuine immutability would require signing the registry, storing
digests outside the repository, or an append-only audit log — none of which exist.

---

## 7. Proposed evaluation sequence with approval gates

Nothing below is authorised. Each gate requires explicit human approval.

```
GATE 0 — Governance corrections
  ├─ Approve Python package licence            (LICENCE_SCOPE_REVIEW H1)
  ├─ Approve + apply ECB registry correction   (ECB_REGISTRY_CORRECTION_PROPOSAL)
  └─ Approve Binance licence_knowledge update  (LICENCE_SCOPE_REVIEW item 9)
         │
GATE 1 — Close preregistration decisions D1–D8
  ├─ All eight closed; numeric inputs supplied by the owner
  ├─ Reserved ETH performance NOT inspected to inform any of them
  └─ Produces a preregistration document (no ID yet)
         │
GATE 2 — Freeze the preregistration
  ├─ Assign preregistration_id
  ├─ Record config_hash, costs_hash, dataset_fingerprint, metric list
  ├─ Record evaluation_first/last and warm-up split
  ├─ assert_clean_working_tree() passes
  └─ Registry updated: reservation gains preregistration_id
         │
GATE 3 — Cross-asset authorization
  ├─ CrossAssetAuthorization recorded: config_asset "BTC/USDT",
  │  dataset_instrument "ETH/USDT", justification, approver, date
  └─ from_record() must validate
         │
GATE 4 — EVALUATE (single use)
  ├─ run_backtest with ResearchContext, evaluation_start = index 17544
  ├─ Guard decision recorded before results are read
  ├─ consume_reservation() IMMEDIATELY after the run, before interpretation
  └─ Results reported exactly as preregistered — no threshold substitution
         │
GATE 5 — Report
  ├─ SUPPORTED / NOT SUPPORTED / INCONCLUSIVE per the pre-set rule
  └─ No parameter change, no re-run on the same window
```

**[V] Gate ordering is enforced by design, not convention:** the guard refuses a
context with `preregistration_id=None` and refuses a cross-asset evaluation
without an authorization record, so Gates 2 and 3 cannot be skipped and still
produce a run.

**[V] Gate 4's ordering matters.** `consume_reservation()` should run **before**
results are interpreted. Consuming first makes re-evaluation impossible even if
the result is disappointing — which is precisely the moment the temptation to
re-run appears. This is the one procedural control that has no technical
substitute.

---

## 8. Recommendation

**Confirm Option A.**

The recommendation rests on the finding in §1: with no fitted parameters,
walk-forward does not deliver the generalisation evidence its name implies,
while adding multiplicity risk to evidence that is consumed irreversibly.
Option A executes today on existing code with every safeguard intact, and
converts already-frozen, checksum-verified data into a result without touching
frozen BTC research semantics.

**Option B remains the correct long-term direction** — the change to
`validate_dataset_integrity` is small and safe — and should be done as its own
phase, with the asset-agnostic API and its own test coverage, on separate data.

**[H] Human approval required** to confirm Option A, and for Gates 0–4
individually. **Readiness is not authorisation: nothing here permits an
evaluation to run.**