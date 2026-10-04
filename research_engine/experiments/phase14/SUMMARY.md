# Phase 14C - Descriptive Entry-Context Analysis

**Research only.** Nothing below optimises the strategy, changes a
threshold, ranks a configuration, or claims predictive power. Every
figure describes trades the existing strategy already produced.

## 1. Scope

Describe the entry-time context of the existing strategy's trades
using the causal features instrumented in Phase 14B, and state
plainly what the sample can and cannot support.

Out of scope by construction: strategy optimisation, threshold
selection, new trading rules, leverage, position-sizing changes,
MAE/MFE, and any outcome-derived entry feature.

## 2. Data used

- Dataset: `data/BTCUSDT_1h_Cleaned (1).csv`
- Dataset SHA-256: `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B`
- Range: 2024-01-01 00:00:00 -> 2025-12-31 23:00:00
- Candles: 17544 (expected 17544)
- Windows: 6 frozen Phase 13 evaluation windows
- Execution model: `cost_deduction` (fee 0.001, slippage 0.0005, spread 0.0)
- Starting balance 10000.0, risk fraction 0.01
- Warm-up rule: `full_preceding_series`; boundary policy: `retain_boundary_force_closes`

The 2026 dataset was **not** used. Phase 14A classified it as
documented historical context only, and it must not be pooled with
Phase 13 to enlarge the sample.

Before any feature or outcome was read, each pass was verified to
reproduce the frozen Phase 13 trade counts and ending balances
exactly. These are the same trades Phase 13 recorded.

## 3. Features analysed

Pre-declared before any outcome was examined. Full rationale for
each is in `INSTRUMENTATION.md` and the Phase 14A audit.

| feature | kind | availability | used as D2 condition |
|---|---|---|---|
| `side` | categorical | ENTRY_TIME | yes |
| `trend_state` | categorical | ENTRY_TIME | no |
| `signal_kind` | categorical | ENTRY_TIME | yes |
| `signal_close` | continuous | ENTRY_TIME | no |
| `breakout_distance` | continuous | ENTRY_TIME | yes |
| `retest_distance` | continuous | ENTRY_TIME | no |
| `realised_volatility` | continuous | ENTRY_TIME | yes |
| `mean_range` | continuous | ENTRY_TIME | no |
| `mean_range_pct` | continuous | DERIVED_FROM_ENTRY_TIME | yes |
| `support_at_entry` | continuous | ENTRY_TIME | no |
| `resistance_at_entry` | continuous | ENTRY_TIME | no |
| `level_width_pct` | continuous | DERIVED_FROM_ENTRY_TIME | yes |
| `range_position` | continuous | DERIVED_FROM_ENTRY_TIME | yes |

Deliberately **not** conditioned on:

- `trend_state` - exactly determined by side; adds no information
- `retest_distance` - present on too few trades to form a defensible cell
- `signal_close` - price level; would encode calendar position, not context
- `mean_range` - absolute price units; superseded by mean_range_pct
- `support_at_entry` - price level; superseded by level_width_pct
- `resistance_at_entry` - price level; superseded by level_width_pct

## 4. D1 descriptive findings

Full table: `RESULTS_feature_summary.csv`. Every distribution below
is of an entry-time value; outcomes are not involved at this stage.

### `signal_close` (baseline)

- present 267 / 267 (missing 0)
- min 53663.600000, q05/q25/q50/q75/q95: q05=57947.45; q25=79873.85; q50=95717.5; q75=105076.05; q95=117408.03
- max 123985.500000, mean 90785.316854, sd 19194.484110

### `breakout_distance` (baseline)

- present 267 / 267 (missing 0)
- min 0.001003, q05/q25/q50/q75/q95: q05=0.0011165909; q25=0.0018383727; q50=0.0031340888; q75=0.006599789; q95=0.0138403212
- max 0.049472, mean 0.005177, sd 0.005381

### `retest_distance` (baseline)

- present 24 / 267 (missing 243)
- min 0.000010, q05/q25/q50/q75/q95: q05=7.24665e-05; q25=0.0002980602; q50=0.0007877351; q75=0.0014927375; q95=0.0019315589
- max 0.001957, mean 0.000910, sd 0.000680

### `realised_volatility` (baseline)

