# Phase 29D — BTC/USDT Holdout Evaluation Pre-Registration

**Status: PRE-REGISTRATION. No Phase 29D evaluation has been run. No Phase 29D
results exist. No strategy, backtest, or optimisation has been executed against
the frozen holdout dataset as part of this phase.**

This document freezes the evaluation methodology **before** any holdout
evaluation is executed. It exists so that the analysis design cannot be adjusted
after seeing results, and so that a reader can check in advance exactly what
will be measured and how each number will be defined.

Frozen at Git commit `dccebbd53ee8365474345506db9099b13356b53c`.

Every configuration value and metric definition below was copied from the live
source at that commit and is cited as `file:line`. Nothing here is invented. Where
a requested metric does not exist in the code, that is recorded as a limitation
rather than silently computed by a new formula.

---

## 1. What Phase 29D is, and what it is not

Phase 29D is the **pre-registration of a single frozen holdout evaluation**. It
is a document only. The evaluation itself is Phase 29E.

It is **NOT** an optimisation study, **NOT** a parameter search, and **NOT** a
second validation attempt.

### Standing research conclusion, unchanged

No reliable profitability has been established for this strategy. Across
23,376 hourly candles, 12+ configurations and two full evaluation periods, the
project has no evidence of a profitable trading rule
(`experiments/phase15/RESEARCH_STATE.json:14`).

**This evaluation does not revise that conclusion, and must not be used to
revise it in either direction.**

### What this holdout can and cannot do

| It can | It cannot |
|---|---|
| Show how the frozen baseline behaved on 38 days it has never seen | Establish that the strategy is profitable |
| Provide one more genuinely unseen data point | Confirm or refute the standing conclusion |
| Provide descriptive metrics under frozen settings | Support any parameter change |
| Detect gross malfunction | Resolve the effect size in question |

---

## 2. Frozen holdout dataset

