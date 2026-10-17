# Phase 60 Verification

**Date:** 2026-10-09

---

## 1. Baseline (Step 1)

**[V] Git:** `main` · `HEAD` `dccebbd53ee8365474345506db9099b13356b53c` ==
`origin/main` · ahead/behind **0/0** · staged **0** · 19 tracked modified ·
374 untracked.

**[V] Stop-condition checks — passed:**

```
ETH SHA-256 : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
status/used/prereg : RESERVED False None
VERDICT            : INTACT - proceed
```

**[V] Phase 59 deliverables:** 7 present. Workflow at
`.github/workflows/reservation-locking.yml`.

**[V] Runtime:** Windows 11 (10.0) AMD64 · CPython 3.12.10.

---

## 2. Workflow review (Step 2)

**[V] One genuine defect found and fixed.**

**`python - <<'PY'` is bash syntax; `windows-latest` defaults to PowerShell.**
The Windows leg would have failed at **step 4 of 6**, before the test suite,
producing a failure unrelated to locking and supplying **zero** Windows evidence.

Why it was new: all three pre-existing workflows are `runs-on: ubuntu-latest`,
so their heredocs have always run under bash. This is the first workflow pairing a
Windows runner with a heredoc.

**Fix:** `shell: bash` on the two affected steps (Git Bash ships with Windows
runners). Plus `permissions: contents: read`.

**[V] Post-fix validation:** YAML parses; matrix `windows-latest, ubuntu-latest,
macos-latest`; 6 steps; 2 pinned to bash; **zero** backtest/optimisation
references; unrelated workflows untouched (`git status` shows only the new file).

**[V] Not reproduced on a real runner** — the fix rests on documented shell
semantics, and is not claimed as observed.

---

## 3. CI evidence (Step 3)

**[V] Access:** `gh` installed but **not authenticated**. Unauthenticated
public API **was** available; the repository is public.

**[V] Measured remote state:**

```
Workflows GitHub knows : 3 — Baseline Backtest, Research Engine Checks,
                               Yearly Backtest
reservation-locking.yml: NOT PRESENT (untracked, never pushed)
Total runs             : 26
  Baseline Backtest      9   latest 2026-09-28   success
  Research Engine Checks 16   latest 2026-09-28   success
  Yearly Backtest        1    latest 2026-09-25   success
Runs matching "*Reservation*": NONE
```

**[V] None of the 21 distinct remote head SHAs is the local `HEAD`.** Remote CI
has never run against the locking code at all.

**[V] Platform status:** Windows **verified locally** (2533 passed). **Linux and
macOS unverified** — no local environment, no CI run. **No POSIX claim is made.**

**[V] Nothing was pushed, committed, or triggered.** Rule 11 observed: obtaining
remote evidence requires owner authorization, so it was reported rather than
attempted.

---

## 4. Failure analysis (Step 4)

| Category | Count |
|---|---|
| Workflow defects | **1** (plus 1 hardening) |
| Product defects | **0** |
| Test defects | **0** |
| Test failures during local runs | **0** |

Prior-phase defects recorded for continuity: **six product defects** (Phases 55–59)
and **seven test defects** (Phases 55–59), all resolved. Every product defect
caused **over-refusal or unrecoverable state**, never under-protection.

The most instructive: a malformed-registry read in Phase 59 that looked like an
`os.replace` defect was **the test's own non-atomic `write_text`**. Correcting
the setup made the symptom vanish.

**No assertion was weakened to obtain a green run.**

---

## 5. Local regression tests (Step 7)

**[V] Locking, guard and schema suites**

```bash
cd research_engine
python -X utf8 -m pytest tests/test_registry_locking.py tests/test_crash_recovery.py \
  tests/test_cross_process_guard.py tests/test_reservation_single_use.py \
  tests/test_research_guard.py tests/test_research_gaps.py tests/test_registry_schema.py \
  -q --no-header -p no:cacheprovider --tb=short
```

```
241 passed in 28.03s      exit code 0
```

