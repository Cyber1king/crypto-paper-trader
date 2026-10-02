# Phase 7 — Entry Signal Research: Summary

All figures are net of `fee_rate=0.001` + `slippage_rate=0.0005`, starting
balance $10,000, next-candle-open execution, `risk_fraction=0.01`.

**2024 and 2025 are EXPLORATORY and IN-SAMPLE.** Both years were examined in
Phases 2–6. Neither is an untouched out-of-sample test.

## Baseline reproduction

| Metric | Expected | Actual | Match |
|---|---|---|---|
| Trades | 344 | 344 | YES |
| Net P&L | -157.14 | -157.14 | YES |
| Return | -1.57% | -1.57% | YES |
| Win rate | 31.686% | 31.686% | YES |
| Profit factor | 0.6920 | 0.6920 | YES |
| Max drawdown | 1.74% | 1.74% | YES |
| Ending balance | 9842.86 | 9842.86 | YES |

No discrepancy. Gross P&L -54.56, costs 102.58.

## Comparison table (full period)

| Experiment | Group | n | Δn | Net P&L | Ret | WR | PF | MDD | End bal | Trades kept |
|---|---|---|---|---|---|---|---|---|---|---|
| P0_baseline | control | 344 | +0 | -157.14 | -1.57% | 31.69% | 0.692 | 1.74% | 9842.86 | 100% |
| A1_min_dist=0.001 | A | 344 | +0 | -157.14 | -1.57% | 31.69% | 0.692 | 1.74% | 9842.86 | 100% |
| A2_min_dist=0.002 | A | 284 | -60 | -87.16 | -0.87% | 33.45% | 0.796 | 1.08% | 9912.84 | 83% |
| A3_min_dist=0.003 | A | 257 | -87 | -112.94 | -1.13% | 32.69% | 0.737 | 1.39% | 9887.06 | 75% |
| A4_min_dist=0.004 | A | 225 | -119 | -75.88 | -0.76% | 33.78% | 0.806 | 0.97% | 9924.12 | 65% |
| B2_confirm_2 | B | 254 | -90 | -113.10 | -1.13% | 29.92% | 0.731 | 1.19% | 9886.90 | 74% |
| B3_confirm_3 | B | 148 | -196 | -56.88 | -0.57% | 34.46% | 0.793 | 0.82% | 9943.12 | 43% |
| C1_long_only | C | 172 | -172 | -34.19 | -0.34% | 33.72% | 0.861 | 0.66% | 9965.81 | 50% |
| C2_short_only | C | 172 | -172 | -123.37 | -1.23% | 29.65% | 0.536 | 1.35% | 9876.63 | 50% |
| D1_dist0.002+conf2 | D | 227 | -117 | -119.52 | -1.20% | 30.84% | 0.706 | 1.28% | 9880.48 | 66% |
| D2_dist0.002+long_only | D | 142 | -202 | +0.94 | +0.01% | 37.32% | 1.005 | 0.45% | 10000.94 | 41% |
| D3_conf2+long_only | D | 127 | -217 | -10.51 | -0.10% | 31.50% | 0.947 | 0.44% | 9989.49 | 37% |

## Year by year (exploratory, in-sample)

| Experiment | 2024 net | Δ24 | 2025 net | Δ25 | Better both yrs | Verdict |
|---|---|---|---|---|---|---|
| A1_min_dist=0.001 | -67.52 | +0.00 | -91.95 | +0.00 | no | identical to baseline |
| A2_min_dist=0.002 | -33.18 | +34.34 | -57.80 | +34.15 | **YES** | negative both years |
| A3_min_dist=0.003 | -47.50 | +20.02 | -69.38 | +22.57 | **YES** | negative both years |
| A4_min_dist=0.004 | **+2.25** | +69.77 | -81.74 | +10.21 | **YES** | 2024 only positive |
| B2_confirm_2 | -49.89 | +17.63 | -65.92 | +26.03 | **YES** | negative both years |
| B3_confirm_3 | -6.17 | +61.35 | -50.31 | +41.64 | **YES** | negative both years |
| C1_long_only | **+10.64** | +78.16 | -46.52 | +45.43 | **YES** | 2024 only positive |
| C2_short_only | -78.08 | -10.56 | -45.65 | +46.30 | no | worse in 2024 |
| D1_dist0.002+conf2 | -52.09 | +15.43 | -71.36 | +20.59 | **YES** | negative both years |
| D2_dist0.002+long_only | **+27.69** | +95.21 | -30.33 | +61.62 | **YES** | 2024 only positive |
| D3_conf2+long_only | **+21.22** | +88.74 | -34.07 | +57.88 | **YES** | 2024 only positive |

## Gross vs cost decomposition (full period)

| Experiment | n | Gross | Costs | Net | Cost/trade |
|---|---|---|---|---|---|
| P0_baseline | 344 | -54.56 | 102.58 | -157.14 | 0.2982 |
| A2_min_dist=0.002 | 284 | -2.16 | 85.00 | -87.16 | 0.2993 |
| A4_min_dist=0.004 | 225 | -8.42 | 67.47 | -75.88 | 0.2999 |
| B3_confirm_3 | 148 | -12.49 | 44.40 | -56.88 | 0.3000 |
| C1_long_only | 172 | **+17.44** | 51.63 | -34.19 | 0.3002 |
| C2_short_only | 172 | -72.04 | 51.33 | -123.37 | 0.2984 |
| D2_dist0.002+long_only | 142 | **+43.67** | 42.73 | +0.94 | 0.3009 |
| D3_conf2+long_only | 127 | **+27.66** | 38.17 | -10.51 | 0.3006 |

