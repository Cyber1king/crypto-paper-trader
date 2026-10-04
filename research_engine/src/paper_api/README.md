# Paper-Trading API — Phase 16A

A local HTTP API in front of the `crypto_paper_lab` research engine.

**Paper trading only.** No exchange connectivity, no order submission, no
wallet, no deposits or withdrawals, no leverage, no margin. There is no
credential handling anywhere in this package.

## Scope

Phase 16A — liveness:

```
GET /healthz  ->  {"status": "ok", "service": "crypto-paper-lab"}
```

Phase 16B — paper-session state:

```
GET /api/session  ->  account + strategy/execution identity
```

`/api/session` is **read-only**. It reports:

- `service`, `session_id`, `mode` (always `"paper"`), `state`, `active`
- `account` — `starting_balance`, `balance`, `realized_pnl`, `trade_count`
- `strategy` — `config_repr` and `config_hash` of the frozen baseline config
- `execution` — `execution_model`, `fee_rate`, `slippage_rate`,
  `spread_rate`, `costs_repr`, `costs_hash`, `risk_fraction`
- `has_open_position`, `open_position`

Every figure is **read** from `crypto_paper_lab`. The API computes no balance,
no P&L and no position. `starting_balance` is
`walkforward.STARTING_BALANCE` = 10,000.0 — not the dashboard mock's 100,000.

Phase 16C — historical market data:

```
GET /api/market?start=&end=&limit=
```

Read-only OHLCV slices from the frozen research dataset
(`data/BTCUSDT_1h_Cleaned (1).csv`, 17,544 candles, 2024-01-01 → 2025-12-31,
UTC). Served through the engine's own `dataset.load_dataset` and verified with
`walkforward.validate_dataset_integrity` (SHA-256, count, bounds, strict
ordering, exact 1h spacing). **Loaded once per API process** and cached; the
cache returns a tuple of frozen `Candle` objects, so mutation is impossible.

Query parameters:

| Parameter | Default | Meaning |
|---|---|---|
| `start` | none | Inclusive lower bound on bar time |
| `end` | none | Inclusive upper bound on bar time |
| `limit` | `200` | Max candles, `1`–`5000` |

- Bounds accept a naive timestamp (read as UTC) or an offset-aware one
  (converted to UTC). No local-time conversion anywhere.
- Malformed timestamps → `422`. `start > end` → `422`. `limit` outside
  `1..5000` → `422`.
- Source ordering is always preserved (chronological ascending).
- **Truncation keeps the most recent `limit` matches**, not the first. So
  `start=2025-03-01&limit=3` returns the three most recent candles *from* that
  date, not the first three. Bound `end` as well to pin a historical window.
  `metadata.truncated` reports when this happened.
- With no dates, the response is a bounded **recent** slice — never all 17,544.
- No filesystem path is ever exposed; the dataset is identified by its
  SHA-256 and a `local-research-dataset` label.

Deliberately **absent** from `/api/session`, because Phase 16B has no data
source and no execution and therefore cannot derive them (see
`session.UNSUPPORTED_FIELDS`):

`replay_index` · `current_candle` · `last_signal` · `bars_processed` ·
`dataset_id` · `total_candles` · `unrealized_pnl` · `equity` ·
`available_balance` · `reserved_capital` · `statistics`

`available_balance` and `reserved_capital` are omitted on purpose: the engine
has no margin concept, so there is no authoritative value to report, and
inventing `0.0` would assert something the engine does not know.

Phase 16D — strategy signal:

```
GET /api/signal?at=<optional exact bar time>
```

Read-only research signal from `crypto_paper_lab.strategy.analyze`. Reports
every field of the engine's `Signal` model verbatim, plus the strategy
`config_hash` and the source `dataset_sha256`.

- `signal` is the engine's `Signal.side` **verbatim and lowercase**
  (`long` / `short` / `flat`). Uppercase `LONG`/`SHORT`/`FLAT` is a display
  concern for React, not a value this API invents.
