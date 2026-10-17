# Phase 32 — Research and Improvement Design

**Status: RESEARCH AND DOCUMENTATION ONLY.** No source code changed, no
parameter tuned, no backtest run, no AI provider integrated, no new performance
calculated, nothing committed or pushed.

Every finding carries one of three labels:

| Label | Meaning |
|---|---|
| **1. VERIFIED FACT** | Read directly from source or an existing recorded artifact |
| **2. HYPOTHESIS REQUIRING TESTING** | Consistent with evidence, unproven, requires a preregistered experiment |
| **3. UNKNOWN DUE TO MISSING DATA** | Cannot be assessed from what exists |

No finding is described as a proven defect. **No claim of profitability or
reliability is made anywhere in this document.**

---

## 1. Baseline: what the system actually does

### 1.1 Strategy

**VERIFIED FACT.** The strategy is a single-asset, single-timeframe,
long/short breakout-and-retest rule with an opposite-signal exit
(`strategy.py:14-46`, `RESEARCH_STATE.json:20`).

Frozen defaults (`StrategyConfig`, `strategy.py:16-46`):

| Field | Value | Field | Value |
|---|---|---|---|
| `asset` | `BTC/USDT` | `min_breakout_distance` | `0.0` |
| `timeframe` | `1h` | `trend_strength_min` | `0.001` |
| `lookback` | `20` | `retest_use_close` | `False` |
| `fast_period` | `5` | `breakout_confirm_bars` | `1` |
| `slow_period` | `12` | `max_holding_bars` | `None` |
| `breakout_buffer` | `0.001` | `stop_loss_pct` | `None` |
| `retest_tolerance` | `0.002` | `take_profit_pct` | `None` |
| | | `allowed_sides` | `None` |

**VERIFIED FACT.** Signal decision chain, in order (`strategy.py:177-192`):

1. `uptrend` + `retest_up` → **long**, `"bullish retest"`
2. `downtrend` + `retest_down` → **short**, `"bearish retest"`
3. `uptrend` + `broke_up` → **long**, `"uptrend breakout"`
4. `downtrend` + `broke_down` → **short**, `"downtrend breakdown"`
5. otherwise → **flat**, `"no confirmed breakout or retest"`

**VERIFIED FACT.** Indicator mechanics:
- `trend` = SMA(5) vs SMA(12) with a tolerance of `slow_ma × 0.001`; anything
  inside the band is `"sideways"` (`indicators.py:13-36`).
- `support_resistance` = `min(low)`, `max(high)` over the trailing 20 candles,
  computed on `candles[:-2]` so the two most recent bars are excluded
  (`indicators.py:39-45`, `strategy.py:63-65`).
- `realised_volatility` and `mean_candle_range` **exist and are causal** but are
  **not used by the baseline decision chain** — they are Phase 14C observation
  fields only (`indicators.py:48-106`).

### 1.2 Entry and exit timing

**VERIFIED FACT.** The signal is computed on `candles[:index]` — bars strictly
*before* the fill bar — and filled at **`candles[index].open`**
(`backtest.py:139-149`). Exit rules detect on `candles[index-1]` and fill at
`current.open` (`backtest.py:159`, `:184-186`). No intrabar fills are assumed.

**VERIFIED FACT.** Exits are processed before entries each iteration
(`backtest.py:151` then `:195`), so a close and an open can share one bar.

**VERIFIED FACT.** The only live exit rule is the opposite-signal exit
(`backtest.py:177-181`). `max_holding_bars`, `stop_loss_pct` and
`take_profit_pct` are all `None`, i.e. disabled. Any open position at the end is
force-closed at the final candle's close and **retained and counted**
(`backtest.py:207-213`).

### 1.3 Sizing, positions, execution assumptions

**VERIFIED FACT.** `quantity = (cash × risk_fraction) / fill` — a fraction of
**then-current cash**, not of starting balance (`simulator.py:92`). The broker
refuses `risk_fraction` outside `(0, 1]` (`simulator.py:82-83`).

