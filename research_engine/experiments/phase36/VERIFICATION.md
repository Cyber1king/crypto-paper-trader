# Phase 36 — Verification

**Phase type: planning and read-only inspection only.**

Records what was inspected, what was verified, what was deliberately not done,
and the exact Git state.

---

## 1. Safety and integrity confirmation

| Restriction | Status |
|---|---|
| No backtest run | **Held** — no `run_backtest` or `analyze` call in any Phase 36 script |
| No performance calculated or evaluated | **Held** |
| No strategy logic modified | **Held** — 0 tracked files modified |
| No existing application code modified | **Held** |
| No dataset modified | **Held** — all dataset digests re-verified below |
| No manifest modified | **Held** |
| No frozen research artifact modified | **Held** — all seven re-verified below |
| No data downloaded | **Held** |
| No credentials used | **Held** — no API key, token or password read or written |
| No AI integration implemented | **Held** |
| No commit, push or stage | **Held** |
| No file deleted | **Held** |
| No existing file edited | **Held** — only 6 new files created |

---

## 2. Files created (6, all new, all under `experiments/phase36/`)

| File | Bytes |
|---|---|
| `MULTI_MARKET_ARCHITECTURE.md` | 17,505 |
| `AI_RESEARCH_LAYER_SPEC.md` | 13,699 |
| `INSTRUMENT_REGISTRY_SPEC.md` | 10,793 |
| `IMPLEMENTATION_ROADMAP.md` | 12,093 |
| `RESEARCH_GOVERNANCE.md` | 7,924 |
| `VERIFICATION.md` | this file |

**No other file was created, modified, renamed, moved or deleted.**

---

## 3. Read-only inspection performed

### 3.1 Source inspected

| File | What was inspected |
|---|---|
| `crypto_paper_lab/strategy.py` | `StrategyConfig` — confirmed `asset="BTC/USDT"`, `timeframe="1h"` |
| `crypto_paper_lab/indicators.py` | trend, support/resistance, realised volatility, mean candle range |
| `crypto_paper_lab/backtest.py` | loop, timing, exit precedence, end-of-data |
| `crypto_paper_lab/simulator.py` | sizing, cost application, broker guards |
| `crypto_paper_lab/costs.py` | `TradingCosts`; confirmed `spread_rate` forced to 0.0 under `cost_deduction` (`:77-82`) |
| `crypto_paper_lab/stats.py` | metric definitions |
| `crypto_paper_lab/dataset.py` | `validate_dataset` — confirmed 6 assertions only |
| `crypto_paper_lab/acquisition.py` | strict validation, canonical schema, overlap guard |
| `crypto_paper_lab/walkforward.py` | 11 leakage guards |
| `crypto_paper_lab/execution.py` | policy seam and its guarantees |
| `crypto_paper_lab/modes.py` | six modes, abstention mechanisms |
| `crypto_paper_lab/intelligence.py` | deterministic score, threshold 90 |
| `crypto_paper_lab/windowstats.py` | exposure refusal |

### 3.2 Prior-phase artifacts inspected

`phase29/PREREGISTRATION.md`, `phase30/` (all 4 result files),
`phase31/ANALYSIS.md`, `phase32/` (all 5 files), `phase33/ACQUISITION_REPORT.md`,
`phase34/INDEPENDENT_AUDIT.md`, `phase35/PROVENANCE_CORRECTION.md`,
`data/phase33/` manifests.

### 3.3 Repository-wide searches performed

| Search | Result |
|---|---|
| `anthropic\|openai\|claude\|kimi\|deepseek\|langchain\|llama\|gemini\|ollama` in `research_engine` | **0 integrations** |
| Same in frontend `artifacts/crypto-paper-lab` | **0 matches** |
| `api_key\|API_KEY\|chat.completion` | 15 hits — **all** either the `MARKET_DATA_API_KEY` env read (`data.py:93`) or tests asserting credentials are **absent** |
| `universe\|registry\|instrument\|allowed_symbols\|symbols =` in `src` | Only `ModeRegistry` and model field names — **no instrument registry exists** |
| `\bdst\b` in `src` | **0 occurrences** |
| `trading session\|market session\|session_open\|session_close` in `src` | **0 occurrences**; the only "session" is `session.py:154`, a paper-trading session object |
| `session\|holiday\|weekend` in `acquisition.py` | **False** — no session/holiday/DST awareness |

