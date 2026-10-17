# Batch 1 — Phases 43–45 Final Report

**Date:** 2026-10-09

---

## 1. Phase verdicts

| Phase | Verdict | Basis |
|---|---|---|
| **43** — Repository and change audit | **PASS** | 292 untracked files and 11 tracked modifications audited; Phase 39–42 reports verified against source; three real defects found; nothing deleted |
| **44** — Research governance | **PASS** | Rules consolidated; seven unresolved preregistration decisions itemised; no threshold invented; ETH not frozen or approved |
| **45** — Instrument registry | **PASS** | Six demonstrated gaps closed; registry upgraded to v2 with metadata that is now validated, not decorative; forex still blocked |

No phase was skipped. No phase was blocked.

---

## 2. Tests actually run

All from `research_engine/`, per file, so a slow file could not mask the rest.
Per-file cap 25 minutes.

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

| Stage | Result | Duration |
|---|---|---|
| Focused: registry + guard + validation + gates | **273 passed** | 11s |
| Full suite, 40 files | **2230 passed, 0 failed** | ~28 min |

| File | Time | File | Time |
|---|---|---|---|
| test_acquisition | 1s | test_mode_contracts | 22s |
| test_analysis | 1s | test_modes | 8s |
| test_api_account | 28s | test_oos_dataset | 33s |
| test_api_health | 12s | test_phase14c_analysis | 189s |
| test_api_market | 5s | test_phase15_checkpoint | 1s |
| test_api_replay | 25s | test_registry_schema | 2s |
| test_api_session | 21s | test_replay | 155s |
| test_api_signal | 4s | test_replay_lifecycle | 4s |
| test_api_statistics | 15s | test_research_gaps | 9s |
| test_backtest | 1s | test_research_gates | 1s |
| test_config_request_policy | 62s | test_research_guard | 2s |
| test_daily_target | 46s | test_robustness | 42s |
| test_dataset | 1s | test_simulator | 1s |
| test_dataset_validation | 2s | test_strategy | 1s |
| test_entry_filters | 1s | test_validation_boundary | 1s |
| test_entry_time_features | 44s | test_walkforward | 13s |
| test_execution_model | 1s | test_windowstats | 12s |
| test_execution_policy | 28s | test_yearly | 1s |
| test_exit_rules | 1s | test_experiment | 1s |
| test_high_risk | 527s | | |

**No timeouts. No skips. No deletions. No xfail.** No test weakened to obtain a
pass.

Two slow files are pre-existing: `test_high_risk.py` (527s) and
`test_phase14c_analysis.py` (189s). Phases 40–41 established their character
against pristine `HEAD`; their cost is unchanged.

### Tests modified

- `test_research_guard.py` — the `_instrument()` fixture now builds *valid*
  entries. Phase 45 made metadata load-bearing, so a fixture omitting provenance
  and licensing fields would be refused. Fields are minimal and honest
  (`licence_knowledge: UNVERIFIED`) rather than inventing fake licence terms.
- Six consumed-window fixtures gained the required `consumed_on` field.

Both changes make previously under-specified fixtures meet a stricter standard.
**No assertion was relaxed and no expectation was weakened.**

---

## 3. Files changed

### Created (5)

| File | Purpose |
|---|---|
| `src/crypto_paper_lab/registry_schema.py` | Metadata completeness + contradiction refusal |
| `tests/test_registry_schema.py` | 73 tests |
| `experiments/phase43/AUDIT_REPORT.md` | |
| `experiments/phase44/RESEARCH_GOVERNANCE.md` | |
| `experiments/phase45/REGISTRY_REPORT.md` | |

### Modified (4 tracked)

| File | Change |
|---|---|
| `research_registry.json` | v1 → v2; 5 instruments × full metadata; forex licensing recorded |
| `researchguard.py` | `__all__` corrected; metadata validation invoked at load; `status: USED` written on consumption; duplicate status check consolidated |
| `dataset.py` | `identity=` binds declared timeframe to actual spacing |
| `dataset_identity.py` | `identity_covers()` removed as dead code |

Tracked total: 11 files, +368/−11. Untracked: 297.

---

## 4. Defects found and fixed

Phase 43's mandate was to audit; it found four real problems.

**1. `status`/`used` contradiction in the reservation writer.** Phase 45's schema
refused the registry's own output:

```
reservation 'ETH-2026-RESERVATION': status is RESERVED but 'used' is true.
A window cannot be both available and spent.
```

`_consume_reservations()` set `used: true` while leaving `status: "RESERVED"`.
Nothing checked this across Phases 39–41. **The writer was fixed, not the
validator relaxed** — the clearest evidence in this batch that making metadata
load-bearing surfaces defects that prose never did.

**2. Stale `__all__`.** Omitted `assert_series_permitted`,
`consume_reservation` and `candle_fingerprint`. Low impact, but `__all__` is
documentation too. Fixed with two tests pinning it.

**3. Declared timeframe was not bound to actual data.** A caller could declare
`1h` and validate 5-minute data by simply omitting `expected_interval_seconds`.
`identity_covers()` was written in Phase 41 to catch this and then never called.
Fixed: `validate_dataset(identity=…)` derives the interval from the declaration
and refuses contradictory arguments.

