# Phase 50 Release-Readiness Report

**Date:** 2026-10-09

---

## 1. Phase verdicts

| Phase | Verdict | Basis |
|---|---|---|
| **49** — Dashboard upgrade | **PASS** | 4 read-only routes + 5 panels; 478 frontend / 2499 backend tests; typecheck and build clean |
| **50** — Independent readiness audit | **PASS** | Read-only audit; 11/11 frozen hashes verified; guards active at all six entry points; no credential in any source or bundle |

---

## 2. Implemented capabilities

**Crypto data pipeline** — ingestion, publisher-checksum verification *before
parsing*, reproducible manifests with a provenance ceiling, schema/OHLCV
validation, duplicate and gap detection, declared volume semantics.

**Instrument registry** — 5 instruments with 13-field metadata; 22 classes of
contradictory metadata refused; `load_registry` fails closed.

**Research safeguards** — all six strategy-executing entry points refuse the
reserved ETH series without a valid context; per-bar index closes the omission
bypass across arbitrary sub-slices; consumption is explicit and atomic.

**Evidence schema** — publication vs retrieval time, freshness bands, syndication
and story clustering, economic events with revision and cancellation states,
sentiment that cannot be presented as a probability.

**AI provider status reporting** — four read-only routes; static, no network call.

**Dashboard** — overview, instrument explorer, governance, provider status,
evidence; three distinct rendering of loading / fault / genuinely-empty.

---

## 3. Mocked and unimplemented capabilities

Stated plainly, because this is where overclaiming happens.

| Capability | Truth |
|---|---|
| **Claude integration** | **NOT IMPLEMENTED.** Docs verified; zero client code, zero credentials, zero calls |
| **Kimi integration** | **NOT IMPLEMENTED.** Not researched at all |
| **DeepSeek integration** | **NOT IMPLEMENTED.** Not researched at all |
| **AI-generated analysis** | **MOCKED.** Interface + 73 mocked tests; the ability to produce an analysis does not exist |
| News evidence ingestion | **NOT IMPLEMENTED** |
| Economic-event retrieval | **NOT IMPLEMENTED** |
| Sentiment analysis | **NOT IMPLEMENTED.** Schema only; no source, no scoring |
| Forex session/DST validation | **NOT IMPLEMENTED** |
| Forex OHLC data | **BLOCKED** — no such source exists |

`ResearchAnalysis` is a schema for an output that does not exist yet.

---

## 4. Tests and builds actually run

### Frontend

| Command | Result |
|---|---|
| `pnpm exec tsc -p tsconfig.json --noEmit` | **exit 0** |
| `pnpm test` | **478 passed**, 9 files, 0 failed |
| `PORT=5000 BASE_PATH=/ pnpm exec vite build` | **exit 0** |

Baseline: 435 tests → 478 (+43).

### Backend

| Command | Result |
|---|---|
| Focused (5 files: research API, guards, registry, pipeline) | **331 passed**, 12.6s |
| Full suite, 45 files, per file, 25-min cap | **2499 passed, 0 failed** |

Baseline: 2441 → 2499 (+58).

**No timeouts. No skipped tests. No deleted tests. No xfail. No test weakened.**

### Not run, and why

| Area | Reason |
|---|---|
| Live backend ↔ dashboard integration | Every frontend test uses the existing `setDefaultApi` stub. A contract drift would not be caught |
| axe / screen reader / keyboard traversal | No tooling in the repo. Implemented by construction, **unmeasured** |
| Viewport-matrix responsive test | No tooling. Breakpoints applied, **unmeasured** |
| Visual regression / screenshots | No tooling |
| Any provider integration test | **Cannot exist.** No provider is integrated; mocked tests are not evidence of one |

---

## 5. Files created and modified

### Created (8)

| File | Purpose |
|---|---|
| `src/paper_api/research_view.py` | Read-only registry/governance/provider/evidence projections |
| `src/components/research-panels.tsx` | Five research panels |
| `tests/test_research_api.py` | 58 API truthfulness tests |
| `src/test/research-panels.test.tsx` | 40 UI honesty tests |
| `experiments/phase49/DASHBOARD_REPORT.md` | |
| `experiments/phase49/UI_VERIFICATION.md` | |
| `experiments/phase50/FEATURE_TRUTH_MATRIX.md` | |
| `experiments/phase50/SECURITY_AUDIT.md` | |
| `experiments/phase50/RELEASE_READINESS_REPORT.md` | this file |

### Modified (17 tracked)

Frontend: `api.ts`, `hooks.ts`, `dashboard.tsx`, `no-mock-data.test.ts`.
Backend: `app.py`, `schemas.py`, plus the 9 Phase 39–41 files.
Tests: `test_api_health.py`, `test_replay.py`.

