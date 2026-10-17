# Phase 41 Market Readiness Matrix

**Date:** 2026-10-09

Statuses: **IMPLEMENTED AND TESTED** · **DOCUMENTED, NOT IMPLEMENTED** ·
**BLOCKED — MISSING DATA** · **BLOCKED — MISSING SESSION/DST** · **NOT APPROVED**

---

## Crypto spot

### Common to BTC/USDT and ETH/USDT

| Capability | Status |
|---|---|
| Required OHLCV columns present | IMPLEMENTED AND TESTED |
| Timestamp/date column present | IMPLEMENTED AND TESTED |
| `Z` and offset timestamps → naive UTC | IMPLEMENTED AND TESTED |
| Single timezone convention per series | IMPLEMENTED AND TESTED |
| Strictly chronological, no duplicates | IMPLEMENTED AND TESTED |
| Exact interval spacing | IMPLEMENTED AND TESTED |
| Gaps classified as defects (24×7 has no closure) | IMPLEMENTED AND TESTED |
| Positive finite OHLCV | IMPLEMENTED AND TESTED |
| OHLC relationships (open/close within high/low) | IMPLEMENTED AND TESTED |
| Declared instrument identity | IMPLEMENTED AND TESTED |
| Declared timeframe | IMPLEMENTED AND TESTED |
| Volume semantics declared explicitly | IMPLEMENTED AND TESTED |
| Config asset label vs dataset identity | IMPLEMENTED AND TESTED |
| File SHA-256 provenance | IMPLEMENTED AND TESTED (Phase 33/34) |
| Reservation / consumption enforcement | IMPLEMENTED AND TESTED (Phase 39/40) |
| Cross-asset transfer authorization | IMPLEMENTED AND TESTED (Phase 39) |
| Bid/ask spread modelling | NOT APPROVED — crypto venue data is not in the repository |
| Order-book or slippage depth model | DOCUMENTED, NOT IMPLEMENTED |

### BTC/USDT

| Aspect | Status |
|---|---|
| Data (17,544 bars, 2024-01-01 → 2025-12-31) | IMPLEMENTED AND TESTED — validates clean |
| Dataset validation | PASSES all Phase 41 checks |
| Untouched validation data available | **BLOCKED — MISSING DATA** |
| Reuse of 2026 OOS window | **NOT APPROVED** — consumed Phase 10/11 |
| Reuse of Phase 29 holdout | **NOT APPROVED** — consumed Phase 30B |
| Research readiness | **BLOCKED** — no untouched data remains |

Every available BTC window has been consumed. Validation passing does not create
new data.

### ETH/USDT

| Aspect | Status |
|---|---|
| Data (24,288 bars, 2024-01-01 → 2026-10-08) | IMPLEMENTED AND TESTED — validates clean, 0 gaps |
| Dataset validation | PASSES all Phase 41 checks |
| Warm-up 2024-01-01 → 2025-12-31 (17,544 bars) | reserved as indicator context only |
| Evaluation 2026-01-01 → 2026-10-08 (6,744 bars) | RESERVED, UNSPENT, UNAPPROVED |
| Reservation enforcement | IMPLEMENTED AND TESTED (Phase 40) |
| Preregistration | **BLOCKED — MISSING** (must be frozen before results are seen) |
| Research question and thresholds | **BLOCKED — MISSING** (Phase 38 left open) |
| Instrument-transfer scope | DOCUMENTED, NOT IMPLEMENTED (needs an explicit authorization record) |
| Research readiness | **NOT APPROVED** |

ETH's data is the best in the repository and its validation is the strongest.
That is exactly why the remaining blockers are governance, not data.

---

## Forex — EUR/USD, GBP/USD, USD/JPY

**Overall: BLOCKED. Do not approve.**

### Data

| Aspect | Status |
|---|---|
| OHLC data | **BLOCKED — MISSING DATA** |
| Available: ECB daily reference rates | A single fixing per day — no `high`, no `low`, no intraday range |
| Converting reference rates to OHLC | **NOT APPROVED** — would fabricate the volatility a strategy trades on |
| Tick or bar source with licensing | **BLOCKED — MISSING DATA** |
| Volume | **BLOCKED — MISSING DATA** — no volume of any kind exists in these sources |

A daily reference rate is a published fixing, not a traded price range. There was
no intraday high or low at the fixing because no intraday trading occurred. Any
OHLC built from it would be invented.

### Session and calendar

| Aspect | Status |
|---|---|
| Session boundaries (Sydney/Tokyo/London/New York) | **BLOCKED — MISSING SESSION/DST** |
| Weekend closures | **BLOCKED — MISSING SESSION/DST** |
| Holiday calendars per pair | **BLOCKED — MISSING SESSION/DST** |
| DST transitions | **BLOCKED — MISSING SESSION/DST** |
| Missing interval vs legitimate closure | **BLOCKED — MISSING SESSION/DST** |
| UTC conversion | PARTIAL — loader normalises offsets; a trading calendar still needs it |
| Calendar library | **BLOCKED — MISSING SESSION/DST** — none in the repository |

### Execution realism

| Aspect | Status |
|---|---|
| Bid/ask and spread handling | **BLOCKED — MISSING DATA** — forex is quoted bid/ask, not a single price |
| Spread model | **BLOCKED — MISSING DATA** |
| Tick volume vs centralised traded volume | Vocabulary implemented; no applicable source |
| Source licensing and provenance | **BLOCKED — MISSING DATA** |

Forex's bid/ask spread is often comparable to the signal being traded. Ignoring
it would not merely weaken results — it would invert their meaning. No
implementation was attempted, because the data to validate against does not
exist.

### Enforcement (all three pairs)

| Aspect | Status |
|---|---|
| Registry entries | Present as explicit documentation |
| `market_type` validation | IMPLEMENTED AND TESTED — refuses `forex_reference_rates` |
| Volume semantics declared `"none"` | IMPLEMENTED AND TESTED |
| Identity construction | IMPLEMENTED AND TESTED — refuses |
| Interval classification | IMPLEMENTED AND TESTED — refuses, names session/DST as the reason |

Forex cannot reach evaluation through any supported path. Three independent
refusal points, each tested.

---

## Summary

| Instrument | Data | Validation | Session/DST | Research readiness |
|---|---|---|---|---|
| BTC/USDT | CONSUMED | PASSES | N/A (24×7) | **BLOCKED** |
| ETH/USDT | RESERVED | PASSES | N/A (24×7) | **NOT APPROVED** |
| EUR/USD | REFERENCE RATES ONLY | REFUSES | **BLOCKED** | **BLOCKED** |
| GBP/USD | REFERENCE RATES ONLY | REFUSES | **BLOCKED** | **BLOCKED** |
| USD/JPY | REFERENCE RATES ONLY | REFUSES | **BLOCKED** | **BLOCKED** |

No instrument is ready for evaluation. Passing validation is a necessary
condition for readiness, not a sufficient one — the gaps above are governance,
data and calendar problems, none of which validation can fix.