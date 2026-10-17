# Phase 36 — AI Research Layer Specification

**Status: SPECIFICATION ONLY. No provider is integrated. No API call was made.**

> **Verified during this phase:** the repository contains **zero** external AI
> integrations. A repository-wide search for `anthropic`, `openai`, `claude`,
> `kimi`, `deepseek`, `langchain`, `llama`, `gemini`, `ollama` and
> `chat.completion` found none. The only credential-shaped references are
> `MARKET_DATA_API_KEY` in `data.py:93` and tests asserting credentials are
> **absent** from responses (`test_api_health.py:161`, `test_api_market.py:588`).
>
> **The existing `ai_intelligence` mode is not an AI model.** It is a
> deterministic 0–100 score with a fixed threshold of 90
> (`intelligence.py:105`, `execution.py:332-417`). The dashboard states it is
> *"a deterministic qualification gate on a 0–100 scale, not a probability, win
> rate, confidence percentage or expected return"* (`ai-panels.tsx:48-51`).
> There is no model anywhere in this system today.

---

## 1. Purpose and hard boundary

The layer produces **attributed, timestamped, uncertainty-bearing analysis**.
It never produces a number the engine trades on.

| The layer may | The layer may **never** |
|---|---|
| Return structured, sourced analysis | Compute P&L, size, fee, fill or balance |
| Qualify or decline an entry via `should_enter` | Alter strategy code or parameters |
| Abstain when evidence is insufficient | Override `risk_fraction` or any risk limit |
| Disagree with another provider | Set or alter a position |
| Be logged and compared | Execute, schedule or route a trade |
| State its own uncertainty | Emit untraceable "facts" |

**Enforcement is structural, not advisory.** The only integration point is
`ExecutionPolicy.should_enter` (`execution.py:20-26`), and a policy is handed an
immutable `DecisionContext` that **"carries no candle objects at all … cannot
introduce future leakage, because the data required to do so is never handed to
it"** (`execution.py:46-49`). A policy may not set size, fee, fill or balance
(`execution.py:28-41`).

---

## 2. Provider interface

```
class ResearchProvider(Protocol):
    provider_id: str
    model_id: str          # exact model, pinned, never "latest"
    async def analyse(request: AnalysisRequest) -> AnalysisResult: ...
```

### 2.1 Contract every provider must satisfy

| # | Requirement |
|---|---|
| P1 | Returns structured output conforming to one schema — never prose to be regex-parsed |
| P2 | **Abstains** when evidence is insufficient, with a reason |
| P3 | Emits no executable instruction, parameter, size or price |
| P4 | Reports its own uncertainty; if it cannot quantify, it must say so |
| P5 | Records: provider, `model_id`, prompt hash, parameters, token counts, latency |
| P6 | Never receives credentials in the request path |
| P7 | Cannot reach a broker, account or execution endpoint |
| P8 | Never receives data stamped after the decision time |

### 2.2 Structured output schema

```json
{
  "facts": [
    { "statement": "...",
      "source_item_ids": ["..."],
      "published_at": "2026-09-15T08:00:00Z" }
  ],
  "interpretations": [
    { "statement": "...",
      "based_on_fact_ids": ["..."],
      "confidence": "low|medium|high",
      "confidence_rationale": "..." }
  ],
  "uncertainty": [
    { "about": "...", "reason": "...",
      "what_would_resolve_it": "..." }
  ],
  "missing_evidence": ["..."],
  "conflicts": [ { "item_ids": ["..."], "nature": "..." } ],
  "staleness": { "oldest_source_published_at": "...", "newest_source_published_at": "..." },
  "abstain": false,
  "abstain_reason": null
}
```

**The rule that makes this meaningful:** a `facts` entry must cite
`source_item_ids` that exist in the evidence store and whose `published_at ≤
decision_time`. An uncitable "fact" is an interpretation and belongs in
`interpretations`. This is what prevents a guess being rendered as a measurement
— the exact failure the dashboard already guards against by deleting its mock
`confidence` field (`paper_api/README.md:110-117`).

---

## 3. Analysis domains

### 3.1 Price structure and volatility

