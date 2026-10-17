# Phase 55 — Governance Status

**Date:** 2026-10-09
**Scope:** B1–B4, B9, B10 — the items that are not evaluation gates.

**No governed registry state was changed. No legal approval is claimed or
implied.**

---

## Status at a glance

| ID | Item | Status | Can be prepared now? | Needs authoritative evidence? | Needs owner approval? |
|---|---|---|---|---|---|
| **B1** | Python package licence | **OPEN** | Yes | No | **Yes** |
| **B2** | ECB registry correction | **READY FOR APPROVAL** | Yes — done | **Yes** — ECB page should be captured in-repo | **Yes** |
| **B3** | Binance `licence_knowledge` | **READY FOR APPROVAL** | Yes — done | No — evidence already in-repo | **Yes** |
| **B4** | ECB data provenance / re-acquisition | **DEFERRED** | Partly | **Yes** | **Yes** |
| **B9** | Confirm Option A | **READY FOR APPROVAL** | Yes — done | No | **Yes** |
| **B10** | Preregistration freeze | **BLOCKED on gates** | Partly | No | **Yes** |

**Separation of concerns.** B2, B3 and B9 are *fully prepared* — the analysis
and the proposed wording are done, and only a signature is missing. B4 is the
one item that genuinely cannot be closed without new external evidence. B10 is
mechanically blocked by B5–B8 and B11.

---

## B1 — Python package licence

**Status: `OPEN — OWNER DECISION REQUIRED`**

**Verified facts.**

| Fact | Evidence |
|---|---|
| Root `package.json` declares `"license": "MIT"` for npm package `"workspace"` | file |
| `pnpm-workspace.yaml` scopes that to `artifacts/*`, `lib/*`, `lib/integrations/*`, `scripts` | file |
| **`research_engine` is not in that workspace** | file |
| `research_engine/pyproject.toml` has **no** `license` field and no licence classifier | file |
| **No `LICENSE` file exists anywhere in the repository** | tracked-file search |
| `research_engine/README.md` states "no licence granted" | Phase 53 edit |

**Accurate position:** the JS tooling carries an MIT declaration; the Python
research engine is **unlicensed — all rights reserved by default**.

**Options and consequences.**

| Option | Effect | Consequence |
|---|---|---|
| MIT | Permissive | Consistent repo-wide; permits commercial reuse and relicensing of derivatives |
| Apache-2.0 | Permissive + patent grant | Adds patent terms and NOTICE obligations |
| BSD-3-Clause | Permissive + no-endorsement | Common for research code |
| **No grant** | All-rights-reserved | Default today; blocks all reuse. Often unintentional |
| CC BY-NC-SA 4.0 on code | Non-commercial, share-alike | **Would propagate NC to derived works** and conflicts with keeping tooling permissive and separate from data terms |

**Prepared now?** Yes. **No licence was selected** — that is the owner's
decision, and it is a grant of rights, not a technical finding.

**Interaction with data.** Whichever option is chosen applies to **code only**.
It cannot alter the CC BY-NC-SA 4.0 terms on Binance-derived data, which Binance
sets.

**Decision required:** choose A/B/C/D/E and name the approver.

---

## B2 — ECB registry correction

**Status: `READY FOR APPROVAL` — analysis complete, awaiting sign-off**

**Verified facts.**

| Fact | Evidence |
|---|---|
| Registry asserts `CC BY-NC-SA 4.0` for EUR/USD, GBP/USD, USD/JPY | `research_registry.json` |
| **Zero ECB licence documentation exists in the repository** | `git grep` across `*.md`/`*.txt` |
| The label is unsourced — no URL, retrieval date or quoted text | as above |
| ECB's own terms grant free use with conditions: cite ECB, **state modifications**, resale notice, no framing | Phase 53 retrieval, 2026-10-09 |
| The label asserts a share-alike obligation that does not exist | Phase 53 + 54 |
| The label asserts an NC restriction that does not exist | Phase 53 + 54 |
| The label **omits** modification-disclosure and resale duties that do apply | Phase 53 + 54 |
| Acquisition URLs carried **no `providers=ecb` pin** | Phase 33 manifest |
| Stored raw JSON has no provider/attribution field | file inspection |

**Proposed change** (written out in full in
`phase54/ECB_REGISTRY_CORRECTION_PROPOSAL.md`): replace `licence_name` and
`licence_note`; leave `licence_knowledge` at `VERIFIED`.

**Prepared now?** **Yes** — wording, rationale, evidence and transition steps
are all complete. **No registry write was performed.**

**Authoritative evidence still needed?** **Yes, and this is the one genuine gap.**
The ECB page should be **captured into the repository as a dated citation** so
the label is sourced. Phase 53 fetched it externally; Phase 54 confirmed nothing
in-repo backs the current label. Until it is captured, the correction would
replace one unsourced label with another.

**Decision required:** approve the wording; approve or defer capturing the ECB
page; name the approver and date.

---

## B3 — Binance `licence_knowledge` status

**Status: `READY FOR APPROVAL` — evidence already in-repo**

**Verified facts.**

