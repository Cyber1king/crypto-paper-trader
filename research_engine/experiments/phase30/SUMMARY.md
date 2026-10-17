# Phase 30B — Frozen Baseline Holdout Evaluation

**Status: EXECUTION COMPLETE. One evaluation, run once, exactly as pre-registered.**
No parameter was tuned, no configuration was varied, and no second run was made.

This is the execution of `experiments/phase29/PREREGISTRATION.md` §6.6. The
pre-registration is a frozen input and was **not** modified: its SHA-256 is
`b06f36e21df0fe403e3a75cbf8c3de84161607348966d622b65ea3f51bf217cc` before and
after this run.

---

## 1. Headline result

| Metric | Value |
|---|---|
| Trade count | **20** |
| Net P&L after costs | **−12.32** |
| Return from 10,000.0 | **−0.1232%** |
| Ending balance | **9,987.68** |
| Win rate | **25.00%** (5W / 15L / 0 flat) |
| Profit factor | **0.4925** |
| Maximum drawdown (closed-trade) | **0.1577%** |
| Gross P&L | **−6.32** |
| Total friction | **6.00** |
| Exit-reason counts | `{'opposite_signal': 19, 'end_of_data': 1}` |

**Verdict: INCONCLUSIVE.** Declared in advance in §10.1 of the
pre-registration and unchanged by this result.

---

## 2. Interpretation — mandatory report item 15

The pre-registered interpretation is applied here without adjustment.

1. **The result is INCONCLUSIVE for establishing profitability.** This was
   declared before any number existed and does not change afterwards.
2. **A negative outcome is not proof that the strategy can never work.** It is
   one 20-trade sample from one 38-day window on one venue (§10.3).
3. **Trades are not independent observations.** One position at a time, mean
   hold far exceeding the sample, so the 20 trades are mechanically clustered
   (§10.4). They must not be read as 20 independent pieces of evidence.
4. **No p-value and no significance test is reported**, because the
   one-position-at-a-time design does not support the independence assumption
   such a test requires (§10.5, `RESEARCH_STATE.json:402`).
5. **The standing conclusion is not revised** (§10.9). This evaluation neither
   overturns nor confirms it. One 20-trade sample cannot do either (§10.10).
6. **This holdout is now spent.** It cannot inform any parameter selection or
   strategy revision without permanently ceasing to be out-of-sample (§6.7,
   §10.7). Any future revision requires a separate, genuinely unseen holdout
   (§10.8).

The honest summary is: **the frozen baseline lost a small amount of money on this
window, and that observation is too small and too short to support any
conclusion about the strategy's edge.**

---

## 3. Frozen inputs — mandatory report items 1, 2

