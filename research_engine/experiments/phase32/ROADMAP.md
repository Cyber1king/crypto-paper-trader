# Phase 32 — Prioritised Roadmap

**Status: PROPOSAL ONLY.** No phase below has been started. No acceptance
criterion here has been met, tested or evaluated.

Sequencing rule, as previously agreed: **UI redesign follows core research and
functionality work.** Dashboard work in this roadmap is limited to *additive
panels required for the research*, not a redesign.

---

## 0. The gating fact

**VERIFIED FACT.** No unused validation data remains anywhere in this project
(`RESEARCH_CHECKPOINT.md:417-428`), and the 2026-09…10 holdout has been consumed
(`phase30/SUMMARY.md:343`).

**Therefore Phase R1 is a hard blocker.** Every evaluation phase below it is
impossible until genuinely new data exists. No amount of instrumentation,
AI work or UI work substitutes for it.

---

## 1. Phase sequence and dependencies

```
R1  Acquire fresh, provenance-documented data ──────┐
                                                    │ (blocks all validation)
R2  Instrumentation: persist signal + indicators ───┤
                                                    ├──► R5 Individual-provider eval
R3  Reporting hygiene: dual-basis metrics ─────────┤
                                                    │
R4  AI provider abstraction (no live calls yet) ───┘
                                                    │
                                                    ├──► R6 Multi-AI eval
                                                    │
R7  Six-mode testing of any AI-adjacent change ────┤
                                                    │
                                                    ├──► R8 Additive dashboard panels
R9  Full regression + reliability ─────────────────┘
```

---

## R1 — Acquire genuinely unused, provenance-documented data

**Why first.** Blocks everything. Also closes the open provenance gap: the
2024–2025 dataset "has no documented provenance" and construction continuity with
2026 is unestablished (`phase10/SUMMARY.md:150-153`).

**Scope.** Extend coverage beyond BTC/USDT 1h. Add a second asset and/or
timeframe so any conclusion is not single-asset. Optionally begin the forex
asset class (§ `AI_ARCHITECTURE.md` §3).

**Dependencies.** None.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R1.1 | New data obtained from a source with published checksums and a documented licence |
| R1.2 | Per-archive SHA-256 verified against the publisher **before** parsing, as Phase 29C did |
| R1.3 | Manifest written recording path, SHA-256, row count, UTC range, source, licence, retrieval timestamp — mirroring the existing `…manifest.txt` |
| R1.4 | Zero overlap with the 2024–2025 research window and with the consumed 2026 windows |
| R1.5 | Row counts and timestamps strictly validated by the existing acquisition library, **unmodified** |
| R1.6 | Dataset frozen and **not yet examined for performance** |
| R1.7 | Partitions defined: development / validation / untouched test, each with its own SHA-256 |

**Explicitly out of scope.** No strategy evaluation on this data in R1.

---

## R2 — Instrumentation: persist per-trade signal and indicator context

**Why.** Phase 31 §4.5 established that entry quality is **not testable**,
because the per-trade signal label and all Phase 14C indicator fields were never
written to the results artifacts, even though they exist on `PaperTrade`.

**Scope.** Persist, for every trade in every run: the four-way signal label
(`bullish retest`, `bearish retest`, `uptrend breakout`, `downtrend breakdown`,
`flat`) plus `signal_close`, `trend_state`, `breakout_distance`,
`retest_distance`, `realised_volatility`, `mean_range`, `support_at_entry`,
`resistance_at_entry`.

**Dependencies.** None technically. Should follow R1 so instrumentation is proven
on new data.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R2.1 | All fields present on every recorded trade |
| R2.2 | **Behaviour-neutral:** all 1968 existing tests pass unchanged; recorded Phase 30 figures reproduce bit-for-bit |
| R2.3 | Fields are provably causal — a value at index *i* cannot depend on candles after *i* |
| R2.4 | A regression test asserts a look-ahead violation is caught |
| R2.5 | No new field is used by any strategy decision path |

**Risk if skipped.** Every subsequent entry-quality hypothesis stays untestable,
and the phase repeats Phase 31's dead end.

---

## R3 — Reporting hygiene

**Why.** Two documented misreading risks: `stats.performance()` computes
`profit_factor` from **net** P&L while naming its locals `gross_profit`/
`gross_loss` (`stats.py:102-111`); and `friction / gross P&L` is meaningless
when gross is negative (Phase 31 §5).

**Scope.** Report both profit-factor bases explicitly; label the drawdown basis;
distinguish undefined from zero everywhere.

