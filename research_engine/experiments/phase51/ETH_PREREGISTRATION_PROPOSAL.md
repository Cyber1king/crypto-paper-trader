# Phase 51 — ETH Preregistration **PROPOSAL**

**Status: PROPOSAL — NOT FROZEN, NOT APPROVED**

**This document does not authorise an evaluation.** The registry reservation
remains `status: RESERVED`, `used: false`, `preregistration_id: null`, and that
is correct: a protocol draft is not a frozen preregistration, and a frozen
preregistration is not permission to evaluate.

Every claim below is tagged:

| Tag | Meaning |
|---|---|
| **[FACT]** | Read from source or a frozen artifact; verifiable now |
| **[JUSTIFIED]** | A decision derivable from existing evidence before evaluation |
| **[APPROVAL]** | Cannot be settled without an explicit human decision |

No profitability threshold is invented here. Where a number cannot be justified
from existing evidence, the choice is presented with its rationale in
`DECISIONS_REQUIRING_APPROVAL.md` and left open.

---

## 0. What changed in understanding during this audit

Three findings from inspecting the actual code that previous reports did not
state, each of which constrains the protocol:

1. **`walk_forward` cannot run ETH at all.** `walkforward.DATASET_PATH` and
   `DATASET_SHA256` are hard-wired to the BTC primary dataset.
   **[FACT]** Verified: calling `validate_dataset_integrity` on the ETH series
   raises `WalkForwardValidationError: dataset ends 2026-10-08 23:00:00, expected
   2025-12-31 23:00:00`, with the BTC default path *and* with the ETH path
   supplied explicitly — the expected bounds are constants, not derived from the
   path.

   Consequence: **any walk-forward framing of an ETH evaluation is unavailable
   today.** The only ETH-capable execution path is `run_backtest` with a
   `ResearchContext`.

2. **The strategy was selected on BTC, and ETH 2024–2025 is warm-up context
   only.** Disclosed in full in §1.3 rather than footnoted.

3. **Recorded trades are mechanically clustered, not independent.** Phase 30's
   own summary states this: *"Trades are not independent observations. One
   position at a time, mean hold far exceeding the sample, so the 20 trades are
   mechanically clustered."* **[FACT]** This constrains any rule built on trade
   count — see §5.

---

## 1. Research question and scope

### 1.1 The question **[APPROVAL]**

Two candidate framings, materially different claims:

| | Framing A — transferability | Framing B — within-asset fit |
|---|---|---|
| Claim | A configuration selected on BTC/USDT retains its characteristics on ETH/USDT | The strategy has predictive value on ETH/USDT |
| Data used to select | BTC only | BTC **and** ETH warm-up |
| Selection risk | Low — no ETH data touched | Higher — warm-up is adjacent to evaluation |
| Falsified by | Poor ETH performance | Poor ETH performance |
| Not claimed | — | Not a test of transfer; partially circular |

Framing A is proposed, because it is the claim the existing evidence can
actually support and because it does not let ETH warm-up data influence
parameter selection. **This choice is not mine to make.**

### 1.2 Scope — what is and is not in scope

**In scope:** one configuration, one dataset, one window, one run, reported as
recorded.

**Out of scope, explicitly:**
- Any parameter search, re-optimisation or selection on ETH data.
- Any second window. The reservation covers one.
- Any live or paper-trading deployment.
- Any claim of statistical significance — see §6.

### 1.3 Disclosure — ETH is not independent of BTC research

**This must appear in any report produced from this evaluation.**

**[FACT]** The frozen configuration was selected using BTC/USDT data alone,
across 12+ configuration searches recorded from Phase 5 onward. ETH data was
acquired in Phase 33, after that selection was complete.

**[FACT]** ETH/USDT 2024-01-01 → 2025-12-31 (17,544 bars) is **warm-up context**.
Under the engine's semantics, bars before `evaluation_start` feed indicators so
lookbacks are warm, but cannot open a position. Warm-up bars therefore produce
**zero trades** and contribute **no** performance figure.

**[FACT]** A configuration selected on BTC is being applied to a *different,
correlated* asset. BTC and ETH returns are substantially correlated, so this is
**not** an out-of-sample test in the statistical sense. It is a test of whether
one BTC-derived parameterisation behaves acceptably on a second, related asset.

Any ETH result must be reported with that caveat attached. A negative result
does not generalise beyond this configuration, and a positive result does not
establish an edge.

---

## 2. Frozen strategy configuration **[FACT]**

Read from `crypto_paper_lab.strategy.StrategyConfig`, not from a report.

| Field | Value |
|---|---|
| `asset` | `"BTC/USDT"` — see §8 |
| `timeframe` | `"1h"` |
| `lookback` | 20 |
| `fast_period` | 5 |
| `slow_period` | 12 |
| `breakout_buffer` | 0.001 |
| `retest_tolerance` | 0.002 |
| `min_breakout_distance` | 0.0 |
| `trend_strength_min` | 0.001 |
| `retest_use_close` | `False` |
| `breakout_confirm_bars` | 1 |
| `max_holding_bars` | `None` — disabled |
| `stop_loss_pct` | `None` — disabled |
| `take_profit_pct` | `None` — disabled |
| `allowed_sides` | `None` — both directions permitted |

