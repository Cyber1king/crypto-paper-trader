# Phase 49 Dashboard Report

**Date:** 2026-10-09
**Verdict: PASS**

---

## 1. Audit (49.1)

Inspected before any change.

### Frontend

| Aspect | Finding |
|---|---|
| Location | `artifacts/crypto-paper-lab` (React + Vite + Tailwind + shadcn/ui) |
| Data layer | TanStack Query via `lib/hooks.ts`, typed client in `lib/api.ts` (1237 lines) |
| Routing | wouter; a single `/` route |
| Components | 14 live panels/components; ~40 shadcn primitives |
| Tests | 8 Vitest files, 435 tests, all passing at baseline |
| Guards | `no-mock-data.test.ts` enforces honesty properties over an explicit `LIVE_FILES` list |

### Backend contracts (verified, not assumed)

| Route | Method | Notes |
|---|---|---|
| `/healthz` | GET | |
| `/api/session` `/market` `/signal` `/account` `/trades` | GET | existing |
| `/api/modes` `/ai` `/manual` `/high-risk` `/replay` | GET | existing |
| `/api/replay/{start,pause,step,reset}` | POST | existing, unchanged |
| `/api/daily-target[/config]` `/api/high-risk/config` | GET/POST | existing, unchanged |

**The gap: no route exposed any research state.** The API had nothing about the
instrument registry, reservations, provider status or evidence — so the dashboard
could only have shown trading state, or invented research claims in the browser.

### Paper-trading modes — semantics confirmed

`ai_intelligence` (`intelligence.py`) imports only `dataclasses`, `hashlib`,
`math`, `typing`. No HTTP client, no provider SDK, no model. Its own docstring
calls it "a deterministic, causal, explainable heuristic" — a **qualification
gate**, not AI. Phase 49 did not rename it, change its behaviour, or connect it
to anything.

---

## 2. What changed

### Backend: four read-only routes

`paper_api/research_view.py` projects registry state for display;
`paper_api/schemas.py` gained the response models; `paper_api/app.py` gained:

| Route | Returns |
|---|---|
| `GET /api/research/instruments` | every instrument, its real blocker, provenance, licensing |
| `GET /api/research/governance` | reservations and consumed windows |
| `GET /api/research/providers` | AI provider integration state |
| `GET /api/research/evidence` | evidence availability, honestly false |

All four are GET-only, take no body, and have no write path. Authorization and
eligibility decisions stay entirely in the engine.

### Frontend

`components/research-panels.tsx` (new) — five panels: overview, instrument
explorer, governance, provider status, evidence. Wired into `dashboard.tsx`,
with four hooks in `lib/hooks.ts`, types and methods in `lib/api.ts`.

---

## 3. The rule the UI enforces

**A capability that is not implemented must never render as available.**

| Rendered | Means |
|---|---|
| `NOT IMPLEMENTED` | no code path exists |
| `UNAVAILABLE` | code path exists, backend could not answer |
| `BLOCKED` | real, with the backend's stated reason |
| `CONSUMED` | real, permanently spent |
| `RESERVED` | real, unspent |

No "coming soon", no disabled-but-inviting control, no placeholder that could be
mistaken for a value. An empty panel states *why* it is empty.

### Concrete distinctions the UI makes

- **ETH/USDT** → `NOT APPROVED`, never "approved" or "ready".
- **BTC/USDT** → `CONSUMED`, with "retired, not blocked". Spent is not unusable.
- **EUR/USD / GBP/USD / USD/JPY** → `BLOCKED` **with the backend's blocker text
  verbatim**. A block without a reason invites guessing.
- **Reserved window** → `RESERVED` + `NOT EVALUATED` as two separate badges.
- **Providers** → `NONE INTEGRATED`; Anthropic `DOCS VERIFIED`, Kimi/DeepSeek
  `DOCS NOT RESEARCHED`. Verified-documentation is not integration.
- **Evidence** → `NOT IMPLEMENTED`, zero items, "nothing is shown here rather
  than filled with samples".
- **AI Intelligence mode** → an explicit clarifier: "deterministic arithmetic
  qualification gate, not a language model".

---

## 4. Errors, loading and empty states