Cost per trade is effectively constant (~0.299) in every configuration. Any
filter helps only by removing trades whose gross P&L is negative.

## Signal class shifts (full period)

| Experiment | lb n | lb net | sb n | sb net | lr n | lr net | sr n | sr net |
|---|---|---|---|---|---|---|---|---|
| P0_baseline | 155 | -27.00 | 158 | -121.78 | 17 | -6.73 | 14 | -1.64 |
| A2_min_dist=0.002 | 131 | **+12.09** | 134 | -83.44 | 11 | -11.05 | 8 | -4.76 |
| B2_confirm_2 | 64 | -15.96 | 65 | -76.37 | 63 | **+5.63** | 62 | -26.40 |
| B3_confirm_3 | **0** | 0.00 | **0** | 0.00 | 74 | +16.19 | 74 | -73.07 |
| D2_dist0.002+long_only | 131 | +12.03 | 0 | 0.00 | 11 | -11.09 | 0 | 0.00 |

`B3_confirm_3` produces **zero** trades in the breakout/breakdown classes —
it is structurally a different strategy, not a mild confirmation variant.

## Year-outcome spread

- 2024 net range across 12 configs: -78.08 .. +27.69 (spread 105.77)
- 2025 net range across 12 configs: -91.95 .. -30.33 (spread 61.62)
- Configs positive in 2024: **4 / 12**
- Configs positive in 2025: **0 / 12**
- Configs positive in BOTH years: **0 / 12**
- Configs positive over the full period: **1 / 12** (D2, +0.94 = +0.009%)

## Unsuccessful / null results

- **A1 (0.001) is a no-op.** `breakout_buffer=0.001` already requires
  `close > level * 1.001`, so `min_breakout_distance=0.001` is fully implied.
  Results are bit-identical to baseline. The requested value is redundant.
- **A series is non-monotonic**: A2 (-87.16) beats A3 (-112.94). A stricter
  filter performed *worse* than a looser one. There is no smooth
  distance/return relationship.
- **A4 (0.004) is the clearest overfitting trap**: 2024 turns positive
  (+2.25) but 2025 is worse than baseline in profit-factor terms
  (0.578 vs 0.616).
- **C2 (short-only) is worse than baseline in 2024** (-78.08 vs -67.52).
  Shorts are the weaker side in both years on a net basis, but the 2025
  short loss is much smaller (-45.65) than 2024 (-78.08).
- **D1 (combination) is worse than either component alone**
  (D1 -119.52 vs A2 -87.16 and B2 -113.10). The filters are not additive.
- **B2 lowers the win rate** (31.69% → 29.92%) while improving net P&L —
  a reminder that win rate is not the objective.
- **No configuration is profitable in 2025.** Not one.

## Limitations and overfitting risk

1. Every value was chosen after seeing full-period and per-year results on
   the same 17,544 candles. All results are in-sample and exploratory.
2. The best full-period outcome (D2, +0.94 on $10,000 over two years =
   +0.009%) is statistically indistinguishable from zero. Selecting it
   because it is the only positive number would be textbook overfitting.
3. Trade counts fall substantially for the best results: D2 keeps 41%,
   D3 37%, B3 43%, C1/C2 50%. Smaller samples mean wider confidence
   intervals on every statistic.
4. Single asset, single timeframe, one regime. No walk-forward, no
   significance testing, no confidence intervals.
5. `C1`/`C2`/`D2`/`D3` are *diagnostics* built by blocking entries. They are
   not evidence that a long-only strategy would trade well; they only show
   where the historical loss is concentrated.
6. Two long-only filters (A2, B2) both improve 2024 and both leave 2025
   negative. The year split, not the filter, is the dominant variable.
7. Long and short trades are not independent samples — the strategy holds
   only one position at a time, so blocking shorts also changes which longs
   are open at a given moment. C1's long P&L (-34.19) differs slightly from
   baseline long P&L (-33.73) for exactly this reason.

## Research conclusion

**1. Results that improved historical metrics**
- A2 (`min_breakout_distance=0.002`): improved both years (+34.34 / +34.15),
  kept 83% of trades, lifted long_breakout from -27.00 to +12.09, and
  reduced drawdown from 1.74% to 1.08%. Most consistent single filter.
- C1 (long-only diagnostic) and D2/D3 also improved both years, but all
  three discard 50–63% of trades.

**2. Results that were inconsistent across years**
- A4 (0.004): +2.25 in 2024, -81.74 in 2025, with 2025 PF (0.578) worse
  than baseline (0.616).
- Every long-only variant: positive in 2024, negative in 2025.
- The full-period ranking (A4 best, A3 worse than A2) does not survive
  per-year inspection.

**3. Results that reduced losses but remained unprofitable**
- A2, A3, B2, B3, C1, C2, D1, D3 — all still negative over the full period.
- A2 is the closest: -87.16 with gross P&L of only -2.16, i.e. nearly
  cost-neutral before fees.

**4. Results that showed no meaningful improvement**
- A1 (0.001): bit-identical to baseline; the threshold is already implied
  by `breakout_buffer`.
- C2 (short-only): worse than baseline in 2024.
- D1 (A2+B2 combined): worse than either component alone.

**Overall:** no configuration produced a positive result in 2025, and none
produced a meaningfully positive result across both years. The evidence
supports a narrow, honest statement — *filtering weak breakouts and excluding
the short side reduces historical losses on this dataset* — and nothing
stronger. No configuration is shown to be profitable, and no historical
result here indicates how any of these filters would perform in future.
