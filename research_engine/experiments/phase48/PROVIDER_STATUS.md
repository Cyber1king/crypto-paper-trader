# Phase 48 Provider Status

**Date:** 2026-10-09

> **Live provider integration: NOT IMPLEMENTED.**
> No provider client exists in this repository. No credential exists. No
> provider was contacted. Nothing below should be read as "integrated".

---

## 1. Status table

| Provider | Client implemented | Credentials present | Tested | Documentation verified |
|---|---|---|---|---|
| **Anthropic (Claude)** | **NO** | none | mocked only | **YES** |
| **Kimi** | **NO** | none | mocked only | **NO — UNVERIFIED** |
| **DeepSeek** | **NO** | none | mocked only | **NO — UNVERIFIED** |
| Any other | **NO** | none | mocked only | **NO** |

Implemented in this phase: the **provider-independent interface only**
(`AIResearchProvider`, `ProviderRequest`, `ProviderResponse`,
`ResearchAnalysis`).

---

## 2. Anthropic (Claude) — documentation verified, integration absent

### What was verified

Source: `platform.claude.com/docs/en/api/overview`,
`docs.anthropic.com/en/api/messages`,
`platform.claude.com/docs/en/manage-claude/authentication`.

| Aspect | Verified finding |
|---|---|
| Base URL | `https://api.anthropic.com` |
| Primary endpoint | `POST /v1/messages` |
| Required headers | `anthropic-version` (e.g. `2023-06-01`), `content-type: application/json` |
| Auth (primary) | `Authorization: Bearer <key>`, or legacy `x-api-key` header |
| Auth (WIF) | Short-lived token from `POST /v1/oauth/token` via Workload Identity Federation |
| Credential env var | `ANTHROPIC_API_KEY` (picked up automatically by the SDKs) |
| Workspace scoping | `anthropic-workspace-id` header; required for multi-workspace keys, omitted for single-workspace keys |
| Batch API | `POST /v1/messages/batches` — 50% cost reduction |
| Token counting | `POST /v1/messages/count_tokens` |
| Model listing | `GET /v1/models` |

### A discrepancy I am not going to paper over

The two official pages consulted **disagree on model identifiers**:

- `docs.anthropic.com/en/api/messages` lists `claude-sonnet-5`,
  `claude-fable-5-1`, `claude-mythos-5-1`, `claude-opus-5`, `claude-haiku-4-5` …
- `platform.claude.com/docs/en/api/http/messages/create` lists
  `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5`, `claude-mythos-5-1` …

Both also document **deprecation with end-of-life dates** (e.g. entries marked
deprecated reaching EOL in 2026).

**I am not recording a specific model name as authoritative.** Two first-party
pages disagree, and model identifiers change on a schedule shorter than this
project's planning horizon. The correct engineering response is
`GET /v1/models` at integration time, not a hard-coded name copied from a
search result.

No model name appears anywhere in this repository's source.

### Not verified

| Aspect | State |
|---|---|
| Pricing | **UNVERIFIED** — not consulted; no cost model implemented |
| Rate limits | **UNVERIFIED** — not stated on the pages consulted |
| Data retention policy | **UNVERIFIED** — relevant to a research pipeline; must be read before sending any data |
| Tokenisation behaviour on financial text | **UNVERIFIED** |
| Region/data-residency options | **UNVERIFIED** |

Retention in particular is a blocker to *sending research data*, and this phase
sends none.

---

## 3. Kimi — UNVERIFIED

| Aspect | State |
|---|---|
| Official API documentation | **NOT CONSULTED in this phase** |
| Endpoint, auth, model names | **UNVERIFIED** |
| Pricing, rate limits | **UNVERIFIED** |
| Data retention | **UNVERIFIED** |

No claim is made about this provider's capabilities. The prompt named it as a
candidate; researching it was not completed, and **an unresearched provider must
not be treated as available or unsuitable** — it is simply unknown.

To adopt it later, the same verification this received would be required:
official documentation, auth method, model identifiers, retention, and
redistribution terms.

---

## 4. DeepSeek — UNVERIFIED

Identical position to Kimi. Nothing was verified; no claim is made.

---

## 5. Why no client was implemented

The Phase 48 instruction was explicit: *"If credentials are unavailable, do not
ask the user to paste secrets into chat or source files. Implement the interface,
configuration validation, mocked tests, and documented setup requirements
instead. Mark live provider integration as NOT IMPLEMENTED."*

No credential is available, and none was requested. Writing an HTTP client
against documentation that has not been read to completion — with unverified
model names, unverified retention, and unverified rate limits — would produce
code that *looks* integrated and cannot be validated here. That is worse than an
explicit absence, because absence is visible.

---

## 6. What *is* implemented and tested

| Component | Tests |
|---|---|
| `AIResearchProvider` protocol (runtime-checkable) | mock satisfies it; a partial implementation does not |
| `ProviderRequest` — no market data, prompt states limits | 6 |
| `ProviderResponse` — truncation detection, redaction default | 5 |
| `ResearchAnalysis` — required evidence, abstention rules, no probability claims | 30+ |
| `AnalysisPipeline.ordering_is_sound()` | 5, including a deliberately broken pipeline |
| `redact_secrets` | 4 |

**73 tests, all mocked.** A mocked suite demonstrates that the *contract* is
coherent and enforceable. It demonstrates nothing whatsoever about whether any
provider works.

### Tests that assert absence

These exist because the risk is overclaiming:

- `test_no_provider_client_in_module` — no `requests`/`httpx`/`anthropic`
- `test_no_network_import_anywhere_in_package` — the whole engine stays offline
- `test_no_credential_lookup_in_module` — no `os.environ` in the AI layer at all
- `test_no_secret_pattern_in_repository_tests` — this phase adds no secret, not
  even a fake fixture
- `test_no_ai_import_in_execution_path` — AI unreachable from the trading engine
- `test_ai_research_does_not_import_researchguard` — AST-scanned
- `test_protocol_is_not_implemented_by_this_module` — no concrete provider class

---

## 7. Setup requirements if integration proceeds later

Documented, not executed. **Do not paste a key into chat or a source file.**

1. Create a key in the provider's console; scope it to a single workspace.
2. Export it in the **shell environment**, never in a committed file:
   `ANTHROPIC_API_KEY` for Anthropic, or the equivalent for another provider.
3. Confirm the repository `.gitignore` excludes `.env*` — it already does
   (`.env`, `.env.*`, `!.env.example`).
4. **Read the retention policy** and confirm it is acceptable for research data.
5. Confirm rate limits and cost before any bulk use.
6. Implement the adapter against `AIResearchProvider`, honouring:
   - `timeout_seconds` as a required argument
   - `max_retries` as a bound
   - `redact_secrets` on anything logged
   - `ResearchAnalysis.from_record` to validate every response
   - `AbstentionReason.PROVIDER_UNAVAILABLE` for outages, so an outage is
     distinguishable from a considered abstention
7. Add tests that fail without the adapter — and keep them separate from the
   mocked contract tests so the two are never confused.

---

## 8. Honest summary

- **One provider's documentation was verified.** Its API shape, headers, auth
  methods and workspace scoping are recorded above.
- **Two named providers were not researched.** No claim is made about either.
- **Zero providers are integrated.** No client, no credential, no call.
- **The interface is implemented and tested**, so adoption is a bounded task
  rather than a design exercise.

The single most important thing in this document is what it does *not* say: it
does not say any provider is available, working, or tested. Those would be false.