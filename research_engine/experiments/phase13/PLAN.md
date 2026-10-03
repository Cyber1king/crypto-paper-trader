# Phase 13 — Walk-Forward Validation Pre-Registration

**Status: PRE-REGISTRATION. No Phase 13 experiment has been run. No Phase 13
results exist.**

This document freezes the Phase 13 methodology **before** any walk-forward
evaluation is executed. It is written to be committed before implementation so
that the analysis design cannot be adjusted after seeing results.

Frozen at Git commit `f5293c91da33e929a230ff385ab4458cfa232fee`.

---

## 1. What Phase 13 is, and what it is not

Phase 13 is a **historical walk-forward diagnostic**.

It is **NOT** a fresh independent out-of-sample validation.

The reason is a matter of recorded fact. The repository has already used
2026-01-01 through 2026-08-31 in Phase 10:

| Fact | Value |
|---|---|
| Phase 10 OOS dataset | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| Range already examined | `2026-01-01 00:00:00` → `2026-08-31 23:00:00` (5,832 candles) |
| Recorded results | `experiments/phase10/RESULTS_interpretation.txt`, `SUMMARY.md`, `OOS_RESULTS.md` |

Consequently **2026 is not unseen data** and is excluded from the primary
Phase 13 evaluation. Any future window covering 2026 would be evaluated on a
period whose aggregate characteristics are already documented in this
repository, and could not honestly be described as virgin.

Phase 13 therefore measures how the strategy behaved across successive
historical sub-periods, each evaluated only after its boundaries were fixed.
It characterises behaviour. It does not certify an outcome.

### Standing research conclusion

No reliable profitability has been established. Phase 10 recorded the result as
"inconclusive, not a demonstrated improvement" and noted that roughly 90–105
trades cannot resolve the effect size involved. Phase 11 recorded ten
confidence intervals all containing zero, and stated explicitly that these are
"not proof of future performance". Phase 12 stated that improved execution
does not make the strategy suitable for real trading.

**Phase 13 does not revise that conclusion and must not be used to revise it.**

---

## 2. Frozen dataset

| Property | Frozen value |
|---|---|
Path | `research_engine/data/BTCUSDT_1h_Cleaned (1).csv` |
SHA-256 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
First candle | `2024-01-01 00:00:00` |
Last candle | `2025-12-31 23:00:00` |
Candles | `17,544` |
Timeframe | `1h` (verified: every step exactly 3600 s) |
Duplicate timestamps | 0 |
Calendar years | 2024 (8,784 candles, leap year), 2025 (8,760 candles) |

The hash was re-verified at the time this pre-registration was written and
matched the value above.

The harness must recompute this hash at load time and **abort** on mismatch.

### Excluded data

| Dataset | Reason for exclusion |
|---|---|
`data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` | Already used in Phase 10 |
`data/BTCUSDT_1h.csv` | Empty file, 2 bytes, unreferenced |

---

## 3. Frozen window structure

Six windows. Training windows roll forward by three calendar months;
evaluation windows are consecutive, non-overlapping calendar quarters covering
`2024-07-01` → `2025-12-31`.

| Window | Train start | Train end | Eval start | Eval end |
|---|---|---|---|---|
1 | `2024-01-01` | `2024-06-30` | `2024-07-01` | `2024-09-30` |
2 | `2024-04-01` | `2024-09-30` | `2024-10-01` | `2024-12-31` |
3 | `2024-07-01` | `2024-12-31` | `2025-01-01` | `2025-03-31` |
4 | `2024-10-01` | `2025-03-31` | `2025-04-01` | `2025-06-30` |
5 | `2025-01-01` | `2025-06-30` | `2025-07-01` | `2025-09-30` |
6 | `2025-04-01` | `2025-09-30` | `2025-10-01` | `2025-12-31` |

### Verified index ranges

Resolved against the frozen dataset at pre-registration time:

| Window | Train idx | Train candles | Eval idx | Eval candles | Warm-up candles before eval |
|---|---|---|---|---|---|
1 | 0–4367 | 4,368 | 4368–6575 | 2,208 | 4,368 |
2 | 2184–6575 | 4,392 | 6576–8783 | 2,208 | 6,576 |
3 | 4368–8783 | 4,416 | 8784–10943 | 2,160 | 8,784 |
4 | 6576–10943 | 4,368 | 10944–13127 | 2,184 | 10,944 |
5 | 8784–13127 | 4,344 | 13128–15335 | 2,208 | 13,128 |
6 | 10944–15335 | 4,392 | 15336–17543 | 2,208 | 15,336 |