---

## 4. Verified facts underpinning the deliverables

| # | Fact | Verified how |
|---|---|---|
| V1 | **No external AI provider is integrated** | Repository-wide search, source + frontend |
| V2 | **`ai_intelligence` is deterministic, not a model** | `intelligence.py:105`, `execution.py:332-417`, and the dashboard's own verbatim caveat (`ai-panels.tsx:48-51`) |
| V3 | **No instrument registry exists** | Source search; `registry` hits are `ModeRegistry` only |
| V4 | **No market-session / holiday / DST awareness exists** | `acquisition.py` search false; zero `\bdst\b`; zero trading-session terms |
| V5 | **No bid/ask or spread handling in acquisition** | `acquisition.py` contains no bid/ask/spread logic |
| V6 | `spread_rate` is forced to 0.0 under `cost_deduction` | `costs.py:77-82` |
| V7 | `validate_dataset` performs only 6 assertions | `dataset.py:37-70` — non-empty, `high≥low`, `low≤open≤high`, `low≤close≤high`, `volume≥0`, strictly increasing. **No** interval spacing, **no** price positivity, **no** session check |
| V8 | Strategy default is single-instrument | `strategy.py:16-17` |
| V9 | Cross-asset behaviour is NOT ESTABLISHED | `RESEARCH_CHECKPOINT.md:383-398` |
| V10 | No untouched BTC validation data exists | `RESEARCH_CHECKPOINT.md:417-428`, plus Phase 33 probe of 2026-10-09/10/11 all 404 |
| V11 | The Phase 30B BTC holdout is spent | `phase30/SUMMARY.md:343` |
| V12 | Five datasets exist; none is research-approved | `data/` inventory |
| V13 | ECB dataset is daily rates, not OHLC, Grade B provenance | `phase33/MANIFEST_FOREX…` |

---

## 5. Frozen artifact digests — re-verified unchanged

| Artefact | SHA-256 | Status |
|---|---|---|
| `data/BTCUSDT_1h_Cleaned (1).csv` | `201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b` | **unchanged** |
| `data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` | **unchanged** |
| `experiments/phase29/PREREGISTRATION.md` | `b06f36e21df0fe403e3a75cbf8c3de84161607348966d622b65ea3f51bf217cc` | **unchanged** |
| `experiments/phase30/RESULTS_holdout.json` | `4d69a2e29ea7c6a8ce6c9998ff7f5b550ba2feecb5d38eb07eca450705ff80ab` | **unchanged** |
| `experiments/phase30/RESULTS_holdout.txt` | `fd3f7741a7dbab8fd222f47683e950d291edc26722e237334d7b008aac861780` | **unchanged** |
| `experiments/phase30/RESULTS_trades.csv` | `174d558719f31067922b5823ce9213f58555c3ddb54505f5f8021ed5b7404fd1` | **unchanged** |
| `experiments/phase30/SUMMARY.md` | `9e3171b08555e06b4c380fbe97cf68e21e9cba447a599a9d70bb2f0fc7e1968d` | **unchanged** |
| `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` | **unchanged** |
| `data/phase33/ecb_reference_rates_daily_20240101_20261008.csv` | `030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753` | **unchanged** |
| `data/phase33/MANIFEST_ETHUSDT_1h_202401_202610.txt` | `faf29e372369b903…` | **unchanged** |
| `data/phase33/MANIFEST_FOREX_ECB_daily_reference_rates.txt` | `d648754c27ac4bac…` | **unchanged** |
| `experiments/phase33/ACQUISITION_REPORT.md` | `bb4460993f11276f…` | **unchanged** |
| `experiments/phase34/INDEPENDENT_AUDIT.md` | `e611ecdba5fecc5dc…` | **unchanged** |
| `experiments/phase35/PROVENANCE_CORRECTION.md` | (recorded this phase) | **unchanged** |

