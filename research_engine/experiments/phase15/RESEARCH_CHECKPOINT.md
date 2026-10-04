# Phase 15 — Research Checkpoint / Project State Audit

**Status: documentation and audit only.**

No strategy logic, entry rule, exit rule, position-sizing rule, dataset or
prior result artifact was modified. No experiment was run. No parameter was
tuned, no sweep was executed, and no configuration was selected or ranked.
Nothing was committed or pushed. Phase 16 was not started.

Recorded at commit `25bd7d0ab651e356240d8148525fb664938562b0` with a dirty
working tree (Phase 14B and 14C source and results are uncommitted).

Every figure below is taken from an existing project record. Where a value
could not be established from the repository, that is stated rather than
filled in. Section 14 lists the three places where the record is incomplete.

---

## 1. Scope

This checkpoint exists to fix the research boundary before any further
experiment. It documents what the project has established, what it has not,
and which research paths remain legitimately available given that **no unused
validation data remains**.

**Standing research conclusion, unchanged since Phase 10: no reliable
profitability has been established.** Across 23,376 hourly candles, 12 or more
configurations and two full evaluation periods, this project has no evidence of
a profitable trading rule. Phase 15 does not revise that conclusion and must
not be used to revise it.

It deliberately does not propose a next strategy, a next parameter, or a next
configuration. Naming a "best" anything would convert a descriptive record
into an optimisation instruction, which is the specific outcome this phase
exists to prevent.

---

## 2. Data used

Two datasets, both already consumed. No data was acquired, downloaded or
modified.

