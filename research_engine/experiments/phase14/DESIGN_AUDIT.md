# Phase 14A — Regime / Failure Analysis Design Audit

**Status: READ-ONLY DESIGN AUDIT.** No source code, dataset, configuration or
result was modified. No experiment was run. Nothing was staged, committed or
pushed.

Audit performed at commit `25bd7d0ab651e356240d8148525fb664938562b0`.

Phase 13 is treated as a frozen, read-only research artifact throughout.

---

## 1. Research question

**What observable market and trade characteristics are associated with the
existing breakout/retest paper-trading rule's winning and losing behaviour
across the existing historical research data?**

This is an **association** question, not an optimisation question. The audit is
explicitly structured to keep these two apart:

| Statement | Status in Phase 14 |
|---|---|
| "This feature is **associated with** historical outcomes" | May be investigated descriptively |
| "This feature **can improve** future trading performance" | **Requires separate pre-registered validation. Must not be inferred from exploratory analysis.** |

Phase 14A–C are descriptive. Any claim of the second kind requires a Phase 14D
with its own pre-registration, and is **not** assumed to be warranted.

### Explicitly out of scope

Searching for a profitable parameter, selecting a better configuration, tuning
`StrategyConfig`, ranking variants, or using 2026 to enlarge the validation
sample.

---

## 2. Phase 13 context

Phase 13 is a **historical walk-forward diagnostic**, not fresh independent
out-of-sample validation. Its conclusions are frozen and are inputs to this
audit, not objects of change.