**VERIFIED FACT.** Exactly one open position at all times, enforced twice:
`PaperBroker` rejects a second open trade (`simulator.py:79-80`) and the backtest
entry branch requires `broker.open_trade is None` (`backtest.py:196`).

**VERIFIED FACT.** Cost model, `cost_deduction` (`costs.py:57-60`,
`walkforward.py:66-69`): fee `0.001`, slippage `0.0005`, spread `0.0`. Fees are
charged on filled notional for **both** legs (`simulator.py:160-162`), so a round
trip pays ~0.2% fees + ~0.1% slippage. Under `cost_deduction` the fill equals the
raw chart price and spread is **forced to 0.0** — `TradingCosts` raises if a
nonzero spread is combined with this model, because it would double count
(`costs.py:77-82`). **Spread therefore cannot be modelled separately at all
under the frozen model.**

### 1.4 The six paper-trading modes

**VERIFIED FACT.** Defined as string constants with a `MODES` registry
(`modes.py:234-260`, `:344-436`). All six are implemented;
`reserved_modes()` is empty (`modes.py:450-455`).

| # | Mode | Executes | What distinguishes it |
|---|---|---|---|
| 1 | `standard` | yes | Frozen baseline signals, automatic entries and opposite-signal exits |
| 2 | `ai_intelligence` | yes | Deterministic 0–100 score must reach **threshold 90**; up to **5** positions; **no score means no trade** (`intelligence.py:105`, `execution.py:332-417`) |
| 3 | `alerts` | **no** | `supports_execution=False`, `policy=None`, **holds no broker reference at all** (`modes.py:58-65`) |
| 4 | `daily_target` | yes | Standard behaviour until the day's realised P&L reaches a dollar target, then refuses new entries for that UTC day (`daily_target.py:637-673`) |
| 5 | `manual` | yes | `should_enter` → `False` and `select_exit` → `None` unconditionally; every fill is an explicit user action (`manual_paper.py:379-415`) |
| 6 | `high_risk` | yes | Same signals as Standard; only `risk_fraction` differs, default `0.25`, ceiling `1.0` (`high_risk.py:162`, `:175`) |

**VERIFIED FACT — important.** `ai_intelligence` is **not** an LLM. Its score is
a **deterministic** qualification gate, and the dashboard renders the engine's own
caveat verbatim: *"Intelligence Score is a deterministic qualification gate on a
0–100 scale, not a probability, win rate, confidence percentage or expected
return"* (`ai-panels.tsx:48-51`). No external AI model exists anywhere in the
system today.

### 1.5 Execution-policy seam — the key architectural asset

**VERIFIED FACT.** `execution.py:10-14` states the problem precisely: *"`run_backtest`
inlines its entry rule, so 'observe this signal but do not trade it' is
inexpressible… With the decision lifted out here, **refusing to trade is a policy
choice rather than an engine modification**."*

**VERIFIED FACT.** A policy receives an immutable `DecisionContext` that
**"carries no candle objects at all … cannot introduce future leakage, because
the data required to do so is never handed to it"** (`execution.py:46-49`). A
policy may decide only `should_enter`, `select_exit`, `max_positions`
(`execution.py:20-26`) and may not set size, fees, fills or balances
(`execution.py:28-41`).

**VERIFIED FACT — five distinct abstention mechanisms already exist**: structural
(`alerts`), total-and-policy (`DisabledPolicy` `execution.py:420-444`,
`ManualPolicy`), conditional-on-state (`DailyTargetPolicy`), conditional-on-score
(`IntelligencePolicy`). This is the seam a future market-condition filter or an
AI-driven abstain would attach to **without forking the engine**.

### 1.6 Guards that do not exist

**VERIFIED FACT.** There is **no** cooldown period, consecutive-loss limit,
daily-loss limit, drawdown-triggered halt, volatility gate or regime filter
anywhere in the codebase. The only per-day gate is Daily Target's *profit*
target, which halts entries only.

### 1.7 Dashboard

