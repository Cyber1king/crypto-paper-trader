# Phase 60 — B10 / B11 Readiness Audit

**Date:** 2026-10-09

> **A draft or planned hash is not a recorded, approved protocol value.** Where
> a deliverable merely *describes* something, the condition is **UNMET**.

| Label | Meaning |
|---|---|
| ✅ **EVIDENCE VERIFIED** | Checked against the repository this phase |
| ⬜ **UNMET** | No decision or artefact exists |
| 🔒 **OWNER APPROVAL** | Requires a signature — **none exists** |

---

## B10 — Preregistration freeze: 12 prerequisites

| # | Exact requirement | Evidence location | Status | Owner decision | Dependencies |
|---|---|---|---|---|---|
| 1 | B5 minimum trade count + adequacy rule | `phase60/OWNER_DECISION_REGISTER.md` B5 | ⬜ UNMET | Number + method | None — pure decision |
| 2 | B6 four uncertainty parameters | same, B6 | ⬜ UNMET | 4 values | None — pure decision |
| 3 | B7 decision rule and bar | same, B7 | ⬜ UNMET | Bar + level | None — pure decision |
| 4 | B8 cross-asset approver and date | same, B8 | ⬜ UNMET | Name + date | None — pure decision |
| 5 | `config_hash` recorded | `walkforward.config_hash` | ⬜ UNMET — **function exists, no value recorded** | — | #1–#4 |
| 6 | `costs_hash` recorded | `walkforward.costs_hash` | ⬜ UNMET — **function exists, no value recorded** | — | #1–#4 |
| 7 | `dataset_fingerprint` recorded | `walkforward.dataset_fingerprint` | ⬜ UNMET — derivable, **not captured** | — | Capture at freeze |
| 8 | Window and warm-up split confirmed | reservation entry | ✅ **VERIFIED** — 17,544 warm-up (idx 0–17543), 6,744 evaluation (idx 17544–24287), 2026-01-01 → 2026-10-08 | — | None |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | `researchguard.py` | ⬜ UNMET — **rejection of incomplete records verified; no record exists** | Approver from #4 | #4 |
| 10 | `assert_clean_working_tree()` passes | `walkforward.py` | ⬜ UNMET — tree intentionally dirty (19 modified + untracked) | Commit or stash | — |
| 11 | Reservation updated with preregistration ID | `research_registry.json` | ⬜ UNMET — no ID; registry deliberately unchanged | ID assignment | #1–#7, #10 |
| 12 | B11 authorisation obtained | below | ⬜ UNMET | Separate authorisation | All B10 |

**Verified: 1 of 12** (#8). **Unmet: 11.**

**Explicitly not counted as satisfied.** Items 5, 6 and 7: the functions exist
and are tested, but **no value has been captured**. A hash nobody recorded is
not a recorded hash. Item 11: the registry being unchanged is the *correct
current state*, not partial progress.

---

## B11 — Evaluation authorisation: 9 conditions

**STATUS: CLOSED. NOT GRANTED. NO CONDITION APPROVED.**

| # | Exact requirement | Evidence location | Status | Owner decision | Dependencies |
|---|---|---|---|---|---|
| 1 | Preregistration frozen with an assigned ID | registry | ⬜ UNMET | ID | All B10 |
| 2 | B5–B8 closed and recorded | decision register | ⬜ UNMET — all four open | 4 decisions | None |
| 3 | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | — | ⬜ UNMET | — | B10 #5–#7 |
| 4 | `CrossAssetAuthorization` complete and validated | `researchguard.py` | ⬜ UNMET | Approver | B8 |
| 5 | Reservation carries the preregistration ID | registry | ⬜ UNMET — `null` | — | B10 #11 |
| 6 | `assert_clean_working_tree()` passes | `walkforward.py` | ⬜ UNMET | — | B10 #10 |
| 7 | B1–B4 resolved or explicitly waived | decision register | ⬜ UNMET — B1 open · B2 blocked on evidence capture · B3 signature-ready · B4 open | 4 decisions | None |
| 8 | Named evaluator and date | — | ⬜ UNMET — none named | Name + date | None |
| 9 | Explicit statement that **one** evaluation is authorised, consumed **immediately after the run and before any result is read** | — | ⬜ UNMET | Authorisation | #1–#8 |

**Verified: 0 of 9. Unmet: 9.**

### Why condition 9 is worded this way

The risk is not the first run — it is the moment **after a disappointing
result**, when re-running a variant is tempting. `RESERVED` does not prevent it;
`run_backtest` never auto-consumes; nothing in the engine prevents it. Condition
9 converts the consumption protocol from an intention into a written commitment.

The design that would enforce it (`consume_on_completion`) is specified in
`phase59/RESERVED_EVALUATION_DESIGN.md` and **not implemented** — it changes a
public API and needs owner authority.

---

## Safeguards backing these conditions

| Property | Status | Evidence |
|---|---|---|
| Exactly one of N concurrent consumers wins (N = 2, 4, 6) | ✅ Verified | Windows, local |
| Winner's `used_preregistration_id` recorded; loser's never | ✅ Verified | Windows, local |
| Duplicate sequential consumption refused | ✅ Verified | Phase 55 |
| Holder killed → OS releases lock → next consumer proceeds at once | ✅ Verified | Phase 59 |
| Live holder's lock never stolen, any age | ✅ Verified | Phase 59 |
| Interrupted writes preserve registry validity | ✅ Verified | Phase 59 |
| Permission/replacement failures fail closed | ✅ Verified | Phase 59 |
| Concurrent readers never see malformed JSON | ✅ Verified | Phase 59 |
| Registry never partially written; `used` ⇔ `status` | ✅ Verified | Phases 59–60 |
| **Single-use without caller discipline** | ⚠️ **Not enforced** | Design pending approval |
| **POSIX / macOS behaviour** | ❌ **Unverified** | CI never run |

---

## Summary

| Gate | Requirements | Verified | Unmet | Owner approvals |
|---|---|---|---|---|
| **B10** | 12 | **1** | **11** | **0** |
| **B11** | 9 | **0** | **9** | **0** |

**The protocol is not frozen. No ID is assigned. Evaluation is not authorised.**

---

## Ordering

```
B1 B2 B3 B4  ─┐
B5            │
B6            ├─► B10 FREEZE ─► B8 record ─► B11 AUTHORISE ─► EVALUATE
B7            │     (12 prereq)    (validated)   (9 conditions)
B9            ┘
```

B5, B6 and B7 must close **before** the freeze: each is a number that must not
depend on a result not yet in existence. **Freezing does not authorise running.**