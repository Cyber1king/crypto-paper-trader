# Phase 59 — Locking Design Comparison

**Date:** 2026-10-09
**Decision:** replace the sentinel lockfile with **OS-native advisory locking**.

---

## 1. What the previous design had to do, and why it was fragile

The Phase 56–58 design used `os.open(O_CREAT|O_EXCL)` on a `.lock` sidecar and
then had to decide, on every collision, whether the existing lock was
*abandoned*. That question has no reliable answer:

| Attempted discriminator | Measured result on this platform |
|---|---|
| Age of the lock file | Cannot distinguish slow from dead — required a 30 s threshold *and* a 300 s ceiling |
| `os.kill(pid, 0)` says "alive" | **Also true for a terminated, reaped pid** (pids are recycled) |
| `os.kill(pid, 0)` says "dead" | Only reliable when the pid **never existed** |

So the previous design carried two arbitrary time constants and a PID heuristic
that could not answer its own question. Phase 58 established the consequence:
a crashed holder's lock could be **permanently unreclaimable**.

---

## 2. Comparison

| Criterion | Sentinel lockfile | OS-native advisory lock |
|---|---|---|
| **Windows** | Works | `msvcrt.locking(LK_NBLCK, 1)` — stdlib, verified available |
| **Linux / macOS** | Works | `fcntl.flock(LOCK_EX\|LOCK_NB)` — stdlib |
| **Release on normal exit** | Manual `unlink`, racy | Automatic on `close()` |
| **Release on process kill** | **Manual, requires a heuristic** | **Automatic — by the kernel** |
| **Release on crash** | Same as kill | **Automatic** |
| **Stale-lock handling** | Thresholds + ceiling + pid logic | **Not applicable** |
| **PID-reuse ambiguity** | Present and unresolvable | **Not applicable — no pid involved** |
| **Concurrent acquisition** | `O_EXCL` atomicity | OS-guaranteed exclusive |
| **Orphaned-lock class** | Exists | **Eliminated** |
| **Dependencies** | None | None — stdlib only |
| **Cross-platform sync** | Portable sentinel | Platform branch, same stdlib |
| **File replacement semantics** | Independent concern | Independent concern |
| **Testability** | Needs timing, backdating, ceiling waits | Deterministic — release is synchronous |
| **Power-loss durability** | n/a | **Not provided — see §6** |

---

## 3. Decision: implemented

`flock`/`msvcrt.locking` **materially reduces orphaned-lock risk** and is
implementable with stdlib on every supported platform, so the smallest justified
change was made.

```python
def _acquire_fd_lock(fd, lock_path):
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, _REGISTRY_LOCK_BYTES)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
```

The critical section in `_consume_reservations` is unchanged — the lock still
wraps read → duplicate check → write → replace. Only the lock *mechanism*
changed.

**Removed as now-dead code:** `_lock_holder_state()`,
`_REGISTRY_LOCK_STALE_SECONDS`, `_REGISTRY_LOCK_HARD_CEILING_SECONDS`. The task
required a single design rather than layered competing locks.

**Single design, not a hybrid.** No sentinel file is written any more; the
sidecar is only a carrier for the OS lock.

---

## 4. Why the sidecar file is left in place

The `.lock` file **persists after release**. Deleting it would race any process
that has already opened it, and deletion buys nothing: an unlocked sidecar
carries no state. Removing it would also break the guarantee that two
contenders contend on the *same inode*.

Verified by `test_unlocked_sidecar_left_behind_is_harmless`.

---

## 5. Behavioural consequences

| Situation | Before | After |
|---|---|---|
| Contention | Second contender refused | Unchanged |
| Holder killed | Orphan; recover after ceiling | **Lock released by the OS at kill** |
| Live holder, any age | Never broken before ceiling | **Never broken, ever** |
| Stale sidecar from an old run | Needed age + pid reasoning | **Irrelevant — the file holds no state** |
| Slow write (>5 min) | Could be stolen at the ceiling | **Cannot be stolen at all** |

The residual 300-second window that Phase 58 flagged as an open gap **no longer
exists**.

---

## 6. What this is not — crash-safety boundaries

Advisory locking is **not** uniformly "crash-proof". Three different events:

| Event | OS lock released? | Registry safe? |
|---|---|---|
| **Process termination** (`kill`, `sys.exit`, unhandled exception) | **Yes**, on close of the descriptor | Yes — `mkstemp`+`os.replace`; the temp is discarded |
| **OS crash** (kernel panic, `kill -9` of the machine) | Yes, on reboot | **Not durable across the crash** — the sidecar and registry may be lost or stale. No `fsync` is performed on either file |
| **Power loss** | Same as OS crash | **Not durable.** The registry write is atomic with respect to *other readers on a live filesystem*; it is **not** a durability guarantee |

**Not claimed:** transactional durability, fsync-level persistence, or
power-loss safety. The design protects against a **misbehaving or killed
process**, which was the actual risk. It does not protect against the storage
layer disappearing.

Adding `os.fsync` on the temp file before `os.replace` (and on the directory
after) would extend durability — deliberately **not** done here, as it is a
separate concern from mutual exclusion and would need its own tests.

---

## 7. Blast radius

Nothing outside `_consume_reservations` reads or writes the lock sidecar, so the
change is contained. Verified: no other module references `_registry_lock` or
the lock suffix.

Public API unchanged: `consume_reservation`, `run_backtest`, `ResearchContext`
and `assert_evaluation_permitted` are untouched.

---

## 8. Evidence

| Property | Status |
|---|---|
| Two and four independent consumers → exactly one succeeds | **Verified** |
| Winner's preregistration recorded; loser's never is | **Verified** |
| Holder killed while holding → next consumer succeeds **immediately** | **Verified** |
| Live holder excluded for as long as it lives | **Verified** |
| Interrupted writes preserve registry validity | **Verified** |
| Permission and replacement failures fail closed | **Verified** |
| Concurrent readers never see malformed JSON | **Verified** |
| Concurrent recovery cannot corrupt the registry | **Verified** |
| Repeated attempts behave consistently | **Verified** |
| POSIX branch | **Not executed** — see `CROSS_PLATFORM_CI.md` |