- present 267 / 267 (missing 0)
- min 0.000983, q05/q25/q50/q75/q95: q05=0.0017394152; q25=0.0029794794; q50=0.0041424902; q75=0.0053570947; q95=0.0084468244
- max 0.021672, mean 0.004577, sd 0.002423

### `mean_range` (baseline)

- present 267 / 267 (missing 0)
- min 173.300000, q05/q25/q50/q75/q95: q05=268.1725; q25=420.7125; q50=546.165; q75=713.395; q95=1087.066
- max 1771.805000, mean 594.615955, sd 261.893036

### `mean_range_pct` (baseline)

- present 267 / 267 (missing 0)
- min 0.001949, q05/q25/q50/q75/q95: q05=0.0030900171; q25=0.0049063791; q50=0.0063114295; q75=0.007809155; q95=0.0119569937
- max 0.029963, mean 0.006726, sd 0.003065

### `support_at_entry` (baseline)

- present 267 / 267 (missing 0)
- min 48888.000000, q05/q25/q50/q75/q95: q05=56712.42; q25=75569.25; q50=93662.2; q75=104220.65; q95=116260.6
- max 123261.600000, mean 89528.820599, sd 19202.716619

### `resistance_at_entry` (baseline)

- present 267 / 267 (missing 0)
- min 54641.600000, q05/q25/q50/q75/q95: q05=58560.2; q25=80099.35; q50=96600.0; q75=106450.0; q95=117848.44
- max 126208.500000, mean 91834.495880, sd 19345.324710

### `level_width_pct` (baseline)

- present 267 / 267 (missing 0)
- min 0.004340, q05/q25/q50/q75/q95: q05=0.0101134287; q25=0.0172389024; q50=0.0234774866; q75=0.0330974204; q95=0.0517707729
- max 0.135718, mean 0.026765, sd 0.015842

### `range_position` (baseline)

- present 267 / 267 (missing 0)
- min -1.736518, q05/q25/q50/q75/q95: q05=-0.45418266; q25=-0.1518162492; q50=1.0149615792; q75=1.1373575768; q95=1.5583303318
- max 2.523333, mean 0.498564, sd 0.787121

### `signal_close` (A2)

- present 217 / 217 (missing 0)
- min 54785.500000, q05/q25/q50/q75/q95: q05=57880.92; q25=67758.6; q50=92978.1; q75=104350.1; q95=117853.1
- max 123985.500000, mean 89347.463594, sd 19622.354612

### `breakout_distance` (A2)

- present 217 / 217 (missing 0)
- min 0.002003, q05/q25/q50/q75/q95: q05=0.0020857945; q25=0.0028615788; q50=0.004613092; q75=0.008793552; q95=0.0178020341
- max 0.049472, mean 0.006704, sd 0.005976

### `retest_distance` (A2)

- present 14 / 217 (missing 203)
- min 0.000238, q05/q25/q50/q75/q95: q05=0.0002550875; q25=0.0005971353; q50=0.0011263; q75=0.0017649898; q95=0.0019405869
- max 0.001957, mean 0.001143, sd 0.000646

### `realised_volatility` (A2)

- present 217 / 217 (missing 0)
- min 0.001166, q05/q25/q50/q75/q95: q05=0.0018749036; q25=0.0030575367; q50=0.0043474311; q75=0.0056681071; q95=0.0089468728
- max 0.021672, mean 0.004808, sd 0.002555

### `mean_range` (A2)

- present 217 / 217 (missing 0)
- min 176.965000, q05/q25/q50/q75/q95: q05=260.8; q25=421.62; q50=565.79; q75=735.55; q95=1103.287
- max 1757.820000, mean 607.942512, sd 274.769997

### `mean_range_pct` (A2)

- present 217 / 217 (missing 0)
- min 0.001949, q05/q25/q50/q75/q95: q05=0.0031068879; q25=0.0051051872; q50=0.0066513203; q75=0.0080977741; q95=0.0123760195
- max 0.029963, mean 0.006987, sd 0.003228

### `support_at_entry` (A2)

- present 217 / 217 (missing 0)
- min 48888.000000, q05/q25/q50/q75/q95: q05=56557.06; q25=67222.4; q50=91100.0; q75=103805.9; q95=117245.18
- max 123261.600000, mean 88056.871889, sd 19632.033074

### `resistance_at_entry` (A2)

