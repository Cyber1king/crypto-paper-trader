# Phase 62 — B2: ECB Source Capture Report

**Date of retrieval:** 2026-10-10T13:24:13Z
**Outcome: RETRIEVAL SUCCEEDED.** The Phase 61 evidence gap is closed.

---

## 1. Capture metadata

| Field | Value |
|---|---|
| **Exact source URL** | `https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html` |
| **Page title** | `Disclaimer & copyright` |
| **Issuing organisation** | European Central Bank, Frankfurt am Main, Germany |
| **HTTP status** | **200** |
| **Content-Type** | `text/html; charset=UTF-8` |
| **Retrieval timestamp** | **2026-10-10T13:24:13Z** (UTC, ISO 8601) |
| **Retrieval method** | Python 3.12.10 `urllib.request` over HTTPS with `ssl.create_default_context()` (certificate verification enabled) |
| **Preserved artifact** | `research_engine/experiments/phase62/evidence/ecb_disclaimer_copyright_2026-10-10T13-24-13Z.html` |
| **Size** | **107,678 bytes** |
| **SHA-256 of artifact** | **`424859b8d123a61a05aff299157b35d7d665599ef03415c1138f1648f1010343`** |
| **Integrity re-verification** | Recomputed independently after writing: **identical** |
| **Version / publication date** | **No `Last-Modified` header was returned.** No version or publication date is stated on the page. None is asserted |
| **Transformations applied** | **None.** Raw response bytes were written unmodified |

---

## 2. First attempt — failed, recorded for honesty

| Field | Value |
|---|---|
| Method | PowerShell `Invoke-WebRequest` |
| URL | identical |
| Timestamp | 2026-10-10T13:23:54Z |
| Error | *"Windows PowerShell is in NonInteractive mode. Read and Prompt functionality is not available."* |
| Cause | **Client-side**, not a network or availability failure |
| Artifact | **None created** |

**[V]** The first failure was a tooling limitation, not evidence that the page
is unavailable. The second attempt used a different client and succeeded. Both
are recorded so the sequence is auditable.

---

## 3. Verbatim passage, with surrounding context

Extracted from the preserved artifact. **Not a selective excerpt** — the full
conditions list and the exception that follows it are reproduced together, because
quoting only the first bullet would misrepresent the terms.

> **Copyright**
>
> Copyright © for the entire content of this website: European Central Bank,
> Frankfurt am Main, Germany.
>
> Subject to the exception below, users of this website may make free use of the
> information obtained directly from it subject to the following conditions:
>
> - When such information is distributed or reproduced, it must appear accurately
>   and the ECB must be cited as the source.
> - Where the information is incorporated in documents that are sold (regardless
>   of the medium), the natural or legal person publishing the information must
>   inform buyers, both before they pay any subscription or fee and each time
>   they access the information taken from this website, that the information may
>   be obtained free of charge through this website.
> - If the information is modified by the user (e.g. by seasonal adjustment of
>   statistical data or calculation of growth rates) this must be stated
>   explicitly.
> - When linking to this website from business sites or for promotional purposes,
>   this website must load into the browser's entire window (i.e. it must not
>   appear within another website's frame).
>
> As an exception to the above, any reproduction, publication or reprint, in
> whole or in part, of documents that bear the name of their authors, such as ECB
> Working Papers and ECB Occasional Papers, in the form of a different publication
> (whether printed or produced electronically) is permitted only with the
> explicit prior written authorisation of the ECB or the authors.

---

## 4. What the capture establishes

| # | Established | Source text |
|---|---|---|
| 1 | Copyright is held by the **ECB** for its website content | *"Copyright © … European Central Bank, Frankfurt am Main, Germany."* |
| 2 | Use is **free** but **conditional** | *"may make free use … subject to the following conditions"* |
| 3 | **Attribution is required** on distribution or reproduction | *"the ECB must be cited as the source"* |
| 4 | Accuracy must be preserved | *"it must appear accurately"* |
| 5 | A **resale notice** is required for sold documents | *"…must inform buyers … that the information may be obtained free of charge through this website"* |
| 6 | **Modification must be stated explicitly** | *"If the information is modified by the user … this must be stated explicitly."* |
| 7 | A **framing restriction** applies to business links | *"must load into the browser's entire window"* |
| 8 | **Authored works** need prior written authorisation | ECB Working/Occasional Papers exception |

---

## 5. What the capture does **NOT** establish

| Question | Status |
|---|---|
| That the **ECB Data Portal** (`data.ecb.europa.eu`) has identical terms | **Not established.** It is a distinct site and was not captured |
| That the stored daily rates in `data/phase33/` are **ECB-published observations** | **Not established.** Terms say nothing about provider provenance — see `B4_ECB_PROVENANCE_DECISION.md` |
| Any publication or version date for these terms | **None stated.** No `Last-Modified` header; no date on the page |
| That the terms were the same at the time the data was acquired (2024–2026) | **Not established.** This is a 2026-10-10 capture of a page with no visible version date |

**The fourth point matters.** Terms may have changed during the acquisition
window. The capture documents what the ECB publishes **now**.

---

## 6. Limitations

1. **Point-in-time capture.** No version identifier exists. Any future use
   should re-verify and note the date.
2. **HTML, not PDF.** The page's raw HTML was preserved. A PDF link exists on the
   ECB site but was not captured; the two could differ in wording.
3. **English version only.** **[V]** The ECB publishes this in ~24 languages and
   states in its own Terms of Use that *"in the event of any inconsistency …
   the English version shall prevail"* — a statement captured separately in
   Phase 53, not re-verified here.
4. **Website scope only.** The captured terms govern *"this website"*. Whether
   the **Data Portal** or bulk CSV exports are covered by identical terms is
   **unverified**.
5. **No legal interpretation.** This report records published text and checksums
   only.

---

## 7. Effect on B2

| Phase 61 status | Phase 62 status |
|---|---|
| 🔴 **Blocked on missing evidence** — *"the ECB copyright page has never been captured as an artefact"* | ✅ **Evidence gap CLOSED.** Source captured, checksummed, stored in-repo, excerpted with context |

**What remains is an owner decision, not an evidence gap** — see
`B2_ECB_CORRECTION_PROPOSAL.md`.

**The separate Data Portal question remains open** and is item 2 in that
document's owner decision.