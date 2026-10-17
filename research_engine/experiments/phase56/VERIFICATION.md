# Phase 56 Verification

**Date:** 2026-10-09
**Remit:** combined governance, safeguard hardening and readiness.

---

## 1. Baseline (Part 1)

**[V] Git**

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Upstream | `origin/main` @ same commit |
| Ahead / behind | **0 / 0** |
| Staged | **0** |
| Tracked modified | 19 |
| Untracked | 344 |

**[V] Stop-condition checks at baseline — both passed, work proceeded:**

```
ETH SHA-256 : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
status      : RESERVED
used        : False
prereg      : None
consumption fields: []          (none introduced)
VERDICT     : INTACT - proceed
```

**[V] Phase 55 deliverables** — all 5 present: `RESERVATION_ENFORCEMENT_REVIEW.md`
(12,350 b), `GOVERNANCE_STATUS.md` (10,527 b), `OWNER_DECISION_GATE.md` (9,889 b),
`PREREGISTRATION_DRAFT.md` (12,894 b), `VERIFICATION.md` (10,705 b).

**[V] Phase 55 code changes audited, not assumed.** `researchguard.py` contained
the Phase 55 duplicate-consumption clause and `tests/test_reservation_single_use.py`
existed with 7 tests. Both confirmed by direct inspection before further edits.

---

## 2. Code changes (Parts 2, 3)

**[V] Two changes to `researchguard.py`, one new test file.**

| Change | Location | Purpose |
|---|---|---|
| Added `import time`, `from contextlib import contextmanager` | module imports | Lock support |
| Added `_REGISTRY_LOCK_SUFFIX = ".lock"`, `_REGISTRY_LOCK_STALE_SECONDS = 30.0` | module constants | Lock config |
| Added `_registry_lock(target)` context manager | new | **N1** — portable inter-process lock |
| Wrapped read-decide-write in `with _registry_lock(target):` | `_consume_reservations` | **N1** — closes the race |
| Rewrote the "Every attempt is recorded" docstring bullet | module docstring L29 | **N4** — accurate description |

**[V] No public signature changed.** `consume_reservation`, `run_backtest`,
`ResearchContext`, `assert_evaluation_permitted` and every existing caller are
untouched. No established behaviour was altered.

**[V] Structural verification after the edits:**

```
parse OK
import OK
lock suffix: .lock
stale secs : 30.0
already_spent blocks: 1   OK
touched blocks      : 1   OK
lock acquisitions   : 1   OK
```

Checked because the edit was a large in-place restructure; duplicated blocks
would have been a silent correctness hazard.

---

## 3. Test results (Part 7)

### Exact commands, exit codes and counts

**[V] Locking tests — new file**

```bash
cd research_engine
python -X utf8 -m pytest tests/test_registry_locking.py -q --no-header -p no:cacheprovider
```

```
11 passed in 0.30s
exit code: 0
```

**[V] Guard and schema regression**

```bash
python -X utf8 -m pytest tests/test_reservation_single_use.py tests/test_research_guard.py \
  tests/test_research_gaps.py tests/test_registry_schema.py -q --no-header -p no:cacheprovider
```

```
214 passed in 10.74s
exit code: 0
```

**[V] Full suite**

```bash
python -X utf8 -m pytest tests -q --no-header -p no:cacheprovider
```

```
2517 passed in 1872.71s (0:31:12)
exit code: 0
```

**Failures: 0. No test failed at any point in this phase.** (The one failure in
Phase 55 was in a test I had written, and was corrected there.)

**Accounting:** 2517 = 2499 baseline + 7 (Phase 55 single-use) + 11 (Phase 56
locking). **No regression** from the N1 lock or the N4 docstring change.

### Tests use synthetic data only

**[V] Every locking test uses a `tmp_path` registry** with synthetic
`LOCK-A` / `LOCK-B` reservations cloned from a real schema-valid template.

**[V] One test per file asserts the real reservation is untouched:**

