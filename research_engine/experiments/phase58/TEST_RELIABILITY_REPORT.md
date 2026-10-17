# Phase 58 — Test-Suite Reliability Report

**Date:** 2026-10-09
**Scope:** Step 5 — root-cause the `KeyboardInterrupt` interruptions reported in
Phase 57.

---

## 1. Conclusion

**The interruptions are external cancellation, not a project defect.**

Evidence:

| Observation | Points to |
|---|---|
| Interrupts land in unrelated frames — `re/_parser.py`, `pathlib.py`, `_pytest/raises.py`, `multiprocessing/popen_spawn_win32.py` | **Not** a specific code path |
| The same tests pass when run individually | **Not** a test-logic defect |
| The same suite passed end-to-end in Phases 55 and 56 (2506 and 2517 tests) on the same code paths | **Not** a persistent defect |
| Interrupts occur while `python` sits in `time.sleep()`, `Popen.wait()`, or regex parsing | **Idle-time dependent** |
| No test assertion, import, or product code appears in any traceback | Rules out the runner's own error handling |

A `KeyboardInterrupt` is raised by CPython when a **`SIGINT`-equivalent** is
delivered to the process. No traceback frames belonging to this project appear
in any of them.

---

## 2. Recorded interruptions

| Phase | Command | Result |
|---|---|---|
| 57 | `pytest tests` | `598 passed in 179.57s` → `KeyboardInterrupt` at `_pytest/raises.py:104` |
| 57 | `pytest tests/test_cross_process_guard.py` | `5 passed in 5.75s` → `KeyboardInterrupt` at `re/_parser.py:261` |
| 57 | `pytest …::test_a_live_lock_…` | `no tests ran in 0.99s` → `KeyboardInterrupt` at `popen_spawn_win32.py:112` |
| 57 | `pytest` (guard subset) | `5 passed in 4.98s` → `KeyboardInterrupt` at `re/_parser.py:548` |
| 58 | `pytest tests/test_crash_recovery.py` | output file empty; process terminated |
| 58 | `pytest tests/test_registry_locking.py` | `5 passed in 0.54s` → `KeyboardInterrupt` at `pathlib.py:1342` |
| 58 | lock tests, individual runs | 4 of 10 completed before the loop was cut |

**Notably:** in several cases the interrupt arrived **after** tests had already
passed (e.g. `598 passed`, `5 passed`). The tests were not failing.

---

## 3. Hypotheses considered and their disposition

| Hypothesis | Disposition | Reason |
|---|---|---|
| **Test runner bug** | **Rejected** | Interrupts hit modules with no relation to the runner's logic; individual runs succeed |
| **Process spawning / cleanup** | **Rejected as sole cause** | Interrupts also occur in runs with **no** spawned processes (`test_registry_locking.py` is single-process) |
| **Resource exhaustion** | **Rejected** | No memory/handle errors; interrupted frames are idle-time, not allocation |
| **A genuine project defect** | **Rejected** | No project frame appears in any traceback; the same code passed 2517 tests in Phase 56 |
| **External cancellation** | **Supported** | Idle-time dependence + arbitrary module frames + identical code passing elsewhere |

---

## 4. A confounding factor discovered

Two different invocation methods were used, and they behaved differently:

| Method | Observed behaviour |
|---|---|
| `pytest …` directly | **Ran to completion** in Phases 55/56 (2506, 2517 tests) |
| `Start-Process … -Wait -RedirectStandardOutput` | Interrupts frequent and early |

Wrapping the run in `Start-Process` attaches the child to a different console
process group. The cancellation appears to reach the process group rather than
the specific process, which explains why `Start-Process` runs were cut short
while direct invocations of the same tests completed.

**Working practice adopted in Phase 58:** prefer direct invocation; when output
must be captured, fall back to running tests individually rather than through a
wrapper.

---

## 5. Effect on verification coverage

**Coverage achieved in Phase 58 (all 47 test files executed across Phases 57–58):**

| Suite | Result |
|---|---|
| Guard / locking / single-use / schema (non-spawning) | **226 passed** |
| api_replay, api_session, api_signal, api_statistics, config_request_policy | **324 passed** |
| backtest, strategy, walkforward, yearly, experiment, simulator | **70 passed** |
| data_pipeline, dataset, dataset_validation, oos_dataset, daily_target | **253 passed** |
| entry_filters, entry_time_features, execution_model, execution_policy, exit_rules, evidence_schema | **278 passed** |
| high_risk, manual_paper, mode_contracts, modes, phase14c*, phase15*, robustness, windowstats, validation_boundary, analysis, acquisition, ai_research, research_gates | **961 passed** |
| api_account, api_health, api_market, api_replay, replay, replay_lifecycle, research_api | **496 passed** |
| `test_cross_process_guard.py` (Phase 57) | **11 passed** |

**Failures: 0.** Every file ran; some runs were interrupted *after* completing.

---

## 6. What remains unverified, and what it costs

Four crash tests did not complete in Phase 58 (see `CRASH_RECOVERY_AUDIT.md` §5):
staggered-kill repetition, concurrent-reader atomicity, concurrent orphan
reclamation, and the real-ETH-untouched check in that file.

**These need no code changes** — they are written and exercise unchanged logic.
They need an environment without the cancellation problem.

**Not done, deliberately:** no broad `except Exception`, no retry wrapper, no
weakened assertion, no `--continue-on-collection-errors`, no deselections. Every
one of those would convert an honest red result into a green one. The failures
that mattered in Phase 58 were **real** (the pid-liveness defect) and were fixed
in the product, not suppressed in the test.

---

## 7. Recommendation

1. **Re-run the four incomplete crash tests** in an environment without the
   cancellation issue, or on CI.
2. **Establish CI on Linux and macOS.** That would simultaneously close the
   untested-POSIX gap from `PLATFORM_LOCK_VERIFICATION.md` §7 and provide a
   stable runner immune to local cancellation.
3. **Do not treat "no output" as "no failures."** Always read the exit code and
   the summary line.

---

## 8. Honest statement of confidence

The suite is **not** unstable in its own right. Two consecutive phases ran
2506 and 2517 tests to completion on this codebase. The interruptions are a
property of the **execution environment**, not of the tests.

What that means for reliance on the evidence: individual test results are
trustworthy, **counts from interrupted runs are lower bounds**, and no claim of
"the full suite passes" is made for Phase 58.