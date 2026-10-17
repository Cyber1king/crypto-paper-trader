# Phase 36 — Multi-Market Research Architecture

**Status: PLANNING AND READ-ONLY INSPECTION ONLY. Nothing in this document is
implemented.** No architecture was built, no backtest run, no performance
calculated, no source code, dataset, manifest or frozen artifact modified, no
data downloaded, no credentials used, no AI integrated, nothing committed,
staged or pushed.

---

## 1. What exists today — verified, not assumed

Everything in this section was read from the repository during this phase. Where
a capability does not exist, that is stated plainly rather than implied.

### 1.1 Implemented and verified

| Capability | Evidence |
|---|---|
| Six paper-trading modes, all implemented | `modes.py:234-260`, `:344-455`; `reserved_modes()` returns an empty tuple |
| Execution-policy seam with 5 abstention mechanisms | `execution.py:10-14`, `:420-444`; `DisabledPolicy`, `ManualPolicy`, `DailyTargetPolicy`, `IntelligencePolicy`, `alerts` mode |
| Eleven leakage guards, all raising | `walkforward.py:169-687`; `RESEARCH_CHECKPOINT.md:199-204` |
| Strict data acquisition with research-window overlap guard | `acquisition.py:315-425`, `:396-399` |
| Canonical 6-column OHLCV schema, `dd-mm-yyyy HH:MM` UTC | `acquisition.py:46-47` |
| Publisher-checksum-verified bulk acquisition at scale | Phase 29C and Phase 33: 41/41 ETH archives verified before parsing |
| FastAPI service, loopback-only, CORS disabled | `paper_api/app.py`, `config.py` |
| React dashboard showing dataset SHA, config hash, costs, drawdown basis | `artifacts/crypto-paper-lab/` |
| Frozen pre-registration precedent | `phase29/PREREGISTRATION.md`, 662 lines, SHA `b06f36e2…` |
| Independent audit and provenance-correction precedent | `phase34/INDEPENDENT_AUDIT.md`, `phase35/PROVENANCE_CORRECTION.md` |

### 1.2 Explicitly NOT implemented — do not mistake these for capabilities

| Not implemented | Evidence |
|---|---|
| **Any external AI provider** | Repository-wide search for anthropic / openai / claude / kimi / deepseek / langchain / llama / gemini / ollama found **zero** integrations. The only `api_key` references are `data.py:93` (`MARKET_DATA_API_KEY` env read) and tests asserting credentials are **absent** (`test_api_health.py:161`, `test_api_market.py:588`) |
| **AI Intelligence is not AI** | It is a **deterministic 0–100 score** with threshold 90 (`intelligence.py:105`, `execution.py:332-417`). The dashboard states verbatim: *"a deterministic qualification gate on a 0–100 scale, not a probability, win rate, confidence percentage or expected return"* (`ai-panels.tsx:48-51`). No model is involved anywhere |
| **Any instrument registry or universe concept** | No such module exists. The `registry` hits are `ModeRegistry`; the `instrument` hits are model field names. Neither is an instrument universe |
| **Any market trading-session awareness** | `acquisition.py` has **no** session, holiday, weekend or DST logic. Repository-wide, `\bdst\b` has **zero** occurrences. The only "session" is `session.py:154` — *"An in-memory paper-trading session backed by one `PaperBroker`"*, i.e. a trading session, not a market session |
| **Any bid/ask, spread or quote handling** | `acquisition.py` contains no bid/ask/spread logic. `TradingCosts.spread_rate` is forced to `0.0` under `cost_deduction` (`costs.py:77-82`) |
| **Multi-instrument research** | `StrategyConfig.asset` defaults to `"BTC/USDT"` and every recorded research result is BTC-only. Cross-asset behaviour is recorded as **NOT ESTABLISHED** (`RESEARCH_CHECKPOINT.md:383-398`) |
| **Forex OHLC data** | Only ECB **daily reference rates** exist. No OHLC, no volume, no bid/ask (`phase33/MANIFEST_FOREX…`) |
| **News, sentiment, economic-calendar data** | Does not exist in any form |
| **Exposure / percent-time-in-market metric** | Deliberately never computed; the repository refuses to fabricate it (`windowstats.py:8-12`) |

