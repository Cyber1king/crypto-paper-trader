# Phase 36 — Implementation Roadmap

**Status: PLAN ONLY. No phase below has been started, met or tested.**

**Sequencing rule, as previously agreed: UI work follows core research and
functionality work.** Dashboard items here are additive panels required by the
research, never a redesign.

---

## 0. The gating facts

Three constraints dominate everything below.

| # | Fact | Consequence |
|---|---|---|
| G1 | **No untouched BTC validation data exists.** The Phase 30B holdout is spent; unseen BTC begins 2026-10-09 | No BTC evaluation can proceed |
| G2 | **No instrument registry exists.** No instrument universe concept is present in source | Every pipeline needs one first |
| G3 | **No market-session, holiday or DST logic exists.** Zero `dst` occurrences repo-wide | Any forex OHLC work needs it built from scratch |

---

## Phase dependency graph

```
P1 Close data-approval gaps ──┐
                               ├──► P3 Registry + data contracts ──► P4 Acquire per instrument
P2 Session/DST library ────────┘                                          │
                                                                          ▼
                                                        P5 Preregistration procedures
                                                                          │
                                                                          ▼
                                          P6 Single-instrument evaluation
                                                                          │
                                                                          ▼
                                          P7 Provider abstraction (stub only)
                                                                          │
                                                          ┌───────────────┴───────────────┐
                                                          ▼                               ▼
                                                P8 Individual providers         P9 Multi-provider
                                                          └───────────────┬───────────────┘
                                                                          ▼
                                                              P10 Six-mode testing
                                                                          │
                                                                          ▼
                                                              P11 Additive UI panels
                                                                          │
                                                                          ▼
                                                              P12 Full regression
```

**Critical path: P1 → P3 → P4 → P5 → P6.**

---

## P1 — Close remaining data-approval requirements

**Why first.** ETH sits at PROVENANCE VERIFIED but is not RESEARCH APPROVED, and
BLOCKS prevent evaluation regardless of what follows.

| # | Item |
|---|---|
| P1.1 | Decide and record whether a BTC→ETH instrument change is within strategy scope. Phase 32 records cross-asset behaviour as **NOT ESTABLISHED** |
| P1.2 | Record the Phase 34/35 provenance item as resolved, with the corrected sidecar digests referenced |
| P1.3 | Record the Phase 34 cosmetic naming observation for the forex file |
| P1.4 | Record explicitly that ETH's date overlap is **not** an independent BTC sample |
| P1.5 | Decide whether the ECB daily-rate dataset is worth keeping as a non-executable reference, or should remain research-only |
| P1.6 | Record that **no untouched BTC data exists** and when it becomes available |

**Dependencies:** none.
**Acceptance:** each item has a written decision with a rationale. No item may be
deferred silently.

**Out of scope:** approving any dataset; evaluating anything.

---

## P2 — Market session, holiday and DST library

**Why.** Forex OHLC cannot be validated without it, and it does not exist today.

| # | Item |
|---|---|
| P2.1 | Session model per venue: opens, closes, breaks |
| P2.2 | Weekly closure rules per pair |
| P2.3 | Holiday calendar with provenance and a documented update path |
| P2.4 | DST transition handling; session boundaries shift |
| P2.5 | **Gap classifier:** `legitimate_closure` vs `anomaly`, with reason |
| P2.6 | Bar-boundary convention recorded per instrument |

**Dependencies:** P3 (needs the registry to key sessions per instrument).
**Acceptance:** given a real FX series, the classifier correctly labels every
absence; no absence is silently filled. **Anomalies raise; closures do not.**

**Risk:** a wrong session model produces silently wrong features. It must be
preregistered and independently reviewed before use.

---

## P3 — Instrument registry and market data contracts

**Why.** G2. Every pipeline and every governance stage depends on it.

| # | Item |
|---|---|
| P3.1 | Registry with every field in `INSTRUMENT_REGISTRY_SPEC.md` §2 |
| P3.2 | Seed records for the five known instruments |
| P3.3 | Discovery producing `DISCOVERED` only |
| P3.4 | Eligibility screening; criteria preregistered **before** discovery runs |
| P3.5 | Rename → alias, never a new record |
| P3.6 | Delist → `RETIRED`, never deletion |
| P3.7 | Refresh recording "checked, nothing new" as distinct from "not checked" |
| P3.8 | `consumed_windows` authoritative anti-reuse record |

**Dependencies:** P1 (decisions inform seed records).
**Acceptance:** A1–A10 in the registry spec. Renaming and delisting proven by test.

**Risk:** eligibility criteria chosen *after* seeing which assets pass is data
mining. Criteria must be frozen first.

---

## P4 — Acquire fresh, sourced data per approved instrument

**Why.** No evaluation is possible without untouched data.

| # | Item |
|---|---|
| P4.1 | Per-instrument source decision with **publisher checksums where they exist** |
| P4.2 | Acquire to the data contract; grade provenance A or B honestly |
| P4.3 | Reserve an untouched evaluation partition **at acquisition time** |
| P4.4 | Manifest every dataset: digest, rows, range, source, licence, retrieval timestamp |
| P4.5 | For FX: only after P2. Record volume semantics; never synthesise bid/ask |

**Dependencies:** P1, P2, P3.
**Acceptance:** every dataset passes C1–C14 by **independent recomputation**; an
untouched partition exists and is registered.

**Open dependency:** BTC data before 2026-10-09 does not exist. Wait or proceed
with other instruments.