```python
assert real["status"] == "RESERVED"
assert real["used"] is False
assert real["preregistration_id"] is None
assert "used_on" not in real
assert "used_preregistration_id" not in real
```

**[V] The reserved ETH CSV is never read by any test** — only `exists()` is
asserted. No test performs a backtest, parameter search or optimisation.

---

## 4. N1 findings

**[V] The race was real.** `os.replace` makes each write atomic, but
read-decide-write is not. Two processes could both read `used=false`, both pass
the Phase 55 duplicate check (which reads its own snapshot), and both write.

**[V] Phase 55's fix did not cover this** — it closes sequential re-spending,
not simultaneous attempts.

**[V] Fix verified:** a threaded test released by `threading.Barrier` produced
exactly one winner:

```
assert sorted(outcomes) == ["consumed", "refused"]
```

and the surviving `used_preregistration_id` belonged to that winner rather than
being a blend.

**[V] Limitation stated, not hidden:** staleness is judged by **age alone** (30 s).
No PID-liveness check, because a portable liveness test needs a platform branch
or a dependency. A live-but-descheduled holder could have its lock broken.
Accepted for a small file rewrite.

**[V] Not claimed:** cross-*process* safety is only argued from `O_EXCL` atomicity
and the threaded test. A `multiprocessing` test would be stronger evidence and is
listed as open.

---

## 5. Evaluation-without-consumption findings

**[V] All six engine entry points traced:**

| Module | Entry point | Guard | Consumes? |
|---|---|---|---|
| `backtest.py` | `run_backtest` (L65) | `assert_series_permitted` (L157) | **No** — `mark_used=False` (L180) |
| `experiment.py` | `run_experiment` (L16) | none directly | forwards (L39) |
| `yearly.py` | `run_yearly_backtests` (L24) | none directly | forwards (L52) |
| `walkforward.py` | `run_window` (L491), `walk_forward` (L616) | 2 calls | No |
| `replay.py` | replay session | `assert_series_permitted(series, research_context=None)` (L583) | No |
| `app.py` | 5 replay endpoints | via replay | No |

**[V] No entry point bypasses the guard.** Every path reaching the engine passes
through `run_backtest`'s unconditional check. `replay.py` deliberately passes
`research_context=None`, so replaying a reserved series is **refused**.

**[V] Two ways reserved data can be evaluated without consumption:** (1) a valid
`ResearchContext` supplied repeatedly, each call permitted, none consuming; (2)
a **consumed** series, deliberately permitted and marked
`consumed_series_development_use`.

