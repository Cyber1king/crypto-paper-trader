# Phase 62 — Owner Action Packet

**Nothing here is approved. A complete brief is not an approved decision.**

---

## Status at a glance

| Gate | Status | Verified | Approved |
|---|---|---|---|
| **B10** freeze | `BLOCKED` | **1 of 12** | 0 |
| **B11** authorisation | `BLOCKED` | **0 of 9** | 0 |
| **ETH reservation** | Intact — `RESERVED` / `false` / `null` | — | — |

**Changed this phase:** the B2 evidence gap is **closed**. No gate tally moved.

---

## Group 1 — Evidence-ready decisions

*Evidence is sufficient to present a concrete choice.*

### B3 — Binance registry state ✅ **signature-ready**

| | |
|---|---|
| **Status** | Evidence complete; awaiting signature |
| **Context** | Registry says `licence_knowledge: UNVERIFIED`. Eight provenance sidecars, four phase reports and the publisher's current terms (v1.0, 26 Aug 2026) say CC BY-NC-SA 4.0. The schema permits `UNVERIFIED → VERIFIED` |
| **Options** | (a) approve the transition · (b) decline and keep the conservative marker |
| **Recommended** | **(a)** — the registry is currently less accurate than the repository it governs |
| **Risk** | None identified. The underlying use is unaffected by the label |
| **Question** | *"Do I approve the transition to `VERIFIED` / `CC BY-NC-SA 4.0` for BTC/USDT and ETH/USDT, with the `licence_note` as specified?"* |
| **Unchanged until approval** | `research_registry.json` |

### B1 — Python package licence

| | |
|---|---|
| **Status** | Owner preference; five options documented |
| **Context** | Root npm tooling is MIT; `research_engine` is outside that workspace and has **no** licence declared; no `LICENSE` file exists. It is all-rights-reserved by default |
| **Options** | **A** none · **B** MIT · **C** Apache-2.0 · **D** BSD-3-Clause · **E** CC BY-NC-SA 4.0 |
| **Recommended** | None. If consistency with the JS tooling is the priority, **B** |
| **Risk** | **E** propagates a non-commercial restriction to every derived work — the compounding effect is rarely intended |
| **Question** | *"Which licence for `crypto-paper-lab`, and who is the copyright holder?"* |
| **Unchanged until approval** | `pyproject.toml`; no `LICENSE` file |

### B2 — ECB terms correction ✅ **evidence now captured**

| | |
|---|---|
| **Status** | Evidence gap **CLOSED** this phase; awaiting decision |
| **Context** | ECB page captured 2026-10-10T13:24:13Z, HTTP 200, SHA-256 `424859b8…`. ECB grants free use **with conditions** — it does **not** grant CC BY-NC-SA. The current label asserts two obligations the ECB does not impose and omits three it does, including **explicit modification disclosure** |
| **Options** | (a) approve the correction · (b) also capture Data Portal terms now · (c) defer Data Portal capture until forex is proposed |
| **Recommended** | **(a) + (c)** |
| **Risk** | Not correcting leaves a demonstrably unsupported label on the machine-readable registry a future integration would read |
| **Question** | *"Do I approve the correction, and do I defer Data Portal capture?"* |
| **Unchanged until approval** | `research_registry.json` licence fields |
| **Still unresolved** | Whether stored rates are ECB observations → **B4** |

### B9 — Option A confirmation

| | |
|---|---|
| **Status** | Recommendation recorded; confirmation open |
| **Context** | The strategy has **no fitted parameters**, so segmentation would give robustness checks, not train/test generalisation. Option A runs today with no code change |
| **Options** | (a) Option A · (b) direct Option B with scope and phase |
| **Recommended** | **(a)** |
| **Risk** | Choosing B adds multiplicity risk to irreversibly consumed evidence |
| **Question** | *"Do I confirm Option A?"* |
| **Unchanged until approval** | The preregistration protocol |
| **Note** | B9 should be decided **first** — B5–B7 are easier to set once the design is fixed |