Training candle counts vary because windows are defined by calendar month
boundaries, not by a fixed candle count. This is intentional and must not be
"corrected" to a uniform length.

### Verified constraints

| Constraint | Result |
|---|---|
All twelve boundaries resolve to real candles | ✅ |
Training ends strictly before evaluation begins | ✅ all six |
Evaluation windows do not overlap | ✅ contiguous, `6575 → 6576` etc. |
Evaluation windows cover `2024-07-01` → `2025-12-31` exactly | ✅ 13,176 candles |
No non-1h steps inside any evaluation window | ✅ 0 |
All windows inside dataset bounds | ✅ |
Warm-up availability ≥ required minimum (22) | ✅ minimum is 4,368 |

### Frozen rules

* Evaluation windows must not overlap.
* Training must end strictly before evaluation begins.
* **These dates must not be altered after seeing results.**
* Overlap between consecutive windows is **zero** for both training and
  evaluation.
* No window may be added, dropped, reordered or re-dated. If a window must be
  excluded for a data-integrity reason, the exclusion and its reason must be
  recorded in `EXPERIMENT_LOG.md` and in the results file.

---

## 4. Frozen warm-up policy

**Full preceding series + `evaluation_start`.**

For each window the backtest receives:

```
run_backtest(
    candles[:eval_end_index + 1],   # dataset start .. end of evaluation window
    config=<frozen>,
    costs=<frozen>,
    starting_balance=10000.0,
    risk_fraction=0.01,
    evaluation_start=eval_start_index,
)
```

### Rules

* The complete available dataset from its beginning through the end of the
  evaluation window is passed in. The series is **not** sliced to the
  evaluation period.
* `evaluation_start` prevents any entry before the evaluation boundary.
* `yearly.py` must **not** be used under any circumstances.
* The minimum warm-up is verified as 4,368 candles against a requirement of 22.

### Why this avoids a warm-up approximation

The engine's stated warm-up requirement is
`minimum_history = max(lookback + 2, slow_period) = max(22, 12) = 22` candles.
That is the minimum for the loop to start, **not** a guarantee that indicator
state is identical to a continuous run.

This was measured during the Phase 13 design audit. For a window beginning
2025-07-01, three constructions produced three different trade counts:

| Construction | Trades in window |
|---|---|
Full history + `evaluation_start` | 79 |
Naive slice of evaluation period only | 78 |
Slice with 48 warm-up candles | 80 |

A 22-candle or 48-candle warm-up prefix is therefore an **approximation** whose
error is unquantified and grows with lookback depth. Passing the full preceding
series removes the choice entirely: indicator state at the evaluation boundary
is exactly what a continuous run would have produced. No warm-up length needs
to be defended, because none is chosen.

### Consequence to accept

Because every window receives the full preceding series, indicator state at each
boundary is identical to a continuous run — which is the point — but the
windows are **not** independent in their indicator state. This must be stated
in the report as a limitation.

---

## 5. Frozen boundary policy

**Keep all evaluation windows and retain boundary force-closes.**

`run_backtest` closes any open position at the last candle it is given, with
`exit_reason="end_of_data"`. That behaviour is unchanged and is correct for a
windowed evaluation.

When a position is force-closed at an evaluation window boundary:

* **keep** the trade;
* **retain** `exit_reason="end_of_data"`;
* **count it separately** in an `end_of_data_count` metric;
* **report it** as a boundary-affected trade.

### Rules

* Do **not** discard windows because of their outcome.
* Do **not** discard trades because of their outcome.
* Do **not** discard the boundary trade to make a window look cleaner. Doing so
  would be outcome-dependent filtering.
* `end_of_data_count` must appear in the per-window table for every window.

### Measured magnitude

During the design audit, `end_of_data` accounted for roughly 2.0%–2.6% of
trades in sampled three-month windows, with arbitrary sign. It is small but
non-zero and is disclosed rather than removed.

---

## 6. Frozen configurations

Two separate, independently pre-registered passes. Each is a single-pass
evaluation. Neither is compared to the other for superiority.

### Pass A — baseline

```python
StrategyConfig()
```

