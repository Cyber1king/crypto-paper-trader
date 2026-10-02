# Phase 8 — Out-of-Sample Validation Plan

Written before any validation run, so the design is on record independently
of its outcome.

## Objective

Determine whether the Phase 7 finding — that the `min_breakout_distance =
0.002` filter (A2) reduces historical losses relative to the original
baseline — persists on data that played no part in choosing it.

## Configurations under test (exactly two, no others)

| ID | Configuration | Source |
|---|---|---|
| A | Original baseline, all optional research filters disabled | `StrategyConfig()` defaults |
| B | Phase 7 A2: baseline with `min_breakout_distance = 0.002` | `replace(StrategyConfig(), min_breakout_distance=0.002)` |

No thresholds, no combinations, no additional filters.

## Held constant between A and B

| Setting | Value |
|---|---|
| Starting balance | $10,000.00 |
| Fee rate | 0.001 |
| Slippage rate | 0.0005 |
| Position sizing | `risk_fraction = 0.01` of then-current cash |
| Execution model | next-candle open; signals from closed candles only |
| Validation period | identical candle range |
| Warm-up length | identical |

## Data requirements

A validation dataset is accepted only if **all** hold:

1. It contains at least `WARMUP_CANDLES = 48` leading bars of context.
   (48 > the 22 bars the strategy needs: `max(lookback + 2, slow_period)` =
   `max(22, 12)`.)
2. Its **first validation-eligible timestamp is strictly after
   2025-12-31 23:00**, the end of the Phase 7 window. Any overlap means the
   data is not unseen and the run is refused.
3. Timestamps are strictly increasing and contiguous at 1-hour spacing
   (no duplicates, no gaps).
4. OHLC relationships are internally consistent and prices are positive
   (`validate_dataset` passes).
5. The file is readable by the existing loader without modification.

## Warm-up and boundary design

- Warm-up bars are prepended to the same in-memory candle list and are used
  **only** to fill the indicator lookback windows.
- Entries are gated by `run_backtest(..., evaluation_start=N)` where `N` is
  the index of the first validation bar. No position can be opened before
  that index.
- Because no position can be open at the boundary, **the account starts flat
  at the boundary with the full $10,000**. No balance carries over from
  warm-up, and nothing is silently reset between configurations.
- Signals during warm-up are still computed (so indicators are warm) but
  discarded.
- The gate blocks **entries only**. An open position still exits on an
  opposite-side signal exactly as in the baseline.
- Any position still open at the final candle is closed at that candle's
  close and labelled `end_of_data`. The count and P&L contribution of these
  forced closes are reported so the boundary effect is visible.

## Metrics reported per configuration

Trades, net P&L, return, win rate, profit factor, maximum drawdown, ending
balance, total fees+slippage, gross P&L, average net P&L per trade, long
breakdown, short breakdown, exit-reason breakdown, and an explicit
positive/negative-after-costs verdict.

## Cost assumptions

Fixed at fee 0.001 / slippage 0.0005 for the primary comparison. No
cost sensitivity analysis is included, because presenting hypothetical
lower costs alongside a primary result invites misreading. If costs ever
become the research question, that belongs in a separate, clearly labelled
hypothetical section.

## Anti-overfitting commitments

- No tuning on the validation set. A2's parameter was fixed in Phase 7.
- The harness reports whichever result it finds, including a negative one.
- If the validation window yields too few trades to be informative, that is
  reported as inconclusive rather than suppressed.

## Decision rule (fixed in advance)

- If both A and B are negative on unseen data → the Phase 7 "improvement"
  does not generalise; report that plainly.
- If B beats A on unseen data → report it as a *single* out-of-sample
  observation, explicitly insufficient to establish future performance.
- Any outcome is one window on one asset. None of these outcomes authorises
  selecting or deploying a strategy.