**No parameter may be changed.** Any change voids the evaluation: the whole
point is to test *this* configuration, and tuning on ETH is prohibited.

`allowed_sides = None` means long and short are both permitted. On spot ETH/USDT
a short is not directly expressible; it is a paper-only modelling convention.
**[APPROVAL]** — whether to constrain to long-only is a real decision, because
changing it changes the configuration (§7, D-6).

---

## 3. Costs and execution assumptions **[FACT]**

Read from `crypto_paper_lab.costs` and `walkforward.phase13_costs`.

| Parameter | Value |
|---|---|
| `fee_rate` | 0.001 (10 bps) |
| `slippage_rate` | 0.0005 (5 bps) |
| `spread_rate` | **0.0** |
| `execution_model` | `"cost_deduction"` |
| Starting balance | 10,000.00 |
| Risk fraction | 0.01 (1% of equity per position) |

### The spread is zero, and that is a stated limitation

**[FACT]** No bid/ask data was acquired for either instrument. The registry
records `bid_ask_available: false` with an explicit `spread_note` for both
BTC/USDT and ETH/USDT.

**[FACT]** Phase 47 established that for a *liquid* market a bid/ask spread is
frequently comparable to the signal being traded; ignoring it would not merely
weaken a result, it would risk inverting its meaning.

**ETH/USDT is extremely liquid**, so this limitation is material here and is
disclosed rather than papered over. Slippage (5 bps) partially absorbs it, but
slippage and spread are not the same quantity and the model does not claim they
are.

**[APPROVAL]** Whether 0.0 spread is acceptable for ETH, or whether a sensitivity
band should be reported alongside. See D-5.

---

## 4. Execution timing, fill assumptions, exit semantics **[FACT]**

### Timing

- Signals computed from bars that have already closed.
- **Fills occur at the open of the following bar.** Intrabar fills are never
  assumed; a stop or target touched intrabar is a *trigger*, not a guaranteed
  fill.
- When one bar breaches both stop and target, the order is unknowable from
  hourly data; the stop is assumed hit first. The fill price is the next bar's
  open either way, so this affects only the recorded exit label, not P&L.

### Exit reasons

Only four, from `backtest.py`:

| Exit | When |
|---|---|
| `opposite_signal` | an opposite-side signal fires — **the default rule** |
| `max_holding` | disabled (`max_holding_bars = None`) |
| `stop_loss` | disabled (`stop_loss_pct = None`) |
| `take_profit` | disabled (`take_profit_pct = None`) |
| `end_of_data` | final candle forces a close |

With the optional rules disabled, behaviour is the original V1 rule: close on an
opposite signal, or force-close at the end of the data. **A forced
`end_of_data` close is not a strategy decision** and must be reported separately
in any results — it can flatter or penalise a window depending on where it ends.

### Warm-up and the boundary

`evaluation_start = 17544`. The broker starts flat with the full balance at the
boundary. Indicators are warmed by the preceding 17,544 bars; no position can be
opened before index 17544.

---

## 5. Data sufficiency and minimum trades

### What is verifiable now **[FACT]**

| Quantity | Value |
|---|---|
| Evaluation bars | 6,744 (2026-01-01 → 2026-10-08, ≈281 days) |
| Reference: BTC holdout bars | 912 (≈38 days) |
| Reference: BTC holdout trades | **20** |
| Reference: BTC holdout net PF | 0.4925 |
| Reference: BTC holdout verdict | INCONCLUSIVE |
| Reference: BTC median net per trade | −1.4220 |

### Why no threshold is proposed here

**[FACT]** Phase 30 recorded, in advance and in its own words, that the 20
holdout trades were *not independent* — one position at a time, mean hold far
exceeding the sample, so the trades are mechanically clustered.

This has a direct consequence: **a minimum-trade-count rule justified by
"independent observations" would be unjustified.** Trade count alone cannot
establish sample adequacy when observations overlap in time.

A naive linear scaling (912 bars → 20 trades implies ≈148 trades over 6,744
bars) would *look* like sufficient evidence. It is not, because the scaling
assumes a constant trade rate that the BTC window does not establish, and it
counts clustered observations as if they were independent.

**[APPROVAL]** D-1: the minimum-trade rule, and if clustering is material, the
adequacy criterion. Presented with options in `DECISIONS_REQUIRING_APPROVAL.md`.
**Not decided here.**

---

## 6. Metrics, uncertainty and limitations **[JUSTIFIED]** / **[APPROVAL]**

### Metrics to record — all already implemented

**[FACT]** `stats.py` computes these; none is newly invented:

