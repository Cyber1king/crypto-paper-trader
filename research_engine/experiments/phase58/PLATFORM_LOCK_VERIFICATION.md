# Phase 58 — Platform Lock Verification

**Date:** 2026-10-09
**Platform:** Windows 11 (10.0), AMD64 · CPython 3.12.10 · `os.name == "nt"`

> **No POSIX evidence exists.** This host runs Windows only. POSIX behaviour is
> **not** claimed, and no CI evidence for it has been produced. Every statement
> below is Windows-only and was measured here.

---

## 1. What was verified on this platform

| Property | Status |
|---|---|
| Independent-process contention (2 and 4 processes, 1 reservation) | **Verified** (Phase 57) |
| Exactly one consumer wins | **Verified** |
| Winner's `used_preregistration_id` recorded; loser's not | **Verified** |
| Registry never partially written; `used` agrees with `status` | **Verified** |
| Fail-closed on unreadable registry / uncreatable lock | **Verified** |
| Duplicate sequential consumption refused | **Verified** (Phase 55) |
| Lock released on normal exit and on exception | **Verified** (Phase 58) |
| Lock is exclusive | **Verified** (Phase 58) |
| A fresh lock is never treated as stale | **Verified** (Phase 58) |
| A lock under 30 s is never broken | **Verified** (Phase 57/58) |
| Leftover `.tmp` from a crashed writer is inert | **Verified** (Phase 58) |
| `os.replace` failure → fail-closed, no commit, temp cleaned | **Verified** (Phase 58) |

---

## 2. The decisive measurement: PID liveness is not knowable on Windows

This phase overturned a Phase 57 conclusion. Phase 57 introduced a
liveness-first stale-lock policy on the basis of a probe, and treated a
successful probe as proof the holder was alive.

**That inference is wrong on Windows, and measurably so.**

```
spawned + killed + reaped pid : 7524
probe after kill             : ALIVE
DEAD pid reported as ALIVE?  : True
own pid                      : ALIVE
never-used pid (999999)      : UNKNOWN(OSError errno=22)
```

Three facts:

1. A **terminated and reaped** process still answers a signal-0 probe as alive.
2. Only a pid that has **never existed** reports failure (`EINVAL`, or
   `ProcessLookupError` on POSIX).
3. Therefore a positive probe means *"this pid is in the process table"* — which
   does **not** distinguish a live holder from a dead holder whose pid has been
   recycled.

**Consequence if the Phase 57 policy had shipped unchanged:** `alive → never
break` combined with pid recycling means a lock left by a **crashed** holder is
**permanently unreclaimable**. The registry would wedge forever. Phase 57's own
recovery test passed only because it used `pid=999999` — a pid that never
existed, so it exercised the *indeterminate* branch and never the real
crash-recovery path. **That test gave false confidence**, and the correction is
recorded here rather than quietly folded in.

---

## 3. Correction applied

`_lock_holder_state()` now returns **two** values, and there is deliberately no
`"alive"` answer:

| Probe result | Classification | Rationale |
|---|---|---|
| `ProcessLookupError` | **`gone`** | No such process. Reliable. |
| `OSError` with `errno == EINVAL` | **`gone`** | Windows' signal for a pid that does not exist |
| `PermissionError` | **`gone`** | Exists but belongs to another user; unusable as a holder marker |
| Probe succeeds | **`indeterminate`** | May be alive, may be a recycled pid. **Never treated as life** |

The policy that consumes it:

| Lock age | Holder state | Action | Rationale |
|---|---|---|---|
| ≤ 30 s | any | **Never break** | A fresh lock is never an abandoned one |
| > 30 s | **`gone`** | **Break and proceed** | Provably no holder remains |
| > 30 s | `indeterminate`, ≤ 300 s | **Never break** | Ownership cannot be established |
| > 30 s | `indeterminate`, > 300 s | **Break** | Bounded wait; a crash must not wedge the registry forever |

**Every failure direction is now safe in both senses:** a live holder is never
displaced before the ceiling, and a crashed holder is reclaimed no later than
the ceiling.

---

