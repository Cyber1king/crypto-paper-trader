# Phase 58 Verification

**Date:** 2026-10-09

---

## 1. Baseline (Step 1)

**[V] Git**

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Upstream | `origin/main` @ same commit |
| Ahead / behind | **0 / 0** |
| Staged | **0** |
| Tracked modified | 19 |
| Untracked | 358 |

**[V] Platform:** Windows 11 (10.0), AMD64 · CPython **3.12.10** · `os.name == "nt"`.
**No POSIX environment was available.** POSIX behaviour is **not claimed**.

**[V] Stop-condition checks at baseline — both passed:**

```
ETH SHA-256 : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
status/used/prereg : RESERVED False None
consumption keys   : []
VERDICT            : INTACT - proceed
```

**[V] Phase 57 deliverables** — all 6 present and unchanged.

**[V] Lock implementation and test inventory** inspected directly: 4 relevant
test files (`test_registry_locking.py`, `test_cross_process_guard.py`,
`test_research_guard.py`, `test_reservation_single_use.py`).

---

## 2. Code changes

**[V] One product defect found and fixed**, plus one new test file.

| # | Finding | Impact | Fix |
|---|---|---|---|
| 1 | **PID liveness is not knowable on Windows.** A terminated, **reaped** pid still answers a signal-0 probe as alive; only a **never-used** pid reports failure (`EINVAL`) | Phase 57's `alive → never break` policy would have made a **crashed holder's lock permanently unreclaimable**, wedging the registry forever | `_lock_holder_state` reduced to `gone` / `indeterminate`. A resolvable pid is **never** treated as life |

**Measured evidence:**

```
spawned + killed + reaped pid : 7524
probe after kill             : ALIVE
DEAD pid reported as ALIVE?  : True
never-used pid (999999)      : UNKNOWN(OSError errno=22)
```

**Phase 57's recovery test gave false confidence** — it used `pid=999999`, which
exercises the *indeterminate* branch and never the real crash path. That is
documented rather than quietly corrected.

**[V] Policy after correction:**

| Age | Holder | Action |
|---|---|---|
| ≤ 30 s | any | never break |
| > 30 s | `gone` (ProcessLookupError / EINVAL / PermissionError) | **break** |
| > 30 s | `indeterminate` (pid resolves) | never break until 300 s ceiling, then break |

**No public signature changed.** `run_backtest`, `ResearchContext`,
`assert_evaluation_permitted`, `consume_reservation` untouched.

**[V] New file:** `tests/test_crash_recovery.py` (8 tests).

---

## 3. Test results (Step 5)

### Passed this phase

| Test | Result |
|---|---|
| `test_lock_is_released_after_normal_exit` | passed |
| `test_lock_is_released_after_an_exception` | passed |
| `test_lock_is_exclusive` | passed |
| `test_fresh_lock_is_not_treated_as_stale` | passed |
| `test_stale_lock_is_not_broken_while_its_holder_may_be_alive` | passed |
| `test_leftover_temp_file_cannot_corrupt_the_registry` | passed |
| `test_atomic_replace_failure_fails_closed_and_cleans_up` | passed |
| guard / locking / single-use / schema subset (earlier run) | **226 passed** |

### Failed — and the failure was a real product defect

`test_crash_while_holding_lock_leaves_a_recoverable_registry` **failed** with
*"locked by pid that is still running"* for a child that had been killed and
reaped. This drove the correction in §2. **The test was right; the code was
wrong.**

### Not completed

`test_repeated_kills_never_corrupt_the_registry`,
`test_reader_never_observes_a_partially_written_registry`,
`test_two_contenders_recovering_one_stale_lock_yield_one_winner`,
`test_real_eth_reservation_untouched_by_crash_testing` — cut off by the
cancellation described below. **These are gaps in evidence, not known defects.**

### Regression found and fixed

`test_stale_lock_is_not_broken_while_its_holder_may_be_alive` initially
**DID NOT RAISE** — it used `pid=999999`, which is now correctly `gone`. Its
premise inverted once liveness stopped being fiction. Rewritten to use
`os.getpid()`, plus a new test for the reclaimable `gone` case.

### Interruption investigation

**[V] Root cause: external cancellation, not a project defect.** Interrupts
landed in `re/_parser.py`, `pathlib.py`, `_pytest/raises.py` and
`popen_spawn_win32.py` — no project frame in any traceback. They occur while
Python sits idle (`time.sleep`, `Popen.wait`), and the same tests pass when run
individually. The same code ran 2506 and 2517 tests to completion in Phases 55
and 56.

