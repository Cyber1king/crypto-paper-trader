# Phase 31 — Read-Only Post-Holdout Trade Analysis

**Status: DIAGNOSTIC RESEARCH ONLY. No strategy change, no parameter tuning, no
holdout rerun.**

This phase asks one question: **why did the frozen Phase 30B baseline lose
money?** It answers using only artifacts that already exist. The Phase 30B
holdout is **spent** and was not re-executed, re-evaluated, or reused as
validation. Nothing here is a strategy-optimisation proposal.

Every claim below carries one of three labels, as required:

| Label | Meaning |
|---|---|
| **DIRECTLY OBSERVED** | Supported by recorded trade data |
| **PLAUSIBLE HYPOTHESIS** | Consistent with the evidence, unproven |
| **NOT TESTABLE HERE** | Needs data or an experiment this phase forbids |

No causal claim is made, and no statistical significance is claimed anywhere.

---

## 1. Method and sources

### What was read

| Artifact | Role |
|---|---|
| `experiments/phase30/SUMMARY.md` | Phase 30B narrative report |
| `experiments/phase30/RESULTS_holdout.txt` | Recorded execution record |
| `experiments/phase30/RESULTS_holdout.json` | Machine-readable results, provenance |
| `experiments/phase30/RESULTS_trades.csv` | Per-trade table, 20 rows |
| `experiments/phase29/PREREGISTRATION.md` | The frozen protocol |
| `src/crypto_paper_lab/simulator.py` | Cost formulas (`:156-189`) |
| `src/crypto_paper_lab/stats.py` | Metric definitions (`:96-151`) |
| `src/crypto_paper_lab/strategy.py`, `backtest.py`, `costs.py`, `indicators.py` | Strategy and exit logic |

### What was NOT done

No backtest. No `run_backtest` call. No `analyze` call. No walk-forward
harness. No A2 configuration. No `validation_harness.main()`. No holdout
performance recalculation. No parameter selection. No news retrieval. No commit
or push.

### The one derivation performed, and why it is safe

Per-trade **fees and slippage are not recorded** in the Phase 30B artifacts —
only a combined `costs` column. They were reconstructed by arithmetic from
recorded `entry_price`, `exit_price` and `quantity`, using the frozen formulas in
`simulator.py:180-189`:

```
notional      = (entry_price + exit_price) × quantity
fee           = notional × 0.001
slippage      = notional × 0.0005
spread        = 0.0            (cost_deduction, simulator.py:185)
costs         = fee + slippage
```

This derivation **adds no new information** — it was validated against recorded
values before being used anywhere:

| Validation | Max residual |
|---|---|
| derived costs vs recorded `costs` column | 1.31e-06 |
| recomputed gross vs recorded `gross_pnl` | 5.50e-06 |
| recomputed net vs recorded `net_pnl` | 6.59e-06 |
| derived fee total vs recorded `fee_total` | 4.000928 vs 4.000930 |
| derived slippage total vs recorded `slippage_total` | 2.000464 vs 2.000465 |

All residuals are per-row floating-point rounding. Column names in
`TRADE_BREAKDOWN.csv` use `_recorded` and `_derived` suffixes so the distinction
is machine-visible.

### Recorded results verified against the Phase 30 report

| Quantity | Recorded | Verified |
|---|---|---|
| Trade count | 20 | 20 — agrees |
| Gross P&L | −6.321462 | −6.321462 — agrees |
| Total friction | 6.001395 | agrees (see discrepancy 1) |
| Net P&L | −12.322857 | −12.322857 — agrees |
| Winners / losers | 5 / 15 | 5 / 15 — agrees |
| Profit factor | 0.4925 | agrees (see discrepancy 2) |
| Ending balance | 9987.677143 | 9987.677143 — agrees |
| Exit counts | 19 opposite_signal, 1 end_of_data | 20 total — agrees |

**No discrepancy was found between the Phase 30 report and the underlying
artifacts.** Two apparent mismatches surfaced during checking and are documented
below rather than corrected.

---

## 2. Two documented discrepancies

### Discrepancy 1 — CSV rounding, not a data conflict

Summing the `costs` column of `RESULTS_trades.csv` gives **6.001396**; the
full-precision `total_friction` in the JSON is **6.001395**. The difference is
**1.15e-06**.