**VERIFIED FACT.** A Vite + React 18 + TypeScript SPA at
`artifacts/crypto-paper-lab/`, backed by a FastAPI service on loopback with CORS
disabled and `/docs` off (`paper_api/app.py`, `config.py`). It already displays
**dataset SHA-256, strategy config hash, execution model, fee/slippage/risk
fraction, closed-trade drawdown basis, per-trade friction and every `Signal`
field** (`standard-panels.tsx:115-171`, `:339-388`, `market-chart.tsx:303-324`).

**VERIFIED FACT.** It deliberately refuses to show confidence, probability or
expected return — the mock `confidence` field was deleted as having no
authoritative source (`paper_api/README.md:110-117`). A static test suite
(`no-mock-data.test.ts`) forbids `Math.random`, `Date.now()` and a list of
live-trading terms across the UI.

### 1.8 Research infrastructure already in place

**VERIFIED FACT.** Walk-forward (`walkforward.py`) defines six windows
(`:195-208`) with `WARMUP_RULE = "full_preceding_series"` (`:75`) and
`BOUNDARY_POLICY = "retain_boundary_force_closes"` (`:78`), and enforces
**eleven leakage guards that raise rather than warn** (`RESEARCH_CHECKPOINT.md:199-204`),
including training-before-evaluation separation, overlapping-window rejection,
premature/stray trade rejection, state-carry detection by object identity, and
mid-run mutation checks on config hash, cost hash and dataset fingerprint.

---

## 2. Diagnosis

### A. Entry quality

**VERIFIED FACT.** Breakouts are identified as a close beyond a 20-bar
support/resistance level plus a `0.001` buffer; retests as a return toward a
broken level within `0.002` tolerance (`strategy.py`, `indicators.py:39-45`).

**VERIFIED FACT — the decisive limitation.** The per-trade **signal label was not
recorded** in the Phase 30B artifacts. `PaperTrade` carries `signal_close`,
`trend_state`, `breakout_distance`, `retest_distance`, `realised_volatility`,
`mean_range`, `support_at_entry`, `resistance_at_entry`, but none were persisted
into `phase30/RESULTS_trades.csv` or `RESULTS_holdout.json`. Phase 31 §4.5
recorded this as **NOT TESTABLE**.

**VERIFIED FACT.** Phase 14C (`phase14/SUMMARY.md`, not `phase14C/` — that
directory does not exist) did examine entry-context features on 2024–2025:
267 baseline trades, net −133.86, **all Spearman |ρ| ≤ 0.21**, and it
**deliberately reported no confidence interval** because the trade count is not
an independent sample (`SUMMARY.md:410-413`). It recorded 6 hypothesis
candidates and stated "**No strategy modification follows from any of them**"
(`:459-462`).

**UNKNOWN DUE TO MISSING DATA.** Whether entries were false breakouts or failed
retests. No per-trade signal label or indicator value exists for the holdout, and
re-deriving them would require re-executing the strategy over a **spent**
holdout.

**HYPOTHESIS REQUIRING TESTING.** Entry *label* may matter where the continuous
entry feature did not — Phase 14C tested continuous features, not the four-way
categorical label. Untested and untestable on existing data.

**VERIFIED FACT — what evidence would be needed.** Per-trade signal label plus
the indicator fields above, recorded on **development** data (2024–2025), with a
sample large enough to clear the repository's own floor: *"fewer than ~50 trades
makes any comparison inconclusive"* (`phase9/ACQUISITION_PLAN.md:135-146`).

### B. Market exposure

**VERIFIED FACT.** In Phase 30B the strategy held a position for **all 850
evaluated hours with zero flat periods** — sum of `bars_held` equals the
first-entry-to-last-exit span exactly, and each trade's entry timestamp equals
its predecessor's exit timestamp (Phase 31 §4.4). 20 sequential positions, no
idle time.

**VERIFIED FACT.** The engine *does* have a valid no-trade state: `analyze`
returns `"flat"` when no breakout or retest confirms (`strategy.py:191-192`),
`PaperBroker` refuses a flat signal (`simulator.py:76-77`), and `AutomaticPolicy`
excludes flat from entry (`execution.py:323`). So continuous exposure was
**because signals kept firing, not because the engine cannot decline**.

