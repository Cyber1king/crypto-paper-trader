# Phase 68 — Cross-Platform CI Readiness

**Prerequisites:** `.github/workflows/reservation-locking.yml` (Phase 59);
repository CI conventions.
**Safety check at start:** no new blocker.
**Not published. Not triggered. No Git state altered.**

---

## 1. Configuration review — validated locally

| Check | Method | Result |
|---|---|---|
| YAML parses | `yaml.safe_load` | ✅ |
| Matrix OS | structure read | ✅ `windows-latest, ubuntu-latest, macos-latest` |
| `fail-fast` | structure read | ✅ `false` — one platform's failure won't hide others |
| Python version | structure read | ✅ `3.11` (matches `research-checks.yml`, `requires-python >=3.11`) |
| Permissions | structure read | ✅ **`contents: read`** (added Phase 61) |
| Windows shell compatibility | structure read | ✅ **two steps pinned `shell: bash`** (Phase 61 fix) |
| Steps | count | ✅ 6 |

### Step list

| Step | Shell |
|---|---|
| Checkout repository | default |
| Set up Python | default |
| Install dependencies | default |
| Report the locking backend under test | **bash** |
| Locking, crash-recovery and guard tests | default |
| Confirm the reserved ETH window is untouched | **bash** |

**[V] The `shell: bash` pinning is load-bearing.** `python - <<'PY'` is bash
syntax; `windows-latest` defaults to PowerShell. Without pinning, the Windows leg
would fail at step 4 of 6 **before running any test**. All three pre-existing
workflows are `ubuntu-latest`, which is why the issue was invisible before this
workflow.

---

## 2. Requirement checks

| Requirement | Status |
|---|---|
| Windows / Linux / macOS configured | ✅ |
| No backtest or optimisation step | ✅ **0** occurrences of "backtest"/"optimi" |
| Reservation isolated from tests | ✅ tests use `tmp_path` synthetic registries; two assert the real registry is byte-identical |
| ETH checksum asserted | ✅ post-test step recomputes the SHA-256 and asserts |
| Reservation state asserted | ✅ asserts `RESERVED` / `used is False` / `preregistration_id is None` / no `used_on` |
| Failure propagates | ✅ no `continue-on-error`; pytest exit code fails the job |
| Path filter | ✅ locking source + 4 test files + the workflow itself |
| Trigger | `workflow_dispatch` + `push` on `main` |

---

## 3. Platform evidence — stated precisely

| Platform | Tests executed? | CI run? | Verdict |
|---|---|---|---|
| **Windows 11 / CPython 3.12.10** | ✅ **Yes** — 2533 passed, exit 0 | n/a | **Verified** |
| **Linux** | ❌ No | ❌ Never | **UNVERIFIED** |
| **macOS** | ❌ No | ❌ Never | **UNVERIFIED** |

**[V] Remote state (queried Phase 60, unauthenticated public API):**
GitHub knows **3** workflows; `reservation-locking.yml` is **not** among them.
26 historical runs exist (Baseline Backtest 9, Research Engine Checks 16, Yearly
Backtest 1 — all `workflow_dispatch`, all success), **none** on the locking
commit.

> **Linux and macOS are UNVERIFIED. No claim of cross-platform coverage is made.**

**Structural argument, offered as reasoning and not evidence:** the Phase 59
redesign removed all PID inspection, so the POSIX and Windows paths now differ
only in which stdlib call takes the lock (`flock` vs `msvcrt.locking`). That
reduces divergence risk; it does not substitute for running it.

---

## 4. Publication checklist — NOT executed

| # | Step | State |
|---|---|---|
| 1 | Review the workflow | ⬜ Owner |
| 2 | Commit the workflow **plus** locking source and test files | ⬜ Owner |
| 3 | `git push origin main` — triggers all three legs via the path filter | ⬜ **Requires owner authorization** |
| 4 | Confirm all three matrix legs green | ⬜ |
| 5 | Record the run URL and per-platform results | ⬜ |
| 6 | Update `CROSS_PLATFORM_CI_EVIDENCE.md` | ⬜ |

**Note for the owner.** This would be the repository's **first workflow to
trigger automatically on push** — all three existing workflows are
`workflow_dispatch`-only. That is desirable for locking code, but it is a real
change in CI posture and should be a conscious decision.

**Nothing was committed, pushed or triggered in this batch.**

---

## 5. Findings

| # | Finding | Severity |
|---|---|---|
| 1 | POSIX branch never executed | **High** — the only untested critical surface |
| 2 | Workflow not on remote; no run exists | **High** — blocks any CI evidence |
| 3 | Would be the first auto-triggering workflow | Medium — owner decision |
| 4 | `shell: bash` dependency is subtle and undocumented in-repo | Low — now commented in the file |
| 5 | Windows reader/`os.replace` interaction can cause spurious failures | Low — fails closed; documented |

**No workflow defect was found in this phase.** The two defects found in earlier
phases (missing `shell: bash`, inherited permissions) were fixed there and are
confirmed fixed here.