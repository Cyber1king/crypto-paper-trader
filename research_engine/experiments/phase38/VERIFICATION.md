# Phase 38 — Verification

**Phase type: planning and read-only inspection.** No backtest, simulation or
performance calculation; no ETH 2026 performance inspected; no strategy tuned;
no source code, dataset, manifest or frozen artifact modified; no data
downloaded; no AI integrated; nothing staged, committed or pushed.

---

## 1. Integrity constraints — confirmation

| Restriction | Status |
|---|---|
| No backtests or simulations | **Held** — no `run_backtest`, `analyze`, `walk_forward` or `run_window` call |
| No performance calculations | **Held** — no P&L, win rate, profit factor, drawdown or trade count computed for ETH |
| ETH 2026 performance not inspected | **Held** — its only property touched is its timestamp boundary |
| No strategy tuning | **Held** — no parameter read for selection, altered or proposed |
| No source-code modification | **Held** — 0 tracked files modified |
| No dataset / manifest modification | **Held** — digests re-verified below |
| No frozen-artifact modification | **Held** |
| No data downloaded | **Held** |
| No AI integrated | **Held** |
| No stage, commit or push | **Held** |
| Reserved-window source unchanged | **Held** — verified below |

**The test suite was deliberately not executed.** `test_walkforward.py`,
`test_oos_dataset.py` and others run backtests internally, so executing the
suite would breach the no-backtest constraint. Tests were **inspected** (source
read, function names and coverage enumerated) and that inspection is reported.

---

## 2. Reserved-window source data — verified unchanged

