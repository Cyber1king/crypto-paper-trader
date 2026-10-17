# Phase 32 — Proposed AI Market Research Layer Architecture

**Status: PROPOSAL ONLY. Nothing in this document is implemented.** No AI API was
called, no provider integrated, no source code changed. Providers named here are
**planned components, not assumed capabilities**.

Every provider-specific question is marked **[VERIFY]** and must be answered from
official documentation before any implementation. **No API capability, price,
rate limit or data availability is asserted in this document.**

---

## 1. Design principles

These follow from what the repository already enforces, so the AI layer does not
weaken existing guarantees.

| # | Principle | Why it exists |
|---|---|---|
| P1 | **Python is the only calculation authority** | The engine already owns all arithmetic (`simulator.py`, `stats.py`). A model that computed P&L would duplicate and diverge from the audited path |
| P2 | **A model may never alter the strategy, override a risk limit, or execute** | `execution.py:28-41` already forbids policies from setting size, fee, fill or balance. This extends the rule upward |
| P3 | **A model may only influence `should_enter` via the existing policy seam** | `execution.py:10-14` states refusing to trade is a policy choice, not an engine change. That is the integration point |
| P4 | **Weak or conflicting evidence must produce abstention, not a guess** | `IntelligencePolicy` already treats an absent score as a fail (`execution.py:388-392`) |
| P5 | **Every claim carries its source and timestamp** | The dashboard already shows dataset SHA and config hash; external claims need the same discipline |
| P6 | **Facts, interpretations, uncertainty and missing evidence stay separated** | Prevents a model's guess being read as a measurement |
| P7 | **Provider is replaceable** | Avoids lock-in; one provider failing must not stop the system |
| P8 | **Determinism of record** | `walkforward.py` already hashes config, costs and dataset fingerprint mid-run. Analysis inputs must be hashed too |

---

## 2. Layer separation

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION      React dashboard — sources, timestamps,           │
│                    uncertainty, disagreement, abstentions           │
└──────────────────────────────────────────────────────────────────────┘
                              ▲ read-only
┌──────────────────────────────────────────────────────────────────────┐
│  ANALYSIS LAYER    Structured outputs: facts / interpretations /     │
│  (new)             uncertainty / missing_evidence — never numbers    │
│                    that drive trading                                │
└──────────────────────────────────────────────────────────────────────┘
                    ▲ provider interface (replaceable)
┌──────────────────────────────────────────────────────────────────────┐
│  PROVIDERS (new)  Claude │ Kimi │ DeepSeek │ existing AI             │
│                    + future providers. [VERIFY] each.               │
└──────────────────────────────────────────────────────────────────────┘
                              ▲ only timestamped, attributed inputs
┌──────────────────────────────────────────────────────────────────────┐
│  EVIDENCE LAYER    Price/volume │ News │ Economic events │ Sentiment │
│  (new)             Each with: source, publisher, published_at,       │
│                    retrieved_at, revision, confidence, provenance    │
└──────────────────────────────────────────────────────────────────────┘
                              ▲ never influences arithmetic
