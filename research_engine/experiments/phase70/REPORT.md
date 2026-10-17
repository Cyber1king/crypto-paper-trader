# Phase 70 — AI Intelligence-Layer Readiness

**Prerequisites:** `ai_research.py`, `researchguard.py`, provider interfaces.
**Safety check at start:** no new blocker.
**No provider called. No API key read or printed. No cost incurred.**

---

## 1. Verified implementation status

| Check | Method | Result |
|---|---|---|
| Concrete provider classes (Claude / Kimi / DeepSeek / OpenAI / Anthropic) | `class \w*(Claude\|Kimi\|DeepSeek\|OpenAI\|Anthropic)\(` across `src/` and `tests/` | **NONE** |
| Provider-name mentions in `ai_research.py` | case-insensitive search | **claude: 0 · kimi: 0 · deepseek: 0** |
| Outbound network calls in the package | `urllib.request` / `requests` / `httpx` / `aiohttp` / `openai.` / `anthropic.` | **NONE** |
| `ai_research.py` size | line count | ~600 lines |
| AI test file | filesystem | `tests/test_ai_research.py` — 20,928 bytes |

> **No AI provider is integrated. The layer is an architecture, not a connection.**

---

## 2. What actually exists

**Verified by direct inspection of `ai_research.py`:**

| Component | Line | Purpose |
|---|---|---|
| `ProviderConfigurationError` | L60 | Missing-configuration refusal |
| `ProviderNotConfigured` | L68 | Explicit not-configured state |
| `AbstentionReason(str, Enum)` | L76 | **Structured abstention** — the layer can decline to answer |
| `AnalysisState(str, Enum)` | L94 | State machine |
| `assert_no_probability_claims(text)` | L124 | **Blocks probability/return claims in AI output** |
| `ResearchAnalysis` (frozen dataclass) | L143 | Immutable result type |
| `_refuse_naive(value: datetime)` | L329 | Rejects naive datetimes |
| `ProviderRequest` (frozen) | L340 | Immutable outbound request |
| `ProviderResponse` (frozen) | L405 | Immutable inbound response |
| `AIResearchProvider(Protocol)` | L447 | **A Protocol — structural type, no implementation** |
| `timeout_seconds: float = 30.0` | L474 | Timeout contract, with the note that *implementations must enforce it themselves* |
| `redact_secrets(text, secrets)` | L486 | Secret redaction |
| `AnalysisPipeline` | L503 | Orchestration |
| `default_pipeline()` | L593 | Composition root |

**Assessment:** the governance scaffolding is **substantive and well-designed**.
`assert_no_probability_claims` and `redact_secrets` are exactly the controls an
AI layer needs, and `AbstentionReason` means refusal is a first-class outcome.

---

## 3. Requirement-by-requirement

| Requirement | Status |
|---|---|
| Provider interfaces | ✅ `AIResearchProvider(Protocol)` |
| **Capability discovery** | ⚠️ Not verified — no capability-negotiation surface observed |
| Configuration and model selection | ❌ No concrete provider; no model registry observed |
| **Timeouts** | ⚠️ Declared as a **contract** (`timeout_seconds = 30.0`); **no implementation enforces it** |
| Failure handling | ✅ `ProviderNotConfigured`, `ProviderConfigurationError` |
| Structured output validation | ✅ `ResearchAnalysis` frozen dataclass |
| Source attribution / evidence provenance | ✅ `EvidenceSourceModel` in `paper_api`; guards in `researchguard` |
| Reproducibility and audit logs | ✅ Every `research_evaluation` call is logged (Phase 46 tests) |
| **Prompt-injection boundaries** | ⚠️ **Not verified** — no sanitisation surface observed |
| Secret handling | ✅ `redact_secrets` exists; **no secrets exist in the codebase** |
| Cost / rate-limit controls | ❌ Not present |
| Separation of AI from trading | ✅ **No provider exists**, therefore no AI→execution path |

---

## 4. Findings

| # | Finding | Severity |
|---|---|---|
| **A1** | **No provider is integrated.** Architecture only. | **Informational** — this is the documented state, not a defect |
| **A2** | `timeout_seconds` is a **contract, not an enforcement**. A future implementer could ignore it. | **High** when a provider is added |
| **A3** | **No prompt-injection defence observed.** If market data or news ever enters a prompt, untrusted content reaches the model. | **High** when a provider is added |
| **A4** | No cost ceiling or rate-limit budget | **Medium** — required before any live call |
| **A5** | No capability-negotiation surface | **Low** |
| **A6** | `AIResearchProvider` is a `Protocol`, so **static typing cannot prove an implementation conforms** | **Low** — mitigated by tests at the seam |

**No defect was found in what exists.** The gaps are all in what does not yet
exist — which is the correct state for an un-integrated layer.

---

## 5. Documentation-vs-implementation reconciliation

| Claim in documentation | Verified |
|---|---|
| "Provider-independent AI interfaces" (Phase 48) | ✅ **True** — `Protocol`, zero provider bindings |
| "No providers integrated" | ✅ **True** — zero classes, zero network calls |
| "Replaceable provider architecture" | ✅ **True** — one Protocol seam |

**[V] No documentation overstatement was found.** The Phase 48 claim is precise:
*provider-independent interfaces*, not *integrated providers*.

---

## 6. Staged integration plan — NOT executed

### Stage 0 — prerequisites (no provider)

| # | Item |
|---|---|
| 0.1 | Add a **fake/deterministic provider** implementing `AIResearchProvider` for offline tests |
| 0.2 | Enforce `timeout_seconds` in a shared adapter so no implementer can forget |
| 0.3 | Add **prompt-injection boundaries**: untrusted content (market data, news, retrieved docs) marked as data, never as instructions |
| 0.4 | Add a **cost ceiling** and a per-run request budget |
| 0.5 | Add capability negotiation to the Protocol |

**Stage 0 requires no API key and no network.** It is the whole of what can be
built and tested safely.

### Stage 1 — first provider

| # | Item |
|---|---|
| 1.1 | Owner selects provider **and approves the cost ceiling** |
| 1.2 | Implement the adapter against `AIResearchProvider` |
| 1.3 | Reuse `redact_secrets`, `assert_no_probability_claims`, `AbstentionReason` |
| 1.4 | Tests with a **mocked transport** — no live call in CI |

### Stage 2 — evidence binding

| # | Item |
|---|---|
| 2.1 | Every `ResearchAnalysis` must carry `EvidenceSourceModel` references |
| 2.2 | No analysis may influence orders — **structurally enforced** |
| 2.3 | Deterministic offline mode remains the default in CI |

### Invariants that must never change

1. **AI output never bypasses `researchguard`.** A model cannot authorise a
   reserved evaluation or alter a reservation.
2. **AI output never reaches an execution path.** No such path exists.
3. **AI output is never a performance claim.** `assert_no_probability_claims`
   enforces this; it must run on **every** provider response.
4. **No secret is logged.** `redact_secrets` must be applied before any
   persistence.

---

## 7. What was NOT done

- **No provider was called.** No network request, no API cost.
- **No API key was read, printed, or stored.**
- **No code was modified.**
- **No integration was claimed.** The layer is an architecture with strong
  governance primitives and zero providers.

---

## 8. Honest status

> **The AI layer is a well-built, provider-independent, provider-free
> architecture.** It is not an integration. Any claim that Claude, Kimi or
> DeepSeek is "integrated" would be false — there are zero provider classes and
> zero network calls in the package.

The most valuable next step costs nothing: **Stage 0**, particularly a
deterministic fake provider and enforced timeouts, which make any future
integration testable without a key.