# Phase 10 — Out-of-Sample Results

## Validity

Out-of-sample testing was completed validly. The Phase 8 harness was used
**unmodified** — no methodology change, no parameter change, no new filter.
Two configurations only, as specified:

- **A — baseline:** `StrategyConfig()` with every optional research filter
  at its default (disabled).
- **B — A2:** identical to A except `min_breakout_distance = 0.002`.

Both were frozen before the new data was seen and neither was tuned during
Phase 10. A test asserts the two configurations differ in exactly one field.

## Validation design

| Parameter | Value |
|---|---|
| Dataset | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| Full file range | 2026-01-01 00:00 → 2026-08-31 23:00 (5,832 bars) |
| Warm-up (context only) | 2026-01-01 00:00 → 2026-01-02 23:00 (48 bars) |
| **Validation window** | **2026-01-03 00:00 → 2026-08-31 23:00 (5,784 bars)** |
| Starting balance | $10,000.00, identical for both |
| Balance method | Account starts **flat** at the boundary; warm-up bars cannot open a position, so no balance carries over |
| Fee rate | 0.001 |
| Slippage rate | 0.0005 |
| Position sizing | `risk_fraction = 0.01` of then-current cash |
| Execution | Next-candle open; signals from closed candles only |
| End of window | Any open position closed at the final candle's close (`end_of_data`) |
| Warm-up excluded from trades | Yes, enforced by `evaluation_start` |

## Results

| Measure | A — baseline | B — A2 |
|---|---|---|
| Trades | 105 | 90 |
| **Net P&L** | **+$5.05** | **+$14.07** |
| Return | +0.05% | +0.14% |
| Win rate | 34.29% | 36.67% |
| Profit factor | 1.0424 | 1.1330 |
| Max drawdown | 0.34% | 0.31% |
| Ending balance | $10,005.05 | $10,014.07 |
| Total fees + slippage | $31.52 | $27.04 |
| Gross P&L (pre-cost) | +$36.57 | +$41.11 |
| Avg net P&L per trade | +$0.05 | +$0.16 |
| Longs | 53 trades, −$1.01, 37.74% WR | 45 trades, +$3.11, 37.78% WR |
| Shorts | 52 trades, +$6.05, 30.77% WR | 45 trades, +$10.95, 35.56% WR |
| Exits | 104 opposite-signal, 1 end-of-data | 89 opposite-signal, 1 end-of-data |
| Costs as % of gross | 86.2% | 65.8% |

Both configurations are **positive after costs** on this window.

## Are these results meaningful?

**No — neither result is distinguishable from zero.**

| Configuration | Measure | Per-trade mean | Std error | mean / SE | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| baseline | net | +0.0481 | 0.3657 | **0.13** | [−0.6688, +0.7649] | spans zero |
| baseline | gross | +0.3482 | 0.3656 | **0.95** | — | spans zero |
| A2 | net | +0.1563 | 0.4181 | **0.37** | [−0.6632, +0.9758] | spans zero |
| A2 | gross | +0.4567 | 0.4180 | **1.09** | — | spans zero |

Every confidence interval contains zero, and every mean/standard-error ratio
is far below the conventional 1.96 threshold — even **before costs**. On this
evidence neither strategy demonstrates an edge.

Three further reasons the sign should not be over-read:

1. **Magnitudes are trivial by construction.** `risk_fraction = 0.01` means
   each trade risks ~1% of equity, so 105 trades can only move the account by
   a fraction of a percent. Max drawdown is under 0.35% for both.
2. **Costs consume most of the gross result.** Baseline costs equal 86.2% of
   its gross P&L; A2's equal 65.8%. Both are close to the break-even line.
3. **Monthly results are inconsistent.** Baseline net by month: +14.08,
   +11.31, −16.94, −5.31, +9.53, −5.43, −8.40, +6.21. Four positive, four
   negative, no persistent direction.

## Does this validate the Phase 7 A2 finding?

**No.** A2 beat baseline on this single window (+14.07 vs +5.05, PF 1.133 vs
1.042), but:

- A2's own mean/SE is **0.37**. The difference is well inside noise.
- This is **one window** on one asset.
- A2 was chosen on 2024–2025 data; one out-of-sample window is not
  confirmation of a general effect.

A single positive observation is not evidence of a persistent advantage.

## Regime comparison

| Measure | Research 2024–2025 | Validation 2026 |
|---|---|---|
| Range | 2024-01-01 → 2025-12-31 | 2026-01-01 → 2026-08-31 |
| Price range | 38,545.00 – 126,208.50 | 57,800.19 – 97,924.49 |
| First → last | 42,503.50 → 87,608.20 (**+106.1%**) | 87,809.23 → 78,581.29 (**−10.5%**) |
| Hourly volatility | 0.520% | 0.471% |
| Mean bar range | 0.713% | 0.635% |
| Baseline net | −157.14 | **+5.05** |
| A2 net | −87.16 | **+14.07** |

Both configurations flipped from clearly negative on 2024–2025 to marginally
positive in 2026, and the market direction flipped from a strong uptrend to a
downtrend over the same span. **The strategy was not modified between these
periods**, so the sign change tracks the market regime, not a change in the
strategy. This is the same regime sensitivity documented descriptively in
Phase 8 for 2024 vs 2025, now observed a third time.

## Trade-count sufficiency

105 (baseline) and 90 (A2) trades exceed the ~50-trade threshold set in
Phase 9, so the runs are not *too few* to interpret. They are nonetheless
**statistically inconclusive** because per-trade dispersion (σ ≈ 3.75–3.97)
is large relative to the mean (≈ 0.05–0.16).

## Verdict

Out-of-sample testing was validly performed and both configurations came out
marginally positive. On this evidence neither strategy is distinguishable
from having no edge, and neither is demonstrated to be profitable. These
results do not authorise selecting, deploying, or trusting either
configuration, and they do not retroactively validate A2.

A negative result at this scale would have been reported the same way. The
outcome here is a small positive that the statistics do not support.