**Cause:** the CSV stores costs rounded to 6 decimal places; the JSON stores
full float precision. **Assessment:** not an error, no action taken. A reader
recomputing totals from the CSV should expect agreement only to ~1e-05.

### Discrepancy 2 — profit factor basis, a genuine methodological subtlety

An initial check computed a profit factor of **0.6805** against the recorded
**0.4925**. Both are correct; they use different bases:

| Basis | Wins | Losses | Profit factor |
|---|---|---|---|
| On **net** P&L (after friction) | +11.9593 | −24.2822 | **0.4925** — the recorded value |
| On **gross** P&L (before friction) | +13.4662 | −19.7877 | **0.6805** |

**Cause:** `stats.performance()` computes the ratio from `net_pnl`
(`stats.py:102-111`), but names its local variables `gross_profit` and
`gross_loss`. Those names describe winning/losing *trades*, not pre-cost P&L.

**Assessment:** not an error in the artifacts. The recorded 0.4925 is correct as
labelled in Phase 30. But **the variable names are misleading**, and the
pre-registration §8.1 inherited that wording, describing the formula as
"gross_profit / gross_loss". Anyone reading the code could reasonably believe the
metric is cost-free. Documented here; not corrected, as that would require
modifying source or frozen documents.

---

## 3. Per-trade results

Full table in `TRADE_BREAKDOWN.csv`. Summary of the 20 recorded trades:

| # | Side | Entry (UTC) | Exit (UTC) | Hold | Gross | Fee* | Slip* | Net | Exit reason |
|---|---|---|---|---|---|---|---|---|---|
| 1 | long | 09-03 13:00 | 09-04 14:00 | 25 h | +0.92 | 0.201 | 0.100 | **+0.62** | opposite_signal |
| 2 | short | 09-04 14:00 | 09-05 17:00 | 27 h | −0.84 | 0.201 | 0.100 | −1.14 | opposite_signal |
| 3 | long | 09-05 17:00 | 09-07 16:00 | 47 h | −1.52 | 0.198 | 0.099 | −1.82 | opposite_signal |
| 4 | short | 09-07 16:00 | 09-09 05:00 | 37 h | −0.44 | 0.200 | 0.100 | −0.74 | opposite_signal |
| 5 | long | 09-09 05:00 | 09-10 13:00 | 32 h | −2.87 | 0.197 | 0.099 | **−3.17** | opposite_signal |
| 6 | short | 09-10 13:00 | 09-11 13:00 | 24 h | −1.48 | 0.201 | 0.101 | −1.78 | opposite_signal |
| 7 | long | 09-11 13:00 | 09-13 09:00 | 44 h | −1.56 | 0.198 | 0.099 | −1.86 | opposite_signal |
| 8 | short | 09-13 09:00 | 09-14 10:00 | 25 h | −1.73 | 0.202 | 0.101 | −2.03 | opposite_signal |
| 9 | long | 09-14 10:00 | 09-15 07:00 | 21 h | −1.09 | 0.199 | 0.099 | −1.39 | opposite_signal |
| 10 | short | 09-15 07:00 | 09-18 04:00 | 69 h | −0.13 | 0.200 | 0.100 | −0.42 | opposite_signal |
| 11 | long | 09-18 04:00 | 09-20 03:00 | 47 h | +3.80 | 0.204 | 0.102 | **+3.50** | opposite_signal |
| 12 | short | 09-20 03:00 | 09-21 01:00 | 22 h | −1.59 | 0.201 | 0.101 | −1.89 | opposite_signal |
| 13 | long | 09-21 01:00 | 09-23 13:00 | 60 h | +4.78 | 0.205 | 0.102 | **+4.47** | opposite_signal |
| 14 | short | 09-23 13:00 | 09-27 08:00 | 91 h | +0.84 | 0.199 | 0.100 | +0.54 | opposite_signal |
| 15 | long | 09-27 08:00 | 09-28 02:00 | 18 h | −1.29 | 0.199 | 0.099 | −1.59 | opposite_signal |
| 16 | short | 09-28 02:00 | 09-30 13:00 | 59 h | −1.91 | 0.202 | 0.101 | −2.21 | opposite_signal |
| 17 | long | 09-30 13:00 | 10-02 19:00 | 54 h | −1.20 | 0.199 | 0.099 | −1.50 | opposite_signal |
| 18 | short | 10-02 19:00 | 10-04 10:00 | 39 h | −1.15 | 0.201 | 0.100 | −1.45 | opposite_signal |
| 19 | long | 10-04 10:00 | 10-07 02:00 | 64 h | −0.99 | 0.199 | 0.099 | −1.29 | opposite_signal |
| 20 | short | 10-07 02:00 | 10-08 23:00 | 45 h | +3.12 | 0.197 | 0.098 | **+2.83** | **end_of_data** |

