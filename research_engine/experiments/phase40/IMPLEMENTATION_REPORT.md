# Phase 40 Implementation Report: Close Research Enforcement Gaps

**Verdict: PASS**

**Date:** 2026-10-09
**Scope:** Verify the Phase 39 report against the code, then close the omission bypass it documented.

Phase 39 closed with an honest PARTIAL-shaped gap: `run_backtest` without a
`research_context` behaved exactly as before, so a caller could bypass research
governance by omitting the context. This phase closed it.

---

## 1. Verification of the Phase 39 report

The Phase 39 report was **accurate**. Independently confirmed before changing
anything:

| Claim | Verified |
|---|---|
| `researchguard.py`, `research_registry.json`, `test_research_guard.py` exist | Yes |
| 5 source files modified, 174 insertions | Yes, exactly |
| Nothing staged, `HEAD == origin/main`, 0 ahead/behind | Yes |
| ETH reservation `RESERVED` / `used: false` / `preregistration_id: null` | Yes |
| Frozen artifact hashes unchanged | Yes |
| Guard wired into `run_backtest`, `run_window`, `walk_forward`, `marketdata` | Yes |

One reported behaviour was **misleading rather than wrong**, and is fixed below:
the `marketdata` guard called `assert_no_registered_range(allow_consumed=True)`,
which *returns* a list of hits. Nothing read it. The comment said the run was
"refused"; nothing was refused.

---

## 2. Entry-point inventory

Audit only — no entry point was executed during this step.

| # | Entry point | Executes strategy | Context param (Phase 39) | Guard now |
|---|---|---|---|---|
| 1 | `backtest.run_backtest` | yes | yes | `assert_series_permitted` |
| 2 | `walkforward.run_window` | yes | yes | forwards to #1 |
| 3 | `walkforward.walk_forward` | yes | yes | forwards to #2 |
| 4 | `experiment.run_experiment` | yes | **no** | guard added, context plumbed |
| 5 | `yearly.run_yearly_backtests` | yes | **no** | guard added, context plumbed |
| 6 | `replay.Replay.__init__` | yes (stepwise) | **no** | guard added |
| 7 | `walkforward.validate_dataset_integrity` | no | no | `assert_dataset_not_reserved` added |
| 8 | `paper_api.marketdata.load_research_candles` | no | no | decision now actually recorded |
| 9 | `dataset.load_dataset` / `load_ohlcv_csv` / `validate_dataset` | no | no | validation only, by design |
| 10 | `acquisition.normalize_source` | no | no | overlap status explicit |

Gaps 4, 5, 6 were the real holes: three independent paths to strategy execution
with no guard at all.

---

## 3. Closing the omission bypass

### The problem

The guard only ran when the caller supplied a context. The engine is handed
`Candle` objects and is never told which file they came from, so a caller could
load ETH 2026, call `run_backtest(candles)` with no context, and the engine had
no way to know what it was holding.

### The fix: identify the series, not the declaration

`assert_series_permitted` fingerprints the candles actually passed in, and runs
**before** anything is conditioned on context presence. Omitting the context is
no longer a way to stay unchecked.

Three layers, because whole-series matching alone was not enough:

1. **Whole-series fingerprint** — catches a byte-identical copy.
2. **Evaluation-slice fingerprint** — catches the 6,744 evaluation bars alone.
3. **Per-bar index** (`researchindex.py`) — catches arbitrary sub-slices.

The third layer was necessary. Probing showed a mid-series chunk of 4,000 bars
passed layers 1 and 2: it is neither the whole dataset nor the evaluation slice.

### The per-bar index

`data/research_registry.candle_index.json` holds a 32-hex-char SHA-256 prefix per
bar for every protected window (1.9 MB, machine-only). A series is treated as
protected when **at least half** its bars are registered, with a floor of three
bars.

Threshold rather than any-hit, deliberately: one coincidentally identical
synthetic candle must not make an unrelated dataset look protected.

Kept in a sidecar rather than the registry so the registry stays a 5.8 KB
human-reviewable document.

### Probe results — data-level only, no strategy execution

| Series | Bars | Result |
|---|---|---|
| ETH full dataset | 24,288 | **REFUSED** |
| ETH evaluation slice | 6,744 | **REFUSED** |
| ETH mid-chunk (spans warm-up → eval) | 4,000 | **REFUSED** |
| ETH 5-bar slice | 5 | **REFUSED** |
| ETH evaluation tail | 100 | **REFUSED** |
| ETH warm-up head | 100 | **REFUSED** |
| ETH evaluation slice, reversed | 6,744 | **REFUSED** |
| ETH evaluation, every-other-bar | 3,372 | **REFUSED** |
| Synthetic series dated 2026 | 60 | PERMITTED (correct) |

The last row matters: an earlier iteration refused on **date overlap** alone,
which broke legitimate synthetic fixtures and protected nothing. Dates are not
identity. `test_reserved_dates_alone_do_not_refuse_synthetic` pins the corrected
behaviour so date-matching cannot creep back in.

### An error worth recording

That date-based version was wrong and I shipped it into the codebase before
testing caught it. Four test files failed immediately. The correction was to
match content, not dates — not to weaken the tests.

---

## 4. Persistence safety

