# Phase 55 — Preregistration Draft (NOT FROZEN)

> **STATUS: DRAFT. NOT FROZEN. NO PREREGISTRATION ID ASSIGNED OR RESERVED.**
>
> Every field that requires a human decision is marked
> **`OPEN — OWNER DECISION REQUIRED`** and must be closed **before** any
> evaluation runs. A decision left open until the result is known has already
> been decided by the result.
>
> No performance figure from the reserved window appears in this document.
> None has been computed.

---

## 0. Identification

| Field | Value |
|---|---|
| Preregistration ID | **`OPEN — NOT ASSIGNED. NOT RESERVED.`** |
| Draft status | Unfrozen, unapproved |
| Reserved window | `ETH-2026-RESERVATION` |
| Dataset SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Approval requirements | §10 |

---

## 1. Research question and falsifiable hypothesis

**Question.** Does a strategy configuration developed on BTC/USDT 2024–2025
transfer to ETH/USDT 2026, after trading costs?

**Falsifiable hypothesis.**

> **H₀:** Under this configuration, ETH/USDT net expectancy per trade after
> costs is **indistinguishable from zero** on the reserved window.
>
> **H₁:** Net expectancy per trade is sufficiently positive, and its uncertainty
> interval sufficiently clear of zero, to meet the pre-set bar (§7).

**H₀ is the stated expectation.** It is registered as the prior, not as a
fallback. Every prior period in this project was non-distinguishable from zero:
BTC 2024–2025 and the BTC holdout (`INCONCLUSIVE`, net PF 0.4925, median
net/trade −1.4220, 20 trades from 912 bars). Registering a hypothesis that
predicted success would bias the study toward reporting success.

**Falsifiability.** H₁ is falsified if the estimate fails the bar with an
adequate sample, **or** if the interval spans the bar. Either outcome ends the
study for this configuration. No variant may be substituted afterwards.

**Out of scope.** Any claim about ETH generally, other assets, live trading, or
regimes outside the reserved window.

---

## 2. Frozen strategy configuration and provenance

**All values below are read from source and are unchanged from the frozen
configuration.**

| Field | Value |
|---|---|
| `asset` | `"BTC/USDT"` — a **label only**; the engine never checked it |
| `timeframe` | `"1h"` |
| `lookback` | `20` |
| `fast_period` | `5` |
| `slow_period` | `12` |
| `breakout_buffer` | `0.001` |
| `retest_tolerance` | `0.002` |
| `min_breakout_distance` | `0.0` |
| `trend_strength_min` | `0.001` |
| `retest_use_close` | `False` |
| `breakout_confirm_bars` | `1` |
| `max_holding_bars` | `None` (disabled) |
| `stop_loss_pct` | `None` (disabled) |
| `take_profit_pct` | `None` (disabled) |
| `allowed_sides` | **`None` — both long and short permitted** |

**Provenance.** Origin: `walkforward.baseline_config()`. No parameter may be
tuned, and no variant may be substituted, under this preregistration. A modified
configuration requires a **new preregistration and a new reservation**.

**Fitted parameters: none.** The configuration contains no estimated
coefficients. This is why the evaluation is a transfer test rather than a
walk-forward study, and it constrains what §8 can claim.

**Frozen hash:** `config_hash(config)` — **`OPEN — RECORD AT FREEZE`**

---

## 3. Trading costs

| Item | Value | Status |
|---|---|---|
| `fee_rate` | `0.001` | Frozen (`phase13_costs()`) |
| `slippage_rate` | `0.0005` | Frozen |
| **`spread_rate`** | **`0.0`** | **Assumption — stated limitation** |
| `execution_model` | `cost_deduction` | Frozen |
| `STARTING_BALANCE` | `10000.0` | Frozen |
| `RISK_FRACTION` | `0.01` | Frozen |

**Mandatory registered limitation:**

> Costs **exclude** bid–ask spread. No bid/ask data was acquired
> (`bid_ask_available: false`). Results therefore **overstate** achievable
> returns by an unquantified amount. **This bias runs in favour of the
> strategy** and is not corrected in this evaluation.

**Rationale.** `spread_rate = 0.0` is part of the frozen cost fingerprint.
Introducing a band requires a sourced spread measurement; inventing endpoints
would fabricate a parameter. A strategy whose edge is comparable to spread could
appear viable here and be eliminated by realistic costs. **That is the single
largest threat to interpreting a positive result**, and it is registered here
rather than left for a reader to discover.

