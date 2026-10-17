# Phase 57 — Authorization Gate Checklist

**Date:** 2026-10-09
**Scope:** Step 7 — B10 freeze prerequisites and B11 authorization conditions.

> **Nothing is frozen. No preregistration ID is assigned. No evaluation is
> authorised.**

## Status vocabulary

Each condition carries exactly one of four labels. **Documentation existing is
never treated as a satisfied condition.**

| Label | Meaning |
|---|---|
| ✅ **EVIDENCE VERIFIED** | Independently checked against the repository in this phase |
| 🟡 **DECISION PROPOSED** | A recommendation exists; the owner has not decided |
| ⬜ **UNMET** | No decision, value or artefact exists |
| 🔒 **OWNER APPROVAL RECEIVED** | Recorded owner sign-off — **none exists for any condition** |

---

## B10 — Preregistration freeze: 12 prerequisites

| # | Prerequisite | Status | Evidence / blocker |
|---|---|---|---|
| 1 | B5 minimum trade count and adequacy rule | ⬜ **UNMET** | `OWNER_DECISION_REGISTER` B5 — no number, no method chosen |
| 2 | B6 block length, iterations, basis, confidence level | ⬜ **UNMET** | Four parameters, all unset |
| 3 | B7 decision rule and bar | ⬜ **UNMET** | Framework proposed; bar unset |
| 4 | B8 cross-asset approver and date | ⬜ **UNMET** | No approver named; **none invented** |
| 5 | `config_hash` recorded | ⬜ **UNMET** | Requires a frozen config; dependent on #1–#4 |
| 6 | `costs_hash` recorded | ⬜ **UNMET** | Requires the frozen cost set; dependent on #1–#4 |
| 7 | `dataset_fingerprint` recorded | 🟡 **DECISION PROPOSED** | Fingerprint derivable, but must be captured **at freeze**, not pre-recorded |
| 8 | Evaluation window and warm-up split confirmed against the reservation | ✅ **EVIDENCE VERIFIED** | 17,544 warm-up bars (idx 0–17543); 6,744 evaluation bars (idx 17544–24287); 2026-01-01 → 2026-10-08. Matches reservation |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | ⬜ **UNMET** | Blocked on #4. `from_record()` rejects incomplete records — verified in Phase 56 |
| 10 | `assert_clean_working_tree()` passes | ⬜ **UNMET** | Working tree is intentionally dirty (19 modified + untracked). Must be clean at freeze |
| 11 | Reservation updated with the preregistration ID | ⬜ **UNMET** | No ID exists; registry deliberately unchanged |
| 12 | B11 authorisation obtained (separate, explicit) | ⬜ **UNMET** | See below. **Freezing does not authorise running** |

**Verified complete: 1 of 12.** One condition (#8) is factually settled; it does
not depend on an owner decision.

**Explicitly NOT satisfied by documentation:** items 5, 6, 7 and 11 exist as
*concepts* in the Phase 56 draft, but none has been produced. A draft that
*describes* a hash is not a recorded hash.

---

## B11 — Evaluation authorisation: 9 conditions

**STATUS: CLOSED. NOT GRANTED. NO CONDITION IS APPROVED.**

| # | Condition | Status | Evidence / blocker |
|---|---|---|---|
| 1 | Preregistration frozen with an assigned ID | ⬜ **UNMET** | Blocked on all of B10 |
| 2 | B5–B8 closed and recorded | ⬜ **UNMET** | All four OPEN |
| 3 | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | ⬜ **UNMET** | B10 #5–#7 |
| 4 | `CrossAssetAuthorization` complete and validated | ⬜ **UNMET** | B10 #9; B8 approver unnamed |
| 5 | Reservation carries the preregistration ID | ⬜ **UNMET** | Registry unchanged: `RESERVED` / `false` / `null` |
| 6 | `assert_clean_working_tree()` passes | ⬜ **UNMET** | Tree intentionally dirty |
| 7 | B1–B4 governance items resolved or explicitly waived | ⬜ **UNMET** | B1 open · B2 awaiting ECB capture · B3 awaiting signature · B4 open |
| 8 | Named evaluator and date | ⬜ **UNMET** | None named |
| 9 | Explicit statement that **one** evaluation is authorised, to be consumed **immediately after the run and before any result is read** | ⬜ **UNMET** | No authorisation exists |

**Verified complete: 0 of 9.**

---

## Why condition 9 is worded that way

The dangerous moment is not the first run — it is the moment **after a
disappointing result**, when re-running a variant becomes tempting. `RESERVED`
does not prevent that; nothing in the engine prevents a caller from simply not
calling `consume_reservation()`.

Phase 57's testing confirmed the surrounding mechanics are sound — exactly one of
N concurrent processes consumes, a live holder's lock cannot be stolen, refusal
is fail-closed — but **single-use remains a protocol obligation**, not an
enforced invariant. Condition 9 exists because that obligation needs a written
commitment, not only good intentions.

---

## Current verified state of the guard

| Property | Status |
|---|---|
| Exactly one of N concurrent processes consumes | ✅ Verified (N = 2 and 4, real OS processes) |
| Winner's `used_preregistration_id` recorded; loser's not | ✅ Verified |
| Registry never partially written; `used` agrees with `status` | ✅ Verified |
| Fail-closed on unreadable registry / uncreatable lock | ✅ Verified |
| A live holder's lock is never broken, regardless of age | ✅ Verified |
| A lock under 30 s is never broken | ✅ Verified |
| Duplicate sequential consumption refused | ✅ Verified (Phase 55) |
| **Single-use without caller discipline** | ⚠️ **Not enforced** — `run_backtest` never auto-consumes |

---

## Gate ordering

```
B1–B4 governance ─┐
B5 trade count ───┤
B6 uncertainty ───┼──► B10 FREEZE ──► B8 approver record ──► B11 AUTHORISE ──► EVALUATE
B7 decision rule ─┤        (12 prereqs)        (recorded)          (9 conditions)
B8 approver ──────┘
```

B5, B6 and B7 must all close **before** the freeze, because each is a number
whose value must not depend on a result that does not yet exist. B11 is
separate and last: **freezing does not authorise running.**

---

## Summary

| Gate | Prerequisites | Evidence verified | Decisions proposed | Owner approvals received |
|---|---|---|---|---|
| **B10** | 12 | **1** | 1 | **0** |
| **B11** | 9 | **0** | 0 | **0** |

**No condition anywhere in this checklist is approved.** The protocol is not
frozen, no ID is assigned, and evaluation is not authorised.