- `timestamp` is the **signal candle** — the latest *completed* bar the
  strategy evaluated. It is not a fill: no execution occurs, and in the
  walk-forward harness a signal for this bar would be filled at the **next**
  candle's open.
- Causality: the endpoint evaluates `analyze(candles[:index + 1])`, so nothing
  after the signal bar is reachable by the strategy. The one-candle gap is
  preserved exactly.
- `at` must match a bar **exactly**. Between bars → `404`. Malformed → `422`.
  A valid bar before the strategy has 22 candles of history → `422`. Nothing is
  ever interpolated.
- Minimum history is `max(lookback + 2, slow_period)` = **22** for the frozen
  baseline, derived from the config rather than hard-coded.
- Strategy config is `walkforward.baseline_config()`, the Phase 13 Pass A
  configuration. `config_hash` = `2FBDB9A8…ADC3BF7`, matching the frozen
  Phase 13 record. A2 is **not** used.
- **No `confidence`, probability, expected-return or price-forecast field
  exists.** The engine defines no such quantity, so any value would be
  fabricated. The dashboard mock's `confidence` and its canned rationale text
  have no authoritative source and are deliberately not reproduced.
- `realised_volatility` is not annualised; `mean_range` is not ATR.
- `breakout_distance` / `retest_distance` are `null` when not applicable —
  never zero-filled.

Phase 16E — account, position and trade history (all read-only):

```
GET /api/account   ->  starting_balance, balance, realized_pnl, trade_count
GET /api/position  ->  { has_position: false, position: null }   when flat
GET /api/trades    ->  { trades: [], trade_count: 0 }           when empty
```

Every value is read from `PaperBroker`. `balance` is `broker.cash`;
`realized_pnl` is `balance - starting_balance`, the engine's own
`BacktestResult.net_pnl` definition, computed in exactly one place so
`/api/session` and `/api/account` cannot disagree.

Not exposed, because the engine represents none of them: `available_balance`,
`reserved_capital`, `equity`, `unrealized_pnl`, `margin`, `buying_power`,
`notional`, `leverage`.

**`/api/position` deliberately omits cost fields and `bars_held`.** For an open
trade the broker has not computed them — `costs`, `fee_total`, `slippage_total`,
`spread_total` are `0.0` dataclass defaults and `bars_held` is `0` — so
reporting them would claim an open trade cost nothing and was held zero bars.
They are all computed by `close()` and appear in `/api/trades`. There is also
no mark price and no unrealized P&L: the engine has no live price feed.

`/api/trades` returns `PaperBroker.journal` verbatim in the broker's own
append order (chronological by entry). No re-sorting, no pagination — the
journal is small and re-ordering would be a transformation the engine never
asked for. `pnl`, `net_pnl` and `total_friction` are the engine's own
`PaperTrade` properties, read from the dataclass and never recomputed.

Phase 16F — closed-trade statistics (read-only):

```
GET /api/statistics  ->  basis, trades, net_pnl, win_rate, profit_factor,
                         profit_factor_infinite, average_pnl, max_drawdown,
                         ending_balance, costs{...}, strategy, execution
```

Every figure is a return value of `crypto_paper_lab.stats.performance` or
`stats.cost_breakdown`. The module `paper_api/perfstats.py` exists only so
`app.py` stays a pure serialiser; it calls those two functions and nothing else.

`basis` is always `"closed_trades"`. That is not decoration —
`stats.performance` excludes unrealized P&L by construction, so this is a
closed-trades view, not a live equity curve.

### One deliberate transformation: `Infinity` is not valid JSON

`stats.performance` returns `float("inf")` whenever `gross_loss == 0`. `json.dumps`
emits that as a bare `Infinity` token, which `JSON.parse` rejects — a 200
response that no client can read. So:

```json
{ "profit_factor": null, "profit_factor_infinite": true }
```

Substituting a large finite number would fabricate a statistic, so the flag
travels with the value and the UI renders "∞ (no losing trades)". Note the flag
is also `true` for an empty journal, where the ratio is *vacuous* rather than
exceptional.