| Property | Value |
|---|---|
| Dataset path | `data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` |
| Dataset SHA-256 | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` — **re-verified at run time** |
| Row count | 912 — re-verified |
| UTC range | `2026-09-01 00:00:00` → `2026-10-08 23:00:00` — re-verified |
| Pre-registration | `experiments/phase29/PREREGISTRATION.md` |
| Pre-registration SHA-256 | `b06f36e21df0fe403e3a75cbf8c3de84161607348966d622b65ea3f51bf217cc` — unchanged |
| Git commit | `dccebbd53ee8365474345506db9099b13356b53c` |
| Working tree at run time | 0 modified, 0 staged, 0 deleted tracked files |
| Python | 3.12 |
| Random seed | none — the backtest is fully deterministic |
| Backtests executed | **1** |

All 16 integrity gates of pre-registration §12 were executed **before** the
backtest and all 16 passed. A first implementation of gate 16 aborted the run
before any evaluation; that gate was mis-scoped by the operator (see §9) and was
corrected to the gate as written, after which all 16 passed.

---

## 4. Configuration and execution path — mandatory report item 3

Exactly the call pre-registered in §6.6:

```python
result = run_backtest(
    candles,                                   # load_ohlcv_csv(holdout)
    config=StrategyConfig(),
    starting_balance=10_000.0,
    risk_fraction=0.01,
    costs=TradingCosts(0.001, 0.0005),
    evaluation_start=48,
)
stats = create_report(result)
```

| Field | Value |
|---|---|
| `config_repr` | `StrategyConfig(asset='BTC/USDT', timeframe='1h', lookback=20, fast_period=5, slow_period=12, breakout_buffer=0.001, retest_tolerance=0.002, min_breakout_distance=0.0, trend_strength_min=0.001, retest_use_close=False, breakout_confirm_bars=1, max_holding_bars=None, stop_loss_pct=None, take_profit_pct=None, allowed_sides=None)` |
| `execution_model` | `cost_deduction` |
| `fee_rate` / `slippage_rate` / `spread_rate` | `0.001` / `0.0005` / `0.0` |
| `starting_balance` / `risk_fraction` | `10_000.0` / `0.01` |
| `evaluation_start` | `48` |
| `warmup_rule` | `full_preceding_series` |
| `boundary_policy` | `retain_boundary_force_closes` |
| Configurations run | **`baseline` only** |

Every `StrategyConfig` field and every `TradingCosts` field was compared against
the live classes at run time and matched the frozen record exactly.

### No alternative strategy was run

- One `run_backtest` call exists in the run script; the backtest executed once.
- `StrategyConfig()` defaults only. No `replace(...)`, no `min_breakout_distance`
  override.
- `validation_harness.main()`, `walkforward.a2_config()`, `phase13/run_walk_forward.py`
  and `phase10/oos_interpretation.py` were **not invoked**, per §6.6.
- Only one dataset was loaded. No pooling with 2024–2025 or with the consumed
  2026-01…08 OOS.

---

## 5. Evaluation window — mandatory report items 4, 5

| Property | Value |
|---|---|
| Warm-up context (produced no trades) | `2026-09-01 00:00:00` → `2026-09-02 23:00:00`, 48 bars |
| First evaluable bar | `2026-09-03 00:00:00` |
| Last bar | `2026-10-08 23:00:00` |
| **Evaluated candles** | **864** |

The account starts flat with the full 10,000.0 at the boundary. No balance
carries over from warm-up bars.

---

## 6. Full pre-registered metric set — mandatory report items 6–13

| Metric | Value | Definition source |
|---|---|---|
| Trade count | 20 | `stats.py:132` |
| Net P&L | −12.32 | `stats.py:133` |
| Percentage return | −0.1232% | `(ending_balance / 10000.0 − 1) × 100`, per `validation_harness.py:128` |
| Ending balance | 9,987.68 | `stats.py:150` |
| Win rate | 25.00% | `stats.py:134-138` |
| Profit factor | 0.4925 | `stats.py:139-143` |
| Average P&L per trade | −0.6161 | `stats.py:144-148` |
| Maximum drawdown | 0.1577% | `stats.py:113-129` — **closed-trade cumulative curve**, not mark-to-market |
| Gross P&L | −6.32 | `models.py:109-128`, before costs |
| Total friction | 6.00 | `stats.py:7-27` |
| — fees | 4.00 | `stats.py:30-33` |
| — spread | 0.00 | `stats.py:36-39` |
| — slippage | 2.00 | `stats.py:42-45` |
| — deducted costs | 6.00 | `stats.py:48-57` |
| Exit-reason counts | `opposite_signal` 19, `end_of_data` 1 | `backtest.py:190-192`, `:213` |

**Bridge check.** `gross P&L − total friction = −6.322857 − 6.000000 =
−12.322857`, which equals net P&L to 0.00e+00. The gross→net bridge is exact.

### Undefined versus zero

Every reported metric is **defined**. No metric is undefined in this run:

- **Profit factor is defined** (0.4925) because there were 15 losing trades. Had
  there been none, `stats.performance()` returns `float("inf")` and that would be
  reported as undefined, not as a large finite number.
- **Spread is `0.00`, and that is a real zero, not undefined**: under
  `cost_deduction` the spread cannot be separated from slippage and is zero by
  construction (`costs.py:77-82`).
- **No metric is silently coerced.** Nothing was substituted for a missing value.

**A ratio that is deliberately NOT reported.** `total friction / gross P&L` is
6.00 / −6.32, which is not a meaningful quantity when gross P&L is negative. Phase
10 quoted this ratio only because its gross P&L was positive. It is therefore
omitted here rather than presented as a percentage. Friction is reported in
absolute terms, which is unambiguous.

### Monthly breakdown — mandatory report item 13

From `robustness.monthly_breakdown`, trades grouped by **entry** month:

| Month | Trades | Net P&L | Gross P&L | Costs | Return | W/L | Sign |
|---|---|---|---|---|---|---|---|
| 2026-09 | 17 | −12.41 | −7.30 | 5.11 | −0.1241% | 4/13 | negative |
| 2026-10 | 3 | +0.09 | +0.98 | 0.89 | +0.0009% | 1/2 | positive |

October covers only 2026-10-02 onward for entry purposes and holds 3 trades. One
positive month out of two, from 3 trades, is not evidence of anything.

### Uncertainty — mandatory report item 8 context

Reported as the §10.5 **heuristic only**. It is **not** a p-value and **not** a
t-test: no degrees-of-freedom correction, no normality check, and the
underlying trades are not independent.

| Quantity | Value |
|---|---|
| n | 20 |
| Mean net per trade | −0.6161 |
| Stdev | 2.0307 |
| Standard error | 0.4541 |
| mean/SE | −1.3569 |
| 95% band | `[−1.5061, +0.2738]` |

**The band contains zero.** The heuristic ratio is also below the 1.96 magnitude
that Phase 10's heuristic would flag. No significance verdict is drawn, per
§10.5.

### Distribution and concentration

The pre-registration §9 warned in advance that a handful of trades would
determine the headline figure. That is exactly what happened:

| Quantity | Value |
|---|---|
| Median net per trade | **−1.4220** |
| Best trade | +4.47 |
| Worst trade | −3.17 |
| Gross profit (5 winners) | +11.96 |
| Gross loss (15 losers) | −24.28 |
| Three best trades combined | +10.80, i.e. 87.6% of the total loss magnitude |

The three best trades earned +10.80 while the fifteen losers lost −24.28. The
result is driven by a handful of positions, and the median trade was negative.

---

## 7. Per-trade table — mandatory report item 14

Full machine-readable version in `RESULTS_trades.csv`.

| # | Entry (UTC) | Exit (UTC) | Side | Entry px | Exit px | Gross | Costs | Net | Exit reason |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-03 13:00 | 2026-09-04 14:00 | long | 78652.37 | 79378.66 | +0.92 | 0.3014 | +0.62 | opposite_signal |
| 2 | 2026-09-04 14:00 | 2026-09-05 17:00 | short | 79378.66 | 80041.99 | −0.84 | 0.3013 | −1.14 | opposite_signal |
| 3 | 2026-09-05 17:00 | 2026-09-07 16:00 | long | 80041.99 | 78822.00 | −1.52 | 0.2977 | −1.82 | opposite_signal |
| 4 | 2026-09-07 16:00 | 2026-09-09 05:00 | short | 78822.00 | 79171.50 | −0.44 | 0.3006 | −0.74 | opposite_signal |
| 5 | 2026-09-09 05:00 | 2026-09-10 13:00 | long | 79171.50 | 76896.01 | −2.87 | 0.2956 | −3.17 | opposite_signal |
| 6 | 2026-09-10 13:00 | 2026-09-11 13:00 | short | 76896.01 | 78032.98 | −1.48 | 0.3020 | −1.78 | opposite_signal |
| 7 | 2026-09-11 13:00 | 2026-09-13 09:00 | long | 78032.98 | 76813.71 | −1.56 | 0.2974 | −1.86 | opposite_signal |
| 8 | 2026-09-13 09:00 | 2026-09-14 10:00 | short | 76813.71 | 78141.57 | −1.73 | 0.3023 | −2.03 | opposite_signal |
| 9 | 2026-09-14 10:00 | 2026-09-15 07:00 | long | 78141.57 | 77286.71 | −1.09 | 0.2980 | −1.39 | opposite_signal |
| 10 | 2026-09-15 07:00 | 2026-09-18 04:00 | short | 77286.71 | 77383.47 | −0.13 | 0.2998 | −0.42 | opposite_signal |
| 11 | 2026-09-18 04:00 | 2026-09-20 03:00 | long | 77383.47 | 80331.52 | +3.80 | 0.3053 | +3.50 | opposite_signal |
| 12 | 2026-09-20 03:00 | 2026-09-21 01:00 | short | 80331.52 | 81607.72 | −1.59 | 0.3021 | −1.89 | opposite_signal |
| 13 | 2026-09-21 01:00 | 2026-09-23 13:00 | long | 81607.72 | 85510.90 | +4.78 | 0.3068 | +4.47 | opposite_signal |
| 14 | 2026-09-23 13:00 | 2026-09-27 08:00 | short | 85510.90 | 84790.99 | +0.84 | 0.2985 | +0.54 | opposite_signal |
| 15 | 2026-09-27 08:00 | 2026-09-28 02:00 | long | 84790.99 | 83694.42 | −1.29 | 0.2978 | −1.59 | opposite_signal |
| 16 | 2026-09-28 02:00 | 2026-09-30 13:00 | short | 83694.42 | 85290.32 | −1.91 | 0.3026 | −2.21 | opposite_signal |
| 17 | 2026-09-30 13:00 | 2026-10-02 19:00 | long | 85290.32 | 84262.01 | −1.20 | 0.2979 | −1.50 | opposite_signal |
| 18 | 2026-10-02 19:00 | 2026-10-04 10:00 | short | 84262.01 | 85233.84 | −1.15 | 0.3014 | −1.45 | opposite_signal |
| 19 | 2026-10-04 10:00 | 2026-10-07 02:00 | long | 85233.84 | 84391.49 | −0.99 | 0.2981 | −1.29 | opposite_signal |
| 20 | 2026-10-07 02:00 | 2026-10-08 23:00 | short | 84391.49 | 81754.45 | +3.12 | 0.2949 | +2.83 | **end_of_data** |

Trade 20 is the retained boundary force-close, closed at the final candle's close
per BOUNDARY_POLICY `retain_boundary_force_closes`. It is counted, not discarded.

Exits are processed before entries, so a close and an open share a bar timestamp;
19 of the 20 trades show the same entry and exit bar as their predecessor, the
expected behaviour from §6.3.

---

## 8. Confirmation — mandatory report item 16

**No parameter, filter, rule, cost, or configuration was changed after seeing the
result.** Nothing was changed at any point. The configuration, costs, balance,
risk fraction, warm-up and evaluation start were taken from the frozen
pre-registration before execution and verified field-by-field against the live
classes at run time.

No metric was selected after seeing results; the full §8.1 set is reported above
including figures that are unfavourable.

---

## 9. Operator note on a gate failure that was mine, not the data's

The first execution of integrity gate 16 **failed and correctly aborted the run
before any backtest was performed**. The cause was an operator error in the gate
implementation, not data corruption: it globbed all 17 `.zip` files in
`data/oos/raw/` and required each to appear in the Phase 29C manifest.

`data/oos/raw/` legitimately contains **17** archives — 8 pre-existing Phase 10
monthly files (2026-01…08) that predate the manifest, plus the 9 new Phase 29
files. Investigation established:

- all 17 archives have `local == published` for their `.CHECKSUM` — no
  integrity failure anywhere;
- the 8 pre-existing archives verify against **their own** provenance sidecars
  with zero discrepancies;
- all 27 Phase 29 artefacts (9 zip + 9 CHECKSUM + 9 provenance) are present, and
  all 9 archives match both their published checksum and the manifest.

Gate 16 was then implemented as the pre-registration actually specifies — "all
**27** raw artefacts" — plus the extra check of the 8 pre-existing archives
against their own sidecars. All 16 gates passed and the evaluation ran.

Recorded here because a gate failure that aborts a frozen-protocol run must be
disclosed rather than quietly corrected. No data was repaired, altered or
regenerated at any point.

---

## 10. Artefacts

Written to `research_engine/experiments/phase30/`, kept separate from the frozen
inputs in `experiments/phase29/` and `data/oos/`:

| File | Contents |
|---|---|
| `RESULTS_holdout.txt` | Human-readable execution record with all frozen inputs and metrics |
| `RESULTS_holdout.json` | Machine-readable full result, provenance and gate record |
| `RESULTS_trades.csv` | Per-trade table |
| `SUMMARY.md` | This report |

**Placement note.** Pre-registration §12 says results are written into
`experiments/phase29/`. They were placed in `experiments/phase30/` instead,
because the pre-registration itself is a frozen input with a recorded digest and
Phase 30B requires results "clearly separated from the frozen inputs". No existing
file was modified, moved or deleted; §12's preservation commitments are intact.

The run script lives in `%TEMP%\opencode\p30b_run.py` and is not part of the
repository.

---

## 11. Standing conclusion

Unchanged, as §10.9 requires.

> No reliable profitability has been established for this strategy
> (`experiments/phase15/RESEARCH_STATE.json:14`).

This holdout adds one more genuinely unseen window in which the frozen baseline
was slightly negative after costs. On 20 clustered trades across 38 days, with a
95% band spanning zero and a negative median trade, that observation is
consistent with the standing conclusion and **does not revise it in either
direction**.

The holdout is now spent.