# Batch 2 — Phases 46–48 Final Report

**Date:** 2026-10-09

---

## 1. Phase verdicts

| Phase | Verdict | Basis |
|---|---|---|
| **46** — Multi-market data pipelines | **PASS** | 8 unvalidated provenance fields closed; publisher-checksum verification and manifests implemented; forex still blocked with reasons documented |
| **47** — News, economic calendar, sentiment | **PASS** | Two sources verified from official documentation; evidence schema implemented with 72 tests; no provider contacted |
| **48** — AI market research layer | **PASS** | Provider-independent interface implemented and tested; live integration explicitly NOT IMPLEMENTED |

No phase was skipped. No phase was blocked.

---

## 2. Tests actually run

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

| Stage | Result |
|---|---|
| Focused: Phases 46+47+48 + guards + validation | **473 passed**, 12.6s |
| Full suite, 44 files | **2441 passed, 0 failed** |

2230 (end of Batch 1) → 2441: **211 new tests**, none executing strategy logic.

**No timeouts. No skips. No deletions. No xfail. No test weakened.**

Two slow files are pre-existing and unchanged: `test_high_risk.py` (527s) and
`test_phase14c_analysis.py` (189s).

### Test files created (3)

| File | Tests |
|---|---|
| `tests/test_data_pipeline.py` | 66 |
| `tests/test_evidence_schema.py` | 72 |
| `tests/test_ai_research.py` | 73 |

### Test fixtures updated

`_instrument()` and `instrument()` helpers now emit valid provenance fields, using
`example.invalid` (a reserved non-resolvable TLD) so a fixture can never resemble
a real source. Fixtures were updated to satisfy a **stricter** schema; no
assertion was relaxed.

### Two tests failed on first run — self-reference

A secret-pattern scan matched its own pattern list; an assertion that
`researchguard` was absent matched a prose mention in a docstring. Both fixed by
scanning structurally via the AST. Substring scans give false positives against
test code and false confidence against code that merely *discusses* a name.

---

## 3. Verified external sources and licensing limitations

### Verified (official documentation, no data endpoint contacted)

| Source | Verified |
|---|---|
| **ECB reference rates** | SDMX entry point `data-api.ecb.europa.eu/service/`, `EXR` dataflow, series keys `D.USD.EUR.SP00.A`, coverage 1999-01-04 → 2026-10-07 |
| **BLS release schedule** | Eastern Time convention, 08:30/10:00 releases, preliminary `(P)` vs revised `(R)`, holiday rows |
| **BLS public API** | No registration required; **one-day publication→availability lag** |
| **Anthropic Claude API** | `POST /v1/messages`, `anthropic-version` header, `Authorization: Bearer` / `x-api-key` / WIF, `ANTHROPIC_API_KEY`, workspace scoping |

### Two findings that changed the project's position

**1. The ECB disclaims transactional use of its own reference rates** — "published
for information purposes only", using them "for transaction purposes is strongly
discouraged." The publisher independently corroborates keeping forex blocked.

**2. The Phase 46 schema caught a wrong provenance claim.** Phase 46 initially
recorded the ECB Data Portal as the forex `source_url_pattern`; validation
rejected it, and the Phase 33 manifest revealed acquisition used
`frankfurter.app`. The registry now distinguishes **publisher (ECB)** from
**retrieval endpoint (frankfurter.app)**. Had the check been loosened, the
registry would have carried a confident, wrong claim about its own data.

### Licensing limitations

| Source | State |
|---|---|
| ECB reference rates | ECB reproduction policy; **exact EXR terms UNVERIFIED** |
| BLS | U.S. Government work; attribution required |
| frankfurter.app | **UNVERIFIED** — used in Phase 33, terms not confirmed |
| Binance Vision | **UNVERIFIED** — recorded as such |
| News wires (Reuters, Bloomberg, CoinDesk) | **Restricted** — redistribution prohibited without agreement |
| Sentiment indices | **Restricted**; methodology largely proprietary |
| Anthropic data retention | **UNVERIFIED** — blocker to sending research data |

`licence_knowledge: UNVERIFIED` is a recorded state, not a gap in diligence. It
prevents an unverified assumption from hardening into an unexamined claim.

---

## 4. Implemented vs mocked provider integrations

| Provider | Client | Credentials | Tested | Docs |
|---|---|---|---|---|
| Anthropic (Claude) | **NO** | none | mocked only | **verified** |
| Kimi | **NO** | none | mocked only | **NOT RESEARCHED** |
| DeepSeek | **NO** | none | mocked only | **NOT RESEARCHED** |

**Zero providers integrated. Zero credentials. Zero provider calls.**

Implemented: the **interface only** — `AIResearchProvider`, `ProviderRequest`,
`ProviderResponse`, `ResearchAnalysis`, `AnalysisPipeline`, `redact_secrets`.

### A discrepancy recorded rather than resolved

The two official Anthropic pages consulted **disagree on model identifiers**:
`docs.anthropic.com` lists `claude-sonnet-5` / `claude-opus-5`;
`platform.claude.com` lists `claude-sonnet-5-5` / `claude-opus-5-5`. Both
document deprecations with EOL dates.

**No model name was hard-coded anywhere.** The correct answer is `GET /v1/models`
at integration time.

### Seven tests assert *absence*, not presence

No provider client · no network import anywhere in the package · no credential
lookup at all · no secret fixtures · AI unreachable from the trading engine ·
AI cannot import `researchguard` · no concrete provider class exists.

A mocked suite is not evidence that any provider works, and this report does not
present it as such.

---

