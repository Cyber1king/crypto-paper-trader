# Phase 61 — B10: Preregistration Freeze Prerequisites

**Status: `BLOCKED` — 1 of 12 VERIFIED, 11 unmet.**
The protocol is **not** frozen. No preregistration ID is assigned.

---

## 1. Authoritative list

**[V] Source:** `experiments/phase57/AUTHORIZATION_GATE_CHECKLIST.md` §"B10 —
Preregistration freeze: 12 prerequisites". Exactly **12** items. Carried
forward unchanged through Phases 58–60.

**This list was located and verified in the repository. It was not invented or
reconstructed.** No item was added or removed.

### Status vocabulary

| Status | Meaning |
|---|---|
| `VERIFIED` | Checked against identified evidence this phase |
| `UNMET` | No decision or artefact exists |
| `BLOCKED` | Cannot proceed until a dependency resolves |
| `OWNER DECISION REQUIRED` | Only the owner can supply it |

**Conservative rule applied:** *a hash function without a recorded and approved
value is not a satisfied prerequisite. A draft is not an approved protocol.*

---

## 2. Prerequisite-by-prerequisite audit

| # | Exact requirement | Status | Evidence path | What the evidence proves | What it does **not** prove | Missing action | Hard blocker? |
|---|---|---|---|---|---|---|---|
| **1** | B5 minimum trade count and adequacy rule | **OWNER DECISION REQUIRED** | `phase61/B5_MINIMUM_TRADE_COUNT.md` | That four framings exist and are documented | Any threshold | Owner sets value + method + framing | **Yes** |
| **2** | B6 block length, iterations, basis, confidence level | **OWNER DECISION REQUIRED** | `phase61/B6_UNCERTAINTY_PARAMETERS.md` | That the four parameter names and the block-bootstrap methodology are documented | Any value for any of the four | Owner sets 4 values | **Yes** |
| **3** | B7 decision rule and bar | **OWNER DECISION REQUIRED** | `phase61/B7_RESULT_INTERPRETATION.md` | That a three-verdict framework is proposed and prior results are recorded | **The bar value** | Owner sets framework + bar + confidence | **Yes** |
| **4** | B8 cross-asset approver and date | **OWNER DECISION REQUIRED** | `phase61/B8_APPROVER_REQUIREMENTS.md` | That the required role and the `CrossAssetAuthorization` fields are documented | Any identity, approval or date | Owner names approver + date | **Yes** |
| **5** | `config_hash` recorded | **UNMET** | `walkforward.py` L450 (`config_hash` exists) | That a **hash function exists** and is tested | **That any value was computed, recorded or approved** | Compute and record after #1–#4 close | **Yes** |
| **6** | `costs_hash` recorded | **UNMET** | `walkforward.py` L456 (`costs_hash` exists) | That a hash function exists | Any recorded value | Compute and record | **Yes** |
| **7** | `dataset_fingerprint` recorded | **UNMET** | `walkforward.py` L462; `researchguard.py` `candle_fingerprint` | That fingerprinting is implemented | Any recorded value | Capture at freeze | **Yes** |
| **8** | Evaluation window and warm-up split confirmed against the reservation | **VERIFIED** | `data/research_registry.json` → `reservations[ETH-2026-RESERVATION]` | 17,544 warm-up bars (idx 0–17543); 6,744 evaluation bars (idx 17544–24287); 2026-01-01 → 2026-10-08; SHA-256 `7507c100…` matches the dataset on disk | Nothing about results | — | No |
| **9** | `CrossAssetAuthorization` validated by `from_record()` | **BLOCKED** | `researchguard.py` L147–162 | That `from_record()` **rejects** an incomplete record — verified by tests | That **any** authorization record exists | Blocked on #4 | **Yes** |
| **10** | `assert_clean_working_tree()` passes | **UNMET** | `walkforward.py` L693 | That the check exists | That it currently passes | Working tree is intentionally dirty: **19 tracked modified, 380 untracked** | **Yes** |
| **11** | Reservation updated with the preregistration ID | **BLOCKED** | `data/research_registry.json` | That the reservation exists and is unspent | That any ID exists | Blocked on #5–#7, #10 | **Yes** |
| **12** | B11 authorisation obtained (separate, explicit) | **BLOCKED** | `phase61/B11_EVALUATION_AUTHORIZATION.md` | — | Any authorisation | Blocked on all of B10 | **Yes** |

---

## 3. Tally

| Status | Count | Items |
|---|---|---|
| **VERIFIED** | **1** | #8 |
| **OWNER DECISION REQUIRED** | 4 | #1, #2, #3, #4 |
| **UNMET** | 4 | #5, #6, #7, #10 |
| **BLOCKED** | 3 | #9, #11, #12 |
| **Total** | **12** | — |

**Hard blockers: 11 of 12.** Only #8 is satisfied.

---

## 4. Items explicitly NOT counted as satisfied

**[V] A function existing is not a value recorded.**

| Item | Why it is UNMET, not partially met |
|---|---|
| #5 `config_hash` | `config_hash(config)` exists and is tested. **No value has been computed for this protocol**, and none is approved |
| #6 `costs_hash` | Same |
| #7 `dataset_fingerprint` | Derivable on demand, **not captured** as a protocol value |
| #11 Reservation + ID | The registry being *unchanged* is the **correct current state**, not partial progress |

**[V] The preregistration drafts** (`phase56/PREREGISTRATION_DRAFT.md`,
`phase58/PREREGISTRATION_DRAFT.md`, `phase59/PREREGISTRATION_DRAFT.md`) **describe**
sections for these hashes. **A document describing a hash is not a hash.**

---

## 5. What #8's verification actually establishes

| Proves | Does not prove |
|---|---|
| The reserved window is 2026-01-01 → 2026-10-08, 6,744 evaluation bars | Anything about results in that window |
| The warm-up/evaluation split is 17,544 / 6,744 at index 17,544 | That the split is statistically adequate |
| The reservation's recorded SHA-256 matches the dataset on disk | That the dataset is fit for any particular purpose |
| The reservation is unspent | That it will remain unspent |

**No reserved-period performance was inspected to establish #8.** Only metadata.

---

## 6. Order in which the 11 blockers can be cleared

```
#1 B5 ─┐
#2 B6 ─┼─► #5 config_hash ─┐
#3 B7 ─┤   #6 costs_hash  ─┼─► #11 reservation + ID ─┐
#4 B8 ─┘   #7 fingerprint ─┘                          ├─► FREEZE
#9  CrossAssetAuthorization ◄─ #4                    │
#10 clean working tree ◄─ commit/stash               │
#12 B11 authorisation ◄──────────────────────────────┘
```

**#10 is the only blocker that does not depend on an owner decision** — it is
purely a matter of committing or stashing the working tree, which is itself an
owner action.

---

## 7. Exact owner actions required to unblock

> **B5:** "Minimum trade count = [N], derived by [method], framing [1–4]."
> **B6:** "Block length [N]; iterations [N]; basis [holding horizon / fixed /
> BTC development autocorrelation]; confidence [N]%."
> **B7:** "Three-verdict framework; `Promising` requires estimate AND interval
> clear [bar]."
> **B8:** "Cross-asset approver is [name/role], dated [date], having read the
> frozen preregistration."
> **#10:** commit or stash the working tree so `assert_clean_working_tree()` passes.
> **#5–#7, #11:** these follow mechanically **once #1–#4 close** — OpenCode may
> then compute and record the hashes **only under explicit instruction**.

**Not to be done by OpenCode:** freeze the protocol, assign a final ID, compute
and record protocol hashes as approved, or alter the registry.