## 4. Stale-lock recovery matrix

| Scenario | Before correction | After correction |
|---|---|---|
| Live holder, lock 10 s old | Refuse | Refuse |
| Live holder, lock 40 s old | Break ← **wrong** | **Refuse** |
| Holder pid recycled from a crash, 40 s old | Refuse forever ← **wedged** | **Refuse**, then break at 300 s |
| Holder pid never existed, 40 s old | Refuse until ceiling | **Break** — provably abandoned |
| Holder pid never existed, 400 s old | Break | Break |
| Malformed / pid-less lock, 40 s old | Break at ceiling | Refuse, break at ceiling |
| Two contenders reclaiming one orphan | 1 wins | 1 wins; registry consistent, no leaked lock |

---

## 5. PID reuse — the ambiguous case, addressed explicitly

The task asked for this case "where safely reproducible". It is the *normal*
case on Windows, not an edge case, and it is what §2 measured.

**Handling:** a resolvable pid is classified `indeterminate`, never `alive`.
That means a crashed holder whose pid has been reused is **not** stolen
immediately, but is reclaimed at the ceiling. The cost is a bounded 300 s delay
after a crash; the benefit is never displacing a live holder.

**Residual risk, stated plainly:** after 300 s, a lock whose holder is *genuinely
still running* would be broken. The guarded operation is a small file rewrite
(milliseconds), so holding it for over 300 s requires the holder to be
pathologically stalled. The residual window is real and is **not** closed by this
implementation.

---

## 6. The correct long-term fix — not implemented here

The residual risk in §5 exists because a **lockfile with a PID cannot be made
crash-safe**: the OS gives no trustworthy "is this pid alive" answer that
distinguishes recycling.

The proper mechanism is an **OS-native advisory lock**, which the OS releases
automatically when the process dies — including on a crash, with no PID
heuristics at all:

| Platform | Mechanism | Crash behaviour |
|---|---|---|
| POSIX | `fcntl.flock(fd, LOCK_EX \| LOCK_NB)` | Released by the kernel on process death |
| Windows | `msvcrt.locking(fd, LK_NBLCK, n)` or `LockFileEx` via `ctypes` | Released by the OS on handle close / process death |

**This is strictly better than anything PID heuristics can achieve**: no stale
locks, no staleness thresholds, no ceilings, no PID-reuse ambiguity, and
crash-safety by construction.

**Not implemented in this phase.** It requires a platform branch, careful
handling of file-descriptor lifetimes, and a compatibility shim for callers that
currently rely on the lockfile. It is proposed here for owner approval.

**Migration note.** The lockfile scheme is interoperable with nothing; nothing
outside `_consume_reservations` reads it. Replacing it is therefore a contained
change with a small blast radius — the timing is the owner's call, not a
technical constraint.

---

## 7. POSIX: not tested, not claimed

| Requirement | Status |
|---|---|
| Independent-process contention on POSIX | **Not run** |
| `ProcessLookupError` branch on POSIX | **Not run** — handled in code, untested |
| `O_EXCL` semantics on POSIX filesystems | **Not run** |

**This host has no POSIX environment.** No WSL, container, or remote runner was
available in this phase. Claiming POSIX correctness without a run would be
inventing evidence.

The POSIX-relevant difference is narrow and known: on POSIX a terminated pid
raises `ProcessLookupError`, which the code classifies as **`gone`** — a
*stronger* signal than Windows provides. The `gone` branch is therefore the
better-tested path conceptually, but it remains **untested on POSIX**.

**Required before claiming cross-platform safety:** one CI run on Linux and one
on macOS.

---

## 8. Summary

The Phase 57 liveness-first policy contained a defect that would have made a
crashed lock permanently unreclaimable on Windows. It is corrected, the false
confidence in the Phase 57 recovery test is documented, and the residual
300-second window is stated rather than hidden.

**The proper fix — OS-native advisory locking — is proposed, not implemented.**
Single-use enforcement for reserved evaluations remains unresolved and is
handled in `RESERVED_EVALUATION_CONSUMPTION_DESIGN.md`.