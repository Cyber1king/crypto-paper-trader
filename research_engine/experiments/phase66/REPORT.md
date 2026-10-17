# Phase 66 — B10 Freeze-Gate Audit

**Prerequisites:** authoritative 12-item list at
`experiments/phase57/AUTHORIZATION_GATE_CHECKLIST.md` (verified: 21 numbered rows = 12 + 9).
**Safety check at start:** ETH checksum MATCH; reservation `RESERVED/false/null`; no new blocker.

> **No status was changed. No hash was computed. No protocol value was frozen.**

## 1. Prerequisite audit

| # | Requirement | Status | Evidence | Remaining work | Dependencies | Completable without creating/freezing a preregistration? |
|---|---|---|---|---|---|---|
| 1 | B5 minimum trade count and adequacy rule | OWNER DECISION REQUIRED | phase61/B5_MINIMUM_TRADE_COUNT.md | Owner sets value + method + framing | None | No — owner judgement |
| 2 | B6 block length, iterations, basis, confidence level | OWNER DECISION REQUIRED | phase61/B6_UNCERTAINTY_PARAMETERS.md | Owner sets 4 values | None | No — owner judgement |
| 3 | B7 decision rule and bar | OWNER DECISION REQUIRED | phase61/B7_RESULT_INTERPRETATION.md | Owner sets framework + bar | None | No — owner judgement |
| 4 | B8 cross-asset approver and date | OWNER DECISION REQUIRED | phase61/B8_APPROVER_REQUIREMENTS.md | Owner names approver | None | No — identity required |
| 5 | `config_hash` recorded | UNMET | walkforward.py L450 (code only) | Compute + record after #1-#4 | #1-#4 | No — requires creating a preregistration |
| 6 | `costs_hash` recorded | UNMET | walkforward.py L456 (code only) | Compute + record after #1-#4 | #1-#4 | No — requires creating a preregistration |
| 7 | `dataset_fingerprint` recorded | UNMET | walkforward.py L462; researchguard.candle_fingerprint | Capture at freeze | #1-#4 | No — requires creating a preregistration |
| 8 | Window and warm-up split confirmed | VERIFIED | data/research_registry.json reservations[ETH-2026-RESERVATION] | None | None | n/a |
| 9 | `CrossAssetAuthorization` validated by `from_record()` | BLOCKED | researchguard.py L147-162 (rejection logic only) | Supply approver record | #4 | No — requires an identity |
| 10 | `assert_clean_working_tree()` passes | UNMET | walkforward.py L693 | Commit or stash the working tree | None | Yes — but only by the owner |
| 11 | Reservation updated with preregistration ID | BLOCKED | data/research_registry.json | Assign ID | #5-#7, #10 | No — governed-state change |
| 12 | B11 authorisation obtained | BLOCKED | phase67 | Grant after all B10 | All B10 | No — governed-state change |

## 2. Hash prerequisites — four-stage distinction

| Stage | #5 `config_hash` | #6 `costs_hash` | #7 `dataset_fingerprint` |
|---|---|---|---|
| 1. Hashing code exists | Y | Y | Y |
| 2. Value computed | N | N | N |
| 3. Value recorded in artefact | N | N | N |
| 4. Value approved and frozen | N | N | N |
| **Status** | **UNMET** | **UNMET** | **UNMET** |

**Missing step (all three):** after #1-#4 close and the tree is clean, compute
and record each value **in the preregistration document**, then approve and
freeze. Not performed here — computing one requires creating the very artefact
these prerequisites gate.

## 3. #10 Git-state condition

**Exact condition:** `assert_clean_working_tree()` passes (`walkforward.py` L693).

| Component | Value |
|---|---|
| Staged | 0 |
| Tracked modified | 19 |
| Untracked | 402 |
| Stash | 0 |

**Why it matters:** ensures the code producing a result is the code reviewed.
**Nature:** a **repository action, not a judgement**. It is still the owner's
because the uncommitted work is theirs. Nothing was staged, stashed or committed.

## 4. Tally

| Status | Count | Items |
|---|---|---|
| VERIFIED | **1** | #8 |
| OWNER DECISION REQUIRED | 4 | #1-#4 |
| UNMET | 4 | #5, #6, #7, #10 |
| BLOCKED | 3 | #9, #11, #12 |
| **Total** | **12** | — |

**Hard blockers: 11 of 12. Unchanged from Phase 61.**

## 5. Ordering

```
#1 B5, #2 B6, #3 B7, #4 B8  ->  #5/#6/#7 compute + record
#10 clean tree (owner)      ->  #9 validate authorization
#5-#7 + #10                 ->  #11 reservation + ID
all of the above            ->  #12 B11 authorisation  ->  FREEZE
```