### Two totals that differ in the last bits

`/api/account` reports `broker.cash - broker.starting_balance`. `/api/statistics`
reports `stats.performance`'s `net_pnl`, a sum accumulated from `0.0`. These are
the same quantity by two different accumulation orders, so they can differ by
about one ULP (~1e-13 relative, measured). Both are reported from their own
engine function; forcing bit equality would mean the API overriding one engine
function with another, which is the duplication this package exists to prevent.
Compare them with a tolerance, not `==`.

### Conventions the client must honour

- `max_drawdown` is a **fraction**, not a percentage (`0.0017` = 0.17%).
- `win_rate` is a **fraction**, not a percentage.
- `max_drawdown` is the **realized** drawdown over closed trades, not
  mark-to-market. The two differ by construction and must never share a label.
- `ending_balance` is realized cash only; it includes no unrealized amount.

Not exposed, because the engine defines none: `sharpe_ratio`, `sortino_ratio`,
`calmar_ratio`, `recovery_factor`, any bootstrap confidence interval, monthly
breakdown and concentration analysis. Reasons are recorded in
`paper_api.perfstats.UNSUPPORTED_METRICS`.

Still not implemented: replay,
`/api/trades`, `/api/statistics`, `/api/replay/*`, order submission,
persistence, live data, and any dashboard wiring.

## Not in this phase

Deliberately absent, so nobody mistakes the absence for an oversight:
`/api/signal`, `/api/position`, `/api/account`, `/api/trades`,
`/api/statistics`, `/api/replay/*`, order submission, persistence, live data,
and any dashboard wiring.

## Architecture rules this package obeys

- The research engine (`crypto_paper_lab`) is the **single source of truth**
  for strategy, sizing, execution, fills, fees, slippage, spread, P&L and
  accounting.
- The dependency is **one-way and enumerated**: `crypto_paper_lab` never
  imports `paper_api`, and `paper_api` imports only the modules listed in
  `ALLOWED_ENGINE_IMPORTS` in `tests/test_api_health.py` — `simulator`,
  `walkforward`, `strategy`, `costs`. Reaching into engine internals such as
  `indicators` or `backtest` would couple the transport layer to
  implementation detail, and a test enforces it.
- The API computes **no trading value of its own**.
- **Localhost only.** The bind address is validated at construction; a
  non-loopback host raises `UnsafeBindError` rather than starting.
- **No CORS middleware**, so no wildcard — in fact no cross-origin access.
- Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are disabled.

## Running it

From `research_engine/`:

```bash
python -m uvicorn paper_api.app:app --host 127.0.0.1 --port 8000
```

Then:

```bash
curl http://127.0.0.1:8000/healthz
```

```json
{"status":"ok","service":"crypto-paper-lab"}
```

Press `Ctrl+C` to stop.

### Configuration

Optional, via environment variables (documented in `.env.example`; a real
`.env` is git-ignored and must not be committed):

| Variable | Default | Meaning |
|---|---|---|
| `PAPER_API_HOST` | `127.0.0.1` | Bind address. Loopback values only. |
| `PAPER_API_PORT` | `8000` | Bind port. |

Both are optional — the defaults are correct for local use, so the command
above works with no configuration at all. When `--host` / `--port` are passed
to uvicorn they override the application config, so pass
`--host 127.0.0.1` explicitly; uvicorn's own default is `0.0.0.0`, which this
service must never bind.

No secret, token or API key is read from the environment.
`MARKET_DATA_API_KEY` exists elsewhere for a future *public* price-data
provider and is deliberately not consumed here.

## Tests

```bash
cd research_engine
python -m pytest tests/test_api_health.py -q
```

## Not in this phase

Deliberately absent, so nobody mistakes the absence for an oversight:
`/api/session`, `/api/market`, `/api/signal`, `/api/position`, `/api/account`,
`/api/trades`, `/api/statistics`, `/api/replay/*`, order submission,
persistence, live data, and any dashboard wiring.