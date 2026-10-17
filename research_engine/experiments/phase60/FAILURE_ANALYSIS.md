# Phase 60 — Failure Analysis

**Date:** 2026-10-09

---

## 1. Failure found by workflow review: Windows heredoc

**Classification: WORKFLOW DEFECT — confirmed by inspection, fixed, not yet
reproduced on the real runner.**

### Exact error it would produce

```
windows-latest default shell is PowerShell
run block:  python - <<'PY'
             ...
           PY

PowerShell: The '<' operator is reserved for future use.
```

### Root cause

Two steps use the bash heredoc `<<'PY'`. GitHub Actions sets `pwsh` as the
default shell on Windows runners, where that syntax is invalid.

### Why it was not caught earlier

All three pre-existing workflows are `runs-on: ubuntu-latest`. Their heredocs
have always executed under bash. This is the **first** workflow to pair a
Windows runner with a heredoc, so the defect is new to this file.

### Blast radius if unfixed

The Windows leg fails at **step 4 of 6** — before the test suite ever runs. It
would produce a red X caused by a shell mismatch, supply **zero** Windows CI
evidence, and misrepresent the locking design as broken when it is not.

### Fix

```yaml
- name: Report the locking backend under test
  shell: bash
- name: Confirm the reserved ETH window is untouched by the tests
  shell: bash
```

Git Bash ships with `windows-latest` runners, so this is a one-line change per
step with no rewrite of the scripts.

### Residual uncertainty

**Not reproduced.** The fix is based on documented Actions shell semantics, not
on an observed failure. It is verified only when a Windows leg actually runs.

---

## 2. Failure found by review: inherited permissions

**Classification: WORKFLOW DEFECT — hardened.**

No `permissions:` block meant the workflow inherited the repository default.
Added `permissions: contents: read`; the job only checks out code and runs tests.

Not a failure — a hardening. Recorded because the review asked for it.

---

## 3. Product defects found in earlier phases, for continuity

Recorded so the ledger is complete. **None is outstanding.**

| Phase | Defect | Classification | Resolution |
|---|---|---|---|
| 55 | `consume_reservation` accepted duplicate consumption and overwrote `used_preregistration_id` | **Product** | Duplicate rejection added; audit record preserved byte for byte |
| 56 | `O_CREAT\|O_EXCL` race — two processes could both write | **Product** | Inter-process locking added (later replaced, see below) |
| 57 | `_lock_holder_state` used `os` with no `os` in scope → `NameError` on every stale-lock path | **Product** | Local `import os` added |
| 57 | Non-`FileExistsError` `OSError` escaped instead of failing closed | **Product** | Converted to `ResearchGuardError` |
| 58 | A killed, reaped pid still resolves on Windows → crashed holder's lock permanently unreclaimable | **Product** | Liveness inference removed entirely |
| 59 | Sentinel design required two arbitrary time constants and an unanswerable PID heuristic | **Product** | Replaced with OS-native advisory locking; constants and heuristic deleted |

**A pattern worth naming.** Every one of these caused **over-refusal or
unrecoverable state**, never under-protection. The guard failed safe each time.

---

## 4. Test defects found and fixed in earlier phases

Also for completeness. **All were in test code, never in the product, and no
assertion was weakened to obtain a green result.**

| Phase | Symptom | Real cause | Fix |
|---|---|---|---|
| 55 | `test_consumption_…` raised `"not in the registry"` | `consume_reservation` resolves the reservation before checking for a writable target | Corrected the test to use the real reservation id |
| 57 | `test_distinct_processes…` expected both to succeed | Lock fails closed with **no wait** | Rewritten to assert the safety property |
| 58 | `test_stale_lock_is_broken_…` DID NOT RAISE | Encoded the old age-only semantics | Replaced with refusal + ceiling tests |
| 59 | `test_atomic_replace_failure_…` "lock leaked" | Obsolete — sidecar now persists by design | Assert the lock is **free**, not absent — a stronger check |
| 59 | Reader saw 1 malformed registry | **The test's own `write_text`**, which truncates and is not atomic | Seed via `tmp + os.replace`; read became clean |
| 59 | `test_unlocked_sidecar_…` FileNotFoundError | Missing directory in my test | Created it |
| 59 | Reader `reads == 0` | Windows: writer holds the file throughout | Baseline reads before the writer starts |
| 60 | — | — | No test failures this phase |

**The most instructive of these is the malformed-registry read.** It looked like
a product defect in `os.replace` and was actually the test measuring its own
non-atomic setup. Correcting the setup made the symptom vanish — which is what
established that the product's write path was sound.

---

## 5. Environmental issues (not failures of the code)

| Issue | Evidence | Status |
|---|---|---|
| `KeyboardInterrupt` injected into pytest (Phases 57–58) | Landed in `re/_parser.py`, `pathlib.py`, `_pytest/raises.py`, `popen_spawn_win32.py` — no project frame | **Did not recur.** Phase 59 and 60 full suites completed uninterrupted |
| `Start-Process -Wait` wrapper aggravates it | Wrapped runs truncated; direct invocation completed | **Avoided** — all Phase 59/60 runs used direct invocation |
| No POSIX environment | `fcntl` unavailable; no WSL/container/runner | **Unresolved** — requires CI |

---

## 6. Failures in this phase

| Source | Count | Detail |
|---|---|---|
| Workflow defects | **1** (plus 1 hardening) | Windows heredoc — fixed, not yet reproduced |
| Product defects | **0** | — |
| Test defects | **0** | — |
| Test failures during local runs | **0** | 241 passed (locking/guard/schema); 2533 passed (full suite) |

**No test failed in this phase.** The single substantive finding came from
*reviewing* the workflow, not from running it — which is precisely the value of
reading before shipping.

---

## 7. What would count as evidence that the Windows fix worked

A green `windows-latest` leg on the locking commit, with:

1. `lock API : msvcrt.locking (Windows)` printed in the backend step;
2. the seven suites passing;
3. `ETH reservation intact: RESERVED / used=false / preregistration_id=null`
   printed by the final step.

**Until that exists, the fix is argued from documented behaviour, not observed.**
It is expected to be correct, and it is not claimed as verified.