# Phase 50 Security and Integrity Audit

**Date:** 2026-10-09
**Method:** Live checks against running code. Every claim below was executed.

---

## 1. Credentials and secrets

| Check | Command | Result |
|---|---|---|
| Credential patterns in tracked Python source | scan `research_engine/src/**/*.py` for `sk-ant-`, `sk-proj-`, `*_API_KEY` | **NONE** |
| Credential patterns in frontend source | scan `artifacts/crypto-paper-lab/src/**/*.{ts,tsx}` | **NONE** |
| Credential patterns in **built bundle** | scan `dist/public/assets/*.js` | **NONE** |
| API reads credentials from environment | `test_api_replay` forbids `api_key`/`secret`/`credential` in API code | **PASS** |
| AI layer reads environment | `os.environ` in `ai_research.py` | **FALSE** |
| Provider status performs a network call | socket patched, projection called | **NO CALL** |
| `.gitignore` covers `.env` | — | `.env`, `.env.*`, `!.env.example` |

### A false positive worth recording

A naive substring scan for `sk-` flagged the built bundle. Every match was
inside a **CSS class name**: `mask-`, `risk-`, `task-`, `flask-conical`.

A precise scan (`sk-ant-*`, `sk-proj-*`, bearer tokens, secret assignments,
API-key env references) found nothing.

Recorded because "we grepped and it was clean" and "we grepped wrongly" look
identical from outside. The wrong scan is the dangerous one.

---

## 2. Research guards remain active

Verified by source inspection at every strategy-executing entry point:

| Entry point | Guard | Context plumbed |
|---|---|---|
| `run_backtest` | **direct** | yes |
| `replay.Replay.__init__` | **direct** | yes |
| `run_experiment` | forwards | yes |
| `run_yearly_backtests` | forwards | yes |
| `run_window` | forwards | yes |
| `walk_forward` | forwards | yes |

Behavioural proof (Phase 42, re-confirmed): all six refuse the real reserved
ETH dataset with no research context, across eight series shapes including
arbitrary sub-slices, reversals and every-other-bar subsets.

---

## 3. UI cannot bypass research eligibility

| Control | Status |
|---|---|
| Research API routes | **GET only** — confirmed by `app.routes` inspection and 16 tests asserting POST/PUT/DELETE/PATCH → 405 |
| Route parameters | none; extra params ignored, so nothing can steer a reported state |
| Governance panel controls | **zero** `button`, **zero** `input` elements |
| Registry write path | **none exists** anywhere in the API |
| Approval from the browser | **impossible** — no route accepts it |

The browser cannot approve an instrument, spend a window, or evaluate anything.
Those decisions are made in the Python engine and are not reachable from the
interface.

---

## 4. ETH reservation

```
status                     : RESERVED
used                       : False
preregistration_id         : None
used_on present            : False
research_approval          : DATA_VERIFIED_NOT_RESEARCH_APPROVED
approved_preregistration_id: None
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

All three required values match. The digest matches the value specified in the
Phase 50 brief exactly.

**No ETH 2026 performance was computed, inspected or revealed in Phases 49–50.**
The two Phase 46 tests that read the file assert row count, endpoint timestamps
and digest only.

---

## 5. Frozen research artifacts — 11 of 11

| Artifact | Digest | Result |
|---|---|---|
| BTC primary | `201a3b15…` | OK |
| Consumed BTC holdout | `c475e541…` | OK |
| Phase 29 preregistration | `b06f36e2…` | OK |
| ETH dataset | `7507c100…` | OK |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e2…` | OK |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741…` | OK |
| Phase 30 `RESULTS_trades.csv` | `174d5587…` | OK |
| Phase 30 `SUMMARY.md` | `9e3171b0…` | OK |
| Phase 33 acquisition report | `bb446099…` | OK |
| Phase 34 independent audit | `e611ecdb…` | OK |
| Phase 35 provenance correction | `ee704878…` | OK |

**Verified against previously recorded values. No baseline re-derived, no
expected hash overwritten, no historical result edited.**

---

## 6. Consumed BTC holdout — retired

```
preregistration_id : phase29d-eth0-btc-holdout
outcome            : INCONCLUSIVE
bars               : 912
window             : 2026-09-01 .. 2026-10-08
retired            : true
```

Enforced by `assert_evaluation_permitted`, which refuses any consumed window
outright, and surfaced in the dashboard as `RETIRED`.

---

## 7. No performance-producing evaluation ran

| Check | Result |
|---|---|
| Backtests run in Phases 49–50 | **none** |
| Trade-generating replays | **none** |
| Walk-forward evaluations | **none** |
| Performance calculations | **none** |
| New test files invoking engine strategy logic | **none** |

`test_research_api.py` (58) and `research-panels.test.tsx` (40) contain no
engine call. The suite is 2499 backend + 478 frontend tests, all policy and
rendering.

---

## 8. Findings requiring a decision

### 8.1 A fabricated observation, found and removed

Phase 49 initially shipped `credential_configured: false` on the provider
response. `providers_projection()` never reads the environment, so it **cannot
know** whether a key exists. The field was a hardcoded constant dressed as a
measurement.

An existing test (`test_api_replay`) forbids the word "credential" in API code
and flagged it. The guard was right — but the *word* was the symptom, not the
disease.

**Fixed:** field removed. The test now asserts it is *absent*, which is the
stronger property. Absence of a key is a deployment detail; the honest way to
express "I do not know" is not to claim to know.

### 8.2 Scope guard extended, not relaxed

`test_only_the_permitted_routes_exist` maintains an exact route inventory. Four
read-only routes were added to it with the reasoning documented in the guard's
own docstring. The guard now *knows about* them rather than being loosened.

---

## 9. Residual risks

| Risk | Severity | Why it remains |
|---|---|---|
| Guards are editable Python, not a security boundary | **structural** | Anyone with repo access can change them. They raise the cost of a mistake; they do not stop a determined actor |
| Unregistered series are permitted | low | Data the registry has never seen cannot be identified |
| Sub-3-bar slices unmatched | **inert** | The engine needs >22 bars to signal, so an unmatched series cannot trade |
| `consume_reservation()` can be skipped | low | Deliberate — a crashed attempt must not spend a window. Protects against unauthorised reuse, not process-skipping |
| Four sources have UNVERIFIED licensing | medium | Terms were not confirmed; redistributing under an unknown licence is a real exposure |
| Provider status is static | low | Will go stale if an adapter lands without updating `_PROVIDER_STATUS` |
| Dashboard untested against a live backend | medium | All frontend tests use a stub; a contract drift between client and server would not be caught |

---

## 10. Verdict

**PASS.** No credential in any source or bundle. All six strategy-executing
entry points remain guarded. UI controls cannot bypass eligibility. The ETH
reservation is `RESERVED` / `used: false` / `preregistration_id: null` with the
specified digest intact. All 11 frozen hashes match. No performance-producing
evaluation ran.

One fabricated observation was found and removed, and one scope guard was
extended with justification rather than relaxed.