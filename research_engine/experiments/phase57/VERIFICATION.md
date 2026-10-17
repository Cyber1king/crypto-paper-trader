# Phase 57 Verification

**Date:** 2026-10-09

---

## 1. Baseline (Step 1)

**[V] Git**

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Upstream | `origin/main` @ same commit |
| Ahead / behind | **0 / 0** |
| Staged | **0** |
| Tracked modified | 19 |
| Untracked | 351 |

**[V] Stop-condition checks at baseline — both passed:**

```
ETH SHA-256 : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
status/used/prereg : RESERVED False None
consumption keys   : []
VERDICT            : INTACT - proceed
```

**[V] Phase 56 deliverables** — all 6 present: `FINAL_READINESS_AUDIT.md`,
`LICENSING_AND_PROVENANCE.md`, `OWNER_DECISION_REGISTER.md`,
`PREREGISTRATION_DRAFT.md`, `RESERVATION_HARDENING.md`, `VERIFICATION.md`.

---

## 2. Code changes

**[V] Two product defects found by cross-process testing, both fixed in
`researchguard.py`:**

| # | Defect | Impact | Fix |
|---|---|---|---|
| 1 | `_lock_holder_state` used `os` with no `os` in scope (`os` was imported only inside `_registry_lock`) | `NameError` on every stale-lock path instead of `ResearchGuardError` | Local `import os` added |
| 2 | A non-`FileExistsError` `OSError` while creating the lock propagated raw | Breaks the guard's fail-closed contract — callers catching `ResearchGuardError` would see an unhandled error | Converted to `ResearchGuardError` with reason preserved |

**Neither was reachable from the Phase 56 thread tests.** Both were found only by
cross-process and fail-closed testing.

**[V] Deliberate behaviour change — stale-lock policy.** Age-only breaking was
replaced with liveness-first:

| | Phase 56 | Phase 57 |
|---|---|---|
| ≤ 30 s | never broken | never broken (unchanged) |
| > 30 s, holder **alive** | broken ← the defect | **never broken** |
| > 30 s, holder **indeterminate** | broken | **kept until 300 s ceiling** |
| > 30 s, holder **dead** | broken | broken (unchanged) |

Added `_lock_holder_state()` returning `alive` / `dead` / `indeterminate`, and
`_REGISTRY_LOCK_HARD_CEILING_SECONDS = 300.0`.

**[V] No public signature changed.** `consume_reservation`, `run_backtest`,
`ResearchContext`, `assert_evaluation_permitted` untouched. No established
workflow altered.

**[V] New test file:** `tests/test_cross_process_guard.py` (11 tests).

---

## 3. Cross-process evidence

**[V] All run against independent OS processes** (`multiprocessing` spawn),
released through a gate file. Two distinct PIDs asserted.

| Test | Result |
|---|---|
| 2 processes race 1 reservation | **passed** (1.08 s) |
| Winning preregistration recorded, not overwritten | **passed** (1.11 s) |
| 4 processes race 1 reservation | **passed** (1.47 s) |
| Distinct reservations never corrupt the registry | **passed** (0.68 s) |
| Real ETH reservation untouched | **passed** (0.86 s) |
| Read failure fails closed | **passed** |
| Lock uncreatable fails closed | **passed** |
| Live holder's lock never stolen | **passed** |
| Indeterminate holder blocks until ceiling, then breaks | **passed** |
| Malformed lock treated as unknown, not dead | **passed** |
| Young lock never broken | **passed** |

**[V] A hypothesis of mine was wrong, and the test showed it.** I expected
`os.kill(pid, 0)` to be unsafe on Windows. Probing this process's own pid and
then continuing to execute **proved it does not terminate the target** on
CPython 3.12.10 / Windows. The more consequential finding was that a
**non-existent** pid raises a generic `OSError`, **not** `ProcessLookupError` —
so a naive implementation would either break live locks or wedge the registry.
Both are now avoided by the three-way result.

---

## 4. Test results (Step 8)

**[V] Commands and results:**

```bash
# Governance regression, non-spawning
python -X utf8 -m pytest tests/test_registry_locking.py tests/test_reservation_single_use.py \
  tests/test_research_guard.py tests/test_research_gaps.py tests/test_registry_schema.py \
  -q --no-header -p no:cacheprovider
#   226 passed in 12.49s
```

**[V] Coverage achieved by batching** — every one of the 47 test files executed:

| Batch | Result |
|---|---|
| acquisition, ai_research, analysis, api_account, api_health, api_market | **267 passed** |
| api_replay, api_session, api_signal, api_statistics, config_request_policy | **324 passed** |
| backtest, strategy, walkforward, yearly, experiment, simulator | **70 passed** |
| data_pipeline, dataset, dataset_validation, oos_dataset, daily_target | **253 passed** |
| entry_filters, entry_time_features, execution_model, execution_policy, exit_rules, evidence_schema | **278 passed** |
| high_risk, manual_paper, mode_contracts, modes, phase14c*, phase15*, robustness, windowstats, validation_boundary, analysis, acquisition, ai_research, research_gates | **961 passed** |
| api_account, api_health, api_market, api_replay, replay, replay_lifecycle, research_api | **496 passed** |
| Cross-process guard (11 tests, run individually) | **11 passed** |