┌──────────────────────────────────────────────────────────────────────┐
│  AUTHORITATIVE     Python: strategy · simulator · costs · stats ·   │
│  ENGINE (existing) backtest · paper execution · modes · policy seam │
│  UNCHANGED. Computes every number shown or traded.                  │
└──────────────────────────────────────────────────────────────────────┘
```

**Direction of authority is one-way and downward.** Evidence informs analysis;
analysis may only *qualify* an entry through the policy seam; the engine
computes everything and is never overridden.

---

## 3. Data-source separation: crypto and forex

**VERIFIED FACT.** The repository currently holds **only BTC/USDT 1h OHLCV**.
No forex data has ever been acquired (`RESEARCH_CHECKPOINT.md:417-428` records
no other asset or timeframe was ever obtained).

**Design.** Separate namespaces and separate provenance chains per asset class:

| Concern | Crypto | Forex |
|---|---|---|
| Instrument identity | exchange + symbol + quote currency | base/quote pair + venue |
| Session/24×7 | 24×7 continuous | **has sessions, weekends, DST** |
| Bar semantics | exchange-defined | venue/broker-defined |
| News attribution | often undifferentiated | often currency/central-bank scoped |
| Cost model | per-leg fee + slippage | may be spread-dominated |
| Publication cadence | monthly/daily archives | vendor-dependent |

**Hazard to design against:** an "hourly candle" in forex and an hourly crypto
candle are not the same object. DST transitions, session opens and weekend gaps
mean naive concatenation is invalid. The existing dataset validator
(`dataset.py:33-72`) checks OHLC relationships and strictly increasing
timestamps but **does not check calendar alignment or session gaps** — a forex
adapter would need its own strict validator, modelled on `acquisition.py`'s
`_check_row` (`:297-312`) plus session-awareness.

**[VERIFY]** Which forex venue/data source, and its licensing terms. **[VERIFY]**
Whether historical tick or candle data can be obtained at acceptable cost.

**Note:** adding forex is a **new asset class with new semantics**, not a
parameter change. It requires its own acquisition, validation and manifest
before any comparison to crypto is meaningful.

---

## 4. Evidence layer

### 4.1 Required record structure for every item

Every news, event or sentiment record must carry:

| Field | Purpose |
|---|---|
| `item_id` | stable identifier |
| `source_id`, `source_name` | attribution |
| `published_at` | **when the item was published** — the leakage-critical field |
| `retrieved_at` | when we obtained it |
| `effective_at` | when it became actionable |
| `revision` | version, for corrections |
| `lang` | language |
| `assets` / `instruments` | what it refers to |
| `event_type` | scheduled / unscheduled |
| `importance` | source's own grading, if any |
| `confidence` | **source's** confidence, not the model's |
| `raw_payload_hash` | integrity of the stored original |
| `provenance` | acquisition method and license |

**Leakage rule.** Only items with `published_at <= decision_time` may be
presented to a provider. `retrieved_at` is recorded for audit but must **not** be
used as a substitute for `published_at`, because a backfill library often
retrieves far more recent than the item's true publication time. Where
`published_at` is uncertain, the item must be **excluded**, not guessed.

### 4.2 News ingestion

**Design.** Fetch → store immutable raw → parse → normalise → index by
`(instrument, published_at)`. Never summarise in place; keep the raw payload so a
later claim can be re-verified against the original text.

**Attribution is mandatory**, not optional, for two reasons: licensing, and the
project's existing refusal to show unsourced claims in the UI.

### 4.3 Economic calendar and event risk

Two categories that must not be conflated:

| Category | Example | Availability |
|---|---|---|
| **Scheduled** | known future release time | Times published in advance |
| **Unscheduled** | unscheduled intervention, exchange incident | Times known only after |

**Design.** Store scheduled events with a prior-known timestamp so a backtest can
honestly reproduce what was knowable *before* the event. A surprise print has no
prior timestamp — its `published_at` is the release moment, which is correct and
must be preserved rather than smoothed.

**[VERIFY]** Whether a usable economic calendar with historical
*as-known-at-the-time* data is obtainable, and under what licence. If only
current-version calendars are available, historical backtests would face an
unresolvable look-ahead problem and this data source must be excluded from
backtests while possibly remaining useful for live observation.

### 4.4 Sentiment and its provenance

**Design principle: sentiment is an interpretation, not a fact.** It must be
labelled as such and attributed to whoever produced it.

| Source type | Example | Treat as |
|---|---|---|
| Vendor score | a paid sentiment index | **third-party opinion**, cite the vendor |
| Model-derived | a provider's own assessment | **interpretation**, cite model + version + prompt hash |
| Social aggregate | posts/mentions counts | **weak proxy**, cite platform and coverage |
| Our own | anything we derive | **interpretation**, cite our method |

**Anti-pattern to avoid:** presenting an aggregate mention count as if it were
market truth. Coverage and selection bias are severe and unquantifiable without
vendor methodology.

**[VERIFY]** Any specific sentiment product's methodology, coverage and licensing
before use.

### 4.5 Freshness, deduplication, conflicts, reliability

| Problem | Handling |
|---|---|
| **Freshness** | Every item carries `published_at` and `retrieved_at`. Staleness is a first-class field, not inferred. A stale item is shown as stale |
| **Duplication** | Deduplicate on content hash plus source; syndication of one wire story must count as **one** event, not N. Otherwise one headline inflates apparent corroboration |
| **Conflicting reports** | Preserve both, mark `conflicting`, and let the analysis layer surface disagreement. **Never silently pick one** |
| **Correction/retraction** | Store revisions; a retraction must invalidate prior derived claims. Derived claims must therefore be **recomputable from raw** |
| **Source reliability** | Maintain a provenance-ranked list per category. Reliability is an **assumption to be tested**, not a constant to assert |
| **Gaps** | Absence of evidence is recorded as `missing_evidence`, never as "no news" |

---

## 5. Provider interface (replaceable)

```
class ResearchProvider(Protocol):
    name: str
    model_id: str            # exact model, pinned
    async def analyse(request: AnalysisRequest) -> AnalysisResult: ...
