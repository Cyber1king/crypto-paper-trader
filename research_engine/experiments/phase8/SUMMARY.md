# Phase 8 — Final Summary: What Can and Cannot Be Concluded

## Headline

**Out-of-sample validation was NOT performed. The repository contains no
genuinely unseen data.**

Every requirement for a valid out-of-sample test fails on availability
grounds, not on technical grounds. The harness needed to perform the
validation has been built, tested, and is ready — but it was deliberately
*not* run against in-sample data, because doing so and calling the result
"out-of-sample" would be false.

## 1. Baseline and A2 both reproduce exactly

| Metric | Baseline expected | Baseline actual | A2 expected | A2 actual |
|---|---|---|---|---|
| Trades | 344 | **344** ✅ | 284 | **284** ✅ |
| Net P&L | -157.14 | **-157.14** ✅ | -87.16 | **-87.16** ✅ |
| Return | -1.57% | **-1.57%** ✅ | -0.87% | **-0.87%** ✅ |
| Win rate | 31.686% | **31.686%** ✅ | 33.45% | **33.451%** ✅ |
| Profit factor | 0.6920 | **0.6920** ✅ | 0.796 | **0.7957** ✅ |
| Max drawdown | 1.74% | **1.74%** ✅ | 1.08% | **1.08%** ✅ |
| Ending balance | 9842.86 | **9842.86** ✅ | 9912.84 | **9912.84** ✅ |

The two apparent mismatches (33.451 vs 33.45, 0.7957 vs 0.796) are decimal
precision in the *published* Phase 7 figures, not differences in the
underlying values. Verified at matching precision.

Re-verified after every code change in this phase.

## 2. Unseen-data search — exhaustive and negative

| Location checked | Result |
|---|---|
| `research_engine/data/` | 2 files: one real, one empty |
| Whole repository (`*.csv`, `*.json`, `*.parquet`, `*.txt`, archives) | no other OHLCV data |
| Git history, all branches | only the same 2 CSV paths ever existed |
| `BTCUSDT_1h.csv` in every commit | **1 byte** — never contained data |
| `BTCUSDT_1h_Cleaned (1).csv` | 17,544 candles, ends **2025-12-31 23:00** |

**Zero candles exist after 2025-12-31 23:00 in this repository.**

The one real dataset is high quality: 17,544 candles, 0 duplicates, 0
non-increasing timestamps, **0 gaps, 0 missing hours**, 0 OHLC integrity
violations, `validate_dataset` passes, price range 38,545 – 126,208.

Git history spans 2026-09-11 to 2026-09-28. Today's date is 2026-10-01, so
roughly nine months of 2026 candles would exist in the world — but they are
**not in this repository**, and I did not download anything.

## 3. Validation design (implemented, documented, unused)

Full plan in `validation_plan.md`. Summary:

- **Two configurations only:** baseline and A2 (`min_breakout_distance=0.002`).
- **Warm-up:** 48 leading bars (strategy needs 22). Warm-up bars feed
  indicators only and cannot open a position.
- **Boundary:** `run_backtest(..., evaluation_start=N)` gates entries.
  Since no position can be open at the boundary, the account starts **flat
  with the full $10,000** — no carry-over, nothing reset silently, identical
  for both configurations.
- **End of window:** any open position closes at the final candle's close,
  labelled `end_of_data`, with count and P&L reported.
- **Costs fixed:** fee 0.001, slippage 0.0005. No sensitivity analysis
  included, to avoid presenting hypothetical costs as achievable.

The harness **correctly refuses** in all three cases tested:
1. No file supplied → "VALIDATION NOT PERFORMED"
2. The in-sample dataset supplied → rejected (overlaps Phase 7 window)
3. The empty dataset supplied → rejected (unreadable)

A **synthetic self-test** (invented prices, temp directory, clearly labelled
*not a research result*) confirms the harness runs end to end: 480 candles,
correct warm-up exclusion, both configurations reported, boundary documented.
The synthetic run returns a 100% win rate, which is precisely why it carries
no research meaning.

## 4. Validation results

**None. There are no out-of-sample results for either configuration.**

No number in this phase is an out-of-sample measurement of baseline or A2
performance.

## 5. 2024 vs 2025 — descriptive findings only

### Market conditions (measured)

| Measure | 2024 | 2025 |
|---|---|---|
| Hourly candles | 8,784 | 8,760 |
| Total return | **+120.10%** | **-7.16%** |
| Annualised realised volatility | 52.57% | 44.38% |
| Mean bar range / close | 0.787% | 0.638% |
| Median \|fastMA−slowMA\|/slowMA | 0.283% | 0.244% |

### Strategy activity (baseline, measured)

| Measure | 2024 | 2025 |
|---|---|---|
| Trades | 173 | 172 |
| Mean entry spacing | 50.88 h | 51.06 h |
| Mean bars held | 50.64 | 50.80 |
| % held ≤ 24 bars | 34.10% | 35.47% |
| **Gross P&L (pre-cost)** | **-15.63** | **-40.63** |
| Costs | 51.89 | 51.33 |
| Net P&L | -67.52 | -91.95 |
| Long net | **+10.64** (WR 37.9%) | **-46.41** (WR 29.1%) |
| Short net | -78.17 (WR 25.6%) | -45.54 (WR 33.7%) |
| long_breakout net | +6.05 | -35.02 |
| short_breakdown net | -72.90 | -49.20 |