| Role | Path | Range | Candles |
| --- | --- | --- | --- |
| Research (in-sample) | `data/BTCUSDT_1h_Cleaned (1).csv` | 2024-01-01 → 2025-12-31 | 17,544 |
| Out-of-sample (consumed) | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` | 2026-01-01 → 2026-08-31 | 5,832 |

Total 23,376 candles, matching the figure reported independently in Phase 10
and Phase 11.

The 2024–2025 dataset has **no documented provenance**. This has been an open
gap since Phase 9. Binance discloses that archived files may be revised;
timestamp continuity across the 2025/2026 boundary is established, construction
continuity is not.

---

## 3. The complete research pipeline

### Phases 1–4 — foundation, strategy and backtest development

**No report artifact exists for Phases 1–4.** They predate the
experiment-record convention used from Phase 5 onward. What is established
about them comes from the git log and from cross-references in the Phase 5 and
Phase 9 summaries, and nothing more is claimed here.

The git log records the work: initial trade-analysis and signal tests, a
baseline trade-signal analysis enhancement, three readability refactors of
`analyze`, a `backtest` clarity refactor, and a test commit for broker fee and
slippage calculations. Phase 9 records that by its start the tree held 15
source modules, 11 test files and both data files.

Methodological significance: this is where the single-signal, single-position
engine and the fee/slippage accounting originated. The one-position-at-a-time
design that later constrains all statistical work was fixed here.

### Phase 5 — research gates, exit rules and entry filters

Established the baseline reproduction that every later phase re-verified:
**344 trades, net −157.14, win rate 31.686%, profit factor 0.6920, max drawdown
1.74%, ending balance 9,842.86**. Added the optional research gates
(`min_breakout_distance`, `trend_strength_min`, `retest_use_close`,
`breakout_confirm_bars`) with defaults that reproduce the original signal logic
exactly, so the baseline is unchanged by their presence.

### Phase 6 — exit-rule experiments

Tested `max_holding_bars`, `stop_loss_pct` and `take_profit_pct` as optional
exit rules. None improved on opposite-signal exit; `maxhold=12` produced 662
trades and net −235.65 against the baseline's 344 trades and −157.14. All three
default to `None`.

### Phase 7 — entry-signal research and the A2 selection

Searched twelve configurations across `min_breakout_distance`,
`breakout_confirm_bars` and `allowed_sides`. **A2 (`min_breakout_distance=0.002`)
was selected in this phase**, giving 284 trades, net −87.16, profit factor
0.7957. A1 was identical to baseline. `C1` (long only) gave net −34.19 on 172
trades. No configuration was profitable.

This phase created the project's most consequential contamination, recorded in
§8.

### Phase 8 — what can and cannot be concluded; validation harness

Concluded that out-of-sample validation **could not** be performed: no unseen
data existed. The validation harness was built, tested and deliberately *not*
run against in-sample data, because reporting such a result as out-of-sample
would be false. Refusing to run it was the substantive finding.

### Phase 9 — data-source review

Reviewed Binance Vision, Coinbase Exchange and Kraken. Recommended Binance
Vision for bulk monthly archives with published SHA-256 checksums and
non-commercial research permission. **Downloaded nothing.**

### Phase 10 — official historical OOS acquisition and validation

Acquired 8 monthly Binance Vision archives for 2026-01…2026-08, 5,832 rows,
**8 of 8 checksums verified before parsing**. Availability was probed with HTTP
HEAD: 2026-01…08 returned 200, 2026-09…12 returned **404**, so four months were
never obtained and no partial month was substituted. Four independent validation
stages passed.

Out-of-sample validation then ran on the unmodified Phase 8 harness for the
validation window 2026-01-03 → 2026-08-31 (5,784 bars, 48 warm-up excluded),
fee 0.001, slippage 0.0005, `risk_fraction` 0.01, next-candle-open execution.

| Measure | baseline | A2 |
| --- | --- | --- |
| Trades | 105 | 90 |
| Net P&L | **+$5.05** | **+$14.07** |
| Profit factor | 1.0424 | 1.1330 |
| Win rate | 34.29% | 36.67% |
| mean / SE | **0.13** | **0.37** |
| 95% CI | [−0.6688, +0.7649] | [−0.6632, +0.9758] |

Every interval spans zero. Costs consumed **86.2%** of baseline gross and
**65.8%** of A2 gross. Months split four positive, four negative. Phase 10's own
verdict: *"inconclusive, not a demonstrated improvement."*

### Phase 11 — robustness, bootstrap and dependence

Asked how much of Phase 10 could be trusted. Four measured findings:

1. **Every confidence interval contains zero** — at all five block lengths
   (1, 5, 10, 20, 30) and under both resampling methods, for both
   configurations. The total-P&L interval for baseline's +$5.05 is
   **[−$64.32, +$69.76]**.
2. **Extreme concentration.** Baseline's largest single win is **+378.8%** of
   its entire net P&L; the top three are **+972.2%**. Removing the single
   largest losing trade turns net to **−$1.14**.
3. **The median trade loses money** — −$0.89 baseline, −$0.96 A2. The positive
   mean exists only through a thin tail of large winners.
4. **Monthly results split evenly**, 4 positive / 4 negative.

Mark-to-market drawdown is 1.12–1.16× the closed-trade measure, so the legacy
metric was not materially understating risk. Serial dependence was **measured,
not assumed**, and found negligible — so the block bootstrap neither rescues
nor undermines the conclusion.

### Phase 12 — execution realism

Audited the execution model. **Verified already correct:** slippage on both
legs, directional symmetry, a single execution path shared by backtest and
simulator, and no future-data leakage.

**Five confirmed problems:** recorded prices were not fills; stop-loss and
take-profit levels were anchored to a price the trader would never receive;
position size ignored the fill; fees were charged on raw rather than filled
notional; and spread was not representable at all.

Added `fill_price`, which applies spread and slippage to the fill price,
derives size from the real entry fill and charges fees on filled notional. It is
**opt-in**, so every previously recorded result still reproduces exactly. Phase
12.1 remediated stop-anchoring, cost reporting integration, a docstring
correction and a raw-reference invariant.

Documented limits that remain: proportional constant spread and slippage; no
partial fills, market impact, order-book depth, funding or borrow cost; a short
is a symmetric position with no borrow fee, which understates short cost;
intrabar fills are never assumed.

### Phase 13 — rolling walk-forward diagnostic

Pre-registered before execution. Six windows; training rolls forward three
calendar months; evaluation windows are consecutive non-overlapping quarters
covering **2024-07-01 → 2025-12-31 (13,176 evaluation candles)**.

| Pass | Trades | Windows positive | Window net range | Longest same-sign run |
| --- | --- | --- | --- | --- |
| baseline | 267 | **0 of 6** | −49.73 … −4.67 | 6 |
| A2 | 217 | 2 of 6 | −23.65 … +12.16 | 2 |

Baseline profit factor was below 1.0 in **every** window. Total net −133.86
(baseline) and −72.68 (A2). One `end_of_data` force-close retained per window.

**Leakage controls**, all of which raise rather than warn: evaluation before
training ends; overlapping windows; out-of-bounds windows; duplicate timestamps;
non-1h steps; dataset hash mismatch; configuration changed mid-run; costs
changed mid-run; entries before `evaluation_start`; dirty working tree;
strategy defaults changed. Plus a fresh `PaperBroker` per window, no state
carry, and a prohibition on using `yearly.py`.

Two recorded deviations, both left in place deliberately:

- The run executed with a **dirty working tree** under an explicit
  `--allow-dirty-tree` override. The guard itself was not weakened; the dirty
  state is recorded verbatim in `SUMMARY.md`.
- `dataset_sha256` is **absent from the per-window records**. Found during
  post-run verification and **deliberately not corrected**, because regenerating
  results after observing them is what the no-post-hoc rule forbids.

### Phase 14A — design audit (read-only)

No experiment, no code, no outcome inspected. Established that the binding
constraint is **sample size, not data availability**: trend state, volatility,
breakout distance and retest quality were computable from existing candles with
no hindsight but were not recorded. Confirmed MAE/MFE are hindsight. Concluded
that **Phase 14C cannot be validated on unused data**, because 2026 was already
consumed by Phase 10.

### Phase 14B — causal instrumentation

Added six `Signal` fields and eight `PaperTrade` fields
(`signal_close`, `trend_state`, `breakout_distance`, `retest_distance`,
`realised_volatility`, `mean_range`, `support_at_entry`,
`resistance_at_entry`) plus two causal indicators. Explicitly **not** added:
MAE/MFE, any outcome field, any threshold, any ATR or annualisation.

Proof of non-interference: all six frozen Phase 13 baseline windows reproduce
the committed trade counts and ending balances **to within 1e-9**. Test
sufficiency: **31 of 31** injected defects caught, covering lookahead,
propagation, missing-value handling, distance semantics, gate changes and
execution.

### Phase 14C — descriptive entry-context analysis

D1 feature distributions, D2 conditional outcomes over seven pre-declared
dimensions, D3 robustness accounting. Baseline and A2 reported separately,
never pooled, never ranked. Bins are pre-declared quartiles derived from feature
values only, with an explicit test that corrupting every outcome leaves the bin
edges bit-identical.

Findings are in §6. Test sufficiency: **30 of 30** injected defects caught.
Artifacts are byte-identical across repeated runs.

**Phase 14D was not justified, and the reason is structural rather than a
matter of judgment:** Phase 14C has now consumed the only remaining clean data.
A 14D would either re-use data 14C has seen — which is not validation — or
require data not yet acquired.

---

## 4. Current strategy state

Nothing in this section was changed by Phase 15.

### A. What exists in the implementation

| Property | Value as implemented |
| --- | --- |
| Strategy type | Single-asset, single-timeframe long/short breakout-and-retest rule |
| Config class | `crypto_paper_lab.strategy.StrategyConfig` (frozen dataclass) |
| `asset` / `timeframe` | `BTC/USDT` / `1h` |
| `lookback` | 20 |
| `fast_period` / `slow_period` | 5 / 12 |
| `breakout_buffer` | 0.001 |
| `retest_tolerance` | 0.002 |
| `min_breakout_distance` | 0.0 |
| `trend_strength_min` | 0.001 |
| `retest_use_close` | `False` |
| `breakout_confirm_bars` | 1 |
| `max_holding_bars` | `None` |
| `stop_loss_pct` | `None` |
| `take_profit_pct` | `None` |
| `allowed_sides` | `None` |
| Execution model (default) | `cost_deduction` |
| Execution model (available) | `fill_price`, opt-in, unused by any frozen result |
| `fee_rate` / `slippage_rate` / `spread_rate` | 0.001 / 0.0005 / 0.0 |
| Quantity rule | `cash * risk_fraction / entry_reference_price` |
| `risk_fraction` / starting balance | 0.01 / 10,000.0 |
| Max concurrent positions | 1 |

**Entry logic.** `analyze` receives `candles[:index]`; the fill occurs at
`candles[index].open`. `current` is `candles[index-1]`, `previous` is
`candles[index-2]`, and levels come from `candles[:index-2]`. A mandatory
one-candle gap separates the last closed candle from the fill. Entry fires on
`bullish retest`, `bearish retest`, `uptrend breakout` or `downtrend breakdown`;
otherwise `flat`.

**Trend logic.** Categorical `up` / `down` / `sideways` from a fast/slow simple
moving-average pair, requiring a minimum normalised separation of 0.001.

**Level logic.** `support = min(low)`, `resistance = max(high)` over the
trailing 20 candles, excluding the previous and current signal candles.

**Breakout / retest logic.** A level break requires a close beyond the level by
more than `breakout_buffer` **and** a distance of at least
`min_breakout_distance`. A retest requires the previous candle to have broken
the level, the current candle to come back within `retest_tolerance` of it
(wick by default, close when `retest_use_close`), and the close to hold the
level. `breakout_confirm_bars` optionally requires the last *n* closes to hold
the break.

**Exit behaviour.** Opposite-signal exit only, by default. `stop_loss_pct`,
`take_profit_pct` and `max_holding_bars` are fully implemented but all default
to `None`. Detection is on a closed bar and filling at the next open, so no
intrabar fill is assumed; when one bar breaches both levels the stop is assumed
first, which changes only the recorded label.

### B. What does not exist

Verified absent from the source tree by inspection, not assumed:

**leverage · margin · pyramiding or scale-in · partial take-profit · trailing
stop · profit callback or partial-profit lock · break-even move · funding cost ·
borrow cost on shorts · order-book depth · market impact · partial fills ·
multi-asset support · multi-timeframe support · live or paper broker
connectivity.**

Two clarifications on false positives found during inspection: the string
`margin` occurs in `costs.py` only as the English word "marginally" in
docstrings, and `trailing` occurs only as "trailing window" in `indicators.py`
and `entrycontext.py`. Neither is a trading feature.

The stop-loss, take-profit and max-holding **mechanisms exist in code** but are
disabled by default. Their presence is not a claim that they were tested
profitably — Phase 6 tested variants of them on in-sample data and none
improved on the baseline.

---

## 5. Evidence table

`kind` is either `negative_conclusion` (the stage supports a stated negative
finding) or `diagnostic_only` (the stage produced a measurement or a method
result, not a finding about performance). No stage supports a positive
conclusion.

| Phase | Question tested | Data used | Experiment | Major observed result | Limitation | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | Does the default configuration behave as recorded? | 2024–25 in-sample | Baseline reproduction; research gates | 344 trades, net −157.14, PF 0.6920, MDD 1.74% | In-sample; gates selected on this data | negative_conclusion |
| 6 | Do alternative exit rules improve on opposite-signal exit? | 2024–25 in-sample | Exit-rule grid | None improved; `maxhold=12` → 662 trades, net −235.65 | In-sample grid; weak evidence of general absence | diagnostic_only |
| 7 | Which entry variant behaves least badly? | 2024–25 in-sample | 12-configuration entry grid | A2: 284 trades, net −87.16, PF 0.7957; none profitable | **A2 selected here**, contaminating later windows | negative_conclusion |
| 8 | Can a valid OOS test be run with available data? | 2024–25 only | Unseen-data search; harness build | No unseen data existed; harness deliberately not run | Availability finding, not a performance measurement | diagnostic_only |
| 9 | Which source could supply genuine OOS history? | none | Vendor documentation review | Binance Vision recommended; nothing downloaded | Documentation claims unverified until Phase 10 | diagnostic_only |
| 10 | How do frozen configs behave on unseen 2026 data? | 2026 OOS, 5,832 candles | Checksum-verified acquisition + 4-stage validation + OOS run | baseline +$5.05 (105 trades), A2 +$14.07 (90 trades); **all CIs span zero** | 90–105 trades cannot resolve this effect; single window; 4 months missing | negative_conclusion |
| 11 | How much of Phase 10 can be trusted? | 2026 OOS | MTM drawdown; block bootstrap, 5 block lengths, 2 methods, 10k resamples | All CIs contain zero; largest win = 378.8% of net; median trade −$0.89 / −$0.96 | Describes the historical sample only; exchangeable-block assumption | negative_conclusion |
| 12 | Is the execution model realistic enough to matter? | none | Execution audit + `fill_price` model | 5 confirmed problems, all corrected; opt-in so prior results reproduce | Proportional constant costs; no impact, borrow or funding | diagnostic_only |
| 13 | How does behaviour vary across fixed historical sub-periods? | 2024–25, 6 windows, 13,176 eval candles | Pre-registered walk-forward, 11 leakage controls | baseline 267 trades, **0 of 6 windows positive**, PF < 1.0 in every window; A2 217 trades, 2 of 6 positive | Diagnostic not validation; 6 sequential windows; A2 windows 2–6 inside its selection period | negative_conclusion |
| 14A | What entry features are computable without look-ahead? | Phase 13 artifacts; source | Read-only design audit, designs D1–D5 | Sample size is the binding constraint; 14C cannot be validated on unused data | No experiment run; no outcome inspected | diagnostic_only |
| 14B | Can missing features be recorded without changing decisions? | 2024–25 | Instrumentation + 2 causal indicators + tests | Phase 13 reproduces to 1e-9; **31/31** defects caught | Instrumentation only; no outcome examined | diagnostic_only |
| 14C | Do entry conditions differ descriptively across outcomes? | 2024–25, same 6 windows | D1/D2/D3 over 7 pre-declared dimensions | baseline net −133.86, negative in all 6 windows; all \|ρ\| ≤ 0.21; only 4 of 24 cells per pass met the naming bar | Whole-sample quartile edges; 48 cells examined; mechanical trade dependence | diagnostic_only |

Phases 1–4 are omitted from the table because no report artifact exists for
them; see §14.

---

## 6. What the research currently shows

### OBSERVED — what happened in the tested historical sample

- On 2024–2025 in-sample, baseline produced 344 trades, net −157.14, profit
  factor 0.6920.
- On 2026 out-of-sample, baseline produced 105 trades, net **+$5.05**, profit
  factor 1.0424; A2 produced 90 trades, net **+$14.07**, profit factor 1.1330.
- Every 95% interval computed in Phase 10 and Phase 11 contains zero.
- Costs consumed 86.2% of baseline gross and 65.8% of A2 gross on 2026 data.
- The median trade was negative for both configurations on 2026: −$0.89
  baseline, −$0.96 A2.
- In Phase 13, baseline was net negative in **all six** evaluation windows;
  A2 was negative in four of six. Baseline profit factor was below 1.0 in every
  window.
- The sign of the result reversed between 2024–2025 and 2026 **with no change to
  the strategy**.
- In Phase 14C, no continuous entry-time feature showed more than weak rank
  association with net P&L; all |ρ| ≤ 0.21 across both passes. Only 4 of 24
  cells per pass met even the weak bar for being named a hypothesis candidate.

### NOT ESTABLISHED — what the evidence does not establish

- That any configuration is profitable.
- That baseline is better or worse than A2. The two were never ranked in this
  project and are **not ranked here**.
- That any entry-time feature is predictive of future outcomes.
- That any Phase 14C conditional difference is anything other than sampling
  variation.
- Why the 2024–2025 and 2026 signs differ.
- How the strategy behaves on any other asset or timeframe; neither was tested.
- How the strategy behaves after 2026-08; no data exists.
- Whether the 2024–2025 dataset is construction-continuous with 2026.

Historical observations above are **not** converted into predictions. A
negative result on consumed data is not evidence that a strategy cannot work,
and a marginally positive one is not evidence that it can.

---

## 7. Data inventory

| Property | Research dataset | Out-of-sample dataset |
| --- | --- | --- |
| Path | `data/BTCUSDT_1h_Cleaned (1).csv` | `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` |
| SHA-256 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` | `918153FDE98E39C03EEF8A7B82A2861ADFDC98A080C8810E371869EB3EA22437` |
| Range | 2024-01-01 → 2025-12-31 | 2026-01-01 → 2026-08-31 |
| Candles | 17,544 | 5,832 |
| Timeframe | 1h, 0 duplicates | 1h, 0 gaps, 0 duplicates |
| Provenance | **undocumented** | Binance Vision, 8/8 checksums verified |
| Used for research | Phases 5, 6, 7, 8, 9, 13, 14C | — |
| Used as out-of-sample | no (explicitly in-sample) | Phase 10, Phase 11 |

