# Phase 57 — Owner Sign-off Sheet (B1–B3)

**Date:** 2026-10-09
**Purpose:** Step 4 — auditable sign-off sheets for the three licensing decisions.

> **No licence has been selected. No registry state has been changed. No legal
> position has been adopted on the owner's behalf.**

---

## B1 — Python package licence

### Decision
Choose the licence, or explicitly keep none, for the `crypto-paper-lab` Python
package.

### Evidence

| Fact | Source |
|---|---|
| Root `package.json`: `"name": "workspace"`, `"license": "MIT"` | file |
| `pnpm-workspace.yaml` = `artifacts/*`, `lib/*`, `lib/integrations/*`, `scripts` | file |
| **`research_engine` is not in that workspace** | file |
| `research_engine/pyproject.toml` has **no** `license` field, no classifier | file |
| **No `LICENSE` file anywhere in the repository** | tracked-file search |
| README states *"Tooling — no licence granted"* | Phase 53 edit |
| No SPDX headers anywhere | grep |

**Scope statement.** `research_engine/` is a separate distributable from the npm
workspace. The root MIT declaration does **not** reach it. The Python package is
therefore **unlicensed — all rights reserved by default**.

### Options

| Option | Exact scope | Consequence | Consequence for data |
|---|---|---|---|
| **A. No licence (status quo)** | No one may lawfully copy, modify or redistribute the Python code | Blocks all third-party reuse. Safe default; almost certainly unintentional given the rest of the repo is permissive | Unaffected |
| **B. MIT** | Any use incl. commercial; redistribution with notice; **no** patent grant | Consistent with the JS tooling; widest reuse; simplest to apply | Unaffected |
| **C. Apache-2.0** | As MIT, plus explicit patent grant and a NOTICE obligation | Consistent; adds patent clarity plus a NOTICE file to maintain | Unaffected |
| **D. BSD-3-Clause** | As MIT, plus a no-endorsement clause | Consistent; common for research code | Unaffected |
| **E. CC BY-NC-SA 4.0 on code** | Non-commercial only; **share-alike propagates to all derivatives** | Any derived work becomes non-commercial. Conflicts with keeping tooling permissive and separate from data terms | Aligns code with data terms |

### Recommendation
**None made.** The deciding factor — intended reuse — is an owner preference not
derivable from the repository. **If consistency with the existing JS tooling is
the priority, option B is the conventional match.**

### Alternative consideration
Option E's share-alike has a compounding effect most owners would not intend: a
non-commercial restriction would attach to anything built from this code.

### Exact approval required
> "I select option **[A/B/C/D/E]** for `crypto-paper-lab`, effective
> **[date]**, approved by **[name]**."
>
> For B/C/D/E, name the copyright holder to put in the licence header.

---

## B2 — ECB registry correction

### Decision
Whether to correct the `licence_name` / `licence_note` for EUR/USD, GBP/USD and
USD/JPY, and whether to capture the ECB page in-repo first.

### Evidence — verified source terms

| Fact | Status |
|---|---|
| Registry asserts `CC BY-NC-SA 4.0` for all three pairs | **Verified** — `research_registry.json` |
| **No ECB licence documentation exists in the repository** | **Verified** — `git grep` across `*.md`/`*.txt` returns nothing |
| The label has no URL, retrieval date or quoted source | **Verified** |
| ECB grants free use with conditions: cite ECB, **state modifications**, resale notice, no framing | **Publisher-sourced**, retrieved 2026-10-09 (Phase 53) |
| The label asserts share-alike and non-commercial terms ECB does **not** impose | **Verified** by comparison |
| The label **omits** modification-disclosure and resale duties ECB **does** impose | **Verified** |

### Evidence — NOT verified (provenance)

| Question | Status |
|---|---|
| Are the stored rates ECB-published observations? | **UNVERIFIED — see B4** |
| Do ECB **Data Portal** terms differ from website terms? | **Unverified** — not separately checked |

> **This correction is about *terms*, not provenance.** It must not be read as
> certifying that the stored numbers are ECB fixings. Those values' provider
> identity is unresolved (B4).

### Proposed change

| Field | Existing | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | *"…published under CC BY-NC-SA 4.0. Non-commercial use only, share-alike, attribution required. Commercial use is excluded."* | ECB conditions verbatim + source URL + retrieval date 2026-10-09 + explicit note that stored values may be provider-blended |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use is established; only the description was wrong |

