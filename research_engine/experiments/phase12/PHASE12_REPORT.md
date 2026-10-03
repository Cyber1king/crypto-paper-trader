# Phase 12 — Execution Realism Audit

## Scope

Audit and improvement of the paper-trading execution model in
`research_engine`. No strategy logic, strategy default parameter, dataset,
archive, checksum, provenance file or historical research result was changed.

This is a research and paper-trading project. Nothing here connects to an
exchange, places an order, or introduces leverage or margin.

## 1. Original execution assumptions

As found in the code before this phase:

| Item | Implementation |
|---|---|
| Entry price | `signal.price` verbatim; `backtest` supplies `candles[i].open` |
| Exit price | The price passed to `PaperBroker.close`, verbatim |
| Position size | `quantity = cash * risk_fraction / signal.price` |
| Fees | `(entry_value + exit_value) * fee_rate`, i.e. once per leg |
| Slippage | `(entry_value + exit_value) * slippage_rate`, deducted from P&L |
| Spread | Not represented |
| Default `fee_rate` | `0.001` |
| Default `slippage_rate` | `0.0005` |

Both legs were charged slippage, and the charge was adverse in both
directions: a long paid `(in+out) notional x rate` and so did a short.

## 2. Audit findings

### Verified as already correct

- **Slippage was applied to both entry and exit.** Confirmed by code
  inspection and by a numerical sweep over long/short trades at five exit
  prices.
- **Directional symmetry was correct.** An initial suspicion that shorts were
  mis-charged was tested and found to be wrong. At fixed quantity the legacy
  `(in+out) x rate` deduction equals adverse proportional slippage applied to
  both fills, for both directions.
- **Backtest and simulator could not drift apart.** `run_backtest` delegates
  every fill to the single `PaperBroker` implementation, so there was only one
  execution path to keep consistent.
- **No future data leaked.** Signals are computed from `candles[:index]` and
  filled at `candles[index].open`.

### Confirmed problems

1. **Recorded prices were not fills.** `entry_price` and `exit_price` stored
   the raw chart price, so every reported price was fictitious and every
   downstream consumer inherited that fiction.
2. **Stop-loss and take-profit were anchored to the wrong price.**
   `backtest._levels_breached` measured `trade.entry_price * (1 +/- d)`.
   With the raw price recorded, stop and target levels sat off by exactly the
   slippage.
3. **Position size ignored the fill.** The committed notional was not
   `cash * risk_fraction` whenever the fill differed from the reference.
4. **Fees were charged on raw notional**, not on what was actually paid.
5. **No separate spread concept**, so spread cost was indistinguishable from
   size/latency slippage.
6. **`trade.costs` was undifferentiated**, so fees, spread and slippage could
   not be reported separately.

## 3. Changes made

### `costs.py`

Added two fields, keeping both existing defaults and their positional order so
that every existing `TradingCosts(0.001, 0.0005)` call is unaffected:

- `spread_rate: float = 0.0` — proportional half-spread per leg, kept
  separate from `slippage_rate`.
- `execution_model: Literal["cost_deduction", "fill_price"]` — default
  `"cost_deduction"`.

Plus an `adverse_rate` property (`spread_rate + slippage_rate`) and validation
that rejects a non-zero `spread_rate` under `"cost_deduction"`, because the
spread is then indistinguishable from slippage and charging both would double
count.

### `models.py`

`PaperTrade` gained six defaulted fields: `raw_entry_price`,
`raw_exit_price`, `fee_total`, `slippage_total`, `spread_total`, plus a
`total_friction` property. Being defaulted, existing constructions in tests and
experiment scripts keep working unchanged.

### `simulator.py`

`_fill_price` applies the adverse move to a leg: buying adds
`adverse_rate`, selling subtracts it, so opening and closing a long are exact
opposites.

- **`cost_deduction` (default):** byte-for-byte the previous behaviour.
- **`fill_price`:** fills are the prices actually paid or received, size
  derives from the real entry fill, fees are charged on filled notional, and
  spread/slippage are *attributed* rather than deducted, because they are
  already inside the recorded prices.

### `backtest.py`

No logic change was required. `_levels_breached` already reads
`trade.entry_price`; once that field holds the true fill, stop and target
levels are anchored correctly. Only docstrings were updated to record this.

## 4. Formulas

Let `s` = `spread_rate + slippage_rate` = `adverse_rate`,
`f` = `fee_rate`, `cash` = cash, `r` = `risk_fraction`,
`P_in` / `P_out` = raw reference prices, `q` = quantity.

**`fill_price` model**

