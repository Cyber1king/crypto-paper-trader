# Phase 47 Verification

**Date:** 2026-10-09

---

## 1. Source research verification

Method: live web search against **official documentation pages only**. No data
endpoint was contacted. No API key was used, requested, or stored.

| Source | Documentation consulted | Verified |
|---|---|---|
| ECB SDMX API | `data.ecb.europa.eu/help/api/data` | Entry point `data-api.ecb.europa.eu/service/`, `EXR` dataflow, series-key structure |
| ECB EXR dataset | `data.ecb.europa.eu/data/datasets/EXR` | Coverage 04 Jan 1999 → 07 Oct 2026, `D.USD.EUR.SP00.A` form |
| ECB reference-rate policy | `ecb.europa.eu/stats/policy_and_exchange_rates/...` | Fixing ~14:10 CET, published ~16:00 CET, **"strongly discouraged" for transactional use** |
| BLS schedule | `bls.gov/schedule/news_release/current_year.asp` | Eastern Time convention, 08:30/10:00 releases, preliminary `(P)` vs revised `(R)`, holiday rows |
| BLS API features | `bls.gov/bls/api_features.htm` | Public API needs no registration; **one-day publication→availability lag** |

### Two findings that changed the project's position

**1. The ECB disclaims transactional use of its own reference rates.** Its
documentation states they are "published for information purposes only" and that
using them "for transaction purposes is strongly discouraged."

This is the publisher speaking. It independently corroborates keeping forex
blocked, from a stronger position than an internal argument would have been.

**2. BLS marks preliminary and revised releases distinctly** (`(P)` vs `(R)`),
which confirms `EconomicEvent.revised` is a real, source-expressible distinction
rather than a hypothetical field.

### Also verified, and worth noting

Phase 46 initially recorded the ECB Data Portal as the forex `source_url_pattern`.
The new registry validation **rejected the registry**, and re-reading the Phase 33
manifest revealed the truth: acquisition used `frankfurter.app`, an open-source
API over ECB data. The registry now distinguishes publisher (ECB) from retrieval
endpoint (frankfurter.app). Had the validation been loosened, the registry would
have carried a confident, wrong provenance claim.

---

## 2. Tests actually run

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

| Command | Result | Duration |
|---|---|---|
| `pytest tests/test_evidence_schema.py` | **72 passed** | 0.2s |
| `pytest tests/test_data_pipeline.py` | 66 passed | 1.4s |
| Combined Phase 46 + 47 + guards + validation | **400 passed** | 12.1s |

`test_evidence_schema.py` coverage:

| Area | Tests |
|---|---|
| Required attribution (blank fields) | 5 parametrised + URL + unknown kind |
| Timestamp handling | naive refused (2), offset normalised, undated permitted but unusable, never invented, future-dated not fresh |
| Freshness / staleness | fresh, stale, expired, thresholds pinned, published-vs-retrieved, age bands, explicit window |
| Licensing | missing attribution refuses, not-required permits, public visibility ≠ redistribution |
| Syndication / duplicates | original required, own-source refused, 5 copies = 1 claim, conflicts counted, member≠conflict, deterministic representative |
| Economic events | 4 required fields, enum enforcement, occurred/not, unscheduled has no time, values need source, forecast-without-actual, actual never invented, cancellation note, revision note, naive refused, no headline inference |
| Sentiment | methodology required, value in scale, inverted scale, normalised is not a probability, staleness, 7 forbidden fields, clean record accepted, None not a violation, contrarian flag |
| Serialisation | 3 round-trip tests |

**Entirely synthetic. No provider contacted. No article fetched. No credential
exists in this repository.**

---

## 3. Prohibited-workflow compliance

| Rule | Verification |
|---|---|
| No strategy backtest / simulation / replay | No engine call in Phase 47 code or tests |
| No ETH 2026 performance | No dataset read at all in Phase 47 tests |
| No consumed-window reuse | No evaluation performed |
| No fabricated news | All test records use `example.invalid` (reserved TLD) |
| No fabricated events | Synthetic BLS-shaped records only; no real values asserted |
| No fabricated provider responses | No provider is implemented |
| No secrets in source, logs or fixtures | Phase 47 introduces no credential handling |
| No scraping | BLS HTML schedule deliberately **not** parsed |
| No test weakened | New tests only |

---

## 4. Licensing limitations carried forward

| Source | State |
|---|---|
| ECB reference rates | ECB reproduction policy; **exact EXR terms UNVERIFIED** |
| BLS schedule / API | U.S. Government work; attribution required |
| frankfurter.app | **UNVERIFIED** — used in Phase 33, terms not confirmed |
| Binance Vision | **UNVERIFIED** — recorded as such in the registry |
| News wires (Reuters, Bloomberg, CoinDesk) | **Restricted** — redistribution prohibited without agreement |
| Sentiment indices | **Restricted**; methodology largely proprietary |

`licence_knowledge: UNVERIFIED` is a recorded state, not a gap in diligence. It
prevents an unverified assumption from hardening into an unexamined claim, and
the Phase 45 schema validates the distinction rather than treating every entry as
either verified or absent.

---

## 5. Not implemented, and why

| Item | Reason |
|---|---|
| BLS calendar ingestion | Schedule is HTML; parsing it would be scraping. Structure provided, retrieval not implemented |
| Any news provider | No licence agreement; all wires are redistribution-restricted |
| Any sentiment provider | Licence restricted; methodology unverifiable |
| ECB EXR ingestion into the pipeline | Data already acquired in Phase 33; blocked for evaluation on documented grounds |
| Sentiment scoring | Would require a validated methodology that does not exist here |

---

## 6. Interpretation

400 passing tests mean evidence records enforce their declared discipline:
timestamps must be unambiguous, undated items are never shown as fresh,
attribution is required, syndication is not counted as corroboration, economic
values require a stated source, and sentiment cannot be presented as a forecast.

They say nothing about whether news or sentiment predicts any instrument's
returns. No such evidence exists in this project, and none was sought.