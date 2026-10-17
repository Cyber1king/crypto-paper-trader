# Phase 41 Validation Report

**Date:** 2026-10-09
**Scope:** Strengthen data validation for the crypto pipeline; define safe readiness boundaries for crypto and forex.

Phase 40 closed with PASS and no unresolved critical bypass, so the full Phase 41
scope was available. Nothing here is blocked.

---

## 1. Two real defects found

### 1.1 Mixed timezone-awareness raised `TypeError`, not a refusal

`data._parse_timestamp` converted `Z`-suffixed input to a timezone-*aware*
datetime while plain ISO input produced a naive one. The same file could
therefore yield two incompatible types, and the comparison in
`validate_dataset` raised:

```
TypeError: can't compare offset-naive and offset-aware datetimes
```

A caller saw a crash, not a data-quality refusal.

Fixed at both ends:

- `_parse_timestamp` now normalises **everything to naive UTC**. `Z` input and
  `+02:00` offset input are both converted and stripped, so the loader has one
  output convention. Verified: `08:00+02:00` correctly becomes `06:00` UTC, not
  `08:00`.
- `_check_timezone_consistency` refuses a series mixing aware and naive
  timestamps with an actionable message instead of a `TypeError`.

### 1.2 `dataset_identity` was absent

`load_ohlcv_csv` returned a bare list of candles. Nothing recorded which
instrument, timeframe or market the data represented, so a BTC-labelled config
could be handed an ETH file with nothing to notice. Volume semantics were
equally ambiguous: a `volume` column could be centralised volume or tick volume,
and a backtest comparing the two would be comparing different quantities.

Closed by `dataset_identity.py`.

---

## 2. What was implemented and tested

### 2.1 `dataset_identity.py` (new)

An immutable `DatasetIdentity` requiring `instrument_id`, `timeframe`,
`market_type` and `volume_semantics`. Every field is mandatory and validated on
construction — nothing is inferred from a filename, because a guessed identity
is the failure mode this record exists to prevent.

Rules enforced:

| Rule | Rationale |
|---|---|
| Unknown `volume_semantics` refused | A volume column alone does not say which quantity it holds |
| Unknown `market_type` refused | Forex has no validator here |
| `volume_semantics="none"` invalid for `crypto_spot` | A crypto venue publishes volume; "none" would misreport an unpopulated field |
| Unvalidatable timeframe refused | Only `1h` spacing is implemented |
| `assert_compatible_with_config` refuses label mismatch | The Phase 41 core requirement |

The frozen BTC configuration is untouched. Cross-asset use still requires an
explicit `CrossAssetAuthorization` in the research registry — the error message
says so, pointing a caller at the real mechanism rather than leaving them to
invent one.

`"none"` remains valid vocabulary: it is honest for ECB reference rates, where
no volume of any kind exists and fabricating one would be a fabrication.

### 2.2 `intervals.py` (new)

`classify_intervals`, `contiguous_slice`, `expected_bar_count`.

The central decision is that **in 24×7 crypto a gap is always a defect**, and the
module refuses to generalise to forex:

```
interval classification is implemented for 24x7 crypto spot only; classifying a
gap in a forex series requires session, holiday and DST knowledge that this
repository does not have. Refused rather than guessed, because in forex a
missing bar may be a legitimate closure rather than a defect.
```

That distinction is the whole reason for a separate module. In crypto a gap
means repair or reject. In forex a gap might be expected, and rejecting it would
be wrong. Guessing wrong in either direction is harmful, so the module declines.

`contiguous_slice` reports where a contiguous run exists without modifying data
or interpolating a price. Repair is a caller decision.

### 2.3 `dataset.py` and `data.py`

`validate_dataset` already checked positivity, finiteness, OHLC relationships,
ordering and optional exact spacing from Phase 39. Added timezone consistency.

---

## 3. Market-specific validation

### Crypto spot — implemented and tested

