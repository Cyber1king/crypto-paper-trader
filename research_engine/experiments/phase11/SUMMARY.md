# Phase 11 — Robustness Research

## 1. Executive summary

Phase 10 established that both configurations produced small positive results
on unseen 2026 data. This phase asks **how much those results can be
trusted**. The answer is: very little.

Four findings, all measured:

1. **Every confidence interval contains zero.** Mean-trade 95% intervals
   contain zero at all five block lengths tested and under both resampling
   methods, for both configurations. The total-P&L intervals are far wider
   than the point estimates: baseline +$5.05 has a 95% interval of
   **[−$64.32, +$69.76]**.
2. **Results are extremely concentrated.** Baseline's largest single win is
   **+378.8% of its entire net P&L**. The top three wins are **+972.2%**.
   Remove the single largest losing trade and baseline's net becomes **−$1.14**,
   i.e. slightly negative.
3. **The median trade is negative for both configurations** (baseline
   −$0.89, A2 −$0.96). The positive mean exists only because of a thin tail
   of large winners, not because most trades profit.
4. **Monthly results are evenly split**: 4 positive and 4 negative months for
   both, with a range of roughly 0.31% of the balance.

Both configurations were clearly negative across 2024–2025 and marginally
positive in 2026, with **no change to the strategy between those periods**.
The sign tracks the market regime.

Mark-to-market drawdown is only 1.12–1.16x the existing closed-trade measure,
so the legacy metric does not materially understate risk here. It remains a
small number only because `risk_fraction` is 0.01.

**No strategy was selected, tuned, or recommended in this phase.**

## 2. Dataset and evaluation window

| Item | Value |
|---|---|
| File | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| SHA-256 | `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437` |
| File range | 2026-01-01 00:00 → 2026-08-31 23:00 (5,832 candles) |
| Warm-up (excluded from trading) | 2026-01-01 00:00 → 2026-01-02 23:00 (48 bars) |
| **Validation window** | **2026-01-03 00:00 → 2026-08-31 23:00 (5,784 bars)** |
| Starting balance | $10,000.00 |
| Costs | fee 0.001, slippage 0.0005 |
| Position sizing | `risk_fraction = 0.01` |
| Execution | Next-candle open, closed candles only |

The evaluation covers **January–August 2026 only** — one asset, one
timeframe, roughly eight months.

## 3. Frozen configurations

Verified programmatically before analysis. The script aborts on mismatch.

| Field | Baseline | A2 |
|---|---|---|
| lookback | 20 | 20 |
| fast_period | 5 | 5 |
| slow_period | 12 | 12 |
| breakout_buffer | 0.001 | 0.001 |
| retest_tolerance | 0.002 | 0.002 |
| min_breakout_distance | **0.0** | **0.002** |
| trend_strength_min | 0.001 | 0.001 |
| retest_use_close | False | False |
| breakout_confirm_bars | 1 | 1 |
| max_holding_bars / stop_loss_pct / take_profit_pct | None | None |
| allowed_sides | None | None |

**Result: baseline matches the specification exactly, and A2 differs from
baseline in exactly one field (`min_breakout_distance`).** No discrepancy
found.

**Phase 10 reproduction check (run before any new analysis): all 12 figures
matched** — baseline 105 trades / $5.05 / 34.29% / 1.0424 / 0.34% / $10,005.05
and A2 90 trades / $14.07 / 36.67% / 1.1330 / 0.31% / $10,014.07.

## 4. Methods and assumptions

### 4.1 Mark-to-market drawdown

The existing `stats.performance()` updates equity **only when a trade
closes**, so intra-trade equity changes are invisible to it. Phase 11 adds a
separate mark-to-market measure. **The existing metric is unchanged** and a
test asserts the two agree.

Conventions, chosen to stay as close to the existing engine as the data
allows:

- **Unrealised P&L is gross** (before fees and slippage), because the engine
  recognises all costs at closure. The consequence is that the MTM curve is
  slightly optimistic relative to the realised result by roughly the
  entry-side cost while a trade is open.
