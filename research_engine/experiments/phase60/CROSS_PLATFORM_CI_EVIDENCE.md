# Phase 60 — Cross-Platform CI Evidence

**Date:** 2026-10-09

> **Bottom line: there is no cross-platform CI evidence, because the workflow
> has never run.** This is stated as a fact established by querying the remote,
> not as an assumption.

---

## 1. Access actually available

| Route | Result |
|---|---|
| `gh` CLI | **Installed** (`C:\Program Files\GitHub CLI\gh.exe`) but **not authenticated** — `gh auth status` returns *"You are not logged into any GitHub hosts"* |
| GitHub REST API, unauthenticated | **Available** — repository `Cyber1king/crypto-paper-trader` is **public** (`"private": false`) |
| Push / trigger a run | **Not attempted** — forbidden by rules 9 and 11 |

Read-only inspection of public API data was therefore available and was used.

---

## 2. Remote state — measured

### 2.1 Workflows GitHub knows about

```
GET /repos/Cyber1king/crypto-paper-trader/actions/workflows

Baseline Backtest          id=364285919  state=active  .github/workflows/baseline-backtest.yml
Research Engine Checks     id=364257480  state=active  .github/workflows/research-checks.yml
Yearly Backtest            id=366733207  state=active  .github/workflows/yearly-backtest.yml
```

**Three workflows. `reservation-locking.yml` is not among them** — the file is
untracked and has never been pushed, so GitHub has never seen it.

### 2.2 Workflow runs

```
GET /repos/Cyber1king/crypto-paper-trader/actions/runs?per_page=100
total_count = 26

Baseline Backtest           9 runs   latest 2026-09-28T11:30:19Z   conclusion=success
Research Engine Checks     16 runs   latest 2026-09-28T11:26:57Z   conclusion=success
Yearly Backtest             1 run    latest 2026-09-25T07:03:01Z   conclusion=success

Runs matching "*Reservation*": NONE
```

### 2.3 Commit coverage

**[V] The 26 runs span 21 distinct head SHAs, none of which is the local
`HEAD`.** Local `HEAD` is `dccebbd53ee8365474345506db9099b13356b53c`; the most
recent remote run is on `84a65b132df4847b9f20716124cbc72b93132693`
(2026-09-28), *"Implement tests for broker fee and slippage calculations"*.

**So remote CI has never run against the locking code at all** — not the Phase
55–59 safeguards, not the Phase 59 redesign, not the workflow itself.

---

## 3. Platform evidence table

| Platform | Tests executed? | Evidence | Verdict |
|---|---|---|---|
| **Windows 11 / CPython 3.12.10** | **Yes, locally** | Full suite **2533 passed**, exit 0, uninterrupted | ✅ **Verified on Windows** |
| **Linux** | **No** | None. No runner, container or VM available | ❌ **Unverified** |
| **macOS** | **No** | None | ❌ **Unverified** |
| **Windows (CI)** | **No** | Workflow never run | ❌ **Unverified** |
| **Linux (CI)** | **No** | Workflow never run | ❌ **Unverified** |
| **macOS (CI)** | **No** | Workflow never run | ❌ **Unverified** |

**No POSIX behaviour is claimed.** Local Windows testing is **not**
cross-platform verification, and is not presented as such.

---

## 4. What the local Windows run does and does not establish

**Establishes:** the `msvcrt.locking` branch works; contention, crash recovery
and guard behaviour are correct on this platform; the full suite passes.

**Does not establish:**

- That `fcntl.flock` behaves equivalently. The POSIX branch is written and
  reviewed but **has never executed**.
- That the workflow is syntactically accepted by Actions, that its steps resolve,
  or that any matrix leg passes.
- Anything about macOS-specific filesystem or descriptor semantics.

**One structural argument, offered as reasoning and not as evidence:** the new
design eliminated the PID heuristic entirely. Phase 58 found that on Windows a
terminated pid still resolves, so the old design's `ProcessLookupError` branch
could only be exercised on POSIX. With OS-native locking, no pid is inspected at
all, so the POSIX and Windows paths are now **structurally identical** — differing
only in which stdlib call takes the lock. That reduces the risk of a POSIX-only
defect; it does not remove the need to run it.

---

## 5. Historical remote context

**[V] Every prior run succeeded** — 9/9, 16/16, 1/1. The repository's existing
CI has a clean record on the code it covers.

**[V] All prior runs are `workflow_dispatch`**; no existing workflow triggers
automatically. The new workflow would be the first with a `push` trigger, so it
would also be the first to run unattended.

---

## 6. Exact action required to obtain remote evidence

Obtaining it **requires owner authorization**, because rule 9 forbids triggering
a workflow by pushing and rule 11 requires stopping at that boundary.

**Option 1 — push the workflow (recommended).** It carries a `push` trigger on
`main` with a path filter matching the workflow file and the locking code, so
committing it will start all three legs automatically.

```
git add .github/workflows/reservation-locking.yml \
        research_engine/src/crypto_paper_lab/researchguard.py \
        research_engine/tests/test_registry_locking.py \
        research_engine/tests/test_crash_recovery.py
git commit -m "Add cross-platform reservation-locking CI"
git push origin main
```

Then record the run URL and per-platform results.

**Option 2 — authenticate `gh` and dispatch without a path match**

```
gh auth login
gh workflow run reservation-locking.yml
```

**Required to proceed: explicit owner authorization to push or to authenticate
and dispatch.** Neither was performed. Nothing was pushed, committed or
triggered.

**What closes the gap:** three green matrix legs on the commit that contains the
locking code, with the post-test integrity step passing on each.