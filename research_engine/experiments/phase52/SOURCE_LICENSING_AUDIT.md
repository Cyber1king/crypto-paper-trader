# Phase 52 — Source Licensing Audit

**Date:** 2026-10-09
**Scope:** authoritative licence/provenance verification for research data sources
**Status:** audit only — no registry writes, no data acquisition, no code changes

---

## 0. Method

Two rules governed this audit.

**Rule 1 — A licence is verified only from the publisher's own current text.**
Not from a blog, not from an aggregator, not from a library that happens to
wrap the data, not from a README that describes the data rather than the code.

**Rule 2 — The wrapper is not the content.**
An API that serves a dataset does not thereby acquire rights to that dataset.
Where the wrapper explicitly defers to the upstream publisher, the publisher's
terms govern, and the endpoint's own permissiveness is irrelevant to the rights
in the values.

---

## 1. Which four items were actually UNVERIFIED

The instruction was to identify the exact four sources rather than guess. Reading
the actual records gives a materially different answer than the phrase "four
sources" suggests, and the difference matters:

```
$ registry → licence_knowledge
  BTC/USDT  UNVERIFIED   provider 'Binance Vision'
  ETH/USDT  UNVERIFIED   provider 'Binance Vision'
  EUR/USD   VERIFIED     European Central Bank
  GBP/USD   VERIFIED     European Central Bank
  USD/JPY   VERIFIED     European Central Bank

  UNVERIFIED entries        : 2
  distinct publishers behind them : 1
```

**The registry contains two UNVERIFIED entries, from one publisher.**

The "four" originates in Phase 50's `SECURITY_AUDIT.md`, which recorded "Four
sources have UNVERIFIED licensing", and in Phase 47's `SOURCE_RESEARCH.md`,
whose licence table marked four *rows* unverified across a wider candidate set:

| # | Recorded item | Kind | Registry entry? |
|---|---|---|---|
| 1 | **Binance Vision** | publisher, in use | Yes — 2 instruments |
| 2 | **frankfurter.app** | retrieval endpoint, used in Phase 33 | No — not a publisher |
| 3 | **Crypto sentiment indices** | candidate, not adopted | No |
| 4 | **BLS / rate-limit details** | candidate, not adopted | No |

So "four" is defensible as *four recorded items* but is **wrong as a count of
sources**. It conflates one publisher counted twice with two retrieval/candidate
entries. Phase 50's sentence should be corrected. This audit treats items 2–4 as
unresolved provenance questions and item 1 as the only live compliance question,
because only item 1 governs data actually in the repository.

---

## 2. Item 1 — Binance Vision · **RESOLVED**

**Publisher:** NEST EXCHANGE LIMITED (ADGM Recognised Investment Exchange), per
Vision Dataset Terms §1.3.
**Governing document:** *BINANCE VISION DATASET TERMS*, Version 1.0,
**Last Updated: August 26, 2026**.
**Retrieved from:** `binance-public-data` repository, `TERMS_AND_CONDITIONS.md`,
the file the repository's own README designates as "Dataset Terms".

### The trap this resolves

The `binance-public-data` README ends with a bare `## Licence / MIT`. Read
alone, that says the data is MIT-licensed and the UNVERIFIED marker is
over-cautious. Read in full, the README's *Dataset Terms* section points to a
separate document — and **that document grants nothing MIT**. The repository
MIT covers the repository's own tooling. The data carries different, stricter
terms. Treating the README's MIT line as covering the archives would have been
the single most costly misreading available here.

### What the terms actually grant

| Clause | Effect |
|---|---|
| §3.1 | Datasets under **CC BY-NC-SA 4.0** except where designated otherwise |
| §3.4 | **Commercial licensing strictly excluded.** Commercial use requires a separate written enterprise data licence executed with Binance |
| §4.1 | Permitted non-commercial use: academic research, non-monetised open educational projects, **"algorithmic historical backtesting for purely personal non-production research"**, non-commercial open-source data-science evaluations |
| §4.2 | Prohibited: live proprietary trading execution, automated **commercial** order generation, signal distribution to third parties for compensation |
| §4.3 | Prohibited: licence, sub-licence, sell, rent, lease, host, or commercially exploit the Datasets or derivative feeds |
| §4.4 | Prohibited: integration into commercial financial products, hedge-fund tools, paid subscription newsletters, **commercial trading-bot platforms** |
| §4.5 | Redistribution of derivative works must **attribute Binance Vision** and remain **CC BY-NC-SA 4.0** |
| §5.3 | Binance may modify, redact or discontinue any pair/dataset/endpoint without notice |
| §7.2 | No scraping or automation designed to circumvent rate limits |
| §9.2 | Datasets contain no personal data; de-anonymisation prohibited |
| §1.4 | Amendments apply **prospectively**; rights to already-downloaded datasets under the terms in force at download are preserved |