### Does genuinely unused validation data remain?

**No.**

- 2026-01-01 → 2026-08-31 was genuinely unseen when acquired, and was consumed
  by Phase 10 and Phase 11. It is now documented project history and was
  excluded from Phase 13 and Phase 14 primary analysis for exactly that reason.
- 2026-09 → 2026-12 returned **HTTP 404** at acquisition time and was never
  obtained. Those months may exist now; obtaining them is a Phase 15
  *recommendation of availability*, not an action taken.
- 2024–2025 has been used for research in every phase from 5 onward.
- No other asset, timeframe or period has ever been acquired.

This is the single most consequential fact in the checkpoint. It is the reason
Phase 14D was not justified, and it constrains every path in §10.

---

## 8. Research degrees of freedom

These are **methodological constraints on inference**. They are not claims that
the strategy is invalid, and they do not become invalidity claims by being
listed.

| Source of risk | Detail | Nature |
| --- | --- | --- |
| Parameter selection | Phases 5–7 searched 12+ entry and exit variants on 2024–2025 and selected A2 from that search | Methodological constraint |
| Repeated inspection | 2024–2025 was examined in Phases 2–9, again in Phase 13, again in Phase 14C. Repeated inspection of one period can converge on a pattern by search alone | Methodological constraint |
| A2 contamination | A2's `min_breakout_distance=0.002` was chosen in Phase 7 on 2024–2025, which contains five of six Phase 13 evaluation windows | Methodological constraint |
| Conditional subgroup analysis | Phase 14C examined 48 cells over 7 pre-declared dimensions; 4 met the naming bar, all hypothesis candidates only | Methodological constraint |
| Whole-sample descriptive quartiles | Bin edges came from the whole sample, so a window 1 trade was binned partly using window 6 information. A descriptive grouping, never a live-applicable rule | Methodological constraint |
| Sample size | 267 baseline / 217 A2 trades; per-trade σ ≈ 3.75–3.97 against OOS means of 0.05–0.16 | Methodological constraint |
| Multiple comparisons | Phase 14A recorded that a dozen-feature scan at this sample will surface an apparently interesting pattern by chance. All cells were reported including null ones so the count stays visible | Methodological constraint |
| Sequential dependence | Six windows are consecutive periods of one series, not independent samples. One position at a time means trades are separated by a full holding period (mean 49–60 bars) | Methodological constraint |
| No unused holdout | 2026 consumed by Phases 10–11; 2026-09…12 unavailable at 404 | Methodological constraint |

