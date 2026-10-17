# Phase 41 Verification

**Date:** 2026-10-09

## 1. Commands run, with results

All commands run from `research_engine/`. Pattern for the full suite:

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

Executed per file so a slow file could not mask the rest. Per-file cap 25 min.

### Focused (run first, before any broader work)

| Command | Result | Duration |
|---|---|---|
| `pytest tests/test_dataset_validation.py` | **55 passed** | 1.2s |
| `pytest tests/test_research_gaps.py` | 37 passed | 8s |
| `pytest tests/test_research_guard.py` | 97 passed | 2s |
| `pytest tests/test_dataset.py tests/test_backtest.py tests/test_walkforward.py tests/test_acquisition.py` | 90 passed | 12s |

### Full suite, all 39 files

**2157 passed, 0 failed.**

| File | Time | File | Time |
|---|---|---|---|
| test_acquisition | 1s | test_manual_paper | 41s |
| test_analysis | 1s | test_mode_contracts | 23s |
| test_api_account | 26s | test_modes | 7s |
| test_api_health | 10s | test_oos_dataset | 37s |
| test_api_market | 5s | test_phase14c_analysis | 194s |
| test_api_replay | 24s | test_phase15_checkpoint | 1s |
| test_api_session | 17s | test_replay | 157s |
| test_api_signal | 4s | test_replay_lifecycle | 4s |
| test_api_statistics | 14s | test_research_gaps | 8s |
| test_backtest | 1s | test_research_gates | 1s |
| test_config_request_policy | 53s | test_research_guard | 2s |
| test_daily_target | 43s | test_robustness | 43s |
| test_dataset | 1s | test_simulator | 1s |
| test_dataset_validation | 2s | test_strategy | 1s |
| test_entry_filters | 1s | test_validation_boundary | 1s |
| test_entry_time_features | 46s | test_walkforward | 13s |
| test_execution_model | 2s | test_windowstats | 13s |
| test_execution_policy | 28s | test_yearly | 1s |
| test_exit_rules | 1s | test_experiment | 1s |
| test_high_risk | 521s | | |

No timeouts. No tests skipped, deleted or marked xfail.

Two files are slow by pre-existing design and were **not** re-baselined because
Phase 40 already established their character against pristine `HEAD`
(`test_high_risk.py`: 476s current vs 473s baseline in Phase 40; `test_replay.py`:
157s). Their cost is unchanged and unrelated to Phase 41.

---

## 2. Prohibited-workflow compliance

| Rule | How verified |
|---|---|
| No strategy backtest run | No `run_backtest` call in Phase 41 code or new tests |
| No ETH 2026 performance computed or inspected | `test_dataset_validation.py` contains no backtest, `analyze`, `create_report`, P&L or signal assertion |
| No reuse of consumed windows | No evaluation was run at all |
| No parameter tuning | No `StrategyConfig` field modified |
| No AI integration | None added |
| No fabricated data | Forex OHLC explicitly refused rather than synthesised |
| No test weakened to pass | Two allowlist entries added with written justification (Phase 40); no Phase 41 test was relaxed |
| No frozen artifact altered | §4 |

The two Phase 41 tests that read real datasets assert **structural** facts only:
row counts, endpoint timestamps, spacing, timezone naivety. No price value is
asserted anywhere.

---

## 3. Forex rejection verified

```
$ python -X utf8 -c "...identity_for_registry_entry(forex_entry)"
  EUR/USD   REFUSED: market_type 'forex_reference_rates' has no implemented valid...
  GBP/USD   REFUSED: ...
  USD/JPY   REFUSED: ...
```

```
$ classify_intervals(rows, expected_interval_seconds=3600, market_type="forex_reference_rates")
  ValueError: interval classification is implemented for 24x7 crypto spot only;
  classifying a gap in a forex series requires session, holiday and DST knowledge
  that this repository does not have.
```

Three separate refusal points: identity construction, `validate_dataset`, and
interval classification. Forex cannot be evaluated by any supported path.

---

## 4. Frozen artifacts

| Artifact | SHA-256 | Status |
|---|---|---|
| BTC primary | `201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b` | unchanged |
| BTC holdout (spent) | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` | unchanged |
| Phase 29 preregistration | `b06f36e21df0fe403e3a75cbf8c3de84161607348966d622b65ea3f51bf217cc` | unchanged |
| ETH dataset | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` | unchanged |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e29ea7c6a8…` | unchanged |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741a7dbab8f…` | unchanged |
| Phase 30 `RESULTS_trades.csv` | `174d558719f31067…` | unchanged |
| Phase 30 `SUMMARY.md` | `9e3171b08555e06b…` | unchanged |

Phase 30 digests were re-read from the repository's own files and matched
against the values recorded in the Phase 39 report — not re-baselined.

---

## 5. ETH reservation state

```
status            = RESERVED
used              = False
preregistration_id= None
used_on present   = False
```

Unspent and unapproved.

---

## 6. Git

```
branch   main
HEAD     dccebbd53ee8365474345506db9099b13356b53c
origin   dccebbd53ee8365474345506db9099b13356b53c
ahead/behind  0 / 0
staged    none
```

Phase 41 tracked modifications: `data.py`, `dataset.py`.
New untracked: `dataset_identity.py`, `intervals.py`, `test_dataset_validation.py`,
`experiments/phase41/`.

No commit, stage, push, reset, clean or delete.

---

## 7. Interpretation

2157 passing tests mean the validator refuses malformed input and the research
guards refuse unauthorised evaluation. They say nothing about whether the
strategy is profitable, and no result in this phase bears on that question.