# Phase 59 — B10 / B11 Readiness Audit

**Date:** 2026-10-09

> **A proposal or draft is not evidence of completion.** Where a deliverable
> merely *describes* something (a hash, a checklist, a plan), the condition is
> recorded as **UNMET**, not as partially satisfied.

## Status vocabulary

| Label | Meaning |
|---|---|
| ✅ **EVIDENCE VERIFIED** | Checked against the repository this phase |
| ⬜ **UNMET** | No decision or artefact exists |
| 🔒 **OWNER APPROVAL** | Requires a signature — **none exists** |

---

## B10 — Preregistration freeze: 12 prerequisites

| # | Exact requirement | Evidence location | Verification status | Owner decision | Blocking dependencies |
|---|---|---|---|---|---|
| 1 | B5 minimum trade count + adequacy rule | `phase59/OWNER_DECISION_SHEET.md` B5 | ⬜ **UNMET** — no number, no method | Number + method | None — pure decision |
| 2 | B6 four uncertainty parameters | same, B6 | ⬜ **UNMET** — none set | 4 values | None — pure decision |
| 3 | B7 decision rule and bar | same, B7 | ⬜ **UNMET** — framework proposed, bar absent | Bar + level | None — pure decision |
| 4 | B8 cross-asset approver and date | same, B8 | ⬜ **UNMET** — no approver named | Name + date | None — pure decision |
| 5 | `config_hash` recorded | `walkforward.config_hash` | ⬜ **UNMET** — function exists, **no value recorded** | — | #1–#4 (config must be final) |
| 6 | `costs_hash` recorded | `walkforward.costs_hash` | ⬜ **UNMET** — function exists, **no value recorded** | — | #1–#4 |
| 7 | `dataset_fingerprint` recorded | `walkforward.dataset_fingerprint` | ⬜ **UNMET** — derivable, **not captured** | — | Must be captured at freeze |
| 8 | Window and warm-up split confirmed | reservation entry | ✅ **EVIDENCE VERIFIED** — 17,544 warm-up (idx 0–17543), 6,744 evaluation (idx 17544–24287), 2026-01-01 → 2026-10-08; matches registry | — | None |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | `researchguard.py` | ⬜ **UNMET** — mechanism verified to reject incomplete records; **no record exists** | Approver from #4 | #4 |
| 10 | `assert_clean_working_tree()` passes | `walkforward.py` | ⬜ **UNMET** — tree intentionally dirty (19 modified, untracked work) | Commit or stash | — |
| 11 | Reservation updated with the preregistration ID | `research_registry.json` | ⬜ **UNMET** — no ID exists; registry deliberately unchanged | ID assignment | #1–#7, #10 |
| 12 | B11 authorisation obtained | below | ⬜ **UNMET** | Separate authorisation | All of B10 |

**Verified complete: 1 of 12** (#8).

**Explicitly not counted as satisfied:** items 5, 6 and 7. The *functions* exist
and are tested, but no value has been captured. A hash nobody recorded is not a
recorded hash. Item 11 likewise: the registry is unchanged, which is the
correct current state, not a partial completion.

---

## B11 — Evaluation authorisation: 9 conditions

**STATUS: CLOSED. NOT GRANTED. NO CONDITION APPROVED.**

| # | Exact requirement | Evidence location | Verification status | Owner decision | Blocking dependencies |
|---|---|---|---|---|---|
| 1 | Preregistration frozen with an assigned ID | registry | ⬜ **UNMET** | ID | All B10 |
| 2 | B5–B8 closed and recorded | decision sheet | ⬜ **UNMET** — all four open | 4 decisions | None |
| 3 | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | — | ⬜ **UNMET** | — | B10 #5–#7 |
| 4 | `CrossAssetAuthorization` complete and validated | `researchguard.py` | ⬜ **UNMET** | Approver | B8 |
| 5 | Reservation carries the preregistration ID | `research_registry.json` | ⬜ **UNMET** — `null` | — | B10 #11 |
| 6 | `assert_clean_working_tree()` passes | `walkforward.py` | ⬜ **UNMET** | — | B10 #10 |
| 7 | B1–B4 resolved or explicitly waived | `OWNER_DECISION_SHEET.md` | ⬜ **UNMET** — B1 open, B2 blocked on evidence capture, B3 signature-ready, B4 open | 4 decisions | None |
| 8 | Named evaluator and date | — | ⬜ **UNMET** — none named | Name + date | None |
| 9 | Explicit statement that **one** evaluation is authorised, consumed **immediately after the run and before any result is read** | — | ⬜ **UNMET** — no authorisation exists | Authorisation | #1–#8 |

**Verified complete: 0 of 9.**

### Why condition 9 is worded precisely

The risk is not the first run — it is the moment **after a disappointing result**,
when re-running a variant is tempting. `RESERVED` does not prevent that;
`run_backtest` never auto-consumes; nothing in the engine prevents it. Condition
9 makes the consumption protocol a written commitment rather than an intention.

---

## Guard state backing these conditions

| Property | Status |
|---|---|
| Exactly one of N concurrent consumers wins (N = 2, 4, 6) | ✅ Verified |
| Winner's `used_preregistration_id` recorded; loser's never | ✅ Verified |
| Duplicate sequential consumption refused | ✅ Verified (Phase 55) |
| Holder killed → lock released by the OS → next consumer proceeds at once | ✅ Verified (Phase 59) |
| Live holder's lock never stolen, at any age | ✅ Verified (Phase 59) |
| Interrupted writes preserve registry validity | ✅ Verified (Phase 59) |
| Registry never partially written; `used` ⇔ `status` | ✅ Verified |
| **Single-use without caller discipline** | ⚠️ **Not enforced** — design in `RESERVED_EVALUATION_DESIGN.md`, awaiting approval |

---

## Ordering

```
B1 B2 B3 B4  ─┐
B5            │
B6            ├─► B10 FREEZE ─► B8 record ─► B11 AUTHORISE ─► EVALUATE
B7            │      (12 prereq)    (validated)   (9 conditions)
B9            ┘
```

B5, B6 and B7 must close **before** the freeze: each is a number that must not
depend on a result not yet in existence. **Freezing does not authorise running.**

---

## Summary

| Gate | Requirements | Verified | Unmet | Owner approvals |
|---|---|---|---|---|
| **B10** | 12 | **1** | **11** | **0** |
| **B11** | 9 | **0** | **9** | **0** |

**The protocol is not frozen. No ID is assigned. Evaluation is not authorised.**