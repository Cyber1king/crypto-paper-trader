# Phase 37 — Data Approval Checklist

**Phase type: read-only audit and planning.** No backtest, no performance
calculation, no data acquisition, no file modification, no AI integration,
nothing staged, committed or pushed.

**Nothing is approved by this document.** It states what remains before approval
could even be considered.

---

## 0. Method

Every fact below was **recomputed during this phase**, not read from a prior
report. Specifically re-derived:

- all dataset SHA-256 digests;
- ETH row count, range, gaps, duplicates, line endings, span arithmetic;
- **all 24,288 ETH rows re-derived from the 41 raw archives** using an
  independent epoch decoder, compared numerically;
- all 41 publisher `.CHECKSUM` digests re-hashed;
- the epoch-unit distribution across archives;
- the actual assertions inside `validate_dataset`;
- whether `StrategyConfig.asset` is enforced anywhere.

Where a prior phase's claim was checked and found **incomplete or imprecise**, that
is recorded rather than repeated.

---

## 1. Verification performed this phase

| Check | Result |
|---|---|
| Five dataset digests match recorded values | **PASS** |
| ETH 24,288 rows, 2024-01-01 → 2026-10-08 | **PASS** |
| ETH zero gaps, zero duplicates, LF only | **PASS** |
| ETH span arithmetic: 1012 × 24 = 24,288 | **PASS** |
| 41 archives match publisher `.CHECKSUM` | **PASS** |
| 24,288 rows re-derived from archives | **PASS** — **0 numeric mismatches** |
| Epoch units: 8,784 ms + 15,504 µs | **PASS** |
| 12 2024 sidecars assert MILLISECONDS | **PASS** (assertion-aware) |
| 29 later sidecars assert MICROSECONDS | **PASS** (assertion-aware) |
| Forex schema is not OHLCV | **PASS** |
| `config.asset` is **not** enforced against data | **VERIFIED FACT** |

---

## 2. ETH/USDT approval checklist

### 2.1 VERIFIED requirements — satisfied

