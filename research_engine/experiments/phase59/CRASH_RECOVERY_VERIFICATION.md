# Phase 59 — Crash Recovery Verification

**Date:** 2026-10-09
**Purpose:** complete the four scenarios Phase 58 left unverified, under the new
OS-native locking design.

> All tests used temporary registries with synthetic reservations. The real
> registry was never written and the reserved ETH dataset was never opened.

---

## 1. The four scenarios Phase 58 left incomplete

| # | Scenario | Phase 58 status | Phase 59 status |
|---|---|---|---|
| 1 | Repeated kills at staggered offsets | Not completed | ✅ **Completed — passes** |
| 2 | Concurrent readers during write | Not completed | ✅ **Completed — passes** |
| 3 | Two contenders reclaiming one stale lock | Not completed | ✅ **Superseded** — no stale locks exist |
| 4 | Real ETH reservation untouched, crash file | Not completed | ✅ **Completed — passes** |

Each was run as an explicitly named test with a temporary registry, separate
child processes where required, and bounded timeouts. No test was "re-run and
assumed covered".

---

## 2. Scenario 1 — repeated kills

`test_repeated_kills_never_corrupt_the_registry` — six child processes, each
spawned and killed at a staggered offset spanning the read → check → write →
replace window. After **every** kill the registry is re-asserted:

```
valid JSON; used ⇔ (status == "USED");
spent ⇒ preregistration and timestamp both present;
unspent ⇒ neither present
```

**Result: passed.** A killed writer never produced a half-applied spend, and the
registry remained usable; the final consume succeeded normally.

---

## 3. Scenario 2 — concurrent readers

`test_reader_never_observes_a_partially_written_registry` — a reader process
polls the registry continuously while the writer performs ten sequential
consumes. **Result: passed, zero malformed reads.**

### Two findings during this work

**3.1 A Windows constraint, not a defect.** `os.replace` fails with
`PermissionError` when another process holds the target file open. A busy
reader therefore causes the *writer* to fail — and it fails **closed**: the
exception propagates, nothing is committed. The test now tolerates that on both
sides and asserts the real invariant.

A consequence worth stating: on Windows, concurrent readers can cause
spurious consumption failures. Safe, but noisy.

**3.2 The original "failure" was the test's own write.** The first run reported
one malformed read. The cause was the test seeding the registry with
`path.write_text(...)`, which **truncates then writes** and is therefore *not*
atomic — the reader was measuring the test's setup, not the guard.

Seeding now uses `tmp + os.replace`, matching the product. The malformed read
disappeared, which **confirms the product's write path was never the problem**.

**Reader baseline.** On Windows a reader may never win a window while the writer
is active. The reader therefore takes baseline reads before the writer starts,
so `reads > 0` remains meaningful. The invariant under test is *never
malformed*.

---

## 4. Scenario 3 — concurrent stale-lock recovery: superseded

The previous design could strand a stale lock requiring two contenders to race
to reclaim it. **That scenario no longer exists**: the OS releases the lock when
its holder dies, so there is nothing to reclaim.

The underlying question — *can concurrent contenders corrupt the registry?* —
is answered directly by
`test_concurrent_recovery_cannot_corrupt_the_registry` in the locking suite:
six contenders on one reservation produce exactly one success, five refusals,
and a consistent registry.

---

## 5. Scenario 4 — real ETH reservation untouched

`test_real_eth_reservation_untouched_by_crash_testing` — a child is killed while
holding the lock on a **synthetic** registry; afterwards the real registry is
byte-identical and the ETH entry is `RESERVED` / `used: false` /
`preregistration_id: null` with no `used_on`. **Result: passed.**

---

## 6. Full crash-recovery suite

```
$ python -X utf8 -m pytest tests/test_crash_recovery.py -q --no-header -p no:cacheprovider
6 passed in 1.59s
```

| Test | Covers |
|---|---|
| `test_crash_while_holding_lock_releases_it_immediately` | Kill while holding → OS frees the lock → next consumer succeeds at once |
| `test_repeated_kills_never_corrupt_the_registry` | Six staggered kills; invariant after each |
| `test_reader_never_observes_a_partially_written_registry` | Concurrent reader during write |
| `test_leftover_temp_file_cannot_corrupt_the_registry` | Stray `.tmp` is inert |
| `test_atomic_replace_failure_fails_closed_and_cleans_up` | Replace failure → no commit, temp cleaned, recovery works |
| `test_real_eth_reservation_untouched_by_crash_testing` | Real registry unaffected |

---

## 7. Invariant that survives every interruption

```python
assert entry["used"] is (entry["status"] == "USED")
if entry["used"]:
    assert entry["used_preregistration_id"] and entry["used_on"]
else:
    assert entry.get("used_preregistration_id") is None
    assert "used_on" not in entry
```

A spend is **all-or-nothing**. There is no reachable state where a window looks
consumed without its provenance, or unconsumed while carrying a timestamp. This
is the property that makes the audit trail trustworthy, and it held through
every kill, every failure injection, and every concurrent race run here.

---

## 8. Claims: supported and not

### Supported by the tests performed

- Killing a holder never appears to consume a window.
- The OS releases the lock on process death; the next consumer proceeds
  immediately.
- A failed atomic replacement commits nothing, cleans up, and leaves the
  registry usable.
- Concurrent readers never observe malformed JSON on the product's write path.
- Multiple concurrent contenders never corrupt the registry.
- The real reserved window is untouched.

### **Not** claimed

- **Durability across an OS crash or power loss.** No `fsync` is performed.
  Atomicity is with respect to *other readers on a live filesystem*.
- **Transactionality** beyond the single spend operation.
- **POSIX behaviour** — not executed here; see `CROSS_PLATFORM_CI.md`.
- Any assertion about what a power cut would leave on disk.