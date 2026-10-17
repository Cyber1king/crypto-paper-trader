# Phase 61 — B9: Option A Confirmation Brief

**Status: `OWNER DECISION REQUIRED` — confirmation OPEN.**
Existing scope is preserved unchanged. No protocol modification, no approval,
no ID assignment, no evaluation.

---

## 1. The existing proposal, as recorded

**[R] Option A — a single preregistered ETH evaluation window**, executable
today with **no code change**, recommended across Phases 53–60.

**Alternative — Option B: a segmented walk-forward framework**, requiring a
change to `validate_dataset_integrity` (`walkforward.py` L320–328).

---

## 2. The rationale as recorded

**[V] Verified facts supporting Option A:**

| Fact | Evidence |
|---|---|
| `run_backtest` already accepts a `ResearchContext` | `backtest.py` L65, L155–181 |
| Option A requires **no code change** | design review |
| Option A weakens **no** safeguard | every control remains active |
| Option B requires modifying the **integrity-checking layer** | `walkforward.py` L320–328 |
| The reserved window is **6,744 evaluation bars** (17,544 warm-up) | reservation entry |

**[V] Option B's cost:** segmenting a 6,744-bar window with clustered trades
produces very small segments; the BTC holdout produced **20 trades from 912
bars**, so comparable segments would yield too few trades to support inference.

---

## 3. Why segmentation does not establish train/test generalisation here

**This is the central technical point and it is settled by verified facts, not
preference.**

**[V] The strategy has no fitted parameters.** `StrategyConfig` fields
(`lookback=20`, `fast_period=5`, `slow_period=12`, and the thresholds) are **fixed
constants**. `walkforward.py` exposes `config_hash`, which **records** a
configuration; it does not **derive** one. The project README states optimisation
frameworks are deliberately excluded.

**Walk-forward's warrant is:** fit on train → test on validation → measure
**generalisation of the fitting procedure**.

**With no fitting procedure, there is nothing to generalise.**

Segmenting the reserved window would therefore produce **segmented
out-of-sample evaluation** — a robustness check across sub-periods. That is a
genuine benefit, but a **strictly smaller claim** than the name implies.

**Describing Option B as "walk-forward generalisation" would assert a guarantee
that was never tested and, given zero fitted parameters, cannot be tested.**
The preregistration must describe whichever option is chosen accurately.

---

## 4. What the evaluation is intended to establish

**Supported by a result:**

> *"Under this pre-registered configuration, on this reserved ETH window, at
> these costs, the measured outcome was X."*
>
> Plus a narrow **BTC→ETH transfer** statement.

**Not supported by any result:**

| Not supported | Why |
|---|---|
| Generalisation beyond this window | Single window, single regime |
| Generalisation of a fitted model | **No model is fitted** |
| Robustness across sub-periods | The *point* of Option A is that it does not test this |
| Performance in other assets or regimes | Out of scope by design |
| Live-trading suitability | Paper-only research |
| Guaranteed future profitability | No historical result can establish this |

---

## 5. Limitations and outstanding conditions

| # | Limitation | Evidence |
|---|---|---|
| 1 | Single window; no regime diversity | design review |
| 2 | Trades clustered; effective sample < trade count | Phase 30 |
| 3 | `spread_rate = 0.0` — biases **in favour** of the strategy | `costs.py`, registry `bid_ask_available: false` |
| 4 | Next-open fills; gap risk not modelled | `backtest.py` |
| 5 | Optional exits disabled — evaluates the raw signal | `StrategyConfig` |
| 6 | `allowed_sides = None` — both directions; ~doubles exposure | `StrategyConfig` |
| 7 | The strategy is BTC-labelled and applied to ETH | B8 cross-asset authorization |
| 8 | Prior BTC development + spent holdout are real prior work | `consumed_windows` |

**Outstanding conditions before Option A could run** (all currently unmet):

| # | Condition | Path |
|---|---|---|
| 1 | B5, B6, B7 closed | this packet |
| 2 | B8 cross-asset authorization recorded | `B8_APPROVER_REQUIREMENTS.md` |
| 3 | Preregistration frozen with an assigned ID | `B10_FREEZE_PREREQUISITES.md` |
| 4 | Explicit evaluation authorisation | `B11_EVALUATION_AUTHORIZATION.md` |

---

## 6. Option B's continuing merit

**[R] Option B remains the correct long-term direction** — an asset-agnostic
walk-forward framework is what the project will need for any future instrument.
The change is small and safe: `expected_sha256` and `expected_count` are already
overridable parameters; only `DATASET_FIRST`/`DATASET_LAST` are bare constants,
and adding `expected_first`/`expected_last` parameters that **default to those
constants** would make every existing call site take the identical branch,
leaving frozen BTC research semantics unchanged.

**It should be built on separate data in its own phase, not on the reserved
window.**

---

## 7. Exact owner confirmation required

> **"I confirm [Option A — a single preregistered ETH evaluation window /
> Option B — direct the asset-agnostic walk-forward framework, with scope:
> … and phase: …]."**

If Option B is chosen, the preregistration must additionally pre-specify:
segment count and boundaries, the aggregation rule, and an explicit statement
that segments are **never** selected on outcome.

**Not to be done by OpenCode:** confirming either option, changing the protocol,
assigning a preregistration ID, or running an evaluation.