- Equity is sampled at each candle **close**. Intrabar highs and lows are
  **not** used — no intrabar execution data exists, and inventing it would
  overstate the drawdown.
- Cash is credited only at closure, exactly as the engine does.
- A trade still open on the final candle is valued at that close, which is
  the price the engine uses to force-close it.
- Flat stretches carry the last realised equity forward.
- Exactly one sample per candle.

### 4.2 Block bootstrap

- **Resampling unit:** one block of `block_length` **consecutive trades**,
  drawn with replacement from all overlapping starting positions
  (moving-block bootstrap), concatenated and truncated to the original
  length.
- **Block length:** a user choice, not fitted. A default of 10 is reported,
  and sensitivity across 1, 5, 10, 20, 30 is shown rather than relying on
  one number.
- **Reproducibility:** all randomness comes from `random.Random(seed)` with
  `seed = 20260101`, so any `(values, block_length, n_resamples, seed)`
  always yields the same interval. Verified by test.
- **Not proof of future performance.** These intervals describe uncertainty
  in the observed sample only.

### 4.3 Dependence was measured, not assumed

A moving-block bootstrap is only warranted if consecutive trades are actually
dependent. Phase 11 measured this:

| Config | lag-1 | lag-2 | lag-3 | white-noise band |
|---|---|---|---|---|
| baseline | −0.0480 | +0.0019 | −0.0155 | ±0.1952 |
| A2 | −0.0479 | +0.0700 | −0.1176 | ±0.2108 |

All values sit **inside** the white-noise band. No strong serial dependence
was found, and consequently **the block intervals came out slightly
narrower than i.i.d., not wider**. The block method is therefore reported as
a cross-check, not as a correction that inflates the interval.

This corrected an assumption written into the module documentation before
the measurement was made.

### 4.4 Monthly return denominator

`return_pct` uses the fixed starting balance ($10,000), not a month-opening
balance. That keeps months mutually comparable and comparable to the headline
return, and avoids implying compounding that a per-trade ledger does not
define. Each trade is assigned to the month of its **entry**, so nothing is
double counted.

## 5. Statistical uncertainty

### Mean net P&L per trade

| Config | Point | Method | 95% CI | Contains zero |
|---|---|---|---|---|
| baseline | +0.0481 | i.i.d. | [−0.6260, +0.8098] | **Yes** |
| baseline | +0.0481 | block 10 | [−0.6126, +0.6644] | **Yes** |
| A2 | +0.1563 | i.i.d. | [−0.5943, +1.0219] | **Yes** |
| A2 | +0.1563 | block 10 | [−0.5755, +0.8300] | **Yes** |

### Block-length sensitivity

| Block | baseline CI | baseline zero? | A2 CI | A2 zero? |
|---|---|---|---|---|
| 1 | [−0.6260, +0.8098] | Yes | [−0.5943, +1.0219] | Yes |
| 5 | [−0.6078, +0.7819] | Yes | [−0.5419, +0.9853] | Yes |
| 10 | [−0.6126, +0.6644] | Yes | [−0.5755, +0.8300] | Yes |
| 20 | [−0.6600, +0.4302] | Yes | [−0.6251, +0.6372] | Yes |
| 30 | [−0.6535, +0.2873] | Yes | [−0.5045, +0.4482] | Yes |

**Ten intervals, all containing zero.** The conclusion does not depend on
the method or the block length.

### Total P&L of the observed trade sequence

| Config | Point | 95% CI (block 10) | Contains zero |
|---|---|---|---|
| baseline | +$5.05 | **[−$64.32, +$69.76]** | **Yes** |
| A2 | +$14.07 | **[−$51.80, +$74.70]** | **Yes** |

The intervals are roughly an order of magnitude wider than the point
estimates. A plausible reading of this data is a result anywhere from a
meaningful loss to a meaningful gain.

### What the intervals do and do not establish

**Do:** the observed averages are too small relative to their dispersion, at
n = 90–105, to distinguish from zero.