| # | Requirement | Evidence (recomputed this phase) |
|---|---|---|
| **V1** | Source provenance | Binance Vision, 41 archives, per-archive `.CHECKSUM` published |
| **V2** | Licensing | CC BY-NC-SA 4.0 + Binance Vision Dataset Terms; **non-commercial**, attribution required on redistribution |
| **V3** | Correct epoch interpretation | 8,784 rows ms (2024), 15,504 µs (2025+); per-row decoder reproduces all 24,288 rows with **0 mismatches** |
| **V4** | Provenance record accuracy | Phase 35 correction in force: 12 sidecars assert milliseconds, 29 assert microseconds |
| **V5** | Timestamp validation | Strictly increasing, 0 duplicates, 0 gaps, all on the hour |
| **V6** | OHLCV validation | 0 invalid OHLC, 0 non-positive prices, 0 negative volume, 0 unparseable, 0 malformed column counts |
| **V7** | Continuity | Every step exactly 1 hour across the whole 1,012-day span |
| **V8** | Schema | `Date,Open,High,Low,Close,Volume`, `dd-mm-yyyy HH:MM` UTC, LF only |
| **V9** | Independent reproducibility | All 24,288 rows re-derived from archives by independent code — **0 mismatches** |
| **V10** | Dataset digest | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb`, stable |
| **V11** | Provenance grade | **Grade A** — publisher digests published and matched 41/41 |

### 2.2 VERIFIED requirement — strategy compatibility

**This is a finding that changes the risk picture, and it was not previously
stated plainly.**

The strategy is **fully scale-invariant**. Every threshold is a fraction or a
relative distance:

| Element | Expression | Scale dependence |
|---|---|---|
| Trend | `fast_ma > slow_ma + slow_ma * strength` | none |
| Breakout | `close > level * (1 + breakout_buffer)` | none |
| Retest | `abs(close - level) / level <= retest_tolerance` | none |
| Support/resistance | `min(low)`, `max(high)` of the data itself | none |
| Position sizing | `cash * risk_fraction / fill` | adapts |

And `StrategyConfig.asset` is **never validated against the dataset**. The only
non-declaration reference is `replay.py:363`, which passes the label into the
replay context. Nothing raises if the data is ETH and the label says BTC/USDT.

**Consequence: nothing technical would prevent running the strategy on ETH
without approval.** That is precisely why the governance stage exists — and why
it must not be treated as a formality.

It also means "strategy compatibility" is **not** a blocker for ETH. The blocker
is entirely on the governance side.

### 2.3 UNRESOLVED requirements — must be closed before approval

| # | Requirement | Status |
|---|---|---|
| **U1** | **Cross-asset scope decision** | Phase 32 records cross-asset behaviour as **NOT ESTABLISHED**. A written decision is required: is a BTC→ETH instrument change in scope? |
| **U2** | **Documented research question** | None exists. A question must be preregistered before approval, not after. |
| **U3** | **Preregistration plan** | None exists. Must name the exact dataset digest, configuration, costs, warm-up, evaluation-start and the full decision rule, per the `phase29/PREREGISTRATION.md` precedent. |
| **U4** | **Untouched evaluation data — identified and reserved** | **Existence shown below, but not yet formally reserved.** |
| **U5** | Formal governance record | No instrument has ever been advanced to `RESEARCH APPROVED`. |

### 2.4 Suitable, untouched evaluation data for ETH — precise finding

**ETH 2026-01-01 → 2026-10-08 has never been examined for performance.** No ETH
performance figure was ever calculated in any phase: Phase 33 acquired, Phase 34
audited integrity only, Phase 35 corrected provenance text, Phase 36 planned.
**No trade has ever been generated on ETH.**

That makes the ETH 2026 window a **genuinely unexamined window for ETH**, unlike
BTC where every window is consumed.

**But the evaluation design matters enormously.** `WARMUP_RULE =
"full_preceding_series"` (`walkforward.py:75`) means the engine must be given the
preceding series so indicators are warm. The correct design is therefore:

- feed ETH 2024-01-01 → 2026-10-08 in full;
- set `evaluation_start` at the **ETH 2026 boundary**;
- the account starts flat with the full balance and no pre-boundary trade occurs.

This makes the 2026 trades genuinely untouched **provided** ETH 2024–2025 is never
used for exploratory performance analysis. If ETH 2024–2025 is inspected for
strategy behaviour, it becomes consumed for that purpose and the design must
change.

**Two cautions:**

1. **ETH 2024–2025 is not a clean development set in the usual sense.** The
   strategy's parameters were selected on BTC 2024–2025, not ETH. Using ETH
   2024–2025 as "development data" risks a second search on top of a
   BTC-derived configuration — exactly the contamination that made A2 unusable
   for overlapping windows (`RESEARCH_STATE.json:169`, `:289`).
2. **ETH's date range overlaps consumed BTC windows.** That is *not*
   contamination (different instrument) but is also *not* an independent BTC
   sample. ETH results say nothing about BTC without a BTC-specific test.

### 2.5 ETH verdict

**INCOMPLETE.** All data-side prerequisites (V1–V11) are verified and the data is
Grade A. The outstanding items U1–U5 are governance artefacts, not data defects.
Nothing here blocks acquisition or integrity work; everything here blocks
**approval**.

---

## 3. BTC/USDT readiness

### 3.1 The spent holdout remains retired — verified

| Fact | Verified |
|---|---|
| Holdout digest | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` — **unchanged** |
| Range | 2026-09-01 00:00 → 2026-10-08 23:00 UTC, 912 candles |
| Phase 30B verdict | INCONCLUSIVE, pre-declared |
| Retirement | `phase30/SUMMARY.md:343` — *"This holdout is now spent."* |