**Dependencies.** None.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R3.1 | Both PF bases appear in every report, labelled |
| R3.2 | Drawdown always labelled closed-trade vs mark-to-market |
| R3.3 | Undefined metrics render as "undefined", never as `0` or a large finite number |
| R3.4 | No ratio whose denominator is negative is reported as a percentage |
| R3.5 | All existing tests pass; recorded figures unchanged in meaning |

**Constraint.** Reporting clarity only. **No metric may be redefined**, or
frozen artifacts and their digests would become invalid.

---

## R4 — AI provider abstraction (no live calls)

**Why.** Multi-provider work is impossible without a replaceable interface, and
the interface must exist and be tested **before** any provider is trusted.

**Scope.** Build the `ResearchProvider` protocol, the structured-output schema
(`AI_ARCHITECTURE.md` §5), the abstention path, caching, cost accounting,
timeouts and logging — against a **fake/stub provider only**.

**Dependencies.** R3 for logging conventions.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R4.1 | A stub provider can be added without touching engine code |
| R4.2 | Output schema rejects malformed, unparseable or schema-invalid responses |
| R4.3 | Provider failure, timeout and rate-limit paths all degrade to `abstain` |
| R4.4 | Credentials are server-side only; none appear in logs, prompts or the UI bundle |
| R4.5 | Per-call cost, latency, token counts and prompt hash recorded |
| R4.6 | All six modes still pass their full suites unchanged |
| R4.7 | **No live provider call is made in this phase** |

**Explicitly out of scope.** No provider integration, no API key, no spend.

---

## R5 — Individual-provider evaluation

**Why.** Establishes whether any single provider adds value over the baseline.

**Dependencies.** **R1** (fresh data), **R2** (instrumentation), **R3**, **R4**,
plus resolution of every **[VERIFY]** item in `AI_ARCHITECTURE.md` §10.

**Scope.** Configurations C0 (baseline) and C2 (one provider), per
`EVALUATION_PROTOCOL.md` §3, each as a separate run over identical inputs,
**preregistered first**.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R5.1 | A preregistration exists, frozen, before any run — modelled on `phase29/PREREGISTRATION.md` |
| R5.2 | Provider model id and prompt hash pinned and logged |
| R5.3 | Runs use only the R1 validation partition, opened once |
| R5.4 | All eleven existing leakage guards active and re-verified |
| R5.5 | New evidence-leakage controls L13–L20 active and independently tested |
| R5.6 | Gross and net results, both PF bases, drawdown basis, trade count, exposure, abstention rate, cost and latency all reported |
| R5.7 | Results reported against the preregistered decision rule, whatever it says |
| R5.8 | The untouched test partition is **not** opened |

**Explicit constraint.** No configuration may be selected on validation data. A
change prompted by these results requires R1.7's untouched test partition.

---

## R6 — Multi-AI evaluation

**Why.** Tests whether combination beats single providers, and whether
disagreement is informative.

**Dependencies.** R5 complete for each provider individually.

**Scope.** Configuration C3.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R6.1 | Preregistered before any run |
| R6.2 | Per-provider attribution preserved; combined result is not the only output |
| R6.3 | Provider disagreement quantified and reported, never silently reconciled |
| R6.4 | Abstention on disagreement follows a preregistered rule |
| R6.5 | Compared against each single provider, not only against baseline |
| R6.6 | Total API cost and latency reported |

---

## R7 — Six-mode testing of AI-adjacent changes

**Why.** The repository has six modes with distinct contracts and a large test
surface: `test_modes.py`, `test_mode_contracts.py`, `test_execution_policy.py`,
`test_daily_target.py`, `test_manual_paper.py`, `test_high_risk.py`.

**Dependencies.** R4 for any change touching the policy seam.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R7.1 | `standard`, `ai_intelligence`, `alerts`, `daily_target`, `manual`, `high_risk` all pass their full existing suites |
| R7.2 | `alerts` remains structurally incapable of trading — no broker reference (`modes.py:58-65`) |
| R7.3 | `ai_intelligence` still treats an absent score as a fail (`execution.py:388-392`) |
| R7.4 | `manual` still refuses automatic entry and exit (`manual_paper.py:398-412`) |
| R7.5 | Risk ceiling still rejects `risk_fraction > 1.0` (`simulator.py:82-83`); no analysis path can reach it |
| R7.6 | Unknown mode never silently falls back to `standard` (`modes.py:466-480`) |

