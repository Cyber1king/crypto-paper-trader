# Phase 61 — B2: ECB Terms and Rights Evidence Brief

**Status: `OWNER DECISION REQUIRED` — blocked on missing evidence.**

---

## 1. What the repository currently claims

`research_engine/data/research_registry.json`, for **EUR/USD, GBP/USD, USD/JPY**:

```
licence_knowledge : "VERIFIED"
licence_name      : "CC BY-NC-SA 4.0"
licence_note      : "ECB reference rates are published under CC BY-NC-SA 4.0.
                     Non-commercial use only, share-alike, attribution required.
                     Commercial use is excluded."
attribution_required : true
```

---

## 2. What the repository directly supports

**[V] Nothing in the repository substantiates that claim.**

```
$ git grep -In "ECB" -- "*.md" "*.txt" | grep -Ei "licen|copyright|CC BY|terms|attribut|reproduc"
  (no results)
```

| What exists | What it proves |
|---|---|
| `data/phase33/MANIFEST_FOREX_ECB_daily_reference_rates.txt` | Acquisition URLs, retrieval metadata, checksum evidence |
| `data/phase33/_forex_meta.json` | `source: "European Central Bank euro foreign exchange reference rates"` — an **assertion**, not a citation |
| Normalised CSV `source` column | `European_Central_Bank_via_frankfurter.app` — accurate about the *path*, silent about transformation |
| Normalised CSV `rate_type` column | `ECB_reference_rate` — an **assertion** |
| Zero ECB licence documents | **The registry label has no in-repository source** |

**Conclusion:** the `CC BY-NC-SA 4.0` label was **recorded without captured
evidence**. It is not corroborated by anything in the repository.

---

## 3. What was retrieved externally (and is not retained)

**[R]** Phase 53 fetched the ECB's *Disclaimer & copyright* page on 2026-10-09 and
recorded: free use subject to conditions — cite the ECB as source; **state
modifications explicitly**; give buyers of sold documents a "free of charge"
notice; no framing; ECB Working/Occasional Papers need prior written
authorisation. It also recorded that ECB reference rates are *"published for
information purposes only"*.

**This text exists only in a phase report. It was never captured as an artefact
with its own integrity record.**

---

## 4. Assessment of the current label

| Claim in `licence_note` | Assessment against the ECB page recorded in Phase 53 |
|---|---|
| "CC BY-NC-SA 4.0" | **Unsupported.** ECB does not publish under a Creative Commons grant |
| "Non-commercial use only" | **Not imposed** by the ECB copyright clause |
| "share-alike" | **Not imposed** by the ECB copyright clause |
| "attribution required" | **Supported** — *"the ECB must be cited as the source"* |
| "Commercial use is excluded" | **Not imposed** by the ECB copyright clause |

**The label is wrong in both directions:** it asserts obligations the ECB does
not impose, and it **omits** duties the ECB does impose — most importantly
**explicit modification disclosure**.

**Crucially:** correcting the label is a correction of *terms*. It says nothing
about whether the stored values are ECB observations. That is B4.

---

## 5. Evidence that must be captured

| # | Item | Value |
|---|---|---|
| 1 | **Source URL** | `https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html` |
| 2 | **Publisher** | European Central Bank, Frankfurt am Main |
| 3 | **Retrieval date** | to be recorded at capture time |
| 4 | **Relevant passage** | the *Copyright* section, quoted verbatim |
| 5 | **Retained copy** | a dated text or PDF stored in-repo, with its own SHA-256 |
| 6 | **Currency note** | a statement that the copy is a point-in-time capture, and that the ECB may amend its policy |

### Capture checklist

- [ ] Fetch the page and store a dated copy under e.g.
      `research_engine/data/provenance/ecb_copyright_<retrieval-date>.txt`
- [ ] Record the retrieval date and the URL in the file header
- [ ] Record the SHA-256 of the stored copy
- [ ] Quote the *Copyright* section verbatim in the registry `licence_note`
- [ ] Add a note that the capture is point-in-time and re-check on any future use
- [ ] **Separately:** verify whether the **ECB Data Portal** (`data.ecb.europa.eu`)
      has its own terms — it is a distinct site and was never checked

---

## 6. Proposed correction (NOT APPLIED)

| Field | Current | Proposed |
|---|---|---|
| `licence_name` | `"CC BY-NC-SA 4.0"` | `"ECB website copyright policy (free use with conditions)"` |
| `licence_note` | See §1 | ECB conditions verbatim + URL + retrieval date + an explicit statement that the stored values' provider attribution is unresolved |
| `licence_knowledge` | `"VERIFIED"` | **Unchanged** — the right to use for non-commercial research is established; the *description* was wrong |

**[V]** `licence_name` is free text; only `licence_knowledge` is schema-constrained
(`registry_schema.py` L307, L89). The change is schema-valid.

---

## 7. What this decision does and does not resolve

| Resolves | Does not resolve |
|---|---|
| The incorrect terms label | **Whether the stored rates are ECB observations** (B4) |
| The missing in-repo citation | Forex's data-quality blocker (daily fixings are not OHLC) |
| Attribution/modification-disclosure obligations | Whether the ECB Data Portal has different terms |

---

## 8. Exact owner decision required

> **"I approve the B2 correction [as written / as amended: …]. I also approve
> [capturing the ECB copyright page in-repo with a dated copy and SHA-256 /
> deferring that]. Approved by [name], [date]."**

**Not to be done by OpenCode:** applying the registry change, capturing the
page, or asserting that the stored rates are ECB-sourced.

---

## 9. Legal uncertainty

**This brief does not offer a legal conclusion.** It reports what a publisher's
own published text says and where the repository diverges from it. Whether the
ECB's terms permit a particular downstream use is a question for the owner,
potentially with counsel. What is stated here is narrower and checkable: **the
registry's label is not supported by the ECB's recorded terms.**