### What the data shows

1. **2024 was a strong uptrend year (+120%); 2025 was mildly negative (-7%).**
2. Trade *frequency* was essentially identical (173 vs 172, spacing 50.9 h
   vs 51.1 h). The strategy was equally active.
3. **The year-over-year difference is concentrated almost entirely on the
   long side**: longs moved from +10.64 to -46.41 (a ~$57 swing), while
   shorts moved from -78.17 to -45.54 (an improvement of ~$33).
4. **Costs were near-identical** (51.89 vs 51.33). The gap is in *gross*
   P&L (-15.63 vs -40.63), so cost assumptions are not the explanation.
5. A2 shows the same pattern: gross +11.59 (2024) vs -17.14 (2025).
6. `long_breakout` flipped from +6.05 to -35.02 — the single largest
   component change.

### Candidate explanations — hypotheses only, none tested

- **H1 Directional dependence.** If any edge exists in one trend direction
  only, a +120% year and a -7% year would produce opposite long results.
  Consistent with the data; **not established**.
- **H2 Cost drag binds differently by regime.** *Partially contradicted* —
  costs were nearly equal across years, so this cannot explain the gap.
- **H3 The 20-bar level window behaves differently by volatility.** Bar range
  (0.787% vs 0.638%) and trend-gap statistics do differ. Plausible;
  **not tested**.
- **H4 Ordinary sampling noise.** ~86 long trades per year, and Phase 5
  measured single-trade gross P&L spanning -6.92 to +27.33. A ~$0.65/trade
  difference in the long-side mean is small against that dispersion.
  Entirely plausible; **no significance test performed**.

**A correlation between a measured market statistic and a P&L difference does
not establish causation.** None of H1, H3, H4 is demonstrated.

## 6. Files created or modified

**Modified (defaults unchanged, baseline bit-identical):**
- `src/crypto_paper_lab/backtest.py` — added optional
  `evaluation_start: int | None = None` parameter with validation

**Created:**
- `tests/test_validation_boundary.py` — 13 tests
- `experiments/phase8/validation_plan.md`
- `experiments/phase8/validation_harness.py`
- `experiments/phase8/harness_self_test.py`
- `experiments/phase8/dataset_inspection.py`
- `experiments/phase8/verify_configurations.py`
- `experiments/phase8/descriptive_2025_analysis.py`
- `experiments/phase8/RESULTS_*.txt` (5 files)
- `experiments/phase8/SUMMARY.md` (this file)

**Removed:** `experiments/phase8/probe_series.py` (scratch). No dataset,
test, or earlier-phase report deleted. Nothing committed or pushed.

## 7. Test results

`python -m pytest tests/ -q` → **79 passed, 0 failed** (66 pre-existing +
13 new). No existing test modified or weakened.

New tests prove: default is bit-identical; the pre-existing baseline series
still returns 9,992.4522; warm-up bars produce no trades; the gate reduces
account activity to validation only; invalid boundaries are rejected;
look-ahead stays absent; end-of-window closes are labelled; costs are charged
once; and boundary handling does not favour one configuration over another.

## 8. Limitations and unresolved issues

1. **No unseen data exists.** This is the blocking issue. Until post-2025
   candles are supplied, no out-of-sample claim about baseline or A2 is
   possible.
2. The 20-bar support/resistance window is a fixed candle count, not
   volatility-adjusted — a plausible weakness across regimes, untested.
3. Only one asset and one timeframe. No cross-market or cross-period
   robustness evidence.
4. No statistical significance testing or bootstrap anywhere in this project.
5. Drawdown is computed on the trade-closure equity curve (344 points), not
   mark-to-market, so intra-trade drawdown is understated.
6. The synthetic self-test proves harness mechanics only. Its numbers are
   meaningless as research.
7. A2's parameter was chosen in Phase 7 on the same data used for the 2024
   and 2025 figures. Even a favourable out-of-sample result would be one
   observation on one window.
8. The repository's newest commit is 2026-09-28 while today is 2026-10-01,
   so the project has no data newer than its own creation — the project has
   never seen post-2025 market data.

## 9. Conclusion — what the evidence supports

**Supported:**

- The baseline and A2 reproduce exactly on the in-sample period.
- The existing dataset is clean and internally consistent.
- No genuinely unseen data exists in this repository, so out-of-sample
  validation of Phase 7's A2 finding **has not been performed and cannot be
  performed here**.
- A tested, documented validation harness now exists and will run correctly
  the moment unseen candles are provided.
- Descriptively, 2024 and 2025 differed sharply in market direction
  (+120% vs -7%), and the strategy's year-over-year P&L difference sits
  almost entirely on the long side, with near-identical costs in both years.

**Not supported:**

- Any claim that A2 improves performance out of sample.
- Any claim that A2 is profitable, or profitable in future.
- Any causal explanation for the 2024/2025 difference.
- Any statement about how baseline or A2 would have performed after
  2025-12-31.

**Bottom line:** Phase 7's A2 improvement remains an in-sample observation.
It has not been validated, cannot be validated with the data on hand, and
must not be described as a strategy that works. The honest status of this
project is that it has tested 12 configurations against the same 17,544
candles and has produced no evidence of a profitable trading rule.