**VERIFIED FACT.** A valid abstention mechanism exists for exactly this purpose
(`DisabledPolicy`, `execution.py:420-444`), and `DecisionContext` already exposes
`intelligence_score`, `bars_held`, `open_position_count` and `daily_target_reached`
— the fields a market-condition filter would need (`execution.py:114-227`).

**HYPOTHESIS REQUIRING TESTING.** A market-condition filter would reduce the
number of trades that go on to lose. **Not testable on existing data**, and
`RESEARCH_CHECKPOINT.md:517-520` classifies adding such a filter and reporting on
2024–2025 as **exploratory data mining**.

**UNKNOWN DUE TO MISSING DATA.** What the market was doing during each holdout
trade. No regime, volatility or volume annotation was recorded per trade.

### C. Exit logic

**VERIFIED FACT.** An opposite-signal exit fires when a directional signal
appears on the side opposite the open position, detected on the last closed bar
and filled at the next open (`backtest.py:177-181`). Stop-loss, take-profit and
max-holding are implemented but disabled by default. `end_of_data` force-closes
at the final close and is retained.

**VERIFIED FACT — what Phase 31 establishes:**
- 20 trades, 15 losers; 15 of 19 opposite-signal exits closed a losing position.
- Winners were held longer than losers (median 47 h vs 37 h); the three shortest
  holds (18/21/22 h) were all losers.
- Friction flipped **no** individual trade's sign and did not create the loss —
  gross was already −6.32 before costs.
- Three best trades equalled 87.6% of the net loss magnitude; the median trade
  (−1.42) lost more than twice the mean (−0.62).

**VERIFIED FACT — what Phase 31 explicitly does NOT establish:**
- That the exit rule *caused* the losses. Exits are recorded, not blame-assigned.
- That any alternative exit would have helped.
- Any association with market conditions.

**HYPOTHESIS REQUIRING TESTING.** That a minimum-holding or confirmation rule
would improve the outcome, given the observed short-hold losers. **Requires
rerunning the strategy — forbidden here, and the holdout is spent.**

**UNKNOWN DUE TO MISSING DATA.** MAE/MFE per trade. Deliberately never
instrumented as hindsight (`RESEARCH_CHECKPOINT.md:229-230`). Without it, "did
the trade go against us before it recovered?" cannot be answered.

### D. Trading costs and execution

**VERIFIED FACT.** Fee `0.001` and slippage `0.0005` per filled leg, both legs;
spread `0.0` **forced** under `cost_deduction` (`costs.py:57-82`). No fee tiers,
no partial fills, no funding, no borrow, no market-impact or latency model.

**VERIFIED FACT.** In Phase 30B friction totalled 6.00 — 48.7% of the net loss
magnitude, ~0.30 per trade. **It flipped zero trade signs.** Gross P&L was −6.32
before any cost; net was −12.32 after.

**VERIFIED FACT — why lower costs cannot fix this.** The gross-basis profit factor
is **0.6805** and gross P&L is **−6.32**. Halving fees and slippage would still
leave a negative gross result. Costs amplified a pre-existing negative edge; they
did not create it. Any strategy-level improvement must therefore act on gross
P&L, not on cost modelling.

**VERIFIED FACT.** Friction was 86.2% of gross on the Phase 10 window, where gross
was positive (`phase10/OOS_RESULTS.md`). So cost sensitivity differs in sign
depending on whether gross is positive or negative.

**UNKNOWN DUE TO MISSING DATA.** True traded friction including bid/ask spread and
funding. The repository holds no order-book, volume-profile or funding data, and
the frozen model cannot represent spread at all.

### E. Research quality

**VERIFIED FACT — recorded results, all existing reports:**