**Failures across all batches: 0.**

**[V] A full single-command run was attempted and interrupted** by the harness:
`598 passed in 179.57s`, then `KeyboardInterrupt` in
`_pytest/raises.py`. Several other attempts produced `KeyboardInterrupt` inside
unrelated frames (`re/_parser.py`, `multiprocessing/popen_spawn_win32.py`).

**This is a harness artefact, not a product defect** — the interrupts landed in
modules unrelated to the lock, and plain invocation of the same tests passes.
Coverage was therefore completed by batching. **I am not claiming a single
uninterrupted full-suite green run in this phase.**

**[V] Two genuine test failures occurred and were fixed honestly:**

1. My `test_distinct_processes_consume_distinct_reservations` assumed both
   distinct reservations would be consumed concurrently. They are not — the lock
   **fails closed with no wait**, so the second process is refused. **My
   assumption was wrong**, not the code. Rewritten to assert the safety property
   (consistent registry, no partial spend, ≥1 success), and the availability
   limitation is documented.
2. `test_stale_lock_is_broken_and_removed` (Phase 56) **genuinely failed** after
   the policy change, because it encoded the old age-only semantics. Replaced by
   two tests: refusal while indeterminate, and break past the ceiling.

**[V] Safeguards exercised:** duplicate consumption, concurrent consumption (2
and 4 processes), live-holder lock protection, stale/indeterminate/young lock
handling, malformed lock, unreadable registry, uncreatable lock, registry
consistency, real-ETH-untouched.

**[V] No backtest, optimisation or reserved-period analysis ran.** The reserved
ETH CSV was never opened by any test — only `exists()` is asserted.

---

## 5. Final integrity (Step 9)

**[V] ETH dataset SHA-256, recomputed after all work:**

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation:**

```
status            : RESERVED
used              : False
preregistration_id: None
consumption keys  : []
VERDICT           : INTACT
```

**[V] Confirmed:** no frozen artifact changed (`data/BTCUSDT_1h_Cleaned (1).csv`
prefix `201a3b15…` unchanged); no backtest or evaluation ran; no final
preregistration ID assigned; nothing staged, committed or pushed (staged 0).

**[V] Git:**

```
HEAD   dccebbd53ee8365474345506db9099b13356b53c  (unchanged, == origin/main)
staged 0
?? research_engine/src/crypto_paper_lab/researchguard.py   (pre-existing untracked)
?? research_engine/tests/test_cross_process_guard.py       (Phase 57, new)
?? research_engine/tests/test_registry_locking.py           (Phase 56)
?? research_engine/experiments/phase57/                     (6 deliverables)
```

---

## 6. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `OWNER_SIGNOFF_SHEET.md` | B1–B3 with evidence, options, consequences, exact approval wording |
| 2 | `CROSS_PROCESS_SAFEGUARD_AUDIT.md` | Real multi-process evidence, two defects, stale-lock investigation, claim boundaries |
| 3 | `ECB_PROVENANCE_PLAN.md` | Reproducible recovery plan; requirements for new acquisition; guarantee boundary |
| 4 | `RESEARCH_DECISION_REGISTER.md` | B5–B9 with structures recommended, values left open |
| 5 | `AUTHORIZATION_GATE_CHECKLIST.md` | B10 12 prerequisites, B11 9 conditions, verified vs proposed vs unmet |
| 6 | `VERIFICATION.md` | This document |

**[V]** No earlier phase report was rewritten or deleted.

---

## 7. Strict rules observed

| Rule | Observed |
|---|---|
| Inspect repo state before changing | Yes — baseline + direct code inspection |
| Preserve existing modifications and historical reports | Yes |
| Never reset, clean, delete, overwrite unrelated work | Yes |
| Never run backtests / optimisation / reserved-period analysis | Yes |
| Never consume the ETH reservation | Yes — verified |
| Never change frozen datasets or historical results | Yes — verified |
| Never choose a licence or legal position | Yes — options only |
| Never invent approvals, thresholds, evidence, results | Yes |
| Never stage, commit, push, publish | Yes — staged 0 |
| Run sequentially, report failures honestly | Yes — 2 test failures recorded and fixed, harness interrupts disclosed |
| No additional numbered phases | Yes — only `phase57/` |
| No freeze, no ID, no authorisation | Yes |

---

## 8. Verdict

# `PARTIAL — SAFEGUARD GAPS REMAIN`

The cross-process contention risk that Phase 56 could not exclude is now
**verified closed** with real multi-process evidence, and two genuine defects it
exposed were fixed.

The verdict is not `READY FOR OWNER SIGN-OFF` because three items remain
unresolved and two of them are safety-relevant:

1. **Single-use is still not enforced.** `run_backtest` never auto-consumes.
   Protocol discipline is still the only guarantee. A bounded-wait/consume-on-
   completion proposal exists but needs owner approval.
2. **Cross-platform evidence does not exist.** All results are Windows /
   CPython 3.12.10. The POSIX `ProcessLookupError` branch is handled but
   untested.
3. **True crash-safety is untested** — no simulation of process death or
   filesystem failure mid-write.

None of these blocks an owner decision, and none is a data-integrity risk to the
reserved window, which remains provably intact. They are engineering gaps that
should be closed before the reservation is ever consumed.