| Fact | Evidence |
|---|---|
| Registry records `UNVERIFIED`, `licence_name: null`, note *"unestablished redistribution terms"* | `research_registry.json` |
| Terms are **CC BY-NC-SA 4.0** + Vision Dataset Terms v1.0, 26 Aug 2026 | publisher, re-fetched Phase 52/53/55 |
| Eight provenance sidecars already state the licence | `data/oos/raw/*.provenance.txt` L46 |
| Phase 9 recorded the licence as **Verified** | `DATA_SOURCE_REVIEW.md` L39 |
| The registry is **less accurate than the repository it governs** | comparison |

**Proposed change:** `licence_knowledge` → `VERIFIED`, `licence_name` →
`CC BY-NC-SA 4.0`, `licence_note` citing Vision Dataset Terms v1.0 §3.1.

**Prepared now?** **Yes.** This is the rare governance item whose evidence is
**already durable in the repository** — no external capture is needed.

**Decision required:** approve the transition; name the approver and date.

---

## B4 — ECB data provenance and possible re-acquisition

**Status: `DEFERRED` — cannot be closed without new evidence or acquisition**

**Verified facts.**

| Fact | Evidence |
|---|---|
| Forex data exists: `ecb_reference_rates_daily_*.csv` + raw JSON | `data/phase33/` |
| Schema is `date,pair,rate,rate_type,source` — **daily fixings, not OHLC** | file |
| Manifest: *"THIS IS NOT AN OHLC DATASET"*, cannot load via the canonical loader | manifest |
| Acquisition URL: `…/2024-01-01..2026-10-08?from=EUR&to=USD` — **no `providers=ecb`** | manifest |
| Frankfurter's documented default is to **blend** across providers | publisher docs |
| Raw JSON keys: `amount, base, start_date, end_date, rates` — **no provider field** | file |
| `rate_type` asserts `ECB_reference_rate` | file |

**The unresolved question:** whether the stored values are unmodified ECB
fixings or provider-blended figures. **This cannot be determined from the
repository.**

**Why it matters:** if blended, ECB's explicit condition — *"if the information
is modified by the user … this must be stated explicitly"* — is engaged, and
the series is a derived figure, not an ECB fixing.

**Options.**

| Option | Action |
|---|---|
| 1 | **Defer.** Forex stays blocked on data quality; no exposure. **Recommended** |
| 2 | Re-acquire with `providers=ecb` and compare values |
| 3 | Inspect the Phase 33 acquisition code to determine the actual request |

**Prepared now?** Partly — the question is precisely framed. **Resolving it
requires either acquisition (out of scope) or code archaeology.**

**Decision required:** defer, re-acquire, or investigate the acquisition path.

**Note:** forex is blocked on **data quality** regardless — daily reference
fixings are not OHLC, and no session/holiday/DST modelling exists. Resolving
licensing **would not unblock forex**.

---

## B9 — Confirmation of Option A

**Status: `READY FOR APPROVAL`**

**The recommendation:** Option A — a single pre-registered ETH evaluation window,
executable now with no code change.

**Verified basis.**

| Fact | Evidence |
|---|---|
| The strategy has **no fitted parameters** | `walkforward.py` exposes `config_hash`, no estimation; README excludes optimisation frameworks |
| `run_backtest` already supports a `ResearchContext` | `backtest.py` |
| Option A requires **no code change** | design review |
| Option A weakens **no** safeguard | all controls remain active |
| Segmentation would give robustness checks, not train/test generalisation | no fitted model exists |
| Multiplicity risk is higher under segmentation | design review |
| Reserved evidence is consumed irreversibly | reservation semantics |

**Prepared now?** **Yes** — the analysis is complete and recorded in
`phase54/ETH_EVALUATION_READINESS.md`.

**Decision required:** confirm Option A, or direct Option B (which requires the
`validate_dataset_integrity` change first, and its own phase).

---

## B10 — Preregistration freeze

**Status: `BLOCKED` on B5–B8 and B11**

**A freeze cannot proceed yet.** It requires:

| Prerequisite | State |
|---|---|
| B5 minimum trade count | `OPEN` |
| B6 block length / iterations | `OPEN` |
| B7 decision rule and bar | `OPEN` |
| B8 cross-asset approver | `OPEN` |
| `config_hash`, `costs_hash`, `dataset_fingerprint` recorded | Pending freeze |
| Preregistration ID assigned | Not assigned |
| B11 authorisation | `OPEN` |

**What has been prepared.** The consolidated draft exists at
`phase55/PREREGISTRATION_DRAFT.md`, with every unresolved field explicitly
marked `OPEN — OWNER DECISION REQUIRED`. It is **not frozen** and carries
**no ID**.

**Nothing about the freeze requires further analysis.** Once B5–B8 close, it is
a mechanical step: record the three hashes, assign the ID, update the
reservation, validate the cross-asset record.

**Decision required:** close B5–B8, then authorise the freeze.

---

## Summary

| Item | Can be closed by analysis? | Blocked on |
|---|---|---|
| B1 | No — owner's grant decision | Human |
| B2 | Analysis done; needs ECB page captured | Human + evidence capture |
| B3 | Analysis done; evidence already in-repo | Human |
| B4 | **No** — needs acquisition or code archaeology | Human |
| B9 | Analysis done | Human |
| B10 | No — mechanical, but prerequisites open | B5–B8, B11 |

**Three of six (B2, B3, B9) are ready for signature today.** B1 needs only an
owner's choice. B4 is the single item that cannot be closed without new external
input, and it is also the one with the least operational consequence.

**Nothing in this document authorises a registry change, a licence grant, a
legal conclusion, or an evaluation.**