| Study | Window | Trades | Net P&L | Profit factor | Notes |
|---|---|---|---|---|---|
| Phase 7 in-sample | 2024–2025 | 344 | −157.14 | 0.6920 | Win rate 31.686%, max DD 1.74% |
| Phase 10 OOS | 2026-01…08 | 105 | +5.05 | 1.0424 | 95% CI per trade **[−0.6688, +0.7649]**; 4 of 8 months positive; **median trade −0.89** |
| Phase 13 walk-forward | 2024–2025, 6 windows | 267 | −133.86 | **below 1.0 in all 6 windows** | **0 of 6 windows positive** |
| Phase 14C entry-context | 2024–2025 | 267 | −133.86 | — | all \|ρ\| ≤ 0.21; **no CI reported** |
| Phase 30B holdout | 2026-09…10 | 20 | −12.32 | 0.4925 (net) / 0.6805 (gross) | **INCONCLUSIVE**, pre-declared; holdout now spent |

**VERIFIED FACT.** Standing conclusion, unchanged since Phase 10
(`RESEARCH_STATE.json:14`, `RESEARCH_CHECKPOINT.md:26-30`): *"no reliable
profitability has been established… Across 23,376 hourly candles, 12 or more
configurations and two full evaluation periods, this project has no evidence of a
profitable trading rule."* Every one of the 13 phases in the checkpoint is
classified `negative_conclusion` or `diagnostic_only`; **no stage supports a
positive conclusion** (`RESEARCH_CHECKPOINT.md:337-340`).

**VERIFIED FACT — limitations recorded by the project's own reports:**
- *Single window, single asset, single timeframe* — Phase 10, 11, 13 all state
  this.
- *Statistical power too low* — per-trade σ ≈ 3.75–3.97 against means of 0.05–0.16;
  ~90–105 trades cannot resolve that effect size (`phase11/SUMMARY.md:370-371`).
- *Non-stationarity unresolved* — the 2024–2025 → 2026 sign flip with an unchanged
  strategy is a live concern eight months cannot settle (`phase11/SUMMARY.md:389-390`).
- *Bootstrap intervals describe the historical sample only*, are not forecasts,
  and assume exchangeable blocks although trades are time-adjacent
  (`phase11/SUMMARY.md:372-375`).
- *Mark-to-market drawdown uses candle closes only*; true intrabar drawdown could
  be larger (`phase11/SUMMARY.md:377-378`).
- *Six walk-forward windows are sequential, not independent*; aggregate figures
  overstate precision and no window-level CI is produced
  (`phase13/SUMMARY.md:49-51`).
- *2024–2025 dataset has no documented provenance*; construction continuity with
  2026 is not established (`phase10/SUMMARY.md:150-153`).
- *No live mark price*, so the dashboard shows no unrealised P&L
  (`standard-panels.tsx:247-255`).

**VERIFIED FACT — the binding constraint on all future work.** `Phase 15`
recorded: *"Does genuinely unused validation data remain? **No.**"*
(`RESEARCH_CHECKPOINT.md:417-428`) — 2026-01…08 consumed by Phases 10–11,
2024–2025 used since Phase 5, no other asset/timeframe ever acquired. Phase 29
acquired 2026-09…10 and Phase 30 consumed it. **Therefore, as of Phase 32, no
unused validation data remains anywhere.** Any future validation requires
acquiring genuinely new data.

**UNKNOWN DUE TO MISSING DATA.** Behaviour on any asset or timeframe other than
BTC/USDT 1h; on any market after 2026-10-08; behaviour of the strategy on forex
(never acquired); and the data-selection question of why 2024–2025 and 2026
produced opposite signs.

---

## 3. What this baseline implies for the AI research direction

**VERIFIED FACT.** The system already has: a deterministic Python calculation
engine, six modes, a policy seam with working abstention, eleven leakage guards,
six walk-forward windows, a dashboard that already shows provenance digests, and
a frozen pre-registration precedent (`phase29/PREREGISTRATION.md`, 662 lines).

**VERIFIED FACT.** What it lacks: any external data source beyond OHLCV; any
news, sentiment or economic-event capability; any non-BTC asset; any forex data;
and any unused validation data.