Three different facts, three different renderings:

| State | Rendered as |
|---|---|
| Loading | `role="status"` + `aria-live="polite"`, "Loading …" |
| Backend fault | `role="alert"`, "unavailable", **and** "This is a connection or server fault, not an absence of data" |
| Genuinely empty | "No X to display" + the backend's reason |

The middle row is the one that matters. A fault and an empty dataset lead to
opposite conclusions, and conflating them is how a reader concludes "none exist"
when the truth is "could not ask". The registry route returns **503** rather than
an empty list for exactly this reason.

`retry: false` on all four queries: a status indicator that retries forever is
worse than one that admits it failed.

---

## 5. A design decision worth flagging

I initially added a `credential_configured: boolean` field to the provider
response, reporting `False`. An existing test (`test_api_replay.py`) forbids the
word "credential" anywhere in API code, and it was right to.

The deeper problem was not the word. **`providers_projection()` never reads the
environment**, so it cannot know whether a key is present. A hardcoded `False`
would be a fabricated observation wearing the costume of a fact.

The field was removed. Absence of a key is a deployment detail; the honest way to
express it is to not claim to know it. The test now asserts the stronger property
— the field must be absent — rather than asserting a value that was never
measured.

---

## 6. Verification

### Commands run

```
# Frontend
pnpm exec tsc -p tsconfig.json --noEmit          # exit 0
pnpm test                                        # 478 passed, 9 files
PORT=5000 BASE_PATH=/ pnpm exec vite build       # exit 0

# Backend
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

### Results

| Suite | Baseline | Now |
|---|---|---|
| Frontend Vitest | 435 passed | **478 passed** (+43) |
| Frontend typecheck | exit 0 | **exit 0** |
| Frontend build | exit 0 | **exit 0** |
| Backend pytest | 2441 passed | **2499 passed**, 0 failed (+58) |

Backend full suite run per file, 25-minute cap: **2499 passed, 0 failed, 45
files.** No timeouts, no skips, no deletions, no xfail.

### Two tests failed on first run, from my own changes

1. **`test_api_health::test_only_the_permitted_routes_exist`** — an exact route
   inventory. Four legitimate read-only routes were added to the expected set,
   with the reasoning documented in the guard's own docstring. The guard was
   **extended deliberately, not relaxed**: `test_research_api.py` additionally
   asserts POST/PUT/DELETE/PATCH are refused on all four.
2. **`test_api_replay`'s credential guard** — see §5. Resolved by removing a
   claim that should not have been made, not by editing the guard.

### Build output scanned for credentials

A naive `sk-` substring scan flagged the bundle. Every match was inside a CSS
class name — `mask-`, `risk-`, `task-`, `flask-conical`. A precise scan for
`sk-ant-*`, `sk-proj-*`, bearer tokens, secret assignments and API-key env
references found **no leak**. The naive scan was the false positive; it is
recorded because "we grepped and it was clean" and "we grepped wrongly" look
identical from outside.

---

## 7. Known limitations

- **Responsive and accessibility are implemented by construction, not measured.**
  Grid classes, semantic elements (`dl`/`section[aria-label]`), `aria-live`,
  `role="alert"`, visible focus via existing primitives. No axe, no screen-reader,
  no viewport-matrix test ran. Stated as untested rather than assumed good.
- **The panels are display-only.** No search or filter is implemented, because
  five instruments do not need one; adding a control that filters nothing would
  be decoration.
- **No chart on the research panels.** There is no time series behind them. The
  only chart remains the existing market chart, fed by `/api/market`.
- **Provider status is static by design.** It will not change until an adapter
  lands. That is honest, and it is also now stale-prone; a future phase must
  update `_PROVIDER_STATUS` deliberately.
- **Evidence panel is permanently "not implemented"** until an ingestion
  adapter exists, which requires a licence-resolved source.
- **The dashboard was not run against a live backend** in this phase. All
  frontend tests use the same `setDefaultApi` stub as the existing suite.

---

## 8. What this does not establish

478 frontend and 2499 backend tests passing mean the dashboard reads real
contracts and states them accurately. They say nothing about whether this
project's strategy is profitable, and nothing here bears on that question.