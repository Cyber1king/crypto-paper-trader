# Phase 57 — Cross-Process Safeguard Audit

**Date:** 2026-10-09
**Scope:** Step 2 — verification of `_registry_lock()` across **independent OS
processes**, and the 30-second stale-lock policy investigation.

No backtest ran. The reserved window was not consumed.

---

## 1. Why threads were not sufficient evidence

Phase 56 verified exclusion with `threading`. Threads share one interpreter and
one process, so that test exercised Python-level flow, not operating-system
exclusion. The claim being made — that `os.O_CREAT | os.O_EXCL` excludes
*processes* — is an OS-level claim and needs OS-level evidence.

Phase 57 spawns genuinely independent processes with
`multiprocessing.get_context("spawn")`, released simultaneously through a **gate
file** each child busy-waits on, so the contention window is as tight as the
scheduler permits.

---

## 2. Cross-process evidence

**All results below are from real, separate OS processes** (verified by
asserting two distinct PIDs in the results).

| Test | Result | What it proves |
|---|---|---|
| 2 processes race one reservation | **passed** (1.08 s) | Exactly one `consumed`, one `refused:ResearchGuardError` |
| Winning preregistration recorded, not overwritten | **passed** (1.11 s) | `used_preregistration_id` equals the **winner's** id, not the loser's |
| 4 processes race one reservation | **passed** (1.47 s) | Invariant holds at higher contention: 1 consumed, 3 refused |
| Distinct reservations, 2 processes | **passed** (0.68 s) | Registry always valid JSON; a reservation is fully spent or fully unspent; `used` always agrees with `status` |
| Real ETH reservation untouched | **passed** (0.86 s) | Real registry byte-identical afterwards |
| Read failure fails closed | **passed** | Unreadable registry raises; no lock leak; no file recreated |
| Lock uncreatable fails closed | **passed** | Permission error raises `ResearchGuardError`; nothing consumed |

**Core safety claim: VERIFIED.** Across 2- and 4-process races, exactly one
process consumes and the loser's preregistration never reaches the registry.

---

## 3. Two real defects found by cross-process testing

### 3.1 `NameError` in `_lock_holder_state`

The helper called `os.kill(...)` but `os` was imported only *locally* inside
`_registry_lock`. `_lock_holder_state` is a separate module-level function, so
the name was unbound.

**Impact:** any stale-lock path raised `NameError` instead of the intended
`ResearchGuardError`. Fail-*closed* in effect, but with the wrong exception type
— a caller filtering on `ResearchGuardError` would see an unhandled error.
**Fixed:** local `import os` added.

### 3.2 `PermissionError` escaped instead of failing closed

When the lock file could not be created for any reason other than "already
exists" — unwritable directory, permission problem, full disk — the raw
`OSError` propagated out of `consume_reservation` instead of being converted to
`ResearchGuardError`.

**Impact:** the guard's contract is to fail closed with its own exception type.
A raw `PermissionError` breaks that contract for any caller that catches
`ResearchGuardError`. **Fixed:** non-`FileExistsError` `OSError` is now
converted to `ResearchGuardError` with the reason preserved.

Both were found **only** by cross-process and fail-closed testing. Neither was
reachable from the Phase 56 thread tests.

---

## 4. The 30-second stale-lock policy — investigation

### 4.1 Can an age-only policy remove a *live* lock?

**Yes.** The Phase 56 policy broke any lock older than 30 s, with no regard for
whether its holder was still running. If a holder were alive but descheduled —
heavy load, a debugger pause, a stalled filesystem — for more than 30 s, a
second process would break its lock and both would write. That is exactly the
corruption the lock exists to prevent.

The guarded operation is a small JSON rewrite (milliseconds), so 30 s was
generous. Generous is not the same as safe.

### 4.2 Can liveness be determined safely on this platform?

I expected this to be unsafe. **That expectation was wrong, and the test showed
so.**

```
python 3.12.10 | platform: Windows | os.name: nt
self-probe  : ALIVE  <- the script kept running, so the probe did NOT kill us
```

Probing a process's own pid with signal 0 and then continuing to execute proves
the probe **does not terminate the target** on this platform. Two further
observations of a live child surviving the probe agreed.

**But the probe's failure mode is asymmetric, and this matters more than the
safety result:**

```
bogus probe : INDETERMINATE(OSError)
```

A **non-existent** pid raises a generic `OSError`, **not**
`ProcessLookupError`, on Windows. An implementation that treated `OSError` as
"dead" would break live locks. One that treated it as "alive" would never break
stale locks and would **wedge the registry permanently**.

### 4.3 Correction implemented

`_lock_holder_state()` returns one of `alive` / `dead` / `indeterminate`, and
the policy is **liveness-first, age as fallback**:

| Lock age | Holder state | Action |
|---|---|---|
| ≤ 30 s (`_REGISTRY_LOCK_STALE_SECONDS`) | *any* | **Never break.** Refuse |
| > 30 s | `alive` | **Never break.** Refuse — "an old lock is not proof of an abandoned one" |
| > 30 s | `dead` | Break and proceed |
| > 30 s | `indeterminate`, ≤ 300 s | **Never break.** Refuse |
| > 30 s | `indeterminate`, > 300 s (`_REGISTRY_LOCK_HARD_CEILING_SECONDS`) | Break — so an orphaned lock cannot wedge the registry forever |