| Requirement | Status |
|---|---|
| Registry file authoritative when configured | Fixed — a stale in-memory copy cannot authorise a spent window |
| `mark_used` cannot silently do nothing | Enforced; refuses with no file to record into |
| Writes atomic | `mkstemp` + `os.replace`; verified no temp files left |
| Failed persistence prevents proceeding | Verified — reservation absent ⇒ nothing written |
| Reservation changes auditable | `used`, `used_on`, `used_preregistration_id` recorded |
| Hash, identity, timeframe, boundary, preregistration checked | Yes |

### Consumption moved out of the check

Phase 39 had `mark_used=True` by default, spending the reservation inside the
guard call. That was wrong for a reason worth stating: a crash *after* the guard
but *before* a result would consume a window that produced nothing.

Now `assert_series_permitted(..., mark_used=False)` by default, and consumption
is a separate explicit `consume_reservation(...)` call after a successful run.
**An evaluation spends a window; an attempt does not.**

Pinned by `test_failed_run_does_not_consume_the_reservation`.

---

## 5. Overlap status

`AcquisitionReport.overlap_check` defaults to `failed`, so a report that never
states an outcome is non-compliant rather than an implied pass. A bypassed check
records `skipped` and a note reading `NOT verified`.

`test_skipped_is_distinct_from_checked` fixes the exact Phase 33 defect: two
reports both with empty `overlapping_rows`, only one a real pass.

---

## 6. Two allowlists extended — not relaxed

Two architectural tests failed because `researchguard` was not on their
allowlists. Both were **extended with an explicit entry and a written
justification**, not weakened:

- `tests/test_api_health.py` — `ALLOWED_ENGINE_IMPORTS`
- `tests/test_replay.py` — `engine_modules`

Both entries state that the module computes nothing and only refuses. These
tests exist to stop the API coupling to engine internals; permitting a
refusal-only guard is consistent with that intent. Recorded here because
"added to a security allowlist" deserves scrutiny rather than a quiet merge.

---

## 7. Tests

| Scope | Result | Duration |
|---|---|---|
| `test_research_gaps.py` (new, 37 tests) | 37 passed | 9s |
| `test_research_guard.py` (97 tests) | 97 passed | 2s |
| **Full suite, all 38 files** | **2102 passed, 0 failed** | ~35 min |

Per-file execution with a 25-minute per-file cap. Two long files are pre-existing
and unchanged in character: `test_high_risk.py` (913s) and
`test_phase14c_analysis.py` (322s).

No test timeouts. No tests skipped or deleted.

Prohibited-workflow check: `run_backtest`, `Replay`, `run_experiment` and
`run_yearly_backtests` appear in `test_research_gaps.py` **only inside
`pytest.raises`**. Verified structurally that the guard is called at relative
line 78 while `PaperBroker` is constructed at line 125 — refusal happens before
any trading state exists. No ETH price, signal, trade or P&L value is asserted
anywhere.

---

## 8. Frozen artifacts

All re-hashed after the change, all unchanged:

| Artifact | SHA-256 | Status |
|---|---|---|
| BTC primary | `201a3b15…ba016b` | unchanged |
| BTC holdout (spent) | `c475e541…f99b` | unchanged |
| Phase 29 preregistration | `b06f36e2…17cc` | unchanged |
| ETH dataset | `7507c100…deeb` | unchanged |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e2…` | unchanged |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741…` | unchanged |
| Phase 30 `RESULTS_trades.csv` | `174d5587…` | unchanged |
| Phase 30 `SUMMARY.md` | `9e3171b0…` | unchanged |

**ETH reservation:** `status: RESERVED`, `used: false`,
`preregistration_id: null`, no `used_on` key. Asserted by
`test_reserved_eth_is_not_consumed_by_this_test_module`.

---

## 9. Git

```
branch   main
HEAD     dccebbd53ee8365474345506db9099b13356b53c
origin   dccebbd53ee8365474345506db9099b13356b53c
ahead/behind  0 / 0
staged    none
```

Tracked modifications: 10 files, +275/−4.

New untracked: `researchguard.py`, `research_registry.json`,
`research_registry.candle_index.json`, `test_research_guard.py`,
`test_research_gaps.py`, `experiments/phase39/`, `experiments/phase40/`.

No commit, stage, push, reset, clean or delete.

---

## 10. Remaining bypasses

One, stated rather than hidden:

**Unregistered series is permitted.** Data the registry has never seen runs as
"unregistered development data". Nothing can identify data it has never been
told about. Closing this means requiring a research context for *every* series
regardless of content — a broader change than this phase should make silently.

**Sub-threshold slices are inert.** One- and two-bar series are below the match
floor, but the engine requires more than `minimum_history` (22) bars before any
signal can exist. A series too short to be matched cannot produce a trade. The
gap is real and is not a path to performance.

---

## 11. Verdict

**PASS**

The documented omission bypass is closed at the data layer across all six
strategy-executing entry points. Registry persistence is authoritative, atomic
and auditable. Overlap status is unambiguous. Frozen artifacts are unchanged
and the ETH reservation is intact and unspent.

Passing software tests establishes that the safeguards refuse as designed. It
establishes nothing about whether the strategy is profitable.

**Phase 41 may proceed.**