All Phase 5–7 research gates at their V1-preserving defaults:
`lookback=20`, `fast_period=5`, `slow_period=12`, `breakout_buffer=0.001`,
`retest_tolerance=0.002`, `min_breakout_distance=0.0`, `trend_strength_min=0.001`,
`retest_use_close=False`, `breakout_confirm_bars=1`, `max_holding_bars=None`,
`stop_loss_pct=None`, `take_profit_pct=None`, `allowed_sides=None`.

### Pass B — A2

```python
StrategyConfig(min_breakout_distance=0.002)
```

Identical to Pass A except `min_breakout_distance=0.002`.

### Mandatory disclosure for Pass B

**A2 was selected during Phase 7 using 2024–2025 research data.** Phase 7
examined a grid of entry filters on that dataset and `min_breakout_distance=0.002`
was carried forward as configuration A2.

Five of the six evaluation windows (windows 2–6) fall entirely inside the
2024–2025 period that informed that selection.

Therefore:

* A2's Phase 13 results **must not** be described as clean independent
  validation.
* A2's results are a **re-evaluation on a period overlapping its own selection
  data**, and must be labelled as such wherever they appear.
* This contamination is pre-existing. Phase 13 can disclose it; it cannot
  undo it.

### Rules

* Do **not** choose between Pass A and Pass B after seeing Phase 13 results.
* Do **not** rank them.
* Do **not** declare either superior.
* Do **not** merge them into a single "best" configuration.
* Do **not** introduce any configuration beyond these two.

---

## 7. Frozen primary execution model

**`cost_deduction`**

| Parameter | Frozen value |
|---|---|
`execution_model` | `cost_deduction` |
`fee_rate` | `0.001` |
`slippage_rate` | `0.0005` |
`spread_rate` | `0.0` |

These values must remain **identical across all six windows in both passes**.
The harness must recompute a hash of the `TradingCosts` value at every
iteration and abort on any change.

### Rationale

1. This is the repository default and the model under which every Phase 5–11
   result was produced, so Phase 13 remains comparable with the whole record.
2. It is the only execution model for which historical results exist at all.
3. Switching models for Phase 13 would change the execution assumption
   mid-project and break comparability with every prior phase.

### Explicitly not part of this pre-registration

`fill_price` with a non-zero spread is **not** used in the primary experiment.

A future `fill_price` sensitivity analysis may be conducted, but it is a
**separate** exercise with its own plan, its own output files and its own
report. It is not authorised by this document and must not be run before the
primary result is recorded.

---

## 8. Frozen account assumptions

| Assumption | Frozen value |
|---|---|
Starting balance | `10000.0` |
Risk fraction | `0.01` |
Concurrent open trades | exactly one (enforced by `PaperBroker`) |
Leverage | none |
Margin | none |
Pyramiding / scaling in | none |

No compounding between windows: every window starts from `10000.0`. Each window
is an independent account.

---

## 9. Frozen leakage controls

The eventual harness must **raise an exception**, not warn, on any of the
following:

| # | Condition | Check |
|---|---|---|
1 | Evaluation begins before training ends | `train_end < eval_start` |
2 | Evaluation windows overlap | `eval_start[i] > eval_end[i-1]` |
3 | Evaluation outside dataset bounds | `eval_end <= dataset_last`, `eval_start >= dataset_first` |
4 | Duplicate timestamps | `len(ts) == len(set(ts))` |
5 | Non-1h intervals | every step exactly 3600 s |
6 | Dataset hash mismatch | recomputed SHA-256 equals the frozen value |
7 | Configuration changed mid-run | config hash identical at every iteration |
8 | Execution costs changed mid-run | costs hash identical at every iteration |
9 | Entries before `evaluation_start` | count of trades with `entry_time < eval_start` equals 0 |
10 | Dirty Git working tree | `git status --porcelain` empty |
11 | Strategy defaults changed | frozen `StrategyConfig` defaults still equal their Phase 12 values |

Additional mandatory controls:

* A **fresh `PaperBroker` per evaluation window**. No position, cash or
  indicator state carries between windows.
* **`yearly.py` must never be used.** It resets warm-up per calendar year and
  force-closes at year boundaries; it is not walk-forward.
* Insufficient warm-up (`candles_before_eval < 22`) must raise.
* A window extending past the dataset end must raise. (This check exists
  because an earlier draft design would have generated windows running to
  2026-10-01 and 2026-12-31, past the data.)

---

## 10. Frozen metrics

Recorded for **every** window in **both** passes.

### Currently available in `stats.performance()` / `stats.cost_breakdown()`