**The holdout may be read as a historical record. It may never be used to
validate, select, tune or compare anything.** No re-use is proposed anywhere in
this phase.

### 3.2 No untouched BTC validation data exists

| Window | Status |
|---|---|
| 2024-01-01 → 2025-12-31 | Consumed — every research phase from Phase 5 onward |
| 2026-01-01 → 2026-08-31 | Consumed — Phases 10 and 11 |
| 2026-09-01 → 2026-10-08 | **SPENT** — Phase 30B |
| 2026-10-09 onward | **Does not exist yet** |

Phase 33 probed forward and recorded `HTTP 404` for monthly `2026-10` and daily
`2026-10-09`, `-10`, `-11`. The newest available data is `2026-10-08`, already
held.

### 3.3 Exact requirements for new BTC evaluation data

| # | Requirement | Note |
|---|---|---|
| B1 | Wait for Binance to publish data after 2026-10-08 | Monthly archive expected first Monday of November 2026 |
| B2 | Acquire with publisher `.CHECKSUM` verification before parsing | Mechanism already proven 41/41 on ETH |
| B3 | Pass data contract C1–C14 | See `VALIDATION_GAPS.md` |
| B4 | Reach Grade A provenance | Publisher digests exist for Binance Vision |
| B5 | Record it in the registry with `consumed_windows` empty for the new range | |
| B6 | **Sufficient length** | The repository's own floor: *"fewer than ~50 trades makes any comparison inconclusive"* (`phase9/ACQUISOCATION_PLAN.md:135-146`). A handful of days will not suffice |
| B7 | Preregistration naming the exact digest | |
| B8 | Formal `RESEARCH APPROVED` record | |

**No unavailable data is claimed to have been acquired.**

### 3.4 BTC verdict

**BLOCKED.** Not by a governance decision — by the **absence of data**. Nothing
can proceed until Binance publishes, and then only after B1–B8.

---

## 4. Forex readiness

Assessed **separately per instrument**, because none has suitable market data.

### 4.1 What exists

`ecb_reference_rates_daily_20240101_20261008.csv`, re-verified this phase:

| Property | Verified |
|---|---|
| SHA-256 | `030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753` |
| Schema | `date,pair,rate,rate_type,source` — **5 fields on every row** |
| OHLC columns | **none** — verified by regex over the header |
| Volume column | **none** |
| Pairs | EURUSD, GBPUSD, USDJPY, 709 dates each |
| Row count | 2,127 = 709 × 3 |
| Provenance grade | **Grade B** — ECB publishes no digests; local SHA-256 establishes local integrity only |

**This is a daily reference fixing, not market OHLC.** A reference rate is a
single official rate published after the fact. It is not a traded bar, carries no
open/high/low/close, no volume and no bid/ask, and cannot be substituted for
candles or resampled into them.

### 4.2 Per-instrument status

| Instrument | Status | Reason |
|---|---|---|
| **EUR/USD** | **BLOCKED** | Only a daily reference rate exists. No OHLC market data. Grade B provenance |
| **GBP/USD** | **BLOCKED** | Same |
| **USD/JPY** | **BLOCKED** | Same. Also precision is 3 decimals vs 5 for the other two, so precision is not uniform |

### 4.3 Requirements for suitable forex data

