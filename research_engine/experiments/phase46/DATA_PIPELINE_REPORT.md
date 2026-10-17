# Phase 46 Data Pipeline Report

**Date:** 2026-10-09

---

## 1. Audit findings (46.1)

Inspected before editing: `registry_schema.py`, `dataset_identity.py`,
`dataset.py`, `data.py`, `intervals.py`, `researchguard.py`, `acquisition.py`,
the Phase 33 provenance sidecars, and the Phase 36–45 reports.

### What the pipeline already enforced

Positivity, finiteness, OHLC relationships, ordering, duplicates, optional
interval spacing, timezone consistency, gap classification, declared instrument
identity, volume semantics, and reservation/consumption enforcement. Phase 41
and Phase 45 work was solid and was not redone.

### Gaps demonstrated by probing, not assumed

The decisive method was to mutate the shipped registry and see what was
accepted:

| Probe | Phase 45 behaviour | Meaning |
|---|---|---|
| `checksum_published` deleted | **ACCEPTED** | Whether the publisher issues digests was optional |
| `checksum_published = "maybe"` | **ACCEPTED** | A non-boolean passed |
| `source_url_pattern` deleted | **ACCEPTED** | Origin was not reproducible |
| `source_url_pattern = "not-a-url"` | **ACCEPTED** | Garbage passed |
| `symbol_native = "XXXYYY"` | **ACCEPTED** | Contradicted base/quote |
| `timeframes_available = []` | **ACCEPTED** | Claimed a resolution with no data |
| `quality_status = "excellent"` | **ACCEPTED** | Vocabulary unenforced |
| `dataset_sha256` malformed | **ACCEPTED** | Digest shape unchecked |

Eight fields the Phase 36 spec had proposed were recorded in the file and read
by **no code**. That is the same class of defect Phase 45 found and fixed for
the earlier field set: claims recorded as documentation rather than validated
declarations.

---

## 2. What was implemented

### 2.1 `provenance.py` (new)

Publisher-checksum verification and reproducible manifests.

| Function | Purpose |
|---|---|
| `verify_publisher_checksum` | Compare an archive against the publisher's digest **before** parsing |
| `build_manifest` | Describe a dataset and every input that produced it |
| `verify_manifest` | Re-verify against files on disk; returns all discrepancies at once |
| `write_manifest` | Byte-stable JSON output |

Three design decisions worth stating:

**Verification precedes parsing.** Phase 33's sidecars recorded
`"verified BEFORE the archive was parsed; a mismatch aborts the..."`. That
discipline existed only in a one-off script. Now it is a callable contract.

**Nothing downloads.** A missing file raises. Auto-fetching would turn a
verification step into a network operation with side effects, and would make
tests non-deterministic.

**Reproducible ≠ publisher-verified.** `provenance_ceiling` returns `A` only when
*every* input archive carries a verified publisher digest. A dataset assembled
from unverified files is reported as `B`, because conflating the two would
overstate evidence.

### 2.2 Registry source-provenance validation

Added `_validate_source_provenance`, applied to **every** instrument — not just
consumed ones, since an origin claim matters before any window is spent.

| Check | Refuses |
|---|---|
| `checksum_published` must be a bool | Deletion or `"maybe"` |
| `source_url_pattern` required, http(s) | Missing or non-URL origin |
| `checksum_url_pattern` when digests are published | Unreproducible verification |
| `symbol_native` vs `base_asset`/`quote_asset` | `XXXYYY` for BTC/USDT |
| `symbol_normalized` vs the pair | `BTC/USDT` claiming `ETH/USDT` |
| `instrument_id` vs `symbol_normalized` | Ambiguous reservation target |
| `timeframe` ∈ `timeframes_available` | A resolution with no data |
| Empty `timeframes_available` + declared timeframe | A valid-looking empty instrument |
| `quality_status` vocabulary | `"excellent"` |
| `dataset_sha256` hex shape | Malformed digest |

The symbol checks are the ones with real teeth: **a wrong native symbol is how
one instrument's data gets fetched under another's name**, which is precisely
the failure the registry exists to prevent.

### 2.3 A registry correction found during implementation

The first attempt at Phase 46 filled `source_url_pattern` for the ECB pairs with
the ECB Data Portal URL. The new validation rejected the registry for the forex
entries — and investigation showed the value was wrong, not the check.