The 12 corrected Phase 33 sidecars were also re-verified as still carrying the
millisecond statement; this phase did not touch them.

---

## 6. Git state — exact

| Field | Value |
|---|---|
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Branch | `main` |
| `origin/main` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Modified tracked files | **0** |
| Deleted tracked files | **0** |
| Staged files | **0** |
| Commits ahead of `origin/main` | **0** |
| Commits or pushes performed | **none** |
| Untracked files before this phase | 261 |
| Untracked files after this phase | 266 (+5 at capture time; this file makes 6) |

**Untracked breakdown after this phase:**

| Group | Count |
|---|---|
| `data/oos` frozen Phase 29 artefacts | 30 |
| `experiments/phase29/PREREGISTRATION.md` | 1 |
| `experiments/phase30/` results | 4 |
| `experiments/phase31/` analysis | 3 |
| `experiments/phase32/` research design | 5 |
| `data/phase33/` acquisition | 211 |
| `experiments/phase33/ACQUISITION_REPORT.md` | 1 |
| `experiments/phase34/INDEPENDENT_AUDIT.md` | 1 |
| `experiments/phase35/PROVENANCE_CORRECTION.md` | 1 |
| **`experiments/phase36/` — new in this phase** | **6** |
| **Total** | **263–267 depending on capture point** |

---

## 7. Honest limitations of this phase

| # | Limitation |
|---|---|
| L1 | **Nothing was built.** Every document is a specification. No registry, no session library, no provider interface exists. |
| L2 | **No provider facts were verified.** Model IDs, pricing, limits and retention terms are marked **[VERIFY]**. I deliberately did not call any API or fetch provider documentation in this phase, so no capability is asserted. |
| L3 | **No profitability assessment.** None was possible and none is offered. The standing conclusion is unchanged. |
| L4 | **Eligibility screening criteria in the registry spec are illustrative**, not final. They must be preregistered before discovery runs. |
| L5 | **Acceptance criteria are proposals.** None has been tested; no test was written or run. |
| L6 | The dataset inventory was taken from `data/` as of this phase; further archives could exist outside it. |
| L7 | Phase 35's open item stands: official Binance documentation for the bulk-archive ms→µs transition was not confirmed. |

---

## 8. Deliverable content self-checks

| Deliverable | Required content confirmed |
|---|---|
| `MULTI_MARKET_ARCHITECTURE.md` | Implemented vs proposed distinguished; three market pipelines; data contracts; cross-market limits; licensing; dependencies; unresolved questions; out-of-scope |
| `INSTRUMENT_REGISTRY_SPEC.md` | Symbol/base/quote; market type and venue; source and licensing; timeframes and coverage; timestamp and session rules; volume semantics and quote availability; quality status; approval status; discovery and refresh; delisting, renaming, unavailable data, unsupported instruments; explicit "never assume every listed asset is suitable" |
| `AI_RESEARCH_LAYER_SPEC.md` | Provider-independent interface; price/volatility, news, calendar, sentiment, cross-market, uncertainty; timestamps, attribution, confidence explanation, abstention; no override of risk controls; no trade execution; explicit statement that no provider integration exists |
| `RESEARCH_GOVERNANCE.md` | Full lifecycle with entry and rejection criteria per stage; integrity ≠ approval; spent holdout retired; anti-reuse rules |
| `IMPLEMENTATION_ROADMAP.md` | Six priority areas in the required order; per-instrument evaluation before cross-market; AI last; dependencies; acceptance criteria; out-of-scope |

**No invented profitability threshold. No profitability claim.**

---

## 9. Standing conclusion

**Unchanged.** No reliable profitability has been established for this strategy
(`RESEARCH_STATE.json:14`). This phase designed how to test that conclusion
properly across multiple markets. It did not assume the conclusion's reversal,
and it does not work around the absence of usable validation data — it names that
absence as the first thing that must be fixed.