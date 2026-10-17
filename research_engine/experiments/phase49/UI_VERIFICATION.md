# Phase 49 UI Verification

**Date:** 2026-10-09

---

## 1. Commands and exact results

### Frontend

| Command | Result |
|---|---|
| `pnpm exec tsc -p tsconfig.json --noEmit` | **exit 0**, no diagnostics |
| `pnpm test` | **478 passed**, 9 files, 0 failed |
| `PORT=5000 BASE_PATH=/ pnpm exec vite build` | **exit 0**, `✓ built in 9.59s` |

Baseline before Phase 49: 435 tests, typecheck exit 0, build exit 0.

`PORT` and `BASE_PATH` are **required** by `vite.config.ts`, which throws
without them. That is pre-existing, not introduced here.

### Backend

| Command | Result |
|---|---|
| `pytest tests/test_research_api.py tests/test_research_guard.py tests/test_research_gaps.py tests/test_registry_schema.py tests/test_data_pipeline.py` | **331 passed**, 12.6s |
| Full suite, 45 files, per file, 25-min cap | **2499 passed, 0 failed** |

New: `tests/test_research_api.py`, 58 tests.

**No timeouts. No skipped tests. No deleted tests. No xfail. No test weakened.**

Two pre-existing test files were **extended with justification**, never relaxed —
see §4.

---

## 2. What the tests actually assert

### Backend — truthfulness, not shape

| Property | Test |
|---|---|
| No reservation is ever reported `evaluated` | `test_no_reservation_is_ever_reported_evaluated` |
| ETH is `RESERVED`, `used: false`, `preregistration_id: null` | `test_eth_reservation_is_reserved_and_unused` |
| ETH is never `RESEARCH_APPROVED` | `test_eth_is_not_labelled_approved` |
| BTC reads `CONSUMED`, not `BLOCKED` | `test_btc_is_labelled_consumed_not_blocked` |
| Every blocked instrument carries a reason | `test_every_blocked_instrument_states_its_blocker` |
| POST/PUT/DELETE/PATCH refused on all four routes | 16 parametrised tests |
| Query parameters cannot steer reported state | `test_research_routes_accept_no_parameters` |
| Provider status opens no socket | `test_provider_projection_makes_no_outbound_call` |
| No credential string in any response | `test_no_credential_is_ever_exposed` |
| Unreadable registry → 503, never empty | `test_unreadable_registry_yields_503_not_empty` |
| No filesystem path in any payload | `test_instruments_response_exposes_no_filesystem_path` |
| Consumed window retired with its outcome | `test_btc_holdout_is_retired_with_its_outcome` |

### Frontend — cannot mislead a reader

| Property | Test |
|---|---|
| ETH never labelled approved | `never labels ETH approved` |
| Blocked instrument shows its blocker | `labels a blocked instrument BLOCKED and shows its reason` |
| Consumed distinguished from blocked | `distinguishes consumed from blocked` |
| Reserved window reads `NOT EVALUATED` | `shows a reserved window as NOT EVALUATED` |
| No preregistration is stated plainly | `says no preregistration is frozen` |
| No provider reads as integrated | `states that no provider is integrated` |
| Unresearched ≠ unsuitable | `distinguishes verified documentation from unresearched providers` |
| AI Intelligence clarified as arithmetic | `clarifies that the AI mode is not a model` |
| Evidence fabricates nothing | `fabricates no items to fill an empty panel` |
| No chart rendered from nothing | `renders no chart or metric, because none is available` |
| Fault ≠ empty | 3 separate tests, one per panel family |
| **No control can spend or approve** | `offers no control that could spend or approve a window` — asserts zero `button` and zero `input` elements |

### Source-level guards on the panel module

Stripped of comments/strings/JSX first (matching the existing suite's
`codeOnly` approach), then scanned for: `Math.random`, `Date.now`/`new Date`,
`fetch`/`axios`, `import.meta.env`, and profitability vocabulary. **No matches.**

---

## 3. Bundled output scanned

`dist/public/assets/*.js` scanned for `sk-ant-*`, `sk-proj-*`,
`Bearer <token>`, secret-shaped assignments, and API-key environment references.
**No leak found.**

A first, naive scan for the substring `sk-` reported a hit. Every match was
inside a CSS class name: `mask-`, `risk-`, `task-`, `flask-conical`. Recorded
because a naive scan that reports "clean" and a naive scan that reports "leak"
are equally unreliable, and only the second one prompts investigation.

---

## 4. Existing tests changed — and why

Two. Both were extensions with written justification, not relaxations.

| Test | Change | Justification |
|---|---|---|
| `test_api_health::test_only_the_permitted_routes_exist` | 4 read-only routes added to the expected set | An exact route inventory. Phase 49 adds four GET-only routes with their own 58 tests, including 16 asserting writes are refused. The guard now *knows about* them rather than being loosened to ignore them |
| `test_research_api::test_credential_configured_is_false_and_boolean` | **Rewritten** to assert the field is *absent* | See below |

### The credential field

I initially shipped `credential_configured: false`. Two things were wrong with it.

The existing `test_api_replay` guard forbids the word "credential" anywhere in
API code, and it was right to.

But the real problem was subtler: **`providers_projection()` never reads the
environment.** It cannot know whether a key exists. A hardcoded `false` is a
fabricated observation presented as a measurement.

The field was removed and the test now asserts a stronger property — that no
key-presence claim appears at all. Absence is the honest representation; a
confident `false` is not.

---

## 5. Not verified

Stated plainly rather than implied:

| Area | Status |
|---|---|
| Live backend integration | **NOT RUN.** All frontend tests use the existing `setDefaultApi` stub |
| Accessibility (axe, screen reader, keyboard traversal) | **NOT RUN.** Implemented by construction — `dl`, `section[aria-label]`, `aria-live`, `role="alert"`, existing focus primitives — but unmeasured |
| Responsive behaviour at real viewports | **NOT RUN.** Tailwind breakpoints applied; no viewport-matrix test |
| Visual regression / screenshots | **NOT RUN** |
| Lighthouse / bundle analysis | **NOT RUN** |

These are real gaps. The dashboard is verified to be *correct in what it claims*,
not verified to be *pleasant to use*.

---

## 6. ETH and frozen artifacts

```
status             : RESERVED
used               : False
preregistration_id : None
research_approval  : DATA_VERIFIED_NOT_RESEARCH_APPROVED
dataset SHA-256    : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

All 11 frozen digests verified unchanged against previously recorded values. No
baseline re-derived.

---

## 7. Interpretation

2499 backend and 478 frontend tests mean the dashboard cannot misrepresent the
project's capabilities: a blocked instrument carries its blocker, a reserved
window cannot read as evaluated, no provider reads as integrated, and a backend
fault cannot read as absent data.

They say nothing about profitability, and nothing in Phase 49 bears on that
question.