\* Fee and slippage are **derived**, not recorded. See §1.

### Extremes, median, dominance

| Quantity | Value |
|---|---|
| Largest winner | #13 long, +4.47 net, 60 h hold |
| Second | #11 long, +3.50 net, 47 h |
| Third | #20 short, +2.83 net, 45 h |
| Worst | #5 long, −3.17 net, 32 h |
| **Median net per trade** | **−1.4220** |
| Mean net per trade | −0.6161 |
| Sum of top 3 winners | +10.795 |
| Net loss magnitude | 12.323 |

**DIRECTLY OBSERVED:** the three best trades (+10.795) equal **87.6%** of the
magnitude of the total loss. Removing them, the result would be **−23.12**.

**DIRECTLY OBSERVED:** the median trade (−1.422) lost **more than twice** the
mean (−0.616). The average is less negative than the typical trade purely
because five large winners pull it up. The typical trade lost money.

---

## 4. Loss patterns

### 4.1 Every exit was an opposite-signal exit, and most lost money

**DIRECTLY OBSERVED.**

| Exit reason | Count | Net P&L | Wins | Losses |
|---|---|---|---|---|
| `opposite_signal` | 19 | −15.148 | 4 | 15 |
| `end_of_data` | 1 | +2.825 | 1 | 0 |

No stop-loss, take-profit, max-holding or time exit occurred, because all three
are disabled by default in the frozen configuration (`max_holding_bars=None`,
`stop_loss_pct=None`, `take_profit_pct=None`). The only live exit rule is the
opposite-signal exit (`backtest.py:177-181`).

**DIRECTLY OBSERVED:** 15 of the 19 opposite-signal exits closed a losing
position. The mechanism that ends a trade is the same mechanism that ends a
winner — a reversal in the signal — and that reversal happened to arrive while
the position was underwater in 15 of 19 cases.

**NOT A CAUSAL CLAIM.** This shows the exit rule fires and often fires at a
loss. It does **not** show the exit rule caused the loss, nor that a different
exit would have helped.

### 4.2 Winners were held longer than losers

**DIRECTLY OBSERVED.**

| Group | n | Mean hold | Median hold | Min | Max | Net |
|---|---|---|---|---|---|---|
| Winners | 5 | 53.6 h | 47.0 h | 25 h | 91 h | +11.959 |
| Losers | 15 | 38.8 h | 37.0 h | 18 h | 69 h | −24.282 |

By holding-time bucket:

| Bucket | n | Net | Wins | Losses |
|---|---|---|---|---|
| 0–24 h | 3 | −4.870 | **0** | **3** |
| 24–48 h | 11 | −7.046 | 3 | 8 |
| 48–72 h | 5 | −0.950 | 1 | 4 |
| > 72 h | 1 | +0.543 | 1 | 0 |

**DIRECTLY OBSERVED:** the three shortest-hold trades (18 h, 21 h, 22 h) were
**all losers**. The single longest hold (91 h) was a winner. Winners' median hold
exceeded losers' by 10 hours.

**SAMPLE WARNING:** these buckets contain 3, 11, 5 and 1 trades. The 0–24 h
bucket is 3 trades, and "> 72 h" is a **single** trade. This is a descriptive
ordering in a 20-trade sample, not a reliable relationship.

**PLAUSIBLE HYPOTHESIS:** positions that resolve quickly may be resolving on
counter-trend noise rather than on a confirmed reversal, and may be paying full
friction for the privilege. Unproven.

**NOT TESTABLE HERE:** whether imposing a minimum holding period would improve
results. That requires rerunning the strategy with a changed rule, which this
phase forbids — and the holdout is spent anyway.

