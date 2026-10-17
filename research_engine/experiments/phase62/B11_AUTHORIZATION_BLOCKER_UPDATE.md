# Phase 62 — B11: Authorisation Blocker Update

**Status: `BLOCKED` — 0 of 9 VERIFIED. Evaluation NOT authorised.**
**No status was changed. No person was nominated. No approval was recorded.**

---

## 1. Authoritative list — re-verified

**Source:** `experiments/phase57/AUTHORIZATION_GATE_CHECKLIST.md`. **Exactly 9
items**, confirmed by row count this phase (21 total rows − 12 B10 = 9 B11).

---

## 2. Condition-by-condition

| # | Requirement | Status | Evidence required | Evidence path | Owner/approver action | Dependencies | Resolvable in Phase 62 without governed-state change? |
|---|---|---|---|---|---|---|---|
| **1** | Preregistration frozen with an assigned ID | **BLOCKED** | A frozen protocol and an assigned ID | none | Assign after B10 clears | All B10 | ❌ Requires a governed-state change |
| **2** | B5–B8 closed and recorded | **BLOCKED** | Four recorded owner decisions | `phase61/B5…B8` | Supply 4 decisions | None | ❌ Requires owner judgement |
| **3** | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | **BLOCKED** | Three recorded, approved hashes | `walkforward.py` L450/456/462 (code only) | Record after #2 | B10 #5–#7 | ❌ Requires creating a preregistration |
| **4** | `CrossAssetAuthorization` complete and validated | **BLOCKED** | A complete record with approver identity | `researchguard.py` L147–162 (rejection logic only) | Supply approver | B8 | ❌ Requires an identity |
| **5** | Reservation carries the preregistration ID | **BLOCKED** | Registry updated | none | — | B10 #11 | ❌ Governed-state change |
| **6** | `assert_clean_working_tree()` passes | **UNMET** | Clean working tree | `walkforward.py` L693 | Commit or stash | None | ⚠️ **Technically yes**, but requires altering Git state — a repository action for the owner |
| **7** | B1–B4 governance items resolved or explicitly waived | **PARTLY ADVANCED** | Four resolutions or waivers | B1 ✅ brief · B2 ✅ **evidence captured** · B3 ✅ ready · B4 ⬜ open | Resolve or waive | None | ✅ **B2's evidence gap was closed this phase** |
| **8** | Named evaluator and date | **OWNER DECISION REQUIRED** | A name and a date | none | Name | None | ❌ Requires an identity |
| **9** | Written one-evaluation authorisation, consumed immediately after the run and before any result is read | **OWNER DECISION REQUIRED** | A written authorisation | `backtest.py` L180; `phase59/RESERVED_EVALUATION_DESIGN.md` | Authorise | #1–#8 | ❌ Is itself the authorisation |

---

## 3. Tally

| Status | Count | Items |
|---|---|---|
| **VERIFIED** | **0** | — |
| **BLOCKED** | 5 | #1, #2, #3, #4, #5 |
| **UNMET** | 1 | #6 |
| **PARTLY ADVANCED** | 1 | #7 |
| **OWNER DECISION REQUIRED** | 2 | #8, #9 |
| **Total** | **9** | — |

**Still 0 of 9 verified.** No condition flipped.

---

## 4. What changed this phase

| Change | Effect |
|---|---|
| **B2 evidence captured** | ✅ **Condition #7 advanced.** One of four governance inputs is now evidence-backed rather than blocked |
| **B4 recommendation prepared** | Condition #7 partially advanced — decision still open |
| Nothing else | — |

**Net effect on the tally: none.** #7 moved from *fully blocked on evidence* to
*awaiting an owner decision* — a real improvement that does not change a count.

---

## 5. Named approver and named evaluator — treated separately

**[V] These are different roles and must not be conflated.**

| Role | Gate | Function | Status |
|---|---|---|---|
| **Cross-asset approver** | B8 / B11 #4 | Accepts the **research claim** that a BTC-labelled configuration transfers to ETH. Must have read the frozen protocol | 🔴 **No identity, approval or date exists** |
| **Evaluator** | B11 #8 | Executes the authorised evaluation | 🔴 **No identity or date exists** |
| **Authorising party** | B11 #9 | Grants one-evaluation authority and the consumption protocol | 🔴 **Not granted** |

**[V] The guard mechanically prevents skipping B8/B11 #4** — an incomplete
authorization record causes a refusal. **Nothing prevents skipping B11 #8**; it is
a protocol obligation.

**[V] No project document defines an independence requirement or separation of
duties** between these roles. Recorded as unresolved in
`phase61/B8_APPROVER_REQUIREMENTS.md` §3; not invented here.

**No person was nominated in this phase.**

---

## 6. Precise blockers

| # | Blocker | Cleared by | Type |
|---|---|---|---|
| 1 | B5–B8 all open | Four owner decisions | Judgement |
| 2 | No preregistration ID; protocol not frozen | B10 completion | Governed state |
| 3 | Protocol hashes not computed or recorded | After B5–B8 | Governed state |
| 4 | No cross-asset authorization record | B8 | Identity |
| 5 | Reservation carries no ID | After freeze | Governed state |
| 6 | Working tree dirty (19 modified, 394 untracked) | Commit or stash | Repository action |
| 7 | B1–B4 not all resolved | B1, B3, B4 decisions (B2 evidence now ready) | Judgement |
| 8 | No named evaluator | Owner names | Identity |
| 9 | No written authorisation | Owner authorises | Authorisation |

---

## 7. What must **not** be inferred as authorisation

| Signal | Why insufficient |
|---|---|
| **The B2 evidence capture** | Closes an input to condition #7. Authorises nothing |
| Passing tests | Verifies code, not permission |
| Matching ETH checksum | Data integrity, not consent |
| "Signature-ready" briefs | Readiness ≠ approval |
| A preregistration draft | A draft is not a frozen protocol |
| A verified `CrossAssetAuthorization` **format** | An unpopulated record is not an approval |

**No such signal exists in the current state in any case — all nine conditions
remain unmet or blocked.**

---

## 8. Recommended addition to the preregistration (not a listed condition)

**[R]** From `phase59/RESERVED_EVALUATION_DESIGN.md` §7:

> A result that cannot be shown to be paired with a consumption record **must be
> discarded** and the window re-evaluated.

This closes the window between "result computed" and "consumption recorded", which
no implementation currently eliminates. Recording it in the protocol costs
nothing and closes an audit question later.

**Not applied.** It is a proposal for the owner's protocol, not a gate.