| Metric | Source |
|---|---|
`trades` | `performance()["trades"]` |
`win_rate` | `performance()` |
`profit_factor` | `performance()` — guard non-finite when gross loss is 0 |
`average_pnl` | `performance()` |
`max_drawdown` | `performance()` (trade-close basis) |
`ending_balance` | `performance()` |
`fee_total` | `cost_breakdown()` |
`spread_total` | `cost_breakdown()` |
`slippage_total` | `cost_breakdown()` |
`total_friction` | `cost_breakdown()` |
`gross_pnl` | Σ `trade.pnl` per trade |
`net_pnl` | `performance()["net_pnl"]` |
`exit_counts` | `BacktestResult.exit_counts` |
`first_entry` | earliest `trade.entry_time` |
`last_exit` | latest `trade.exit_time` |

### Must be implemented for Phase 13

| Metric | Note |
|---|---|
`median_pnl` | **Not currently available.** Must be added. |
`bars_held` mean / median | Available per trade via `PaperTrade.bars_held` |
`end_of_data_count` | Count of `exit_reason == "end_of_data"` |
Window boundaries and candle counts | Window metadata |

`median_pnl` must be added to `stats.py` as a purely additive change. Existing
keys and values must not change.

### Not available and not to be fabricated

**Exposure / percent of time in market.** No market-time accounting exists in
`stats.py`. Deriving it from `bars_held` would be an approximation that ignores
gaps and intrabar paths. It is excluded rather than estimated. If a later phase
introduces it, it must be labelled an approximation.

### Status of all metrics

**Every metric above is descriptive.**

There is:

* **no** profitability threshold;
* **no** pass/fail score;
* **no** ranking of configurations;
* **no** winner selection.

No metric may be used to accept or reject a configuration.

---

## 11. Frozen aggregation requirements

The eventual Phase 13 report must contain all eight of the following:

1. **Complete per-window table** — one row per window per pass, including every
   metric in section 10. This is the primary artefact and must not be
   summarised away.
2. **Positive / negative / zero window counts**, stated as counts and always
   displayed adjacent to the per-window table.
3. **Minimum, maximum and median** window net P&L.
4. **Full sorted list** of window net P&L values.
5. **Full sorted list** of window profit factors.
6. **Aggregate results**, explicitly labelled as a sum over sequential
   historical windows, not independent draws, with the precision caveat stated.
7. **Consecutive same-sign window runs** — longest run and full run sequence.
8. **Limitations and uncertainty.**

An aggregate figure must never be presented without the per-window table and
the sign counts beside it.

### Confidence intervals

**No window-level confidence interval will be produced.** With six windows,
such an interval is not methodologically defensible.

If a **trade-level** bootstrap interval is later calculated using the existing
`robustness.block_bootstrap_ci` (repository default `block_length=10`,
`n_resamples=10000`, `seed=20260101`), it must be labelled:

> Describes uncertainty within this historical sample. Not evidence of future
> performance.

This mirrors the wording Phase 11 already adopted. Any interval must use a
**pre-declared** block length; the block length must not be varied until a
favourable interval appears.

---

## 12. Frozen multiple-testing controls

### Recorded history

| Phase | Contribution |
|---|---|
Phase 5 | Added 4 research gates (`min_breakout_distance`, `trend_strength_min`, `retest_use_close`, `breakout_confirm_bars`) |
Phase 6 | Added 3 exit rules (`max_holding_bars`, `stop_loss_pct`, `take_profit_pct`) |
Phase 7 | Examined **12 configurations**; selected `A2 = min_breakout_distance=0.002` on 2024–2025 data |
Phase 10 | Evaluated baseline and A2 on 2026 OOS |
Phase 11 | Robustness and dependence analysis |
Phase 12 | Changed execution semantics and introduced spread |

### Standing risks

* Phase 5–7 already introduced multiple research configurations.
* Phase 7 examined 12 configurations.
* **A2 was selected using 2024–2025 research data.**
* **Phase 13 cannot erase that selection history.** Five of six evaluation
  windows lie inside the selection period.
* Phase 13 results must **not** be used to repeatedly modify the strategy until
  a preferred result appears.

### Controls

* This pre-registration is committed **before** any Phase 13 implementation or
  run. It is the pre-registration record.
* The harness must refuse to run if the configuration, execution model, window
  dates or metric set differ from this document.
* Every variant attempted must get its **own** report and output files.
* **Never overwrite previous results.** Re-running with any modified parameter
  requires new filenames.