**Frozen hash:** `costs_hash(costs)` — **`OPEN — RECORD AT FREEZE`**

---

## 4. Execution assumptions

| Assumption | Frozen value |
|---|---|
| Signal generation | Closed candles only (`analyze(candles[:index])`) |
| Fill price | **Next bar's open** |
| Intrabar fills | **Never assumed** |
| Reversal | Close position, then re-enter at next open |
| Position at window end | `end_of_data` close at the final bar |
| Stop loss / take profit / max holding | **Disabled** |

**Limitations.** Next-open fills are mildly optimistic relative to a realistic
queue-and-execution model; **gap risk is not modelled**. With 1-hour bars
next-open fills are standard practice and defensible. Disabled optional exits
mean this evaluates the **raw signal**, not a risk-managed strategy.

---

## 5. Data period and reservation controls

| Item | Value |
|---|---|
| Dataset | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Total bars | 24,288 |
| **Warm-up** | indices **0…17,543** — 17,544 bars, 2024-01-01 → 2025-12-31 |
| **Evaluation** | indices **17,544…24,287** — **6,744 bars**, 2026-01-01 → 2026-10-08 |
| Timeframe | 1h, 3600 s spacing |

**Controls.**

| Control | Mechanism |
|---|---|
| Identity | Dataset **SHA-256**, not path — a copy cannot evade it |
| Range | `evaluation_first` / `evaluation_last` must match the reservation |
| Explicit range | `run_backtest` raises if a context is supplied without `evaluation_start` |
| Warm-up | Bars 0…17,543 produce **no trades**; indicator context only |
| Single use | `consume_reservation()`; **duplicate consumption now refused** (Phase 55) |
| Fail-closed | Consumption requires a writable `registry_file`; empty registry refused |
| **Spent BTC holdout** | **Prohibited** — recorded in `consumed_windows`, guard refuses |
| Working tree | `assert_clean_working_tree()` must pass |

**Known procedural limit, registered not hidden:** `run_backtest` does **not**
auto-consume. If `consume_reservation()` is omitted, the window can be
evaluated again and nothing detects it. Single-use is a **protocol obligation**,
enforced by discipline and by the Gate 4 sequencing — consume **before**
interpreting any result.

---

## 6. Minimum sample requirements

| Requirement | Value |
|---|---|
| Minimum bars | **6,744** — fixed by the reservation, not a choice |
| **Minimum trade count** | **`OPEN — OWNER DECISION REQUIRED`** |
| Clustering caveat | **Registered**: trades are mechanically clustered, not independent |

> **Registered caveat.** Trade count is not a count of independent observations.
> Phase 30 recorded that BTC trades are mechanically clustered. A reader must not
> treat N trades as N independent samples.

**Adequacy rule:** `OPEN — OWNER DECISION REQUIRED` (see
`OWNER_DECISION_GATE.md` B5 for options).
**Below the minimum, the verdict is `INCONCLUSIVE` regardless of sign.**

---

## 7. Metrics, uncertainty and decision rule

### 7.1 Metrics

| Role | Metric |
|---|---|
| **Primary** | Net expectancy per trade, after costs |
| Secondary | Win rate, net P&L, profit factor, max drawdown, trade count |

### 7.2 Uncertainty

| Element | Value |
|---|---|
| Primary method | **Block bootstrap over time-ordered blocks** |
| Also reported | Per-trade 95% CI — **for continuity with Phase 30 only** |
| Block length | **`OPEN — OWNER DECISION REQUIRED`** |
| Iterations | **`OPEN — OWNER DECISION REQUIRED`** |
| Basis for block length | **`OPEN — OWNER DECISION REQUIRED`** (must not use ETH 2026) |

**Rationale.** Phase 30's per-trade CI was recorded as optimistic given
clustering. The block bootstrap respects serial dependence. Block length must be
fixed in advance and **must not** be derived from the reserved window.

### 7.3 Decision rule

| Verdict | Condition |
|---|---|
| `SUPPORTED` | **`OPEN — OWNER DECISION REQUIRED`** |
| `NOT SUPPORTED` | Estimate fails the bar with an adequate sample |
| `INCONCLUSIVE` | Sample adequacy not met, **or** the interval spans the bar |