---

## P5 — Leakage-safe, preregistered evaluation procedures

**Why.** Proven repeatedly: unpreregistered evaluation produces numbers that
cannot be trusted.

| # | Item |
|---|---|
| P5.1 | Reuse the eleven existing leakage guards — do not reinvent |
| P5.2 | Add evidence-leakage control `published_at ≤ decision_time` |
| P5.3 | Preregistration template based on `phase29/PREREGISTRATION.md` |
| P5.4 | Freeze thresholds **before** results, never after |
| P5.5 | Declare the number of comparisons in advance |
| P5.6 | Define every metric basis explicitly — Phase 31 showed PF is **net**, and friction/gross is meaningless when gross is negative |

**Dependencies:** P4.
**Acceptance:** a preregistration exists, frozen, naming the exact dataset digest.

**Precedent:** Phase 29D declared INCONCLUSIVE *before* any number existed.

---

## P6 — Evaluate instruments separately

**Why.** Cross-market strategy multiplies the search space; A2 was already
contaminated by a 12+ variant search.

| # | Item |
|---|---|
| P6.1 | Single-instrument evaluation only |
| P6.2 | Run once; report whatever the preregistered rule says |
| P6.3 | Report null and negative results in the same form as positive ones |
| P6.4 | Cross-market strategies **only after** single-instrument work completes |

**Dependencies:** P5.
**Acceptance:** no cross-market evaluation attempted before this completes.

**Standing constraint:** the goal is **reliable evidence, not guaranteed returns**.

---

## P7 — Provider abstraction, stub only

**Why.** The interface must exist and be tested before any provider is trusted —
and before any credential or spend exists.

| # | Item |
|---|---|
| P7.1 | `ResearchProvider` protocol and structured-output schema |
| P7.2 | Abstention path, caching, cost accounting, timeouts, logging |
| P7.3 | Built against a **stub provider only** |
| P7.4 | Static guard: credentials absent from logs, prompts, UI bundle |
| P7.5 | All six modes still pass their suites |

**Dependencies:** P3 (registry keys instruments for analysis).
**Acceptance:** B1–B3, B6, B10 in the AI spec. **No live provider call in this
phase.**

---

## P8 — Individual provider evaluation

**Dependencies:** P7, plus resolution of every **[VERIFY]** item: model IDs,
pricing, limits, retention terms, structured-output support, pinning.
**Acceptance:** each provider's marginal contribution measured against C0 with
cost, latency and abstention rate reported.
**Out of scope:** selecting a "best" provider on the holdout.

---

## P9 — Multi-provider evaluation

**Dependencies:** P8 complete for each provider independently.
**Acceptance:** per-provider attribution preserved; disagreement quantified, never
silently reconciled; total cost and latency reported.

---

## P10 — Six-mode testing of AI-adjacent changes

**Dependencies:** P7 for anything touching the policy seam.
**Acceptance:** `standard`, `ai_intelligence`, `alerts`, `daily_target`, `manual`,
`high_risk` all pass their existing suites. `alerts` remains structurally
incapable of trading. `ai_intelligence` still treats an absent score as a fail.
Risk ceiling still rejects `risk_fraction > 1.0` and no analysis path reaches it.

---

## P11 — Additive dashboard panels

**Dependencies:** P10. **No redesign.**
**Acceptance:** sources, both timestamps, staleness, fact-vs-interpretation
styling, uncertainty, missing evidence, disagreement, abstention counts, cost,
`model_id` and prompt hash all visible; static test extended to forbid fabricated
confidence.

---

## P12 — Full regression and reliability testing

**Dependencies:** all preceding.
**Acceptance:** full Python suite (baseline 1,968 tests) and full dashboard suite
pass; all recorded Phase 10/13/14C/29C/30B figures reproduce; leakage guards
verified; failure-mode tests pass; no secret in repo or logs.

---

## Summary table

| Phase | Depends on | Blocks | Risk if rushed |
|---|---|---|---|
| P1 Close approval gaps | — | P3, P4 | Approving data without untouched validation |
| P2 Session/DST library | P3 | P4 (FX) | Silently wrong features from a wrong calendar |
| P3 Registry + contracts | P1 | P4–P7 | No authoritative instrument universe |
| P4 Acquire per instrument | P1, P2, P3 | P5, P6 | Evaluating on absent or consumed data |
| P5 Preregistration | P4 | P6 | Untrustworthy numbers |
| P6 Single-instrument eval | P5 | P8, P9 | Cross-market search explosion |
| P7 Provider abstraction | P3 | P8, P9 | Untested interface, live spend |
| P8 Individual providers | P7 | P9 | Unbounded cost, no attribution |
| P9 Multi-provider | P8 | — | Silent reconciliation of disagreement |
| P10 Six-mode testing | P7 | P11 | Broken mode contracts |
| P11 UI panels | P10 | — | Premature redesign |
| P12 Full regression | all | — | Silent regressions |

---

## Explicitly out of scope for the whole roadmap

| Item | Reason |
|---|---|
| UI redesign | Agreed to follow core research |
| Live or leveraged trading | Out of scope; structural prevention remains |
| Strategy rewrite | Phase 15 deliberately proposes none |
| Parameter tuning on consumed data | Classified as exploratory data mining |
| Inventing acceptance thresholds | Must be preregistered when data exists |
| Naming a preferred provider | **[VERIFY]** items unresolved |
| Any profitability claim | None exists; none is promised |