Full wording: `phase54/ECB_REGISTRY_CORRECTION_PROPOSAL.md` §2.

### Consequences
- **Correcting** removes an obligation that does not exist (share-alike) and a
  prohibition that does not exist (non-commercial), and adds two duties that do
  (modification disclosure, resale notice).
- **Not correcting** leaves the registry asserting terms its own publisher's text
  does not support — and it is the machine-readable surface a future
  integration would consult.
- **Not correcting** also leaves `licence_knowledge: VERIFIED` resting on a claim
  that was never sourced.

### Precondition — the gap to close first
**Capture the ECB page into the repository as a dated citation.** Without it, the
correction replaces one unsourced label with another. This is the single item
preventing B2 from being fully evidence-backed.

### Exact approval required
> "I approve the B2 correction as **[written / amended as follows]** for EUR/USD,
> GBP/USD and USD/JPY; I also approve **[capturing the ECB page in-repo /
> deferring that]**; approved by **[name]**, **[date]**."

---

## B3 — Binance registry state

### Decision
Whether to transition BTC/USDT and ETH/USDT `licence_knowledge` from
`UNVERIFIED` to `VERIFIED`.

### Evidence

| Evidence | Location | Strength |
|---|---|---|
| CC BY-NC-SA 4.0 + Vision Dataset Terms stated | 8 × `data/oos/raw/*.provenance.txt` L46 | Strong — per-dataset |
| Permitted / prohibited uses stated | same sidecars | Strong |
| Licence split (tooling vs data) recorded | `phase9/DATA_SOURCE_REVIEW.md` L39 — *"Verified"* | Strong |
| Publisher terms v1.0, 26 Aug 2026 | Re-fetched Phase 52 / 53 / 55, unchanged | Strong — publisher-controlled |
| Attribution + share-alike stated in READMEs | Phase 53 edits | Strong |

### Schema compatibility
`LICENSE_KNOWLEDGE = {"VERIFIED", "UNVERIFIED", "RESTRICTED"}`
(`registry_schema.py` L89). `UNVERIFIED → VERIFIED` is a **permitted value**.

**[V]** The schema's own standard (L86–88): *"Licence states this repository can
state with confidence. Anything else must be recorded as `UNVERIFIED` rather
than guessed."* The Binance evidence comfortably clears that bar.

**[V]** The current `UNVERIFIED` marker is a **regression below the repository's
own documentation** — Phase 9 already recorded the licence as verified.

### Exact before/after

**Before** (both BTC/USDT and ETH/USDT):
```
licence_knowledge : "UNVERIFIED"
licence_name      : null
licence_note      : "Same provider and same unestablished redistribution
                     terms as BTC/USDT."   (ETH)
```

**After:**
```
licence_knowledge : "VERIFIED"
licence_name      : "CC BY-NC-SA 4.0"
licence_note      : cites Binance Vision Dataset Terms v1.0 (26 Aug 2026)
                    s3.1 and s4.5; attribution to Binance Vision required on
                    redistribution; derivatives remain CC BY-NC-SA 4.0;
                    commercial use excluded without a separate written
                    enterprise agreement (s3.4)
```

### Consequences
- **Approving** makes the machine-readable registry agree with the evidence
  already in the repository, and removes a false implication that redistribution
  terms are unestablished.
- **Declining** leaves a deliberately conservative marker that contradicts
  Phase 9, Phase 10 and eight provenance sidecars.
- Either way, the underlying use (personal, non-production, non-commercial) is
  permitted and unaffected by the label.

### Exact approval required
> "I approve the B3 transition to `VERIFIED` / `CC BY-NC-SA 4.0` for BTC/USDT
> and ETH/USDT, with the licence_note as written; approved by **[name]**,
> **[date]**."

---

## Summary

| ID | Evidence complete? | Blocked on | Code change needed |
|---|---|---|---|
| **B1** | Yes — scope verified | Owner licence choice | `pyproject.toml` + `LICENSE` |
| **B2** | **Partly** — terms verified, provenance not | Owner sign-off **+ capturing the ECB page** | Registry `licence_name` / `licence_note` |
| **B3** | **Yes** — evidence in-repo, schema-valid | Owner sign-off only | Registry licence fields |

**B3 is the only one of the three requiring nothing but a signature.**

**None of the three has been applied.** No licence selected, no registry field
changed, no legal approval claimed.