### 1.3 Current dataset inventory

| Dataset | Range | Status |
|---|---|---|
| `BTCUSDT_1h_Cleaned (1).csv` | 2024-01-01 → 2025-12-31 | Primary research; fully consumed |
| `binance_spot_BTCUSDT_1h_202601-202608.csv` | 2026-01-01 → 2026-08-31 | OOS; consumed by Phases 10–11 |
| `binance_spot_BTCUSDT_1h_202609-202610.csv` | 2026-09-01 → 2026-10-08 | **SPENT** — Phase 30B holdout, permanently retired |
| `binance_spot_ETHUSDT_1h_202401-202610.csv` | 2024-01-01 → 2026-10-08 | **ACQUIRED — NOT YET APPROVED FOR VALIDATION** |
| `ecb_reference_rates_daily_*.csv` | 2023-12-29 → 2026-10-08 | Daily reference rates; **not OHLC**, not approved |

**Critical standing constraint.** `RESEARCH_CHECKPOINT.md:417-428` records that no
unused validation data remains. Phase 33 added ETH (a new instrument, but
overlapping dates) and Phase 30 consumed the last untouched BTC window. **As of
this phase, no genuinely unseen BTC data exists.** Unseen BTC begins 2026-10-09,
available only once Binance publishes.

---

## 2. Layer architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│ EVIDENCE LAYER      price/volume │ news │ economic events │ sentiment │
│ (new)               each item carries source, published_at,           │
│                      retrieved_at, revision, provenance               │
└───────────────────────────────────────────────────────────────────────┘
                              ▲ ingestion; nothing flows downward
┌───────────────────────────────────────────────────────────────────────┐
│ RESEARCH LAYER      structured output: facts / interpretations /       │
│ (new, provider-      uncertainty / missing_evidence / conflicts /     │
│  independent)         abstain — never a number that drives a trade     │
└───────────────────────────────────────────────────────────────────────┘
                    ▲ replaceable provider interface
┌───────────────────────────────────────────────────────────────────────┐
│ PROVIDERS (future)  Claude │ Kimi │ DeepSeek │ others — NONE EXIST   │
│                      [VERIFY] every capability, price and term        │
└───────────────────────────────────────────────────────────────────────┘
                    ▲ may only qualify entries, via the existing seam
