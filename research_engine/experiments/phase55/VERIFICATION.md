# Phase 55 Verification

**Date:** 2026-10-09
**Remit:** governance and safeguards only.

---

## 1. Baseline

**[V] Git**

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Upstream | `origin/main` @ same commit |
| Ahead / behind | **0 / 0** |
| Staged | **0** |
| Tracked modified | 19 |
| Untracked | 338 |

**[V] Phase 53–54 deliverables** — all 10 present and non-empty:
Phase 53 (`ECB_RIGHTS_REVIEW.md`, `ETH_EVALUATION_DESIGN.md`,
`LICENCE_REMEDIATION_PLAN.md`, `PREREGISTRATION_DECISION_REGISTER.md`,
`VERIFICATION.md`) and Phase 54 (`ECB_REGISTRY_CORRECTION_PROPOSAL.md`,
`ETH_EVALUATION_READINESS.md`, `LICENCE_SCOPE_REVIEW.md`,
`PREREGISTRATION_DECISION_REGISTER.md`, `VERIFICATION.md`).

**[V] ETH dataset checksum** — recomputed at baseline and again after testing:

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
```

**MATCH** both times.

**[V] Reservation at baseline**

```
reservation_id     : ETH-2026-RESERVATION
status             : RESERVED
used               : False
preregistration_id : None
```

**No discrepancy against prior records.**

---

## 2. Changes made

**[V] One source change, one new test file. Nothing else.**

| File | Change |
|---|---|
| `src/crypto_paper_lab/researchguard.py` | Added a duplicate-consumption rejection clause in `_consume_reservations` (~19 lines), placed between the id-set construction and the mutation loop |
| `tests/test_reservation_single_use.py` | **New** — 7 tests, synthetic fixtures only |

**No other file was modified.** No registry entry, no dataset, no frozen
artifact, no historical research record, no Phase 53/54 deliverable.

**No registry state changed. No reservation consumed. No approval
self-granted. Nothing staged, committed or pushed.**

### Why the implementation was permitted

The phase authorised implementation only if the change was isolated,
backward-compatible, supported by existing governance rules, and fully testable
without reserved-period results. All four held:

| Condition | Evidence |
|---|---|
| Isolated | One function, one clause, no signature changes |
| Backward compatible | Full suite passes; no existing test consumed a reservation twice |
| Supported by governance | Module docstring: *"Without this, 'evaluated once only' is not a real guarantee"* |
| Testable without reserved data | 7 tests, all synthetic; ETH never opened |

---

## 3. Reservation-enforcement findings

**[V] Can the reservation be consumed more than once?**
**Before this phase: yes.** Accepted, silently overwriting `used_preregistration_id`
and `used_on`. Proven empirically — `used_pre` moved `prereg-A` → `prereg-B`.
**After this phase: no.** Refused, with the audit record preserved byte for byte.

**[V] Can it be evaluated without being consumed?**
**Yes — by design, deliberately unchanged.** `run_backtest` passes
`mark_used=False` unconditionally. The rationale (a crash must not spend a window
that produced no result) is sound. The consequence — a forgotten
`consume_reservation()` permits repeated, undetected evaluation — is registered
as a protocol obligation, not a fixed defect.

**[V] Scope correction.** `assert_evaluation_permitted` *does* refuse a consumed
window, so the F1 defect never enabled a second **evaluation** — only a second
**consumption record**, corrupting the audit trail. Stated precisely rather than
overclaimed.

**[V] F3 (concurrency) not fixed.** `os.replace` is atomic for the write, but
the read-modify-write has a TOCTOU window and no inter-process lock. Two
simultaneous consumers could both write. Documented as proposal N1, not applied
— it needs platform-specific code and its own design.

**[V] Documentation-versus-implementation mismatch found (N4).**
`researchguard.py` L29–30 claims *"Every attempt is recorded, including refused
ones"*. `_consume_reservations` records only **successful** spends. The claim
overstates the implementation. Not "fixed" — correcting a docstring versus
building the audit log is an owner decision.

---

## 4. Tests

### 4.1 New single-use tests

**Command**

```bash
cd research_engine
python -X utf8 -m pytest tests/test_reservation_single_use.py -q --no-header -p no:cacheprovider
```

**Result:** `7 passed in 0.25s` — **exit code 0**

### 4.2 Governance regression subset

**Command**

```bash
python -X utf8 -m pytest tests/test_research_guard.py tests/test_research_gaps.py \
  tests/test_registry_schema.py tests/test_evidence_schema.py -q --no-header -p no:cacheprovider