**[V] Full suite**

```bash
python -X utf8 -m pytest tests -q --no-header -p no:cacheprovider --tb=line
```

```
2533 passed in 1934.05s (0:32:14)      exit code 0
```

**Uninterrupted.** The Phase 57–58 `KeyboardInterrupt` did not recur, under
direct invocation with no `Start-Process` wrapper.

**[V] No test accessed reserved-period performance.** Every locking and crash
test builds a synthetic registry under `tmp_path`; two assert the real registry
is byte-identical afterwards.

---

## 6. Decisions (Steps 5–6)

**[V]** B1–B9 register produced with evidence / recommendation / approval /
blocker separated for each. **Nothing selected, approved or invented.**

**[V]** B10 and B11 audited. **B10: 1 of 12 verified, 11 unmet. B11: 0 of 9.**
Hash functions that exist but have no recorded value are counted **UNMET**.

---

## 7. Final integrity (Step 8)

**[V] ETH dataset SHA-256, recomputed after all work:**

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation:**

```
status             : RESERVED
used               : False
preregistration_id : None
consumption keys   : []
VERDICT            : INTACT
```

| Check | Result |
|---|---|
| Frozen artifacts unchanged | `data/BTCUSDT_1h_Cleaned (1).csv` prefix `201a3b15…` **unchanged** |
| Historical results unchanged | No earlier phase report rewritten or deleted |
| No backtest / optimisation / reserved inspection | Confirmed |
| No freeze, no ID, no authorisation | Confirmed |
| Nothing staged, committed or pushed | **staged 0**; `HEAD` unchanged |

---

## 8. Absolute rules observed

| Rule | Observed |
|---|---|
| Inspect Git state before acting | Yes |
| Preserve user changes and historical reports | Yes |
| Never reset, clean, delete, overwrite | Yes |
| Never modify frozen datasets or results | Yes — verified |
| Never run backtests / optimisation / reserved analysis | Yes |
| Never consume the reservation | Yes — verified |
| Never invent CI results, approvals, legal conclusions, results | Yes — CI reported as unverified |
| Do not select a licence or decide thresholds | Yes — options only |
| Do not stage, commit, push, merge, publish, trigger by pushing | **Yes — nothing triggered** |
| Read-only CI inspection where authorized | Yes — public API only, `gh` unauthenticated |
| **If remote CI requires a push, stop and report** | **Yes — reported in `CROSS_PLATFORM_CI_EVIDENCE.md` §6** |
| Sequential; report failures honestly | Yes |

---

## 9. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `CI_WORKFLOW_REVIEW.md` | Requirement-by-requirement review; two fixes |
| 2 | `CROSS_PLATFORM_CI_EVIDENCE.md` | Access, measured remote state, platform table, exact action needed |
| 3 | `FAILURE_ANALYSIS.md` | Windows heredoc defect; full failure ledger across Phases 55–60 |
| 4 | `OWNER_DECISION_REGISTER.md` | B1–B9 with evidence / recommendation / blocker |
| 5 | `B10_B11_READINESS_AUDIT.md` | 12 + 9 conditions with status and dependencies |
| 6 | `VERIFICATION.md` | This document |

**[V]** All earlier phase reports preserved.

---

## 10. Verdict

# `PARTIAL — CI OR GOVERNANCE GAPS REMAIN`

Reviewing the workflow rather than merely running it found a defect that would
have destroyed the Windows leg before a single test executed — the one platform
where local evidence already exists. That was fixed.

Remote CI is **definitively unverified**, and now provably so rather than
assumed: GitHub knows three workflows, not four, and has 26 runs, none on this
code. Obtaining the evidence requires a push, which is your call alone.

Local evidence is strong: **2533 tests pass, exit 0, uninterrupted**, including
every locking and crash scenario on Windows.

**Eleven B10 prerequisites and all nine B11 conditions remain unmet. Nothing is
frozen, no ID is assigned, and evaluation is not authorised.**