**Branch structure:** three branches, not two. The BTC holdout produced
`INCONCLUSIVE`; a two-branch rule would classify that as failure and misrepresent
the evidence.

---

## 8. Stopping rules, multiple-testing limitations

### 8.1 Stopping rules

1. **One evaluation.** The window is consumed once. No second run under any
   configuration.
2. **Consume before interpreting.** `consume_reservation()` runs immediately
   after the run and before any result is read.
3. **No threshold substitution.** If the rule proves unsuitable, it is reported
   as unsuitable. It is not revised mid-study.
4. **No variant rescue.** A modified configuration requires a new
   preregistration and a new reservation.
5. **Publish failures.** `NOT SUPPORTED` is a legitimate, publishable result.

### 8.2 Multiple-testing limitations

**This study performs one primary comparison** and does not correct for multiple
tests, because it registers exactly one.

However, the following uncontrolled degrees of freedom are **registered and must
be disclosed in any report**:

| # | Degree of freedom | Mitigation |
|---|---|---|
| 1 | Selection among strategy variants is precluded by registration | §8.1 rule 4 |
| 2 | The `allowed_sides = None` configuration is one of several possible | Fixed in §2 |
| 3 | The evaluation window end (2026-10-08) is fixed by the reservation, **not** chosen | §5 |
| 4 | Zero-spread assumption flatters results | Registered in §3 |
| 5 | **Single window, single regime** — no robustness across sub-periods | Claim limited to one window |
| 6 | **Clustering reduces effective sample below the trade count** | Registered in §6 |
| 7 | A `SUPPORTED` verdict would still not generalise beyond this window | Claim limited accordingly |

**Supported by a result:** *"under this pre-registered configuration, on this
reserved ETH window, at these costs, the measured outcome was X."* Plus a
narrow BTC→ETH transfer statement.

**Not supported by any result:** generalisation to other regimes, other assets,
live trading, or any claim of profitability beyond this single window.

**No significance level is claimed.** This is a preregistered single test with a
pre-set decision rule, not a hypothesis-testing exercise with an α.

---

## 9. Excluded from this evaluation

| Excluded | Reason |
|---|---|
| The spent BTC holdout | `consumed_windows`; guard refuses |
| BTC 2024–2025 development data | Used to develop the configuration |
| Any second ETH window | Does not exist; would need a new reservation |
| Parameter tuning | §2 |
| Forex / ECB data | Blocked on data quality; not OHLC |

---

## 10. Approval requirements

| Gate | Requirement | Status |
|---|---|---|
| **B5** | Minimum trade count | **`OPEN — OWNER DECISION REQUIRED`** |
| **B6** | Block length, iterations, basis | **`OPEN — OWNER DECISION REQUIRED`** |
| **B7** | Decision rule and bar | **`OPEN — OWNER DECISION REQUIRED`** |
| **B8** | Cross-asset approver and date | **`OPEN — OWNER DECISION REQUIRED`** |
| **Freeze** | Assign preregistration ID; record `config_hash`, `costs_hash`, `dataset_fingerprint` | **`OPEN`** |
| **B11** | Explicit evaluation authorization | **`OPEN — OWNER DECISION REQUIRED`** |

**Cross-asset authorization record** (required by the guard):

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — not a tuning opportunity |
| `approver` | **`OPEN — OWNER DECISION REQUIRED`** |
| `date` | **`OPEN — OWNER DECISION REQUIRED`** |

---

## 11. Freeze checklist

To be completed **before** any evaluation:

- [ ] B5, B6, B7 closed with values recorded
- [ ] B8 approver and date recorded
- [ ] Preregistration ID assigned
- [ ] `config_hash` recorded
- [ ] `costs_hash` recorded
- [ ] `dataset_fingerprint` recorded
- [ ] Evaluation window and warm-up split confirmed against the reservation
- [ ] `CrossAssetAuthorization` validated by `from_record()`
- [ ] `assert_clean_working_tree()` passes
- [ ] Reservation updated with the preregistration ID
- [ ] **B11 separate authorisation obtained**

**Until every box is ticked, the reservation remains `RESERVED` / `used: false` /
`preregistration_id: null`, and no evaluation may run.**

---

**This draft is not frozen. No ID is assigned. No evaluation is authorised.**