trade count · net P&L · gross profit · gross loss · net profit factor ·
win rate · median net per trade · maximum drawdown · exposure fraction ·
per-exit-reason counts · costs

Profit factor must be **defined** in the report, as Phase 30 did: with losing
trades present it is `gross_profit / gross_loss`, net of costs. A ratio defined
only when there are winners would otherwise read as unbounded.

### Uncertainty — this is where a decision is required

**[FACT]** No statistical significance was claimed anywhere in Phase 31, which
set that as an explicit property of this project.

**[APPROVAL]** D-2: how uncertainty should be reported. Three options are
presented in the decisions document. **None is chosen here**, because choosing a
confidence level without observed data is precisely the post-hoc rationalisation
this project has avoided throughout.

### Mandatory limitations in any report

1. Configuration selected on BTC, not ETH. (§1.3)
2. ETH warm-up produced zero trades and no performance contribution.
3. Spread is 0.0; no bid/ask data exists. (§3)
4. `end_of_data` forced closes are not strategy decisions. (§4)
5. Trades are mechanically clustered, not independent. (§5)
6. One window, one run. No replication.
7. Short positions are a paper convention, not directly expressible on spot.
8. Passing tests and a completed protocol establish **nothing** about
   profitability.

---

## 7. Decision rules, invalidation, stopping

### 7.1 Invalidation conditions **[JUSTIFIED]**

The evaluation is **void — not merely negative — if any occurs:**

| # | Condition | Why |
|---|---|---|
| 1 | Any parameter differs from §2 | It is no longer a test of this configuration |
| 2 | `dataset_sha256` ≠ `7507c100…` | Different data |
| 3 | Evaluation window ≠ 17544…24287 | Different window |
| 4 | Any cost differs from §3 | Different economics |
| 5 | Any warm-up bar produced a trade | Warm-up must produce none |
| 6 | Code executed outside `run_backtest` + `ResearchContext` | Different execution semantics |
| 7 | Cross-asset authorization absent | Unauthorised instrument transfer |

These are all **verifiable without reference to the result**, which is what
makes them usable: none can be triggered by a disappointing outcome.

### 7.2 Stopping rules **[JUSTIFIED]**

- **One run. One result.** The reservation is spent by that run.
- **An inconclusive result closes the question.** It does not license a second
  window, a re-run, or a modified configuration. The BTC precedent applies: the
  Phase 29 holdout was evaluated once and is permanently retired.
- **A negative result closes the question for this configuration.** It is a
  finding, not a setback to be addressed by re-running.
- **No result may be obtained before the protocol is frozen.**

### 7.3 Decision rule **[APPROVAL]**

**Not specified here.** D-3 in the decisions document. Inventing a
profitability threshold here would be the single most damaging act available at
this stage: a number chosen before seeing data still becomes the standard the
data is judged against, and choosing it to be attainable is not the same as
choosing it to be correct.

What *is* specified is the **reporting obligation**: whatever the rule, the
result is reported as recorded, including if it is `INCONCLUSIVE` — a category
the BTC evaluation already used.

---

## 8. Cross-asset authorization **[APPROVAL]**

**[FACT]** The frozen `StrategyConfig.asset` is `"BTC/USDT"`. Applying it to
ETH/USDT data is a cross-asset transfer, and `CrossAssetAuthorization` exists
precisely to make it explicit. **[FACT]** No such record has been created.

**[FACT]** The configuration must **not** be edited to `asset="ETH/USDT"`. That
would relabel the data rather than authorise the transfer, and would destroy the
very thing being tested: whether a *BTC-derived* configuration transfers.

Required record before any run:

```
dataset_instrument : ETH/USDT
config_asset       : BTC/USDT
justification      : tests transferability of a BTC-selected configuration
approved_by        : <human>
approved_on        : <date>
```

**[APPROVAL]** D-4: approval of this transfer, by a named person.

---

## 9. Execution path — and one blocker

**[FACT]** `run_backtest` with a `ResearchContext` is the **only** ETH-capable
path. `walk_forward` and `run_window` are BTC-pinned by construction (§0).

**[FACT]** Consequently this is **a single-window evaluation**, not a
walk-forward evaluation. That is a real reduction in evidence relative to what
the BTC work used, and it must be disclosed rather than papered over.

**[APPROVAL]** D-7: accept a single-window evaluation, or generalise
`walk_forward`'s dataset binding first. Generalising it is a code change that
must happen **before** the protocol is frozen and before any run.

---

## 10. Summary of what this document does and does not establish

**Establishes:** the exact configuration, costs, execution semantics, data
boundaries, and invalidation conditions — all read from source, all verifiable
without reference to any result.

**Does not establish:** the research question, minimum-trade rule, uncertainty
method, decision rule, or cross-asset authorization. Those are in
`DECISIONS_REQUIRING_APPROVAL.md`, and **none has been decided.**

**Does not authorise anything.** The reservation is untouched, and it should
remain untouched until the approvals exist and the protocol is frozen.