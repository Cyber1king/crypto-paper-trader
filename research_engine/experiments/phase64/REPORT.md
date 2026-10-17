# Phase 64 — Licence Remediation Plan

**Prerequisites:** Phase 62 ECB capture; Phase 61 licence briefs.
**Safety check at start:** no new blocker.
**No governed change applied. No frozen file altered.**

---

## 1. Phase 62 ECB artifact — verified

| Field | Expected (Phase 62) | Verified now |
|---|---|---|
| SHA-256 | `424859b8d123a61a05aff299157b35d7d665599ef03415c1138f1648f1010343` | ✅ **MATCH** |
| Size | 107,678 bytes | ✅ **MATCH** |
| Path | `experiments/phase62/evidence/…html` | ✅ present |
| Retrieval | 2026-10-10T13:24:13Z, HTTP 200 | ✅ recorded in capture report |

---

## 2. Five distinct layers — kept separate

Conflating these is the error this project has corrected twice (Phase 52,
Phase 53).

| Layer | Holder | Status | Governs |
|---|---|---|---|
| **1. Code licence** | **This project's owner** | ❌ **None declared** | Python package; MIT declared for npm workspace only |
| **2. Crypto dataset licence** | **Binance** (NEST EXCHANGE LIMITED) | ✅ CC BY-NC-SA 4.0 + Vision Dataset Terms v1.0 | BTC/ETH archives and derivatives |
| **3. ECB copyright terms** | **European Central Bank** | ✅ **Captured** 2026-10-10 | Use of ECB-published information |
| **4. Provider provenance** | **Unknown** | ❌ **Unrecoverable** | *Which provider supplied the stored forex values* |
| **5. Trademark** | Binance / ECB | ✅ Not used to market | Names used descriptively only |

**Key distinction:** Layer 3 being resolved says **nothing** about Layer 4.
Copyright terms govern *use*, never *provenance*.

---

## 3. Layer 1 — Python package

**Verified:** `research_engine/pyproject.toml` declares **no** `license` field and
no licence classifier. No `LICENSE` file exists anywhere. Root `package.json`
declares MIT for npm package `"workspace"`, which `pnpm-workspace.yaml` scopes to
`artifacts/*`, `lib/*`, `lib/integrations/*`, `scripts` — **`research_engine` is
not included**.

**Current position:** all-rights-reserved by default.

**Correction proposed (NOT applied):** owner selects one of A none / B MIT /
C Apache-2.0 / D BSD-3 / E CC BY-NC-SA 4.0 and names the copyright holder.
**Owner decision — B1.**

---

## 4. Layer 2 — Binance-derived data

**Verified obligations and current discharge:**

| Obligation | Source | State |
|---|---|---|
| Attribution to Binance Vision on redistribution | §4.5 | ✅ 8 sidecars + 2 READMEs |
| Derivative works remain CC BY-NC-SA 4.0 | §4.5 | ⚠️ prose only — no machine-readable marker |
| Non-commercial use only | §3.1, §3.4 | ✅ complied |
| No sub-licence / sale / hosting | §4.3 | ✅ complied |
| No implied endorsement | §8.2–8.3 | ✅ complied |

**Correction proposed (NOT applied):** `licence_knowledge` `UNVERIFIED` →
`VERIFIED`, `licence_name` → `CC BY-NC-SA 4.0`. **Owner decision — B3.**

**Outstanding, non-blocking:** a root `NOTICE` file. **Rejected approach:** adding
SPDX headers to CSVs — that would change frozen digests and invalidate recorded
provenance. A sidecar or `NOTICE` file is the correct vehicle.

---

## 5. Layer 3 — ECB copyright terms

**Verified from the captured artifact.** The ECB grants **free use subject to
conditions**, not CC BY-NC-SA. Five conditions:

1. Information must appear accurately; **ECB must be cited as source**
2. Sold documents must carry a "free of charge" notice
3. **Modifications must be stated explicitly**
4. No framing of the ECB site on business links
5. ECB Working/Occasional Papers need prior written authorisation

**Current registry claim is wrong in both directions:** it asserts share-alike and
non-commercial terms the ECB does not impose, and omits conditions 2, 3 and 4.

**Correction proposed (NOT applied):** `licence_name` → descriptive ECB policy
label; `licence_note` → the five conditions verbatim plus URL, capture path,
SHA-256, retrieval date, and a pointer that provider attribution is unresolved.
**Owner decision — B2.**

**Still open:** ECB **Data Portal** is a distinct site, not captured.

---

## 6. Layer 4 — Provider provenance

**Verified:** no `providers=ecb` pin in the acquisition URL; Frankfurter's
documented default is to blend; the raw payload records **no provider field**.

**Correction proposed:** **none possible.** Historical provider identity is not
recoverable from repository contents. Either defer, or acquire new data with
provider pinning. **Owner decision — B4.**

**Consequence for Layer 3:** if the stored values are blended, ECB condition 3
(modification disclosure) is engaged, and that disclosure is currently absent
from every forex artefact.

---

## 7. Ordered remediation checklist

| # | Action | Type | Blocks | Approval |
|---|---|---|---|---|
| 1 | Capture ECB Data Portal terms (or defer) | Evidence | B2 sub-item | Owner |
| 2 | Approve B3 Binance registry transition | Governed state | B11 #7 | **Owner** |
| 3 | Approve B2 ECB terms correction | Governed state | B11 #7 | **Owner** |
| 4 | Decide B4 defer / reacquire | Owner judgement | B11 #7 | **Owner** |
| 5 | Choose B1 code licence | Governed state | Release | **Owner** |
| 6 | Add root `NOTICE.md` aggregating attribution | Documentation | Nothing | Owner |
| 7 | Mark derivatives CC BY-NC-SA in a sidecar | Documentation | Nothing | Owner |
| 8 | CI job asserting the ETH digest + reservation | Engineering | Nothing | Owner |

**Items 2–5 are governed-state or judgement changes and were not applied.**
Items 6–8 are proposed only.

---

## 8. What must not be done by an agent

- Selecting a code licence, or writing a `LICENSE` file.
- Editing `research_registry.json` licence or provenance fields.
- Asserting that stored forex rates are ECB observations.
- Adding SPDX headers to frozen CSVs (destroys provenance digests).
- Treating a captured licence page as provenance evidence.