**[V] Decision: documented, not changed.** Existing behaviour is correct and
deliberate. Auto-consuming would invert the documented rationale ("a window should
be spent by an evaluation, not by an attempt") and would break
`consumed_series_development_use`, which the dashboard and tests rely on. A
`consume_on_completion` proposal is documented in
`RESERVATION_HARDENING.md` §3.3 awaiting owner approval.

---

## 6. N4 correction

**[V] Claim found at L29:** *"Every attempt is recorded, including refused ones,
so a refusal cannot be silently repeated."*

**[V] Actual behaviour:** only **successful** consumption is persisted. A refusal
raises and leaves the registry untouched. Neither half of the original claim was
true — the second half (*"a refusal cannot be silently repeated"*) also failed,
since repeating a refusal simply raises again.

**[V] Corrected to an accurate description**, including the explicit statement
that no refusal is durable, and noting that an append-only attempt log was
considered and not built.

**[V] Why documentation and not a log:** the contract requires
*"evaluated once only"* — a property of successful spends. A refusal log would
add on-disk state, a new failure surface (what if the log write fails after the
registry write succeeds?), and a privacy question, without strengthening any
guarantee the design relies on.

---

## 7. Licensing and provenance status

**[V]** No licence selected. No registry state changed. No legal approval
claimed.

| Item | Status |
|---|---|
| **B1** | `OPEN` — A–E compared; scope facts verified; no selection |
| **B2** | Ready for approval — wording written; gap noted: ECB page not yet captured in-repo |
| **B3** | Ready for approval — evidence verified in-repo; transition `UNVERIFIED` → `VERIFIED` is schema-valid |
| **B4** | `OPEN` — the four evidence items and a five-step reproducible plan specified |

**[V] B4 core finding retained:** acquisition URLs carry **no `providers=ecb` pin**,
Frankfurter's default is to blend, and the stored JSON has no provider field.
**The stored values are not confirmed ECB-published observations**, and the
registry correction is presented as a terms correction, not a provenance
certification.

---

## 8. Final integrity (Part 8)

**[V] ETH dataset SHA-256, recomputed after all work:**

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation — field-by-field:**

```
status            : RESERVED          OK
used              : False             OK
preregistration_id: None              OK
used_on present   : False             OK
used_preregistration_id present : False OK
VERDICT           : INTACT
```

**No reservation-consumption fields were introduced.**

**[V] Frozen artifacts:** `data/BTCUSDT_1h_Cleaned (1).csv` prefix `201a3b15…`
**unchanged**; the combined OOS CSV unchanged; the ETH dataset **MATCH**.

**[V] Confirmed absent:** no backtest, no optimisation, no reserved-period
performance inspection, no frozen-byte modification, no SPDX headers in any CSV
or archive, no deletion, no reset, no cleanup.

**[V] Git:**

```
HEAD    dccebbd53ee8365474345506db9099b13356b53c  (unchanged, == origin/main)
staged  0
?? research_engine/src/crypto_paper_lab/researchguard.py   (pre-existing untracked file)
?? research_engine/tests/test_reservation_single_use.py     (Phase 55)
?? research_engine/tests/test_registry_locking.py           (Phase 56)
?? research_engine/experiments/phase56/                     (6 deliverables)
```

**Nothing staged, committed, pushed or published.** No earlier phase report was
rewritten.

---

## 9. Absolute rules observed

| Rule | Observed |
|---|---|
| 1. Inspect Git and Phase 55 before acting | Yes — baseline + direct code inspection |
| 2. Preserve user changes and historical records | Yes — no prior report modified |
| 3. Never reset, clean, delete, overwrite unrelated files | Yes |
| 4. Never modify frozen datasets, checksums, historical results | Yes — verified |
| 5. Never inspect reserved-period performance or run experiments | Yes |
| 6. Never consume the ETH reservation | Yes — verified |
| 7. Never invent decisions, permissions, approvals, results | Yes |
| 8. Do not choose a licence on the owner's behalf | Yes — options only |
| 9. Do not silently alter governed registry states | Yes — proposals only |
| 10. Never stage, commit, push, publish | Yes — staged 0 |
| 11. Preserve paper-only scope | Yes |
| 12. Execute sequentially; continue on failure | Yes — no step failed |
| 13. No additional numbered phases | Yes — only `phase56/` created |
| 14. Stop on consumed reservation / changed checksum / evaluation | Yes — checks passed, no stop |

---

## 10. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `RESERVATION_HARDENING.md` | N1 race, lock implementation, concurrency test, limitation; evaluation-without-consumption trace; N4 correction |
| 2 | `LICENSING_AND_PROVENANCE.md` | B1–B4; verified vs unverified separated; B4 plan |
| 3 | `OWNER_DECISION_REGISTER.md` | B5–B11 with options, trade-offs, exact input |
| 4 | `PREREGISTRATION_DRAFT.md` | Full unfrozen draft, 11 sections, OPEN markers |
| 5 | `FINAL_READINESS_AUDIT.md` | Consolidated readiness; blockers |
| 6 | `VERIFICATION.md` | This document |

**[V]** Phase 55's `PREREGISTRATION_DRAFT.md` is preserved unchanged; the Phase 56
draft supersedes it in structure without deleting it.

---

## 11. Verdict

# `READY FOR OWNER DECISIONS`

**This does not authorise an evaluation.** The reservation remains `RESERVED`,
no preregistration ID exists, and all gates remain open.