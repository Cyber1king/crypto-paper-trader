# Phase 13 - Walk-Forward Results

All figures below are **descriptive**. No profitability threshold,
pass/fail rule, score or configuration ranking is applied or implied.

- Dataset: `data/BTCUSDT_1h_Cleaned (1).csv`
- Dataset SHA-256: `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B`
- Git commit: `f5293c91da33e929a230ff385ab4458cfa232fee`
- Git working tree clean: **False**
- Execution model: `cost_deduction` (fee 0.001, slippage 0.0005, spread 0.0)
- Warm-up rule: `full_preceding_series`
- Boundary policy: `retain_boundary_force_closes`

> **Recorded deviation:** this run was executed with a dirty
> working tree under an explicit override. The Phase 13
> pre-registration requires a clean tree so a run can be tied to
> an exact commit. The dirty state at execution time was:
>
>     ` M research_engine/src/crypto_paper_lab/stats.py`
>     `?? research_engine/experiments/phase13/`
>     `?? research_engine/src/crypto_paper_lab/walkforward.py`
>     `?? research_engine/src/crypto_paper_lab/windowstats.py`
>     `?? research_engine/tests/test_walkforward.py`
>     `?? research_engine/tests/test_windowstats.py`
>
> The clean-tree guard itself was not weakened; it refused the run
> until the override was supplied explicitly.

## Pass: baseline

baseline is the unmodified V1 StrategyConfig(); no Phase 13 result was used to select it.

| window | eval start | eval end | trades | end_of_data | win rate | profit factor | gross | net | total friction | max DD | ending balance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-07-01 | 2024-09-30 | 50 | 1 | 0.3200 | 0.6428 | -16.6703 | -31.6577 | 14.9874 | 0.0042 | 9968.3423 |
| 2 | 2024-10-01 | 2024-12-31 | 42 | 1 | 0.3095 | 0.9209 | 7.8007 | -4.8754 | 12.6761 | 0.0032 | 9995.1246 |
| 3 | 2025-01-01 | 2025-03-31 | 43 | 1 | 0.3256 | 0.6458 | -11.7908 | -24.6519 | 12.8611 | 0.0045 | 9975.3481 |
| 4 | 2025-04-01 | 2025-06-30 | 52 | 1 | 0.2308 | 0.3566 | -34.1409 | -49.7325 | 15.5915 | 0.0053 | 9950.2675 |
| 5 | 2025-07-01 | 2025-09-30 | 38 | 1 | 0.3421 | 0.8624 | 6.7411 | -4.6688 | 11.4099 | 0.0015 | 9995.3312 |
| 6 | 2025-10-01 | 2025-12-31 | 42 | 1 | 0.3810 | 0.7066 | -5.7070 | -18.2733 | 12.5663 | 0.0033 | 9981.7267 |

- Windows: 6 (positive 0, negative 6, zero 0)
- Window net P&L - min -49.7325, max -4.6688, median -21.4626
- Window net P&L sorted: [-49.73, -31.66, -24.65, -18.27, -4.88, -4.67]
- Window profit factor sorted: [0.3566, 0.6428, 0.6458, 0.7066, 0.8624, 0.9209]
- Longest same-sign run: 6
- Boundary-affected (end_of_data) trades retained: 6

Windows are sequential historical periods, not independent draws.
Aggregate figures therefore overstate precision. No window-level
confidence interval is produced (six windows).

## Pass: A2

A2 (min_breakout_distance=0.002) was selected during Phase 7 using 2024-2025 research data. Evaluation windows 2-6 fall inside that selection period, so these results are NOT clean independent validation.

| window | eval start | eval end | trades | end_of_data | win rate | profit factor | gross | net | total friction | max DD | ending balance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-07-01 | 2024-09-30 | 44 | 1 | 0.3636 | 0.6986 | -9.8204 | -23.0135 | 13.1932 | 0.0035 | 9976.9865 |
| 2 | 2024-10-01 | 2024-12-31 | 34 | 1 | 0.3529 | 1.2495 | 22.4399 | 12.1617 | 10.2781 | 0.0020 | 10012.1617 |
| 3 | 2025-01-01 | 2025-03-31 | 39 | 1 | 0.3077 | 0.6403 | -11.5628 | -23.2288 | 11.6660 | 0.0040 | 9976.7712 |
| 4 | 2025-04-01 | 2025-06-30 | 36 | 1 | 0.2778 | 0.5379 | -12.8292 | -23.6480 | 10.8187 | 0.0028 | 9976.3520 |
| 5 | 2025-07-01 | 2025-09-30 | 30 | 1 | 0.3667 | 1.0660 | 10.7350 | 1.7237 | 9.0113 | 0.0011 | 10001.7237 |
| 6 | 2025-10-01 | 2025-12-31 | 34 | 1 | 0.3824 | 0.7122 | -6.5117 | -16.6786 | 10.1669 | 0.0039 | 9983.3214 |

- Windows: 6 (positive 2, negative 4, zero 0)
- Window net P&L - min -23.6480, max 12.1617, median -19.8460
- Window net P&L sorted: [-23.65, -23.23, -23.01, -16.68, 1.72, 12.16]
- Window profit factor sorted: [0.5379, 0.6403, 0.6986, 0.7122, 1.066, 1.2495]
- Longest same-sign run: 2
- Boundary-affected (end_of_data) trades retained: 6

Windows are sequential historical periods, not independent draws.
Aggregate figures therefore overstate precision. No window-level
confidence interval is produced (six windows).

## Limitations

1. Six windows is a small number; window-level inference is not
   supported and no window-level confidence interval is given.
2. Roughly 43 trades per evaluation window on average, so per-window
   metrics are noisy and profit factor is unstable in windows with
   few or no losing trades.
3. Boundary force-closes are retained, not discarded, and affect a
   small non-zero share of window trades with arbitrary sign.
4. A2 was selected in Phase 7 on 2024-2025 data, so its results are
   not clean independent validation for windows 2-6.
5. Indicator state is shared across boundaries by design.
6. Exposure / percent of time in market is not available and is not
   estimated.
7. Single asset, single timeframe, single market regime.
8. Phase 13 is retrospective and says nothing about any later period.

This report makes no claim about profitability, does not rank the
two configurations and does not predict future performance.