```

**Contract every provider must satisfy**

1. Return **structured** output conforming to one schema, never prose to be parsed
   by regex.
2. **Refuse rather than guess** when evidence is insufficient — return
   `abstain` with a reason.
3. Never emit executable instructions, strategy parameters, sizes or prices.
4. Report its own uncertainty; a provider that cannot quantify uncertainty must
   say so.
5. Be **deterministic in record**: log model id, prompt hash, parameters,
   temperature, seed if any, and the exact input item ids.
6. Never receive credentials in the prompt path; never be able to place orders.

**Structured output schema — the central requirement**

```json
{
  "facts": [
    { "statement": "...", "source_item_ids": ["..."], "published_at": "..." }
  ],
  "interpretations": [
    { "statement": "...", "based_on_fact_ids": ["..."], "confidence": "low|med|high" }
  ],
  "uncertainty": [
    { "about": "...", "reason": "...", "what_would_resolve_it": "..." }
  ],
  "missing_evidence": ["..."],
  "conflicts": [ { "item_ids": ["..."], "nature": "..." } ],
  "abstain": false,
  "abstain_reason": null
}
```

**Why this schema matters.** `facts` must be traceable to `source_item_ids`; an
untraceable "fact" is an interpretation and belongs in the other bucket. This is
what prevents a model's guess from being displayed as a measurement — the exact
failure mode the dashboard already guards against by deleting its mock
`confidence` field (`paper_api/README.md:110-117`).

**Planned providers.** Claude, Kimi, DeepSeek, and the existing AI capability.

**[VERIFY] for each, before implementation:** exact model IDs and versioning;
structured-output or JSON-schema support; tool/function calling behaviour;
context window and truncation policy; rate limits and tiering; **current pricing
per token, input and output separately**; data-retention and training-use terms;
regional availability; and whether the provider can be pinned to a specific
model version for reproducibility. **None of these is asserted here.** No price
is quoted because none has been verified.

**"The existing AI" is a placeholder, not a specification.** As verified in
Phase 32 §1.4, `ai_intelligence` today is a **deterministic 0–100 gate with no
model at all** (`intelligence.py:105`, `ai-panels.tsx:48-51`). Any future external
provider is new capability with no existing foundation.

---

## 6. Integration point: the policy seam, and its limits

**VERIFIED FACT.** `ExecutionPolicy` receives an immutable `DecisionContext`
containing **no candle objects**, so a policy "cannot introduce future leakage,
because the data required to do so is never handed to it" (`execution.py:46-49`).
It may decide only `should_enter`, `select_exit`, `max_positions`
(`execution.py:20-26`).

**A future AI-qualification policy would therefore:**

- return `should_enter = False` when evidence is weak, absent or conflicting;
- otherwise defer to the existing engine signal;
- **never** set size, fee, fill or balance;
- read `intelligence_score`, `bars_held`, `open_position_count`,
  `daily_target_reached` from the context (`execution.py:114-227`).

**A real limitation to record honestly.** The seam is structurally leakage-safe
with respect to **candles**. But an external analysis is derived from *evidence*
whose leak-safety depends entirely on the `published_at <= decision_time` rule in
§4.1. **The seam does not protect against a leaking evidence layer.** That control
belongs to ingestion and must be enforced there and tested independently.

**Non-negotiable boundaries**

| The model may | The model may **never** |
|---|---|
| Qualify or decline an entry | Alter strategy code or parameters |
| Supply attributed, timestamped analysis | Override `risk_fraction` or any risk limit |
| Abstain | Set position size, fee, fill or balance |
| Be logged and compared | Execute, schedule or route a trade |
| Disagree with another provider | Be treated as ground truth |

Risk limits are enforced in Python (`simulator.py:82-83` refuses
`risk_fraction > 1.0`) and must remain unreachable from any analysis path.

---

## 7. Observation-only mode

**VERIFIED FACT.** A structurally observation-only mode already exists:
`alerts` has `supports_execution=False`, `policy=None`, and **holds no broker
reference at all** (`modes.py:58-65`). The stated principle: "An object that
cannot reach a `PaperBroker` is incapable of trading, rather than merely
instructed not to" (`modes.py:62-65`).

**Design.** The AI layer defaults to observation-only:

| Condition | Behaviour |
|---|---|
| All providers fail or time out | Log the failure, emit `abstain`, **trade nothing new** |
| Evidence older than a defined staleness bound | Treat as `missing_evidence`, abstain |
| Providers disagree materially | Surface disagreement; abstain unless a preregistered rule says otherwise |
| Model returns unparseable output | Reject, log, abstain — **never** fall back to free-text parsing |
| Provider unavailable at start-up | Degrade to observation-only; do not block the engine |
| Schema validation fails | Treat as provider failure, not as partial success |

**Principle: failure must be safe and boring.** The existing
`IntelligencePolicy` already embodies this — "No score means no qualification…
which is the failure the threshold exists to prevent" (`execution.py:388-392`).

---

## 8. Operational requirements

| Concern | Requirement |
|---|---|
| **Credentials** | Server-side only. Never in the browser bundle, never in a prompt, never in a log. The dashboard's static test already forbids credential terms in UI files (`no-mock-data.test.ts:62-77`) — the backend must match that discipline |
| **Timeouts** | Hard per-request timeout with a bounded retry budget. A hung provider must not stall a replay |
| **Rate limits** | Per-provider client-side limiter with backoff. A 429 must degrade to abstention, never to an unbounded retry loop |
| **Cost tracking** | Per-call token counts and **monetary cost, per provider, per run**, keyed to model id. Cost is an experimental variable (§ `EVALUATION_PROTOCOL.md` §5) and must be measurable |
| **Logging** | Every call: provider, model id, prompt hash, input item ids, latency, token counts, outcome, `abstain_reason`. Logs must be queryable per run and hashable for reproducibility |
| **Caching** | Cache on `(item_ids, prompt_hash, model_id)` so identical questions are not re-billed. Cache hits must be labelled |
| **Graceful degradation** | Every failure mode above results in abstention, never in a silent pass |
| **Determinism** | Pin model id and prompt hash; record both. A provider that silently upgrades its model invalidates comparison across runs |

**Open question for operations.** Whether retrospective bulk analysis is
economically viable depends entirely on token volume and per-token pricing, which
are **[VERIFY]** items. This design intentionally does not estimate cost, because
an invented number would be worse than none.

---

## 9. UI presentation

**VERIFIED FACT.** The dashboard already displays dataset SHA-256, config hash,
execution model, costs, closed-trade drawdown basis and every `Signal` field
(`standard-panels.tsx`, `market-chart.tsx`), and already refuses to show
confidence or expected return without an authoritative source
(`paper_api/README.md:110-117`).

**Required additions, in the same spirit**

| Element | Requirement |
|---|---|
| **Sources** | Every analysis claim shows publisher and a link or identifier to the stored raw item |
| **Timestamps** | `published_at` **and** `retrieved_at` shown together. Age shown. Staleness visible |
| **Fact vs interpretation** | Visually distinct. Never render an interpretation with the styling of a measurement |
| **Uncertainty** | The provider's own uncertainty rendered, not a fabricated confidence |
| **Missing evidence** | Explicitly rendered. Absence of news must never look like absence of risk |
| **Model disagreement** | Where providers differ, show it. Agreement is not evidence, and disagreement is information |
| **Abstention** | Count and reason for abstentions shown, so the system's restraint is visible and auditable |
| **Cost** | Provider spend per run visible |
| **Provenance of the analysis** | Model id and prompt hash shown, so a reader knows what produced it |

**Guard to extend.** `no-mock-data.test.ts` should gain the AI terms, and a new
static guard should forbid the UI from displaying a provider's confidence as if
it were a probability — mirroring the existing forbidden-terminology list
(`:374-387`).

**Explicitly not proposed.** No UI redesign. Per the agreed sequencing, UI work
follows core research and functionality. These are incremental panels on the
existing shell.

---

## 10. Open questions, all marked for verification

| # | Question | Status |
|---|---|---|
| 1 | Exact model IDs, versioning and structured-output support per provider | **[VERIFY]** |
| 2 | Per-token pricing, input and output, per provider | **[VERIFY]** — no price asserted |
| 3 | Rate limits and tiering per provider | **[VERIFY]** |
| 4 | Data-retention and training-use terms per provider | **[VERIFY]** |
| 5 | Whether a provider can be pinned to a fixed model version | **[VERIFY]** |
| 6 | News source licensing, attribution requirements, historical depth | **[VERIFY]** |
| 7 | Whether an economic calendar offers as-known-at-the-time historical data | **[VERIFY]** — if not, exclude from backtests |
| 8 | Sentiment vendor methodology and coverage | **[VERIFY]** |
| 9 | Forex venue, licence, and session/DST semantics | **[VERIFY]** |
| 10 | Whether token volume makes retrospective analysis economical | **[VERIFY]** — deliberately not estimated |
| 11 | Regional availability and data-residency constraints | **[VERIFY]** |
| 12 | The identity and interface of "the existing AI" | **[VERIFY]** — currently a deterministic gate, not a model |

---

## 11. Explicit non-goals

- Not implementing any part of this architecture.
- Not changing the strategy, costs, defaults or any existing module.
- Not asserting any provider capability, price or availability.
- Not allowing a model to compute P&L, set size, override a risk limit or trade.
- Not redesigning the UI.
- Not proposing acceptance thresholds — those belong in a preregistration before
  any test is run.