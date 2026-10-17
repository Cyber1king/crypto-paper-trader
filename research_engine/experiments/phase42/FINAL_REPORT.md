# Phase 42 Final Report

**Date:** 2026-10-09
**Scope:** Phases 40–42 — research enforcement, multi-market validation, independent readiness review.

---

## 1. Phase verdicts

| Phase | Verdict | Basis |
|---|---|---|
| **40** — Close research enforcement gaps | **PASS** | Omission bypass closed at the data layer across all six strategy-executing entry points; verified by live probe |
| **41** — Multi-market data validation | **PASS** | Two real defects found and fixed; 55 new validation tests; forex correctly blocked on three independent grounds |
| **42** — Independent readiness review | **PASS** | Audit completed read-only; documented two places where prior reports overstated what code did |

**No phase was skipped.** No phase was blocked.

---

## 2. Files created

| File | Purpose |
|---|---|
| `src/crypto_paper_lab/researchguard.py` | Fail-closed guards; performs no calculation |
| `src/crypto_paper_lab/researchindex.py` | Per-bar identity index for partial-subset detection |
| `src/crypto_paper_lab/dataset_identity.py` | Declared instrument/timeframe/market/volume identity |
| `src/crypto_paper_lab/intervals.py` | Gap classification, 24×7 crypto only |
| `data/research_registry.json` | Instruments, reservations, consumed windows (5.8 KB) |
| `data/research_registry.candle_index.json` | Per-bar digests (1.9 MB, machine-only) |
| `tests/test_research_guard.py` | 97 tests |
| `tests/test_research_gaps.py` | 37 tests |
| `tests/test_dataset_validation.py` | 55 tests |
| `experiments/phase40/IMPLEMENTATION_REPORT.md` | |
| `experiments/phase41/VALIDATION_REPORT.md` | |
| `experiments/phase41/MARKET_READINESS_MATRIX.md` | |
| `experiments/phase41/VERIFICATION.md` | |
| `experiments/phase42/INDEPENDENT_READINESS_AUDIT.md` | |
| `experiments/phase42/FINAL_READINESS_MATRIX.md` | |
| `experiments/phase42/FINAL_REPORT.md` | this file |

## 3. Files modified

| File | Change |
|---|---|
| `backtest.py` | Guard gate before any trading state; context plumbing |
| `walkforward.py` | Context propagation; `assert_dataset_not_reserved` |
| `replay.py` | Guard before `Replay` construction |
| `experiment.py` | Context plumbing (previously none) |
| `yearly.py` | Context plumbing (previously none) |
| `dataset.py` | Timezone consistency check |
| `data.py` | Timestamp normalisation to naive UTC |
| `acquisition.py` | Explicit overlap-check status |
| `marketdata.py` | Guard decision actually recorded |
| `tests/test_api_health.py` | `researchguard` added to allowlist, with justification |
| `tests/test_replay.py` | `researchguard` added to allowlist, with justification |

11 tracked files, +330/−11.

---

## 4. Tests executed

Full suite, all 39 files, per-file with a 25-minute cap:

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

**2157 passed, 0 failed.** Approximately 30 minutes total.

| Group | Count |
|---|---|
| Pre-existing tests | 1968 |
| `test_research_guard.py` | 97 |
| `test_research_gaps.py` | 37 |
| `test_dataset_validation.py` | 55 |

**No tests skipped. No tests deleted. No tests marked xfail. No timeouts.**

Two slow files are pre-existing: `test_high_risk.py` (521s) and
`test_phase14c_analysis.py` (194s). Phase 40 established their character against
pristine `HEAD` (`test_high_risk.py`: 476s current vs 473s baseline) and their
cost is unchanged.

### Tests modified, and why

Two allowlists gained `researchguard` with a written justification:
`ALLOWED_ENGINE_IMPORTS` (API separation) and `engine_modules` (replay import
surface). Both entries state the module computes nothing and only refuses.

These tests exist to stop the API and replay coupling to engine internals.
Permitting a refusal-only guard is consistent with that intent, but "added an
entry to a security allowlist" deserves scrutiny rather than a quiet merge, so it
is called out here. **No test was weakened, and no assertion was relaxed.**

Two Phase 39 tests were **corrected**, not weakened:

- `test_development_run_without_context_is_unaffected` used timestamps inside the
  ETH reserved window. The dates were moved out of the reserved range; the
  assertion is unchanged and stronger.
- `test_reserved_window_range_refused_without_context` asserted a date-overlap
  refusal that turned out to be wrong. Replaced with
  `test_reserved_dates_alone_do_not_refuse_synthetic`, which pins the corrected
  content-identity behaviour.

---

## 5. Guard coverage and known gaps

### Coverage

All six strategy-executing entry points refuse the reserved ETH series when
called without a research context. Verified by live probe, not by reading the
guard's documentation:

