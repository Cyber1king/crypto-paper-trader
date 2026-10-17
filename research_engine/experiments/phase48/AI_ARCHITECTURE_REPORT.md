# Phase 48 AI Architecture Report

**Date:** 2026-10-09

**Live provider integration: NOT IMPLEMENTED.** No provider client exists in this
repository, no credential exists, and none is required to use the interface.

---

## 1. What the existing `ai_intelligence` mode actually is

Audited before designing anything, per the Phase 48 requirement.

`crypto_paper_lab/intelligence.py` (Phase 17G) imports only `dataclasses`,
`hashlib`, `math`, `typing`. No HTTP client, no provider SDK, no model call.

Its own docstring states what it is:

> Deterministic paper-trading intelligence score (Phase 17G). A **qualification
> gate**. It is a deterministic, causal, explainable heuristic.

**It is arithmetic, not AI.** Nothing was renamed, repackaged, or connected to
any model. Its trading behaviour is unchanged: same inputs, same 0–100 score,
same threshold. Phase 48 introduced no coupling between it and the new layer.

The name contains "ai", which is misleading in isolation. Correcting it would
mean changing a mode identifier used across the API, tests and configuration —
a breaking change this phase should not make unilaterally. Recorded here
instead.

---

## 2. Provider-independent architecture

`crypto_paper_lab/ai_research.py` defines the contract. It contains **no**
provider client, HTTP call, or credential handling.

### Separation of responsibilities

`AnalysisPipeline` declares eight stages and validates their ordering:

| # | Stage | AI-independent |
|---|---|---|
| 1 | Data ingestion | yes |
| 2 | Deterministic validation | yes |
| 3 | News and event retrieval | yes |
| 4 | Evidence aggregation | yes |
| 5 | **AI-assisted analysis** | — |
| 6 | Deterministic policy and risk checks | yes |
| 7 | Research reporting | no |
| 8 | Dashboard presentation | no |

`ordering_is_sound()` is a **checked property, not a comment**. It verifies that
stages 1–4 precede stage 5, that stage 6 follows it, and that no forbidden stage
*is* stage 5. A reordered pipeline returns `False` —
`test_reordered_pipeline_is_detected` constructs a broken one to prove the check
has teeth.

Stages 6 and 7 are *after* AI and must equally never consume AI output. That is
why AI is a ring around the pipeline rather than a bridge across it.

### What the AI layer structurally cannot do

| Capability | Why it is absent |
|---|---|
| Approve its own data | No reference to the registry; `test_ai_research_does_not_import_researchguard` scans the AST |
| Consume a research window | No `ResearchContext`, no `consume_reservation` |
| Bypass a research guard | `researchguard` is not importable from this module |
| Execute a trade | `ai_research` is not imported by `backtest`, `replay`, `walkforward`, `simulator`, `strategy`, or `researchguard` — asserted by test |
| Modify frozen research | No write path to any data file |

`AnalysisPipeline` is a **description of responsibilities, not an executor.** It
exists so the ordering constraint is explicit and testable rather than implied by
directory layout.

---

## 3. Structured output

`ResearchAnalysis` requires: instrument, timeframe, market type, analysis
timestamp, provider name, and evidence/event references.

Optional: price context, news summary, economic event summary, conflicting
evidence, freshness note, limitations, observations, abstention state.

### Rules enforced at construction

- **A complete analysis requires at least one evidence or event reference.**
  Analysis with no inputs is claiming insight from nothing — precisely the
  failure this layer exists to prevent.
- **An abstention requires both a reason and a specific detail.** "The model
  wasn't sure" is not auditable.
- **A reason may only be set on an abstained analysis**, and vice versa.
- **Blank identity fields are refused.**
- **`analysed_at` must be timezone-aware.**
- **`model_name` is optional.** A provider need not disclose which model served a
  request, and recording "unknown" is more honest than guessing.

### Abstention as a first-class outcome

Ten `AbstentionReason` values, covering the required cases:
`insufficient_evidence`, `stale_evidence`, `conflicting_evidence`,
`unsupported_instrument`, `unsupported_market`, `unsupported_timeframe`,
`out_of_scope`, `provider_unavailable`, `schema_invalid`.

