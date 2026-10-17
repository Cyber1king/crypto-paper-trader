# Phase 47 Source Research

**Date:** 2026-10-09
**Method:** Live web search against official documentation. Every capability
claim below is traceable to a URL. Anything not verifiable is labelled
**UNVERIFIED** rather than assumed.

**No source was contacted for data.** No API key was used, requested, or stored.

---

## 1. Candidate: ECB Euro Foreign Exchange Reference Rates

| Field | Finding |
|---|---|
| Publisher | European Central Bank |
| Official documentation | `https://data.ecb.europa.eu/help/api/data` |
| Dataflow | `EXR` |
| Web service entry point | `https://data-api.ecb.europa.eu/service/` |
| Content | Daily euro foreign exchange reference rates |
| Series key form | `D.USD.EUR.SP00.A` (freq.currency.denominator.type.variation) |
| Coverage observed | 04 Jan 1999 → 07 Oct 2026 |
| Update cadence | Updated ~16:00 CET each working day, except TARGET closing days |
| Basis | Daily concertation procedure between European central banks, ~14:10 CET |
| Auth | None observed for the public portal |
| Licensing | ECB reproduction policy applies; ECB data is CC BY 4.0 for many datasets |

### Two findings that matter more than the rest

**1. The ECB itself disclaims transactional use.** Its own documentation states
the reference rates are "published for information purposes only" and that
"using the rates for transaction purposes is strongly discouraged."

This is the publisher speaking, not this project's inference. It independently
corroborates the decision to keep forex blocked, and it is stronger evidence
than an internal argument would have been.

**2. The rates are fixing timestamps, not bar timestamps.** Reference rates are
set at ~14:10 CET and published at ~16:00 CET. There is no intraday path, so no
`high` or `low`, therefore no OHLC bar. Converting these to hourly candles would
fabricate the volatility a strategy trades on.

### Repository note

Phase 33 recorded `Served by: frankfurter.app (open-source API over ECB data)`.
Phase 46's registry now distinguishes:

- **Publisher:** European Central Bank
- **Retrieval endpoint:** frankfurter.app
- `checksum_published: false` — ECB does not publish digests for these series

The ECB Data Portal was initially recorded as the source URL in Phase 46 and
**corrected** once the registry validation rejected it and the Phase 33 manifest
was re-read. Had the schema been loosened, the registry would have carried a
confident and wrong provenance claim.

---

## 2. Candidate: BLS Release Schedule (economic calendar)

| Field | Finding |
|---|---|
| Publisher | U.S. Bureau of Labor Statistics |
| Documentation | `https://www.bls.gov/schedule/news_release/current_year.asp` |
| Machine-readable | `https://www.bls.gov/bls/api_features.htm` |
| API base | `https://api.bls.gov/publicAPI/v2/timeseries/data/` |
| Content | Release dates, times and series for US economic indicators |
| Timezone | **All times on the calendar are Eastern Time** — stated explicitly on the page |
| Coverage | Year-at-a-time HTML schedule; current-year page observed for 2026 |
| Cadence | Schedule published in advance; individual releases monthly or quarterly |
| Auth | **Not required for the public API**; a registration key unlocks optional calculations, catalog data and annual averages |
| Rate limits | **UNVERIFIED** — not stated in the pages consulted |
| Licensing | U.S. Government work; redistribution generally permitted with attribution |

### Verified observations

- Times are consistently **08:30 or 10:00 Eastern**, matching BLS convention.
- Releases are distinguishable: `Employment Situation`, `CPI`, `PPI`, `JOLTS`.
- Preliminary vs revised releases are marked in the release name, e.g.
  `Productivity and Costs (P)` then later `(R)`. **This matters**: it means
  `revised` in `EconomicEvent` is a real, source-expressible distinction rather
  than a hypothetical one.
- Holidays appear as rows with no release, e.g. `New Year's Day`,
  `Columbus Day` — relevant to the Phase 46 holiday-calendar requirement.
- BLS documents a **one-day lag between publication and API availability**. Any
  evidence pipeline must account for it rather than assuming same-instant access.