The Phase 11 finding that serial dependence in trade *returns* was negligible
does **not** license treating trades as independent draws for
characteristic-association questions, where the clustering is mechanical.

---

## 9. Current research status

### Established

- The data pipeline works as designed: verify checksums, preserve raw, validate
  in four independent stages, and refuse to proceed otherwise.
- Baseline reproduces exactly across every phase that re-checked it.
- Execution modelling was audited and five real defects were corrected.
- A causal, leakage-controlled walk-forward harness exists with 11 raising
  controls, verified by 92 targeted tests at Phase 13 and by mutation testing in
  Phases 14B and 14C.
- On the tested historical samples, the strategy did not demonstrate
  profitability: negative in-sample, marginally positive out-of-sample with
  every interval spanning zero, negative in all six walk-forward windows.
- Cost burden is material: 86.2% and 65.8% of gross on 2026 data.
- No entry-time feature instrumented in Phase 14B shows a strong association
  with net P&L.

### Not Established

- Whether the strategy is profitable, in any period, on any asset.
- Whether baseline and A2 differ in any meaningful way.
- Whether any entry-time condition is exploitable.
- Whether the observed regime sensitivity has a single cause.
- Behaviour after 2026-08, on other assets, or on other timeframes.
- The provenance of the 2024–2025 dataset.