- present 217 / 217 (missing 0)
- min 54700.000000, q05/q25/q50/q75/q95: q05=58451.94; q25=69100.0; q50=94489.5; q75=105900.0; q95=118511.44
- max 126208.500000, mean 90427.175115, sd 19808.525780

### `level_width_pct` (A2)

- present 217 / 217 (missing 0)
- min 0.004340, q05/q25/q50/q75/q95: q05=0.0096259898; q25=0.0177551533; q50=0.023996888; q75=0.0343959732; q95=0.058627431
- max 0.135718, mean 0.027946, sd 0.017061

### `range_position` (A2)

- present 217 / 217 (missing 0)
- min -2.264733, q05/q25/q50/q75/q95: q05=-0.6769831807; q25=-0.2281263429; q50=1.0106840231; q75=1.1951923077; q95=1.6658027248
- max 2.523333, mean 0.494403, sd 0.866122

### `side` (baseline)

- long=134 (0.5019); short=133 (0.4981)

### `trend_state` (baseline)

- down=133 (0.4981); up=134 (0.5019)

### `signal_kind` (baseline)

- breakout=243 (0.9101); retest=24 (0.0899)

### `side` (A2)

- long=109 (0.5023); short=108 (0.4977)

### `trend_state` (A2)

- down=108 (0.4977); up=109 (0.5023)

### `signal_kind` (A2)

- breakout=203 (0.9355); retest=14 (0.0645)

**Observation on price-scale features.** `signal_close`,
`support_at_entry`, `resistance_at_entry` and `mean_range` are raw
price quantities. Over a sample in which the asset's price level
roughly doubles, their spread is dominated by calendar position
rather than by trading context. That is why the D2 conditions use the
normalised forms `mean_range_pct`, `level_width_pct` and
`range_position` instead. This is a property of the data, not a
finding about the strategy.

## 5. D2 condition findings

Full table: `RESULTS_condition_summary.csv`. Baseline and A2 are
reported separately and never pooled or ranked.

Bins are pre-declared quartiles (25%, 50%, 75%)
computed from feature values alone, before any outcome was read. No
edge was moved in response to an outcome.

> **Limitation.** Edges are computed over the whole sample, so a
> trade in window 1 was binned partly using information from window
> 6. Per Phase 14A §9.2 this is acceptable only as a descriptive
> grouping of the sample, never as a live-applicable rule. It is not
> something a trader could have known at the time.

**Observations that hold before any conditioning is applied.**

- **baseline**: 267 trades, total net P&L -133.859526, mean -0.501347 per trade, median -1.281229. 0 of 2 direction cells are net positive. 6 of 6 windows are net negative. Total friction across the pass 80.092317.
- **A2**: 217 trades, total net P&L -72.683363, mean -0.334946 per trade, median -1.232738. 0 of 2 direction cells are net positive. 4 of 6 windows are net negative. Total friction across the pass 65.134200.

Every conditional table below should be read against that. A cell
that looks better than its neighbours is usually still losing money
overall, and a relative difference between two negative cells is not
a finding.


### Pass: baseline

**side**

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | friction total | interpretable |
|---|---|---|---|---|---|---|---|
| long | 134 | 0.328358 | -0.333888 | -1.318061 | -44.741023 | 40.155991 | yes |
| short | 133 | 0.300752 | -0.670064 | -1.181846 | -89.118503 | 39.936326 | yes |

**signal_kind**

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | friction total | interpretable |
|---|---|---|---|---|---|---|---|
| breakout | 243 | 0.304527 | -0.522590 | -1.281229 | -126.989452 | 72.911376 | yes |
| retest | 24 | 0.416667 | -0.286253 | -1.117867 | -6.870075 | 7.180941 | NO - under 30 |

**breakout_distance** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 67 | 0.238806 | -0.810132 | -1.370706 | -54.278870 | yes |
| q25_q50 | 67 | 0.298507 | -0.710503 | -1.431812 | -47.603674 | yes |
| q50_q75 | 66 | 0.393939 | -0.033383 | -0.626877 | -2.203310 | yes |
| q75_inf | 67 | 0.328358 | -0.444383 | -1.281229 | -29.773673 | yes |

