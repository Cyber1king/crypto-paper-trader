# Phase 38 — Data Validation Design

**Status: DESIGN ONLY. No code, dataset or validator was modified. The test suite
was inspected but deliberately NOT executed**, because it runs backtests
internally.

---

## 1. Current coverage — verified by reading source

### 1.1 `dataset.validate_dataset` — six assertions

Read directly from `research_engine/src/crypto_paper_lab/dataset.py:33-72`:

| # | Assertion | Line |
|---|---|---|
| 1 | dataset contains no candles | ~37 |
| 2 | invalid high/low range (`high >= low`) | ~41 |
| 3 | invalid open price (`low <= open <= high`) | ~50 |
| 4 | invalid close price (`low <= close <= high`) | ~59 |
| 5 | negative volume | ~64 |
| 6 | timestamps strictly increasing | ~70 |

It is a **structural sanity check, not a market-data contract.**

### 1.2 Layered coverage across the codebase

| Layer | What it checks | What it misses |
|---|---|---|
| `dataset.validate_dataset` | 6 structural assertions | interval spacing, price positivity, finiteness, identity, sessions |
| `acquisition._check_row` | **price positivity**, hour alignment, OHLC, volume ≥ 0, `finite` | sessions, identity, volume semantics |
| `acquisition.normalize_source` | adds research-window overlap (2024–2025 only), duplicates, out-of-order, missing hours | any registry; bypassable by keyword |
| `walkforward.validate_dataset_integrity` | count, edges, 3600 s spacing, **SHA-256**, duplicates | **hard-wired to BTC 2024–2025 constants** |

### 1.3 A structural blocker for ETH

`walkforward.validate_dataset_integrity` defaults to
`expected_sha256=DATASET_SHA256` and `expected_count=DATASET_CANDLES` —
constants pinned to `data/BTCUSDT_1h_Cleaned (1).csv`
(`walkforward.py:51-57`, `:257-262`).

**It cannot validate ETH without explicit overrides.** Reusing it as-is would
reject a correct ETH dataset.

### 1.4 Test coverage — inspected, not run

| File | Test functions | Relevant coverage |
|---|---|---|
| `test_acquisition.py` | 27 | positivity, volume, overlap |
| `test_walkforward.py` | 58 | interval, overlap |
| `test_oos_dataset.py` | 18 | interval |
| `test_validation_boundary.py` | 13 | — |
| `test_dataset.py` | **3** | **none of the above** |

**No test anywhere covers instrument/timeframe identity or volume semantics.**
`test_dataset.py` has only 3 test functions for the primary loader — thin
coverage for a file every dataset passes through.

---

## 2. Proposed safeguards

### 2.1 Positive OHLC prices

**Gap:** `dataset.py` checks containment but not positivity. A row
`0,0,0,0` satisfies `high >= low` and both containment checks.
`acquisition._check_row` **does** enforce positivity, so the gap exists **only on
the `project_native` load path**.

| # | Proposal |
|---|---|
| V1.1 | Add an explicit `price > 0` check for open, high, low, close in `validate_dataset` |
| V1.2 | Add an explicit **finiteness** check — `inf` currently satisfies `high >= low` |
| V1.3 | Both **raise**, consistent with the existing fail-closed style |
| V1.4 | Align `dataset.py` with `acquisition._check_row` so the two layers cannot diverge |

### 2.2 OHLC relationships

Present, but worth pinning explicitly rather than incidentally.

| # | Proposal |
|---|---|
| V2.1 | Assert `high >= low`, `low <= open <= high`, `low <= close <= high` — already present, keep |
| V2.2 | Assert `high >= max(open, close)` and `low <= min(open, close)` **explicitly**; the current containment tests imply them but do not state the intent |
| V2.3 | Reject non-finite values before any comparison (a NaN fails every ordering silently) |

### 2.3 Timestamp ordering, duplicates and interval spacing

| # | Proposal |
|---|---|
| V3.1 | Strictly increasing — present, keep |
| V3.2 | Explicit **duplicate** rejection as a distinct error from out-of-order |
| V3.3 | **Interval spacing must move into `validate_dataset`** as an expected-interval parameter. Today it exists only in `acquisition` (`missing_hours`) and `walkforward` |
| V3.4 | Spacing must be **market-aware** — see §2.6; for 24×7 crypto any deviation is an anomaly |
| V3.5 | Assert every stamp is on the interval boundary (hour alignment). Present in `acquisition`, absent from `dataset` |

### 2.4 Instrument and timeframe identity

**The largest gap after sessions.** Nothing anywhere validates that a dataset
matches a declared instrument or timeframe.

Verified: `StrategyConfig.asset` is a **label**; the only non-declaration use is
`replay.py:363`, which passes it into the replay context. Combined with the
strategy being scale-invariant, **an ETH dataset labelled BTC would run silently**.

| # | Proposal |
|---|---|
| V4.1 | Datasets must carry `instrument_id`, `market_type`, `timeframe` and `venue` metadata, and `load_ohlcv_csv` must return or accept them |
| V4.2 | A loader used with a `StrategyConfig` must **verify** `asset` matches, or an explicit override must be recorded |
| V4.3 | `timeframe` must match the data's actual interval — a 1h config on daily data is currently undetectable |
| V4.4 | Mismatch must **raise**. Defaulting silently to the config label is precisely the failure this prevents |
| V4.5 | The Phase 37 finding must be resolved explicitly at preregistration time: the ETH run has `asset="BTC/USDT"` on ETH data, so V4.2 **cannot** be enabled without first deciding how the label is handled |

