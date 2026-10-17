# Phase 36 — Instrument Registry Specification

**Status: SPECIFICATION ONLY. No registry exists and none was built.**

The repository has **no instrument registry today**. Searching the source for
`universe`, `registry`, `instrument`, `allowed_symbols` or `symbols =` returns
only `ModeRegistry` (unrelated) and model field names (unrelated). This document
specifies what must exist.

---

## 1. Purpose and boundaries

The registry is the single authority on **which instruments the project may
study**, and on **what is known about each one**. It is a metadata catalogue,
not a strategy.

**It must not:** select instruments for trading, encode strategy parameters,
hold market data, or make research-approval decisions on the analyst's behalf.
It records approval *status* that governance sets.

---

## 2. Instrument record

Every instrument occupies exactly one record. Fields are mandatory; "unknown"
is a legal value and is preferred over a guess.

### 2.1 Identity

| Field | Type | Notes |
|---|---|---|
| `instrument_id` | str | Stable, immutable primary key. Never reused after retirement |
| `symbol_native` | str | As the venue writes it, e.g. `ETHUSDT`, `EUR/USD` |
| `symbol_normalized` | str | Project canonical form, e.g. `ETH/USDT` |
| `base_asset` | str | `ETH`, `EUR` |
| `quote_asset` | str | `USDT`, `USD` |
| `venue` | str | e.g. `binance-spot`. Never inferred |
| `market_type` | enum | `crypto_spot` \| `forex_spot` \| `unsupported` |
| `aliases` | list | Prior symbols, including renamed ones |

### 2.2 Data source and licensing

| Field | Type | Notes |
|---|---|---|
| `source_provider` | str | e.g. `Binance Vision`, `ECB` |
| `source_url_pattern` | str | Templated retrieval URL |
| `checksum_published` | bool | **Whether the publisher issues digests.** Drives evidence strength |
| `licence_name` | str | e.g. `CC BY-NC-SA 4.0` |
| `commercial_use` | enum | `permitted` \| `excluded` |
| `attribution_required` | bool | |
| `redistribution_terms` | str | Free text; ShareAlike obligations noted |
| `attribution_string` | str | Exact text to display — e.g. the ECB attribution already recorded |

### 2.3 Coverage and timeframes

| Field | Type | Notes |
|---|---|---|
| `timeframes_available` | list | e.g. `["1h"]`. Empty means unusable |
| `earliest_available` | ts | Null if unknown |
| `latest_available` | ts | Null if unknown |
| `coverage_verified_to` | ts | **What this project has actually verified**, distinct from what exists |
| `coverage_verified_by` | str | Which phase/manifest |

`coverage_verified_to` must never be inferred from `latest_available`. The Phase
33 report's finding matters: BTC data "exists" only to 2026-10-08, which is
already consumed.

### 2.4 Time, session and volume semantics

| Field | Type | Notes |
|---|---|---|
| `timestamp_native_tz` | str | Venue's own timezone |
| `timestamp_normalized_tz` | str | Always `UTC` internally |
| `bar_boundary_convention` | str | e.g. `bar opens at HH:00 UTC` |
| `trading_sessions` | list | **Empty for 24×7 crypto.** Required for forex |
| `weekly_closure` | str | e.g. `Sat 21:00 UTC -> Sun 21:00 UTC` |
| `holiday_calendar` | ref | Per-venue calendar reference |
| `dst_observed` | bool | Whether session boundaries shift with DST |
| `volume_semantics` | enum | `central_base` \| `central_quote` \| `tick` \| `none` |
| `bid_ask_available` | bool | If false, spread cannot be modelled |
| `volume_note` | str | Forced text for `tick`/`none` |

**`volume_semantics` must never be left blank.** Phase 33 recorded the rule
directly: *tick volume must not be represented as centralized exchange volume.*

### 2.5 Quality and governance

| Field | Type | Notes |
|---|---|---|
| `datasets` | list | Per-dataset: path, SHA-256, rows, first/last, manifest ref |
| `quality_status` | enum | `unchecked` \| `checked_clean` \| `checked_with_findings` \| `failed` |
| `last_quality_check` | ts | |
| `quality_findings` | list | Open findings, e.g. the Phase 34/35 provenance item |
| `governance_stage` | enum | See `RESEARCH_GOVERNANCE.md` §1 |
| `research_approved` | bool | **False by default. Never implied by quality_status** |
| `consumed_windows` | list | Ranges already examined — the anti-reuse record |
| `notes` | str | |

---

## 3. Discovery

### 3.1 Automatic discovery

Discovery may enumerate an instrument universe from a venue's published listing.
It creates records at stage `DISCOVERED` only.

**Discovery must never confer eligibility.** A listed asset is a *candidate*, not
a research subject.

### 3.2 Eligibility screening

A discovered instrument must pass all of the following to reach `DATA CHECKED`:

| # | Criterion |
|---|---|
| E1 | Licence permits this project's non-commercial use, and the obligation is recorded |
| E2 | Attribution string exists and is storable |
| E3 | Hourly (or target timeframe) OHLC available for a **meaningful** history |
| E4 | Volume present with unambiguous semantics, or absence is declared |
| E5 | Publisher checksums exist, or local-integrity-only is explicitly accepted |
| E6 | Instrument is not a duplicate, rebrand or low-liquidity variant of an existing one |
| E7 | Data is retrievable **without credentials** |
| E8 | The market's session/closure semantics are fully specifiable |