**realised_volatility** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 67 | 0.313433 | -0.369204 | -1.193960 | -24.736676 | yes |
| q25_q50 | 67 | 0.268657 | -0.627206 | -1.125102 | -42.022782 | yes |
| q50_q75 | 66 | 0.333333 | -0.469333 | -1.148142 | -30.975951 | yes |
| q75_inf | 67 | 0.343284 | -0.539166 | -1.762395 | -36.124118 | yes |

**mean_range_pct** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 67 | 0.328358 | -0.226954 | -1.189679 | -15.205892 | yes |
| q25_q50 | 67 | 0.313433 | -0.321657 | -1.181846 | -21.551022 | yes |
| q50_q75 | 66 | 0.348485 | 0.044490 | -1.030431 | 2.936343 | yes |
| q75_inf | 67 | 0.268657 | -1.493119 | -2.253468 | -100.038956 | yes |

**level_width_pct** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 67 | 0.298507 | -0.392089 | -1.193186 | -26.269995 | yes |
| q25_q50 | 67 | 0.373134 | -0.060921 | -0.665153 | -4.081726 | yes |
| q50_q75 | 66 | 0.212121 | -0.962741 | -1.409854 | -63.540927 | yes |
| q75_inf | 67 | 0.373134 | -0.596521 | -1.765934 | -39.966879 | yes |

**range_position** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 67 | 0.283582 | -0.944530 | -1.190057 | -63.283482 | yes |
| q25_q50 | 67 | 0.328358 | -0.305903 | -1.141640 | -20.495502 | yes |
| q50_q75 | 66 | 0.242424 | -1.090167 | -1.583800 | -71.951010 | yes |
| q75_inf | 67 | 0.402985 | 0.326425 | -0.713888 | 21.870467 | yes |

Rank co-movement with net P&L (Spearman rho, descriptive only,
no significance test):

| feature | n pairs | rho |
|---|---|---|
| `breakout_distance` | 267 | 0.034347 |
| `realised_volatility` | 267 | -0.120439 |
| `mean_range_pct` | 267 | -0.184460 |
| `level_width_pct` | 267 | -0.147527 |
| `range_position` | 267 | 0.081079 |

### Pass: A2

**side**

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | friction total | interpretable |
|---|---|---|---|---|---|---|---|
| long | 109 | 0.376147 | -0.129248 | -1.232738 | -14.088032 | 32.711509 | yes |
| short | 108 | 0.305556 | -0.542549 | -1.228017 | -58.595331 | 32.422691 | yes |

**signal_kind**

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | friction total | interpretable |
|---|---|---|---|---|---|---|---|
| breakout | 203 | 0.330049 | -0.328045 | -1.266044 | -66.593159 | 60.941161 | yes |
| retest | 14 | 0.500000 | -0.435015 | -0.333510 | -6.090205 | 4.193039 | NO - under 30 |

**breakout_distance** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 54 | 0.333333 | -0.165150 | -1.265044 | -8.918078 | yes |
| q25_q50 | 54 | 0.351852 | -0.396368 | -0.892235 | -21.403872 | yes |
| q50_q75 | 55 | 0.363636 | -0.105717 | -1.189991 | -5.814426 | yes |
| q75_inf | 54 | 0.314815 | -0.676796 | -1.642282 | -36.546987 | yes |

**realised_volatility** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 54 | 0.407407 | 0.040005 | -0.688996 | 2.160270 | yes |
| q25_q50 | 54 | 0.277778 | -0.266765 | -1.089765 | -14.405307 | yes |
| q50_q75 | 55 | 0.400000 | 0.379011 | -0.594249 | 20.845580 | yes |
| q75_inf | 54 | 0.277778 | -1.505258 | -2.448852 | -81.283906 | yes |

**mean_range_pct** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 54 | 0.351852 | -0.011314 | -0.740943 | -0.610980 | yes |
| q25_q50 | 55 | 0.363636 | -0.050785 | -0.889996 | -2.793163 | yes |
| q50_q75 | 54 | 0.370370 | 0.300646 | -1.076398 | 16.234886 | yes |
| q75_inf | 54 | 0.277778 | -1.583595 | -2.508931 | -85.514106 | yes |

**level_width_pct** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 54 | 0.351852 | -0.144722 | -1.095275 | -7.814971 | yes |
| q25_q50 | 55 | 0.381818 | 0.039196 | -0.937564 | 2.155789 | yes |
| q50_q75 | 53 | 0.245283 | -0.175371 | -1.141640 | -9.294671 | yes |
| q75_inf | 55 | 0.381818 | -1.049627 | -1.765934 | -57.729511 | yes |

