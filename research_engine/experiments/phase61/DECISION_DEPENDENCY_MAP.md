# Phase 61 — Decision Dependency Map

**Purpose:** show which decisions depend on which, so the owner can act in an
order that minimises rework and preserves research integrity.

**Nothing here is approved.**

---

## 1. Four categories of decision

| Category | Meaning | Items |
|---|---|---|
| **A. Immediate** | The owner can decide now from existing repository evidence | B1, B3, B4, B9, B11 #8 |
| **B. Needs external evidence first** | Cannot be decided until something is captured or obtained | B2 (needs the ECB page captured in-repo), B4 Option B (needs authorisation to acquire) |
| **C. Needs independent approval** | A person other than the decider must accept them | B8 (cross-asset approver) |
| **D. Must wait** | Cannot close until prerequisites resolve | B5, B6, B7 (should follow B9 so the design is settled first); B10 #5–#7, #9, #11; B11 |

---

## 2. Dependency graph

```
                        ┌──────────────────────────────────────────┐
   CATEGORY A           │  IMMEDIATE — decide now                   │
   (existing evidence)  │                                          │
                        │  B1  Python licence                      │──┐
                        │  B3  Binance registry  (signature-ready)  │  │
                        │  B4  ECB provenance: defer or acquire    │  │
                        │  B9  Confirm Option A                    │  │
                        └──────────────────────────────────────────┘  │
                                                                       │
   CATEGORY B           ┌──────────────────────────────────────────┐  │
   (external evidence)  │  B2  ECB terms                           │  │
                        │      └─ BLOCKED ON: capture the ECB      │◄─┘
                        │         copyright page in-repo with      │
                        │         date + SHA-256                   │
                        └──────────────────────────────────────────┘
                                                                       │
   CATEGORY C           ┌──────────────────────────────────────────┐  │
   (independent)        │  B8  Cross-asset approver + date         │◄─┘
                        │      └─ must read the FROZEN protocol    │
                        └──────────────────────────────────────────┘
                                      │
                                      ▼
   CATEGORY D           ┌──────────────────────────────────────────┐
   (must wait)          │  B5  minimum trade count                  │◄── after B9
                        │  B6  four uncertainty parameters         │◄── after B9
                        │  B7  decision rule + bar                  │◄── after B9
                        └──────────────────────────────────────────┘
                                      │
                                      ▼
                        ┌──────────────────────────────────────────┐
                        │  B10 FREEZE (12 prerequisites)           │
                        │    #1–#4  ← B5,B6,B7,B8                │
                        │    #5–#7  ← follows #1–#4 (compute+record)│
                        │    #8     ← ALREADY VERIFIED             │
                        │    #9     ← follows B8                   │
                        │    #10    ← commit/stash (owner action)  │
                        │    #11    ← follows #5–#7, #10          │
                        │    #12    ← follows all B10             │
                        └──────────────────────────────────────────┘
                                      │
                                      ▼
                        ┌──────────────────────────────────────────┐
                        │  B11 AUTHORISATION (9 conditions)         │
                        │    #7 ← B1,B2,B4 resolved or waived       │
                        │    #8 ← name evaluator                    │
                        │    #9 ← written one-evaluation authority  │
                        └──────────────────────────────────────────┘
                                      │
                                      ▼
                              EVALUATION (not authorised)
```

---

## 3. Recommended order

### Step 1 — Immediate, zero rework risk

| Order | Action | Why now |
|---|---|---|
| 1 | **B9** confirm Option A (or direct B) | Determines the protocol's shape. B5–B7 are easier to decide once the design is fixed |
| 2 | **B3** approve the Binance registry transition | Evidence is complete and in-repo; nothing blocks it. It is also a release-readiness item |
| 3 | **B1** choose the Python licence | Pure owner preference; no dependency |
| 4 | **B4** defer or authorise ECB reacquisition | Cheap to decide now; avoids leaving B11 #7 hanging |

**None of these depends on another.** They can be taken in any order or
separately.

### Step 2 — Evidence capture (can run in parallel with Step 1)

| Action | Unblocks |
|---|---|
| Capture the ECB copyright page in-repo with retrieval date + SHA-256 | **B2**, and B11 #7 |

**This is the only item in the packet that requires fetching an external
document.** It does not modify governed state and is low risk.

### Step 3 — Research parameters (after B9)

| Order | Action | Depends on |
|---|---|---|
| 5 | **B7** framework + bar | B9 |
| 6 | **B6** four parameters — **jointly with B7's confidence level** | B9 |
| 7 | **B5** minimum trade count | B9 |

**Why B6 and B7 are joint:** the confidence level and the decision bar are not
independent. Moving one can clear or miss the same result.

### Step 4 — Independent approval (after B10 #1–#7, #10)

| Action | Note |
|---|---|
| **B8** approver named + dated | Must read the **frozen** protocol, so this comes **after** the hashes are recorded, not before |

### Step 5 — Freeze

B10 #5–#7 (compute and record hashes), #9 (validate the authorization record),
#10 (clean tree), #11 (reservation + ID), then **freeze**.

### Step 6 — Authorisation

B11 conditions, ending with a written one-evaluation authority naming the
evaluator and the consumption protocol.

---

## 4. Decisions needing independent approval

| Item | Why independent |
|---|---|
| **B8** | The approver must accept a **research claim** — that BTC development transfers to ETH. Naming someone who has not read the protocol would make the record a formality |

**[U] No project document defines a formal independence rule or separation of
duties.** Recorded as unresolved in `B8_APPROVER_REQUIREMENTS.md` §3.

---

## 5. What must wait, and why

| Waits for | Items |
|---|---|
| **B9** | B5, B6, B7 — the protocol's shape must be fixed before its parameters |
| **B5–B8** | B10 #1–#4 |
| **B10 #5–#7** | B11 #3 |
| **B10 freeze** | B11 #1, #4, #5 |
| **B1–B4** | B11 #7 |
| **Everything** | B11 #9 |

**The single most important ordering constraint:** B5, B6 and B7 must close
**before the freeze and before any result is seen**. Each is a number whose value
must not depend on an outcome that does not yet exist.

---

## 6. Items that cannot be decided by anyone but the owner

| Item | Reason |
|---|---|
| B1 | A grant of rights |
| B3 | A governed state transition |
| B5, B6, B7 | Risk tolerance and threshold judgement |
| B8 | Identity and approval |
| B10 #10 | A repository action |
| B11 #8, #9 | Identity and authorisation |

**OpenCode can prepare, verify and draft every one of these. It cannot decide
any of them.**