| Property | Frozen value |
|---|---|
| Path | `research_engine/data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` |
| SHA-256 | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` |
| Bytes | `56,521` |
| Candles | `912` |
| First candle (UTC) | `2026-09-01 00:00:00` |
| Last candle (UTC) | `2026-10-08 23:00:00` |
| Interval | `1h`, every step exactly 3600 s |
| Timezone | UTC, as recorded by Binance Vision |
| Columns | `Date,Open,High,Low,Close,Volume` |
| Date format | `dd-mm-yyyy HH:MM` (`acquisition.py:47`) |
| Line endings | LF only |
| Price min / max | `74967.97` / `87395.67` |
| Total volume | `598928.15352` |

The SHA-256 was recalculated from disk at the time this pre-registration was
written and matched the value above.

### Dataset independence

| Check | Result |
|---|---|
| Overlap with 2024–2025 research window (`2024-01-01 00:00` … `2025-12-31 23:00`) | 0 bars |
| Overlap with consumed 2026 OOS (`2026-01-01 00:00` … `2026-08-31 23:00`) | 0 bars |
| Seam to consumed OOS | exactly contiguous, delta `0:00:00` |
| Previously examined by any phase | No. First examination is Phase 29E |

### Source and licence

| Property | Value |
|---|---|
| Source | Binance Vision public market data |
| Monthly URL pattern | `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/` |
| Daily URL pattern | `https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h/` |
| Archives | 9 (one monthly + eight daily) |
| Licence | CC BY-NC-SA 4.0 together with the Binance Vision Dataset Terms |
| Commercial use | **Excluded** |
| Attribution | Required on redistribution |

Full per-archive digests, byte counts, row counts, retrieval timestamps and
official URLs are recorded in the dataset manifest:
`research_engine/data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv.manifest.txt`.
Acquisition detail is in the sibling `.report.txt`, and per-archive provenance in
`research_engine/data/oos/raw/*.provenance.txt`.

**Reproducibility caveat.** The repository has `core.autocrlf=true` and no
`.gitattributes`, so a future Windows checkout may rewrite these LF-only files to
CRLF and change their SHA-256 without changing any value. Re-hash after
normalising CRLF → LF before concluding that the data changed.

---

## 3. Code revision and working-tree state

| Field | Frozen value |
|---|---|
| Git commit | `dccebbd53ee8365474345506db9099b13356b53c` |
| Branch | `main` |
| `origin/main` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Modified tracked files | 0 |
| Staged files | 0 |
| Deleted tracked files | 0 |
| New commits in this phase | 0 |
| Untracked files | 30 (the frozen dataset, its report, its manifest, and 27 raw artefacts) |
| Python | `3.12` |
| Random seed | Not applicable — the backtest is fully deterministic, no randomness anywhere |

The working tree is deliberately **not clean**: the holdout dataset and its
provenance are untracked because they were deliberately not committed during
Phase 29. `walkforward.assert_clean_working_tree` (`walkforward.py:660-687`)
would therefore raise if used, and **is not part of this evaluation**.

---

## 4. Frozen strategy configuration

All values are the live defaults of `crypto_paper_lab.strategy.StrategyConfig`
(`strategy.py:16-46`). No field is overridden. No field is added.

| Field | Frozen value | Source |
|---|---|---|
| `asset` | `"BTC/USDT"` | `strategy.py:16` |
| `timeframe` | `"1h"` | `strategy.py:17` |
| `lookback` | `20` | `strategy.py:18` |
| `fast_period` | `5` | `strategy.py:19` |
| `slow_period` | `12` | `strategy.py:20` |
| `breakout_buffer` | `0.001` | `strategy.py:21` |
| `retest_tolerance` | `0.002` | `strategy.py:22` |
| `min_breakout_distance` | `0.0` | `strategy.py:26` |
| `trend_strength_min` | `0.001` | `strategy.py:27` |
| `retest_use_close` | `False` | `strategy.py:28` |
| `breakout_confirm_bars` | `1` | `strategy.py:29` |
| `max_holding_bars` | `None` (disabled) | `strategy.py:37` |
| `stop_loss_pct` | `None` (disabled) | `strategy.py:38` |
| `take_profit_pct` | `None` (disabled) | `strategy.py:39` |
| `allowed_sides` | `None` (both directions) | `strategy.py:46` |

There is **no warm-up field**. Warm-up is derived as
`max(lookback + 2, slow_period) = 22` (`strategy.py:53`, `backtest.py:112-115`).

No trailing stop, break-even move, partial exit, funding or borrow model exists.
`allowed_sides` gates **entries only** (`backtest.py:198`); an open position still
exits on an opposite-side signal (`strategy.py:41-46`).

### Signal logic, as implemented

`analyze` (`strategy.py:49`) returns one of four outcomes, decided in this order
(`strategy.py:177-192`):

| Condition | Signal | Reason label |
|---|---|---|
| `uptrend` and `retest_up` | `long` | `bullish retest` |
| `downtrend` and `retest_down` | `short` | `bearish retest` |
| `uptrend` and `broke_up` | `long` | `uptrend breakout` |
| `downtrend` and `broke_down` | `short` | `downtrend breakdown` |
| otherwise | `flat` | `no confirmed breakout or retest` |

`trend` returns `"up"`/`"down"` only when `fast_ma > slow_ma + slow_ma*strength`,
otherwise `"sideways"` (`indicators.py:31-36`). Support and resistance are
`min(low)` / `max(high)` over the trailing `lookback` bars, excluding the two
most recent candles (`strategy.py:65`, `indicators.py:39-45`).

---

## 5. Frozen cost model and account assumptions

| Field | Frozen value | Source |
|---|---|---|
| `execution_model` | `"cost_deduction"` | `costs.py:60` |
| `fee_rate` | `0.001` | `costs.py:57`, harness `validation_harness.py:34` |
| `slippage_rate` | `0.0005` | `costs.py:58`, harness `validation_harness.py:35` |
| `spread_rate` | `0.0` | `costs.py:59` |
| `starting_balance` | `10_000.0` | `validation_harness.py:36`, `walkforward.py:71` |
| `risk_fraction` | `0.01` | `validation_harness.py:37`, `walkforward.py:72` |
| Warm-up rule | `full_preceding_series` | `walkforward.py:75` |
| Boundary policy | `retain_boundary_force_closes` | `walkforward.py:78` |

All rates are **proportional fractions**, not basis points and not absolute.
Fees and slippage are charged on each filled notional leg
(`simulator.py:160-162`), so a round trip pays each twice: `0.2%` fees plus
`0.1%` slippage, about `0.3%` of reference notional.

Under `cost_deduction` the spread **cannot** be separated from slippage; charging
both would double count, and `TradingCosts` raises if `spread_rate > 0` with this
model (`costs.py:77-82`). Spread is therefore `0.0` by construction, not by
assumption. There is no maker/taker split, no tier, and no size- or
volatility-dependence anywhere in the repository.

---

## 6. Frozen evaluation procedure

### 6.1 Warm-up and evaluation-start semantics

`run_backtest` is called with `evaluation_start = 48`.

| Property | Value |
|---|---|
| `minimum_history` | `22` |
| Loop begins at index | `22` |
| `evaluation_start` (boundary) | `48` |
| Warm-up context bars | indices `0..47` — `2026-09-01 00:00:00` … `2026-09-02 23:00:00` |
| First evaluable bar | index `48` — `2026-09-03 00:00:00` |
| Last bar | `2026-10-08 23:00:00` |
| **Evaluated candles** | **`864`** |

`WARMUP_CANDLES = 48` is inherited unchanged from the Phase 8 harness
(`validation_harness.py:33`), where `48 > max(lookback + 2, slow_period) = 22`.

Semantics, quoted from `backtest.py:94-100`: candles before `evaluation_start`
**still feed the indicators** so lookback windows are fully warmed, but **no
position can be opened there**, so they never contribute trades. The account
therefore starts flat with the full `10,000.0` at the boundary.

The gate is on entries only (`backtest.py:199`). There is **no fixed-length
warm-up prefix**: every pre-boundary candle is passed to `analyze`. This is the
frozen Phase 13 policy. `yearly.py` is **not** used, because it resets warm-up
per calendar year (`walkforward.py:25-26`).

### 6.2 Signal and fill timing

| Step | Bar used | Source |
|---|---|---|
| Signal computation | `analyze(candles[:index])` — bars strictly **before** the fill bar | `backtest.py:139-142` |
| Entry fill price | `candles[index].open` | `backtest.py:145-149` |
| Exit detection bar | `candles[index - 1]` — the bar that has already closed | `backtest.py:159` |
| Exit fill price | `candles[index].open` | `backtest.py:184-186` |

So the signal is derived from closed bars and executed at the **next** candle's
open. No intrabar fills are assumed, so no future candle information is ever
used. `Signal.price` is overwritten with the fill open while the signal-bar close
is retained separately as `signal_close` (`models.py:36-39`).

### 6.3 Position sizing and the single-position rule

| Property | Value | Source |
|---|---|---|
| Sizing | `quantity = (cash × risk_fraction) / fill_price` | `simulator.py:92` |
| Base | **then-current cash**, not starting balance | `simulator.py:92` |
| Concurrent open positions | exactly **1**, always | `simulator.py:79-80`, `backtest.py:196` |

Exits are processed before entries in each iteration (`backtest.py:151` then
`:195`), so a close and an open can both occur on the same bar index. In Phase 10,
104 of 105 consecutive trade pairs had `next_entry_index == previous_exit_index`
(`experiments/phase11/SUMMARY.md:275-277`).

### 6.4 Exit precedence

Evaluated in this order (`backtest.py:158-181`):

| Order | Rule | Active at frozen config |
|---|---|---|
| 0 | `bars_held >= 1` — a position cannot exit on its entry bar | yes, `backtest.py:158` |
| 1 | `max_holding_bars` | **disabled**, default `None` |
| 2 | `stop_loss_pct` / `take_profit_pct` | **disabled**, defaults `None` |
| 3 | Opposite-side signal | **active** — the only live exit rule |

Stop and target levels, if ever enabled, are measured from `trade.entry_price`
(`backtest.py:51-60`). When one bar would breach both, the stop is assumed to be
hit first (`backtest.py:170-171`); because the fill is the next bar's open
either way, that ambiguity changes only the recorded label, never the P&L
(`backtest.py:106-109`).

### 6.5 End-of-data behaviour

Any position still open after the final bar is closed at
`candles[-1].close` with `exit_reason = "end_of_data"`
(`backtest.py:207-213`).

That trade is **retained and counted** in both the trade total and the exit
counts. It is never discarded (`walkforward.py:21-22`,
BOUNDARY_POLICY = `retain_boundary_force_closes`).

### 6.6 The exact invocation, frozen

Phase 29E is pre-specified as a single call with the baseline configuration only:

```python
result = run_backtest(
    candles,
    config=StrategyConfig(),
    starting_balance=10_000.0,
    risk_fraction=0.01,
    costs=TradingCosts(0.001, 0.0005),
    evaluation_start=48,
)
stats = create_report(result)
```

with `candles = load_ohlcv_csv("data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv")`.

**No A2-capable harness or comparison workflow may be invoked.** Phase 29E is
frozen to the single `run_backtest` call above, with `config=StrategyConfig()`
only. Four entry points in this repository are capable of evaluating A2, and
none of them may be used for this evaluation:

| A2-capable entry point | Where A2 enters | Status for Phase 29E |
|---|---|---|
| `validation_harness.main()` | Iterates `CONFIGURATIONS` = `(("baseline", BASELINE), ("A2_min_dist_0.002", A2))` (`validation_harness.py:42-45`); loop at `validation_harness.py:206-209` | **Forbidden.** Highest risk: it accepts any CSV path as `argv[1]` (`validation_harness.py:167`), so it would accept this holdout |
| `walkforward.a2_config()` and `PHASE13_CONFIGS` | `a2_config()` returns `replace(StrategyConfig(), min_breakout_distance=0.002)` (`walkforward.py:120-123`); `PHASE13_CONFIGS` binds `A2_NAME` to it (`walkforward.py:127-130`) | **Forbidden.** Importing or calling `a2_config` for any reason is out of scope |
| `phase13/run_walk_forward.py` | `PASSES` iterates `(BASELINE_NAME, baseline_config), (A2_NAME, a2_config)` (`run_walk_forward.py:76-79`) | **Forbidden.** It validates against `walkforward.DATASET_SHA256` (`run_walk_forward.py:49`), the 2024–2025 dataset digest, so it targets a different dataset entirely |
| `phase10/oos_interpretation.py` | Defines `BASE` and `A2` (`oos_interpretation.py:27-28`) and evaluates both (`oos_interpretation.py:63`) | **Forbidden.** It targets the consumed 2026-01…08 window, not this holdout |

The only permitted invocation is the frozen call in §6.6: one `run_backtest`,
one configuration, one dataset. Any workflow that evaluates two configurations
side by side is out of scope, and §7 explains why A2 is excluded from this
holdout.

### 6.7 Rules

- Use only the frozen holdout. No other dataset feeds this evaluation.
- Preserve strategy, cost and account settings exactly as tabulated above.
- No parameter selection, strategy change, filter, or exclusion based on results.
- No merging with the 2024–2025 dataset. `RESEARCH_STATE.json:400` classifies
  pooling consumed data to enlarge the sample as manufactured validation.
- No re-running this evaluation with variations and presenting the best result
  as independent validation.
- This holdout is **spent** the moment it is first used. It can never be
  re-obtained.

---

## 7. Configuration scope, and why A2 is excluded

**One configuration is evaluated: `baseline` (`StrategyConfig()` defaults).**

The `A2` variant — `replace(StrategyConfig(), min_breakout_distance=0.002)` —
exists in the repository (`validation_harness.py:40`, `walkforward.py:101`) and
is **deliberately not evaluated on this holdout**.

| Reason | Source |
|---|---|
| A2's `min_breakout_distance=0.002` was selected in Phase 7 by searching 12+ entry and exit variants on 2024–2025 | `RESEARCH_STATE.json:169`, `:289` |
| Comparing baseline and A2 again and calling the larger figure a winner is an explicitly recorded path that must not be treated as validation | Declaring array key `RESEARCH_STATE.json:394` (`paths_that_should_not_be_treated_as_validation`), specific entry `RESEARCH_STATE.json:397` |
| The two were never ranked and must not be ranked | `RESEARCH_STATE.json:267` |
| A2 has already been examined on the consumed 2026-01…08 window (90 trades, net +14.07) | `RESEARCH_STATE.json:257` |

On a single ~16-trade window, running two configurations and reporting both
would create a selection opportunity with no statistical support for it. The
baseline is evaluated alone.

---

## 8. Pre-specified metrics

Every metric below is computed by existing repository code. No new formula is
introduced.

### 8.1 Available, with exact definitions

| Metric | Source | Exact definition |
|---|---|---|
| Trade count | `stats.py:132` | `len(closed)` — trades where `net_pnl is not None` |
| Net P&L | `stats.py:133` | `sum(net_pnl)` over closed trades |
| Win rate | `stats.py:134-138` | `count(net_pnl > 0) / len(closed)`; zero-P&L trades count as neither win nor loss |
| Profit factor | `stats.py:139-143` | `gross_profit / gross_loss`; **`float("inf")` if there are no losing trades** |
| Average P&L | `stats.py:144-148` | `sum(net_pnl) / len(closed)` |
| Maximum drawdown | `stats.py:113-129`, `:149` | Maximum of `(peak_balance - balance) / peak_balance` over the **cumulative closed-trade net-P&L curve**, sampled once per closed trade in journal order. Returned as a **fraction**, not a percentage |
| Ending balance | `stats.py:150` | `starting_balance + sum(net_pnl)` |
| Total friction | `stats.py:7-27` | `sum(fee_total + spread_total + slippage_total)` — the correct gross→net bridge under either execution model |
| Fees / spread / slippage | `stats.py:30-45` | `sum` of the respective per-trade field |
| Full cost breakdown | `stats.py:48-57` | `fee_total`, `spread_total`, `slippage_total`, `total_friction`, `deducted_costs` |
| Gross P&L | `models.py:109-128` | `sum(trade.pnl)` — `(exit - entry) × quantity × direction`, **before** costs |
| Net P&L per trade | `models.py:130-137` | `pnl - costs` |
| Exit-reason counts | `backtest.py:190-192`, `:213` | `BacktestResult.exit_counts`, e.g. `{'opposite_signal': n, 'end_of_data': m}` |
| Monthly breakdown | `robustness.py:427-464` | Trades grouped by **entry** month; `return_pct = sum(nets) / starting_balance × 100` |

`create_report(result)` (`report.py:5-11`) simply calls
`performance(result.trades, starting_balance=result.starting_balance)`.

### 8.2 Return percentage — formula is not pinned by library code

**There is no `return_pct` key in `stats.performance()`.** The repository
computes it inline in the harness:

```
(ending_balance / START_BALANCE - 1) * 100
```

`validation_harness.py:128`. Phase 29E pre-specifies **that exact formula**, with
`START_BALANCE = 10_000.0`, so the value is reproducible even though no library
function defines it.

`monthly_breakdown` uses a different, deliberate convention:
`sum(nets) / starting_balance × 100` with a **fixed** denominator, not a
month-opening balance, to avoid implying compounding that did not occur
(`robustness.py:436-440`).

### 8.3 Ambiguities resolved in advance

| Item | Frozen resolution |
|---|---|
| "max drawdown" | The **closed-trade cumulative** measure from `stats.performance()`, reported as a percentage (fraction × 100). Not mark-to-market |
| `profit_factor` when no losing trade | Report the literal `inf` from `stats.performance()` **and** state "no losing trades, profit factor undefined". Do not substitute a large finite number |
| `win_rate` denominator | All closed trades, including zero-P&L trades |
| "total costs" | `total_friction`, **not** `deducted_costs`. Under `cost_deduction` they are equal; `total_friction` is the honest bridge |

Mark-to-market drawdown exists in `robustness.py` (`equity_curve_mark_to_market`,
`mark_to_market_drawdown`) and measured 1.12–1.16× the closed-trade measure on
2026 data (`phase11/SUMMARY.md:294-301`). It is **not** the primary metric here.
It may be reported as a secondary diagnostic only if declared at the time of
reporting, and must never replace or be compared against the primary figure
without saying so.

### 8.4 Not available, and not to be fabricated

| Requested metric | Status |
|---|---|
| Exposure / percent of time in market | **Deliberately not computed.** The repository refuses to fabricate it (`windowstats.py:8-12`): the pre-registration forbids estimating it |
| Sharpe ratio, Sortino, CAGR, annualised return | Do not exist anywhere in `crypto_paper_lab` |
| Return volatility | Does not exist |
| MAE / MFE | Two separate recorded decisions: classified as hindsight ("Confirmed MAE/MFE are hindsight", `phase15/RESEARCH_CHECKPOINT.md:220`), and excluded from instrumentation ("Explicitly **not** added: MAE/MFE, any outcome field, any threshold, any ATR or annualisation", `phase15/RESEARCH_CHECKPOINT.md:229-230`) |
| ATR / true range | `mean_candle_range` is explicitly a range proxy, not an ATR (`indicators.py:86-92`) |
| Per-trade return percentage | Only absolute currency P&L is tracked |
| Trailing drawdown duration, recovery factor, Ulcer index | Do not exist |
| Per-trade entry/exit timestamps | **Available** on `PaperTrade`; must be reported as the exact evaluated-candle window |

**Limitation.** Because exposure is not computed, the trade count cannot be
converted into a capital-efficiency statement. The result will describe *what
happened*, not *how efficiently capital was employed*.

---

## 9. Expected sample size, stated before the run

| Quantity | Value |
|---|---|
| Evaluated candles | 864 |
| Warm-up context bars (no trades) | 48 |
| Phase 10 baseline rate on the consumed 2026-01…08 window | 105 trades over 5,784 evaluated bars |
| **Implied trades at the same rate** | **≈ 15.7** |

Repository guidance on trade-count sufficiency
(`experiments/phase9/ACQUISITION_PLAN.md:135-146`) states that **fewer than ~50
trades makes any comparison inconclusive**, because the baseline profit factor
is below 1.0 and single-trade P&L spans roughly −6.92 to +27.33.

**On 2026 data a single baseline win reached 378.8% of that window's entire net
P&L, and the top three trades equalled 972.2%** (`phase11/SUMMARY.md`). On a
~16-trade window, a handful of trades will determine the headline figure
entirely.

---

## 10. Interpretation rules

These are binding on the Phase 29E report and are fixed in advance.

1. **The result is INCONCLUSIVE for establishing profitability.** This is
   declared now, before any number exists, and does not change afterwards.
2. **A positive outcome is not proof of a profitable edge.** It is one ~16-trade
   sample from one 38-day window on one venue.
3. **A negative outcome is not proof that the strategy can never work.** It is
   the same single small sample.
4. Trades are **mechanically clustered** — one position at a time, mean hold
   49–60 bars — so trades are **not independent observations**. Individual trades
   must never be presented as independent evidence.
5. **No p-value and no significance test will be reported.** The one-position-at-
   a-time design does not support the independence assumption such a test
   requires (`RESEARCH_STATE.json:402`; `phase14C` deliberately reports no
   p-value). A t-like ratio such as `mean/SE` with a 1.96 threshold
   (`phase10/oos_interpretation.py:31-48`) is a heuristic, **not** a t-test: no
   degrees-of-freedom correction, no normality check. It may be shown only if
   labelled as a heuristic, and never as a p-value or a pass/fail verdict.
6. Uncertainty and sample limitations must be reported **beside** every
   aggregate figure, never in a footnote.
7. **This holdout must not be used to tune or select parameters.** Any use that
   informs a strategy revision spends it permanently.
8. **Any future strategy revision requires a separate, genuinely unseen holdout**
   for independent evaluation. A revision evaluated on this window is not
   independent validation (`RESEARCH_STATE.json:363-366`).
9. The standing conclusion in §1 is not revised by this evaluation.
10. A result that contradicts the standing conclusion does not overturn it, and a
    result that agrees does not confirm it. One ~16-trade sample cannot do
    either.

---

## 11. Mandatory report contents

The Phase 29E report must contain all of the following. An aggregate figure must
never be presented without the supporting detail beside it.

| # | Required content |
|---|---|
| 1 | Dataset path, SHA-256, row count and UTC range, re-verified at run time |
| 2 | Exact Git commit and working-tree status at run time |
| 3 | Full `StrategyConfig` repr and the exact `run_backtest` arguments used |
| 4 | Exact evaluation window: first evaluable timestamp, last timestamp, evaluated candle count |
| 5 | Warm-up context range and the count of bars that produced no trades |
| 6 | Trade count |
| 7 | Net P&L and percentage return from the documented `10,000.0` starting balance |
| 8 | Win rate and profit factor, with the no-losses caveat if applicable |
| 9 | Maximum drawdown, explicitly labelled as the closed-trade measure |
| 10 | Gross P&L and total friction, with fees, spread and slippage itemised |
| 11 | Ending balance |
| 12 | Exit-reason counts, including any `end_of_data` force-close |
| 13 | Monthly breakdown from `robustness.monthly_breakdown` |
| 14 | Per-trade table: entry time, exit time, side, entry price, exit price, gross P&L, costs, net P&L, exit reason |
| 15 | An explicit statement that the result is **INCONCLUSIVE**, per §10 |
| 16 | Confirmation that no parameter, filter or rule was changed after seeing the result |

---

## 12. Integrity checks, performed at run time

Phase 29E must re-verify all of the following **before** the backtest runs, and
must abort without evaluating if any check fails.

| # | Check | Pass condition |
|---|---|---|
| 1 | Recompute dataset SHA-256 | equals `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` |
| 2 | Row count | exactly `912` |
| 3 | First / last timestamp | `2026-09-01 00:00:00` / `2026-10-08 23:00:00` |
| 4 | Every step exactly `3600` s | zero irregular intervals |
| 5 | Strictly increasing timestamps | zero duplicates, zero out-of-order |
| 6 | `validate_dataset(candles)` | passes (`dataset.py:33-72`) |
| 7 | `normalize_source(..., strict=True)` | clean, 912/912 accepted (`acquisition.py:315-320`) |
| 8 | Research-window overlap | zero rows in `2024-01-01 00:00` … `2025-12-31 23:00` (`acquisition.py:396-399`) |
| 9 | Consumed-OOS overlap | zero rows in `2026-01-01 00:00` … `2026-08-31 23:00` |
| 10 | `len(candles) >= WARMUP + 24` | `912 >= 72` |
| 11 | `minimum_history <= 48 < len(candles)` | `22 <= 48 < 912` |
| 12 | First evaluable bar strictly after `PHASE7_END` | `2026-09-03 00:00:00 > 2025-12-31 23:00` |
| 13 | Live `StrategyConfig()` defaults match §4 | every field equal |
| 14 | Live `TradingCosts` values match §5 | every field equal |
| 15 | Primary research dataset digest unchanged | `201A3B15…016B` (`walkforward.py:51-53`) |
| 16 | All 27 raw artefacts, checksums and provenance files unchanged | recomputed digests equal recorded digests |

### Preservation commitments

The following must be byte-identical before and after the evaluation:

- `research_engine/data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv`
- `…csv.report.txt` and `…csv.manifest.txt`
- all 9 `data/oos/raw/*.zip`, `*.zip.CHECKSUM`, `*.provenance.txt`
- `research_engine/data/BTCUSDT_1h_Cleaned (1).csv`
- `research_engine/data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv`
- every file in `experiments/`

The evaluation writes **new files only**, into `experiments/phase29/`. It must
not modify, move or delete anything that already exists.

---

## 13. Frozen reproducibility record

| Field | Frozen value |
|---|---|
| `dataset_path` | `data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` |
| `dataset_sha256` | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` |
| `dataset_candles` | `912` |
| `dataset_first` | `2026-09-01 00:00:00` |
| `dataset_last` | `2026-10-08 23:00:00` |
| `config_repr` | `StrategyConfig(asset='BTC/USDT', timeframe='1h', lookback=20, fast_period=5, slow_period=12, breakout_buffer=0.001, retest_tolerance=0.002, min_breakout_distance=0.0, trend_strength_min=0.001, retest_use_close=False, breakout_confirm_bars=1, max_holding_bars=None, stop_loss_pct=None, take_profit_pct=None, allowed_sides=None)` |
| `execution_model` | `cost_deduction` |
| `fee_rate` | `0.001` |
| `slippage_rate` | `0.0005` |
| `spread_rate` | `0.0` |
| `starting_balance` | `10_000.0` |
| `risk_fraction` | `0.01` |
| `warmup_rule` | `full_preceding_series` |
| `boundary_policy` | `retain_boundary_force_closes` |
| `evaluation_start_index` | `48` |
| `evaluated_candles` | `864` |
| `configurations_run` | `baseline` only |
| `git_commit` | `dccebbd53ee8365474345506db9099b13356b53c` |
| `python_version` | `3.12` |
| `platform` | Windows |
| `random_seed` | none — fully deterministic |
| `exclusions` | none |

---

## 14. Pre-registration summary

| Question this evaluation asks | Does the frozen baseline show positive net P&L after frozen costs on 864 genuinely unseen hourly candles? |
|---|---|
| Data | 912 Binance Vision BTC/USDT 1h candles, `2026-09-01` … `2026-10-08`, never previously examined |
| Configuration | `StrategyConfig()` defaults, unmodified |
| Costs | 0.1% fee + 0.05% slippage per leg, `cost_deduction` |
| Balance / risk | `10,000.0` / `0.01` of current cash |
| Warm-up | 48 context bars, no trades; evaluation starts `2026-09-03 00:00` |
| Expected trades | ~16 |
| Metrics | §8.1 only; unavailable metrics recorded, not fabricated |
| Decision rule | **None. There is no threshold, no pass/fail, no score, no ranking, no winner selection** |
| Certainty of outcome | **INCONCLUSIVE by construction**, declared in advance |

---

## 15. Known limitations of this design

Recorded now, before results, so they cannot be discovered later as excuses.

1. **The sample is too small by construction.** ~16 trades against a documented
   ~50-trade floor for even an inconclusive comparison. This is a data-supply
   limit, not a design choice.
2. **A single window supports no inference.** No walk-forward structure, no
   repeated windows, no resampling that would assume independence the design
   does not provide.
3. **The window cannot be extended.** Data from `2026-10-09` onward did not
   exist at freeze time; the 2026-10 monthly archive publishes in November 2026.
   Extending this evaluation would unfreeze the pre-registration.
4. **One venue, one asset, one timeframe.** Venue-specific effects cannot be
   separated from strategy performance.
5. **Cost model is stylised.** Flat proportional rates, no tiers, no partial
   fills, no spread, no impact, no funding, no borrow. Real friction would be
   different and probably worse.
6. **Hourly granularity hides intrabar sequence.** Stop/target fills at the next
   open, so intrabar ordering is unmodellable from this data.
7. **Warm-up uses the holdout's own first 48 bars.** The indicators are warmed
   on data from inside the holdout. This is unavoidable — the evaluation needs
   lookback — but it means the warm-up bars are not themselves untouched.
8. **No exposure metric.** Capital efficiency cannot be assessed (§8.4).
9. **The dataset is untracked.** A future checkout may alter its bytes via
   line-ending conversion (§2). The hash check must normalise before concluding
   the data changed.
10. **Mark-to-market drawdown is not the primary measure.** The two differ by
    12–16% on 2026 data, and only the closed-trade measure is pre-specified.
11. **A result here changes almost nothing.** The standing conclusion is
    robust to one ~16-trade sample in either direction. The main value of this
    evaluation is diagnostic, not decisive.
12. **This holdout is now documented in advance.** Its aggregate characteristics
    are described in the manifest before evaluation, so it can no longer be
    called perfectly virgin even though no performance was examined. It is
    honest and quantified, not hidden.

---

## 16. Status of this phase

Checks actually performed for this pre-registration:

| Check | Result |
|---|---|
| Dataset SHA-256 recalculated | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` — matches |
| Row count | 912 — matches |
| UTC range | `2026-09-01 00:00:00` … `2026-10-08 23:00:00` — matches |
| `validate_dataset()` | passed |
| Harness `inspect()` gate | accepted, 0 problems |
| Evaluated-window arithmetic | 864 bars, first evaluable `2026-09-03 00:00:00` |
| Configuration and metric definitions | read from source and cited by `file:line` |
| Git commit and working-tree status | recorded in §3 |

**No backtest, strategy run, or optimisation was performed. No holdout
performance figure has been calculated or observed.**

---

**End of pre-registration. No Phase 29D evaluation has been run. No Phase 29D
results exist.**