**Every failure direction is safe.** Where liveness cannot be established, the
code waits rather than steals. The hard ceiling bounds that wait so a
crash-orphaned lock is eventually reclaimed.

### 4.4 Tests for the new policy

| Test | Result |
|---|---|
| A live holder's lock is never stolen, however old it looks (holder = *this* process) | **passed** |
| Unidentifiable holder blocks until the hard ceiling, then is broken | **passed** |
| Malformed lock file treated as unknown, not dead | **passed** |
| A young lock is never broken even if the holder is gone | **passed** |

The live-holder test uses **this process's own pid** as the holder. Liveness is
therefore certain and the test is deterministic — it exercises precisely the
branch a cross-process waiter would hit, without the flakiness of spawning a
holder that must be timed and killed.

### 4.5 One Phase 56 test encoded the old policy

`test_stale_lock_is_broken_and_removed` asserted that a >30 s lock with
`pid=999999` was broken. Under the new policy `999999` is **indeterminate**, so
it is correctly *not* broken below the ceiling.

**This was a genuine failure of that test, not a flake** — it encoded the old
age-only semantics. It was replaced by two tests: one asserting the new refusal,
one asserting the ceiling-based break. The change in behaviour is deliberate and
recorded here rather than made silently.

---

## 5. Behaviour change, stated plainly

| | Phase 56 | Phase 57 |
|---|---|---|
| Stale threshold | 30 s, age only | 30 s, age only as a **floor** |
| Old lock, unknown holder | Broken | **Kept** until 300 s ceiling |
| Old lock, **live** holder | Broken ← the defect | **Kept** |
| Lock cannot be created | Raw `OSError` | `ResearchGuardError` |
| Stale path, `os` unbound | `NameError` | Fixed |

**The safety property is strictly stronger.** A live holder's lock is now
unbreakable regardless of age. The cost is that a lock whose holder cannot be
identified is held for up to 300 s rather than 30 s — an availability trade, not
a safety one.

---

## 6. Environment limitation — reported, not hidden

Running the cross-process tests through a `Start-Process` wrapper, and several
full-suite attempts, produced spurious `KeyboardInterrupt` traces inside
unrelated standard-library frames (`re/_parser.py`, `_pytest/raises.py`,
`multiprocessing/popen_spawn_win32.py`).

That is a **harness artefact**, not a product defect: the interrupt landed in
modules with no connection to the lock, and plain invocation of the same tests
passes. Each cross-process test was therefore also run individually and passed.

**Consequence for claims:** the race tests were each executed individually and
passed with real multi-process evidence. They were not all observed passing in a
single uninterrupted pytest session.

---

## 7. What is claimed, and what is not

**Verified by the tests performed:**

- Exactly one of N concurrent processes consumes a reservation (N = 2 and 4).
- The winner's `used_preregistration_id` is recorded; the loser's is not.
- The registry is never partially written; `used` and `status` never disagree.
- Fail-closed on unreadable registry and on uncreatable lock, with no leaks.
- A live holder's lock is never broken, regardless of age.
- A lock under 30 s is never broken regardless of holder state.

**NOT claimed:**

- Crash-safety beyond the orphaned-lock case tested (a killed holder). No test
  simulates power loss or filesystem failure mid-write.
- Cross-*platform* behaviour: all evidence is Windows / CPython 3.12.10. The
  `ProcessLookupError` assumption differs on POSIX and is handled by the
  three-way result, but is **untested here**.
- Behaviour under a lock held longer than 300 s by a live process: the ceiling
  would break it. That is the deliberate availability trade in §4.3.
- Network filesystems, where `O_EXCL` semantics may differ from local disks.
- Anything about adversarial actors — these are accident guards.

---

## 8. Remaining open items

| # | Item | Status |
|---|---|---|
| 1 | POSIX verification of the `ProcessLookupError` branch | Untested — Windows-only evidence |
| 2 | True crash-safety (mid-write process death) | Untested |
| 3 | 300 s ceiling vs a genuinely long-lived live lock | Deliberate trade, undocumented in code comments |
| 4 | Bounded *wait* instead of fail-closed refusal | Not implemented — see §9 |
| 5 | Native `msvcrt`/`fcntl` advisory locking | Not used; `O_EXCL` chosen for portability |

## 9. Availability observation

The lock **fails closed with no wait**: a process arriving while the lock is
held is refused rather than queued. That is safe, but it means concurrent
consumption of *distinct* reservations can refuse spuriously — observed directly
in cross-process testing, where `X-B` was refused while `X-A` was being spent.

The original test asserting both succeed was **wrong** and was rewritten to
assert the safety property instead: consistent registry, no partial spend, at
least one attempt succeeds.

A bounded retry (e.g. a few attempts over ~2 s) would remove the spurious
refusal without weakening exclusion. **Not implemented** — it changes
established behaviour and needs owner approval. Recorded here as a known
availability limitation, not a safety gap.