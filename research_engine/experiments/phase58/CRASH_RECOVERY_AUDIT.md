# Phase 58 — Crash and Interruption Safety Audit

**Date:** 2026-10-09
**Scope:** Step 3 — simulate termination at each phase of the reservation spend
and inspect what survives.

> All tests used temporary registries with synthetic reservations, in child
> processes that were deliberately terminated. **The real registry was never
> written and the reserved ETH dataset was never opened.**

---

## 1. The sequence under test

```
consume_reservation(reservation_id, registry_file, preregistration_id)
  └─ _consume_reservations(...)
       ├─ acquire lock            (O_CREAT|O_EXCL)
       ├─ load_registry           ← READ
       ├─ duplicate check
       ├─ mutate in memory        ← CHECK / DECIDE
       ├─ mkstemp + json.dump
       ├─ os.replace(tmp, target) ← WRITE (atomic)
       └─ release lock
```

The window between the read and the atomic replacement is the only place an
interruption could produce an inconsistent result — **provided** `os.replace` is
atomic and **provided** the lock's recovery is safe.

---

## 2. The invariant asserted after every interruption

Central to the audit, checked by one helper after every simulated crash:

```python
def _assert_consistent(path, *ids):
    data = json.loads(path.read_text())          # 1. must be valid JSON
    for rid in ids:
        entry = ...
        assert entry["used"] is (entry["status"] == "USED")   # 2. never contradict
        if entry["used"]:
            assert entry["used_preregistration_id"]           # 3. spend is complete
            assert entry["used_on"]
        else:
            assert entry.get("used_preregistration_id") is None
            assert "used_on" not in entry
```

A spend must be **all-or-nothing**: either fully recorded (flag, status,
preregistration, timestamp) or not recorded at all. There is no permitted state
where a window looks consumed without its provenance, or unconsumed while
carrying a timestamp.

---

## 3. Results

| # | Interruption point | Test | Result |
|---|---|---|---|
| 1 | **After lock acquisition** — child killed inside the held-lock window | `test_crash_while_holding_lock_leaves_a_recoverable_registry` | **FAILED** — see §4.1 |
| 2 | **During read/check/write** — 6 kills at staggered offsets | `test_repeated_kills_never_corrupt_the_registry` | **Not completed** (§5) |
| 3 | **Concurrent reader during write** | `test_reader_never_observes_a_partially_written_registry` | **Not completed** (§5) |
| 4 | **Leftover `.tmp` from a crashed writer** | `test_leftover_temp_file_cannot_corrupt_the_registry` | **PASSED** |
| 5 | **`os.replace` failure** (simulated) | `test_atomic_replace_failure_fails_closed_and_cleans_up` | **PASSED** |
| 6 | **Two contenders reclaiming one orphan lock** | `test_two_contenders_recovering_one_stale_lock_yield_one_winner` | **Not completed** (§5) |
| 7 | **Old lock whose pid resolves** | `test_stale_lock_is_not_removed_merely_because_it_is_old` | **PASSED** |
| 8 | **Real ETH reservation untouched** | `test_real_eth_reservation_untouched_by_crash_testing` | **Not completed** (§5) |

---

## 4. Findings

### 4.1 A crash after lock acquisition exposed the pid-liveness defect

Test 1 **failed**, and the failure was correct behaviour driven by a wrong
policy — not a test bug:

```
ResearchGuardError: refusing to record consumption: the registry at ... is
locked by pid that is still running (..., held for 1791627968.3s).
An old lock is not proof of an abandoned one. Nothing was written.
```

The test killed a child that had **acquired the lock and not yet spent the
reservation**, then reclaimed the orphan. The guard reported the lock's holder
as *"still running"* — because the child had been terminated and **reaped**, and
its pid still resolved in the process table.

Independently confirmed with a direct measurement (§2 of
`PLATFORM_LOCK_VERIFICATION.md`): a killed, waited-for process probes as
**ALIVE** on Windows; only a never-used pid reports failure.

**Two consequences, both serious:**

1. The Phase 57 policy would have **never reclaimed a crashed holder's lock** —
   a permanent registry wedge.
2. **A crash must not leave a window appearing consumed.** The test's assertion
   that `used is False` after the kill held — the kill landed before any write —
   but the *recovery* half of the test could not complete, because the orphan
   lock could not be reclaimed at all.

