# Phase 61 — B8: Approver Requirements

**Status: `OWNER DECISION REQUIRED` — identity, approval and date all OPEN.**

---

## 1. Required authorization role

**[V] What the governance documents require:**

| Element | Evidence |
|---|---|
| `StrategyConfig.asset` is **only a label**; the engine never checked it | `researchguard.py` L13–15 |
| The frozen configuration declares `asset="BTC/USDT"` | `walkforward.baseline_config()` |
| Applying it to ETH data is a **cross-asset authorization** event | `researchguard.py` L122 |
| `CrossAssetAuthorization` requires `config_asset`, `dataset_instrument`, `justification` | `researchguard.py` L147–159 |
| `from_record()` **rejects** an incomplete record | same |
| No authorization currently exists for ETH | registry `research_note` for ETH/USDT |

**The required role is therefore:**

> A person who can accept the **research claim** that a configuration developed
> on BTC 2024–2025 transfers to ETH 2026 — **having read the frozen
> preregistration**.

**This is a research judgement, not a code fact.** That is precisely why it cannot
be automated, delegated to an agent, or inferred from repository ownership.

---

## 2. Separation of role, person and evidence

Per instruction, these are kept distinct:

| Element | State |
|---|---|
| **Required role** | Verifiable above: a person accepting a research claim after reading the frozen protocol |
| **Person occupying that role** | 🔴 **OPEN — no identity established by any authoritative record** |
| **Approval evidence** | 🔴 **OPEN** — no signed record exists |
| **Approval date** | 🔴 **OPEN** |

**[V] The repository contains no approver record of any kind.** Nothing was
invented.

---

## 3. Independence and conflict-of-interest considerations

**[R]** Considerations recorded in the project literature:

| Consideration | Why it matters |
|---|---|
| The approver must have **read the frozen preregistration** | A record of approval that documents no review is a formality |
| Naming an approver **who has not read it** would defeat the control | The record would exist; the review it documents would not |
| The approver should be **distinct from whoever tunes the strategy** | The same person selecting a configuration and certifying its transfer has an incentive conflict |

**[U] No project document defines a formal independence requirement, a
separation-of-duties rule, or a conflict-of-interest declaration.** These are
raised here as considerations, **not** as documented rules, and are marked for
owner determination.

---

## 4. The record that must be created

`CrossAssetAuthorization` fields required by `from_record()`:

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — **not** a tuning opportunity |
| `approver` | 🔴 **OPEN — OWNER DECISION REQUIRED** |
| `date` | 🔴 **OPEN — OWNER DECISION REQUIRED** |

---

## 5. No ordering hazard

**[V]** The guard refuses to run without a complete authorization record, so B8
**cannot be silently skipped**. Unlike a manual checklist item, its absence stops
the evaluation mechanically.

**However:** nothing enforces that the named approver actually read the
protocol. That part is a trust obligation, not a technical control.

---

## 6. Timing

B8 should close **after** B5, B6 and B7 are set and **before** the freeze
(B10 #4 → #9), so the approver reads a complete protocol rather than a draft that
will still change.

Approving before the thresholds are fixed would mean certifying a claim against
parameters that have not yet been stated — which would defeat the purpose.

---

## 7. Exact owner decision required

> **"The authorized cross-asset approver is [name or role], who has read the
> frozen preregistration at [preregistration version/ID], dated [date].
> [Optional, if the owner wishes to adopt them:] The approver is independent of
> strategy development."**

**Not to be done by OpenCode:** naming an approver, recording an approval,
setting a date, or approving on the owner's behalf.