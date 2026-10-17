# Phase 54 — Preregistration Decision Register

**Date:** 2026-10-09
**Supersedes nothing.** Phase 51 (`D-1`…`D-8`) and Phase 53 recorded eight
decisions in an earlier framing. This register restates them as the eight
canonical preregistration decisions and maps each across, so no earlier decision
is lost.

**The reserved ETH evaluation window was not inspected to inform any entry
below.** No performance figure from ETH 2026 appears in this document, because
none has been computed.

**No preregistration is frozen. No ID is assigned or reserved.**

---

## Mapping to earlier decisions

| Phase 54 | Phase 51/53 | Note |
|---|---|---|
| **P1** Research question and hypothesis | — | **New.** Earlier phases assumed it implicitly |
| **P2** Strategy configuration | D-6 (long-only vs both) | Folded in |
| **P3** Trading costs | D-5 (zero spread) | Folded in |
| **P4** Execution assumptions | — | **New.** Was never explicitly registered |
| **P5** Minimum data and trade requirements | D-1 | Directly |
| **P6** Metrics and uncertainty reporting | D-2 | Directly |
| **P7** Stopping rules and failed-evaluation handling | D-3 (decision rule) | Extended: adds stopping rules |
| **P8** Cross-asset authorization and reservation | D-4, D-8 | Combined |
| — | **D-7** single window vs walk-forward | Decided in `ETH_EVALUATION_READINESS.md` §8 |
| — | **D-8** freeze/evaluate approval | Became Gates 2–4 in the same document |

---

## P1 — Research question and hypothesis

**Question.** Does a configuration developed on BTC 2024–2025 transfer to ETH
2026, after costs?

**Evidence available.** BTC 2024–2025 and the BTC holdout were both
non-distinguishable from zero; holdout verdict `INCONCLUSIVE`, 20 trades from
912 bars, net PF 0.4925, median net/trade −1.4220, with trades recorded as
mechanically clustered. The strategy has **no fitted parameters**.

**Proposed default.**

> **H₀ (stated expectation): there is no transferable edge.** The BTC-derived
> configuration is expected to produce net expectancy indistinguishable from zero
> on ETH 2026 after costs. H₀ is the prior, not the fallback.

Framing matters: registering a hypothesis that predicts *success* would bias the
study toward reporting success, and given every prior period here was
non-distinguishable from zero, that framing would be unfaithful to the evidence.
The research question is **transfer**, and `INCONCLUSIVE` is a legitimate,
expected outcome.

**Explicitly out of scope:** any claim about ETH generally, other assets, or live
trading.

**Consequences and limitations.** A single 2026 window tests one regime
transfer, not general robustness. Transfer failure does not prove the strategy
has no edge anywhere; transfer success on one window does not establish one.

**Human approval required:** **Yes** — the hypothesis is a research claim.
**Finalizable without evaluation results:** **Yes.**

---

## P2 — Strategy configuration

**Question.** Which `StrategyConfig` is frozen for the evaluation, and are both
trade directions permitted?

**Evidence available.** `baseline_config()` in `walkforward.py`;
`StrategyConfig.asset = "BTC/USDT"`; `allowed_sides = None`. Full field values
verified from source in Phase 51.

**Proposed default — testable and unchanged:**

| Field | Value |
|---|---|
| `asset` | `"BTC/USDT"` (a **label only**; the engine never checked it) |
| `timeframe` | `"1h"` |
| `lookback` / `fast_period` / `slow_period` | `20` / `5` / `12` |
| `breakout_buffer` / `retest_tolerance` | `0.001` / `0.002` |
| `min_breakout_distance` | `0.0` |
| `trend_strength_min` | `0.001` |
| `retest_use_close` | `False` |
| `breakout_confirm_bars` | `1` |
| `max_holding_bars` / `stop_loss_pct` / `take_profit_pct` | `None` (disabled) |
| **`allowed_sides`** | **`None` — both long and short** |

Freeze via `config_hash(config)`.

**Rationale.** `allowed_sides = None` is part of the frozen configuration.
Restricting to long-only now would be a parameter change made *after* the
configuration was frozen and after BTC results were observed — tuning, even when
motivated by purity. If a long-only variant is wanted it is a **separate
preregistration with its own ID and its own data**.

**Consequences and limitations.** Both directions roughly doubles exposure
relative to long-only and may halve the trade count. ETH will be tested with a
BTC-labelled configuration — that is the point of a transfer test, and it is
recorded as such in P8.

**Human approval required:** **Yes** — departure from the frozen configuration
always requires it. **Finalizable without results:** **Yes.**

---

## P3 — Trading costs

**Question.** What costs apply, and is `spread_rate = 0.0` acceptable?

**Evidence available.** `phase13_costs()`: `fee_rate=0.001`,
`slippage_rate=0.0005`, **`spread_rate=0.0`**, `execution_model="cost_deduction"`.
Registry records `bid_ask_available: false` — no bid/ask data was acquired.
Binance Vision klines are OHLCV only; no spread series exists.

