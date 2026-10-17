# Phase 46 Verification

**Date:** 2026-10-09

---

## 1. Commands and results

All from `research_engine/`. Pattern:

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
```

### Focused

| Command | Result | Duration |
|---|---|---|
| `pytest tests/test_data_pipeline.py` | **66 passed** | 1.4s |
| `pytest tests/test_registry_schema.py tests/test_research_gaps.py tests/test_dataset_validation.py` | 164 passed | 9.9s |
| `pytest tests/test_research_guard.py` | 97 passed | 1.0s |
| Combined: pipeline + registry + guard + validation | **328 passed** | 12.4s |

### Full suite

Per file, 25-minute cap each:

**2249 passed, 0 failed, 41 files.**

| File | Time | File | Time |
|---|---|---|---|
| test_acquisition | 1s | test_dataset_pipeline | 2s |
| test_analysis | 1s | test_entry_filters | 1s |
| test_api_account | 28s | test_entry_time_features | 44s |
| test_api_health | 12s | test_execution_model | 1s |
| test_api_market | 5s | test_execution_policy | 28s |
| test_api_replay | 25s | test_exit_rules | 1s |
| test_api_session | 21s | test_experiment | 1s |
| test_api_signal | 4s | test_high_risk | 527s |
| test_api_statistics | 15s | test_manual_paper | 50s |
| test_backtest | 1s | test_mode_contracts | 22s |
| test_config_request_policy | 62s | test_modes | 8s |
| test_daily_target | 46s | test_oos_dataset | 33s |
| test_dataset | 1s | test_phase14c_analysis | 189s |
| test_dataset_validation | 2s | test_phase15_checkpoint | 1s |
| test_registry_schema | 2s | test_replay | 155s |
| test_replay_lifecycle | 4s | test_research_gaps | 9s |
| test_research_gates | 1s | test_research_guard | 2s |
| test_robustness | 42s | test_simulator, test_strategy, test_validation_boundary | 1s each |
| test_windowstats | 12s | test_walkforward | 13s |
| test_yearly | 1s | | |

**No timeouts. No skips. No deletions. No xfail.**

Two slow files are pre-existing: `test_high_risk.py` (527s) and
`test_phase14c_analysis.py` (189s), both characterised against pristine `HEAD` in
Phases 40–41 and unchanged since.

---

## 2. Prohibited-workflow compliance

| Rule | Verification |
|---|---|
| No strategy backtest run | No `run_backtest`/`walk_forward` call in Phase 46 code or tests |
| No ETH 2026 performance computed or inspected | Two tests read the file for row count, endpoint timestamps and digest only |
| No consumed-window reuse | No evaluation performed at all |
| No parameter tuning | No `StrategyConfig` field touched |
| No fabricated data | ECB rates not converted to OHLC; no candle, spread or volume synthesised |
| No fabricated source metadata | `example.invalid` used for fixtures (reserved non-resolvable TLD) |
| No test weakened | Fixtures updated to satisfy a *stricter* schema; no assertion relaxed |
| No secrets in source | Phase 46 introduces no credential handling |

---

## 3. Forex blocking verified

Three refusal points, each tested:

```
DatasetIdentity(market_type='forex_reference_rates')  -> ValueError: no implemented validator
classify_intervals(market_type='forex_reference_rates') -> ValueError: requires session, holiday and DST knowledge
registry research_approval='RESEARCH_APPROVED' on a forex entry -> RegistryMetadataError: contradicts that
```

Plus `test_ecb_reference_rates_are_not_ohlc`: daily fixings fail hourly OHLCV
validation on interval grounds, so they cannot silently become candles.

---

## 4. Provenance behaviour verified

```
checksum verify        : verified
mismatch refused       : checksums differ -> archive quarantined, not parsed
missing file refused   : nothing downloaded
manifest tamper        : dataset digest changed ... file is <actual>
provenance ceiling     : A when all inputs publisher-verified, B otherwise
roundtrip byte-stable  : True
```

---

## 5. ETH reservation and frozen artifacts

```
status                     : RESERVED
used                       : False
preregistration_id         : None
research_approval          : DATA_VERIFIED_NOT_RESEARCH_APPROVED
dataset SHA-256            : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
rows                       : 24288
first / last timestamp     : 2024-01-01 00:00 / 2026-10-08 23:00
```

All 11 frozen artifact digests verified unchanged, compared against the exact
values recorded in earlier phases. No baseline re-derived.

---

## 6. Interpretation

2249 passing tests mean the pipeline refuses contradictory provenance, the
registry refuses malformed metadata, and the guards refuse unauthorised
evaluation.

They say nothing about profitability, and nothing in Phase 46 bears on that
question.