| Input | Availability | Notes |
|---|---|---|
| OHLCV | Available for BTC, ETH | Deterministic |
| Trend / S&R | `indicators.trend`, `support_resistance` | **Python computes these; the model interprets them** |
| Realised volatility | `indicators.realised_volatility` exists | Sample stdev of hourly returns; not ATR, not annualised |
| Order book / depth | **Does not exist** | No data; must be reported as `missing_evidence` |
| Funding / open interest | **Does not exist** | Same |

**The model never recomputes an indicator.** It receives Python's values and
explains them. Recomputation would create a second, unaudited calculation path.

### 3.2 News and source credibility

Every item must carry: `item_id`, `source_id`, `source_name`, **`published_at`**,
`retrieved_at`, `revision`, `lang`, `instruments`, `event_type`, `importance`,
`confidence` (the *source's*, never the model's), `raw_payload_hash`,
`provenance`.

| Problem | Required handling |
|---|---|
| **Leakage** | Hard filter `published_at ≤ decision_time`, enforced in ingestion |
| **Backfill libraries** | If `published_at` cannot be verified independently, **exclude the item** — do not substitute `retrieved_at` |
| **Duplicates** | Deduplicate on content hash; one wire story = one event, or corroboration is inflated |
| **Conflicts** | Preserve both, mark `conflicting`, surface disagreement — never silently pick one |
| **Retraction** | Store revisions; a retraction invalidates derived claims, which must therefore be recomputable from raw |
| **Gaps** | Absence of coverage is `missing_evidence`, **never** "no news" |
| **Credibility** | A provenance-ranked list per category — an assumption to be tested, not a constant |

**Status: no news data exists in this project.** None was fetched, and none may
be retrospectively attached to past trades.

### 3.3 Economic calendar and event risk

| Category | Handling |
|---|---|
| **Scheduled** | Store the prior-known timestamp so a backtest reproduces what was knowable *before* the event |
| **Unscheduled** | `published_at` is the release moment; that is correct and must be preserved, not smoothed |

**[VERIFY]** Whether a calendar with historical *as-known-at-the-time* data
exists. If only current-version calendars are available, historical backtests face
an unresolvable look-ahead problem and that source must be excluded from
backtests while possibly remaining useful for live observation.

**Status: no calendar data exists.**

### 3.4 Sentiment and conflicting evidence

Sentiment is an **interpretation, not a fact**, and must be labelled as such.

| Source type | Label as |
|---|---|
| Vendor index | Third-party opinion; cite vendor and methodology |
| Model-derived | Interpretation; cite model, version, prompt hash |
| Social aggregate | Weak proxy; cite platform and coverage |
| Our own derivation | Interpretation; cite method |

An aggregate mention count must never be presented as market truth; coverage and
selection bias are severe and unquantifiable without vendor methodology.

**Status: no sentiment data exists.**

### 3.5 Cross-market relationships

Permitted only where data support it — see `MULTI_MARKET_ARCHITECTURE.md` §5.
Currently feasible for BTC↔ETH (identical timestamps and interval). **Blocked**
for crypto↔FX because no FX OHLC and no FX session calendar exist.

All cross-market arithmetic is computed in Python; the model only interprets.

### 3.6 Uncertainty, missing evidence, staleness

Every result carries `uncertainty`, `missing_evidence` and `staleness`. A result
with empty `uncertainty` and empty `missing_evidence` should be treated as
**suspicious**, not confident — it more likely indicates incomplete retrieval.

---

## 4. Observation-only mode

**A structurally observation-only mode already exists.** `alerts` has
`supports_execution=False`, `policy=None`, and **holds no broker reference at
all** (`modes.py:58-65`). The stated principle: *"An object that cannot reach a
`PaperBroker` is incapable of trading, rather than merely instructed not to."*

**Default behaviour of the AI layer: observation-only.**

| Condition | Behaviour |
|---|---|
| All providers fail or time out | Log, emit `abstain`, open nothing |
| Evidence older than a preregistered staleness bound | Treat as `missing_evidence`, abstain |
| Providers disagree materially | Surface disagreement; abstain unless a preregistered rule says otherwise |
| Unparseable output | Reject, log, abstain — never regex a fallback |
| Provider unavailable at start-up | Degrade to observation-only; do not block the engine |
| Schema validation fails | Treat as provider failure, not partial success |
| Cost budget exhausted | Abstain, log the exhaustion |