**Do not:** they do not establish that the strategy has no edge. They show
this sample cannot resolve an edge of this size. A larger sample could move
the interval off zero in either direction. They also say nothing about
non-stationarity, which the 2024→2026 sign flip demonstrates is a live
concern.

## 6. Monthly variability

### Baseline

| Month | Trades | Net | Return | Gross | Costs | W | L | Sign |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 8 | +14.08 | +0.141% | +16.47 | 2.38 | 4 | 4 | positive |
| 2026-02 | 13 | +11.31 | +0.113% | +15.19 | 3.88 | 7 | 6 | positive |
| 2026-03 | 17 | −16.94 | −0.169% | −11.82 | 5.12 | 5 | 12 | negative |
| 2026-04 | 14 | −5.31 | −0.053% | −1.09 | 4.22 | 3 | 11 | negative |
| 2026-05 | 12 | +9.53 | +0.095% | +13.10 | 3.57 | 3 | 9 | positive |
| 2026-06 | 12 | −5.43 | −0.054% | −1.83 | 3.60 | 5 | 7 | negative |
| 2026-07 | 16 | −8.40 | −0.084% | −3.59 | 4.81 | 6 | 10 | negative |
| 2026-08 | 13 | +6.21 | +0.062% | +10.15 | 3.94 | 3 | 10 | positive |

### A2

| Month | Trades | Net | Return | Gross | Costs | W | L | Sign |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 8 | +11.17 | +0.112% | +13.55 | 2.38 | 3 | 5 | positive |
| 2026-02 | 13 | +11.31 | +0.113% | +15.19 | 3.88 | 7 | 6 | positive |
| 2026-03 | 12 | −0.21 | −0.002% | +3.40 | 3.61 | 5 | 7 | negative |
| 2026-04 | 11 | −4.29 | −0.043% | −0.96 | 3.33 | 3 | 8 | negative |
| 2026-05 | 8 | +15.00 | +0.150% | +17.37 | 2.37 | 3 | 5 | positive |
| 2026-06 | 12 | −9.29 | −0.093% | −5.68 | 3.61 | 4 | 8 | negative |
| 2026-07 | 16 | −16.99 | −0.170% | −12.18 | 4.82 | 5 | 11 | negative |
| 2026-08 | 10 | +7.38 | +0.074% | +10.42 | 3.04 | 3 | 7 | positive |

### Summary

| Measure | Baseline | A2 |
|---|---|---|
| Months with trades | 8 of 8 | 8 of 8 |
| Positive months | **4** | **4** |
| Negative months | **4** | **4** |
| Best month | 2026-01 (+14.08) | 2026-05 (+15.00) |
| Worst month | 2026-03 (−16.94) | 2026-07 (−16.99) |
| Range | 0.310% of balance | 0.320% of balance |
| Mean monthly return | +0.006% | +0.018% |
| Months with no trades | 0 | 0 |

**Reconciliation with Phase 10:** the monthly net figures for baseline
(+14.08, +11.31, −16.94, −5.31, +9.53, −5.43, −8.40, +6.21) match Phase 10's
monthly breakdown exactly. Nothing was overwritten.

**Limitations:** eight months is not a large or representative sample. Every
month has at least 8 trades, so no month is empty, but 8 trades in a month is
a small sample in itself. The even 4/4 split is what one would expect from a
strategy with no reliable edge.

## 7. Trade concentration and dependence

### Concentration

| Measure | Baseline | A2 |
|---|---|---|
| Net P&L | +5.05 | +14.07 |
| Gross profit | +124.08 | +119.84 |
| Gross loss | 119.04 | 105.77 |
| Largest single win | +19.12 | +19.16 |
| Largest single loss | −6.19 | −6.19 |
| **Net excluding largest win** | **+104.96** | **+100.68** |
| **Net excluding largest loss** | **−1.14** | **+7.88** |
| **Median trade** | **−0.89** | **−0.96** |
| Mean trade | +0.0481 | +0.1563 |
| Stdev of trade | 3.7478 | 3.9665 |
| Top 1 win as % of net | **+378.8%** | **+136.2%** |
| Top 3 wins as % of net | **+972.2%** | **+342.2%** |
| Top 5 wins as % of net | **+1299.6%** | **+459.7%** |
| Worst 1 as % of net | −122.6% | −44.0% |
| Worst 5 as % of net | −441.8% | −159.0% |