**Tracked: 17 files modified. Untracked: 321. Nothing staged, committed, pushed,
reset, cleaned or deleted.**

### Existing tests changed — both extended, none relaxed

| Test | Change |
|---|---|
| `test_only_the_permitted_routes_exist` | 4 read-only routes added, reasoning in the guard's docstring |
| `test_credential_configured_is_false_and_boolean` | **Rewritten** — asserts the field is *absent* |

---

## 6. Known security and integration limitations

| Limitation | Severity |
|---|---|
| Guards are editable Python, not a security boundary | **structural** |
| Dashboard never tested against a live backend | medium |
| Four sources have UNVERIFIED licensing | medium |
| Provider status is static; will go stale if an adapter lands | low |
| Unregistered series are permitted | low |
| Sub-3-bar slices unmatched | **inert** |
| `consume_reservation()` can be skipped by a careless caller | low |
| Accessibility and responsiveness unmeasured | medium |

**One fabricated observation was found and removed.** `credential_configured:
false` was shipped in Phase 49 while `providers_projection()` never reads the
environment — a hardcoded constant dressed as a measurement. Removed; the test
now asserts absence, which is stronger.

---

## 7. ETH reservation state

```
status                     : RESERVED
used                       : False
preregistration_id         : None
research_approval          : DATA_VERIFIED_NOT_RESEARCH_APPROVED
approved_preregistration_id: None
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

Unspent, unapproved, unmodified. **The ETH evaluation was not started in Phase
50.**

---

## 8. Frozen research hash verification

**11 of 11 verified, 0 mismatches**, against previously recorded values. No
baseline re-derived; no expected hash overwritten; no historical result edited.

BTC primary · BTC holdout · Phase 29 preregistration · ETH dataset · four Phase 30
result artifacts · Phase 33 acquisition report · Phase 34 audit · Phase 35
correction.

Consumed BTC holdout: `INCONCLUSIVE`, 912 bars, permanently retired.

---

## 9. Git state

```
branch            main
HEAD              dccebbd53ee8365474345506db9099b13356b53c
origin/main       dccebbd53ee8365474345506db9099b13356b53c
ahead / behind    0 / 0
staged            none
tracked modified  17
untracked         321
```

---

## 10. Readiness matrix

| Area | Status | Reason |
|---|---|---|
| Dashboard | **INCOMPLETE** | Built and tested against a stub; never run against a live backend; accessibility unmeasured |
| Crypto data pipeline | **READY FOR REVIEW** | Ingestion, checksums, manifests, validation all implemented and tested |
| Forex data pipeline | **BLOCKED** | No OHLC source; no session/DST validator |
| Research safeguards | **READY FOR REVIEW** | Six entry points guarded; omission bypass closed; verified by probe |
| AI provider integration | **BLOCKED** | No credentials, no client. Interface ready; nothing connected |
| News/economic-event evidence | **BLOCKED** | Sources licence-restricted; no adapter exists |
| Research preregistration | **BLOCKED** | Eight decisions unresolved; thresholds deliberately not invented |
| Strategy profitability evidence | **BLOCKED** | One pre-registered test: net PF **0.4925**, INCONCLUSIVE |
| Release readiness | **BLOCKED** | Depends on the four BLOCKED rows above |

`READY FOR REVIEW` does **not** mean profitable or approved for live trading.

---

## 11. Recommended next step

**One action, in this order:**

1. **Finalise the ETH preregistration** — research question, configuration
   choice, costs, execution assumptions, thresholds, uncertainty reporting,
   stopping rules, and a cross-asset authorization record — *without observing
   any result*. Phase 44 itemised all eight; none has moved. This is the only
   thing standing between the project and a governance-complete state, and it
   requires no new data, no new code and no provider.

Then, in rough value order:

2. **Verify the four UNVERIFIED licences** — redistribution under unknown terms
   is the largest untested legal exposure in the repository.
3. **Run the dashboard against a live backend** and add a contract-drift test.
4. **Add accessibility tooling** — the current state is implemented by
   construction, which is not the same as verified.
5. **Integrate a provider**, if one is ever wanted — the interface is ready and
   the setup steps are documented in Phase 48.

**Explicitly not recommended:** starting the ETH evaluation. Four of its six
required conditions are unmet, and the remaining two cannot be resolved without
first fixing the preregistration.

---

## 12. What this batch does not establish

2499 backend and 478 frontend tests passing mean the dashboard cannot
misrepresent the project's capabilities: a blocked instrument carries its
blocker, a reserved window cannot read as evaluated, no provider reads as
integrated, and a backend fault cannot read as absent data.

They say nothing about profitability. The one pre-registered out-of-sample
evaluation this project has run returned a net profit factor of 0.4925 and was
recorded as inconclusive. Nothing since has changed that.

`BATCH 3 PHASES 49–50: PASS`