### B4 — ECB provenance

| | |
|---|---|
| **Status** | Provider identity unresolved and **not recoverable** from repository contents |
| **Context** | Acquisition carried no `providers=ecb` pin; Frankfurter's default is to blend; the payload records no provider |
| **Options** | **A** defer · **B** authorise reacquisition + comparison |
| **Recommended** | **A** — forex is blocked on data quality regardless, and B has a hard ceiling (a new comparison cannot prove what a past response contained) |
| **Risk** | B risks *apparent* resolution: a matching comparison could be read as vindication while proving less |
| **Question** | *"Do I select Option A or B?"* |
| **Unchanged until approval** | All forex artefacts; no synthesis of OHLC ever |

---

## Group 2 — Evidence-dependent decisions

### B2 — Data Portal terms *(sub-item)*

| | |
|---|---|
| **Status** | Not captured. `data.ecb.europa.eu` is a **distinct site** from the captured one |
| **Needed** | A second capture with URL, timestamp, checksum |
| **Recommended** | **Defer** until a forex integration is actually proposed — no bulk export is used today |
| **Question** | *"Capture the Data Portal terms now, or defer?"* |

### B4 — if Option B is chosen

| | |
|---|---|
| **Status** | Conditional on the B4 decision |
| **Needed** | Pinned re-query, provider attribution preserved, manifest with timestamps and SHA-256, and an honest report **including an inconclusive result** |
| **Question** | *"Who is authorised to perform it, and under what manifest requirements?"* |

---

## Group 3 — Research-governance decisions

*Require explicit judgement, an approved threshold, an authorised person, or formal approval.*

| ID | Decision | What is unset | Why it cannot be inferred |
|---|---|---|---|
| **B5** | Minimum trade count | value · derivation method · adequacy framing | Expresses tolerance for an underpowered study |
| **B6** | Uncertainty | **Block length** · **Iteration count** · **Basis for block length** · **Confidence level** | Each changes interval width and therefore the verdict |
| **B7** | Result interpretation | **the decision bar** · confidence level | Determines what counts as support |
| **B8** | Cross-asset approver | identity · approval · date | A **research judgement**, not a code fact |
| **B11 #8** | Named evaluator | identity · date | Cannot be inferred from repository ownership |
| **B11 #9** | Evaluation authorisation | written one-evaluation authority | **Is** the authorisation |
| **B10 #10** | Clean working tree | commit or stash of the owner's work | Repository action, no judgement |

**Coupling:** B6's confidence level and B7's bar are **not independent**. Fixing
one without the other lets a result clear or miss the bar on a technicality.

**Timing rule:** B5, B6 and B7 must close **before** any result exists. Each is a
number that must not depend on an outcome.

---

## Recommended order

```
 1. B9  confirm Option A            ─┐ no dependencies
 2. B3  approve registry change     │
 3. B1  choose licence              │
 4. B4  defer or reacquire         ─┘

 5. B7  framework + bar  ─┐
 6. B6  four parameters   ├─ coupled; fix jointly
 7. B5  trade count      ─┘

 8. B2  approve correction (evidence ready)

 9. B10 #5-#7  compute + record hashes
10. B10 #10    commit or stash
11. B8         approver named + dated (reads the frozen protocol)
12. B10 #9,#11  validate authorization; reservation + ID   ──► FREEZE
13. B11 #7,#8,#9                                          ──► AUTHORISE
```

---

## What must remain unchanged until approval

| Item | Current state |
|---|---|
| `research_registry.json` licence fields | Unchanged |
| `licence_knowledge` on BTC/USDT, ETH/USDT | `UNVERIFIED` |
| ETH reservation | `RESERVED` / `used: false` / `preregistration_id: null` |
| Preregistration | Not frozen, no ID |
| Protocol hashes | Not computed, not recorded, not approved |
| Git state | 0 staged, 19 modified, 394 untracked, 0 stashed |
| All historical phase reports | Preserved |

---

**This packet prepares decisions. Approving a brief is not approving a decision.**