### 4.3 Both directions lost; shorts lost more

**DIRECTLY OBSERVED.**

| Side | n | Net P&L | Gross P&L | Mean hold | Median hold |
|---|---|---|---|---|---|
| long | 10 | −4.026 | −1.030 | 41.2 h | 45.5 h |
| short | 10 | −8.297 | −5.291 | 43.8 h | 38.0 h |

Both directions were unprofitable. Shorts lost roughly twice as much as longs.
The sample is balanced (10/10), so this is not a side-imbalance artefact.

**SAMPLE WARNING:** 10 trades per side. The gap could easily be noise.

**NOT TESTABLE HERE:** whether restricting to one side helps. Phase 7 already
examined a long-only variant on 2024–2025 data, and Phase 10 recorded the two
configurations as never ranked (`RESEARCH_STATE.json:267`).

### 4.4 The strategy was continuously in the market

**DIRECTLY OBSERVED.** Sum of `bars_held` across all 20 trades is **850 hours**;
the span from first entry (`2026-09-03 13:00`) to last exit
(`2026-10-08 23:00`) is also **850 hours**. There are **zero gaps** between a
trade's exit and the next trade's entry — each trade's entry timestamp equals its
predecessor's exit timestamp exactly.

So after the 48-bar warm-up the strategy held a position **continuously for the
entire 850-hour evaluation window**, taking 20 positions in sequence.

**PLAUSIBLE HYPOTHESIS:** a strategy with no flat periods has no ability to
stand aside during unfavourable conditions, and therefore pays friction on every
up-tick and down-tick in the window regardless of conditions. This is consistent
with the cost analysis in §5, where friction consumed 48.7% of the net loss.

**NOT TESTABLE HERE:** the pre-registration deliberately refused to compute
exposure/percent-of-time-in-market (`windowstats.py:8-12`, §8.4). That metric
does not exist in the library. The 850/864 figure above is derived purely from
recorded timestamps and bars_held, not from an exposure metric.

### 4.5 False breakouts and failed retests cannot be assessed

**NOT TESTABLE HERE.**

The strategy distinguishes four entry situations — `bullish retest`,
`bearish retest`, `uptrend breakout`, `downtrend breakdown`
(`strategy.py:177-192`). **The per-trade signal label was not recorded** in any
Phase 30B artifact.

Accordingly, **no claim is made about false breakouts, failed retests, or entry
quality.** Doing so would require re-deriving signals by rerunning the strategy
over the spent holdout, which is forbidden by this phase and would in any case
consume the holdout a second time.

The same gap blocks every indicator-level question. `PaperTrade` carries
`signal_close`, `trend_state`, `breakout_distance`, `retest_distance`,
`realised_volatility`, `mean_range`, `support_at_entry`, `resistance_at_entry`
(fields added in Phase 14C), but **none of these were persisted** into the
Phase 30B records. Confirmed absent by scanning the JSON, CSV and TXT artifacts.

### 4.6 Market-condition association cannot be assessed

