# Phase 39 Implementation Report: Research Integrity Guards

**Status:** COMPLETE
**Date:** 2026-10-09
**Scope:** Technical safeguards for evaluation-window reservation, instrument identity, overlap reporting and dataset validation.

Phase 38 left two problems documented but unenforced: the ETH 2026 evaluation
window was protected only by prose, and `StrategyConfig.asset` was an unchecked
label. This phase makes both refusals executable.

---

## 1. What was built

A single enforcement module, plus a registry it reads, wired into the four
places that can start an evaluation.

| File | Status | Purpose |
|---|---|---|
| `src/crypto_paper_lab/researchguard.py` | new | Fail-closed guards; performs no calculation |
| `data/research_registry.json` | new | Instrument identities, reservations, consumed windows |
| `src/crypto_paper_lab/dataset.py` | modified | Positivity, finiteness, optional interval/identity checks |
| `src/crypto_paper_lab/backtest.py` | modified | Guard gate in `run_backtest` |
| `src/crypto_paper_lab/walkforward.py` | modified | Context propagation through `run_window` / `walk_forward` |
| `src/crypto_paper_lab/acquisition.py` | modified | Explicit overlap-check status |
| `src/paper_api/marketdata.py` | modified | Range guard on the API data path |
| `tests/test_research_guard.py` | new | 91 tests |

### Registry

`data/research_registry.json` declares five instruments, one reservation and
three consumed windows:

- `BTC/USDT` — `RESEARCH_CONSUMED`
- `ETH/USDT` — reserved 2026, **not approved**
- `EUR/USD`, `GBP/USD`, `USD/JPY` — ECB daily reference rates, `volume_semantics: "none"`, blocked

The three forex entries declare `"volume_semantics": "none"` because no volume
exists in that source. Absence is stated rather than filled with a guess.

---

## 2. Enforcement

### Fail closed

A missing, unreadable, malformed or incomplete registry raises
`ResearchGuardError` (a `RuntimeError`, deliberately, so it cannot be swallowed
by a broad `except ValueError`). There is no permissive fallback and no
"unknown means allowed" path. `load_registry` validates that all four required
sections exist and are lists.

### Identity is the dataset hash, not the path

A byte-identical copy has the same identity, so copying a reserved file to a new
name cannot evade its reservation. Verified by
`test_byte_identical_copy_shares_identity`.

### Consumed windows are permanent

`test_shipped_registry_records_spent_holdout` re-hashes the Phase 29 holdout on
disk and asserts that attempting an evaluation against it raises. The BTC primary
dataset and Phase 10/11 OOS window are likewise recorded as consumed.

### Reserved windows are spent once, durably

`mark_used` defaults to `True`. Consumption is written to the registry file
before the run proceeds, via a temp file plus `os.replace` so a crash cannot
leave a half-written registry. The file is re-read from disk immediately before
editing, so a stale in-memory copy cannot clobber it.

Two refusal cases here were found and fixed during implementation:

- **Consumption was not enforced.** The parameter existed but did nothing, so
  "evaluated once only" was not a real guarantee. Now enforced, and refusing to
  evaluate when there is no file to record into.
- **A stale registry copy could re-run a spent window.** When `registry_file` is
  named it is now authoritative for the decision, regardless of `mark_used`.
  The in-memory object is updated after a successful write.

### Evaluation range must be declared and must match

A caller cannot dodge the guard with `evaluation_start=None` and trade the whole
series. Narrowing, widening, starting early, overrunning, or trading only inside
warm-up are each refused separately
(`test_narrowed_evaluation_range_refuses` through
`test_warmup_only_window_does_not_grant_evaluation`).

Warm-up separation is additionally asserted against real trades in
`test_engine_never_trades_during_warmup`.

### Cross-asset transfer must be explicit

`StrategyConfig.asset` remains `"BTC/USDT"` and was not rewritten. Running that
config against ETH data raises `instrument transfer refused` unless a
`CrossAssetAuthorization` is supplied that names *this* pair. Authorization for
the wrong pair, an incomplete record, or a malformed type all raise. Mismatches
are never resolved by relabelling data or config.

### No bypass flag

