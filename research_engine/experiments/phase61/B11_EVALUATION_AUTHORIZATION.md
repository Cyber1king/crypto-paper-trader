# Phase 61 — B11: Evaluation Authorization Conditions

**Status: `BLOCKED` — 0 of 9 VERIFIED.**
**Evaluation is NOT authorised.** No condition is approved.

---

## 1. Authoritative list

**[V] Source:** `experiments/phase57/AUTHORIZATION_GATE_CHECKLIST.md` §"B11 —
Evaluation authorisation: 9 conditions". Exactly **9** items. Carried forward
unchanged through Phases 58–60.

**Located and verified in the repository. Not invented or reconstructed.**

---

## 2. Condition-by-condition audit

| # | Exact requirement | Status | Evidence path | Owner/approver action | Dependencies | Why it matters |
|---|---|---|---|---|---|---|
| **1** | Preregistration frozen with an assigned ID | **BLOCKED** | `data/research_registry.json`; `phase61/B10_FREEZE_PREREQUISITES.md` | Assign ID after all B10 blockers clear | All of B10 | Without a fixed protocol, a result cannot be checked against what was declared beforehand |
| **2** | B5–B8 closed and recorded | **BLOCKED** | `B5_MINIMUM_TRADE_COUNT.md`, `B6_UNCERTAINTY_PARAMETERS.md`, `B7_RESULT_INTERPRETATION.md`, `B8_APPROVER_REQUIREMENTS.md` | Supply 4 decisions | None | These are the numbers and the approver. Deciding them after results exist defeats the protocol |
| **3** | `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | **BLOCKED** | `walkforward.py` L450/456/462 | Record after #2 | B10 #5–#7 | Makes any later change to config or costs **detectable** rather than silent |
| **4** | `CrossAssetAuthorization` complete and validated | **BLOCKED** | `researchguard.py` L147–162 | Supply approver identity | B8 | Declares that a BTC-labelled configuration is being applied to ETH — a research claim needing a person |
| **5** | Reservation carries the preregistration ID | **BLOCKED** | `data/research_registry.json` | Update after freeze | B10 #11 | Ties the window to a specific protocol |
| **6** | `assert_clean_working_tree()` passes | **UNMET** | `walkforward.py` L693 | Commit or stash | None | Ensures the code that produced the result is the code that was reviewed |
| **7** | B1–B4 governance items resolved or explicitly waived | **BLOCKED** | `B1_PYTHON_LICENCE_DECISION.md` … `B4_ECB_PROVENANCE_DECISION.md` | Resolve or waive all four | None | Licence decisions taken *after* publication are hard to apply retroactively |
| **8** | Named evaluator and date | **OWNER DECISION REQUIRED** | — | Name evaluator + date | None | Distinguishes the person running the evaluation from the person authorising it |
| **9** | Explicit statement that **one** evaluation is authorised, to be consumed **immediately after the run and before any result is read** | **OWNER DECISION REQUIRED** | `researchguard.py`; `backtest.py` L180 | Written authorisation | #1–#8 | See §3 |

---

## 3. Tally and the precise blockers

| Status | Count | Items |
|---|---|---|
| **VERIFIED** | **0** | — |
| **BLOCKED** | 6 | #1, #2, #3, #4, #5, #7 |
| **UNMET** | 1 | #6 |
| **OWNER DECISION REQUIRED** | 2 | #8, #9 |
| **Total** | **9** | — |

**Exact blockers preventing authorization:**

| # | Blocker | Cleared by |
|---|---|---|
| 1 | B5–B8 all open | Four owner decisions |
| 2 | No preregistration ID; protocol not frozen | B10 completion |
| 3 | Protocol hashes not recorded | #2 |
| 4 | No cross-asset authorization record | B8 |
| 5 | Working tree dirty (19 modified, 380 untracked) | Commit or stash |
| 6 | B1–B4 governance open | Four owner decisions or explicit waivers |
| 7 | No named evaluator | Owner names |
| 8 | No written authorisation | Owner authorises |

---

## 4. Why condition 9 is worded this way

**[V] The risk is not the first run — it is the moment after a disappointing
result, when re-running a variant becomes tempting.**

**[V] Nothing in the engine prevents it:** `run_backtest` passes
`mark_used=False` unconditionally (`backtest.py` L180) and never consumes.
`RESERVED` is a marker, not a lock — the reservation's own note records it as
*"NOT protected against evaluation until a preregistration is frozen and the
guard is exercised."*

**Enforcing consumption automatically was specified but deliberately not
implemented** (`phase59/RESERVED_EVALUATION_DESIGN.md`) because it changes a
public API and needs owner authority. Until then, condition 9 converts the
commitment from an intention into a written record.

---

## 5. What must **not** be inferred as authorisation

Per instruction, explicitly **not** sufficient:

| Signal | Why it is not authorisation |
|---|---|
| Successful unit tests | Tests verify code correctness, not permission to evaluate |
| A matching ETH checksum | Integrity of data is not consent to use it |
| "Signature-ready" documentation | Readiness is not approval |
| The existence of a preregistration draft | A draft is not a frozen protocol |
| A verified `CrossAssetAuthorization` record with no date | An incomplete record |
| Green CI | Correctness of locking, not research permission |

**No such signal exists in the current state anyway** — all nine conditions are
unmet or blocked.

---

## 6. Exact owner authorisation required

> **"I authorise exactly one evaluation of the reserved ETH window under
> preregistration [ID], to be executed by [evaluator] on [date], to be consumed
> immediately after the run via `consume_reservation()` and before any result is
> read. Approved by [name], [date]."**
>
> Plus, if applicable: **"I waive [B1 / B2 / B4] on the grounds that […]."**

**Additionally recommended, though not a listed condition:** adopt the
persistence-window rule from `phase59/RESERVED_EVALUATION_DESIGN.md` §7 —
*a result that cannot be shown to be paired with a consumption record must be
discarded and the window re-evaluated.*

**Not to be done by OpenCode:** authorising, scheduling or running an evaluation,
assigning an ID, or consuming the reservation.