| # | Requirement | Detail |
|---|---|---|
| F1 | **Genuine OHLC observations** | Real traded or vendor OHLC bars. **Reference rates must never be substituted for candles**, and no candle may be synthesised |
| F2 | **UTC timestamps, timezone documented** | Native venue timezone recorded alongside normalised UTC; bar-boundary convention stated per instrument |
| F3 | **Trading sessions** | Venue session opens/closes and breaks. A missing bar outside session hours is **not** a gap |
| F4 | **Weekend closures** | Classified as legitimate closure, never as missing data |
| F5 | **Holidays** | Per-venue calendar with provenance and a documented update path |
| F6 | **DST transitions** | Session boundaries shift; naive UTC+hour assumptions break. **Zero `dst` occurrences exist in the codebase today** |
| F7 | **Missing-interval rules** | Every absence classified `legitimate_closure` or `anomaly`, with reason. Anomalies raise; closures do not |
| F8 | **Volume semantics** | Named precisely: `central_base`, `central_quote`, `tick`, or `none`. **Tick volume must never be represented as centralised exchange volume** |
| F9 | **Bid/ask and spread** | Present where the methodology requires it; **never synthesised**. `TradingCosts.spread_rate` is currently forced to `0.0` under `cost_deduction` (`costs.py:77-82`), so the frozen execution model cannot represent spread at all |
| F10 | **Source provenance** | Preferably publisher digests. If absent, Grade B with the limitation stated explicitly |
| F11 | **Permitted use** | Licence recorded; non-commercial constraint confirmed; attribution string stored |
| F12 | **Session/DST library** | **Does not exist.** Must be built and independently reviewed before any FX data is validated |

### 4.4 A source explicitly considered and rejected

The **Dukascopy datafeed** returns real binary tick data and is reachable.
Converting it to hourly OHLC would require this project to author and own a
tick-to-hourly aggregation whose methodology becomes part of the dataset's
provenance, and whose "volume" would be **tick count, not exchange volume**
(`phase33/ACQUISITION_REPORT.md` §4.5). Recorded as an open option with that
caveat, not silently performed. The **Yahoo chart endpoint** was rejected on
provenance and licensing grounds.

### 4.5 Forex verdict

**All three: BLOCKED.** Not by governance — by the absence of any market OHLC
data, and of the session/DST machinery required to validate it.

---

## 5. Integrity approval remains separate from research approval

Restated because it is the most common failure mode:

| Passing | Does **not** imply |
|---|---|
| Data contract C1–C14 | The dataset may be evaluated |
| Checksum verification (Grade A) | Research approval |
| Provenance verification | That a result will be positive |
| Research approval | Profitability or a deployable edge |
| A full two-year ETH history | An independent BTC sample |

**No instrument in this repository is, or is close to, `RESEARCH APPROVED`.**

---

## 6. Cross-instrument observation

The three asset classes are blocked for **three different reasons**, and the
remedies differ:

| Instrument | Blocking reason | Remedy |
|---|---|---|
| BTC/USDT | Data does not exist yet | **Wait** for publication, then acquire and approve |
| ETH/USDT | Governance artefacts absent | **Write** the scope decision, question and preregistration |
| EUR/USD, GBP/USD, USD/JPY | Suitable data does not exist | **Acquire** genuine OHLC, and **build** session/DST validation |

Only ETH can be advanced by work done inside this repository today. BTC is
blocked on an external publisher. Forex is blocked on both an external source
and internal engineering.

---

## 7. Limitations of this audit

| # | Limitation |
|---|---|
| L1 | **No performance was calculated for any instrument.** Whether a preregistered question would be answerable is untested and untestable here |
| L2 | Suitability of the ETH 2026 window is inferred from the fact that no ETH performance was ever computed. It was **not** confirmed by inspecting any result, because none exists |
| L3 | Whether ~6,700 ETH bars yield enough trades to exceed the ~50-trade floor is **unknown**. ETH's realised trade rate has never been measured, and measuring it would require a backtest, which is forbidden |
| L4 | No FX venue, licence or session calendar was evaluated this phase; no data was downloaded |
| L5 | Provider, session-calendar and licensing details remain **[VERIFY]** items from Phase 36 |
| L6 | This audit verified **integrity and readiness**, not scientific merit. Readiness is not permission |

---

`PHASE 37 DATA READINESS` continues in `INSTRUMENT_READINESS_MATRIX.md`,
`VALIDATION_GAPS.md` and `VERIFICATION.md`.