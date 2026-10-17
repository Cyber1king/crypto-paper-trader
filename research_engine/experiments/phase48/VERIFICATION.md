# Phase 48 Verification

**Date:** 2026-10-09

---

## 1. Commands and results

All from `research_engine/`:

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

### Focused

| Command | Result | Duration |
|---|---|---|
| `pytest tests/test_ai_research.py` | **73 passed** | 0.3s |
| `pytest tests/test_evidence_schema.py` | 72 passed | 0.2s |
| `pytest tests/test_data_pipeline.py` | 66 passed | 1.4s |
| Combined Phases 46+47+48 + guards + validation | **473 passed** | 12.6s |

### Full suite

Per file, 25-minute cap each:

**2441 passed, 0 failed, 44 files.**

Growth across this batch: 2230 (end of Batch 1) → **2441**, i.e. **211 new
tests**, none of which execute strategy logic.

---

## 2. Provider integration status — the honest answer

| Provider | Client | Credentials | Tested | Docs verified |
|---|---|---|---|---|
| Anthropic (Claude) | **NO** | none | mocked only | **YES** |
| Kimi | **NO** | none | mocked only | **NO** |
| DeepSeek | **NO** | none | mocked only | **NO** |

**Zero providers integrated. Zero credentials. Zero provider calls.**

A mocked suite is not evidence that any provider works, and this verification
does not present it as such.

### Anthropic — what was verified

From `platform.claude.com/docs/en/api/overview`,
`docs.anthropic.com/en/api/messages`,
`platform.claude.com/docs/en/manage-claude/authentication`:

- Base URL `https://api.anthropic.com`; primary endpoint `POST /v1/messages`
- Required headers: `anthropic-version`, `content-type`
- Auth: `Authorization: Bearer <key>` or legacy `x-api-key`; WIF via
  `POST /v1/oauth/token`
- `ANTHROPIC_API_KEY` env var
- `anthropic-workspace-id` required for multi-workspace keys
- Batch API, token counting, and model listing endpoints exist

### A discrepancy recorded rather than resolved

**The two official pages consulted disagree on model identifiers.**
`docs.anthropic.com` lists `claude-sonnet-5` / `claude-opus-5`;
`platform.claude.com` lists `claude-sonnet-5-5` / `claude-opus-5-5`. Both
document deprecations with EOL dates.

No model name was hard-coded anywhere. Two first-party sources disagree and
model identifiers change faster than this project's planning horizon, so the
correct answer is `GET /v1/models` at integration time.

### Unverified for Anthropic

Pricing, rate limits, **data retention**, tokenisation behaviour on financial
text, and data-residency options. Retention is a blocker to sending research
data, and none was sent.

---

## 3. Tests asserting absence

These exist because the primary risk in this phase is overclaiming:

| Test | Asserts |
|---|---|
| `test_no_provider_client_in_module` | No `requests`/`httpx`/`anthropic`/`openai` in `ai_research.py` |
| `test_no_network_import_anywhere_in_package` | Whole engine stays offline-capable |
| `test_no_credential_lookup_in_module` | No `os.environ` in the AI layer at all |
| `test_no_secret_pattern_in_repository_tests` | This phase adds no secret, not even a fake fixture |
| `test_no_ai_import_in_execution_path` | AI unreachable from `backtest`, `replay`, `walkforward`, `simulator`, `strategy`, `researchguard` |
| `test_ai_research_does_not_import_researchguard` | AST-scanned, not substring |
| `test_protocol_is_not_implemented_by_this_module` | No concrete provider class exists |
| `test_reordered_pipeline_is_detected` | A broken pipeline does not pass the ordering check |

### Two tests failed on first run — self-reference

1. A secret-pattern scan matched its own pattern list.
2. An assertion that `researchguard` was absent matched a prose mention in a
   docstring.

Both fixed by scanning **structurally via the AST**. Substring scans produce
false positives against the test's own code and false confidence against code
that merely discusses a name.

---

## 4. Safety boundaries verified

| Boundary | Test |
|---|---|
| Complete analysis requires evidence | `test_complete_analysis_requires_evidence` |
| Abstention requires reason **and** detail | 2 tests |
| Reason only on an abstention | `test_reason_on_a_complete_analysis_refused` |
| No probability claims in summaries/observations/abstentions | 3 tests + 13 parametrised terms |
| AI cannot consume a reservation | `test_analysis_cannot_reference_a_reservation` |
| Pipeline ordering is sound | `test_pipeline_ordering_is_sound` |
| Stages 6 and 7 are AI-independent | `test_pipeline_validation_and_risk_are_ai_independent` |
| Truncated responses detected | `test_truncated_response_detected` |
| Secrets redacted without leaking length | 4 tests |

---

## 5. Existing `ai_intelligence` mode — unchanged

| Check | Result |
|---|---|
| Imports | `__future__`, `dataclasses`, `hashlib`, `math`, `typing` only |
| Network or model calls | **none** |
| Self-described as | "a deterministic, causal, explainable heuristic" / "qualification gate" |
| Trading behaviour altered by this phase | **no** |
| Renamed or repackaged as real AI | **no** |

It remains a deterministic 0–100 arithmetic gate. The name contains "ai" and is
misleading in isolation; correcting it would change a mode identifier used across
the API, tests and configuration — a breaking change not made unilaterally.

---

## 6. Prohibited-workflow compliance

| Rule | Verification |
|---|---|
| No strategy backtest / simulation / replay | No engine call in Phase 46–48 code or tests |
| No ETH 2026 performance | Two Phase 46 tests read the file for row count, timestamps and digest only |
| No consumed-window reuse | No evaluation performed |
| No parameter tuning | No `StrategyConfig` field touched |
| No AI-provider integration | **none implemented**; asserted by 7 absence tests |
| No secrets in source, logs, fixtures or reports | No credential exists; asserted by AST and keyword scans |
| No fabricated data / news / events / provider responses | All test records use `example.invalid`; no provider response is invented |
| No test weakened | Fixtures updated to satisfy *stricter* schemas; no assertion relaxed |
| No staged / committed / pushed / deleted | Confirmed at end |

---

## 7. ETH reservation and frozen artifacts

```
status                     : RESERVED
used                       : False
preregistration_id         : None
research_approval          : DATA_VERIFIED_NOT_RESEARCH_APPROVED
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

All 11 frozen artifact digests verified unchanged against the exact previously
recorded values. No baseline re-derived.

---

## 8. Interpretation

2441 passing tests mean the pipeline refuses contradictory provenance, evidence
records enforce their declared discipline, and the AI interface is coherent,
bounded and testable.

They say nothing about profitability, and nothing about whether any AI provider
works — none is connected.