**NOT TESTABLE HERE.** No market-regime variable, volatility measure, volume
context or price-trend annotation is recorded per trade. The only recorded
market attributes are the entry and exit prices themselves, from which a
descriptive price move was computed (e.g. #5 moved −2.874% against a long).

Grouping trades by "similar recorded market conditions" is not possible from the
recorded fields, because the recorded fields describe the trade, not the market
it occurred in.

---

## 5. Transaction-cost analysis

### Reconciliation of the gross-to-net bridge

**DIRECTLY OBSERVED.**

| Component | Value |
|---|---|
| Gross P&L | −6.321462 |
| − fees (0.1% per filled leg) | −4.000930 |
| − spread | −0.000000 |
| − slippage (0.05% per filled leg) | −2.000465 |
| = **Net P&L** | **−12.322857** |

Ending balance 10,000.0 − 12.322857 = **9,987.677143**, matching the recorded
value.

### Which components were actually nonzero

**DIRECTLY OBSERVED.** **Fees and slippage were nonzero; spread was exactly
zero.**

Spread is zero **by construction, not by assumption**: under `execution_model =
"cost_deduction"` the fill price equals the raw chart price, so spread cannot be
separated from slippage, and `TradingCosts` raises if `spread_rate > 0` is
combined with this model (`costs.py:77-82`). `spread_rate` is 0.0.

### How much friction mattered

**DIRECTLY OBSERVED.**

| Measure | Value |
|---|---|
| Total friction | 6.001395 |
| Friction per trade (mean) | 0.300070 |
| Friction as share of the **net** loss magnitude | **48.7%** |
| Gross loss excluding all friction | −6.321462 |
| Trades whose sign friction flipped | **0** |

Two conclusions follow, and the second matters more than the first:

1. Friction **roughly doubled** the loss, from −6.32 to −12.32.
2. **Friction did not create the loss and flipped no individual trade's sign.**
   The strategy was already losing money before any cost was charged.

**DIRECTLY OBSERVED.** `friction / gross P&L` is not reported. Phase 10 quoted
that ratio (86.2%, 65.8%) because its gross P&L was positive; here gross P&L is
negative, so the ratio is meaningless.

**DIRECTLY OBSERVED:** gross profit 13.4662 versus gross loss 19.7877 — a
**gross-basis profit factor of 0.6805**. Every trade would need to improve by
about 0.30 on average, roughly 23% of the average loss, merely to break even
after costs.

### Execution-model limitations affecting interpretation

**DIRECTLY OBSERVED from source inspection** (`simulator.py`, `costs.py`):

| Limitation | Consequence for this analysis |
|---|---|
| Flat proportional rates; no fee tiers, no volume-dependent pricing, no partial fills | Real friction on a venue would differ, probably worse for larger size |
| Spread forced to 0.0 under `cost_deduction` | The model **cannot** represent bid/ask cost separately; "costs" understates true traded friction by an unknown amount |
| Fills at raw chart price; slippage deducted as cash | Slippage is not reflected in fill prices, so stop/target levels and position sizing see friction-free prices |
| No funding, borrow, or interest | Long holds of 45–91 h incur no carry cost; a real venue would charge funding |
| No market-impact or latency model | 20 entries into a liquid pair would be largely unaffected, but this is untested |
| `fill_price` alternative exists and is **not** the frozen model | The alternative prices positions off the real fill; the frozen run did not use it |

**PLAUSIBLE HYPOTHESIS:** true friction including spread and funding is likely
higher than the 6.00 recorded, so the −12.32 net result may understate real
attrition. Unproven, and unprovable without venue data.

**NOT TESTABLE HERE:** whether the `fill_price` model would produce a different
result. That is a different execution model and would require rerunning.

---

## 6. News and sentiment — a hard limitation

**NOT TESTABLE HERE. This phase cannot establish whether news or sentiment
analysis would have improved these trades.**

What was checked:

| Source of timestamped news / sentiment / macro-event data | Present? |
|---|---|
| `RESULTS_holdout.json` | **No** |
| `RESULTS_trades.csv` | **No** |
| `RESULTS_holdout.txt` | **No** |
| `SUMMARY.md` (Phase 30B) | **No** |
| Any module in `src/crypto_paper_lab/` | **No** — the only textual match for "news" or "sentiment" anywhere is the word "headline" in an unrelated `robustness.py` docstring |
| Any data file under `research_engine/data/` | **No** — OHLCV only |

The repository contains **no news feed, no sentiment series, no economic-event
calendar, no order-book data, no volume profile and no funding-rate data.** The
strategy itself consumes only OHLCV (`Candle`: open, high, low, close, volume).

Consequently:

- No news or sentiment variable was available at any entry time, because none was
  ever collected.
- No such variable influenced any Phase 30B decision.
- **No historical headlines or sentiment scores have been invented, inferred or
  attached to any trade**, and none will be. Retrofitting narrative onto trades
  after the fact would manufacture a causal story that the data cannot support
  and would risk reading the outcome into a post-hoc explanation.

Whether news analysis would help is a question for a **separate, pre-registered
study on separate data** — not an inference from these 20 trades.

---

## 7. Prioritised recommendations for future investigation

None of these may be implemented in Phase 31, none involves choosing a parameter
value here, and **none may be validated on the Phase 30B holdout, which is
spent**.

### Priority 1 — Persist per-trade signal and indicator context

- **Observation:** the four entry labels and all Phase 14C indicator fields exist
  on `PaperTrade` but were not written to the Phase 30B artifacts (§4.5). Entry
  quality is therefore unassessable.
- **Proposed question:** do `bullish retest` / `uptrend breakout` / `bearish
  retest` / `downtrend breakdown` entries differ in outcome, and does
  `breakout_distance` or `trend_state` at entry relate to outcome?
- **Supporting evidence:** consistent per-label net P&L across a sample large
  enough to exceed the repository's ~50-trade floor for even an inconclusive
  comparison (`phase9/ACQUISITION_PLAN.md:135-146`).
- **Rejecting evidence:** per-label differences that vanish, or that reverse
  sign, on a second window.
- **Data required:** the existing 2024–2025 research set for development
  instrumentation work; a **new** genuinely unseen holdout for any conclusion.
- **Overfitting risk: LOW** for the instrumentation itself — it changes no
  behaviour and records what already happens. **HIGH** if entry labels are then
  used to build filters.

### Priority 2 — Quantify whether friction-free operation is ever viable

- **Observation:** friction was 48.7% of the net loss and flipped no trade's
  sign; the strategy was already negative pre-cost (§5). Average improvement of
  ~0.30 per trade (~23% of the average loss) would be needed just to break even
  after costs.
- **Proposed question:** on 2024–2025 data, what is the friction-free profit
  factor of the frozen baseline, and how large is the gap to 1.0? If
  friction-free performance is already far below 1.0, no realistic cost model
  rescues the strategy and cost optimisation is pointless.
- **Supporting evidence:** a friction-free profit factor materially below 1.0.
- **Rejecting evidence:** friction-free profit factor near or above 1.0, which
  would redirect attention to cost modelling instead of signal quality.
- **Data required:** 2024–2025 only. This is a development question.
- **Overfitting risk: LOW** — a single descriptive statistic on existing data,
  no parameter search.

### Priority 3 — Examine the continuous-exposure behaviour

- **Observation:** the strategy held a position for all 850 evaluated hours with
  zero flat periods, taking 20 sequential positions (§4.4), and the three
  shortest holds were all losers (§4.2).
- **Proposed question:** does the baseline's signal fire near-continuously
  because of its trend/breakout design, and how does that interact with friction?
  On 2024–2025, how often would it have been flat, and does a flat period
  correspond to a losing regime?
- **Supporting evidence:** on 2024–2025, an association between
  would-be-flat periods and subsequent drawdown, measured on data already
  consumed by earlier phases.
- **Rejecting evidence:** no association, indicating exposure is incidental.
- **Data required:** 2024–2025 for development. **Not** the spent holdout.
- **Overfitting risk: MEDIUM-HIGH.** Any rule about when to stand aside is a new
  parameter, and Phase 13 already established that walk-forward windows can be
  individually misleading. `RESEARCH_STATE.json:394-402` lists several
  closely-related paths that must not be treated as validation.

### Priority 4 — Compare execution models on development data

- **Observation:** the frozen run used `cost_deduction` with spread forced to 0.
  The `fill_price` alternative exists and prices from the real fill (§5).
- **Proposed question:** does `fill_price` produce materially different net
  results on 2024–2025, and how much of the difference is the absence of spread?
- **Supporting/rejecting evidence:** a measured divergence in net P&L between the
  two models on identical candles.
- **Data required:** 2024–2025 only.
- **Overfitting risk: LOW** — an accounting comparison, not a strategy change.
  Note `costs.py:46-54` already warns the two models are only approximately
  equivalent.

### Priority 5 — Re-verify the reported profit-factor basis

- **Observation:** `stats.performance()` names its net-P&L sums `gross_profit`
  and `gross_loss` (`stats.py:102-111`), so the reported 0.4925 is a **net**
  figure while the gross-basis factor is 0.6805 (§2, discrepancy 2).
- **Proposed question:** should the reporting surface both bases and rename the
  locals, so a reader cannot mistake a post-cost metric for a pre-cost one?
- **Supporting evidence:** code review confirming the ambiguity is a real
  reading risk.
- **Data required:** none. Documentation and naming only.
- **Overfitting risk: NONE** — no behaviour change.
- **Caveat:** this would modify source and would invalidate recorded digests, so
  it needs its own phase and must not touch frozen artifacts.

---

## 8. Consolidated findings

| # | Finding | Label |
|---|---|---|
| 1 | Recorded Phase 30B results agree with its report on all seven checked quantities | DIRECTLY OBSERVED |
| 2 | Friction did not create the loss and flipped no trade's sign; it roughly doubled a pre-existing loss | DIRECTLY OBSERVED |
| 3 | Fees 4.00 and slippage 2.00 were nonzero; spread is 0.0 by model construction | DIRECTLY OBSERVED |
| 4 | All 20 exits came from two mechanisms; 15 of 19 opposite-signal exits closed a loss | DIRECTLY OBSERVED |
| 5 | Winners held longer than losers (median 47 h vs 37 h); the 3 shortest holds were all losers | DIRECTLY OBSERVED, n=20 |
| 6 | Both directions lost; shorts lost about twice as much as longs | DIRECTLY OBSERVED, 10 per side |
| 7 | The strategy held a position continuously for all 850 evaluated hours, zero flat periods | DIRECTLY OBSERVED |
| 8 | Three best trades = 87.6% of the net loss magnitude; median trade −1.42 was worse than the mean −0.62 | DIRECTLY OBSERVED |
| 9 | The reported profit factor 0.4925 is a net-of-cost figure; gross-basis is 0.6805 | DIRECTLY OBSERVED |
| 10 | Reported `profit_factor` variable names in `stats.py` are misleading | DIRECTLY OBSERVED |
| 11 | Faster-resolving positions may be counter-trend noise paying full friction | PLAUSIBLE HYPOTHESIS |
| 12 | No flat periods means no ability to stand aside in unfavourable conditions | PLAUSIBLE HYPOTHESIS |
| 13 | True friction is likely higher than 6.00 because spread and funding are unmodelled | PLAUSIBLE HYPOTHESIS |
| 14 | Entry quality, false breakouts and failed retests | NOT TESTABLE — signals not recorded |
| 15 | Market-regime association | NOT TESTABLE — no regime variables recorded |
| 16 | Whether news or sentiment would have helped | NOT TESTABLE — no such data exists anywhere |
| 17 | Whether any exit or holding rule would help | NOT TESTABLE — requires rerunning a spent holdout |
| 18 | Whether trade outcomes cluster in market conditions | NOT TESTABLE — fields describe trades, not markets |

### What this analysis does not establish

It does not establish that the strategy is unprofitable. Twenty trades across 38
days on one venue cannot do that, and the pre-registration declared the outcome
INCONCLUSIVE before these numbers existed. The standing conclusion in
`RESEARCH_STATE.json:14` is unchanged. Nothing here revises it.

The Phase 30B holdout is **spent** and must never be reused as fresh validation.

---

## 9. Missing data register

| Requested | Status |
|---|---|
| Per-trade fee and slippage | Not recorded; derived from prices and validated to 1e-06 |
| Per-trade signal label | **Not recorded and not derivable** without rerunning |
| Indicator values at entry (`breakout_distance`, `trend_state`, `retest_distance`, `support`/`resistance`, volatility, `mean_range`, `signal_close`) | **Not recorded and not derivable** without rerunning |
| Market-regime or volatility context per trade | **Not recorded**; OHLCV exists in the dataset but was not annotated per trade |
| Exposure / percent time in market | **Deliberately never computed** (`windowstats.py:8-12`) |
| Order-book, volume-profile, funding data | **Does not exist in the repository** |
| News, sentiment, economic-event data | **Does not exist in the repository** |
| Any marker of what the market was doing | Not recorded |

Per the mission, no requested breakdown was obtained by expanding scope beyond
what the artifacts contain.

---

## 10. Restrictions honoured

- No strategy change. No parameter tuned. No new parameter chosen.
- The spent holdout was not rerun, re-evaluated or reused as validation.
- No backtest, `run_backtest` call, `analyze` call, walk-forward harness, A2
  configuration or `validation_harness.main()` invocation.
- No holdout performance recalculated; only arithmetic over already-recorded
  values, validated against recorded values.
- No news or sentiment fetched, invented or attached to any trade.
- No cost model modified.
- No recommendation implemented.
- No existing file overwritten, renamed, moved or deleted.
- Nothing staged, committed or pushed.

Integrity evidence is in `VERIFICATION.txt`.