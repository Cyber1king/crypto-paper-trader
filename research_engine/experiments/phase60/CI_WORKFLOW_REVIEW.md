# Phase 60 — CI Workflow Review

**Date:** 2026-10-09
**Target:** `.github/workflows/reservation-locking.yml`
**Reviewed against:** Phase 59 deliverable, repo conventions, and the actual
remote state of the repository.

---

## 1. Requirement-by-requirement review

| Requirement | Status | Evidence |
|---|---|---|
| Windows, Linux and macOS jobs configured | ✅ | `matrix.os: [windows-latest, ubuntu-latest, macos-latest]`, `fail-fast: false` |
| Python versions appropriate | ✅ | `3.11`, matching `research-checks.yml` and `pyproject.toml` `requires-python = ">=3.11"` |
| Each platform runs the intended tests | ✅ *(after fix)* | The seven locking/guard suites, listed explicitly |
| Failures fail the workflow | ✅ | `pytest` exits non-zero on failure; `set -e` is the shell default; no `continue-on-error` anywhere |
| No step runs a backtest or optimisation | ✅ | Zero occurrences of "backtest" or "optimi" in any step |
| No step consumes the real ETH reservation | ✅ | The suites use `tmp_path` synthetic registries; a post-test step **asserts** the reservation is unchanged |
| Final check verifies checksum and reservation state | ✅ | Re-computes the ETH SHA-256; asserts `RESERVED` / `used: false` / `preregistration_id: null` / no `used_on` |
| Temporary registries isolated from the real one | ✅ | Every test builds its registry under `tmp_path`; two tests assert the real registry is byte-identical afterwards |
| Permissions no broader than necessary | ✅ *(added)* | `permissions: contents: read` |

---

## 2. Genuine defect found and fixed

### 2.1 The workflow would have failed on Windows before running any test

**The defect.** Two steps use bash heredocs:

```yaml
run: |
  python - <<'PY'
  ...
PY
```

`<<'PY'` is **bash** syntax. On `windows-latest` the default shell is
**PowerShell**, where this is a parse error.

**Why it was missed.** All three pre-existing workflows are `runs-on:
ubuntu-latest`, so their heredocs have always run under bash and never surfaced
the issue. This is the first workflow in the repository to mix a Windows runner
with bash heredocs — the defect is new **to this workflow**, not inherited.

**Impact had it shipped.** The Windows leg would fail at *step 4*, before the
test suite, producing a failure that has nothing to do with locking and would
have supplied **zero** Windows evidence for the one platform we already have.

**Fix.** Pin the two affected steps to bash (Git Bash ships with Windows
runners):

```yaml
- name: Report the locking backend under test
  shell: bash
```

This is the minimal, evidence-based correction: the construct is unchanged, only
the interpreter for it is made explicit.

### 2.2 Permissions were inherited rather than declared

**The defect.** No `permissions:` block meant the workflow inherited whatever
the repository default is.

**Fix.** `permissions: contents: read` — the workflow only checks out code and
runs tests.

---

## 3. Repository conventions followed

| Convention | Source | Followed |
|---|---|---|
| `actions/checkout@v4` | `research-checks.yml` | Yes |
| `actions/setup-python@v5` | `research-checks.yml` | Yes |
| Python `"3.11"` | `research-checks.yml` | Yes |
| `working-directory: research_engine` | `research-checks.yml` | Yes |
| `pip install -e ".[dev]"` | `research-checks.yml` | Yes |
| **Not** running the full suite here | full suite already covered by `research-checks.yml` on Ubuntu | Yes |

**No unrelated workflow content was modified.** Verified: `git status` on
`.github/workflows/` shows only the new file as untracked.

---

## 4. Design choices worth noting

**Why one Python version.** The variable under test is the **OS locking API**,
not the interpreter. A 3-OS × 2-version matrix would double cost and add no
locking evidence.

**Why path-filtered `push`.** The job runs automatically only when locking code
or tests change — not on every unrelated commit. This matters because the
repository has **no automatic CI at all** today (see §5).

**Why the post-test integrity step.** It converts the governance invariant from a
convention into a **build check**: any test that ever consumed the reserved
window would fail all three legs.

**Why the backend-reporting step.** A failure log then states which mechanism
produced it — `msvcrt.locking (Windows)` or `fcntl.flock (POSIX)`.

---

## 5. Repository CI context — a material observation

**[V] All three existing workflows are `workflow_dispatch`-only.** Nothing runs
automatically on push.

**[V] Remote evidence:** 26 runs total — *Baseline Backtest* (9, latest
2026-09-28), *Research Engine Checks* (16, latest 2026-09-28), *Yearly Backtest*
(1, latest 2026-09-25). **All successful**, all `workflow_dispatch`.

**[V] GitHub currently knows 3 workflows.** `reservation-locking.yml` is **not**
among them.

**Implication.** This is the first workflow in the repository to run
automatically on push. That is desirable here — the locking code is exactly the
kind of change that should not reach `main` untested on three platforms — but it
is also a behavioural change to the repository's CI posture and should be a
conscious decision.

---

## 6. Post-fix validation

```
YAML parses OK
permissions   : {'contents': 'read'}
matrix os     : ['windows-latest', 'ubuntu-latest', 'macos-latest']
steps         : 6
  - Checkout repository                             shell=(default)
  - Set up Python                                   shell=(default)
  - Install dependencies                            shell=(default)
  - Report the locking backend under test           shell=bash
  - Locking, crash-recovery and guard tests         shell=(default)
  - Confirm the reserved ETH window is untouched    shell=bash
backtest/optimization references: 0
```

**Structural validity confirmed. Runtime behaviour is unverified** — see
`CROSS_PLATFORM_CI_EVIDENCE.md`.

---

## 7. Verdict on the workflow

**Structurally sound after two minimal, evidence-based fixes.** Both fixes were
required for correctness; neither was cosmetic.

**Not verified to run.** No execution has occurred on any platform, because the
file has never left this machine.