Phase 33's manifest records: `Served by: frankfurter.app (open-source API over
ECB data)`. ECB is the **publisher**; frankfurter.app is the **retrieval
endpoint**. The registry now records both, distinctly, via
`retrieval_endpoint` plus a note explaining the distinction.

This is worth recording as process: had the schema been loosened to accept a
plausible URL, the registry would have carried a confident, wrong claim about
how its own data was obtained. Making the field validated surfaced it.

### 2.4 Phase 45 regression: fixtures updated

`_instrument()` in `test_research_guard.py` and `instrument()` in
`test_registry_schema.py` now emit valid provenance fields, using
`example.invalid` — a reserved non-resolvable TLD — so a fixture can never
resemble a real source by accident.

**No assertion was weakened.** The stricter schema is what forced this; the
tests' expectations are unchanged.

---

## 3. Forex — still blocked, deliberately

Phase 46 requested session-aware validation "only where requirements and source
semantics are sufficiently established". They are not, and the components
below were **documented rather than implemented**, because implementing them
from memory would mean inventing a trading calendar and then validating data
against that invention:

| Component | Status |
|---|---|
| UTC normalisation | **Partial** — loader normalises offsets; a trading calendar does not exist |
| Session boundaries (Sydney/Tokyo/London/New York) | NOT IMPLEMENTED |
| Weekend closures | NOT IMPLEMENTED |
| Holiday calendars per pair | NOT IMPLEMENTED |
| DST transitions | NOT IMPLEMENTED |
| Missing bar vs legitimate closure | **NOT RESOLVABLE** without the above |
| Price precision / pip definition | NOT IMPLEMENTED |
| Bid/ask and spread | NOT IMPLEMENTED — no source supplies them |
| Tick vs central volume | Vocabulary exists; no forex source provides either |

Three independent blockers, unchanged from Phase 41:

1. **No OHLC data.** An ECB reference rate is one published fixing per day. There
   is no `high` or `low` because no intraday range occurred at that fixing.
   Converting it to OHLC would fabricate the volatility a strategy trades on.
2. **No session/DST validator.**
3. **No licensed tick or bar source.**

ECB daily reference rates are **not** converted to hourly OHLC. No candle is
synthesised. No spread is inferred.

---

## 4. Common data contract

| Concern | Where it lives |
|---|---|
| Instrument identity, timeframe, volume semantics | `dataset_identity.DatasetIdentity` |
| OHLCV validity, ordering, timestamps | `dataset.validate_dataset` |
| Declared-vs-actual binding | `validate_dataset(identity=…)` |
| Interval gaps (24×7 crypto) | `intervals.classify_intervals` |
| Source provenance, digests, manifests | `provenance` |
| Registry metadata coherence | `registry_schema` |
| Reservation and consumption | `researchguard` |

Market-specific differences are preserved rather than flattened:
`timestamp_convention` distinguishes `bar_opens_at_hour_utc` from
`instantaneous_fixing`; `volume_semantics` distinguishes `central_base` from
`tick` from `none`; `timeframes_available` is empty for blocked instruments
whose sources serve no bar data.

**Integrity validation is separate from research approval.** A dataset can pass
every check and an instrument can remain `NOT_APPROVED`. Discovery and
successful parsing never approve anything —
`test_clean_parsing_does_not_approve` asserts this.

Validation fails closed on malformed identity, invalid OHLC, incompatible
timeframe, invalid timestamps, and contradictory metadata.

---

## 5. Tests

`tests/test_data_pipeline.py` — **66 tests**, all passing.

| Area | Coverage |
|---|---|
| Publisher checksums | verified, mismatch, quarantine mode, malformed digest, missing file, no-download |
| Manifests | real digest, tamper detection, attribution required, provenance ceiling, archive discrepancies, byte-stable round-trip, version guards |
| Registry provenance | all 10 checks in §2.2 |
| Venue differences | two venues, different native symbols, both valid |
| Timeframe binding | declared vs actual spacing |
| Volume semantics | tick ≠ central, crypto cannot declare `none` |
| Intervals | duplicates, gaps, contiguous slice, no mutation |
| Forex | identity refused, interval refused, approval refused, fixings not OHLC, spread not synthesised |
| Discovery | parsing does not approve |
| Guards | reservation unspent, hash unchanged, refusal intact |

Combined focused run: **328 passed** (pipeline + registry + guard + validation).

Two tests read the real ETH dataset, asserting **only** row count, endpoint
timestamps, and digest — never a price.

---

## 6. Verdict

**PASS.**

Provenance became load-bearing rather than descriptive. The pipeline now
requires venue identity, source URL, checksum availability, symbol coherence,
and a reproducible manifest, and refuses eight classes of contradictory metadata
that previously passed.

Forex remains blocked on documented grounds, with no session rules invented and
no ECB data converted.

The ETH reservation was not touched and no ETH 2026 performance was computed or
inspected.