**range_position** (pre-declared quartiles)

| cell | n | win rate | net P&L mean | net P&L median | net P&L total | interpretable |
|---|---|---|---|---|---|---|
| q00_q25 | 54 | 0.277778 | -1.095600 | -1.635688 | -59.162422 | yes |
| q25_q50 | 54 | 0.333333 | 0.010502 | -1.040378 | 0.567091 | yes |
| q50_q75 | 54 | 0.333333 | -0.693614 | -1.461774 | -37.455144 | yes |
| q75_inf | 55 | 0.418182 | 0.424857 | -0.619301 | 23.367112 | yes |

Rank co-movement with net P&L (Spearman rho, descriptive only,
no significance test):

| feature | n pairs | rho |
|---|---|---|
| `breakout_distance` | 217 | -0.081636 |
| `realised_volatility` | 217 | -0.165697 |
| `mean_range_pct` | 217 | -0.205167 |
| `level_width_pct` | 217 | -0.146104 |
| `range_position` | 217 | 0.129100 |

## 6. D3 robustness and caveats

- **baseline**: 267 trades across 6 windows; 24 cells tested over 7 dimensions; 1 cells below 30 trades; mean holding 49.086142 bars (range 4.000000-295.000000).
- **A2**: 217 trades across 6 windows; 24 cells tested over 7 dimensions; 1 cells below 30 trades; mean holding 60.373272 bars (range 4.000000-295.000000).

- One position at a time and a mean holding period of tens of hours mean trades are mechanically separated, not independent draws. No interval estimate is reported for that reason.
- Windows are sequential periods of one continuous series, not independent samples. Per-window figures describe spread, not significance.

## 7. Sample-size limitations

1. The entire primary sample is a few hundred trades across six
   sequential windows. Any cell is a small sample.
2. Cells below the pre-declared floor are labelled
   `insufficient_sample` in the CSV and must not be interpreted.
3. `retest_distance` exists on very few trades, so retest quality is
   described but never conditioned on.
4. No confidence interval is reported. Phase 14A §10.2 forbids
   treating the trade count as an independent sample size, and the
   block length for clustered one-position-at-a-time trades is
   unvalidated.

## 8. Multiple-comparison and researcher-degrees-of-freedom warning

Across both passes, **48 condition cells** were examined over 7 pre-declared dimensions.

Phase 14A §8.1 states that with a sample this size, scanning even a
dozen features will surface at least one apparently interesting
pattern **purely by chance**. Every cell is reported, including
uninteresting and null ones, precisely so that this count is
visible rather than hidden behind a selected subset.

A further degree of freedom deserves naming: this analysis was
designed after the instrumented features existed, and bin choice,
feature choice and normalisation were all made by someone who knows
the strategy produced mixed results. Repeated inspection of the same
windows can converge on a pattern by search alone.

## 9. What can and cannot be concluded

**Directly observed.**

- The entry-time distributions in D1, and the per-cell counts and
  outcome statistics in D2, for these trades on this data.
- Both passes reproduce the frozen Phase 13 results exactly, so the
  described trades are the committed ones.

**Descriptive interpretation.**

- Where cells differ, the size and direction of that difference in
  this sample. This is a description of past trades, not a mechanism.

**Uncertain.**

- Whether any observed difference is chance. With this many cells
  and this sample size, it cannot be established from these data.
- Whether a difference would persist in a different market period.

**Not supported by anything here.**

- That any entry-time feature predicts future performance.
- That any condition identified is exploitable as a rule.
- That any configuration is better than another.

### Hypothesis candidates

Where a cell difference is large enough to be worth naming, it is
recorded below as a **hypothesis candidate** and nothing more. A
hypothesis candidate is a reason to collect fresh data, not a rule.
**No strategy modification follows from any of them.**

**baseline**

- `mean_range_pct`: cell `q50_q75` (n=66) averaged 0.044490 mean net P&L against `q75_inf` (n=67) at -1.493119, a spread of 1.537609.
- `range_position`: cell `q75_inf` (n=67) averaged 0.326425 mean net P&L against `q50_q75` (n=66) at -1.090167, a spread of 1.416592.