| Fact | Value | Source |
|---|---|---|
Dataset | `data/BTCUSDT_1h_Cleaned (1).csv` | frozen `PLAN.md` §2 |
Dataset SHA-256 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` | frozen |
Range | `2024-01-01 00:00:00` → `2025-12-31 23:00:00` | frozen |
Candles | 17,544, 1h, 0 duplicates | verified |
Windows | 6, eval covering `2024-07-01` → `2025-12-31` (13,176 candles) | frozen `PLAN.md` §3 |
Passes | `baseline` and `A2`, reported separately, never ranked | frozen §6 |
Execution | `cost_deduction`, fee 0.001, slippage 0.0005, spread 0.0 | frozen §7 |
Account | 10,000.0 start, 0.01 risk, one position, no leverage/margin/pyramiding | frozen §8 |
2026 data | **Excluded** — already used in Phase 10 | frozen §2 |

**Sample actually available for Phase 14 (from the frozen artifacts):**

| Pass | Trades | Windows | Mean trades/window |
|---|---|---|---|
`baseline` | **267** | 6 | 44.5 |
`A2` | **217** | 6 | 36.2 |

Baseline per-window trade counts: 50, 42, 43, 52, 38, 42. Mean bars held per
window: 44.1, 52.2, 49.7, 41.8, 57.8, 52.3.

**267 trades over ~18 months of evaluation is the entire primary sample.** This
number constrains every design below and is the single most important number in
this document.

---

## 3. Existing data available

### 3.1 Candle-level (the only raw market data)

`Candle` (`models.py`) carries exactly six fields, all per-hour:

```
timestamp, open, high, low, close, volume
```

There is **no** precomputed volatility, ATR, trend strength or volume profile
anywhere in the repository.

### 3.2 Indicator support (`indicators.py`)

Only three functions exist:

| Function | Purpose |
|---|---|
`simple_moving_average(values, period)` | trailing mean of last `period` values |
`trend(candles, fast, slow, strength)` | categorical `up`/`down`/`sideways` from an MA pair |
`support_resistance(candles, lookback)` | `min(low)`, `max(high)` over the trailing `lookback` |

**Confirmed absent:** ATR, true range, realised volatility, returns series,
volume statistics. Any volatility feature must be newly implemented.

### 3.3 Signal-level (`Signal`, produced by `analyze()`)

```
timestamp, side, reason, price, support, resistance, trend, breakout, retest
```

`reason` takes one of five fixed strings: `"bullish retest"`,
`"bearish retest"`, `"uptrend breakout"`, `"downtrend breakdown"`,
`"no confirmed breakout or retest"`. Signal type (retest vs breakout) is
therefore **recoverable from `reason` without new instrumentation**, which
`analysis.py` already exploits by substring matching.

### 3.4 Trade-level (`PaperTrade`)

All fifteen recorded fields, verified by introspection:

| Field | Type | Availability |
|---|---|---|
`side` | `long`/`short` | at entry |
`entry_time` | datetime | at entry |
`entry_price` | float | at entry (recorded fill) |
`quantity` | float | at entry |
`exit_time` | datetime \| None | at close |
`exit_price` | float \| None | at close (recorded fill) |
`reason` | str | at entry (signal type) |
`costs` | float | at close (deducted amount) |
`exit_reason` | str | at close |
`bars_held` | int | at close |
`raw_entry_price` | float \| None | at entry (reference price) |
`raw_exit_price` | float \| None | at close (reference price) |
`fee_total` | float | at close |
`slippage_total` | float | at close |
`spread_total` | float | at close |

### 3.5 Window-level (`WindowStats`, `windowstats.py`)

36 fields per window per pass, including the frozen metric set plus
`bars_held_mean`/`median`, `first_entry`, `last_exit`,
`boundary_affected_count`, `exit_counts`, `config_hash`, `costs_hash`,
`warmup_rule`, `boundary_policy`.

Note: `dataset_sha256` is **absent** from the frozen Phase 13C records. It was
remediated for future runs in Phase 13D. This audit reads the frozen JSON as-is.

### 3.6 Data scope ruling

| Dataset | Permitted use in Phase 14 |
|---|---|
2024–2025 research dataset | **Primary.** Descriptive association analysis. |
Phase 13 six evaluation windows | **Primary.** Defines the evaluation frame. |
2026 OOS dataset | **Documented historical context only.** No new OOS claim; must **not** be pooled with Phase 13 to manufacture a larger validation sample. |

---

## 4. Existing trade fields vs the required win/loss analysis

Every item on the Phase 14 question list resolves against the fifteen recorded
fields:

| Requirement | Available? | Field |
|---|---|---|
Winning vs losing | ✅ | derived: `net_pnl > 0` |
Long vs short | ✅ | `side` |
Net P&L | ✅ | `net_pnl` (derived) |
Gross P&L | ✅ | `pnl` (derived) |
Fees | ✅ | `fee_total` |
Slippage | ✅ | `slippage_total` |
Total friction | ✅ | `fee+spread+slippage` (derived) |
Bars held | ✅ | `bars_held` |
Entry timestamp | ✅ | `entry_time` |
Exit timestamp | ✅ | `exit_time` |
Entry price | ✅ | `entry_price` |
Exit price | ✅ | `exit_price` |
Raw prices | ✅ | `raw_entry_price`, `raw_exit_price` |
Fill prices | ✅ | `entry_price`, `exit_price` |
Signal type (retest/breakout) | ✅ | `reason` substring |
Exit reason | ✅ | `exit_reason` |
Holding period in time | ✅ | `exit_time - entry_time` |
Entry hour / weekday / month | ✅ | `entry_time` |
Directional return | ✅ | derived from raw prices |

**Explicitly missing and requiring new instrumentation:**

| Missing | Consequence |
|---|---|
`trend` at entry (categorical) | not on `PaperTrade`; available only if re-derived |
`support` / `resistance` at entry | not on `PaperTrade` |
`breakout_distance` (numeric) | **discarded by `analyze()`** — computed, then thrown away |
`retest_distance` (numeric) | **discarded by `analyze()`** |
`breakout_confirm_count` | not recorded |
ATR / realised volatility | no indicator exists |
Range, body size, volume at entry | derivable from `Candle`, not recorded |
MAE / MFE | **hindsight** — see §7 |
`min_breakout_distance` effective value | not on the trade |

### 4.1 The central instrumentation gap

`strategy.analyze()` contains:

```python
def broke_level_up(close, level):
    return (
        close > level * (1 + config.breakout_buffer)
        and (close - level) / level >= config.min_breakout_distance
    )
