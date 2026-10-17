# Phase 38 — Holdout-Reuse Enforcement Design

**Status: DESIGN ONLY. No mechanism was implemented.**

> ## The reserved window is NOT technically protected
>
> As of this document there is **no code** that would prevent anyone from running
> the ETH 2026 window, or the spent BTC holdout, a second time. Protection today
> is documentary: a sentence in a report and a section in this file.
>
> This document specifies what must exist before the phrase *"reserved"* can be
> used honestly.

---

## 1. What exists today — verified this phase

| Finding | Evidence |
|---|---|
| `run_backtest` performs **no** hash, registry, consumption or reservation check | `backtest.py` contains no `sha256`, `consumed`, `reservation` or `registry` reference |
| `normalize_source`'s **only** anti-reuse guard is hard-coded 2024–2025 | `acquisition.py:54-55`, `:396-399` |
| That guard is **bypassable by a keyword argument** | `allow_overlap_with_research: bool = False` (`acquisition.py:318`) |
| `consumed_windows` **does not exist in code** | No registry module exists anywhere |
| `evaluation_start` gates **entries only**, correctly | `backtest.py:199` |

### 1.1 Nine dataset entry points could move data into a backtest

| # | Entry point | Location |
|---|---|---|
| 1 | `run_backtest` | `backtest.py:65` |
| 2 | `walk_forward` | `walkforward.py:585` |
| 3 | `run_window` | `walkforward.py:465` |
| 4 | `validate_dataset_integrity` | `walkforward.py:257` |
| 5 | `load_ohlcv_csv` | `data.py:25` |
| 6 | `load_dataset` | `dataset.py:17` |
| 7 | `validate_dataset` | `dataset.py:33` |
| 8 | `normalize_source` | `acquisition.py:315` |
| 9 | **`load_research_candles`** | `paper_api/marketdata.py:61` |

Entry 9 is easy to miss: an **API-layer loader** outside `crypto_paper_lab`. A
guard placed only in the library would be bypassed by anything calling the API
surface.

---

## 2. A latent trap already present: the silent-bypass pattern

`normalize_source(..., allow_overlap_with_research=True)` **skips** the guard
entirely, leaving `report.overlapping_rows == []`.

Verified in the Phase 33 ETH acquisition log: **all 41 archives record
`overlapping_rows: []`** — yet ETH 2024–2025 shares **17,544 bars** with the
consumed BTC research window.

**An empty list is ambiguous.** It means either "checked, none found" or
"check disabled". A reader of the Phase 33 log would reasonably conclude no
overlap exists. It does.

Phase 33 made the correct call — different instrument, so the guard should not
apply — and the manifest does disclose the overlap in §4. But the *machine-readable
log* does not, and the log is what tooling reads.

**Design consequence:** any enforcement must distinguish **checked-and-clean**
from **not-checked**, and the bypass must be recorded rather than leaving an
empty result that reads as a pass.

---

## 3. The reservation to be registered

| Field | Value |
|---|---|
| `instrument_id` | `ETH/USDT` (registry key) |
| `source_dataset` | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| `dataset_sha256` | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| `timeframe` | `1h` |
| `warmup_first` | `2024-01-01 00:00:00` UTC |
| `warmup_last` | `2025-12-31 23:00:00` UTC |
| `warmup_bars` | 17,544 (indices 0–17,543) |
| `eval_first` | `2026-01-01 00:00:00` UTC |
| `eval_last` | `2026-10-08 23:00:00` UTC |
| `eval_bars` | 6,744 (indices 17,544–24,287) |
| `evaluation_start_index` | **17,544** (verified this phase) |
| `status` | `RESERVED — UNUSED` |
| `preregistration_id` | **unset** — must be set before the run |

### 3.1 Timestamp inclusivity

- All ranges are **inclusive** of both endpoints.
- Stamps are **naive UTC**, matching the repository's `CANONICAL_DATE_FORMAT`
  (`acquisition.py:47`) and `load_ohlcv_csv` behaviour. No tz-aware comparison
  is performed anywhere today.
- The boundary bar `2026-01-01 00:00:00` is the **first evaluable** bar and is
  included in the evaluation range.
- The warm-up bar `2025-12-31 23:00:00` is the **last warm-up** bar and may not
  open a position.

### 3.2 Missing candles and incomplete final periods

| Situation | Rule |
|---|---|
| Missing bar inside the warm-up range | **Invalidates the reservation.** `WARMUP_RULE = full_preceding_series` requires an unbroken series; a gap would silently change indicator state |
| Missing bar inside the evaluation range | **Invalidates the reservation.** Currently there are 0 gaps; a future gap must not be filled |
| Dataset ends mid-period | Already the case: data stops at `2026-10-08 23:00`, a complete hour but an incomplete month. `end_of_data` force-close applies and **must be retained**, not discarded (`backtest.py:207-213`, `walkforward.py:21-22`) |
| New data published after `2026-10-08` | **Not automatically added.** Extending the dataset changes its digest and invalidates the reservation; a new reservation is required |

---

## 4. Conditions that invalidate the reservation

Any one of these voids it. A new reservation must be registered before evaluation.