Named because the best cell is net positive in this sample
and both cells clear the pre-declared size floor. That is a
weak bar: it means "worth recording", not "supported".
A spread of this size across cells this small is within what
chance produces, the bin edges came from the same sample,
and both passes sit in-sample. No rule, threshold or
configuration change follows from this.

**A2**

- `realised_volatility`: cell `q50_q75` (n=55) averaged 0.379011 mean net P&L against `q75_inf` (n=54) at -1.505258, a spread of 1.884268.
- `mean_range_pct`: cell `q50_q75` (n=54) averaged 0.300646 mean net P&L against `q75_inf` (n=54) at -1.583595, a spread of 1.884241.
- `level_width_pct`: cell `q25_q50` (n=55) averaged 0.039196 mean net P&L against `q75_inf` (n=55) at -1.049627, a spread of 1.088824.
- `range_position`: cell `q75_inf` (n=55) averaged 0.424857 mean net P&L against `q00_q25` (n=54) at -1.095600, a spread of 1.520457.

Named because the best cell is net positive in this sample
and both cells clear the pre-declared size floor. That is a
weak bar: it means "worth recording", not "supported".
A spread of this size across cells this small is within what
chance produces, the bin edges came from the same sample,
and both passes sit in-sample. No rule, threshold or
configuration change follows from this.

Note that the two passes are **not** independent confirmations of
each other. A2's `min_breakout_distance` was chosen in Phase 7 on
2024-2025, so both passes describe overlapping, already-used data.
Apparent agreement between them is not out-of-sample evidence.

## 10. Is a Phase 14D justified?

**No, and this is a structural problem rather than a matter of
judgment.**

Phase 14A §12.1: Phase 14C has now consumed the only remaining
clean data. The 2026 set was already used in Phase 10, and
2024-2025 is used here. There is therefore **no unused data left** on
which a Phase 14D hypothesis could be validated.

A Phase 14D would have to either re-use data Phase 14C has already
seen - in which case it is not validation - or wait for data not yet
acquired. So the honest position is that Phase 14 terminates at
hypothesis generation, and any future validation requires new data
and its own pre-registration.

## 11. Reproducibility

- Script: `experiments/phase14/run_descriptive.py`
- Module: `research_engine/src/crypto_paper_lab/entrycontext.py`
- Tests: `research_engine/tests/test_phase14c_analysis.py`
- Deterministic: no randomness, fixed iteration and sort order,
  fixed rounding for output. Repeated runs are byte-identical.
- Bins are derived from feature values only, so they cannot depend
  on an outcome.
- Git commit: `25bd7d0ab651e356240d8148525fb664938562b0`
- Git working tree clean: **False**

> **Recorded deviation:** this analysis was produced with a dirty
> working tree. The dirty state at execution time was:
>
>     `M research_engine/src/crypto_paper_lab/indicators.py`
>     ` M research_engine/src/crypto_paper_lab/models.py`
>     ` M research_engine/src/crypto_paper_lab/simulator.py`
>     ` M research_engine/src/crypto_paper_lab/strategy.py`
>     `?? research_engine/experiments/phase14/`
>     `?? research_engine/src/crypto_paper_lab/entrycontext.py`
>     `?? research_engine/tests/test_entry_time_features.py`
>     `?? research_engine/tests/test_phase14c_analysis.py`
>
> The Phase 14B instrumentation is part of that dirty state, so
> the commit alone does not identify the code that produced these
> figures. This is recorded rather than hidden.

## 12. Dataset SHA-256

    201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B

Path: `data/BTCUSDT_1h_Cleaned (1).csv`

Verified at load time against the frozen constant in
`crypto_paper_lab.walkforward`. The dataset was opened read-only and
not modified.

## 13. Statement on strategy parameters

**No strategy parameter, threshold, default, entry rule or exit rule
was changed.**

The analysis re-runs the frozen Phase 13 windows using
`baseline_config()` and `a2_config()` exactly as committed. It reads
the resulting trades and writes new files under
`experiments/phase14/`. No file under `research_engine/src/` was
modified by this phase, and the Phase 13 artifacts are unchanged.

No leverage, margin, partial exit, trailing stop, profit callback or
position-sizing change was introduced. MAE/MFE were not computed.
No outcome-derived entry feature was created.

Phase 14D was not started.