**Proposed default.**

| Item | Value | Status |
|---|---|---|
| Fee | `0.001` | Frozen |
| Slippage | `0.0005` | Frozen |
| **Spread** | **`0.0`** | **Assumption, stated as a named limitation** |
| Model | `cost_deduction` | Frozen |
| Balance / risk | `10000.0` / `0.01` | Frozen |

Freeze via `costs_hash(costs)`.

**Mandatory preregistration statement:**

> *Costs exclude bid–ask spread. Results therefore **overstate** achievable
> returns by an unquantified amount. This is a directional bias in favour of the
> strategy, and it is not corrected in this evaluation.*

**Rationale for keeping 0.0.** It is frozen and part of the cost fingerprint.
Introducing a band requires a sourced spread measurement; inventing endpoints
would fabricate a parameter and change the fingerprint. Note the bias direction:
a zero-spread assumption **flatters** the strategy. Registering it explicitly
means the reader can discount accordingly.

**Consequences and limitations.** A strategy whose edge is comparable to spread
would be eliminated by realistic costs but could appear viable here. That is
the single largest threat to interpreting a positive result.

**Human approval required:** **Yes** — explicit acceptance of the limitation.
**Finalizable without results:** **Yes.**

---

## P4 — Execution assumptions

**Question.** What execution model does the evaluation assume?

**Evidence available.** Verified from `backtest.py`: signals generated from
closed candles only (`analyze(candles[:index])`); fill at the **next bar's
open**; intrabar fills are never assumed. Exit reasons:
`opposite_signal`, `max_holding`, `stop_loss`, `take_profit`, `end_of_data`.
All optional exits are disabled.

**Proposed default — testable:**

| Assumption | Frozen value |
|---|---|
| Signal timing | Closed bars only |
| Fill price | **Next bar open** |
| Intrabar fills | **Never assumed** |
| Position reversal | Close then reopen at next open |
| Position at window end | `end_of_data` close at the final bar |
| Max holding | Disabled |
| Stop loss / take profit | Disabled |

**Consequences and limitations.** Next-open fills are mildly optimistic relative
to a realistic queue-and-execution model, and gap risk is not modelled. With
1-hour bars, next-open fills are standard practice and defensible, but the
limitation belongs in the record. Optional exits being disabled means the
evaluation tests the **raw signal**, not a risk-managed strategy.

**Human approval required:** **Yes** — these are protocol assertions.
**Finalizable without results:** **Yes.**

---

## P5 — Minimum data and trade-count requirements

**Question.** What sample is adequate, and what happens below it?

**Evidence available.** BTC holdout: **20 trades from 912 bars** — trades
recorded as **mechanically clustered, not independent**. ETH evaluation window:
**6,744 bars**, warm-up 17,544, evaluation start index 17,544.

**Proposed default.**

1. **Minimum trade count:** `[OWNER]` — a floor below which the result is
   declared uninformative regardless of sign.
2. **Minimum bar count:** **6,744** — fixed by the reservation, not a choice.
3. **Clustering caveat stated in the preregistration**, so no later reader treats
   N trades as N independent observations.
4. **Below-threshold outcome is `INCONCLUSIVE`**, never `NOT SUPPORTED`.

**Rationale.** A raw trade-count threshold alone is a poor adequacy proxy
precisely because clustering breaks the independence assumption any count-based
test relies on. That is why the caveat is registered as a protocol term, not a
footnote.

**Consequences and limitations.** The owner-supplied value materially affects the
verdict: set too high, the study is almost certainly `INCONCLUSIVE`; set too
low, it will read noise as signal. **That is the owner's risk appetite to
express — it cannot be derived from the data.** Choosing it after seeing the
trade count would make it outcome-dependent.

**Human approval required:** **Yes** — `[OWNER]`.
**Finalizable without results:** **Yes**, and it must be closed before P7.

---

## P6 — Performance metrics and uncertainty reporting

**Question.** Which metrics, and how is uncertainty quantified?

**Evidence available.** Engine already computes win rate, net P&L, average P&L
and profit factor. Phase 30 used a **per-trade 95% CI**, recorded as optimistic
given clustering.

**Proposed default.**

| Element | Value |
|---|---|
| Primary metric | **Net expectancy per trade**, after costs |
| Secondary | Win rate, net P&L, profit factor, max drawdown, trade count |
| Uncertainty method | **Block bootstrap over time-ordered blocks** (primary) |
| Also reported | Per-trade 95% CI, **for continuity with Phase 30 only** |
| Block length | `[OWNER]` |
| Iterations | `[OWNER]` |
| Reporting | Point estimate **and** interval; state explicitly whether it spans the bar |

**Rationale.** The block bootstrap respects serial dependence; the per-trade
interval does not, and is known to understate uncertainty when trades cluster.
Reporting both keeps continuity with the existing record while making the
stronger method primary. It also directly addresses Phase 30's own caveat.