| # | Condition |
|---|---|
| V1 | Dataset SHA-256 differs from `7507c100…` |
| V2 | Row count, first or last timestamp differs |
| V3 | Any gap, duplicate, or ordering violation appears |
| V4 | `evaluation_start` is anything other than 17,544 |
| V5 | The preregistration digest does not match the registered one |
| V6 | The evaluation range was evaluated under *any* prior experiment |
| V7 | Any ETH 2024–2025 performance figure was computed (warm-up becomes consumed) |
| V8 | The preregistration is absent or not frozen |
| V9 | The instrument, timeframe or execution assumptions differ from registration |
| V10 | The registry record is missing or inconsistent |

**V7 deserves emphasis.** If ETH 2024–2025 is ever explored for behaviour, it
stops being warm-up context and becomes consumed data. The reserved window then
sits behind a configuration that may have been adjusted using it, and the
reservation must be abandoned.

---

## 5. Enforcement design — not implemented

### 5.1 Reservation record

A single machine-readable record per reservation, holding the §3 fields plus
`status`, `preregistration_id`, `preregistration_sha256`, and a monotonic
`run_history` that is **append-only**.

`run_history` must record every evaluation attempt, including **refused** ones.
A refusal that is not recorded can be repeated silently.

### 5.2 Guard placement — must cover every path

The guard cannot live in one function, because nine entry points exist and one of
them (`load_research_candles`) is outside the core package.

| Layer | Placement | Purpose |
|---|---|---|
| **G-a Primary** | A single `assert_evaluation_permitted(dataset_sha256, instrument_id, eval_first, eval_last, preregistration_id)` called at the **top of `run_backtest`, `walk_forward` and `run_window`** | No backtest can start without passing |
| **G-b Secondary** | A **pytest marker/guard** that fails any test declaring `evaluation_start` against a reserved range without registering a run | Catches the "just a quick test" path |
| **G-c API surface** | An assertion in `paper_api.marketdata.load_research_candles`, or a rule that the API refuses to serve a reserved range | Closes the non-library path |
| **G-d Reporting** | Every results artifact must carry `dataset_sha256`, `reservation_id`, `preregistration_sha256` | Makes an undeclared run detectable after the fact |

**G-d matters because G-a–G-c are all bypassable by someone editing code.** The
report-level requirement makes an undeclared run *visible* even then.

### 5.3 Fail-closed behaviour

The single most important property.

| Situation | Required behaviour |
|---|---|
| Reservation record missing | **RAISE** |
| Reservation record malformed or unparseable | **RAISE** |
| Dataset digest does not match the reservation | **RAISE** |
| Range or instrument mismatch | **RAISE** |
| Preregistration absent, or digest mismatch | **RAISE** |
| Status already `EVALUATED` | **RAISE** |
| Registry unavailable or unreadable | **RAISE** — never fall back to permissive |
| Any metadata field unknown or null | **RAISE** |

**"Unknown" must never be treated as "allowed".** A missing guard is not a
pass.

### 5.4 Warm-up and scored observations kept separate

| Requirement | Mechanism |
|---|---|
| Warm-up contributes no trades | Already enforced by `evaluation_start` on entries (`backtest.py:199`) |
| Pre-boundary trades must be impossible to miss | Assert at run end that **every** trade has `entry_time >= eval_first`; raise otherwise. `walkforward.run_window` already does this for its own windows (`:513-523`) but **not for a bare `run_backtest`** |
| The scored set must be explicit | Results must report evaluation-range trades and warm-up-range trades as **separate counts**, warm-up expected to be 0 |
| Indicators may legitimately see warm-up | Not a violation. Warm-up feeds `analyze(candles[:index])` by design |

### 5.5 Recording identity

Every evaluation must bind, immutably:

`dataset_sha256` + `instrument_id` + `timeframe` + `eval_first`/`eval_last` +
`evaluation_start_index` + `config_hash` + `costs_hash` + `preregistration_sha256`
+ `git_commit` + `timestamp` + `outcome`

Reuse of the existing `_stable_hash` scheme (`walkforward.py:424-442`) is
preferred over inventing a new one.

---

## 6. Consumption recording

| Event | Effect |
|---|---|
| Evaluation **runs** | `status = EVALUATED`; window appended to `consumed_windows` |
| Evaluation **refused** | Attempt logged; status unchanged |
| Window registered | `consumed_windows` unchanged until a run occurs |
| ETH 2024–2025 explored for behaviour | Warm-up designation revoked; reservation invalid per V7 |

**The spent BTC holdout** must be registered as permanently consumed, with
`phase30/SUMMARY.md:343` as the provenance of that status.

---

## 7. Sequencing — enforcement before evaluation

```
  P1  Registry exists (Phase 36 P3)
   ↓
  P2  Reservation record created for ETH 2026 + BTC holdout retired
   ↓
  P3  Guard implemented at run_backtest / walk_forward / run_window  (G-a)
   ↓
  P4  Test-suite guard (G-b) and API guard (G-c)
   ↓
  P5  Report-level provenance requirement (G-d)
   ↓
  P6  Only THEN may a preregistration be frozen and a run considered
```

**The reservation may be *declared* before P3, but must not be described as
*protected* until P3 exists.** Declaring intent and enforcing it are different
claims, and only the second survives contact with a well-intentioned mistake.

---

## 8. Out of scope for this phase

Implementing any part of this design, creating the registry or reservation,
modifying any guard, running anything, or freezing any preregistration.