## 5. Crypto and forex readiness

### Crypto spot — pipeline strengthened

| Capability | Status |
|---|---|
| Venue + instrument identity | required and validated |
| Source URL + provenance | required; http(s) enforced |
| Publisher-checksum verification | implemented; runs before parsing |
| Reproducible manifests | implemented; provenance ceiling A only when all inputs verified |
| Schema + OHLCV validation | unchanged from Phase 41 |
| Duplicate + missing-interval detection | unchanged from Phase 41 |
| Volume semantics | required, cannot be inferred |
| Dataset hashes | required |

Two new refusal classes: **reproducible ≠ publisher-verified** (ceiling drops to
`B` when inputs lack digests), and **symbol coherence** — a wrong native symbol
is how one instrument's data is fetched under another's name.

### Forex — still BLOCKED

| Blocker | Type |
|---|---|
| No OHLC data (ECB serves one daily fixing) | missing data |
| No session/holiday/DST validator | missing implementation |
| No licensed tick or bar source | missing source |

Session boundaries, weekend closures, holiday calendars, DST transitions, price
precision, and spread modelling were **documented as not implemented rather than
invented**. ECB daily reference rates were **not** converted to hourly OHLC. No
candle or spread was synthesised.

---

## 6. Files created and modified

### Created (11)

| File | Purpose |
|---|---|
| `src/crypto_paper_lab/provenance.py` | Publisher checksums + manifests |
| `src/crypto_paper_lab/evidence.py` | News/event/sentiment records |
| `src/crypto_paper_lab/ai_research.py` | Provider-independent AI interface |
| `tests/test_data_pipeline.py` | 66 tests |
| `tests/test_evidence_schema.py` | 72 tests |
| `tests/test_ai_research.py` | 73 tests |
| `experiments/phase46/DATA_PIPELINE_REPORT.md` | |
| `experiments/phase46/VERIFICATION.md` | |
| `experiments/phase47/SOURCE_RESEARCH.md` | |
| `experiments/phase47/EVIDENCE_SCHEMA.md` | |
| `experiments/phase47/VERIFICATION.md` | |
| `experiments/phase48/AI_ARCHITECTURE_REPORT.md` | |
| `experiments/phase48/PROVIDER_STATUS.md` | |
| `experiments/phase48/VERIFICATION.md` | |

### Modified (3 tracked)

| File | Change |
|---|---|
| `registry_schema.py` | Source-provenance validation (10 new checks) |
| `research_registry.json` | Forex provenance corrected; `checksum_url_pattern`, `retrieval_endpoint` recorded |
| `dataset.py` | (Batch 1 change, unchanged here) |

Tracked: 11 files, +368/−11. Untracked: 312. Nothing staged, committed, pushed,
or deleted.

---

## 7. ETH reservation status

```
status                     : RESERVED
used                       : False
preregistration_id         : None
research_approval          : DATA_VERIFIED_NOT_RESEARCH_APPROVED
approved_preregistration_id: None
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

**No ETH 2026 performance was computed, inspected or revealed.** The two Phase 46
tests reading the file assert row count, endpoint timestamps and digest only.

---

## 8. Frozen artifact verification — 11 of 11

BTC primary · BTC holdout · Phase 29 preregistration · ETH dataset · four Phase 30
result artifacts · Phase 33 acquisition report · Phase 34 audit · Phase 35
correction. All matched the exact previously recorded values. **No baseline
re-derived; nothing silently updated.**

---

## 9. Git state

```
branch            main
HEAD              dccebbd  (== origin/main)
ahead / behind    0 / 0
staged            none
tracked modified  11 files, +368 / -11
untracked         312
```

---

## 10. Remaining blockers

**ETH evaluation** — eight prerequisites still unmet, from Batch 1 Phase 44 and
unchanged: research question, configuration choice, costs, execution assumptions,
thresholds, uncertainty reporting, stopping rules, cross-asset authorization
record. None invented.

**Forex** — three independent blockers, documented not faked.

**Provider integration** — no credentials; interface ready; docs verified for one
provider, unresearched for two.

**Licensing** — four sources remain UNVERIFIED; all news and sentiment sources
are redistribution-restricted.

**Known limitation, stated plainly:** `assert_no_probability_claims` is lexical.
It will not catch "there is a strong chance". A semantic check would need a
model, which is circular.

**Another:** clustering and conflict detection in Phase 47 are structural. An item
is flagged as conflicting when its credibility note contains "conflict"; nothing
infers that two reports actually disagree.

---

## 11. Next permitted action

**Permitted:** drafting the ETH research question and preregistration without
observing results; verifying remaining licences; specifying an event-calendar
ingestion adapter against a documented source; implementing a provider adapter
**if** a credential is supplied via environment (never in chat or source).

**Prohibited:** any backtest/replay/walk-forward against ETH 2026; reading ETH
2026 performance; reusing any consumed BTC window; tuning on ETH data; modifying
the frozen BTC config; setting thresholds after results; converting ECB rates to
OHLC; inventing forex session/DST rules; representing a mocked integration as
working; scraping restricted sources; staging or committing.

---

## 12. What this batch does not establish

2441 passing tests mean the pipeline refuses contradictory provenance, evidence
records enforce their discipline, and the AI interface is coherent and bounded.

They say nothing about profitability. No AI provider is connected, and the mocked
tests demonstrate the *contract*, not any provider's behaviour.

The one pre-registered out-of-sample evaluation this project has run returned a
net profit factor of 0.4925 and was recorded as inconclusive. Nothing since has
changed that.

`BATCH 2 PHASES 46–48: PASS`