┌───────────────────────────────────────────────────────────────────────┐
│ POLICY SEAM         ExecutionPolicy.should_enter / select_exit /       │
│ (EXISTS TODAY)      max_positions — 5 abstention mechanisms already   │
└───────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────┐
│ AUTHORITATIVE       Python: strategy │ simulator │ costs │ stats │    │
│ ENGINE — EXISTING,  backtest │ paper execution │ modes.              │
│ NOT MODIFIED BY     Computes every number shown or traded.            │
│ THIS DESIGN                                                         │
└───────────────────────────────────────────────────────────────────────┘
```

**Authority flows one way, downward.** Evidence informs research; research may
only *qualify* an entry through the seam that already exists; Python computes
everything and is never overridden.

### 2.1 The three invariants

| # | Invariant | Basis |
|---|---|---|
| **I1** | Python is the only calculation authority for P&L, size, fee, fill, balance | Already true: policies "may not set a size, a fee, a fill price or a balance" (`execution.py:28-41`) |
| **I2** | No model may alter strategy, override a risk limit, or execute | Extends I1 upward to the research layer |
| **I3** | Weak, absent or conflicting evidence produces abstention, not a guess | Already true in spirit: `IntelligencePolicy` treats an absent score as a fail (`execution.py:388-392`) |

---

## 3. Market data pipelines

Pipelines are **separate by market type**, because their semantics differ
irreconcilably. There is no shared "candle" abstraction across them.

### 3.1 Crypto spot — 24×7 continuous

**Existing capability, already proven.** 41/41 archives checksum-verified before
parsing at scale in Phase 33.

| Aspect | Rule | Status |
|---|---|---|
| Timestamp | UTC, whole-hour | **Implemented** (`acquisition.py:300`) |
| Epoch unit | Per-row magnitude inference; ms before 2025-01-01, µs after | **Implemented** (`acquisition.py:185-197`) |
| Expected interval | Exactly 1 hour, no gaps | **Implemented** (`missing_hours`) |
| OHLC invariants | `high ≥ max(open, close)`, `low ≤ min(open, close)`, `high ≥ low` | **Implemented** |
| Volume | Venue base-asset volume, must be ≥ 0 | **Implemented** |
| Gaps | Any gap is an anomaly — 24×7 has no legitimate closure | **Implemented** |
| Bid/ask | **Not available**; `spread_rate` forced 0.0 | **Limitation** |
| Venue outages | Would surface as gaps and must be investigated, never filled | **Manual** |

### 3.2 Forex — session-bound, and almost entirely unbuilt

**The project currently has zero market-session awareness.** Everything below is
new work.

| Aspect | Required rule | Status |
|---|---|---|
| Trading sessions | Must model venue sessions; a missing hourly bar outside session hours is **not** a gap | **Does not exist** |
| Weekends | Legitimately closed — must be classified, not counted as missing | **Does not exist** |
| Holidays | Per-venue calendar; absences must be verified, not assumed | **Does not exist** |
| DST transitions | Session boundaries shift; naive UTC+hour assumptions break | **Does not exist** (zero `dst` occurrences repo-wide) |
| Candle semantics | Bar boundary convention is **venue-specific** and must be recorded per instrument | **Does not exist** |
| Volume | Tick volume ≠ exchange volume; must never be relabelled | **Does not exist** |
| Bid/ask | Required for realistic execution cost; **never synthesised** | **Does not exist** |
| Timestamp | UTC internally; **native timezone recorded alongside** | Not recorded |

**Hard separation rule.** ECB daily reference rates are **not** executable forex
prices. They are single official fixings published after the fact, with no OHLC,
no volume and no bid/ask. They must live in a separate namespace, use a distinct
schema, and must never be resampled or relabelled as hourly bars. The Phase 33
dataset already complies (5-column `date,pair,rate,rate_type,source`, distinct
filename) and that separation must be preserved by any pipeline.

### 3.3 Extensibility to other market types

Futures, perpetuals, options and equities are **out of scope**. When one is
added it must define, before any data is taken: session calendar, holiday
calendar, timezone/DST rules, margin and funding semantics, volume semantics,
contract-roll rules, and corporate-action handling. A market type without a
complete contract must not be onboarded.

---

## 4. Data contracts

Every instrument's dataset must satisfy a contract **before** it may be used.

| # | Requirement | Applies to |
|---|---|---|
| C1 | Row count, first/last timestamp and interval verified independently | all |
| C2 | No duplicate timestamps, no non-monotonic ordering | all |
| C3 | Every timestamp on the expected interval boundary | all |
| C4 | OHLC relationships valid; all prices strictly positive | all |
| C5 | Volume present, finite, non-negative, with **declared semantics** | all |
| C6 | Every gap classified as *legitimate closure* or *anomaly*, with reason | all |
| C7 | **Every row independently re-derivable from a checksummed source** | all |
| C8 | Publisher digest matched where one exists; otherwise local-integrity **stated explicitly** | all |
| C9 | Licence, attribution and redistribution terms recorded | all |
| C10 | Provenance manifest with retrieval timestamp and source URL | all |
| C11 | Zero overlap with any already-consumed research or validation window | all |
| C12 | Session/holiday/DST rules validated where the market has closures | forex only |
| C13 | Volume semantics named precisely (`central`, `tick`, `quote`, `none`) | all |
| C14 | Bid/ask either present or explicitly declared absent | forex, futures |

**C7 deserves emphasis.** The Phase 34 audit established that re-deriving all
24,288 ETH rows from the archives, using code independent of the repository's own
acquisition library, produced **zero numeric mismatches**. That is the standard
this contract encodes.

---

## 5. Cross-market analysis

Permitted only where data support it, and only through Python.

| Relationship | Prerequisite | Status |
|---|---|---|
| BTC/ETH correlation or co-movement | Both on identical timestamps and interval | Feasible — both acquired |
| Crypto↔FX relationship | Overlapping timestamps **and** a defensible FX session calendar | **Blocked** — no FX OHLC exists |
| Volatility regime comparison | Comparable volatility definitions | Partly feasible; `realised_volatility` exists (`indicators.py:48`) |
| Liquidity or volume comparison across venues | Comparable volume semantics | **Not valid** — semantics differ per venue |

**No cross-market strategy may be evaluated before single-instrument evaluation
is complete.** Combining instruments multiplies the search space, and Phase 32
already documented that 12+ configurations on 2024–2025 were searched before A2
was chosen, permanently contaminating it for overlapping windows
(`RESEARCH_STATE.json:169`, `:289`).

---

## 6. Licensing constraints on expansion

| Source | Terms | Constraint |
|---|---|---|
| Binance Vision (all crypto) | CC BY-NC-SA 4.0 + Binance Vision Dataset Terms | **Non-commercial only.** Attribution required on redistribution |
| ECB reference rates | Free reuse for non-commercial purposes, attribution required | **Non-commercial only.** Attribution mandatory |
| Any future FX OHLC source | **[VERIFY]** | Must be established before acquisition |

**Architectural consequence.** ShareAlike has an obligation-of-sharing character.
Before any dataset is published outside this repository, the licence terms must be
reviewed for that effect. This project is non-commercial research and does not
currently publish data.

---

## 7. Dependencies

| Dependency | Needed by | Status |
|---|---|---|
| Instrument registry | Every pipeline, every governance stage | Spec in `INSTRUMENT_REGISTRY_SPEC.md` |
| Market data contracts | Any new instrument | Spec in §4 |
| Session/holiday/DST library | Forex only | **Must be built** |
| Evidence leakage control (`published_at ≤ decision_time`) | AI research layer only | Spec in `AI_RESEARCH_LAYER_SPEC.md` |
| Provider interface | Any AI integration | Spec in `AI_RESEARCH_LAYER_SPEC.md` |
| Untouched evaluation data | Any evaluation | **Does not exist for BTC** |
| Official FX OHLC source | Any FX OHLC work | **Not obtained** |

---

## 8. Unresolved questions

| # | Question | Status |
|---|---|---|
| U1 | Will Binance publish the 2026-10 monthly archive, and when? | 2026-10-09+ unavailable; November expected |
| U2 | Which FX venue and licence can supply checksummed hourly OHLC? | **Open** |
| U3 | Official Binance documentation for the bulk-archive ms→µs transition | **Not confirmed** (Phase 35 §6) |
| U4 | What session calendar does each FX pair follow? | **Open** |
| U5 | Is any cross-asset result permissible given the consumed BTC windows? | Governance question, not technical |
| U6 | Provider pricing, limits, retention terms | **[VERIFY]** before any integration |
| U7 | Does a historical economic calendar exist with as-known-at-the-time data? | **[VERIFY]** |

---

## 9. Out of scope for this phase

- Implementing any part of this architecture.
- Any AI provider integration or API call.
- Any backtest, signal evaluation or performance calculation.
- Any strategy, parameter, cost or application-code change.
- Any data download, credential use, commit, push or stage.
- Any profitability claim. **The strategy has none.**

`PHASE 36 ARCHITECTURE` companion documents:
`INSTRUMENT_REGISTRY_SPEC.md`, `AI_RESEARCH_LAYER_SPEC.md`,
`RESEARCH_GOVERNANCE.md`, `IMPLEMENTATION_ROADMAP.md`, `VERIFICATION.md`.