**Consequences and limitations.** Block-bootstrap intervals depend on block
length. Choosing it *after* seeing results is a researcher degree of freedom,
which is why it must be fixed in advance — ideally tied to the strategy's typical
holding horizon rather than to observed data.

**Human approval required:** **Yes** for block length and iterations; **No** for
adopting the block bootstrap itself, which is a method choice with a sound
rationale. **Finalizable without results:** **Yes.**

---

## P7 — Stopping rules and failed-evaluation handling

**Question.** What are the possible verdicts, what stops the study, and what
happens if it fails?

**Proposed default — three branches, not two.**

| Verdict | Condition |
|---|---|
| `SUPPORTED` | Point estimate **and** interval both clear the pre-set bar `[OWNER]` |
| `NOT SUPPORTED` | Estimate fails the bar with adequate sample |
| `INCONCLUSIVE` | **Sample adequacy (P5) not met**, or the interval spans the bar |

**Stopping rules:**

1. **One evaluation.** The window is consumed once. No second run on the same
   window, under any configuration.
2. **Consume before interpreting.** `consume_reservation()` runs immediately
   after the run and before any result is read — the only control that survives
   the moment of temptation.
3. **No threshold substitution.** If the rule proves unsuitable, it is reported as
   unsuitable. It is not revised mid-study.
4. **No variant rescue.** A modified configuration requires a new
   preregistration and a new reservation.
5. **On failure: publish it.** A `NOT SUPPORTED` result on ETH, added to the
   existing non-distinguishable-from-zero BTC evidence, is a legitimate research
   outcome and strengthens the record.

**Rationale.** The three-branch rule exists because the BTC holdout produced
`INCONCLUSIVE`. A two-branch rule would force that outcome into
`NOT SUPPORTED` and destroy the distinction this protocol exists to maintain.

**Consequences and limitations.** A high minimum-trade threshold makes
`INCONCLUSIVE` likely. That is the honest reading of a 6,744-bar clustered
sample, and suppressing it would be the failure mode this register prevents.

**Human approval required:** **Yes** — the bar `[OWNER]` is the central
pre-registered quantity. **Finalizable without results:** **Yes**, and it must
be.

---

## P8 — Cross-asset authorization and data reservation

**Question.** Who authorises applying a BTC-labelled configuration to ETH, and
what protects the window?

**Evidence available.** `StrategyConfig.asset` is **only a label**; the engine
never checked it (`researchguard.py` L13–15). `CrossAssetAuthorization` already
exists (L122) with `config_asset`, `dataset_instrument`, `justification`, plus
approver fields; `from_record()` rejects an incomplete record. Reservation
`ETH-2026-RESERVATION` is `RESERVED` / `used: false` / `preregistration_id: null`.

**Proposed default — using the existing mechanism, not a new one.**

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — a transfer test, explicitly **not** a tuning opportunity |
| Approver | **`[OWNER]` — named person** |
| Date | **`[OWNER]`** |

**Reservation handling:**

- Identity is the dataset **SHA-256**, not a path — a copy cannot evade it.
- `evaluation_first` / `evaluation_last` must match the declared range.
- `run_backtest` raises if a research context is supplied without
  `evaluation_start`.
- Warm-up bars (0…17,543) produce no trades; evaluation is indices
  17,544…24,287.
- Consumption requires an explicit writable `registry_file`.
- **Known limitation:** `run_backtest` never consumes automatically — see
  `ETH_EVALUATION_READINESS.md` §6. Single-use is a protocol obligation, not an
  enforced invariant.

**Human approval required:** **Yes** — this is the decision that most requires a
person. It asserts BTC development carries over to ETH, which is a research
claim, not a code fact. **Finalizable without results:** **Yes**, and the guard
refuses to run without it, so there is no ordering hazard.

---

## Summary

| # | Decision | Proposed default needs | Owner input | Finalizable pre-result |
|---|---|---|---|---|
| **P1** | Research question / hypothesis | Hypothesis statement | Approval | **Yes** |
| **P2** | Strategy configuration | Frozen values (given) | Approval | **Yes** |
| **P3** | Trading costs | Spread-limitation acceptance | Approval | **Yes** |
| **P4** | Execution assumptions | Protocol assertions (given) | Approval | **Yes** |
| **P5** | Min data / trades | Minimum trade count | **`[OWNER]`** | **Yes** |
| **P6** | Metrics / uncertainty | Block length, iterations | **`[OWNER]`** | **Yes** |
| **P7** | Stopping rules / verdict | Decision bar | **`[OWNER]`** | **Yes** |
| **P8** | Cross-asset / reservation | Approver name, date | **`[OWNER]`** | **Yes** |

**Status: all eight OPEN.** None closed by this phase. Four require
owner-supplied numeric or identity inputs.

**The binding constraint:** every decision here is finalizable **without**
evaluation results — and three of them (P5, P6 parameters, P7) only have
meaning if closed **before** results exist. A decision left open until the
result is known has already been decided by the result.

**No profitability threshold has been proposed or selected in this document.**
Every numeric gate is `[OWNER]`.