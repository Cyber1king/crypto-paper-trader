# Phase 38 — ETH/USDT Research Protocol (Draft)

**Status: DRAFT, NOT FROZEN. This document authorises nothing.**

No backtest, simulation or performance calculation was run. ETH 2026
performance has not been inspected and no parameter was tuned on ETH.

---

## 1. Disclosure — read before anything else

### 1.1 The configuration is BTC-derived

The strategy's parameters were selected during Phases 5–15 using **BTC/USDT
2024–2025** research data. Twelve or more configurations were searched
(`RESEARCH_STATE.json:289`). Applying that configuration to ETH is a
**cross-asset transfer of an already-fixed rule**, not a fresh strategy design.

**No parameter may be re-selected on ETH data.** If any ETH result leads to a
parameter change, the evaluation is void and a new holdout is required.

### 1.2 ETH 2024–2025 is not a clean development set

This is stated explicitly because it is easy to get wrong:

- ETH 2024–2025 was **never** used to select any parameter;
- but it is also **not** a neutral development set, because the configuration
  arriving with it was chosen on a *different asset*.

Exploring ETH 2024–2025 for strategy behaviour risks a **second search layered on
a BTC-derived configuration** — precisely the contamination that permanently
disabled A2 for overlapping windows (`RESEARCH_STATE.json:169`, `:289`).

**Therefore ETH 2024–2025 is designated warm-up context only.** It must not be
used to explore, screen, tune or select anything. See §3.

### 1.3 ETH is a different instrument from BTC

The ETH date range overlaps the consumed BTC windows. That is **not**
contamination, and it is also **not** an independent BTC sample. An ETH result
says nothing about BTC without a BTC-specific test on genuinely new BTC data.

---

## 2. Draft research question

> **On BTC/USDT-derived parameters that were frozen before any ETH data was
> examined, does the frozen configuration produce a non-negative net result
> after frozen costs on ETH/USDT over a single pre-registered 2026 window that
> has never been examined?**

### 2.1 What the question is and is not

| It **is** | It **is not** |
|---|---|
| A cross-asset generalisation question | A search for an ETH edge |
| Single-configuration, frozen | A tuning exercise |
| Bounded to one reserved window | An invitation to iterate |
| Explicitly inconclusive by construction | A profitability test |

### 2.2 Why it is inconclusive by construction

The repository's own floor: *"fewer than ~50 trades makes any comparison
inconclusive"* (`phase9/ACQUISITION_PLAN.md:135-146`). ETH's realised trade rate
has **never been measured**, and measuring it requires a backtest — which is
forbidden here. **It is unknown whether 6,744 evaluation bars will yield enough
trades to clear that floor.**

If the answer proves to be "no", the honest outcome is **INCONCLUSIVE — insufficient
sample**, not a negative finding about the strategy. That branch must be written
into the decision rule before freezing.

---

## 3. Data partition

### 3.1 The three regions

| Region | Indices | Range (UTC) | Bars | Permitted use |
|---|---|---|---|---|
| **Warm-up context** | 0 – 17,543 | `2024-01-01 00:00` … `2025-12-31 23:00` | 17,544 | **Indicator warm-up only.** Produces no trades. Not for exploration |
| **Reserved evaluation** | 17,544 – 24,287 | `2026-01-01 00:00` … `2026-10-08 23:00` | 6,744 | **One pre-registered run, once.** Never inspected before |
| (none) | — | — | — | No other partition exists |

Source dataset: `research_engine/data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv`
SHA-256 `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb`

**Boundary verified this phase:** the first bar with timestamp ≥ `2026-01-01 00:00`
is at index **17,544**. `evaluation_start = 17544`.

*(Coincidence worth noting so it is not mistaken for a bug: 17,544 is also
`walkforward.DATASET_CANDLES`, the BTC 2024–2025 count. Both cover the same
two calendar years.)*

### 3.2 Why warm-up must be fed in full