`test_no_bypass_flag_exists` asserts `run_backtest` exposes no `skip_guard`,
`ignore_guard`, `unsafe`, `allow_reserved`, `bypass_guard`, `force` or
`disable_guard` parameter.

### Overlap status is stated, never implied

This was a real defect: `allow_overlap_with_research=True` left
`overlapping_rows=[]` while 17,544 date-overlapping bars were in fact present.
All 41 Phase 33 ETH archives carry that ambiguous empty list.

`AcquisitionReport.overlap_check` now records `checked` / `skipped` / `failed`
and **defaults to `failed`** — a report that never states an outcome is
non-compliant, not a pass. Every report gains a note, and a bypassed check says
`NOT verified` rather than implying a clean result.

### Dataset validation

`validate_dataset` now rejects non-finite and non-positive prices. The
non-positive check is explicit because a zero price satisfies every ordering
comparison; `inf`/`nan` are checked separately because `inf >= inf`.

Optional, because candles alone cannot supply them:

- `expected_interval_seconds` — exact spacing
- `market_type` — refuses anything with no implemented validator
- `instrument_id` / `timeframe` — must be supplied together when declared

Forex stays refused: no session, holiday or DST validator exists here.
`test_ecb_reference_rates_fail_hourly_ohlc_validation` confirms daily reference
rates cannot pass as hourly candles.

---

## 3. ETH 2026 remains unapproved

**No ETH 2026 performance was produced, inspected or compared.** The shipped
reservation has `status: "RESERVED"`, `used: false`,
`preregistration_id: null`. `test_shipped_registry_keeps_eth_unapproved` asserts
all three and that an attempted evaluation raises
`no registered preregistration_id`.

Every engine-level test runs against a synthetic `SYNTH/TEST` instrument on a
synthetic 2023 window, so no engine execution touched data reserved or consumed
for real research.

---

## 4. Test results

| Scope | Result |
|---|---|
| `test_research_guard.py` | **91 passed** |
| `dataset` / `backtest` / `walkforward` / `acquisition` | **90 passed** |
| Full suite, all 37 files | **2059 passed, 0 failed** |

Two baseline runs were used to separate pre-existing slowness from regressions:

- `test_high_risk.py` — 476 s current vs 473 s at pristine `HEAD`; 286 passed
  both ways. Slow before Phase 39, unchanged by it.
- `test_replay.py` (138 s) and `test_phase14c_analysis.py` (193 s) are long by
  design; both pass fully.

An earlier apparent "hang" was a 15-minute command timeout, not a failure. No
test was killed mid-run in the final accounting.

`test_phase14c_analysis.py` and `test_replay.py` do execute `run_backtest` and
`walk_forward` over the BTC primary dataset. That is pre-existing engine
coverage, unrelated to research evaluation: they exercise execution mechanics and
assert on trade mechanics. They assert nothing about the ETH window and produce
no research result.

---

## 5. Scope and limits

What this does **not** do:

- Does not approve, freeze or run the ETH 2026 evaluation.
- Does not resolve Phase 38's open question or its unresolved thresholds.
- Does not add an AI provider.
- Does not implement forex session/holiday/DST validation.
- Does not alter any frozen artifact.

Residual limitation, stated plainly: enforcement is **opt-in by declaration**.
`run_backtest` without a `research_context` behaves exactly as before, which is
what keeps development and the existing suite working. A caller who evaluates
protected data while deliberately omitting the context is outside what this
module can prevent — the registry cannot know it was never asked. Closing that
would require making every engine call declare identity, which would break
ordinary development use. It is a deliberate trade-off, not an oversight.

The API path is guarded separately by `assert_no_registered_range`, since it
serves one fixed dataset and is otherwise the easiest loader to bypass.

---

## 6. Verification

Frozen artifacts re-hashed after all changes, all unchanged:

| Artifact | SHA-256 |
|---|---|
| BTC primary | `201a3b15…ba016b` |
| BTC holdout (spent) | `c475e541…f99b` |
| Phase 29 preregistration | `b06f36e2…17cc` |
| ETH dataset | `7507c100…deeb` |

Git: no commit, stage or push made. Nothing deleted.

**Phase 39 complete.**