```
is_buy(entering) = (side == "long") == entering
sign             = +1 if is_buy else -1

entry_fill = P_in  * (1 + sign(entry) * s)
exit_fill  = P_out * (1 + sign(exit)  * s)

q          = cash * r / entry_fill
pnl        = (exit_fill - entry_fill) * q * direction
fee_total  = (entry_fill * q + exit_fill * q) * f
spread_total    = (P_in * q + P_out * q) * spread_rate
slippage_total  = (P_in * q + P_out * q) * slippage_rate
costs      = fee_total            # spread/slippage already in the prices
net_pnl    = pnl - costs
```

`total_friction = fee_total + spread_total + slippage_total`.

**`cost_deduction` model (unchanged)**

```
entry_fill = P_in
exit_fill  = P_out
q          = cash * r / P_in
pnl        = (P_out - P_in) * q * direction
fee_total  = (entry_fill * q + exit_fill * q) * f
slippage_total = (entry_fill * q + exit_fill * q) * slippage_rate
spread_total    = 0.0
costs      = fee_total + slippage_total
net_pnl    = pnl - costs
```

**No double counting.** In both models `net_pnl == pnl - costs` holds
identically, and total friction is charged exactly once: either inside the
fill price or as a deduction, never both. For a long,
`(P_out(1-s) - P_in(1+s)) * q = (P_out - P_in) * q - s * (P_in + P_out) * q`,
so the spread and slippage attributed on raw notional exactly account for the
difference between raw and filled gross P&L. The same identity holds for a
short.

## 5. Test results

Phase 12 checkpoint, before the section 8 remediation:

```
$ python -m pytest tests/ -q
237 passed
```

- Pre-existing suite: **177 passed**, unchanged and unreduced.
- New `tests/test_execution_model.py`: **60 passed**.
- Failed: **0**. Skipped: **0**.

The final post-remediation counts are recorded in section 8.

New coverage: entry and exit fill prices, entry and exit fees, slippage in
both directions for long and short, spread modelled separately, net P&L after
all costs, the `net_pnl == pnl - costs` identity across five exit prices and
both directions, zero-cost edge cases, cost-model validation and rejection
rules, position sizing, backtest/PaperBroker consistency, stop-loss anchoring,
determinism, and a check that no leverage or margin can be introduced.

All expected values are hand-calculated on round prices. No test asserts
profitability or any performance threshold.

## 6. Impact on earlier research

**None of the stored results changed.** The default execution model is still
`cost_deduction`, so every Phase 5-11 number is preserved.

Verified by re-running the read-only analyses:

| Analysis | Stored | Re-run | Difference |
|---|---|---|---|
| `RESULTS_robustness.txt` | 267 lines | 267 lines | **0** |
| `RESULTS_dependence.txt` | 61 lines | 61 lines | **0** |
| Phase 10 OOS verdict | "NOT distinguishable from zero" | same | **0** |

All 123 files under `experiments/` and `data/` were SHA-256 compared before
and after: **0 changed, 0 deleted**. Datasets, ZIP archives, checksums and
provenance files are byte-identical; all 8 archives still match their
published checksums.

### What the new model would change

Same parameters, no tuning, on the merged 2026 OOS dataset (5,832 candles):

| Assumption set | Trades | Net P&L | Total friction |
|---|---|---|---|
| Legacy `cost_deduction` (0.1% fee, 0.05% slippage) | 105 | 7.2630 | 31.5280 |
| `fill_price`, same rates | 105 | 7.2655 | 31.5278 |
| `fill_price` + 0.02% spread | 105 | 3.0652 | 35.7240 |

Two factual observations:

1. Switching to `fill_price` at identical rates moves net P&L by **+0.0024**
   and leaves the trade count unchanged, confirming the two models are
   equivalent in P&L up to second-order sizing and fee-base effects.
2. Adding a 0.02% half-spread per leg reduces the recorded OOS net P&L by
   **4.20**, from 7.26 to 3.07. The small edge already recorded for the OOS
   period is of the same order as the cost of a realistic spread.

This is reported as a sensitivity observation only. No parameter was selected
for being favourable, and the OOS dataset was not used to tune anything.

## 7. Remaining limitations

1. **The bid-ask spread is a proportional approximation.** Hourly OHLC
   candles carry no bid/ask information, so the true spread is not observable
   from the available data. `spread_rate` must be supplied from external
   knowledge of the venue and is a single constant, not a function of size or
   volatility. A size-dependent or volatility-dependent spread cannot be
   implemented correctly with this data.
2. **Slippage is proportional and constant.** Real slippage varies with order
   size relative to volume, and during gaps. A fixed rate cannot capture that.
3. **No partial fills, no market impact, no order-book depth, no funding or
   borrow cost.** A short is modelled as a symmetric position with no
   borrow fee and no liquidation risk, which understates the cost of a short.
4. **Intrabar fills are never assumed.** Stop and target rules detect on a
   closed bar and fill at the next open, so a stop touched intrabar records a
   trigger rather than the realised price. When one bar breaches both levels
   the stop is assumed first, which changes only the recorded label.