**4. Less actionable error message.** Two duplicate status checks meant a spent
window reported *"status is 'USED'"* instead of *"already been used"*.
Consolidated and reordered.

---

## 5. Remaining blockers

### Unresolved preregistration decisions (Phase 44)

None invented. Each blocks ETH evaluation:

| Decision | State |
|---|---|
| Research question | UNRESOLVED — Phase 38's draft not finalised |
| Configuration (frozen BTC vs re-derived) | UNRESOLVED — the two test different claims |
| Costs | PARTIAL — frozen costs exist; no bid/ask data, spread unmodellable |
| Execution assumptions | UNRESOLVED — undocumented for ETH |
| Thresholds and decision rules | UNRESOLVED — **deliberately not invented** |
| Uncertainty reporting | UNRESOLVED |
| Stopping rules | UNRESOLVED |
| Cross-asset authorization record | NOT CREATED — mechanism exists and is tested |

### Forex — BLOCKED on three independent grounds

1. No OHLC data (ECB gives one daily fixing, no high/low).
2. No session/holiday/DST validator.
3. No licensed tick or bar source.

Forex pairs are now *described* accurately in the registry — licence verified,
`blocker` stated — while remaining blocked. They are described, not absent.

### Documentation conflict — needs a human decision

Three readiness matrices disagree on ETH: Phase 37 says `INCOMPLETE`, Phase 41
says `NOT APPROVED`, Phase 42 says `BLOCKED`. BTC and forex agree across all
three. Left unresolved deliberately — picking one silently would edit history.

### Standing gaps

- Unregistered series permitted (unknowable to a registry that has never seen them).
- Sub-3-bar slices unmatched (inert; engine needs >22 bars to signal).
- `consume_reservation()` can be skipped by a careless caller (deliberate — a
  crashed attempt must not spend a window).
- `optional_market_data_key()` unused, reads `MARKET_DATA_API_KEY`. Flagged, not
  removed: whether an API-key hook belongs in a paper-only project is a
  judgement call.

---

## 6. ETH reservation state

```
status                     : RESERVED
used                       : False
preregistration_id         : None
used_on present            : False
registry research_approval : DATA_VERIFIED_NOT_RESEARCH_APPROVED
approved_preregistration_id: None
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

Unspent, unapproved, unmodified. **No ETH 2026 performance was computed,
inspected or revealed in any of Phases 43–45.**

---

## 7. Frozen hashes — 11 of 11 verified

| Artifact | SHA-256 | Result |
|---|---|---|
| BTC primary | `201a3b15…` | OK |
| Consumed BTC holdout | `c475e541…` | OK |
| Phase 29 preregistration | `b06f36e2…` | OK |
| ETH dataset | `7507c100…` | OK |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e2…` | OK |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741…` | OK |
| Phase 30 `RESULTS_trades.csv` | `174d5587…` | OK |
| Phase 30 `SUMMARY.md` | `9e3171b0…` | OK |
| Phase 33 `ACQUISITION_REPORT.md` | `bb446099…` | OK |
| Phase 34 `INDEPENDENT_AUDIT.md` | `e611ecdb…` | OK |
| Phase 35 `PROVENANCE_CORRECTION.md` | `ee704878…` | OK |

No baseline re-derived. Nothing silently updated.

---

## 8. Git state

```
branch            main
HEAD              dccebbd53ee8365474345506db9099b13356b53c
origin/main       dccebbd53ee8365474345506db9099b13356b53c
ahead / behind    0 / 0
staged            none
tracked modified  11 files, +368 / -11
untracked         297
```

No commit, stage, push, reset, clean or delete. No user file deleted or
overwritten.

---

## 9. Next permitted action

**Permitted:** drafting the ETH research question and preregistration — question,
configuration choice, costs, execution assumptions, thresholds, uncertainty
reporting, stopping rules — **without observing any result first**. That is
exactly what the process requires and what Phase 44 itemised.

**Explicitly prohibited:**

- Running any backtest, replay, or walk-forward against ETH 2026.
- Reading ETH 2026 performance in any form.
- Reusing any consumed BTC window.
- Tuning parameters on ETH data.
- Modifying the frozen BTC configuration so ETH data appears to be BTC.
- Setting thresholds or decision rules after observing results.
- Converting ECB reference rates into synthetic OHLC.
- Inventing forex session, holiday or DST rules.
- Approving any instrument in the registry.
- Staging, committing or pushing.

---

## 10. What this batch does not establish

2230 passing tests mean the registry refuses malformed metadata, the guards
refuse unauthorised evaluation, and the validator refuses malformed data.

They say nothing about profitability. No result in Phases 43–45 bears on that
question. The one pre-registered out-of-sample evaluation this project has run
returned a net profit factor of 0.4925 and was recorded as inconclusive, and
nothing since has changed that.

The ETH dataset remains the cleanest in the repository and its provenance is
Grade A. That is why it stays unapproved: what is missing is governance, not
data quality.

`BATCH 1 PHASES 43–45: PASS`