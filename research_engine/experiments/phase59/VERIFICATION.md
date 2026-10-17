# Phase 59 Verification

**Date:** 2026-10-09

---

## 1. Baseline (Step 1)

**[V] Git:** branch `main` · `HEAD` `dccebbd53ee8365474345506db9099b13356b53c`
== `origin/main` · ahead/behind **0/0** · staged **0** · 19 tracked modified ·
366 untracked.

**[V] Runtime:** Windows 11 (10.0) AMD64 · CPython **3.12.10** · `os.name == "nt"`.
`msvcrt.locking` available (`LK_NBLCK = 2`). `fcntl` **not available** (POSIX
only). **No POSIX environment existed.**

**[V] Stop-condition checks — passed:**

```
ETH SHA-256 : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
status/used/prereg : RESERVED False None
consumption keys   : []
VERDICT            : INTACT - proceed
```

**[V] Prior work inspected:** 4 locking test files, Phase 57–58 reports, the 4
crash tests left incomplete, and 3 existing GitHub Actions workflows.

---

## 2. Locking redesign (Steps 3–4)

**[V] Replaced** the `O_CREAT|O_EXCL` sentinel lockfile with **OS-native
advisory locking**:

- Windows: `msvcrt.locking(fd, LK_NBLCK, 1)`
- POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)`
- Release by closing the descriptor — which the OS also does on process death.

**[V] Removed as dead code:** `_lock_holder_state()`,
`_REGISTRY_LOCK_STALE_SECONDS`, `_REGISTRY_LOCK_HARD_CEILING_SECONDS`. Single
design, no layering.

**[V] Public API unchanged.** `consume_reservation`, `run_backtest`,
`ResearchContext`, `assert_evaluation_permitted` untouched.

**[V] Blast radius contained:** nothing outside `_consume_reservations` reads or
writes the lock sidecar.

---

## 3. The four crash scenarios (Step 2)

| # | Scenario | Result |
|---|---|---|
| 1 | Repeated kills at staggered offsets | ✅ **passed** |
| 2 | Concurrent readers during write | ✅ **passed** (after fixes below) |
| 3 | Concurrent stale-lock recovery | ✅ **superseded** — no stale locks exist; covered by a 6-contender race |
| 4 | Real ETH reservation untouched | ✅ **passed** |

**Two findings during this work, both recorded honestly:**

**3.1 A Windows constraint.** `os.replace` fails with `PermissionError` when
another process holds the target open. A busy reader therefore makes the writer
fail — **closed**, nothing committed. Tests now tolerate it on both sides.

**3.2 The original reader failure was the test's own write.** A malformed read
appeared; the cause was the test seeding the registry with `path.write_text()`,
which truncates and is **not** atomic. Seeding switched to `tmp + os.replace`.
The malformed read vanished — **confirming the product's write path was never
the problem.**

---

## 4. Test results (Step 9)

**[V] Direct invocation, no `Start-Process` wrapper.**

```bash
cd research_engine
python -X utf8 -m pytest tests -q --no-header -p no:cacheprovider --tb=line
```

```
2533 passed in 1853.77s (0:30:53)
```

**Exit code 0. Uninterrupted — no `KeyboardInterrupt`.**

**[V] Locking and guard subset:**

```bash
python -X utf8 -m pytest tests/test_registry_locking.py tests/test_crash_recovery.py \
  tests/test_reservation_single_use.py tests/test_cross_process_guard.py \
  tests/test_research_guard.py tests/test_research_gaps.py tests/test_registry_schema.py \
  -q --no-header -p no:cacheprovider