**[V] Confounder identified:** `Start-Process … -Wait -RedirectStandardOutput`
attaches the child to a different console process group; the cancellation
appears to reach the group. Direct invocation completed in Phases 55/56; wrapped
invocations truncate.

**[V] No suppression applied.** No broad `except`, no retry wrapper, no weakened
assertion, no deselection. The one genuine failure was fixed **in the product**.

**[V] No claim of an uninterrupted full-suite green run in this phase.**

---

## 4. Steps 4, 6, 7 — design and documentation only

**[V]** Step 4 produced a **design** for `consume_on_completion`
(`RESERVED_EVALUATION_CONSUMPTION_DESIGN.md`) with a state machine, the
persistence-window limitation, compatibility analysis and a 9-test synthetic
plan. **Nothing was implemented.** All six entry points were traced; none
bypasses the guard.

**[V]** Step 6 produced the B1–B11 decision package with exact owner-input
wording. **No licence selected, no threshold chosen, no approver named.**

**[V]** Step 7 produced the final readiness audit: 7 engineering gaps, 11
governance gaps, 10 freeze conditions, 13 evaluation conditions.

---

## 5. Final integrity (Step 8)

**[V] ETH dataset SHA-256, recomputed after all work:**

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation:**

```
status             : RESERVED
used               : False
preregistration_id : None
consumption keys   : []          (none added)
VERDICT            : INTACT
```

**[V] Confirmed:**

| Check | Result |
|---|---|
| Frozen artifacts unchanged | `data/BTCUSDT_1h_Cleaned (1).csv` prefix `201a3b15…` **unchanged** |
| Historical results unchanged | No phase report rewritten or deleted |
| No backtest or optimisation ran | Confirmed |
| No reserved-period performance inspected | Confirmed |
| No preregistration freeze or ID assigned | Confirmed |
| Nothing staged, committed or pushed | **staged 0**; `HEAD` unchanged |

---

## 6. Non-negotiable rules observed

| Rule | Observed |
|---|---|
| Inspect Git state before changing | Yes |
| Preserve user modifications and historical reports | Yes |
| Never reset, clean, delete, overwrite | Yes |
| Never modify frozen datasets or results | Yes — verified |
| Never run backtests / optimisation / reserved analysis | Yes |
| Never consume the reservation | Yes — verified |
| Never invent approvals, legal conclusions, results, thresholds | Yes |
| Never choose the licence | Yes — options only |
| Never stage, commit, push, publish | Yes — staged 0 |
| Synthetic data and temp registries for safety testing | Yes |
| **Report platform limitations rather than claiming unrun tests** | **Yes — POSIX explicitly not claimed** |
| Sequential work; record failures | Yes — 2 real failures recorded and fixed |

---

## 7. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `PLATFORM_LOCK_VERIFICATION.md` | Windows-only evidence; the PID measurement; corrected policy; recovery matrix; POSIX gap |
| 2 | `CRASH_RECOVERY_AUDIT.md` | Interruption points, invariant, 3 passed / 1 failed / 4 incomplete; guarantees claimed and not claimed |
| 3 | `RESERVED_EVALUATION_CONSUMPTION_DESIGN.md` | Six entry points; four cases; state machine; `consume_on_completion` design; synthetic test plan |
| 4 | `TEST_RELIABILITY_REPORT.md` | Root cause of interruptions; hypotheses rejected; coverage; what is not claimed |
| 5 | `OWNER_DECISION_PACKAGE.md` | B1–B11 with exact owner-input wording |
| 6 | `FINAL_READINESS_AUDIT.md` | Engineering and governance gaps; freeze and evaluation conditions |
| 7 | `VERIFICATION.md` | This document |

**[V]** All previous phase reports preserved.

---

## 8. Verdict

# `PARTIAL — SAFEGUARD GAPS REMAIN`

The phase **corrected a real defect** that would have made a crashed holder's
lock permanently unreclaimable — a wedge no test had caught, because Phase 57's
recovery test used a pid that never existed.

Two critical safeguards remain unverified: **POSIX locking** (no environment
available) and **crash-window evidence** for four tests (interrupted, not
failing). Both need verification, not design.

Neither blocks an owner decision. Neither puts the reserved window at risk — it
is provably intact.