**The result depends on a handful of trades.** Baseline's largest win is
nearly four times its entire net result. Remove that one trade and baseline
has +$104.96 of gross wins against $119.04 of losses — the survivors are
net negative. Remove the single largest *losing* trade instead and baseline
is **−$1.14**, i.e. negative.

The **negative median trade** is the clearest signal: the typical trade loses
money. Positive mean P&L comes entirely from a thin right tail.

### Dependence and sequence overlap

The strategy holds at most one position at a time, so trade intervals cannot
overlap. In the 2026 sample, 104 of 105 consecutive baseline trade pairs have
`next_entry_index == previous_exit_index`, i.e. a position closes and the
next opens on the same bar, both filling at that bar's open. This has two
consequences:

- Trade *intervals* abut rather than overlap, so no capital is double
  counted.
- Consecutive trades are near-adjacent in time (~51 hours apart on average),
  which is why serial dependence was checked rather than assumed. It was
  found to be negligible at lags 1–3.

This adjacency also means trades are **not** 105 independent observations of
a stationary process. The bootstrap treats them as exchangeable blocks,
which is an approximation.

## 8. Drawdown analysis

| Measure | Baseline | A2 |
|---|---|---|
| **Existing** closed-trade max drawdown | **0.3395%** | **0.3058%** |
| **New** mark-to-market max drawdown | **0.3943%** | **0.3415%** |
| MTM peak equity | 10,032.28 | 10,036.50 |
| MTM trough equity | 9,992.72 | 10,002.22 |
| MTM trough timestamp | 2026-05-26 10:00 | 2026-08-04 00:00 |
| MTM samples (candles) | 5,832 | 5,832 |
| Closed-trade samples (trades) | 105 | 90 |
| MTM / closed ratio | 1.16x | 1.12x |

**Findings:**

- Mark-to-market drawdown exceeds the closed-trade measure by only
  12–16%. The existing metric does not materially understate risk for this
  strategy on this data.
- Both figures are tiny (< 0.4%) **only because `risk_fraction` is 0.01**,
  risking ~1% of equity per trade. This is not evidence of low risk; it is a
  consequence of deliberately conservative position sizing. Scaling risk up
  would scale drawdown roughly proportionally.
- The legacy metric is preserved unchanged and a test asserts the two
  definitions agree.

### Bug found and corrected during this phase

An early version of the mark-to-market curve emitted **5,936 samples from a
5,832-candle dataset** — an impossible count that revealed two defects:
a pre-trade flat period was dropped, and bars where a trade closes and the
next opens were emitted twice. Both were fixed; the curve now emits exactly
one sample per candle (asserted by test).

**Impact on reported figures: none of substance.** The corrected run returns
the same mark-to-market drawdown values (0.3943% / 0.3415%) because the
duplicated values were identical at the moment of duplication and did not
affect the running peak/trough scan. Phase 10 results are entirely
unaffected, since they derive from the engine, not from this new code.

## 9. Baseline versus A2

**Descriptive comparison. No ranking, score, or selection is expressed.**

| Measure | Baseline | A2 |
|---|---|---|
| Trades | 105 | 90 |
| Net P&L | $5.05 | $14.07 |
| Return | +0.05% | +0.14% |
| Win rate | 34.29% | 36.67% |
| Profit factor | 1.0424 | 1.1330 |
| Max drawdown (closed-trade) | 0.3395% | 0.3058% |
| Max drawdown (mark-to-market) | 0.3943% | 0.3415% |
| Positive months | 4 | 4 |
| Negative months | 4 | 4 |
| Months with trades | 8 | 8 |
| Mean/trade 95% CI | [−0.6126, +0.6644] | [−0.5755, +0.8300] |
| CI contains zero | **Yes** | **Yes** |
| Total P&L 95% CI | [−64.32, +69.76] | [−51.80, +74.70] |
| Median trade | −0.89 | −0.96 |
| Largest win as % of net | +378.8% | +136.2% |

