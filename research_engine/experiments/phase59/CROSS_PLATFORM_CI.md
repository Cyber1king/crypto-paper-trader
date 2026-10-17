# Phase 59 — Cross-Platform CI

**Date:** 2026-10-09

> **The workflow is configured but UNVERIFIED.** It has never been executed by
> GitHub Actions. No run exists, so no result is claimed for Linux or macOS.

---

## 1. What was added

`.github/workflows/reservation-locking.yml` — **not committed, not pushed.**

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [windows-latest, ubuntu-latest, macos-latest]
runs-on: ${{ matrix.os }}
```

| Choice | Rationale |
|---|---|
| Three OSes, **one** Python version (3.11) | Matches the existing `research-checks.yml`; the variable under test is the OS locking API, not the interpreter. Avoids an unnecessary matrix |
| `fail-fast: false` | A failure on one platform must not hide results on the others |
| `workflow_dispatch` + `push` on `paths:` | Matches the repo's existing trigger style; path filter means the job runs when locking code changes |
| `defaults.run.working-directory: research_engine` | Consistent with `research-checks.yml` |

**Structural validation performed locally:** the YAML parses, the matrix
resolves to the three expected runners, and six steps are present.

---

## 2. What it runs

```bash
python -m pytest \
  tests/test_registry_locking.py \
  tests/test_crash_recovery.py \
  tests/test_cross_process_guard.py \
  tests/test_reservation_single_use.py \
  tests/test_research_guard.py \
  tests/test_research_gaps.py \
  tests/test_registry_schema.py -v
```

These are exactly the suites that exercise reservation locking, cross-process
contention, crash recovery and the guard. They are **fast** (~30 s locally) and
spawn real independent processes, which is the point.

**Not run in this workflow:** the full engine suite. It is covered by
`research-checks.yml` on Ubuntu; duplicating a ~30-minute run across three
platforms would add cost without adding locking evidence.

---

## 3. Two extra steps

**3.1 Report the locking backend.** Prints the Python version, `os.name`, and
which API is under test — `msvcrt.locking (Windows)` or `fcntl.flock (POSIX)`.
A failure log then states which mechanism produced it.

**3.2 Assert the reserved window is untouched after the tests.** Re-verifies the
ETH dataset SHA-256 and that the reservation is still `RESERVED` / `used: false`
/ `preregistration_id: null` with **no `used_on` field**.

This makes the governance invariant a *CI check* rather than a convention: any
test that ever consumed the reserved window would fail the build on all three
platforms.

---

## 4. Cross-platform status — stated precisely

| Platform | Tests executed locally? | CI configured? | CI run completed? |
|---|---|---|---|
| **Windows 11 / CPython 3.12.10** | **Yes** — 2533 full suite, 0 failures | Yes | n/a (local) |
| **Linux** | **No** | Yes | **No** |
| **macOS** | **No** | Yes | **No** |

**No POSIX claim is made.** The `fcntl.flock` branch is written and reviewed but
**has never been executed**. Everything asserted about POSIX behaviour is
expectation, not evidence.

The relevant difference is narrow: on POSIX a terminated pid raises
`ProcessLookupError`, which the *previous* design treated as authoritative
"holder is gone". The **new** design no longer inspects pids at all, so that
difference has been **eliminated** — the POSIX path is now symmetric with the
Windows path rather than subtly different. That is a structural argument for
correctness, **not** a substitute for running the tests.

---

## 5. Repository conventions followed

| Convention | Source | Followed |
|---|---|---|
| `actions/checkout@v4` | `research-checks.yml` | Yes |
| `actions/setup-python@v5` | `research-checks.yml` | Yes |
| Python `"3.11"` | `research-checks.yml`, `pyproject.toml` `requires-python = ">=3.11"` | Yes |
| `working-directory: research_engine` | `research-checks.yml` | Yes |
| `pip install -e ".[dev]"` | `research-checks.yml` | Yes |

No new action versions, no new dependency, no unrelated workflow changes.

---

## 6. What running it would close

Running this workflow to completion would close the last cross-platform gap —
**E1** in `phase58/FINAL_READINESS_AUDIT.md`, carried forward as the single
remaining *critical* engineering gap after the locking redesign.

Until then, the honest position is: **locking is verified on one platform,
designed to be correct on three, and configured for three.**

---

## 7. Required next step

1. Review the workflow.
2. Push it (or run it via `workflow_dispatch`).
3. Confirm all three matrix legs are green.
4. Record the run URL.

**Until step 3 completes, this file is a configuration, not a result.**