```

The term `(close - level) / level` **is** the breakout distance. It is evaluated
only as a boolean gate and then discarded. `Signal` retains `support`,
`resistance` and the categorical `trend`, but no distance. The same is true of
the retest tolerance term `abs(current.low - resistance) / resistance`.

**Consequence:** three of the ten candidate feature families — breakout
distance, retest quality, and trend strength at entry — are *computable today
from `Candle` plus `StrategyConfig`, without any hindsight*, but are **not
recorded**. They need instrumentation, not new data.

---

## 5. Missing instrumentation summary

Minimum set required for the association questions, all entry-time safe:

1. `trend_at_entry` — categorical, from `analyze()`
2. `support_at_entry`, `resistance_at_entry` — from `analyze()`
3. `breakout_distance` — numeric `(close - level)/level` at the signal bar
4. `retest_distance` — numeric deviation at the retest bar
5. `realised_volatility` — trailing stdev of 1h returns, window stated
6. `atr` or trailing high-low range — needs a new indicator
7. `body_ratio`, `range_pct`, `volume_at_entry` — derivable from `Candle`

Items 1–4 are **recoverable without touching market data**. Items 5–7 require
new indicator code over the existing candles.

---

## 6. Candidate features

Grouped by availability class, not by promise. **None is assumed to explain
performance.**

### Class A — available today, zero instrumentation

| Feature | Source | Entry-time safe? |
|---|---|---|
Trade direction | `side` | ✅ |
Signal type (retest / breakout / breakdown) | `reason` substring | ✅ |
Bars held | `bars_held` | ✅ outcome-side |
Calendar hour, weekday, month | `entry_time` | ✅ |
Entry-to-exit duration | timestamps | ✅ outcome-side |
Raw price move | `raw_entry_price`, `raw_exit_price` | ✅ |
Friction, and friction as % of gross move | derived | ✅ |
Hold-window high/low excursion | `Candle` between entry and exit | ⚠️ **hindsight** |

### Class B — computable from existing candles, needs instrumentation only

| Feature | Derivation |
|---|---|
Trend state at entry | `analyze()` categorical `trend` |
MA fast/slow spread | `(fast_ma - slow_ma)/slow_ma` from existing `trend()` internals |
Price distance from slow MA | `close/slow_ma - 1` |
Trend strength | `abs(fast_ma - slow_ma)/slow_ma`, already computed as `tolerance` input |
Breakout distance | `(signal_close - level)/level` |
Retest distance | `abs(close - level)/level` at retest |
Support/resistance at entry | from `analyze()` |
Trailing range width | `max(high)-min(low)` over lookback |
Distance to recent extreme | `close` vs trailing `max(high)`/`min(low)` |

### Class C — requires a new indicator over existing candles

| Feature | Note |
|---|---|
Realised volatility | trailing stdev of 1h log returns; window length must be pre-declared |
ATR | true range needs `prev_close`; not currently implemented |
Volatility percentile | **see §9.3 — percentile needs care** |
Body / range ratio | from OHLC |
Volume at entry | already in `Candle`, unused anywhere |

### Class D — explicitly rejected as entry-time predictors

| Feature | Reason |
|---|---|
MAE / MFE | use candles **after** entry |
Mark-to-market drawdown (`robustness.mark_to_market_drawdown`) | marks to exit across the holding window |
Realised P&L | outcome, by definition |
Any post-exit window statistic | future information |

---

## 7. Look-ahead assessment

### 7.1 The engine's leakage boundary (verified from code)

`run_backtest` computes:

```python
signal = analyze(candles[:index], config)
execution_signal = replace(signal, timestamp=current.timestamp, price=current.open)
```

Inside `analyze(candles[:index])`:

| Quantity | Candles used |
|---|---|
`current` | `index-1` |
`previous` | `index-2` |
`support`/`resistance` (trailing 20) | `0 … index-3` |
`trend` (last 12 closes) | `index-12 … index-1` |
Fill price | `index` (open) |

**Every signal input is derived from candles at or before `index-1`; the fill
occurs at `index`. There is a mandatory one-candle gap. No signal feature uses
the entry candle or any later candle.**

### 7.2 Per-feature verdict

| Feature | Last candle used | Pre-entry? | Verdict |
|---|---|---|---|
Trend state at entry | `index-1` | ✅ | **Admissible** |
MA spread / trend strength | `index-1` | ✅ | **Admissible** |
Support / resistance at entry | `index-3` | ✅ | **Admissible** |
Breakout distance | `index-1` | ✅ | **Admissible** |
Retest distance | `index-1` | ✅ | **Admissible** |
Trailing range width | `index-1` | ✅ | **Admissible** |
Realised volatility, ATR | `index-1` | ✅ | **Admissible** (new indicator) |
Volume at entry | `index-1` | ✅ | **Admissible** |
Calendar fields | `index-1` | ✅ | **Admissible** |
MAE / MFE | `exit` | ❌ | **Outcome descriptor only** |
Mark-to-market drawdown | `exit` | ❌ | **Outcome descriptor only** |
Trade outcome, bars held | `exit` | ❌ | **Outcome, not predictor** |

### 7.3 The hindsight-label trap

The single most important rule for Phase 14:

> A variable may be *described* using post-entry information, but it may
> **never** be presented as something known at entry time.

Phase 5's `diagnose_trades.py` already computes MAE, MFE and `dist`. `dist` is
entry-time safe (it uses signal-bar prices and levels). **MAE and MFE are not**
— they scan `candles[entry_i+1 : exit_i+1]`. Reusing that script for Phase 14
without an explicit entry-time/hindsight split would import hindsight labels
into an association study.

Any Phase 14 output must carry an explicit `availability` classification
(`ENTRY_TIME` / `OUTCOME_SIDE`) per feature.

### 7.4 Bounded-lookback consequence

`analyze()` reads only trailing windows (20 for levels, 12 for trend), so
signal state at any index does **not** depend on arbitrarily deep history. This
means "entry-time" features are genuinely reconstructible from a short prefix —
useful for Phase 14B, which can recompute them without re-running any backtest.

---

## 8. Selection and contamination risks

| # | Risk | Detail | Mitigation |
|---|---|---|---|
1 | **A2 Phase 7 contamination** | A2's `min_breakout_distance=0.002` was chosen on 2024–2025. Windows 2–6 lie inside that period. | Treat A2 as **descriptive only**. Primary analysis on `baseline`. Never rank the two. |
2 | **Phase 7 grid** | 12 configurations were examined on 2024–2025. | Any Phase 14 feature that happens to encode `min_breakout_distance` inherits that contamination. |
3 | **Phase 13 window construction** | 6 windows were fixed pre-registration, but the choice to analyse this data at all is a selection. | Windows stay frozen; report per-window, never pooled only. |
4 | **Exploratory-to-explanatory slippage** | Testing many features on 267 trades will find *some* apparently predictive feature by chance. | Pre-declare the feature list before analysis; report **all** tested features including null ones. |
5 | **Boundary artefacts** | 1 `end_of_data` force-close per window (6 of 267 baseline trades, 2.2%). | Report separately; never discard. |
6 | **2026 reuse** | 2026 informed Phase 10 and possibly Phase 12 spread choice. | Context only. No new OOS claim. No pooling. |
7 | **Phase 12 execution change** | The engine gained an optional model after Phase 10. | Analysis uses the frozen `cost_deduction` default, matching Phase 13. |

### 8.1 The governing risk

With **267 trades** across **6 sequential windows**, a naive scan of even a
dozen features will produce at least one feature that appears predictive at
conventional thresholds **purely by chance**.

Phase 14 must therefore be framed as **hypothesis generation**, and its outputs
must carry that label. The only defensible route from "associated" to "useful"
is a fresh, separately pre-registered Phase 14D on data not used in Phase 14C —
and no such data currently exists, because 2026 has already been used.

---

## 9. Regime bucketing

### 9.1 Fixed conventional thresholds — preferred where defensible

| Bucket | Candidate rule | Source of threshold |
|---|---|---|
Trend strength | terciles of `abs(fast_ma - slow_ma)/slow_ma` | **No conventional standard exists.** Must be justified or dropped. |
Volatility | annualised realised vol bands | Conventionally documented, but the exact cut-offs are arbitrary. |
Range width | ratio to trailing mean range | Relative measure; no absolute threshold needed. |
Breakout distance | signed, reported continuously | Avoids arbitrary bins. |
Friction burden | `total_friction / abs(gross_pnl)` | Ratio, no threshold. |

**Where a threshold has no external justification, it must not be invented.**

### 9.2 Quantile buckets — and the look-ahead they introduce

Quantiles are attractive but carry a specific defect:

> If quantile edges are computed over the **whole** 2024–2025 sample, then the
> bucket assigned to a trade in window 1 is defined partly by trades in window
> 6. That is look-ahead across windows.

Two acceptable variants:

| Variant | Definition | Status |
|---|---|---|
**Expanding** | Edges from data **strictly before** the window only | ✅ Leakage-free; edges vary per window, complicates comparison |
**Fixed external** | Edges from a published/prior source | ✅ Leakage-free; may not suit the data |
**Whole-sample quantiles** | Edges from all 267 trades | ❌ **Reject as entry-time descriptors.** Acceptable only if labelled explicitly as a *descriptive grouping of the sample*, not as a live-applicable rule. |

### 9.3 Volatility percentile — same defect

A "high volatility" label defined by the sample's own volatility distribution
is a hindsight label unless edges are expanding or externally fixed.

**Recommendation:** report volatility and trend strength **continuously**
(continuous values, scatter/summary statistics) rather than bucketed. Bucketing
adds a discretionary choice without adding information.

---

## 10. Trade-level vs window-level analysis

| Question | Unit | Why |
|---|---|---|
Which signal types lose more? (retest vs breakout) | **trade** | Direct characteristic contrast |
Long vs short outcome difference | **trade** | Direct |
Duration vs outcome | **trade** | `bars_held` is per-trade |
Friction burden vs outcome | **trade** | Per-trade ratio |
Do losses cluster by calendar period? | **month** | Aggregating trades to month reduces over-counting |
Does behaviour differ across windows? | **window** (n=6) | The walk-forward frame |
Is the pattern stable over time? | **window** (n=6) | Stability, not significance |

### 10.1 Dependence — must not be ignored

**Trades are not independent.** Evidence: mean bars held is **44–58 hours**
(~2 days) per window, and positions are strictly one-at-a-time, so consecutive
trades are mechanically separated by a full holding period. Overlapping
positions are impossible.

Phase 11 measured dependence in trade returns and found values inside the
white-noise band, reporting block bootstrap as a cross-check. That finding
concerns **return serial dependence**; it does **not** license treating trades
as independent draws for *characteristic-association* questions, where the
clustering is mechanical (one open position at a time).

**Windows are sequential, not independent**, by construction.

### 10.2 Consequences

* Report **counts and medians**, not only means; distributions are skewed.
* Any interval must use `robustness.block_bootstrap_ci` with a **pre-declared**
  `block_length`, labelled as within-sample uncertainty.
* **No window-level interval** — n=6.
* Never pool 267 trades into a single test as if they were 267 independent
  observations.

---

## 11. Candidate designs D1–D5

**These are not ranked.**

### D1 — Descriptive trade diagnostics

| Aspect | Detail |
|---|---|
Purpose | Characterise the existing trade population: duration, direction, signal type, friction burden, calendar distribution, exit reason |
Required data | Frozen Phase 13 JSON + `PaperTrade` fields — **no new instrumentation** |
Leakage risk | Low, provided MAE/MFE are excluded or explicitly labelled hindsight |
Selection risk | Low — no feature selection, only description |
Complexity | **Low** |
Answers | "What does the existing strategy's trade population look like?" |
Does **not** answer | Why outcomes differ |

### D2 — Regime-conditioned descriptive analysis

| Aspect | Detail |
|---|---|
Purpose | Compare outcome distributions across pre-declared market states (trend, volatility, breakout distance, retest quality) |
Required data | **New entry-time instrumentation** (§5 items 1–7) |
Leakage risk | **Manageable** — all features admissible per §7.2, provided buckets use expanding or fixed edges |
Selection risk | **Material** — feature × bucket scanning on 267 trades invites chance findings |
Complexity | **Medium** |
Answers | "Which market states coincide with which outcomes?" |
Does **not** answer | Whether any state is *causal* or *exploitable* |

### D3 — Failure-mode analysis

| Aspect | Detail |
|---|---|
Purpose | Characterise losses specifically: exit reason, duration to loss, whether losers cluster after trends reverse, adverse excursion before exit |
Required data | `exit_reason`, `bars_held`, timestamps + **hindsight** excursion measures (MAE) |
Leakage risk | **High if mixed with entry-time features.** Excursion is post-entry by construction |
Selection risk | Low |
Complexity | Medium |
Answers | "What does a losing trade look like in hindsight?" |
Does **not** answer | Whether any of it was knowable at entry |

### D4 — Feature-availability / instrumentation audit

| Aspect | Detail |
|---|---|
Purpose | Establish exactly which features are computable entry-time, and add only those, with tests |
Required data | None (code inspection) |
Leakage risk | **None** — the point is to prevent leakage |
Selection risk | None — commits to a feature list **before** any outcome is examined |
Complexity | **Low–medium** |
Answers | "What can be measured without look-ahead, and how do we record it?" |
Does **not** answer | Any empirical question |

### D5 — Combination (D4 → D2, with D1 and D3 as context)

| Aspect | Detail |
|---|---|
Purpose | Staged: prove feature availability, then analyse regimes descriptively, with trade diagnostics and failure modes as context |
Required data | D4 output, then instrumented features |
Leakage risk | Controlled by D4 preceding any outcome inspection |
Selection risk | Controlled by pre-registering the feature list in D4 |
Complexity | **High** |
Answers | All of the above, in a defensible order |
Does **not** answer | Future performance |

---

## 12. Recommended staged workflow

Proposed on methodological grounds only. **Phase 14D is not assumed to be
warranted** and may never be justified by this evidence.

| Stage | Scope | Gate to proceed |
|---|---|---|
**14A** | This read-only design audit | User decision |
**14B** | **Instrumentation and tests only.** Add entry-time fields to the trade record; add indicators; add tests asserting (a) each feature is computable from candles `≤ index-1`, (b) no feature changes when post-entry candles are altered. **No outcome analysis.** | Feature list frozen and reviewed |
**14C** | **Descriptive analysis only.** Run D1, D2, D3 over the frozen Phase 13 windows. Report **all** tested features including null results. Label every feature `ENTRY_TIME` or `OUTCOME_SIDE`. Report per window, not pooled only. | — terminal, unless separately authorised |
**14D** | **Only if justified.** A pre-registered regime-conditioned experiment on data not used in 14C. | **Requires new unused data.** None currently exists — 2026 was used in Phase 10 |

### 12.1 The 14D problem, stated plainly

Phase 14C will consume the only remaining clean data. Therefore:

> **A finding in Phase 14C cannot be validated on data that Phase 14C has not
> already used.** Any 14D would either re-use contaminated data or require
> data not yet obtained.

This is a hard constraint, not a scheduling detail. It means Phase 14C's
honest terminus is **hypothesis generation**, and describing it as anything
stronger would misrepresent the evidence.

### 12.2 Instrumentation ordering rule

In 14B, features must be added and **frozen before** any outcome is examined.
Adding a feature after seeing that it separates winners from losers is exactly
the contamination this staging prevents.

---

## 13. Explicit non-goals

* Do not search for, select, or recommend a profitable parameter or configuration.
* Do not tune `StrategyConfig` or change any default.
* Do not rank `baseline` against `A2`.
* Do not modify Phase 13 artifacts, code, `PLAN.md`, `SUMMARY.md` or logs.
* Do not modify or regenerate any dataset.
* Do not use 2026 to enlarge the validation sample or create new OOS claims.
* Do not claim Phase 14 findings imply future performance.
* Do not discard negative or null results.
* Do not bucket on whole-sample quantiles while describing buckets as
  entry-time knowable.
* Do not treat 267 trades as 267 independent observations.
* Do not produce window-level confidence intervals (n=6).

---

## 14. Open methodological questions

| # | Question | Status |
|---|---|---|
1 | Which trend-strength threshold, if any, has an external justification? | **Unresolved.** No conventional standard identified. Recommend reporting continuous instead of bucketing. |
2 | Volatility lookback length? | **Unresolved.** Must be pre-declared and justified; 20 matches `lookback`, but that is convenience not evidence. |
3 | Expanding vs fixed-external quantile edges? | **Unresolved.** Expanding is leakage-free but makes windows non-comparable; fixed-external may not fit. Recommend continuous reporting. |
4 | Is 267 trades sufficient for regime-conditioned analysis at all? | **Unresolved, and doubtful.** Six windows, 36–52 trades each. Any bucketed regime cell may hold <20 trades. |
5 | Should MAE/MFE be included at all? | **Contested.** Informative as hindsight description, dangerous if mixed with entry-time features. Recommend excluding from 14C or segregating in a clearly separate D3 section. |
6 | Does a regime association survive dependence-aware testing? | **Unresolved.** Block bootstrap exists with a pre-declared `block_length`, but the right block length for clustered one-position-at-a-time trades is unvalidated. |
7 | Is there any genuinely unused data for 14D? | **Unresolved. Probably not.** 2026 was used in Phase 10; 2024–2025 in Phases 5–9, 13, and would be used in 14C. |
8 | Does exploratory analysis on frozen Phase 13 windows risk re-optimising by repeated inspection? | **Acknowledged.** Mitigated by pre-registering the feature list and reporting all results, but not eliminated. |
9 | Should Phase 14C re-derive features from candles, or consume new instrumented records? | **Unresolved.** Re-derivation is auditable and needs no re-backtest; instrumented records are cheaper but require a re-run, which the no-rerun constraint currently forbids. |
10 | Is per-month aggregation preferable to per-window for calendar effects? | **Unresolved.** Monthly gives 18 points but overlaps sequential windows; window gives 6. |

---

## 15. Files that would need modification in Phase 14B (if approved)

**Nothing below is modified by this audit.** Listed for planning only.

| File | Proposed change | Risk |
|---|---|---|
`src/crypto_paper_lab/models.py` | Add defaulted entry-time fields to `PaperTrade` (e.g. `trend_at_entry`, `support_at_entry`, `resistance_at_entry`, `breakout_distance`, `retest_distance`, `range_at_entry`, `realised_volatility_at_entry`) | **Must be defaulted** so existing construction sites and stored artifacts are unaffected |
`src/crypto_paper_lab/indicators.py` | Add trailing realised-volatility and true-range/ATR helpers | Pure addition |
`src/crypto_paper_lab/strategy.py` | Return the already-computed numeric distances on `Signal` instead of discarding them | **Must not alter any existing boolean gate** — the signal decision must be bit-identical |
`src/crypto_paper_lab/simulator.py` | Copy the new `Signal` fields onto `PaperTrade` at entry | Additive |
`src/crypto_paper_lab/backtest.py` | No change expected — signals already carry the fields | — |
`src/crypto_paper_lab/stats.py` | Possibly add regime-conditional grouping helpers | Pure addition |
`tests/test_feature_availability.py` | **New.** Assert each feature uses only candles `≤ index-1` | New |
`tests/test_no_lookahead.py` | **New.** Mutate post-entry candles; assert features and signals are unchanged | New |
`tests/test_execution_model.py` | Extend to assert new fields do not alter P&L, costs or balances | Additive |
`experiments/phase14/*.py` | Analysis scripts (Phase 14C only) | New |

**Constraints on 14B:**

* No change to any existing numeric result, Phase 13 artifact, or dataset.
* No change to signal logic — instrumentation only.
* Every new field must be `ENTRY_TIME` and demonstrably invariant to
  post-entry candles.
* The Phase 13C artifacts must remain byte-identical.

---

## 16. Audit conclusions

1. **The 10 primary questions are answerable in principle, but not all from
   current records.** Trade-level direction, duration, signal type, cost burden
   and calendar effects are fully available today. Trend, volatility, breakout
   distance and retest quality are **computable from existing candles with no
   hindsight, but are not recorded** — an instrumentation gap, not a data gap.
2. **No look-ahead is required for the primary features.** Every candidate
   entry-time feature derives from candles at or before `index-1`, with a
   mandatory one-candle gap before the fill at `index`.
3. **MAE/MFE and mark-to-market measures are hindsight** and must never be
   presented as entry-time knowable. Phase 5's `diagnose_trades.py` already
   mixes both kinds; reuse requires an explicit availability split.
4. **The binding constraint is sample size, not data availability.** 267 trades
   across 6 sequential windows, with one open position at a time and mean
   holding periods of 44–58 hours, means trades are mechanically clustered.
   Regime-conditioned buckets may hold fewer than 20 trades per cell.
5. **The cleanest high-value work is D4**, because it is the only design with
   zero leakage risk and zero selection risk, and it commits to a feature list
   before any outcome is seen.
6. **Phase 14C cannot be validated on unused data**, because 2026 was already
   consumed by Phase 10 and 2024–2025 would be consumed by 14C itself. Its
   honest terminus is hypothesis generation.
7. **Phase 14 must not be framed as validation.** Every output must separate
   "associated with historical outcomes" from "can improve future trading",
   and the first must never be presented as the second.

---

*End of design audit. No file other than this document was created. No source
code, dataset, configuration or result was modified. Phase 13 remains frozen and
byte-identical. Nothing was staged, committed or pushed.*