A2 shows a higher observed return, a higher profit factor, and lower
drawdown on this window. **That is one observation from one evaluation
window, and it is not evidence that A2 is a better or profitable strategy.**
Specifically:

- Both configurations' intervals contain zero, and the intervals overlap
  heavily. The difference between +$5.05 and +$14.07 is far inside the
  ±$60–70 uncertainty around each.
- Both have a **negative median trade**. Neither is profitable on the
  typical trade.
- Both split months 4 positive / 4 negative.
- A2 was selected on 2024–2025 data. One out-of-sample window does not
  validate that selection.
- No configuration was selected, recommended, or optimised in this phase.

## 10. Limitations

1. **Evaluation covers only January–August 2026** — eight months, one
   asset, one timeframe.
2. **90 and 105 trades is a small sample.** Per-trade σ ≈ 3.75–3.97 against
   means of 0.05–0.16. Confidence intervals are wide and contain zero.
3. **Bootstrap intervals describe the historical sample only.** They are not
   forecasts and do not establish future performance.
4. **The block bootstrap assumes blocks are exchangeable.** Trades are
   time-adjacent, so this is an approximation.
5. **Mark-to-market uses candle closes only.** Intrabar extremes are
   unavailable and were not invented, so true intrabar drawdown could be
   larger than reported.
6. **Mark-to-market unrealised P&L is gross.** The curve is marginally
   optimistic while a trade is open.
7. **Concentration statistics are descriptive.** The >100% figures arise
   because net P&L is a small residual of large offsetting gross flows; they
   are not shares of a positive total and should not be read as such.
8. **The 2024–2025 dataset still has no documented provenance**, so
   cross-period comparison carries an unquantified assumption.
9. **No other variants were tested** on 2026 data — exit rules,
   confirmation, trend-strength and directional variants were explored only
   on 2024–2025.
10. **Non-stationarity is unresolved.** The 2024–2025 → 2026 sign flip with
    an unchanged strategy is a live concern that eight months cannot settle.

## 11. Reproducibility

```bash
cd research_engine
python -m pytest tests/ -q
python experiments/phase11/robustness_analysis.py
python experiments/phase11/dependence_analysis.py
```

Fixed inputs:

| Item | Value |
|---|---|
| Dataset | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| Dataset SHA-256 | `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437` |
| Warm-up bars | 48 |
| Starting balance | 10,000.00 |
| Fee / slippage | 0.001 / 0.0005 |
| Risk fraction | 0.01 |
| Bootstrap seed | 20260101 |
| Bootstrap resamples | 10,000 |
| Reported block length | 10 (sensitivity 1, 5, 10, 20, 30 reported) |
| Bootstrap alpha | 0.05 |

Saved outputs: `RESULTS_robustness.txt`, `RESULTS_dependence.txt`.

## 12. Final research conclusion

Phase 10's out-of-sample results were **marginally positive and statistically
inconclusive**. Phase 11 shows why, in four independent ways: every
confidence interval contains zero; the result is concentrated in a handful
of trades; the median trade loses money; and monthly outcomes split evenly.

Mark-to-market analysis shows the existing drawdown metric was not
materially understating risk on this data. Serial dependence was measured
and found negligible, so the block bootstrap neither rescues nor undermines
the conclusion — both methods agree.

A2's higher observed 2026 return is **one observation from one evaluation
window**. It is not evidence that A2 is a better or profitable strategy.

**Explicit statements:**

- The evaluation covers **only January–August 2026**.
- It uses **one asset** and a **limited number of trades** (90 and 105).
- The confidence intervals reported in Phase 10 **include zero**.
- **Historical results do not establish future profitability.**
- **No strategy was selected or optimized in this phase.**

Across 23,376 hourly candles, 12+ configurations and two full evaluation
periods, this project still has **no evidence of a profitable trading rule**.