### Limitation for this project

The calendar is **HTML**, not a documented JSON schedule endpoint. The JSON API
covers *series values*, not the release schedule. Parsing an HTML page for event
times would be scraping, and its robustness is unverified. Not implemented.

---

## 3. Candidates considered and NOT adopted

| Source | Why not adopted |
|---|---|
| **ECB Data Portal EXR API** | Verified and documented, but it serves **daily fixings only**. No session semantics, no OHLC. Cannot support evaluation |
| **frankfurter.app** | Used in Phase 33 for retrieval. Open-source API over ECB data; **licence terms UNVERIFIED** — not confirmed in this phase |
| **BLS JSON API** | Gives values, not the schedule. Schedule is HTML |
| **Crypto news wires** (Reuters/Bloomberg/CoinDesk) | **All licence-restricted.** Redistribution and automated access require agreements. None obtained |
| **Crypto sentiment indices** | Widely used; **methodology largely proprietary and licence-restricted.** UNVERIFIED for automated use |
| **Coingecko / CoinMarketCap free tiers** | Have public APIs but licence, retention and historical depth terms **UNVERIFIED** |
| **Exchange announcements** | Per-venue, inconsistent format, no uniform licence |

**No scraping was attempted.** Public visibility does not grant redistribution
rights, and none of these sources' terms were confirmed to permit automated
redistribution into a research repository.

---

## 4. What this means for the pipeline

### Usable without credentials

- ECB reference rates (daily fixings) — already acquired in Phase 33, blocked for evaluation on documented grounds.
- BLS release schedule as **reference reading** for a human, not as an automated feed.

### Requires agreements not obtained

- Any news wire content.
- Any commercial sentiment index.
- Any redistributable market-data licence.

### Blocked on data, not access

- Forex OHLC: no source in this repository or verified in this phase serves
  intraday bars with session and DST semantics.

---

## 5. Licensing summary

| Source | Licence | Redistribution | Attribution |
|---|---|---|---|
| ECB reference rates | ECB reproduction policy; many ECB datasets CC BY 4.0 — **exact terms for EXR UNVERIFIED** | UNVERIFIED | Required |
| BLS schedule / API | U.S. Government work | Generally permitted | Required |
| frankfurter.app | **UNVERIFIED** | UNVERIFIED | UNVERIFIED |
| Binance Vision | **UNVERIFIED** (recorded as such in the registry) | UNVERIFIED | Required |
| News wires | Restricted | Prohibited without agreement | Required |
| Sentiment indices | Restricted | Prohibited without agreement | Required |

`licence_knowledge: UNVERIFIED` is a **recorded state, not a gap in diligence**.
It means the terms were not confirmed in this phase, and it prevents an
unverified assumption from hardening into an unexamined claim. The Phase 45
schema validates this distinction rather than treating every entry as either
verified or absent.

---

## 6. Honest limits

- Web search surfaced documentation; **no endpoint was called**. Field-level API
  behaviour — exact JSON shapes, pagination, error codes — is **UNVERIFIED**
  beyond what the documentation states.
- Rate limits and pricing were **UNVERIFIED** for BLS and were not published on
  the pages consulted.
- `frankfurter.app`'s licence was not confirmed, though it was used in Phase 33.
  That use is now recorded explicitly in the registry rather than left implicit.
- Coverage of any news source over 2024–2026 at the fidelity this research would
  need is **UNVERIFIED**. Free historical news APIs are typically shallow, and
  shallow coverage used as if complete would be a silent correctness problem.

---

## 7. Sources consulted

1. `https://data.ecb.europa.eu/help/api/data` — ECB SDMX API documentation
2. `https://data.ecb.europa.eu/data/datasets/EXR` — EXR series and coverage
3. `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html` — reference-rate basis and publication cadence
4. `https://www.bls.gov/schedule/news_release/current_year.asp` — release schedule and Eastern Time convention
5. `https://www.bls.gov/bls/api_features.htm` — BLS public API, auth, publication lag

No source was contacted for data. No credential was used or requested.