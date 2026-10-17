# Phase 50 Feature Truth Matrix

**Date:** 2026-10-09
**Method:** Every row was checked against running code, not against a report.

Labels, used exactly as instructed:

| Label | Meaning |
|---|---|
| **IMPLEMENTED AND TESTED** | Code path exists, tests exercise it, tests pass |
| **IMPLEMENTED BUT INCOMPLETELY VERIFIED** | Code exists; verification is partial |
| **MOCKED** | Only a mock or stub exists; no real capability |
| **PLANNED** | Specified in a document; no code |
| **BLOCKED** | Real capability, deliberately unavailable |
| **NOT IMPLEMENTED** | No code path |

---

## 1. Capability matrix

| # | Capability | Label | Evidence |
|---|---|---|---|
| 1 | Crypto data ingestion | **IMPLEMENTED AND TESTED** | `load_ohlcv_csv`, `normalize_source`, 27+32 tests; publisher checksums verified *before* parsing |
| 2 | Publisher-checksum verification | **IMPLEMENTED AND TESTED** | `provenance.verify_publisher_checksum`; mismatch refuses, quarantine mode exists |
| 3 | Reproducible manifests | **IMPLEMENTED AND TESTED** | `build_manifest` / `verify_manifest`; provenance ceiling A only when all inputs verified |
| 4 | Forex data (OHLC) | **BLOCKED — missing data** | ECB daily fixings only; no intraday range exists |
| 5 | Forex session/holiday/DST validation | **NOT IMPLEMENTED** | No module exists; `classify_intervals` refuses forex explicitly |
| 6 | Instrument registry | **IMPLEMENTED AND TESTED** | 5 instruments, 13-field metadata; 73 schema tests |
| 7 | Registry metadata validation | **IMPLEMENTED AND TESTED** | 22 contradiction classes refused; `load_registry` fails closed |
| 8 | Dataset validation (crypto) | **IMPLEMENTED AND TESTED** | positivity, finiteness, OHLC, ordering, duplicates, interval, timezone |
| 9 | Research guards | **IMPLEMENTED AND TESTED** | 6 entry points refuse reserved ETH; 8 series shapes probed |
| 10 | Omission-bypass closure | **IMPLEMENTED AND TESTED** | per-bar index; 60+40 tests |
| 11 | ETH evaluation reservation | **IMPLEMENTED AND TESTED** | `RESERVED` / `used: false` / `prereg: null`, asserted 4× in the API tests |
| 12 | News evidence ingestion | **NOT IMPLEMENTED** | No adapter; `evidence.available = false` by design |
| 13 | Economic-event retrieval | **NOT IMPLEMENTED** | Same |
| 14 | Evidence schema | **IMPLEMENTED AND TESTED** | `evidence.py`, 72 tests; no provider attached |
| 15 | Sentiment analysis | **NOT IMPLEMENTED** | Schema exists; no source, no scoring |
| 16 | **Claude integration** | **NOT IMPLEMENTED** | Docs verified; **zero** client code, zero calls |
| 17 | **Kimi integration** | **NOT IMPLEMENTED** | Not researched; **zero** client code |
| 18 | **DeepSeek integration** | **NOT IMPLEMENTED** | Not researched; **zero** client code |
| 19 | AI-generated analysis | **MOCKED** | Interface + 73 mocked tests. No provider, ever called |
| 20 | AI provider *status reporting* | **IMPLEMENTED AND TESTED** | `/api/research/providers`; static, no network |
| 21 | Dashboard data integration | **IMPLEMENTED BUT INCOMPLETELY VERIFIED** | 4 routes + 5 panels; verified against a **stub**, never a live backend |
| 22 | Dashboard honesty guards | **IMPLEMENTED AND TESTED** | 43 new tests; added to `LIVE_FILES` inventory |
| 23 | Paper-trading modes (standard) | **IMPLEMENTED AND TESTED** | pre-existing, unchanged by Phases 49–50 |
| 24 | `ai_intelligence` mode | **IMPLEMENTED AND TESTED** | Deterministic arithmetic gate. **Not AI**; behaviour unchanged |
| 25 | **Profitability evidence** | **BLOCKED** | One pre-registered test: net PF **0.4925**, INCONCLUSIVE |