### Constraints

- **No unused validation data exists.** This blocks every validation-shaped
  question.
- The primary sample is 267 / 217 trades across six sequential windows.
- Trades are mechanically clustered, so the trade count is not an independent
  sample size and no p-value on trades is defensible.
- A2 is contaminated for five of six Phase 13 windows.
- Execution realism remains approximate: proportional constant costs, no market
  impact, no borrow or funding cost.
- The decision to analyse this strategy at all, and the choice of these six
  windows, are themselves selections.

### Available Research Paths

Legitimate without pretending reused data is fresh validation:

1. **Acquire genuinely fresh holdout data** (2026-09 onward, or another period).
   The checksum-verified acquisition pipeline already exists. This is the only
   path that can convert an association into a validated claim.
2. **Extend the execution model.** Measurement improvement on consumed data;
   cannot itself produce a profitability claim. Hourly OHLC cannot support a
   size- or volatility-dependent spread.
3. **Additional statistical methodology** on already-recorded results, provided
   the method is fixed and reported before the result is seen. Current data is
   sufficient; no new holdout needed.
4. **Resolve the 2024–2025 data provenance question.** A records question, no
   contamination risk.
5. **Test a separately pre-registered hypothesis or a redesigned strategy on a
   new holdout.** Legitimate only with data not used to derive the hypothesis.