`WARMUP_RULE = "full_preceding_series"` (`walkforward.py:75`). The engine must
receive the preceding series so lookback windows are genuinely warm; any fixed
prefix would approximate indicator state.

Mechanism: pass all 24,288 candles with `evaluation_start=17544`. Pre-boundary
candles still reach `analyze(candles[:index])` but cannot open a position
(`backtest.py:199`), so they contribute **no trades**. The account starts flat
with the full balance at the boundary.

### 3.3 Warm-up and scored observations must stay separable

The report must show, separately:
- trades whose **entry** is at index ≥ 17,544 (the only scorable ones);
- confirmation that **zero** trades have entry before the boundary.

If any pre-boundary trade appears, the run is invalid. This mirrors the existing
guard `run_window` already applies to walk-forward windows
(`walkforward.py:513-523`) but **does not exist for a bare `run_backtest` call**.

---

## 4. Frozen configuration to be recorded in the preregistration

All values must be copied from live code at freeze time, not from this document.

| Component | Value | Source |
|---|---|---|
| `config` | `StrategyConfig()` defaults, unmodified | `strategy.py:16-46` |
| `asset` field | `"BTC/USDT"` — **mislabelled relative to ETH**; see §6 | `strategy.py:16` |
| Costs | `TradingCosts(0.001, 0.0005)` | `costs.py:57-58` |
| `execution_model` | `cost_deduction` | `costs.py:60` |
| `spread_rate` | `0.0` (forced) | `costs.py:77-82` |
| `starting_balance` | `10_000.0` | `validation_harness.py:36` |
| `risk_fraction` | `0.01` | `validation_harness.py:37` |
| `evaluation_start` | `17544` | this phase |
| Fill timing | next-candle open; signals from closed bars only | `backtest.py:139-149` |
| Exit rule | opposite-signal only; stop/target/max-holding disabled | `backtest.py:158-181` |
| End of data | force-close at final close, **retained** | `backtest.py:207-213` |
| Max concurrent positions | 1 | `simulator.py:79-80` |
| Randomness | none — fully deterministic | — |

---

## 5. Metrics — pre-specified, from existing code only

| Metric | Source | Note |
|---|---|---|
| Trade count | `stats.py:132` | |
| Net P&L | `stats.py:133` | |
| Return % | `(ending_balance / 10_000.0 − 1) × 100` | **No library function exists** — the formula must be pinned literally |
| Win rate | `stats.py:134-138` | |
| Profit factor | `stats.py:139-143` | **Computed from NET P&L.** The gross-basis factor must also be reported and labelled |
| Max drawdown | `stats.py:113-129` | **Closed-trade cumulative curve, a fraction.** Basis must be labelled |
| Gross P&L, total friction | `models.py:109-128`, `stats.py:7-27` | |
| Exit counts | `backtest.py:190-192` | |
| Per-trade table | — | Mandatory |

**Two reporting traps identified in earlier phases and carried forward:**

1. `stats.performance()` names its net-P&L sums `gross_profit`/`gross_loss`
   (`stats.py:102-111`), so the recorded profit factor is **post-cost**. Both
   bases must be reported, distinguished.
2. `friction / gross P&L` is **meaningless when gross is negative** and must not
   be reported as a percentage in that case.

**Not available and must not be fabricated:** exposure / percent-time-in-market
(deliberately never computed, `windowstats.py:8-12`), Sharpe, Sortino, CAGR,
MAE/MFE, per-trade percentage return.

---

## 6. Known mismatch that must be disclosed, not hidden

`StrategyConfig.asset` is `"BTC/USDT"` and the data is ETH/USDT. **Nothing in the
codebase validates the two.** The only non-declaration reference is
`replay.py:363`, which passes the label into the replay context.

Two consequences:

1. The preregistration must state the mismatch explicitly. The `asset` field is a
   **label only** and has no effect on any calculation.
2. The engine would run ETH with no error and no warning. **Nothing technical
   prevents an unapproved run**, which is why §7's governance gates are the
   operative control.