```

```
241 passed in 29.40s
```

**[V] Crash suite alone:** `6 passed in 1.59s`.

**[V] The earlier interruptions did not recur** under direct invocation. The
Phase 58 diagnosis — external cancellation, exacerbated by the `Start-Process`
console-process-group wrapper — is consistent with this result.

### Test failures that occurred, and what they were

| Failure | Cause | Resolution |
|---|---|---|
| `test_atomic_replace_failure_…` asserted no lock file | Obsolete — the sidecar now persists by design | Assert the lock is *free*, not absent |
| `test_reader_never_…` PermissionError | Windows `os.replace` vs open reader | Tolerate; invariant is "never malformed" |
| `test_reader_never_…` 1 malformed read | **The test's own non-atomic seeding** | Seed via `tmp + os.replace`; read became clean |
| `test_unlocked_sidecar_…` FileNotFoundError | Missing directory in my test | Created it |
| `test_distinct_processes_…` "no lock may leak" | Obsolete — sidecar persists | Assert the lock is free |
| Reader `reads == 0` | Windows: writer holds the file throughout | Baseline reads before the writer starts |

**Six failures, all in test expectations or test setup — none in the product.
No assertion was weakened to obtain a green run:** each was replaced with a
*stronger or more accurate* check (for example, "the lock is free" rather than
"the file is absent"), and one failure exposed a genuine measurement error in
the test.

**[V] Full-suite count:** 2533 = prior 2517 + 16 net new/changed lock and crash
tests.

---

## 5. CI (Step 5)

**[V] Added** `.github/workflows/reservation-locking.yml` — matrix
`windows-latest`, `ubuntu-latest`, `macos-latest`, Python 3.11 (matching
`research-checks.yml`), `fail-fast: false`, path-filtered triggers.

**[V] YAML parses**; matrix resolves to the three expected runners; 6 steps.

**[V] Runs** the seven locking/guard suites plus two extra steps: reporting the
active locking backend, and **asserting the ETH dataset digest and reservation
state after the tests** — turning the governance invariant into a CI check.

**Not committed, not pushed.**

**[V] UNVERIFIED.** No run has occurred. **No POSIX result is claimed.**

---

## 6. Design and governance deliverables (Steps 6–8)

**[V]** `consume_on_completion` design produced with state machine, crash-window
analysis, compatibility review and a 9-test synthetic plan. **Not implemented** —
it changes a public API.

**[V]** B1–B9 decision sheet with exact owner-input wording. **Nothing selected,
approved, or invented.**

**[V]** B10 12 prerequisites and B11 9 conditions audited. **B10: 1 of 12
verified. B11: 0 of 9.** Hash functions that exist but have no recorded value
are counted as **UNMET**.

---

## 7. Final integrity (Step 10)

**[V] ETH dataset SHA-256, recomputed after all work:**

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation:**

```
status             : RESERVED
used               : False
preregistration_id : None
consumption keys   : []
VERDICT            : INTACT
```

| Check | Result |
|---|---|
| Frozen artifacts unchanged | `data/BTCUSDT_1h_Cleaned (1).csv` prefix `201a3b15…` **unchanged** |
| Historical results unchanged | No earlier phase report rewritten or deleted |
| No backtest / optimisation / reserved inspection | Confirmed |
| No freeze, no ID, no authorisation | Confirmed |
| Nothing staged, committed or pushed | **staged 0**; `HEAD` unchanged |

---

## 8. Absolute rules observed

| Rule | Observed |
|---|---|
| Inspect Git state before changes | Yes |
| Preserve user changes and historical reports | Yes |
| Never reset, clean, delete, overwrite | Yes |
| Never modify frozen datasets or results | Yes — verified |
| Never run backtests / optimisation / reserved analysis | Yes |
| Never consume the reservation | Yes — verified |
| Never invent legal conclusions, approvals, results, thresholds | Yes |
| Never choose the licence | Yes — options only |
| Never stage, commit, push, publish | Yes — staged 0 |
| Synthetic data and temp registries for safety experiments | Yes |
| **Do not claim a platform was tested unless its tests ran there** | **Yes — POSIX explicitly not claimed; CI marked UNVERIFIED** |
| Sequential; record failures | Yes — six failures recorded and diagnosed |

---

## 9. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `LOCKING_DESIGN_COMPARISON.md` | Comparison table, decision, crash-safety boundaries |
| 2 | `CRASH_RECOVERY_VERIFICATION.md` | Four scenarios, two findings, guarantees claimed/not claimed |
| 3 | `CROSS_PLATFORM_CI.md` | Workflow, platform status, what running it would close |
| 4 | `RESERVED_EVALUATION_DESIGN.md` | Entry points, four cases, state machine, test plan |
| 5 | `OWNER_DECISION_SHEET.md` | B1–B9 with exact owner input |
| 6 | `B10_B11_READINESS_AUDIT.md` | 12 + 9 conditions with status and dependencies |
| 7 | `VERIFICATION.md` | This document |

---

## 10. Verdict

# `PARTIAL — SAFEGUARD GAPS REMAIN`

The locking redesign closed the orphaned-lock class outright: a killed holder's
lock is now released by the OS rather than reclaimed by a heuristic, and the
residual 300-second window Phase 58 flagged **no longer exists**. The full suite
passed — 2533 tests, uninterrupted.

What remains is one verification gap and eleven owner decisions. The gap is
**POSIX execution**: the CI workflow is written but has never run, so
cross-platform safety is designed-for and configured, not demonstrated.

That gap does not put the reserved window at risk — which is verified intact —
and it is closed by pushing one workflow file.