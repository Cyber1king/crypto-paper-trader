# Phase 62 — B2: ECB Registry Correction Proposal

**Status: `OWNER DECISION REQUIRED` — proposal only, NOT APPLIED.**
Evidence gap closed in Phase 62; the remaining blocker is the owner's decision.

---

## 1. Current repository claim

`research_engine/data/research_registry.json`, for **EUR/USD, GBP/USD, USD/JPY**:

```
licence_knowledge    : "VERIFIED"
licence_name         : "CC BY-NC-SA 4.0"
licence_note         : "ECB reference rates are published under CC BY-NC-SA 4.0.
                        Non-commercial use only, share-alike, attribution required.
                        Commercial use is excluded."
attribution_required : true
```

**[V] Before Phase 62, this label had no in-repository source.** It now does.

---

## 2. What the captured evidence establishes

Source: `evidence/ecb_disclaimer_copyright_2026-10-10T13-24-13Z.html`,
SHA-256 `424859b8d123a61a05aff299157b35d7d665599ef03415c1138f1648f1010343`,
retrieved 2026-10-10T13:24:13Z, HTTP 200. Full detail in
`B2_ECB_SOURCE_CAPTURE_REPORT.md`.

| Current claim | Against captured ECB text |
|---|---|
| *"CC BY-NC-SA 4.0"* | **Not supported.** The ECB grants no Creative Commons licence; it grants free use under its own conditions |
| *"Non-commercial use only"* | **Not imposed** by the captured copyright clause |
| *"share-alike"* | **Not imposed** by the captured copyright clause |
| *"attribution required"* | ✅ **Supported** — *"the ECB must be cited as the source"* |
| *"Commercial use is excluded"* | **Not imposed** by the captured copyright clause |

**The label errs in both directions:** it asserts two obligations the ECB does
not impose, and it **omits three duties the ECB does impose**:

| Omitted duty | ECB text |
|---|---|
| **Modification must be stated explicitly** | *"If the information is modified by the user … this must be stated explicitly."* |
| **Resale notice** | *"…must inform buyers … that the information may be obtained free of charge through this website."* |
| **Framing restriction** | *"must load into the browser's entire window"* |

**The most consequential omission is modification disclosure**, because whether
that duty is engaged depends on the unresolved provenance question (B4).

---

## 3. What the capture does **not** establish

| Not established | Consequence |
|---|---|
| That the stored daily rates are ECB-published observations | **B4 remains open.** Terms do not speak to provider identity |
| That the ECB **Data Portal** terms are identical | A **separate capture is required** before bulk-export use |
| Any publication/version date for the terms | Point-in-time capture only; 2026-10-10 |
| That the terms were unchanged across 2024–2026 acquisition | Possible historical drift, unverifiable |

**No inference about historical provider provenance is drawn from these terms.**
Doing so would be a category error: copyright terms govern *use*, not
*provenance*.

---

## 4. Proposed correction (NOT APPLIED)

| Field | Current | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | see §1 | The five ECB conditions quoted verbatim, plus: source URL; capture path; capture SHA-256; retrieval date 2026-10-10; an explicit statement that the stored values' provider attribution is **unresolved (B4)**; and a note that Data Portal terms are unverified |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use for non-commercial research is established; the *description* was wrong |
| `attribution_required` | `true` | **Unchanged** — correctly `true` |

**[V]** `licence_name` is free text; only `licence_knowledge` is
schema-constrained (`registry_schema.py` L307, L89). The change is schema-valid.

---

## 5. Attribution, modification-disclosure and provenance implications

**Attribution — now discharged for the first time.** No forex artefact currently
cites the ECB. The correction would create that citation, satisfying the
captured requirement *"the ECB must be cited as the source"*.

**Modification disclosure — conditionally engaged.** The duty applies *"if the
information is modified by the user"*. **[V]** Whether the stored series is
unmodified ECB data is unresolved (B4): the acquisition URL carried no
`providers=ecb` pin, Frankfurter's documented default is to blend, and the raw
payload records no provider. **If blended, the disclosure is required and is
currently absent from every forex artefact.**

**Provenance — unchanged by this correction.** A licence label describes *use
rights*; it never certifies *data lineage*.

---

## 6. Attribution and disclosure requirements if approved

| # | Requirement | Status after approval |
|---|---|---|
| 1 | Cite the ECB as source wherever rates are reproduced | ✅ via `licence_note` |
| 2 | Preserve accuracy of any reproduction | ✅ — data stored unaltered |
| 3 | State explicitly any modification | ⚠️ **Conditional on B4** |
| 4 | Resale notice for sold documents | N/A — no paid product |
| 5 | No framing of the ECB site in business links | N/A — no such link |
| 6 | Prior written authorisation for authored works (Working/Occasional Papers) | N/A — only EXR rates stored |

---

## 7. Exact owner approval required

> **"I approve the B2 correction as written [or as amended: …] for EUR/USD,
> GBP/USD and USD/JPY, on the basis of the ECB copyright page captured at
> `research_engine/experiments/phase62/evidence/` (SHA-256 `424859b8…`, retrieved
> 2026-10-10). Approved by [name], [date]."**
>
> **And, separately:** **"[I also approve capturing the ECB Data Portal terms /
> defer that until forex integration is proposed]."**

**Not to be done by OpenCode:** applying the registry change, altering
`licence_knowledge`, or asserting that the stored rates are ECB observations.