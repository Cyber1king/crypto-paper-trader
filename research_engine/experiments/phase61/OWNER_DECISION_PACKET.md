# Phase 61 — Owner Decision Packet

**Concise index. Every item below requires an owner decision. None has been made.**

---

## Status at a glance

| Gate | Status | Verified | Unmet/Blocked | Approved |
|---|---|---|---|---|
| **B10** preregistration freeze | `BLOCKED` | **1 of 12** | 11 | 0 |
| **B11** evaluation authorisation | `BLOCKED` | **0 of 9** | 9 | 0 |
| **ETH reservation** | Intact — `RESERVED` / `false` / `null` | — | — | — |

---

## The decisions you need to make

### Can be made now from existing evidence

| ID | Decision | Detail | Blocked? |
|---|---|---|---|
| **B1** | Python package licence: **A** none · **B** MIT · **C** Apache-2.0 · **D** BSD-3 · **E** CC BY-NC-SA | `B1_PYTHON_LICENCE_DECISION.md` | No — pure preference |
| **B3** | Approve Binance `licence_knowledge` → `VERIFIED`, `licence_name` → `CC BY-NC-SA 4.0` | `B3_BINANCE_REGISTRY_DECISION.md` | **No — evidence complete, signature-ready** |
| **B4** | ECB provenance: **defer** or **authorise reacquisition + comparison** | `B4_ECB_PROVENANCE_DECISION.md` | No |
| **B9** | Confirm **Option A** (single preregistered evaluation) or direct Option B | `B9_OPTION_A_CONFIRMATION.md` | No — but gates B5–B7 |

### Needs one piece of external evidence first

| ID | Decision | What is missing | Detail |
|---|---|---|---|
| **B2** | ECB terms correction | The ECB copyright page **captured in-repo** with retrieval date + SHA-256. Currently it exists only as a quote in a phase report | `B2_ECB_TERMS_EVIDENCE.md` |

### Needs independent approval by a person

| ID | Decision | Detail |
|---|---|---|
| **B8** | Name the cross-asset approver + date. They must have **read the frozen preregistration** | `B8_APPROVER_REQUIREMENTS.md` |

### Research thresholds — must close before any result is seen

| ID | Decision | Parameters left open | Detail |
|---|---|---|---|
| **B5** | Minimum trade count | value · derivation method · adequacy framing | `B5_MINIMUM_TRADE_COUNT.md` |
| **B6** | Uncertainty: **Block length** · **Iteration count** · **Basis for block length** · **Confidence level** | all four | `B6_UNCERTAINTY_PARAMETERS.md` |
| **B7** | Result interpretation: framework · **the decision bar** · confidence level | bar | `B7_RESULT_INTERPRETATION.md` |

---

## Gates

| Document | Contents |
|---|---|
| `B10_FREEZE_PREREQUISITES.md` | All 12 prerequisites, each with status, evidence path, what it proves and does not prove |
| `B11_EVALUATION_AUTHORIZATION.md` | All 9 conditions, with dependencies and the 8 precise blockers |

---

## Recommended order

```
1. B9  confirm Option A          ─┐ no dependencies
2. B3  approve registry change    │
3. B1  choose licence             │
4. B4  defer or reacquire        ─┘

5. Capture the ECB page in-repo  ──► unblocks B2, and B11 #7

6. B7  framework + bar  ─┐
7. B6  four parameters   ├─ B6's confidence level and B7's bar are coupled
8. B5  trade count      ─┘

9.  B10 #5–#7  compute and record hashes
10. B10 #10  commit/stash so the tree is clean
11. B8   approver named + dated (reads the frozen protocol)
12. B10 #9, #11  validate authorization; reservation + ID  ──► FREEZE
13. B11 #7, #8, #9  ──────────────────────────────────────► AUTHORISE
```

**The one hard ordering rule:** B5, B6 and B7 close **before** the freeze and
before any result exists. Each is a number that must not depend on an outcome.

---

## What has been verified in Phase 61

| Check | Result |
|---|---|
| ETH dataset SHA-256 | **MATCH** — `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Reservation | **`RESERVED` / `used: false` / `preregistration_id: null`** |
| Consumption fields added | **None** |
| Authoritative B10 list | **Found** — 12 items, `phase57/AUTHORIZATION_GATE_CHECKLIST.md` |
| Authoritative B11 list | **Found** — 9 items, same source |
| B6 parameter names | **Found** — canonical names preserved |
| Governed state modified | **None** |
| Backtest / optimisation run | **None** |
| Reserved-period performance inspected | **None** |
| Files staged / committed / pushed | **None — staged 0** |

---

## Three things worth saying plainly

**1. Nothing is time-critical except integrity.** The reservation is intact and
the guard is verified. There is no pressure to decide quickly, and every number
here is better chosen without results in view.

**2. B3 is genuinely ready.** Eight provenance sidecars, four phase reports and
the publisher's current terms support it. It needs only a signature.

**3. The recurring pattern in this project is that recommendations over-reach
evidence.** Phases 52, 53 and 58 each corrected an earlier overstatement. Every
brief here marks what is verified, what is recommended, and what remains open —
because that distinction has been the most valuable output of the whole
sequence.

---

**This packet prepares decisions. It does not make them.**