### Paths That Should Not Be Treated as Validation

Each of these would be **exploratory data mining** if performed on data that
has already been consumed:

- Selecting a Phase 14C condition as an entry filter and reporting the result on
  2024–2025. Search and evaluation would use the same data.
- Re-running the Phase 13 walk-forward after adding a filter derived from
  Phase 14C observations.
- Comparing baseline and A2 on 2026 again and calling the larger figure a
  winner. A2 was selected on 2024–2025 and the 2026 result is one window.
- Any further parameter sweep on 2024–2025 or 2026. Both are fully consumed.
- Re-deriving bin edges or thresholds from outcomes and reporting the improved
  fit.
- Pooling 2024–2025 with 2026 to enlarge the sample. Phase 14A classified this
  as manufacturing validation.
- Treating 2026 as still unseen.
- Reporting a p-value on Phase 14C trades, which assumes an independence the
  one-position-at-a-time design does not provide.

---

## 10. Possible next research directions

**No direction is recommended over another.** These are categories, listed
with what each would require.

### 10.1 Acquisition of genuinely fresh validation data

- **Question:** does anything established here hold on data never before
  examined?
- **Data required:** 2026-09 onward Binance Vision archives once published, or
  another never-acquired period.
- **Current data sufficient:** **no.**
- **Requires a new holdout:** **yes.**
- **Contamination risk:** none for genuinely new data. The pipeline that proved
  acquisition reliable in Phase 10 already exists and is checksum-verified.