5. **Candle-level fills only.** Entries and exits use the next candle's open
   or the final close, so gaps across the fill are captured but intra-candle
   paths are not.
6. **The spread in `fill_price` mode is charged against the raw reference
   notional** for attribution, which is exact for the difference between raw
   and filled P&L but means `spread_total` is a reporting figure rather than a
   separately settled cash amount.
7. **No parameter fitting was performed.** Nothing here demonstrates that the
   strategy is profitable, and more realistic execution does not make it
   suitable for real trading.

## 8. Phase 12.1 remediation

An independent code review of the above found the execution math correct but
identified one untested behaviour, one reporting integration risk and several
documentation issues. All were addressed without changing any execution
formula, strategy parameter or research result.

### Stop anchoring was correct but unpinned

`_levels_breached` anchors to `trade.entry_price`, the recorded fill, so stop
and target levels are measured from the price actually paid. A mutation that
reverted this to `raw_entry_price` passed the entire suite at the time of
review. The suite now pins all four branches:

| Branch | Discriminating behaviour |
|---|---|
| Long stop | fill-referenced stop fires; raw-referenced one does not |
| Short stop | fill-referenced stop fires; raw-referenced one does not |
| Long take-profit | raw-referenced target fires; fill-referenced one does not |
| Short take-profit | raw-referenced target fires; fill-referenced one does not |

The polarity is not uniform, and that is correct rather than accidental. A long
fills above the reference, so its stop is higher (easier to hit) and its
target is also higher (harder to hit). A short fills below the reference, so
both its stop and its target move down, both easier to hit. Consequently a
long take-profit and a short take-profit can only discriminate in one
direction each, and the tests document why.

An end-to-end test also asserts that stop-loss exit *counts* differ between the
two models on a series whose single dip falls inside the anchoring window:
`cost_deduction` records 0 stop exits, `fill_price` records 1.

### Cost reporting integration

`stats.py` gained `total_friction`, `total_fees`, `total_spread`,
`total_slippage` and `cost_breakdown`. Reporting code that shows cost as the
bridge between gross and net P&L now uses `total_friction`.

This matters because `trade.costs` is not the total cost under `fill_price`.
On the 2026 OOS dataset with a 0.02% half-spread:

| Metric | legacy | `fill_price` |
|---|---|---|
| `sum(t.costs)` | 31.528 | 21.014 |
| `total_friction` | 31.528 | 35.724 |

Summing `trade.costs` under `fill_price` understated the true cost by 41%.
Under the default model the two are the same number to the last bit, so no
historical report changes.

Two sites deliberately keep `trade.costs`, because they reconcile
`gross - costs == net` for an individual trade or period and therefore need
the amount actually *deducted* rather than the total: the per-trade record in
`diagnose_trades.py` (which now also reports `total_friction` alongside) and
the reconciliation block in `baseline_reproduction.py` (whose misleading
`total_fees` local was renamed to `total_deducted`; printed text unchanged).

### Docstring correction

The `TradingCosts` docstring previously claimed the two models were
"equivalent in P&L to within the fee base (a few parts in 1e6)". Measurement
puts the worst-case relative difference near 5e-4 at the default 0.05%
slippage, driven mainly by the position-sizing basis rather than the fee base.
The docstring now states the two are only approximately equivalent, names both
causes, and warns against comparing runs that mix models.

### Raw-reference invariant

`PaperBroker.close` previously read `(trade.raw_entry_price or 0.0)`, which
silently halved reported friction for a trade constructed without that field.
Under `fill_price` it now raises a clear `ValueError`. The check is scoped to
`fill_price`, because `cost_deduction` never reads the field, so legacy trades
built without it continue to work.

### Newlines

`costs.py`, `simulator.py` and `test_execution_model.py` now end with exactly
one newline, removing the `\ No newline at end of file` marker that would
otherwise recur in every future diff.

### Final test results

```
$ python -m pytest tests/ -q
254 passed
```

- Pre-existing suite: **177 passed**, unchanged and unreduced.
- `tests/test_execution_model.py`: **77 passed**.
- Failed: **0**. Skipped: **0**.

### Scope

The remediation touched 17 files: 6 library modules, 9 experiment and
reporting scripts, and 2 new files (this report and
`tests/test_execution_model.py`). No dataset, archive, checksum, provenance
file, historical report or strategy default was modified.

## 9. Conclusion

The legacy execution model charged both legs and was directionally symmetric;
its defects were that recorded prices were not fills, that stop and target
levels were anchored to a price the trader would never receive, that position
size ignored the fill, that fees were charged on the wrong notional, and that
spread could not be represented at all.

`fill_price` corrects all five while keeping the model deterministic and
single-sourced with the backtest. It is opt-in, so every previously recorded
research result continues to reproduce exactly.