The strategy is scale-invariant — all thresholds are fractions or relative
distances (`level × (1 + buffer)`, `|close − level| / level ≤ tolerance`,
`slow_ma × strength`) — so ETH prices are handled without adaptation. That is a
mechanical fact, **not** evidence that the rule transfers.

---

## 7. Governance prerequisites — none waived by a clean integrity audit

An integrity audit passing does **not** authorise evaluation. Every gate below
must be satisfied separately.

| # | Gate | Current state |
|---|---|---|
| G1 | Cross-asset scope decision recorded | **Open** — Phase 32 records cross-asset behaviour as NOT ESTABLISHED |
| G2 | This research question preregistered | Draft only |
| G3 | Thresholds fixed (§8) | **Open** |
| G4 | Reserved window registered **and enforcement implemented** | **Open** — see `HOLDOUT_ENFORCEMENT_DESIGN.md` |
| G5 | Dataset digest re-verified at run time | Mechanism exists |
| G6 | Formal `RESEARCH APPROVED` record | **Open** |
| G7 | Re-verification pre-run (`normalize_source` on the exact file) | Available |

**A clean audit satisfies an integrity gate only. It does not satisfy G1–G4 or G6.**

---

## 8. Unresolved thresholds — explicit decisions required before freezing

**No threshold is invented in this document.** Each must be decided and recorded
before the preregistration is frozen.

| # | Unresolved decision | Note |
|---|---|---|
| T1 | **Minimum acceptable evaluation bars** | If the window is too short, the correct verdict is INCONCLUSIVE-INSUFFICIENT-SAMPLE, not a negative result |
| T2 | **Minimum trades for any comparison** | The repository floor is ~50 (`phase9/ACQUISITION_PLAN.md:135-146`), but whether 6,744 bars can reach it is **unknown** |
| T3 | **What constitutes an adequate sample** | Must be decided *before* seeing the trade count, or the decision is contaminated |
| T4 | **Whether a null result changes any decision** | Almost certainly not; must be stated anyway |
| T5 | **Whether cross-asset use requires fresh BTC data too** | A governance judgement, not a technical one |
| T6 | **Full decision rule with all branches** | Including the insufficient-sample branch, decided in advance |

**T2 and T3 interact dangerously:** choosing a threshold after seeing how many
trades occur is exactly the contamination the project has already documented as
forbidden (`RESEARCH_STATE.json:394-402`).

---

## 9. Reporting requirements

Any ETH report must contain, in addition to §5:

1. Warm-up range and confirmation that **zero** trades precede the boundary.
2. Evaluation range, bar count, and the exact `evaluation_start`.
3. Dataset SHA-256 re-verified at run time.
4. The `asset`-label mismatch disclosed (§6).
5. Both profit-factor bases, labelled.
6. Drawdown basis labelled as closed-trade.
7. Trade count against the T1/T2 thresholds decided in advance.
8. The §10 uncertainty statement.
9. An explicit statement that the result is **INCONCLUSIVE** for establishing
   profitability, pre-declared.
10. Confirmation no parameter was changed after seeing the result.

---

## 10. Uncertainty statement — pre-declared

Adopted unchanged from the Phase 29D precedent:

- The result is **INCONCLUSIVE** for establishing profitability. Declared now,
  before any number exists, and it does not change afterwards.
- A positive outcome is **not** proof of a profitable edge.
- A negative outcome is **not** proof the strategy can never work.
- Trades are **not independent observations** — one position at a time, mean hold
  49–60 bars.
- **No p-value and no significance test.** Trades are not independent; a t-like
  ratio is a heuristic, never a p-value.
- The standing conclusion (`RESEARCH_STATE.json:14`) is **not revised** by this
  experiment in either direction.

---

## 11. Out of scope for this document

Implementing the reservation, running anything, freezing the preregistration,
choosing any threshold, or approving any evaluation.