A `provider_unavailable` reason exists so an outage is recorded as a distinct
state rather than being silently indistinguishable from a considered abstention.

### No calibrated claims

`ResearchAnalysis` has **no** `probability`, `expected_return`, `win_rate`, or
`confidence` field. Their absence is the design.

```python
FORBIDDEN_FORECAST_TERMS = (
    "probability", "probabilities", "win_rate", "win rate",
    "expected_return", "expected return", "certainty", "guaranteed",
    "will outperform", "risk-adjusted edge", "sharpe of",
    "confidence interval", "p_value", "p-value",
)
```

`assert_no_probability_claims` runs on every summary, observation and abstention
detail. A record asserting "80% probability" is **refused**, not reinterpreted.

This is a lexical filter and does not pretend to be complete — it catches the
phrasings most likely to be misread as a calibrated number by a downstream reader,
not every possible phrasing.

---

## 4. Prompt construction

`ProviderRequest.to_prompt()` states the limits explicitly, because a provider
that has not been told them will exceed them:

- Do NOT state probabilities, win rates, or expected returns.
- Do NOT recommend entering, exiting, sizing or holding a position.
- Do NOT claim access to data you were not given.
- If evidence is insufficient, stale, contradictory or the market is out of
  scope, **abstain and say why**.
- Distinguish what the evidence states from what you infer.

`ProviderRequest` carries **identifiers and evidence references only** — never
candles, never prices. The provider is asked to reason about context, not handed
engine internals. Asserted by `test_request_carries_no_market_data`.

---

## 5. Safe integration readiness

Implemented, because none of it requires a credential:

| Capability | Status |
|---|---|
| `AIResearchProvider` protocol | implemented, runtime-checkable |
| Timeout as a required adapter argument | implemented |
| Bounded retries (`max_retries`, a bound not a default) | implemented |
| Schema validation of provider output | implemented (`ResearchAnalysis.from_record`) |
| Clear error states | implemented (`ProviderConfigurationError`, `ProviderNotConfigured`) |
| Redacted logging | implemented (`redact_secrets`, marker does not leak length) |
| Provider-independent tests | 73 tests, all mocked |
| Truncation detection | implemented (`finish_reason == "length"`) |

**Not implemented:** any actual provider client. See `PROVIDER_STATUS.md`.

---

## 6. Truncation is a correctness concern

`ProviderResponse.looks_truncated` is `True` when `finish_reason == "length"`. A
truncated response is not a shorter opinion; it is a **partial** one. Treating it
as complete would misrepresent what was received, so the flag is explicit rather
than left for the caller to infer from token counts.

---

## 7. Rejection of self-deception in tests

Two tests were written to match their own search literals and failed:

1. A secret-pattern scan matched its own pattern list.
2. An assertion that `researchguard` was absent matched a prose mention in the
   module docstring.

Both were fixed by scanning **structurally via the AST** rather than by
substring. Substring scans produce false positives against one's own test code
and, worse, false confidence against real code that merely *discusses* a name.

`test_no_credential_lookup_in_module` now checks the module contains no
environment lookup at all, so credentials could not be introduced later without
that test failing.

---

## 8. Limitations

- `assert_no_probability_claims` is lexical. It will not catch "there is a strong
  chance" or "I would expect". A semantic check would need a model, which is
  circular.
- Clustering and conflict detection in Phase 47 are structural, not
  claim-detection. `conflicting_evidence` flags items whose credibility note
  contains "conflict"; it does not infer that two reports disagree.
- No prompt-injection defence beyond stating scope. A provider reading
  attacker-controlled headline text could follow instructions embedded in it.
  Mitigating that requires output validation this phase does not perform.
- No cost model. Token counts are recorded in `ProviderResponse` but nothing
  prices them, and no provider's pricing was verified.

---

## 9. Verdict

**PASS, with live integration explicitly NOT IMPLEMENTED.**

The interface, the safety boundaries and the abstention model are implemented and
tested. No provider is connected, none is claimed to be, and no credential is
required or requested. `ai_intelligence` remains a deterministic arithmetic gate,
described accurately and unchanged.

A mocked suite is not evidence that any provider works, and this report does not
present it as such.