Failure must be **safe and boring** — the principle `IntelligencePolicy` already
embodies: *"No score means no qualification… which is the failure the threshold
exists to prevent"* (`execution.py:388-392`).

---

## 5. Operational requirements

| Concern | Requirement |
|---|---|
| **Credentials** | Server-side only. Never in the browser bundle, a prompt or a log. The dashboard's static test already forbids credential terms in UI files (`no-mock-data.test.ts:62-77`); the backend must match |
| **Timeouts** | Hard per-request timeout with a bounded retry budget. A hung provider must not stall a replay |
| **Rate limits** | Client-side limiter with backoff. A 429 degrades to abstention, never an unbounded retry loop |
| **Cost tracking** | Token counts and monetary cost per provider per run, keyed to `model_id`. Cost is an experimental variable and must be measurable |
| **Logging** | provider, `model_id`, prompt hash, input `item_ids`, latency, tokens, outcome, `abstain_reason` |
| **Caching** | Key on `(item_ids, prompt_hash, model_id)`. **Cache hits must be labelled**, and failure counts reported separately |
| **Determinism** | Pin `model_id` and prompt hash; record both. A silent model upgrade invalidates cross-run comparison |
| **Budgets** | Hard per-run spend ceiling with graceful degradation, not a hard failure |

**Deliberately not estimated.** Whether retrospective bulk analysis is
economically viable depends on token volume and per-token pricing, both
**[VERIFY]**. An invented cost figure would be worse than none.

---

## 6. Provider status — all unverified

| Provider | Integration | Model IDs | Pricing | Limits | Retention terms |
|---|---|---|---|---|---|
| Claude | **none** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** |
| Kimi | **none** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** |
| DeepSeek | **none** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** |
| Other approved | **none** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** | **[VERIFY]** |

**No capability, price, rate limit, context window or data-retention term is
asserted anywhere in this document.** All must be established from official
documentation before implementation.

Additional verification items: structured-output/JSON-schema support; tool-calling
behaviour; model-version pinning; regional availability and data residency.

---

## 7. UI requirements

The dashboard already displays dataset SHA-256, config hash, execution model,
costs, drawdown basis and every `Signal` field, and already refuses unsourced
confidence claims (`paper_api/README.md:110-117`). Additions must follow that
spirit.

| Element | Requirement |
|---|---|
| Sources | Publisher and a reference to the stored raw item for every claim |
| Timestamps | `published_at` **and** `retrieved_at` together; age shown; staleness visible |
| Fact vs interpretation | Visually distinct; an interpretation must never look like a measurement |
| Uncertainty | The provider's own uncertainty, not a fabricated confidence |
| Missing evidence | Explicitly rendered; absence of news must not look like absence of risk |
| Disagreement | Providers that differ must be shown as differing; agreement is not evidence |
| Abstention | Count and reason, so restraint is visible and auditable |
| Cost | Provider spend per run |
| Provenance | `model_id` and prompt hash |

**Guard to extend.** `no-mock-data.test.ts` should gain AI terms and forbid the UI
from displaying provider confidence as a probability, mirroring the existing
forbidden-terminology list (`:374-387`).

**No UI redesign is proposed.** Per agreed sequencing, UI work follows core
research.

---

## 8. Acceptance criteria for a future implementation

| # | Criterion |
|---|---|
| B1 | A stub provider can be added with no engine change |
| B2 | Schema validation rejects malformed output; there is no regex fallback |
| B3 | Timeout, 429, malformed-output and empty-evidence paths all degrade to `abstain` |
| B4 | `published_at > decision_time` items are impossible to reach the provider — proven by test |
| B5 | A fact without a valid `source_item_ids` citation is rejected by test |
| B6 | Credentials appear nowhere in logs, prompts or the UI bundle — proven by static test |
| B7 | Cost, latency and failure counts are recorded per provider per run |
| B8 | All six paper modes still pass their full existing suites |
| B9 | No model output can alter a risk limit — proven by test |
| B10 | The layer runs observation-only by default |

---

## 9. Out of scope

- Implementing the layer or integrating any provider.
- Any API call, credential use or spend.
- Any strategy, parameter, cost or application-code change.
- Any backtest or performance calculation.
- Any UI redesign.
- Asserting any provider capability or price.