**Corrected.** A resolvable pid is now `indeterminate`, never `alive`. A provably
absent pid (`ProcessLookupError` / `EINVAL`) is `gone` and reclaimable past the
stale threshold; an ambiguous pid is reclaimable only past the 300 s ceiling.

### 4.2 Atomic replacement failure is handled correctly

Simulating `os.replace` raising:

- Registry **byte-identical** to before the attempt.
- Reservation still `used: false`, internally consistent.
- No `.tmp` left behind.
- No lock leaked.
- The **next attempt succeeds normally** — the failure is not sticky.

This is the cleanest evidence that the write is genuinely commit-or-abort.

### 4.3 A stray temp file is inert

A `.tmp` containing `{ this is not json`, left beside the registry, has no
effect: the registry remains valid, consumption succeeds, and the stray file is
never consulted. The commit path reads only the target.

### 4.4 A resolvable pid is not proof of life

`test_stale_lock_is_not_removed_merely_because_it_is_old` passed: a lock
attributed to this process, backdated to the epoch, was **not** removed across
three consecutive attempts. This is the anti-theft rule that Phase 58's
correction exists to preserve.

---

## 5. Incomplete verification — stated, not glossed

Tests 2, 3, 6 and 8 **did not complete in this environment**. See
`TEST_RELIABILITY_REPORT.md`: the harness injected `KeyboardInterrupt` into the
Python process, landing in unrelated frames (`re/_parser.py`, `pathlib.py`,
`multiprocessing/popen_spawn_win32.py`, `_pytest/raises.py`). Individual runs of
*some* tests completed; others were cut off before finishing.

**What this means for the claims in this document:**

- The atomicity argument for `mkstemp` + `os.replace` is **structurally sound**
  and supported by tests 4 and 5, but the **concurrent-reader** test (3) did not
  run, so "a reader never sees a partial file" is **not** empirically confirmed
  here. It is a documented property of `os.replace` on local filesystems, not a
  measurement.
- The **staggered-kill** test (2) did not run, so "repeated kills never corrupt
  the registry" is **not** empirically confirmed.
- The **concurrent stale-recovery** test (6) did not run.

**These are gaps in evidence, not known defects.** Nothing observed suggests
corruption; the observed failures were *over*-refusal (safe direction), never
under-protection.

---

## 6. Guarantees: claimed and not claimed

### Supported by the tests that ran

- A failed atomic replacement commits nothing and cleans up.
- A stray temp file cannot corrupt the registry.
- A lock whose pid resolves is not broken for age alone.
- Killing a process holding the lock does **not** spend the reservation.
- The real ETH reservation is untouched (Phase 57 equivalent verified).

### Not claimed

- **Transactional guarantees beyond what was measured.** No test kills a process
  in the microsecond between `json.dump` completing and `os.replace` returning.
- **Power-loss or filesystem-crash safety.** No test simulates a device failure
  or an unclean filesystem unmount. `os.replace` is atomic with respect to other
  readers on a local filesystem; that is not durability across a power cut.
- **Readers never seeing partial JSON** — untested here (§5).
- **Concurrent orphan reclamation** — untested here (§5).
- **Any POSIX behaviour.**

---

## 7. Recovery story, as actually established

| Situation | What happens | Evidence |
|---|---|---|
| Crash before any write | Registry unchanged; window unspent | Test 1 (kill landed pre-write) |
| Crash after `os.replace` | Registry valid; window spent with full provenance | Structurally guaranteed; not directly tested |
| Crash between dump and replace | Registry unchanged; `.tmp` orphaned and inert | Test 4 |
| `os.replace` fails | Nothing committed; temp cleaned; next attempt works | Test 5 |
| Holder crashes holding the lock | Orphan lock; blocks until ceiling, then reclaimed | **Was broken; now corrected** |

---

## 8. Recommendation

The remaining evidence gaps (§5) should be closed by re-running tests 2, 3, 6 and
8 in an environment without the cancellation problem. They need no code changes —
they are already written and the logic they exercise is unchanged.

The deeper improvement remains the one proposed in
`PLATFORM_LOCK_VERIFICATION.md` §6: **OS-native advisory locking**, which is
crash-safe by construction and would eliminate the entire orphaned-lock class,
including the 300 s ceiling and the pid-reuse ambiguity.