```

**Result:** `279 passed in 13.21s` — **exit code 0**

### 4.3 Full suite

**Command**

```bash
python -X utf8 -m pytest tests -q --no-header -p no:cacheprovider
```

**Result:** **`2506 passed in 1944.24s (0:32:24)` — exit code 0**

**Failures: 0.** 2499 pre-existing + 7 new. **No regression** from the change to
`researchguard.py`.

### 4.4 A test of mine failed first — recorded honestly

The initial version of `test_consumption_still_requires_an_explicit_registry_file`
**failed** (`1 failed, 6 passed`, exit 1). It used a synthetic reservation ID
with no `registry_file`; `consume_reservation` resolves the reservation *before*
checking for a writable target, so it raised `"not in the registry"` instead of
`"no registry_file"`.

**The fault was in my test, not the product.** It was corrected to use the real
reservation ID — which does resolve — thereby exercising the genuine fail-closed
path, and asserting the real registry is byte-identical afterwards.

### 4.5 Did the tests touch the reserved ETH window?

**No — verified, not assumed.**

| Evidence | Finding |
|---|---|
| New test fixtures | Synthetic `PROBE-SYNTHETIC` reservation in a `tmp_path` registry |
| `test_real_eth_reservation_is_never_touched_by_this_module` | Asserts the real registry is byte-identical and the ETH reservation is `RESERVED` / `used: false` / `preregistration_id: null` |
| Reserved ETH CSV | Opened by **no** test; only `exists()` is asserted |
| Real registry | Read by the new tests only to inherit a valid instrument block — never written except in `test_consumption_without_a_registry_file_fails_closed`, which asserts no write occurred |
| Pre-existing suite | Guard tests use `ETH_HASH = "a" * 64`; real ETH CSV referenced only for structural validation |

**No backtest, parameter search, optimisation or performance experiment was
run.**

---

## 5. Post-test integrity

**[V] ETH dataset SHA-256** — recomputed after the full suite:

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**[V] Reservation after testing:**

```
status              : RESERVED
used                : False
preregistration_id  : None
used_on present     : False
used_preregistration_id present : False
VERDICT             : INTACT
```

`used_on` and `used_preregistration_id` are absent — no consumption ever
occurred, including from the deliberate probes.

**[V] No stop condition triggered.** The reservation was not consumed, the
checksum did not change, and no proposed operation would have run an evaluation.

---

## 6. Git status

```
branch  main
HEAD    dccebbd53ee8365474345506db9099b13356b53c   (unchanged, == origin/main)
staged  0

Phase 55 changes:
  ?? research_engine/src/crypto_paper_lab/researchguard.py     (pre-existing untracked file, modified)
  ?? research_engine/tests/test_reservation_single_use.py       (new)
  ?? research_engine/experiments/phase55/                      (5 deliverables)
```

Both source files were already untracked before this phase
(`researchguard.py` was created in Phase 42 and never tracked). Nothing was
staged, committed, pushed or published. No file was deleted, reset or cleaned.

---

## 7. Restrictions observed

| Restriction | Observed |
|---|---|
| No real-money trading or exchange execution | **Yes** |
| No backtests, optimisation or performance experiments | **Yes** |
| No reserved-period performance inspection | **Yes** — no ETH figure exists or was computed |
| No consumption of the ETH reservation | **Yes** — `RESERVED` / `false` / `null` throughout |
| No modification of frozen datasets or historical results | **Yes** |
| No deletion, reset or cleanup | **Yes** |
| No staging, committing, pushing, publishing | **Yes** — staged count 0 |
| No invented results, legal claims or approvals | **Yes** — no licence selected, no legal approval asserted, no threshold set |

---

## 8. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `RESERVATION_ENFORCEMENT_REVIEW.md` | What is enforced; F1 proven and fixed; F2 by design; F3 unfixed; transition table; fix; 5 documented proposals; N4 mismatch |
| 2 | `OWNER_DECISION_GATE.md` | B5–B8, B11 with status, evidence, options, risks, exact decision required, dependency order |
| 3 | `PREREGISTRATION_DRAFT.md` | Consolidated draft, unfrozen, no ID, every unresolved field marked |
| 4 | `GOVERNANCE_STATUS.md` | B1–B4, B9, B10 separated by what needs analysis vs evidence vs owner |
| 5 | `VERIFICATION.md` | This document |

---

## 9. Phase verdict

# `READY FOR OWNER DECISIONS — SAFEGUARD HARDENED`

Phase 55's remit is complete. One real defect was found, proven, fixed and
tested. The remaining items are owner decisions, not missing analysis.

**Nothing here authorises an evaluation.** The reservation remains `RESERVED`,
no preregistration ID exists, and all five gates are open.

---

## 10. Exact next actions requiring human approval

**Signature-ready now**

| # | Action |
|---|---|
| 1 | **B3** — approve Binance `licence_knowledge` → `VERIFIED` / `CC BY-NC-SA 4.0` (evidence already in-repo) |
| 2 | **B9** — confirm Option A |
| 3 | **B2** — approve the ECB registry correction, and decide whether to capture the ECB page in-repo first |
| 4 | **B1** — choose the Python package licence (MIT / Apache-2.0 / BSD-3 / no grant / CC BY-NC-SA) |

**Gate-blocking**

| # | Action |
|---|---|
| 5 | **B5** — minimum trade count and adequacy rule |
| 6 | **B6** — block length, iterations, basis |
| 7 | **B7** — three-branch decision rule and the bar |
| 8 | **B8** — named cross-asset approver and date |
| 9 | Freeze the preregistration: record `config_hash`, `costs_hash`, `dataset_fingerprint`; assign ID; update reservation |
| 10 | **B11** — separate, explicit evaluation authorisation |

**Optional**

| # | Action |
|---|---|
| 11 | **B4** — defer or re-acquire ECB data with `providers=ecb` |
| 12 | Resolve **N1** (inter-process locking) |
| 13 | Resolve **N4** (correct the "every attempt is recorded" claim, or build the audit log) |

**Items 5–10 must close in that order. Nothing may be evaluated until every one
is done.**