| Property | Value |
|---|---|
| Dataset | `research_engine/data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Result | **MATCH** |

Other artefacts re-verified this phase:

| Artefact | Status |
|---|---|
| `data/BTCUSDT_1h_Cleaned (1).csv` (`201a3b15…`) | unchanged |
| `data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` — **spent holdout** (`c475e541…`) | unchanged |
| `data/phase33/ecb_reference_rates_daily_20240101_20261008.csv` (`030b48e2…`) | unchanged |
| `experiments/phase29/PREREGISTRATION.md` (`b06f36e2…`) | unchanged |
| `experiments/phase30/` — all 4 result files | unchanged |
| Phase 33 manifests, 41 provenance sidecars | unchanged |

---

## 3. Inspection performed this phase

### 3.1 ETH evaluation boundary — computed, not assumed

```
index of first bar with timestamp >= 2026-01-01 00:00  ->  17,544
warm-up   : indices 0..17,543   2024-01-01 00:00 .. 2025-12-31 23:00   17,544 bars
evaluation: indices 17,544..24,287  2026-01-01 00:00 .. 2026-10-08 23:00    6,744 bars
```

`evaluation_start` would therefore be **17,544**.

### 3.2 Enforcement surface

| Finding | Evidence |
|---|---|
| `run_backtest` performs **no** hash, registry, consumption or reservation check | no `sha256`/`consumed`/`reservation`/`registry` reference in `backtest.py` |
| `normalize_source`'s only anti-reuse guard is hard-coded 2024–2025 | `acquisition.py:54-55`, `:396-399` |
| That guard is bypassable by a keyword argument | `allow_overlap_with_research: bool = False` (`acquisition.py:318`) |
| `consumed_windows` does not exist in code | no registry module anywhere |
| `evaluation_start` correctly gates **entries only** | `backtest.py:199` |
| **Nine** dataset entry points can move data into a backtest | enumerated, incl. `paper_api/marketdata.load_research_candles:61` |

### 3.3 Validation coverage

`dataset.validate_dataset` has exactly **6** assertions (`dataset.py:33-72`),
read directly. Test files inspected, **not run**: `test_dataset.py` (3 test
functions), `test_acquisition.py` (27), `test_walkforward.py` (58),
`test_oos_dataset.py` (18), `test_validation_boundary.py` (13). **No test
anywhere covers instrument/timeframe identity or volume semantics.**

---

## 4. Findings

### F1 — the reserved window is not technically protected

No code prevents a second run of the ETH 2026 window or of the spent BTC
holdout. Protection is documentary. This is stated prominently at the top of
`HOLDOUT_ENFORCEMENT_DESIGN.md`.

### F2 — a silent-bypass trap is already present in the codebase

`normalize_source(..., allow_overlap_with_research=True)` **skips** the guard and
leaves `report.overlapping_rows == []`.

Verified in the Phase 33 ETH log: **all 41 archives record
`overlapping_rows: []`** — yet ETH 2024–2025 shares **17,544 bars** with the
consumed BTC research window.

**An empty list is ambiguous**: it means either "checked, none found" or "check
disabled". A reader of the machine-readable log would conclude no overlap exists.
It does.

Phase 33's call was **correct** — different instrument, so the guard should not
apply — and the manifest does disclose the overlap in §4. But the *log* does not,
and the log is what tooling reads. Recorded as a design requirement
(`DATA_VALIDATION_DESIGN.md` §2.9).

### F3 — the strategy would run ETH without complaint

`StrategyConfig.asset` is a label; the only non-declaration reference is
`replay.py:363`. The strategy is scale-invariant. An ETH dataset labelled
BTC/USDT would load and run with no error and no warning.

**This creates a genuine tension** recorded in `DATA_VALIDATION_DESIGN.md` §2.4
(V4.5): enforcing asset–dataset identity would **block the ETH experiment as
currently drafted**, because the frozen config declares `"BTC/USDT"`. That must
be decided explicitly, not bypassed with a flag.

### F4 — `walkforward.validate_dataset_integrity` cannot validate ETH

Its defaults are pinned to the BTC 2024–2025 constants (`walkforward.py:51-57`,
`:257-262`). Reused as-is it would reject a correct ETH dataset.

### F5 — `validate_dataset` accepts an all-zero price row

`0,0,0,0` satisfies `high >= low` and both containment checks. `acquisition`
enforces positivity; the `project_native` load path does not.

---

## 5. Files created (4, all new, all under `experiments/phase38/`)

| File | Purpose |
|---|---|
| `ETH_RESEARCH_PROTOCOL_DRAFT.md` | Research question, partition, frozen config, metrics, unresolved thresholds |
| `HOLDOUT_ENFORCEMENT_DESIGN.md` | Reservation record, invalidation conditions, guard placement, fail-closed rules |
| `DATA_VALIDATION_DESIGN.md` | Nine safeguard groups, coverage analysis, priorities |
| `VERIFICATION.md` | This file |

**No other file was created, modified, renamed, moved or deleted.**

---

## 6. Git state — exact

| Field | Value |
|---|---|
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Branch | `main` |
| `origin/main` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Modified tracked files | **0** |
| Deleted tracked files | **0** |
| Staged files | **0** |
| Commits ahead of `origin/main` | **0** |
| Commits or pushes performed | **none** |
| Untracked before this phase | **271** |
| Untracked after this phase | **275** (+4, all under `experiments/phase38/`) |

---

## 7. Unresolved limitations

| # | Limitation |
|---|---|
| L1 | **No ETH trade count exists.** Whether 6,744 evaluation bars clear the ~50-trade floor is **unknown**. T2/T3 in the protocol must be decided **before** a run, never after seeing it |
| L2 | **No enforcement mechanism exists.** Every safeguard is a specification. The reserved window remains technically unprotected |
| L3 | **Thresholds T1–T6 are deliberately unset.** Inventing them now would encode a preference before data exists |
| L4 | The test suite was **not executed** — coverage was assessed by reading source, so no safeguard was empirically confirmed exploitable |
| L5 | Asset-identity enforcement is **in tension** with the drafted ETH protocol (F3); unresolved by design |
| L6 | The Phase 37 forex and BTC blockers are unchanged: no FX OHLC exists, and no untouched BTC data is published |
| L7 | This phase established **readiness and protection design**. Neither authorises evaluation, and neither alters the standing conclusion: no reliable profitability has been established |

---

## 8. Outcome

The ETH research scope is now formally drafted with an explicit disclosure that
the configuration is BTC-derived and that ETH 2024–2025 is warm-up context, not a
clean development set. The 2026 window is specified precisely — boundary index
17,544, 6,744 evaluation bars — and **is not yet protected**.

Three findings warrant attention before any evaluation is contemplated: the
window is unprotected (F1), a silent-bypass trap makes anti-reuse signals
ambiguous (F2), and the engine would run ETH without complaint (F3).

**A successful integrity audit does not automatically authorise evaluation.**

`PHASE 38 RESEARCH PROTOCOL` companion documents:
`ETH_RESEARCH_PROTOCOL_DRAFT.md`, `HOLDOUT_ENFORCEMENT_DESIGN.md`,
`DATA_VALIDATION_DESIGN.md`.