| Check | Status |
|---|---|
| Required OHLCV columns present | tested |
| Timestamp or date column present | tested |
| Timestamps parse; `Z` and offsets normalised to naive UTC | tested |
| Single timezone convention per series | tested |
| Strictly chronological, no duplicates | tested |
| Exact interval spacing | tested |
| Gaps classified as defects, not closures | tested |
| Positive finite OHLCV | tested |
| OHLC relationships | tested |
| Declared instrument identity | tested |
| Declared timeframe | tested |
| Volume semantics declared explicitly | tested |
| Config label vs dataset identity | tested |
| Source provenance (file SHA-256) | pre-existing, Phase 33/34 |

### Forex — **BLOCKED**, deliberately

**Do not approve forex OHLC data.** Three independent blockers:

1. **No OHLC data exists.** The ECB source provides daily reference rates: a
   single fixing per day, not a traded price range. There is no `high` or `low`
   because no intraday trading range occurred at that fixing. Converting them
   into synthetic OHLC would be fabricating data, which the rules forbid and
   which would be trivially self-defeating — it would invent the volatility the
   strategy trades on.
2. **No session validator.** See below.
3. **No licensed tick or bar source.** See §5.

The existing ECB data remains correctly blocked: `volume_semantics: "none"`,
`market_type: "forex_reference_rates"`, and
`identity_for_registry_entry` refuses it.
`test_shipped_registry_forex_identities_are_refused` pins this.

### Requirements documented but **not implemented**

Each would need real work and none was faked:

| Requirement | Status |
|---|---|
| UTC conversion | **partially done** — the loader normalises offsets; a forex calendar still needs it |
| Real session boundaries (Sydney/Tokyo/London/New York) | not implemented |
| Weekend closures | not implemented |
| Holiday calendars per currency pair | not implemented |
| DST transitions | not implemented |
| Missing interval vs legitimate closure | **not implementable** without the above |
| Bid/ask and spread handling | not implemented |
| Tick volume vs centralised traded volume | vocabulary exists; no forex source |
| Source licensing and provenance | not started |

Implementing session rules from memory would mean inventing a trading calendar
and then validating data against my own invention. That is fabrication with extra
steps, so it was not done.

---

## 4. Tests

| Scope | Result | Duration |
|---|---|---|
| `test_dataset_validation.py` (new, 55 tests) | 55 passed | 1.2s |
| `test_dataset.py`, `test_backtest.py`, `test_walkforward.py`, `test_acquisition.py` | 90 passed | 12s |
| `test_research_guard.py`, `test_research_gaps.py` | 134 passed | 12s |
| **Full suite** | see `VERIFICATION.md` | — |

Focused coverage: all-zero rows, NaN, infinities, negative values, invalid OHLC,
wrong instrument label, wrong timeframe, duplicates, out-of-order timestamps,
missing hourly intervals, gap-vs-closure classification, missing and ambiguous
volume semantics, forex rejection, and confirmation that real BTC and ETH files
still parse and validate.

`test_eth_dataset_row_count_unchanged` asserts 24,288 rows and both endpoint
timestamps — structural facts, not prices.

**Zero backtests run. No ETH 2026 performance computed or inspected.**

---

## 5. What remains blocked

### Forex: BLOCKED

| Blocker | Type |
|---|---|
| No OHLC data (ECB gives one daily fixing) | blocked by missing data |
| No session/holiday/DST validator | blocked by missing implementation |
| No licensed tick or bar source | blocked by missing source |

### Crypto: no new blockers

BTC and ETH both validate cleanly. Phase 37's `BLOCKED` status for BTC
(consumed data) and `INCOMPLETE` for ETH (governance artifacts absent) are
unchanged by this phase — validation was never what blocked them.

---

## 6. Honest limits

- **Unregistered series still validate.** Identity is checked when supplied.
  `load_ohlcv_csv` cannot require it without breaking every existing caller, so
  declaration remains the caller's choice. The research registry closes this for
  evaluation paths; a purely local development load is unaffected.
- **Provenance is not re-verified by the loader.** File SHA-256 checks exist in
  `walkforward.validate_dataset_integrity` and the research registry, not in the
  generic CSV load, which is right: a generic loader cannot know which digest to
  expect.
- **No calendar library.** Date arithmetic uses `timedelta` against explicit
  timestamps. Fine for hourly crypto; insufficient for DST-aware forex.
- **Passing these tests says nothing about profitability.** It says the data
  validator refuses malformed input. That is all it says.