---

## 2. The four AI rows, stated carefully

This is where overclaiming is most likely, so the detail matters.

### Claude / Anthropic

| Question | Answer | Basis |
|---|---|---|
| Documentation verified? | **YES** | `platform.claude.com` + `docs.anthropic.com`, Batch 2 |
| Client implemented? | **NO** | `ai_research.py` imports only stdlib |
| Credentials present? | **NO** | `os.environ` absent from the module |
| Requests ever made? | **NO** | no network import anywhere in the package |
| Tests? | 73 **mocked** | a mock satisfies the protocol; no provider is exercised |

**A discrepancy was recorded rather than resolved:** the two official pages
disagree on model identifiers (`claude-sonnet-5` vs `claude-sonnet-5-5`), both
documenting deprecations. No model name is hard-coded anywhere.

### Kimi and DeepSeek

**Not researched.** No documentation consulted, no client, no claim made about
capability or suitability. The dashboard renders them as
`DOCS NOT RESEARCHED` — distinct from unavailable, because "we did not look" and
"we looked and it is unsuitable" are different facts.

### AI-generated analysis — MOCKED, not implemented

`ResearchAnalysis` and `AIResearchProvider` are real code. **The ability to
produce an analysis is not.** Every test uses a mock conforming to the protocol.
The Phase 50 audit re-verified: `ai_research.py` imports
`__future__, dataclasses, datetime, enum, json, typing` — no network, no
provider SDK, no environment read.

`ResearchAnalysis` is a **schema for an output that does not exist yet**.

---

## 3. Instrument status — checked against the running backend

| Instrument | Registry state | Evaluation supported | Why |
|---|---|---|---|
| BTC/USDT | `RESEARCH_CONSUMED` | **no** | all three windows spent |
| ETH/USDT | `DATA_VERIFIED_NOT_RESEARCH_APPROVED` | mechanically yes, **not approved** | no preregistration, no authorization record |
| EUR/USD | `BLOCKED_WRONG_DATA_TYPE` | **no** | not OHLC; no session/DST validator |
| GBP/USD | `BLOCKED_WRONG_DATA_TYPE` | **no** | same |
| USD/JPY | `BLOCKED_WRONG_DATA_TYPE` | **no** | same |

`evaluation_supported` means *the pipeline could mechanically run one*. It is
**not** approval, and the API test
`test_listed_instrument_is_not_implied_approved` asserts the two are never
conflated.

---

## 4. Provenance and licensing — real gaps

| Source | Grade | Licence |
|---|---|---|
| BTC/USDT | **A** | **UNVERIFIED** |
| ETH/USDT | **A** | **UNVERIFIED** |
| ECB pairs | **B** | **VERIFIED** — CC BY-NC-SA 4.0, non-commercial |

`UNVERIFIED` is a recorded state, not a gap in diligence. It prevents an
unverified assumption from hardening into an unexamined claim, and Phase 46's
schema validation enforces the distinction.

---

## 5. Dashboard — what is and is not verified

| Area | Label | Note |
|---|---|---|
| Four read-only routes | **IMPLEMENTED AND TESTED** | 58 tests; writes refused on all four |
| Five panels | **IMPLEMENTED AND TESTED** | 43 tests; honesty properties asserted |
| Integration with a **live** backend | **NOT RUN** | all frontend tests use `setDefaultApi` stub |
| Accessibility (axe / screen reader) | **NOT RUN** | implemented by construction, unmeasured |
| Responsive behaviour | **NOT RUN** | Tailwind breakpoints applied, no viewport test |
| Visual regression | **NOT RUN** | |

---

## 6. Summary counts

| Label | Count |
|---|---|
| IMPLEMENTED AND TESTED | 17 |
| IMPLEMENTED BUT INCOMPLETELY VERIFIED | 1 |
| MOCKED | 1 |
| PLANNED | 0 |
| BLOCKED | 3 |
| NOT IMPLEMENTED | 5 |

**Nothing is described as working on the basis of a specification, a placeholder
or a mocked response.** The one MOCKED row is labelled MOCKED precisely because
that is all it is.