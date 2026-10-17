# Phase 67 — B11 Authorization Audit

**Prerequisites:** authoritative 9-item list at
`experiments/phase57/AUTHORIZATION_GATE_CHECKLIST.md` (verified: 21 rows - 12 B10 = 9).
**Safety check at start:** ETH checksum MATCH; reservation `RESERVED/false/null`.

> **Evaluation is NOT authorised. No person nominated. No approval recorded.**

## 1. Condition audit

| # | Requirement | Status | Evidence required | Existing evidence | Owner/approver action | Dependencies | Independently verifiable? |
|---|---|---|---|---|---|---|---|
| 1 | Preregistration frozen with an assigned ID | BLOCKED | A frozen protocol and an assigned ID | Assign after B10 clears | All B10 | No |
| 2 | B5-B8 closed and recorded | BLOCKED | Four recorded owner decisions | Supply 4 decisions | None | No |
| 3 | config_hash, costs_hash, dataset_fingerprint recorded | BLOCKED | Three recorded, approved hashes | Record after #2 | B10 #5-#7 | No |
| 4 | CrossAssetAuthorization complete and validated | BLOCKED | Complete record incl. approver identity | Supply approver | B8 | No |
| 5 | Reservation carries the preregistration ID | BLOCKED | Registry updated with the ID | - | B10 #11 | No |
| 6 | assert_clean_working_tree() passes | UNMET | Clean working tree | Commit or stash | None | Yes, but owner-only |
| 7 | B1-B4 resolved or explicitly waived | PARTLY ADVANCED | Four resolutions or waivers | Resolve or waive | None | Partly - B2 evidence captured |
| 8 | Named evaluator and date | OWNER DECISION REQUIRED | A name and a date | Name | None | No |
| 9 | Written one-evaluation authorisation | OWNER DECISION REQUIRED | Written authority + consumption protocol | Authorise | #1-#8 | No |

## 2. Tally

| Status | Count | Items |
|---|---|---|
| VERIFIED | **0** | - |
| BLOCKED | 5 | #1, #2, #3, #4, #5 |
| UNMET | 1 | #6 |
| PARTLY ADVANCED | 1 | #7 |
| OWNER DECISION REQUIRED | 2 | #8, #9 |
| **Total** | **9** | - |

**0 of 9 verified. Unchanged.**

## 3. Three distinct roles

| Role | Gate | Function | Status |
|---|---|---|---|
| Cross-asset approver | B8 / #4 | Accepts the research claim that a BTC-labelled config transfers to ETH; must have read the frozen protocol | No identity, approval or date exists |
| Evaluator | #8 | Executes the authorised evaluation | No identity or date exists |
| Authorising party | #9 | Grants one-evaluation authority and the consumption protocol | Not granted |

**[V]** The guard mechanically prevents skipping #4 - an incomplete
authorization record causes a refusal. **Nothing mechanically prevents skipping
#8**; it is a protocol obligation.

**[V] No project document defines an independence requirement or separation of
duties** between these roles. Recorded as unresolved; not invented here.

## 4. Precise blockers

| # | Blocker | Cleared by | Type |
|---|---|---|---|
| 1 | B5-B8 all open | Four owner decisions | Judgement |
| 2 | No preregistration ID; protocol not frozen | B10 completion | Governed state |
| 3 | Protocol hashes not computed or recorded | After B5-B8 | Governed state |
| 4 | No cross-asset authorization record | B8 | Identity |
| 5 | Reservation carries no ID | After freeze | Governed state |
| 6 | Working tree dirty (19 modified, 402 untracked) | Commit or stash | Repository action |
| 7 | B1-B4 not all resolved | B1, B3, B4 decisions (B2 evidence ready) | Judgement |
| 8 | No named evaluator | Owner names | Identity |
| 9 | No written authorisation | Owner authorises | Authorisation |

## 5. What must NOT be inferred as authorisation

| Signal | Why insufficient |
|---|---|
| B2 evidence capture | Closes an input to #7. Authorises nothing |
| Passing tests | Verifies code, not permission |
| Matching ETH checksum | Data integrity, not consent |
| Signature-ready briefs | Readiness is not approval |
| A preregistration draft | A draft is not a frozen protocol |
| A validated record *format* | An unpopulated record is not an approval |

**No such signal exists in the current state in any case - all nine remain
unmet or blocked.**