- **Note:** a data task, not a strategy task. It would not by itself make any
  strategy profitable; it would only make the question answerable.

### 10.2 Testing a separately specified strategy hypothesis

- **Question:** does a differently specified rule behave differently?
- **Data required:** a holdout not used to derive the hypothesis.
- **Current data sufficient:** **no.**
- **Requires a new holdout:** **yes.**
- **Contamination risk:** high if specified after inspecting existing results.
  Must be pre-registered before any evaluation, and must not be run
  head-to-head with baseline on consumed data and called a winner.

### 10.3 Independent strategy redesign

- **Question:** does a structurally different design behave better?
- **Data required:** a holdout not used during development.
- **Current data sufficient:** **no.**
- **Requires a new holdout:** **yes.**
- **Contamination risk:** high. A redesign informed by Phase 14C observations
  would import that inspection into the design and could not afterwards be
  treated as independent.

### 10.4 Execution-model extensions

- **Question:** how much gross movement does realistic execution consume?
- **Data required:** existing candles plus external venue knowledge for spread;
  order-book data for size or volatility dependence.
- **Current data sufficient:** **no** for a realistic spread, **yes** for
  applying the existing `fill_price` model.
- **Requires a new holdout:** no.
- **Contamination risk:** low. This improves measurement on consumed data and
  cannot itself yield a profitability claim.

### 10.5 Alternative assets and timeframes

- **Question:** is the observed behaviour specific to BTC/USDT 1h?
- **Data required:** never-acquired assets or timeframes.
- **Current data sufficient:** **no.**
- **Requires a new holdout:** **yes.**
- **Contamination risk:** none for new assets, provided no variant is tuned on
  the new data before evaluation. This tests generalisation, not optimisation.

### 10.6 Additional statistical methodology

- **Question:** how sensitive are the recorded conclusions to the dependence and
  resampling assumptions?
- **Data required:** none beyond what is already recorded.
- **Current data sufficient:** **yes.**
- **Requires a new holdout:** no.
- **Contamination risk:** low, provided the method is fixed before the result
  is seen. Phase 11 already reports block-length sensitivity; Phase 14C
  deliberately reports no p-value because the independence assumption is
  unsupported.

### 10.7 Data provenance resolution

- **Question:** how was the 2024–2025 dataset constructed, and is it continuous
  with 2026?
- **Data required:** vendor documentation or re-acquisition.
- **Current data sufficient:** **no.**
- **Requires a new holdout:** no.
- **Contamination risk:** none. Open since Phase 9.

---

## 11. Phase 15 did not optimise

Explicitly confirmations of what was **not** done:

- No Phase 14C condition was selected as a filter.
- No threshold was invented, moved or tuned.
- No new filter, gate or rule was created.
- Risk, exits, leverage, position sizing and costs were not touched.
- No parameter sweep or grid search was run.
- No configuration was ranked, scored or recommended.
- No profitability claim, predictive claim or forecast appears anywhere in
  this checkpoint.
- No experiment was run; no outcome was inspected for the purpose of producing
  a new idea.
- The strategy was not modified because of any Phase 14C observation.

The four Phase 14C cells that met the weak naming bar remain labelled
hypothesis candidates. They are recorded as reasons to obtain fresh data, not
as candidates for implementation.

---