---

## R8 — Additive dashboard panels

**Why.** The research is unusable if the evidence is invisible. The dashboard
already displays dataset SHA, config hash, costs and drawdown basis, and already
refuses unsourced confidence claims (`paper_api/README.md:110-117`).

**Sequencing.** After R7. **Additive panels only — no redesign**, per the agreed
sequencing.

**Scope.** Per provider and per claim: source, `published_at` **and**
`retrieved_at`, staleness, fact-vs-interpretation styling, uncertainty,
missing-evidence display, disagreement, abstention counts and reasons, and
per-run provider cost.

**Acceptance criteria**

| # | Criterion |
|---|---|---|
| R8.1 | Every analysis claim shows publisher and a reference to the stored raw item |
| R8.2 | `published_at` and `retrieved_at` displayed together |
| R8.3 | Interpretations never styled as measurements |
| R8.4 | Missing evidence explicitly displayed, never rendered as "no risk" |
| R8.5 | Provider model id and prompt hash visible |
| R8.6 | Abstention counts and reasons visible |
| R8.7 | `no-mock-data.test.ts` extended: forbid fabricated confidence, `Math.random` and `Date.now()` in AI panels |
| R8.8 | All existing dashboard tests pass unchanged |

---

## R9 — Full regression and reliability testing

**Why.** Every phase above touches shared infrastructure.

**Dependencies.** All preceding.

**Acceptance criteria**

| # | Criterion |
|---|---|
| R9.1 | Full Python suite passes (baseline 1968 tests) |
| R9.2 | Full dashboard Vitest suite passes |
| R9.3 | All recorded Phase 10, 13, 14C, 29C, 30B figures reproduce bit-for-bit |
| R9.4 | All 16 Phase 12-style integrity gates plus leakage guards L1–L20 verified |
| R9.5 | Failure-mode tests: provider timeout, 429, malformed output, stale evidence, empty evidence, conflicting evidence |
| R9.6 | No secret or credential appears anywhere in the repository or logs |
| R9.7 | Every frozen artifact digest unchanged unless a preregistered phase explicitly superseded it |
| R9.8 | A final preregistration exists for any confirmation run on the untouched test partition |

---

## 2. Cross-phase constraints

Apply to every phase above.

| # | Constraint |
|---|---|
| X1 | No strategy code, defaults or costs change without an explicit preregistered phase |
| X2 | No parameter tuned on validation data |
| X3 | The spent Phase 30B holdout is **never** reused as fresh validation |
| X4 | Every evaluation has a frozen preregistration **before** it runs |
| X5 | Every reported metric states its basis and distinguishes undefined from zero |
| X6 | Unfavourable and null results are reported in the same form as favourable ones |
| X7 | No AI model alters the strategy, overrides a risk limit, or executes a trade |
| X8 | Python remains the authoritative calculation, accounting, backtest and execution engine |
| X9 | Standing conclusion unchanged until evidence supports changing it |
| X10 | Nothing is committed or pushed without explicit instruction |

---

## 3. Critical path and principal risk

**Critical path: R1 → R2 → R4 → R5 → R6 → R9.** R1 is the blocker.

**The principal risk is stated plainly.** The project has tested 12+ configurations
across 23,376 hourly candles and **has no evidence of a profitable trading rule**
(`RESEARCH_STATE.json:14`). Phase 30B's gross P&L was −6.32 before costs, and
Phase 13's baseline lost money in all six walk-forward windows.

Building an AI research layer is a reasonable long-term investment. But nothing
in this roadmap establishes that it will produce a profitable strategy, and the
first-order question is not which model to use — it is whether there is
sufficiently new data to tell whether *anything* works. **R1 must succeed before
any AI work can be evaluated at all.**

---

## 4. What is deliberately not on this roadmap

| Item | Reason |
|---|---|
| UI redesign | Agreed to follow core research and functionality work |
| Live or leveraged trading | Out of scope; `alerts`-style structural prevention remains |
| Strategy rewrite | Phase 15 deliberately declines to propose one (`RESEARCH_CHECKPOINT.md:33-35`) |
| Parameter tuning on any consumed dataset | Classified as exploratory data mining (`RESEARCH_CHECKPOINT.md:517-520`) |
| Choosing acceptance thresholds now | Must be preregistered when data exists, not invented now |
| Provider selection | **[VERIFY]** items unresolved; no provider named as preferred |

**No profitability claim is made in this roadmap.** The standing conclusion
stands unchanged.