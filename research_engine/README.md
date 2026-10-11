# Crypto Paper Lab — Python Research Engine

A small, dependency-light foundation for learning about BTC/USDT market analysis and paper-trading strategy research.

> **Paper trading only.** This package has no exchange account integration, no authenticated trading client, and no order execution or financial transaction capability. Signals and trades are simulations, not financial advice.

## Included

- Historical OHLCV CSV loading
- Simple moving-average trend detection
- Rolling support and resistance
- Breakout and retest signal logic
- In-memory paper trade simulation and journal
- Win rate, net P&L, average P&L, and profit factor
- Configurable asset, timeframe, lookback, and strategy thresholds
- Unit tests for core strategy and simulator behavior

## Data format

Provide a CSV with these headers:

```csv
timestamp,open,high,low,close,volume
2026-01-01T00:00:00+00:00,93000,93500,92500,93200,125.4
```

`load_ohlcv_csv()` reads local historical data. A future public market-data adapter may use `MARKET_DATA_API_KEY`, but the system must never accept exchange trading credentials.

## Setup

```bash
cd research_engine
python -m pip install -e ".[dev]"
cp .env.example .env
```

Do **not** run bare `pytest` here. See [Research safety and the excluded
evaluation set](#research-safety-and-the-excluded-evaluation-set) below for the
safe command and the reason.

Keep `.env` out of version control. Never print API keys or commit them to source.

## Example

```python
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.strategy import StrategyConfig, analyze

candles = load_ohlcv_csv("data/BTCUSDT_1h.csv")
signal = analyze(candles, StrategyConfig(asset="BTC/USDT", timeframe="1h"))
print(signal)
```

## Data and licensing

This repository **ships market data**, so the following applies.

### Market data — Binance Vision

Historical OHLCV files under `data/` and `data/oos/`, and the raw archives under
`data/oos/raw/*.zip`, originate from **Binance Vision** (<https://data.binance.vision>).

Binance Vision data is provided under **CC BY-NC-SA 4.0** together with the
[Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
(version 1.0, last updated 26 August 2026). Permitted uses include academic
research, non-monetised open educational projects and **algorithmic historical
backtesting for personal, non-production research**. Commercial use is excluded.

Attribution to Binance Vision is required on redistribution, and redistributed
derivative works must remain under CC BY-NC-SA 4.0.

Normalised CSVs in this repository are derivative works of that data. Each raw
archive carries a `.provenance.txt` sidecar recording the source URL, the
published `.CHECKSUM`, the retrieval date and the local SHA-256, together with
the licence statement reproduced from the Dataset Terms.

### Tooling — no licence granted

**No licence is granted for this software.** There is deliberately no `LICENSE`
file and no licence field in `pyproject.toml`; absent a licence, the code is
all-rights-reserved. The `"license": "MIT"` field in the repository-root
`package.json` applies to the npm workspace packages (`artifacts/`, `lib/`,
`scripts`) and **not** to this Python package.

A root-level MIT field cannot be read as covering `data/`: Binance Vision data is
CC BY-NC-SA 4.0 and is **not** MIT, and mixing an MIT claim over
non-commercial share-alike data would misstate both.

### Restrictions that bind this project

Non-commercial only. No live or proprietary trading execution, no signal
distribution for compensation, no integration into a commercial product, paid
newsletter or commercial trading-bot platform. Commercial use would require a
separate written enterprise data licence from Binance and is out of scope for
this project.

Note also that reference rates elsewhere in this project (if any) are **not**
converted into synthetic OHLC; no candle is ever fabricated from a rate.

See `experiments/phase53/LICENCE_REMEDIATION_PLAN.md` for the full audit.

## Research safety and the excluded evaluation set

This repository holds a **preregistered reservation** that must not be evaluated
until it is formally released. Read this before running the test suite.

### The reservation

`data/research_registry.json` reserves one series:

| Field | Value |
|---|---|
| Instrument | `ETH/USDT` |
| Dataset | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Status | `RESERVED`, `used=false`, `preregistration_id=null` |

Evaluating that series would spend a one-shot research result and destroy the
value of holding it back. `crypto_paper_lab.researchguard` enforces this at
runtime: any evaluation entry point called without an approved research context
refuses a reserved series before a strategy state exists.

The dataset is **deliberately not tracked in Git**. It is a large research
artifact with unresolved redistribution terms, so it is obtained separately.

### Why bare `pytest` is unsafe

A static call-graph audit found **1,087 test records** whose execution paths
reach a forbidden evaluation entry point — `run_backtest`, `Replay`,
`run_experiment`, `run_yearly_backtests`, `walk_forward` and friends. Five of
them touch the reserved ETH series. The audit is recorded in
`experiments/phase101/excluded_test_audit.json` and is regenerated, never
hand-edited.

`pytest` with no arguments collects all 63 test files, which includes those
records. The names look ordinary, so nothing warns you. **There is no
`conftest.py`, no marker and no default deselection protecting you** — the
exclusion is a convention, not a mechanism.

### The safe procedure

Run only test files with **zero excluded records** — at the time of writing, 34
of the 63 files. Derive that list from the audit rather than transcribing it:

```bash
cd research_engine
python - <<'PY'
import json, pathlib
audit = json.loads(
    pathlib.Path("experiments/phase101/excluded_test_audit.json").read_text()
)
blocked = {r["file"] for r in audit["tests"]}
for p in sorted(pathlib.Path("tests").glob("test_*.py")):
    if p.stem not in blocked:
        print(p.as_posix())
PY
```

Then deselect the fourteen tests that read the untracked dataset. This list was
established by running the safe set in a checkout where `data/phase33/` is
absent and collecting every `FileNotFoundError`, **not** by grepping for `data/`
— several of these resolve their path from the registry entry or from a fixture,
so a text search misses them:

```bash
python -m pytest $(python - <<'PY'
import json, pathlib
a = json.loads(pathlib.Path("experiments/phase101/excluded_test_audit.json").read_text())
blocked = {r["file"] for r in a["tests"]}
print(" ".join(p.as_posix() for p in sorted(pathlib.Path("tests").glob("test_*.py"))
                if p.stem not in blocked))
PY
) \
  --deselect tests/test_registry_locking.py::test_real_eth_reservation_untouched \
  --deselect tests/test_crash_recovery.py::test_real_eth_reservation_untouched_by_crash_testing \
  --deselect tests/test_cross_process_guard.py::test_real_eth_reservation_untouched_by_all_cross_process_work \
  --deselect tests/test_reservation_single_use.py::test_real_eth_reservation_is_never_touched_by_this_module \
  --deselect tests/test_registry_schema.py::test_shipped_eth_dataset_still_validates \
  --deselect tests/test_registry_schema.py::test_eth_dataset_hash_unchanged \
  --deselect tests/test_registry_schema.py::test_reserved_series_still_refused_without_context \
  --deselect tests/test_dataset_validation.py::test_real_datasets_still_validate \
  --deselect tests/test_dataset_validation.py::test_eth_dataset_row_count_unchanged \
  --deselect tests/test_data_pipeline.py::test_eth_dataset_still_validates_structurally \
  --deselect tests/test_data_pipeline.py::test_eth_dataset_hash_unchanged \
  --deselect tests/test_data_pipeline.py::test_reserved_series_still_refused_without_context \
  --deselect tests/test_phase15_checkpoint.py::test_recorded_dataset_digests_match \
  --deselect tests/test_phase15_checkpoint.py::test_recorded_candle_counts_match_the_datasets \
  -q
```

Points worth keeping:

* **Deselect by exact node ID, never by `-k`.** A name filter is shorter and
  wrong: `test_reserved_series_still_refused_without_context` does not mention
  ETH in its name, so `-k "not eth"` would let it run — and the same test name
  exists in three different files, so the node ID must include the file.
* **Deselecting the function name also removes its parametrized instances**,
  which is why `test_real_datasets_still_validate` needs no `[...]` suffix.
* **A missing deselect is loud, not silent.** It fails with `FileNotFoundError`
  for the absent dataset, never with a research-safety error. If a run reports
  `FileNotFoundError` under `data/`, add that node ID and rerun. Re-verify the
  list whenever the suite changes.
* **Never substitute a bare `pytest`, and never widen CI to `pytest tests/`.**

### Continuous integration

`.github/workflows/reservation-locking.yml` runs a deliberately narrow
allowlist of five files. Before pytest it executes a preflight that walks those
files' imports transitively and refuses to run if any reachable source calls a
forbidden entry point. The job fails closed on an empty allowlist, an
unresolved import, or an unparseable file.

The workflow must never be widened to `pytest tests/`.

### What is deliberately not covered

* Reserved-window evaluation, backtests, walk-forward runs, optimization and
  performance analysis on the reserved series.
* Any live exchange, AI provider or news service.
* Browser rendering — no browser automation is installed, so the dashboard is
  verified through typecheck, jsdom tests and the production build only.

## Scope

The initial version intentionally avoids live feeds, databases, optimization frameworks, machine learning, leverage, and exchange connectivity. Those are not required to study deterministic strategy logic safely.