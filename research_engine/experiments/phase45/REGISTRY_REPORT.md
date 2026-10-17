# Phase 45 — Instrument Registry

**Date:** 2026-10-09

Improvements were made **only where a gap was demonstrated by probing the
running code**, not by comparing the registry against the Phase 36 spec. The spec
proposed roughly 50 fields; most of them are genuinely useful, but adding fields
nobody reads would have made the file look thorough while changing nothing.

---

## 1. The gap, demonstrated

Before any change, `load_registry` verified only that four sections existed and
were lists. Probing what that actually caught:

| Probe | Before | Meaning |
|---|---|---|
| Instrument with no `timeframe` | **ACCEPTED** | Required identity field was optional |
| Instrument with no `volume_semantics` | **ACCEPTED** | Volume meaning was unverifiable |
| Instrument with no `venue` | **ACCEPTED** | Source of prices unrecorded |
| Instrument list empty | **ACCEPTED** | "Nothing protected" indistinguishable from "nothing declared" |
| Forex entry with timeframe `"banana"` | **ACCEPTED** | Nonsense passed |
| Reservation with no `instrument_id` | **ACCEPTED** | A reservation that could bind to nothing |

`venue`, `licence_name`, `provenance_grade` and similar fields existed in the
file and were read by **no code**. They were documentation, not declarations.

---

## 2. What was added

### `registry_schema.py` (new)

Metadata coherence validation, invoked from `load_registry` so it runs before
any guard logic can act on a malformed entry.

**Completeness.** Every instrument must declare: `instrument_id`, `market_type`,
`timeframe`, `volume_semantics`, `venue`, `source_provider`,
`licence_knowledge`, `provenance_grade`, `timestamp_convention`,
`timestamp_normalized_tz`, `research_approval`.

**Contradiction refusal** — each a real inconsistency, not a style preference:

| Contradiction | Refused because |
|---|---|
| `timestamp_normalized_tz` ≠ UTC | A silent conversion would change the data it describes |
| `crypto_spot` + `BLOCKED_WRONG_DATA_TYPE` | A supported type cannot be blocked for wrong data type |
| Blocked market type + any approval | A blocked type may not claim approval or consumption |
| `BLOCKED_WRONG_DATA_TYPE` without a `blocker` | A block nobody can review cannot be lifted |
| `crypto_spot` + `volume_semantics: "none"` | A crypto venue publishes volume; "none" misreports an unpopulated field |
| `tick` volume without a `volume_note` | Tick volume is not a traded quantity and must never be compared as one |
| `bid_ask_available: false` without a `spread_note` | Otherwise a backtest could silently ignore costs it cannot see |
| `RESEARCH_APPROVED` without `approved_preregistration_id` | Approval is a governance act; it can never follow from data quality |
| Reservation `status: RESERVED` + `used: true` | A window cannot be both available and spent |
| Reservation `status: USED` + `used: false` | The two fields contradict |
| Reservation naming an unregistered instrument | A reservation for nothing cannot be enforced |
| Duplicate `instrument_id` | A reservation could bind to the wrong entry |
| Empty `instruments` section | Not "nothing is protected" — that is "nothing declared" |

---

## 3. Registry upgraded to version 2

Five instruments, each carrying the full dimension set. Forex pairs are
**described accurately rather than absent**, which is the point of Phase 45's
"extensible metadata":

### ETH/USDT (supported crypto spot)

`venue: binance-spot` · `source_provider: Binance Vision` ·
`licence_knowledge: UNVERIFIED` · `provenance_grade: A` ·
`timestamp_convention: bar_opens_at_hour_utc` ·
`volume_semantics: central_base` · `bid_ask_available: false` +
`spread_note` · `research_approval: DATA_VERIFIED_NOT_RESEARCH_APPROVED`

`provenance_grade: A` is earned — Phase 34 re-derived all 24,288 rows with zero
mismatches.

**`licence_knowledge: UNVERIFIED`, not a guessed licence name.** Binance
redistribution terms are not established in this repository, so the honest state
is recorded. `licence_note` explains why.

`timestamp_convention` is new and load-bearing: a bar that *opens* at HH:00 and
one that *closes* at HH:00 produce identical-looking timestamps with different
meanings.

### EUR/USD, GBP/USD, USD/JPY (blocked forex)

`market_type: forex_reference_rates` · `source_provider: European Central
Bank` · `licence_knowledge: VERIFIED` · `licence_name: CC BY-NC-SA 4.0` ·
`volume_semantics: "none"` · `timestamp_convention: instantaneous_fixing` ·
`timestamp_native_tz: Europe/Frankfurt` · `research_approval:
BLOCKED_WRONG_DATA_TYPE` + stated `blocker`