**§4.1 expressly names this project's use case.** Personal, non-production,
algorithmic historical backtesting is permitted non-commercial use. The
project's paper-only, non-monutised posture falls inside the grant.

**§1.4 matters retrospectively:** the datasets here were downloaded before
26 August 2026, and the audit asserts the terms in force at download govern
them. That preserves the use right; it does not preserve a right to ignore the
obligations attached to it.

---

## 3. Item 2 — frankfurter.app · **ENDPOINT PERMISSIVE, CONTENT NOT**

Frankfurter's own documentation settles this against the intuitive answer:

> **Is the API free for commercial use?**
> Yes. **The rates themselves fall under each provider's terms.**

The endpoint is permissive. The rates are ECB's, under ECB's terms. Frankfurter's
permissiveness transfers nothing.

This is the cleanest illustration of Rule 2 in the whole audit: a green licence
on the retrieval layer, and no change whatsoever to the rights in the data
retrieved through it. Anyone auditing only the API's terms would have concluded
"commercial use fine" and been wrong about the payload.

Phase 47 was right to mark this UNVERIFIED, and right to record it as a
*retrieval* dependency rather than a publisher.

---

## 4. Item 3 — Crypto sentiment indices · **REMAINS UNVERIFIED**

Phase 47 recorded these as proprietary and licence-restricted, with methodology
not open to inspection. No attempt was made to upgrade that status: nothing is
adopted, nothing is fetched, and auditing licence text for a source that is not
integrated would produce a document about a hypothetical. The correct state
remains **UNVERIFIED / RESTRICTED**, and it should stay that way until a
specific provider is proposed for a specific purpose.

---

## 5. Item 4 — BLS · **REMAINS UNVERIFIED, NOT ADOPTED**

Phase 47 recorded rate limits as unstated in the pages consulted. Unadopted,
unfetched, unchanged. Recorded here only so the count of four stays traceable to
actual prior records rather than to repetition.

---

## 6. The finding that matters more than the licence

Having established that redistribution requires attribution (§4.5) and that
CC BY-NC-SA share-alike propagates to derivatives, the audit checked what the
repository actually contains:

```
$ git ls-files | wc -l                     → 204 tracked files
  Binance-derived tracked                  → 44
  raw .csv tracked                         → 14
  original .zip archives tracked           → 9
  .CHECKSUM files tracked                  → 9
  attribution / licence / NOTICE files     → 0
```

The nine original Binance Vision ZIP archives, their checksums, eleven extracted
CSVs and nine acquisition reports are **committed to this repository**, and
**there is no attribution or licence notice file anywhere in it.**

Against §4.5 that is an unmet obligation today, on the present facts. It is a
documentation gap, not a misuse — nothing here is sold, hosted or monetised, and
the use itself is permitted under §4.1. But the obligation is live, not
conditional on the repo going public: CC BY-NC-SA attribution attaches to
redistribution, and the archives are already in a distributed version-control
system.

Two mitigating facts worth stating plainly, because they bound the problem:

- The **ETH reserved archive is not tracked** — it stayed local. The dataset
  under Phase 51's governance is not in git.
- The **ECB/frankfurter material is not tracked** either, so the unresolved
  frankfurter provenance question carries no current distribution exposure.

---

## 7. Out of scope

- The Binance Terms of Use PDF (ADGM/binance RIE) was not read end to end. The
  Vision Dataset Terms are supplemental to it (§1.2) and prevail for these
  datasets (§1.5), so the operative grant is established; the parent terms were
  not independently characterised.
- The ECB copyright page returned HTTP 404 at the URL consulted. The registry's
  `CC BY-NC-SA 4.0` claim for ECB rows therefore stands **un-re-verified in this
  audit** — it entered the registry via the frankfurter dependency, which is
  precisely the transitive-provenance weakness this audit exists to surface.
  It is not contradicted here; it is simply unconfirmed. Flagged for a follow-up
  that fetches the ECB's own notice.

---

## 8. Conclusion

One of the four resolves cleanly and **materially better than "UNVERIFIED"**:
Binance Vision is CC BY-NC-SA 4.0, personal non-production backtesting is
expressly permitted, and the project's current posture is inside the grant.

Three remain unresolved and stay that way.

The licence question is settled. The **compliance obligation it creates is not**,
and that — an attribution file owed on 44 already-tracked Binance-derived files —
is the actionable output of this phase.