| Entry point | Guard location | Result |
|---|---|---|
| `run_backtest` | direct call | REFUSED |
| `replay.Replay` | direct call | REFUSED |
| `run_experiment` | forwards | REFUSED |
| `run_yearly_backtests` | forwards | REFUSED |
| `run_window` | forwards | REFUSED |
| `walk_forward` | forwards | refused (incidentally — see audit §1.2) |

Eight series shapes probed against the real ETH file — full, evaluation slice,
mid-chunk, 5-bar, tail, warm-up head, reversed, every-other-bar — **all
refused**.

### Known gaps

| Gap | Status |
|---|---|
| Unregistered series permitted | Documented limit. Data the registry has never seen cannot be identified. Closing it means requiring a context for every series regardless of content |
| Sub-3-bar slices unmatched | Inert. The engine requires >22 bars before any signal can exist, so an unmatched series cannot trade |
| Repeat reuse possible if `consume_reservation()` is skipped | Deliberate. An attempt that crashes must not spend a window. Protects against unauthorised reuse, not against process-skipping |
| Guards are not a security boundary | They are editable Python. They raise the cost of a mistake; they do not stop a determined actor |

None is a path to reserved ETH performance.

---

## 6. Two errors found and recorded

Stated plainly because an audit reporting only confirmations is not an audit.

**1. The Phase 39 report overstated its API guard.** It described
`load_research_candles` as refusing the run. The code called
`assert_no_registered_range(allow_consumed=True)`, which *returns* a list of
hits that nothing read. Nothing was refused. Phase 40 replaced it with a check
that records something. The conclusion held; the described mechanism did not.

**2. My first Phase 40 fix was wrong.** I initially refused on date-range overlap
alone, which broke four test files and protected nothing — synthetic fixtures
legitimately share calendar dates. Corrected to match per-bar content identity.
The correction was to the implementation, not to the tests.

Also recorded in the audit: `walk_forward`'s refusal of reserved ETH came from its
own hard-wired dataset-bound check, not from the research guard. The guard is
present and would have caught it; something else stopped that particular call. A
passing probe that looked like guard coverage was not quite that.

---

## 7. Frozen hashes verified

8 of 8 matched, 0 mismatches. No baseline re-derived; nothing silently updated.

| Artifact | SHA-256 | Result |
|---|---|---|
| BTC primary dataset | `201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b` | OK |
| Consumed BTC holdout | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` | OK |
| Phase 29 preregistration | `b06f36e21df0fe403e3a75cbf8c3de84161607348966d622b65ea3f51bf217cc` | OK |
| ETH dataset | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` | OK |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e29ea7c6a8…` | OK |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741a7dbab8f…` | OK |
| Phase 30 `RESULTS_trades.csv` | `174d558719f31067…` | OK |
| Phase 30 `SUMMARY.md` | `9e3171b08555e06b…` | OK |

Phase 33–35 provenance reports also unmodified.

---

## 8. Reserved ETH status

```
status             : RESERVED
used               : False
preregistration_id : None
used_on present    : False
dataset SHA-256    : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

Unspent, unapproved, unmodified. **No ETH 2026 performance was computed,
inspected or revealed in any of Phases 40–42.**

---

## 9. Git state

```
branch            main
HEAD              dccebbd53ee8365474345506db9099b13356b53c
origin/main       dccebbd53ee8365474345506db9099b13356b53c
ahead / behind    0 / 0

staged            (none)
tracked modified  11 files, +330 / -11
untracked total   291
```

No commit, stage, push, reset, clean or delete was performed. Nothing was staged.

---

## 10. Next permitted action

**Permitted:** draft the ETH research question and a preregistration, without
running any evaluation against ETH 2026. A preregistration written now, before
any result is seen, is exactly what the process requires.

**Explicitly prohibited:**

- Running any backtest, replay, walk-forward or performance calculation against
  the reserved ETH 2026 window.
- Reading or inspecting ETH 2026 performance, signal-by-signal or in aggregate.
- Reusing the consumed BTC holdout or the Phase 10/11 OOS window for any purpose.
- Tuning or selecting strategy parameters using ETH data.
- Modifying the frozen BTC configuration so ETH data appears to be BTC.
- Inventing profitability thresholds or decision rules after observing results.
- Converting ECB reference rates into synthetic OHLC.
- Inventing forex session, holiday or DST rules.
- Implementing AI-provider integration.
- Committing, staging or pushing this work.

---

## 11. What this report does not establish

2157 passing tests mean the guards refuse unauthorised evaluation and the
validator refuses malformed data. They say nothing about whether the strategy is
profitable, because no result in Phases 40–42 bears on that question.

The BTC holdout evaluation of record was `INCONCLUSIVE` with a net profit factor
of `0.4925` — a negative result on the only untouched data this project ever
held. Nothing since then changes that. ETH's data is the cleanest available and
its validation is the strongest, which is precisely why it remains unapproved:
the remaining blockers are governance and preregistration, not data quality.

No instrument is ready for evaluation.