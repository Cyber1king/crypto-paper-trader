# Phase 65 — Market-Data Provenance Audit

**Prerequisites:** Phase 33 manifests, Phase 62 ECB capture, registry.
**Safety check at start:** no new blocker.
**No dataset downloaded, no synthetic OHLC created, no reserved-period
performance inspected.**

---

## 1. Dataset inventory and per-dataset verdicts

Legend: **S** structural quality · **A** source attribution · **U** permitted use ·
**R** approved for research · **X** blocked/deferred.

| Dataset | Path | S | A | U | R | Notes |
|---|---|---|---|---|---|---|
| **BTC primary** | `data/BTCUSDT_1h_Cleaned (1).csv` | ✅ | ✅ | ✅ | ✅ | Binance Vision; frozen, used for development |
| **BTC OOS** | `data/oos/binance_spot_BTCUSDT_1h_2026{01..08}.csv` | ✅ | ✅ | ✅ | ⚠️ | 9 months; consumed windows recorded |
| **ETH reserved** | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` | ✅ | ✅ | ✅ | ❌ | `RESERVED` — not research-approved |
| **Forex daily rates** | `data/phase33/ecb_reference_rates_daily_*.csv` | ✅ | ❌ | ⚠️ | ❌ | **Provider attribution unresolved (B4)** |
| **Forex raw** | `data/phase33/raw_forex_ecb_daily/*.json` | ✅ | ❌ | ⚠️ | ❌ | **No provider field recorded** |

**Legend key:** ✅ satisfied · ⚠️ partial/conditional · ❌ not satisfied.

---

## 2. Verified provenance evidence

| Dataset | Checksum evidence | Manifest | Sidecars |
|---|---|---|---|
| BTC primary | Registry SHA + prefix `201a3b15…` | Phase 9/10 | — |
| BTC OOS | `.CHECKSUM` per archive + sidecar SHA | Phase 10 | ✅ 8 `.provenance.txt` with licence text |
| ETH reserved | SHA-256 `7507c100…` matches registry and manifest L19 | Phase 33 | ✅ manifest + meta |
| Forex | Manifest records raw SHA-256s | Phase 33 manifest | ⚠️ **no provider attribution** |

**[V] Integrity re-verified this phase:** ETH dataset **MATCH**; BTC primary
prefix **unchanged**.

---

## 3. Structural quality — what is and is not established

**Verified for all crypto datasets:** contiguous 1h spacing, strictly increasing
timestamps, no duplicates, OHLC ordering, finite values — enforced by
`dataset.py` / `dataset_validation.py` and covered by tests.

**Deliberately NOT re-audited this phase:**

| Not done | Reason |
|---|---|
| Gap/duplicate scan over the ETH **evaluation** slice | Would require reading reserved-period data beyond metadata; prohibited by constraint 3 |
| Quality re-scan of OOS months | Already validated in Phase 10 with reports retained |

**[V]** This is a deliberate boundary, not an omission. Metadata-only
verification was performed; content scanning of the reserved window was not.

---

## 4. The forex gap — precise

```
$ git grep -In "ECB" -- "*.md" "*.txt" | grep -Ei "licen|attribut|provider"
  (no attribution records)
```

| Issue | Detail |
|---|---|
| Acquisition URL | `…/2024-01-01..2026-10-08?from=EUR&to=USD` — **no `providers=ecb`** |
| Frankfurter default | blends across providers |
| Raw payload | `amount, base, start_date, end_date, rates` — **no provider field** |
| `rate_type` column | asserts `ECB_reference_rate` — an **assertion**, not evidence |

**Status: ❌ source attribution not satisfied. ⚠️ permitted use conditional —
if blended, ECB's modification-disclosure condition is engaged and no disclosure
exists in any forex artefact.**

---

## 5. Licence status per dataset

| Dataset | Licence | Evidence state |
|---|---|---|
| BTC/ETH crypto | CC BY-NC-SA 4.0 + Vision Terms v1.0 | ✅ 8 sidecars + 4 reports + publisher text |
| Forex | ECB copyright policy | ✅ terms captured (SHA-256 `424859b8…`) |
| Forex | — | ❌ provenance unresolved |

**[V]** Copyright terms and provider provenance are **separate**. The captured
ECB terms resolve usage rights and **do not** establish lineage.

---

## 6. Gaps, duplicates, timestamps

| Aspect | Crypto | Forex |
|---|---|---|
| Timestamp convention | **[V]** Binance spot µs from 2025-01-01, ms before; normalised to `dd-mm-yyyy HH:MM` | **[V]** Daily date only |
| Duplicates | Rejected by loader | **[V]** Not applicable (one rate per day/pair) |
| Gaps | Rejected; contiguity asserted | **Weekend/holiday gaps expected — must NOT be filled** |
| Daily rates vs OHLC | n/a | **[V]** Manifest: *"THIS IS NOT AN OHLC DATASET"*; schema prevents OHLC loading |

**No synthetic OHLC exists or was created.**

---

## 7. Future data-ingestion acceptance checklist

Applicable to **both** crypto and forex.

### A. Source attribution
- [ ] Authoritative publisher URL recorded, not just a mirror
- [ ] **Provider pinned or explicitly recorded as unpinned**
- [ ] Any provider attribution returned by the API **preserved**, not discarded
- [ ] Licence terms captured in-repo with retrieval date + SHA-256
- [ ] If provider cannot be identified, the dataset is **not admissible**

### B. Acquisition metadata
- [ ] Full request URL incl. query, recorded verbatim
- [ ] Retrieval timestamp (UTC, ISO 8601)
- [ ] Endpoint/version identifier
- [ ] Tooling identifier (script name / git SHA)

### C. Integrity
- [ ] SHA-256 of every raw and normalised file
- [ ] Manifest row per file: URL, parameters, timestamp, both digests
- [ ] Raw responses retained **unmodified**
- [ ] Published `.CHECKSUM` verified where the publisher supplies one

### D. Structural quality
- [ ] Interval verified (3600 s for intraday; 1 day for daily)
- [ ] Timestamps strictly increasing, no duplicates
- [ ] Gap policy **explicit per market class** — intraday gaps rejected; daily FX gaps expected
- [ ] OHLC ordering and finiteness (OHLC only)
- [ ] Boundary contiguity against adjacent windows asserted

### E. Market-specific
- [ ] **Crypto:** continuous 24/7 — no weekend/holiday gap-filling
- [ ] **Forex:** trading sessions, weekly closure, holidays, **DST transitions** — none currently populated in the registry
- [ ] **Daily reference rates kept in a distinct schema** so they can never load as OHLC

### F. Governance
- [ ] Registered with schema-valid provenance
- [ ] `attribution_required` honoured in artefacts
- [ ] Approval status recorded (`RESERVED` / research-approved / blocked)
- [ ] Reserved windows carry a reservation entry before any evaluation

---

## 8. Findings

| # | Finding | Severity |
|---|---|---|
| 1 | Forex provider attribution unrecoverable | **High** — blocks any forex integration |
| 2 | No modification disclosure in forex artefacts if blended | **High** — conditional on #1 |
| 3 | No instrument has session / closure / DST data populated | **Medium** — see Phase 69 |
| 4 | Attribution requirements are recorded in sidecars but not machine-readable | **Low** |
| 5 | Crypto provenance is complete and verifiable | ✅ positive |

**No frozen dataset was altered. No replacement was downloaded.**