* All results are written to the results file **before** any interpretation,
  including negative windows.
* Discarding any window or variant requires a written reason referencing a
  pre-declared rule in this document, never a disappointing number.

---

## 13. Frozen reproducibility record

Every future Phase 13 result must record, per window and in aggregate:

| Field | Frozen value where applicable |
|---|---|
`dataset_path` | `data/BTCUSDT_1h_Cleaned (1).csv` |
`dataset_sha256` | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
`dataset_first` | `2024-01-01 00:00:00` |
`dataset_last` | `2025-12-31 23:00:00` |
`dataset_candles` | `17544` |
`window_index` | 1–6 |
`train_start` / `train_end` | per section 3 |
`eval_start` / `eval_end` | per section 3 |
`config_repr` | full `repr(StrategyConfig)` |
`config_hash` | hash of the config value |
`execution_model` | `cost_deduction` |
`fee_rate` | `0.001` |
`slippage_rate` | `0.0005` |
`spread_rate` | `0.0` |
`starting_balance` | `10000.0` |
`risk_fraction` | `0.01` |
`warmup_rule` | `full_preceding_series` |
`boundary_policy` | `retain_boundary_force_closes` |
`git_commit` | `f5293c91da33e929a230ff385ab4458cfa232fee` |
`git_clean` | `git status --porcelain` empty |
`python_version` | recorded at runtime |
`platform` | recorded at runtime |
`random_seed` | `null` — the walk-forward itself is deterministic |
`bootstrap_seed` | `20260101` if and only if a bootstrap interval is computed |
`exclusions` | list, with reasons; `none` if empty |
All section 10 metrics | per window |

Reference environment at pre-registration time: Python `3.12.10`,
platform `Windows-11-10.0.26200-SP0`.

**Determinism requirement.** The walk-forward uses no randomness. Two runs at
the same commit and dataset must produce byte-identical results files. This
must be asserted by a test.

---

## 14. Pre-registration summary

| Item | Frozen value |
|---|---|
Character | Historical walk-forward diagnostic — **not** fresh OOS |
Dataset | `data/BTCUSDT_1h_Cleaned (1).csv`, SHA-256 `201A3B15…BA016B` |
Range | `2024-01-01 00:00:00` → `2025-12-31 23:00:00`, 17,544 candles |
2026 data | **Excluded** — already used in Phase 10 |
Windows | 6 (train 6 months rolling, eval 3 months, step 3 months, overlap 0) |
Eval coverage | `2024-07-01` → `2025-12-31`, 13,176 candles |
Warm-up | Full preceding series + `evaluation_start`; `yearly.py` forbidden |
Boundary | Retain and count `end_of_data`; discard nothing |
Passes | Baseline and A2, both pre-registered, not ranked |
A2 disclosure | Selected in Phase 7 on 2024–2025; not clean validation |
Execution | `cost_deduction`, fee 0.001, slippage 0.0005, spread 0.0 |
Account | 10000.0 start, 0.01 risk, one position, no leverage/margin/pyramiding |
Metrics | 17 recorded, all descriptive, no thresholds |
Window-level CI | **Not permitted** (n=6) |
Git commit | `f5293c91da33e929a230ff385ab4458cfa232fee` |

---

## 15. Known limitations of this design

Recorded now, before results, so they cannot be discovered later as excuses.

1. **Six windows is a small number.** Window-level inference is not supported.
2. **Roughly 43 trades per evaluation window** (measured range 36–52 during the
   design audit). Per-window metrics will be noisy, and `profit_factor` is
   especially unstable in any window containing few or no losing trades.
3. **Boundary force-closes affect a small non-zero share** of window trades
   (measured 2.0%–2.6%) with arbitrary sign.
4. **A2 is contaminated** for windows 2–6 by its own Phase 7 selection.
5. **Windows are sequential, not independent draws.** Aggregate statistics
   across them overstate precision.
6. **Indicator state is shared across boundaries** by design (section 4).
7. **Only 24 of the 32 available months** are usable for a clean walk-forward.
8. **Single asset, single timeframe, single market regime.** No conclusion can
   generalise beyond BTC/USDT 1h over this period.
9. **Exposure cannot be measured** from the current code.
10. **Phase 13 is retrospective.** It cannot provide evidence about any period
    after `2025-12-31`.

---

**End of pre-registration. No Phase 13 experiment has been run. No Phase 13
results exist.**