The forex **licensing is verified** — genuinely known and recorded with
attribution and non-commercial restriction. The crypto **licensing is not** —
recorded as `UNVERIFIED`. That asymmetry is the point: `UNVERIFIED` is a real
state, not a failure to fill in a field.

`blocker` states why: not OHLCV (a single daily fixing carries no intraday
range), and no session/holiday/DST validator exists. Forex stays blocked because
it is *described*, not because it is *absent*.

### BTC/USDT

`research_approval: RESEARCH_CONSUMED`, with all three spent windows enumerated
as objects with outcomes. BTC is the only instrument whose approval state records
exhaustion.

---

## 4. Extensibility

The schema is driven by explicit vocabularies, not hard-coded expectations:

- `MARKET_TYPES_BLOCKED` — recognised-but-refused, so a new blocked type is a
  data change, not a code change
- `PROVENANCE_GRADES` — `A` / `B` / `C` / `UNVERIFIED`
- `QUALITY_STATUSES` — per **dataset**, never per instrument (an instrument can
  hold datasets in different states)
- `APPROVAL_STATES` — six states, with `RESEARCH_APPROVED` the hardest to reach
- `LICENSE_KNOWLEDGE` — `VERIFIED` / `UNVERIFIED` / `RESTRICTED`
- `TIMESTAMP_CONVENTIONS` — open / close / instantaneous fixing

**Discovering an instrument never approves it.** `test_shipped_forex_not_automatically_approved`
asserts that no non-spot entry holds `RESEARCH_APPROVED`, and
`test_approval_without_preregistration_refused` makes the state unreachable
without a frozen preregistration id.

---

## 5. Defects found and fixed

### 5.1 A real contradiction in the reservation writer

Phase 45's schema immediately refused the registry's own output:

```
reservation 'ETH-2026-RESERVATION': status is RESERVED but 'used' is true.
A window cannot be both available and spent.
```

`_consume_reservations()` set `used: true` while leaving `status: "RESERVED"`.
Nothing checked this, so it went unnoticed across Phases 39–41.

**The writer was fixed, not the validator relaxed.** Consumption now sets
`status: "USED"` alongside `used: true`. This is the clearest demonstration in
this phase that making metadata load-bearing surfaces defects that documentation
never did.

### 5.2 A less actionable error message

Two `status != "RESERVED"` checks existed in `assert_evaluation_permitted`, and
the first fired for a spent window, reporting *"status is 'USED'; only RESERVED
may be evaluated"* instead of *"already been used"*. Consolidated and reordered
so the actionable message wins.

### 5.3 Declared timeframe was not bound to actual data

`validate_dataset` took `expected_interval_seconds` as an optional
caller-supplied number. A caller could declare timeframe `1h` and validate
5-minute data by omitting the parameter. `identity_covers()` was written in
Phase 41 to catch this and then never called.

Fixed: `validate_dataset(identity=…)` derives the interval from the declaration,
and refuses contradictory explicit arguments rather than reconciling them
silently. `identity_covers()` removed as dead code, its check now actually
running.

### 5.4 Stale `__all__`

`researchguard.__all__` omitted `assert_series_permitted`,
`consume_reservation` and `candle_fingerprint`. Corrected, with a test asserting
every public name is exported.

---

## 6. Tests

`tests/test_registry_schema.py` — **70 tests**, all passing.

Coverage: missing fields (parametrised over all 11), every contradiction listed
in §2, vocabulary errors, reservation/consumed-window coherence, shipped-registry
conformance, and declared-vs-actual timeframe binding.

Three tests would fail without the Phase 45 fixes specifically:

- `test_consumption_keeps_status_and_flag_consistent`
- `test_spent_window_reports_spent_not_a_status_problem`
- `test_declared_timeframe_must_match_actual_spacing`

Plus Phase 43's `test_registry_all_exports_present`.

---

## 7. Verification

| Suite | Result |
|---|---|
| Focused (registry + guard + validation + gates) | **273 passed**, 11s |
| Full suite, 40 files | **2227 passed, 0 failed** |

ETH reservation re-verified after all changes: `RESERVED` / `used: false` /
`preregistration_id: null`. Registry `research_approval` remains
`DATA_VERIFIED_NOT_RESEARCH_APPROVED` with no approved preregistration id.

All 11 frozen artifact digests match.

---

## 8. What was deliberately not changed

- **`research_registry.candle_index.json`** — derived per-bar data. Regenerating
  it would risk fingerprint drift for no benefit.
- **The Phase 29 pre-registration** — frozen, and Phase 44 confirms it unchanged.
- **Consumed BTC entries** — still recorded, still refused for reuse.
- **The `MARKET_TYPES_SUPPORTED` set** — still `{"crypto_spot"}` only. Nothing
  about forex became supported.

No profitability threshold was invented. No instrument was approved. The ETH
window remains reserved and unspent.