## 12. Reproducibility

| Item | Value |
| --- | --- |
| Git HEAD | `25bd7d0ab651e356240d8148525fb664938562b0` |
| Branch | `main` |
| `origin/main` | `f5293c91da33e929a230ff385ab4458cfa232fee` (local is 1 commit ahead) |
| Working tree | **dirty** — Phase 14B/14C source, tests and results are uncommitted |
| Committed by Phase 15 | no |
| Pushed by Phase 15 | no |
| Test count before this phase's tests | 497 |
| Research dataset SHA-256 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
| OOS dataset SHA-256 | `918153FDE98E39C03EEF8A7B82A2861ADFDC98A080C8810E371869EB3EA22437` |

### Frozen artifact status

All Phase 10–14 artifacts verified **unchanged** at Phase 15. Full SHA-256
digests are recorded in `RESEARCH_STATE.json` and re-verified by
`tests/test_phase15_checkpoint.py`.

| Artifact | Status |
| --- | --- |
| Phase 10 (8 files) | unchanged |
| Phase 11 (3 files) | unchanged |
| Phase 12 (1 file) | unchanged |
| Phase 13 `PLAN.md` | unchanged — `8D9F9021…7D7800` |
| Phase 13 `EXPERIMENT_LOG.md` | unchanged — `2E59ABDB…45F435` |
| Phase 13 `SUMMARY.md` | unchanged — `188D3A1B…4138D` |
| Phase 13 `RESULTS_windows.csv` | unchanged — `1A2D37A4…953E7D` |
| Phase 13 `RESULTS_windows.json` | unchanged — `67092DEC…94224` |
| Phase 14 (6 files) | unchanged |
| Both datasets | unchanged |

The Phase 13 digests recorded here match those independently established
during Phases 13 and 14, which is a cross-check rather than a restatement.

### Strategy source status

`strategy.py`, `models.py`, `simulator.py`, `backtest.py`, `costs.py`,
`indicators.py`, `walkforward.py` and `windowstats.py` were **not modified by
Phase 15**. The Phase 14B changes to the first four remain in the working tree
exactly as Phase 14B left them.

### Reproducing this checkpoint

```bash
cd research_engine
python -m pytest tests/test_phase15_checkpoint.py -q
python -m pytest tests/ -q
```

`tests/test_phase15_checkpoint.py` recomputes every digest in
`RESEARCH_STATE.json`, compares the recorded strategy defaults against the live
`StrategyConfig`, and verifies that each declared capability absence is actually
absent from the source tree.

---

## 13. Verification performed by Phase 15

- Full test suite run; result recorded in §14.
- `git diff --check` clean.
- Phase 10–14 artifact digests recomputed and compared.
- Both dataset digests recomputed and compared.
- Capability absences verified by source inspection, including two false
  positives (`margin` as "marginally" in docstrings; `trailing` as "trailing
  window") that were checked and excluded.
- Phase 13 frozen results re-reproduced for all twelve windows (6 baseline,
  6 A2) to confirm strategy behaviour is unchanged.

---

## 14. Where the record is incomplete

Stated rather than filled in:

1. **Phases 1–4 have no report artifact.** They predate the experiment-record
   convention. What is established about them comes from the git log and from
   cross-references in the Phase 5 and Phase 9 summaries.
2. **The Phase 13 per-window records omit `dataset_sha256`.** Found during
   post-run verification and deliberately uncorrected, per
   `EXPERIMENT_LOG.md` entry 3.
3. **The Phase 14C `RESULTS_analysis.json` `trade_population` entries carry no
   `config_name` key.** Left uncorrected because the artifact is frozen. It is a
   schema inconsistency, not a data error; the two entries are positionally
   baseline then A2.

Two values in this checkpoint could not be established and are therefore
absent rather than estimated: the **provenance of the 2024–2025 dataset**, and
any **strategy behaviour after 2026-08-31**.

---

## 15. Statement on project changes

**No strategy parameter, threshold, default, entry rule, exit rule, position
model or cost assumption was changed.**

No dataset was modified. No Phase 10–14 artifact was modified. No experiment was
run. No configuration was selected or ranked. No Phase 16 work was started.

The sole outputs of Phase 15 are this document,
`research_engine/experiments/phase15/RESEARCH_STATE.json`, and
`research_engine/tests/test_phase15_checkpoint.py`.

---

*End of research checkpoint. Documentation and audit only. Nothing committed,
nothing pushed, no further phase started.*