**Never assume every listed asset is suitable.** Illustrative exclusions, none of
which are rules yet:

- stablecoins or wrapped/bridged variants that duplicate an underlying;
- pairs whose history begins after a research window already consumed;
- extremely low-liquidity pairs where volume semantics are unreliable;
- assets subject to redenomination or token-migration events in the target range.

These are **illustrative** screening considerations. The final criteria must be
fixed in a preregistration before discovery is run, never chosen after seeing
which assets pass.

---

## 4. Refresh

| Trigger | Action |
|---|---|
| Scheduled | Re-probe `latest_available` on a fixed cadence; record the result either way |
| After acquisition | Update `coverage_verified_to` only from a **verified manifest** |
| Licence change | Re-evaluate eligibility; an instrument may be suspended |
| Quality failure | Set `quality_status = failed`; it cannot remain `checked_clean` |
| Governance change | Update `governance_stage` with an audit entry |

**A refresh that finds no new data is still an event worth recording**, since
"checked and nothing new" and "not checked" must be distinguishable.

---

## 5. Edge cases and required handling

| Case | Required behaviour |
|---|---|
| **Delisted asset** | Set `governance_stage = RETIRED`. **Never delete** — the record and its `consumed_windows` are the anti-reuse evidence |
| **Renamed symbol** | Add to `aliases`; keep `instrument_id` stable. Do **not** create a new record |
| **Data temporarily unavailable** | Record the failure with date and cause. **Never** substitute another source silently |
| **Unsupported instrument** | `market_type = unsupported`, with a reason. It may never reach a pipeline |
| **Partial coverage** | Record both available and verified coverage. Never present availability as verification |
| **Checksum unavailable at source** | `checksum_published = false`; evidence strength drops to local-integrity-only, stated in the manifest |
| **Duplicate discovery of the same pair** | Reject as a new record; link to the existing one |
| **Symbol reused for a different asset** | Treat as a **new** instrument with a new `instrument_id`. Never inherit the old record |
| **Retrieved data contradicts the manifest** | Block the dataset; do not update the manifest to match the data |

---

## 6. Storage and integrity

- Records stored as version-controlled data files, one per instrument.
- Every record carries its own `record_sha256`; a change requires a stated reason.
- The registry is **append-only in spirit**: status transitions are recorded, not
  overwritten silently.
- The registry must be able to answer, for any date range and any instrument:
  *"has this range already been examined?"*

---

## 7. Seed records implied by existing evidence

These are the instruments the current repository already knows about. Values are
taken from Phase 33/34/35 artifacts, not invented.

| `symbol_normalized` | `market_type` | `timeframes_available` | `checksum_published` | `commercial_use` | `governance_stage` |
|---|---|---|---|---|---|
| BTC/USDT | `crypto_spot` | `1h` | true | excluded | data acquired, **validation data exhausted** |
| ETH/USDT | `crypto_spot` | `1h` | true | excluded | `ACQUIRED — NOT YET APPROVED` |
| EUR/USD | `forex_spot` (rates only) | `daily rate` | **false** | excluded | `ACQUIRED — NOT YET APPROVED`, granularity insufficient |
| GBP/USD | `forex_spot` (rates only) | `daily rate` | **false** | excluded | as above |
| USD/JPY | `forex_spot` (rates only) | `daily rate` | **false** | excluded | as above |

Notes carried from prior phases:
- ETH: 24,288 rows, 2024-01-01 → 2026-10-08, SHA `7507c100…`, 41/41 publisher
  digests matched, independently re-derived with 0 mismatches. **Dates overlap
  the consumed BTC windows; the instrument does not.**
- Forex trio: local checksums only; **ECB publishes no digests**, so the evidence
  does not authenticate the source. Not OHLC.

---

## 8. Acceptance criteria for a future implementation

| # | Criterion |
|---|---|
| A1 | A registry record exists for every instrument in §7 with every mandatory field populated or explicitly `unknown` |
| A2 | `volume_semantics` is populated for every record |
| A3 | `checksum_published` is populated and drives the evidence-strength wording |
| A4 | `governance_stage` matches `RESEARCH_GOVERNANCE.md` for every record |
| A5 | `consumed_windows` correctly marks the spent BTC holdout |
| A6 | Renaming produces an alias, not a new record — proven by test |
| A7 | Delisting produces `RETIRED`, never deletion — proven by test |
| A8 | A discovery run cannot set `research_approved` |
| A9 | No record may be added with a silent source substitution |
| A10 | Every status change is recorded with a timestamp and reason |

---

## 9. Out of scope

- Implementing the registry.
- Fetching any venue's live instrument listing.
- Any eligibility decision about a specific asset.
- Any strategy, parameter or execution change.

---

## 10. Unresolved questions

| # | Question |
|---|---|
| Q1 | What minimum history length qualifies as "meaningful" for screening? Must be preregistered |
| Q2 | How are bridged/wrapped assets distinguished from their underlying in a reproducible way? |
| Q3 | Which venue becomes authoritative when an instrument lists on several? |
| Q4 | Should `consumed_windows` be global or per research-question? |
| Q5 | What retirement period applies before an instrument is archived? |