**V4.5 is a genuine tension:** enforcing identity would block the ETH experiment
as currently drafted, because the frozen config says BTC/USDT. That must be
decided, not silently bypassed.

### 2.5 Missing-data classification

| # | Proposal |
|---|---|
| V5.1 | Every absent interval must be classified `legitimate_closure` or `anomaly`, with a reason |
| V5.2 | `anomaly` **raises**; `legitimate_closure` does not |
| V5.3 | Classification must be **recorded**, so a later reader can distinguish "closed" from "unknown" |
| V5.4 | **No gap may ever be filled.** `acquisition` already reports rather than repairs, and that must not change |

### 2.6 Market-specific session rules

**Absent entirely.** Verified this phase: `acquisition.py` has no session,
holiday, weekend or DST logic; `\bdst\b` has **zero occurrences** across `src`;
the only "session" is `session.py:154`, a paper-trading session object.

| # | Proposal |
|---|---|
| V6.1 | A **session calendar** per market type: venue sessions, breaks, weekly closure, holidays |
| V6.2 | **DST transition handling.** Session boundaries shift; naive UTC+hour assumptions break. This is the single largest engineering gap |
| V6.3 | A gap classifier that consults the calendar before labelling a gap anomalous |
| V6.4 | Crypto 24×7 requires **no** calendar — any gap is anomalous |
| V6.5 | Forex must **fail closed** until a calendar exists: absent a calendar, absences cannot be classified, so they must raise |
| V6.6 | Bar-boundary convention recorded per instrument |

### 2.7 Volume semantics

**Never declared, never enforced.** Phase 33 recorded the rule that tick volume
must not be represented as centralised exchange volume — but it is documentation,
not code.

| # | Proposal |
|---|---|
| V7.1 | `volume_semantics` becomes a **mandatory** dataset field |
| V7.2 | Enum: `central_base` \| `central_quote` \| `tick` \| `none` |
| V7.3 | Datasets with undeclared semantics **must not load** for research use |
| V7.4 | `none` must be representable without a fabricated zero series |
| V7.5 | Cross-venue volume comparison must **refuse** unless semantics match |
| V7.6 | A tick-volume dataset must carry that label in its manifest **and** its registry record |

### 2.8 Consistency between configured asset and dataset identity

Overlaps §2.4 but is stated separately because it is the specific defect found in
Phase 37.

| # | Proposal |
|---|---|
| V8.1 | `run_backtest` and `run_window` must accept an expected dataset identity and verify it |
| V8.2 | Mismatch **raises**; there is no permissive default |
| V8.3 | The comparison must be by **stable instrument id**, not by display string — `BTC/USDT` vs `ETHUSDT` vs `ETH/USDT` must not compare equal |
| V8.4 | An explicit override must be a **preregistered, recorded** decision, never an ad-hoc flag |
| V8.5 | The dashboard must display the resolved identity so a mismatch is visible, not silent |

### 2.9 Distinguishing "not checked" from "checked and clean"

The trap demonstrated in Phase 38 inspection: `normalize_source(...,
allow_overlap_with_research=True)` leaves `overlapping_rows == []`, which reads
as a pass but means the check never ran. All 41 Phase 33 archives show `[]` while
17,544 rows genuinely overlap the consumed BTC window.

| # | Proposal |
|---|---|
| V9.1 | A bypass must be **recorded as a bypass**, never as an empty result |
| V9.2 | Reports must distinguish `checked_clean`, `checked_found`, and `not_checked` |
| V9.3 | A result with `not_checked` anywhere must be visibly non-compliant |

---

## 3. Priority ordering

| Rank | Safeguard | Why first |
|---|---|---|
| **1** | V4.4 / V8.2 — asset–dataset identity | A mislabelled or wrong-instrument run is currently undetectable |
| **2** | V5.1–V5.3 — gap classification + session calendar | Blocks all forex work |
| **3** | V7.1–V7.3 — volume semantics mandatory | Blocks cross-venue comparison; FX specifically |
| **4** | V9.1–V9.3 — bypass visible | Anti-reuse signals are currently ambiguous |
| **5** | V3.3 — interval spacing in `validate_dataset` | Currently only in two other layers |
| **6** | V1.1–V1.2 — positivity and finiteness | Small, clear correctness gap |
| **7** | `walkforward.validate_dataset_integrity` generalisation | Hard-wired to BTC constants |

---

## 4. Integrity approval remains separate from research approval

Implementing **every** safeguard in this document would make a dataset
*integrity-complete*. It would still **not** authorise evaluation.

`RESEARCH APPROVED` additionally requires a preregistered question, fixed
thresholds, a **reserved and enforced** window, confirmed scope, and a formal
governance record.

**The strongest temptation this design creates is treating "all safeguards
green" as "ready to evaluate". It is not.**

---

## 5. Out of scope for this phase

No code, test, dataset or validator was modified. No safeguard was implemented.
The test suite was inspected but not executed.