**VERIFIED FACT.** `ai_intelligence` is a deterministic 0–100 gate, not a model.
Naming it "AI Intelligence" does not mean an LLM is present. Any future design
must not assume existing AI capability — there is none to build on.

**VERIFIED FACT.** The gap that matters most is not "the model is too simple" but
that **the project cannot currently validate anything**, because all data is
consumed. Instrumentation and data acquisition must precede any AI evaluation.

### Prioritised experiments

Ordered by dependency. Each is a *proposal*; none is implemented here, and
**no parameter value is chosen**.

| # | Experiment | Motivation | Status |
|---|---|---|---|
| **X1** | **Acquire genuinely unused validation data before anything else** | Phase 15: no unused data remains. Without it, no result can be validated | **Blocking prerequisite for X4–X8** |
| **X2** | Record per-trade signal label + Phase 14C indicator fields on all runs | Phase 31 §4.5: entry quality is currently unassessable | Behaviour-neutral instrumentation |
| **X3** | Measure friction-free gross profit factor on 2024–2025 | Phase 31 §5: gross is already negative; establishes whether any cost model could rescue the strategy | Single descriptive statistic, no parameter search |
| **X4** | Entry-label outcome comparison on development data | 14C tested continuous features, not the categorical label | Requires X2 |
| **X5** | Market-condition abstention as an `ExecutionPolicy` | Phase 30B: 850 h continuous exposure | Requires X2 and X1 |
| **X6** | Exit-rule variants (minimum hold, confirmation) | Phase 31 §4.2: short holds all lost | Requires X1; must not use spent holdout |
| **X7** | News/event filter as a policy gate | No news data exists | Requires news acquisition |
| **X8** | Per-provider AI evaluation | Mission scope | Requires X1, X2, provider abstraction |

### Overfitting risks to manage

**VERIFIED FACT.** The project has already searched 12+ configurations on
2024–2025 and selected A2 from that search (`RESEARCH_STATE.json:169`, `:289`),
which is why A2 is contaminated for every later overlapping window. Phase 14C
warned that *"scanning even a dozen features will surface at least one apparently
interesting pattern purely by chance"* (`phase14/SUMMARY.md:417-423`). Adding a
news filter plus four AI providers plus exit variants multiplies that search space
by orders of magnitude.

**VERIFIED FACT.** `RESEARCH_STATE.json:394-402` lists paths that must never be
treated as validation, including ranking baseline against A2, further parameter
sweeps on 2024–2025 or 2026, and pooling 2024–2025 with 2026.

---

## 4. Documentation corrections found during this phase

**VERIFIED FACT.** Two corrections to commonly-repeated references:

1. **There is no `phase14C/` directory.** The Phase 14C work lives at
   `experiments/phase14/SUMMARY.md`, titled "Phase 14C - Descriptive
   Entry-Context Analysis", backed by `RESULTS_analysis.json`,
   `RESULTS_condition_summary.csv` and `RESULTS_feature_summary.csv`.
2. **The repository contains more phases than Phase 15.** Beyond Phase 15 there
   is `phase29/PREREGISTRATION.md` (the frozen pre-registration),
   `phase30/` (four result artifacts) and `phase31/` (three analysis artifacts).
   Phase 15's "no unused validation data remains" finding was partly addressed by
   Phase 29's acquisition and then re-consumed by Phase 30.

---

## 5. Non-negotiables carried forward

1. **Python remains the authoritative calculation, accounting, backtest and
   paper-execution engine.** No external model may compute P&L, sizes, fees or
   fills.
2. **No model may alter the strategy, override a risk limit, or place a trade.**
3. **The spent Phase 30B holdout must never be reused as fresh validation.**
4. **No unused validation data currently exists.** X1 is a blocking prerequisite.
5. **No profitability claim exists and none is made here.** The standing
   conclusion is unchanged.
6. **Thresholds must be preregistered before future tests**, never chosen after
   seeing results — the Phase 29D protocol is the precedent.