# Phase 69 — Multi-Market Research Architecture Audit

**Prerequisites:** registry schema, `costs.py`, `dataset.py`, `intervals.py`,
`researchguard.py`.
**Safety check at start:** no new blocker.
**No performance experiment run. No stable interface redesigned. No code changed.**

---

## 1. Verified architecture facts

| Fact | Evidence |
|---|---|
| `MARKET_TYPES_SUPPORTED = frozenset({"crypto_spot"})` | `registry_schema.py` L61 |
| A separate `MARKET_TYPES_BLOCKED` set exists | `registry_schema.py` L40, L51 |
| Registry holds 2 × `crypto_spot` + 3 × `forex_reference_rates` | `research_registry.json` |
| Single `TradingCosts` dataclass, `spread_rate = 0.0` | `costs.py`, `walkforward.phase13_costs()` |
| `dataset_fingerprint` returns `(len, first, last)` — **not** a content hash | `walkforward.py`, self-described as *"Cheap fingerprint used to detect dataset mutation mid-run"* |
| `candle_fingerprint` **is** content-based (`hashlib`) | `researchguard.py` |
| Weekend/holiday gaps already contemplated | `intervals.py` L5 |
| `tzinfo` 8 hits / 5 files; `timezone.utc` 4/4; DST 10 hits / 5 files | code survey |

---

## 2. Concrete defects

### D1 — No session, closure or DST data is populated for **any** instrument

```
BTC/USDT  crypto_spot               sessions=[]  closure=None  dst=False
ETH/USDT  crypto_spot               sessions=[]  closure=None  dst=False
EUR/USD   forex_reference_rates     sessions=[]  closure=None  dst=False
GBP/USD   forex_reference_rates     sessions=[]  closure=None  dst=False
USD/JPY   forex_reference_rates     sessions=[]  closure=None  dst=False
```

**[V] The schema has the fields; no instrument populates them.** For
`crypto_spot` this is **correct** — 24/7 continuous markets have no sessions,
closure or DST. For `forex_reference_rates` it means the model is **incomplete**,
though the market type is already blocked.

**Severity:** Medium. Blocks nothing today; must be populated before any forex
work.

### D2 — Costs are global, not market-specific

**A single `TradingCosts` with `spread_rate = 0.0` is applied to both crypto and
forex.** For crypto this is a **registered assumption** with a documented bias
(§4 of the preregistration draft). For FX it would be simply **wrong** — FX has
real, material bid–ask spreads.

There is **no per-market cost profile** and no venue/market-type keying on
`TradingCosts`.

**Severity:** Medium. No effect while forex is blocked; would silently
mis-cost any future FX evaluation.

### D3 — `dataset_fingerprint` is not collision-resistant

`dataset_fingerprint` returns `(count, first, last)`. Two **different** datasets
with identical bar count and identical bounds produce the **same** fingerprint.

**[V] Mitigation exists and is used where it matters:** reservation identity uses
`candle_fingerprint`, which **is** content-based (`hashlib`). The cheap
fingerprint is used for mid-run mutation detection, where its scope is
appropriate.

**Severity:** Low for reservations; Medium if `dataset_fingerprint` were ever
promoted to a protocol-level identity value — which is exactly what **B10 #7**
proposes.

> **Note for B10 #7:** if the preregistration records
> `dataset_fingerprint` as the dataset's identity, it should record
> `candle_fingerprint` or the full SHA-256 instead. A `(count, first, last)`
> triple cannot detect a value-level substitution that preserves shape.

### D4 — No FX session/DST calendar implementation

DST utilities exist (10 hits / 5 files) but **no instrument is bound to one**, and
no calendar is populated. There is no function that maps a timestamp to an FX
trading session or resolves a DST transition boundary.

**Severity:** Medium. Blocks forex; irrelevant to crypto.

---

## 3. Missing tests identified

| Area | Gap |
|---|---|
| FX session boundaries | No test — feature not implemented |
| DST transition boundaries | No test — feature not implemented |
| Cross-instrument cost selection | No test — feature not implemented |
| `dataset_fingerprint` collision | **Testable today** and would document the limitation |
| Timezone normalisation on ingest | `tzinfo` present; no test found for a non-UTC source timezone |

**No test was added in this phase.** Adding a fingerprint-collision test would
document a known limitation rather than fix anything, and the FX tests would test
nothing because the features do not exist.

---

## 4. What is genuinely in good shape

| Area | Assessment |
|---|---|
| Market-type gating | ✅ `crypto_spot` allow-list — fail-closed, not permissive |
| Provenance schema | ✅ 20+ fields per instrument, schema-validated |
| Reservation identity | ✅ content-based fingerprint |
| Gap semantics | ✅ `intervals.py` already distinguishes legitimate closures from defects |
| Naive-datetime rejection | ✅ `_refuse_naive` (`ai_research.py` L329) |
| Timestamp normalisation | ✅ normalised to `dd-mm-yyyy HH:MM`; ingest records source epoch units |

**[V] The extensibility seam exists.** Market type, venue, sessions, closure,
DST and volume semantics are all represented in the schema. Forex is **blocked
by policy**, not by architecture.

---

## 5. Prioritised implementation plan

| # | Item | Rationale | Risk if deferred |
|---|---|---|---|
| **P1** | Record the fingerprint-collision limitation in the B10 #7 proposal | Prevents a weak identity being frozen into the protocol | **Protocol-level** — a wrong identity value is hard to change later |
| **P2** | Populate `trading_sessions` / `weekly_closure` / `dst_observed` for any future FX instrument | Schema-complete, currently empty | Any FX work blocked |
| **P3** | Introduce a per-market cost profile keyed by `market_type` | Prevents `spread_rate = 0.0` silently mis-costing FX | Silent cost error in FX |
| **P4** | Implement and test an FX session/DST calendar | Required for FX | FX blocked |
| **P5** | Add an ingest test with a non-UTC source timezone | Cheap regression protection | Low |

**P1 is recommended immediately** — it is documentation, requires no code change,
and prevents a specific protocol error.

**None of P1–P5 was implemented.** P2–P4 are features requiring owner scope
decisions; P5 is a test addition outside a documentation phase.

---

## 6. What was NOT changed

No source file modified. No interface redesigned. No performance run. No dataset
read beyond metadata. No frozen artefact touched.

**Defensible statement:** the multi-market architecture is **structurally
extensible and currently policy-blocked for everything except `crypto_spot`**.
The gap is populated data and unimplemented FX features, not a missing seam.