# Paper-Trading Integration Plan — Python ↔ React

**Design and interface contract only.** No integration was implemented. No
source code, dataset, or Phase 10–15 artifact was modified. No API or UI
implementation file was created. Nothing was committed or pushed.

Prepared at commit `25bd7d0ab651e356240d8148525fb664938562b0` (working tree
dirty from Phase 14B/14C/15 work).

---

## 1. What I verified before designing

I did not take the architecture audit on trust. Every claim below was
re-checked against source, and three new findings emerged that materially
affect the contract.

### 1.1 Audit claims confirmed

| Claim | Verified at |
|---|---|
| Mock candles from trigonometry | `mock-data.ts:generateCandles` — `Math.sin`/`Math.cos` of `time` |
| Random, non-reproducible signals | `signals.ts:generateSignal` — `Math.sin(Date.now() / 10000)` |
| Different strategy | `analysis.ts` SMA20 on closes, `support = min(close)`; vs `strategy.py` 5/12 MA, `min(low)`/`max(high)` |
| Different accounting model | `usePaperEngine.ts` subtracts `size` from balance on entry; `simulator.py` never debits at entry |
| No costs in the mock | `usePaperEngine.ts` has no fee, slippage or spread term |
| Starting balance 100,000 | `usePaperEngine.ts:26` — `useState(100000)` vs `STARTING_BALANCE = 10_000.0` |
| Multiple concurrent positions | `usePaperEngine.ts:66` — `setPositions(p => [...p, pos])` vs `simulator.py:79` raising |
| No bridge to Python | grep for `localhost`, `fastapi`, `flask`, `uvicorn`, `subprocess`, `python` across `artifacts/*/src` and `lib/*/src` → no matches |
| API has only `/healthz` | `api-server/src/routes/index.ts` registers `healthRouter` alone |
| `lib/db` schema empty | `lib/db/src/schema/index.ts` is `export {}` |
| No Python persistence | grep for pickle/sqlite/`save_state`/`json.dump` in `crypto_paper_lab` → no hits |

### 1.2 New findings that change the contract

These were not in the audit and each one would have caused a defect.

**N1 — `stats.performance` can return `float("inf")`.**
`stats.py:139-143` returns `gross_profit / gross_loss if gross_loss else
float("inf")`. A session with no losing trades yields `Infinity`, which
`json.dumps` emits as bare `Infinity` — **invalid JSON** that `JSON.parse`
rejects. The Statistics contract must handle this explicitly (§4.8).

**N2 — orval folds `baseUrl: "/api"` into generated URLs.**
`orval.config.ts` sets `baseUrl: "/api"`, and the generated
`getHealthCheckUrl()` returns `/api/healthz` even though `openapi.yaml` declares
the path as `/healthz`. So **OpenAPI paths must be declared relative**
(`/session`, not `/api/session`), or every generated client URL will be
doubly prefixed. Easy trap; §4 states the convention.

**N3 — the existing UI reads two fields Python does not produce.**
`dashboard.tsx` consumes `analysis.sma20` and `signal.confidence`. Neither
exists in the engine: `indicators.trend()` returns only a string and never
exposes its moving averages, and there is no confidence concept anywhere.
`indicators.simple_moving_average` *does* exist as a public function, so
`sma20` is servable as an explicitly display-only value. `confidence` has no
source at all and must be removed from the UI rather than invented (§4.5,
§8).

**N4 — `analysis.sma20` would be a *different* moving average from the
strategy's.** The mock uses SMA20; the strategy uses a 5/12 pair. Serving
`sma20` from Python is safe for display, but the UI must not imply it drives
the signal.

### 1.3 Also confirmed

- `custom-fetch.ts` declares `DEFAULT_JSON_ACCEPT = "application/json,
  application/problem+json"` and exports an `ApiError` carrying `status`,
  `statusText`, `data`, `headers`. The error contract should therefore be
  **RFC 7807 problem details**, which this client already accepts.
- `custom-fetch.ts` also exports `AuthTokenGetter`. **It must not be
  configured.** Noted in §12.
- orval zod output sets `useDates: true` and coerces `date-time` on responses,
  so `format: date-time` in the spec becomes a JS `Date` in the client.
- `orval.config.ts` sets `clean: true`, so regenerating **deletes and rewrites**
  `lib/api-client-react/src/generated/`. Expected, but worth knowing.
- `trend()` returns a plain string; there is no accessor for `fast_ma` /
  `slow_ma`.

---

## 2. System boundary

### 2.1 Layer diagram

```
 Historical / replay data            (frozen CSV, read-only)
        |
        v
 Python market-data adapter          NEW  — MarketDataSource
        |  list[Candle]
        v
 Python PaperSession                 NEW  — owns the replay loop
        |
        +--> strategy.analyze(candles[:i], config)   EXISTING, UNCHANGED
        |      |
        |      |  Signal(side, price, reason, support, resistance, trend, +6)
        |      v
        +--> replace(signal, price=candles[i].open)  EXISTING pattern
        |      |
        |      v
        +--> PaperBroker.open_from_signal(...)       EXISTING, UNCHANGED
        |      |  PaperBroker.close(price, ts)       EXISTING, UNCHANGED
        |      v
        +--> paper account state                     NEW read model
        |      cash / open_trade / journal
        v
 Python local API                    NEW  — read-mostly HTTP, localhost only
        |  JSON, RFC 7807 errors
        v
 React API client                    orval-generated, from one OpenAPI spec
        |
        v
 React dashboard                     EXISTING UI, mock data layer replaced
```

### 2.2 Ownership

**Python is authoritative for** candles · signals · position state · position
sizing · fills · fees · slippage · spread · realized P&L · unrealized P&L ·
account state · trade history · statistics.

**React is responsible for** presentation · charts · replay controls · display
of all state.

**React must not** compute a signal, a position size, a fill, a fee, a P&L, a
balance, or any indicator that feeds a decision. Concretely, from the current
code these must be deleted rather than ported: `signals.ts` entirely,
`analysis.ts`'s trend/support/resistance/breakout/retest, and
`usePaperEngine`'s `openPosition` / `closePosition` / balance arithmetic.

### 2.3 The one invariant that makes this safe

> If every trade originates from `PaperBroker.open_from_signal(signal)` where
> `signal` came from `strategy.analyze`, then the trades the application shows
> are a subset of the trades the research engine could have produced.

Any UI-side shortcut — a manual close button, a client-side "if price crossed
X then close" — breaks this immediately. It is the property that makes the app
trustworthy, so §14 includes a regression test for it.

---

## 3. Replay model

### 3.1 Cycle

```
 LOAD DATA
     ↓
 RESET SESSION            broker = PaperBroker(starting_balance, costs)
     ↓
 READ NEXT CANDLE         candles[i]
     ↓
 UPDATE STRATEGY          analyze(candles[:i], config)      <- closed candles only
     ↓
 GENERATE SIGNAL          Signal(side ∈ {long, short, flat})
     ↓
 PAPER EXECUTION          open_from_signal(replace(signal, price=candles[i].open))
     or                   close(candles[i].open, ts) on an exit rule
     ↓
 UPDATE ACCOUNT           broker.cash / broker.open_trade / broker.journal
     ↓
 EXPOSE STATE TO UI       SessionSnapshot -> JSON
     ↓
 NEXT CANDLE
```

This mirrors `backtest.run_backtest` (`backtest.py:135-205`) statement for
statement. The session is that loop, made callable one iteration at a time.

### 3.2 Replay state

| Field | Type | Meaning |
|---|---|---|
| `replay_index` | int | Index of the **next** candle to consume |
| `current_candle` | Candle | `candles[replay_index - 1]`, the last consumed candle |
| `current_candle_timestamp` | datetime | `current_candle.timestamp` |
| `last_signal` | Signal | From the most recent `analyze` call, at `candles[i-1].timestamp` |
| `state` | enum | `idle` \| `running` \| `paused` \| `finished` |
| `bars_processed` | int | `replay_index - start_index` |
| `dataset_id` | str | Path + SHA-256 of the loaded file |
| `total_candles` | int | Length of the loaded series |

**`current_candle` is the fill bar, not the signal bar.** `analyze` reads
`candles[:replay_index]`, so the signal's newest input is
`candles[replay_index - 1]` — which is `current_candle`. The one-candle gap
between signal and fill is preserved exactly. The API must expose both
timestamps so the UI can show the gap rather than hide it.

### 3.3 Stepping determinism

`step()` is a pure function of `(replay_index, broker state, dataset)`. It
uses no wall clock, no randomness, no I/O beyond the already-loaded array.
Two consequences, both required:

- **`step()` twice from the same index gives the same result.** No hidden
  timer.
- **Auto-run must be implemented as repeated `step()`**, not as a separate
  code path with its own timing. If a timer decides when to step, the result
  depends on scheduling.

### 3.4 Reset

`reset()` restores the **exact** initial state: fresh `PaperBroker` with the
same `starting_balance` and `TradingCosts`, `replay_index = start_index`,
`bars_processed = 0`, `last_signal = None`, journal empty.

It must not reload the file (wasteful) and must not mutate the strategy
config. After reset, replaying N steps must reproduce the previous run exactly.

### 3.5 Start index and warm-up

`analyze` requires `max(lookback + 2, slow_period)` candles — 22 for the default
config — and raises `ValueError("not enough candles for configured strategy")`
otherwise. Replay must therefore refuse to start before the minimum history is
available, and must surface that as an explicit error rather than a silent
no-op. `start_index` is a parameter so a walk-forward evaluation boundary can
be replayed.

### 3.6 End of data

When `replay_index >= len(candles)`:

- `state` becomes `finished`.
- Any open position is force-closed at the **final candle's close**, labelled
  `end_of_data` — exactly as `backtest.py:207-212` does. This is required for
  replay to reproduce Phase 13, which retains one such trade per window.
- Further `step()` calls return `409 Conflict` with a `REPLAY_FINISHED` error,
  not a silent success. A no-op step would let a UI believe it advanced.

---

## 4. API contract

### 4.1 Path convention (see finding N2)

`orval.config.ts` sets `baseUrl: "/api"`. Therefore:

| Declared in `openapi.yaml` | Actual URL |
|---|---|
| `/healthz` | `/api/healthz` |
| `/session` | `/api/session` |

Every path in §4.2 is the **actual** URL. The OpenAPI spec declares it without
the `/api` prefix, matching the existing `/healthz` entry.

### 4.2 Endpoints

Only endpoints with a demonstrated consumer are included. Justification is
given for each; §4.3 lists what is deliberately excluded.

| Method | Path | Mutates | Justification |
|---|---|---|---|
| GET | `/healthz` | no | **Already exists.** Liveness + engine readiness |
| GET | `/api/session` | no | One aggregate snapshot; the dashboard's primary fetch |
| GET | `/api/market` | no | Latest candle + display-only overlays + chart window |
| GET | `/api/signal` | no | SIGNAL panel |
| GET | `/api/position` | no | POSITION panel |
| GET | `/api/account` | no | ACCOUNT panel |
| GET | `/api/trades` | no | TRADES panel |
| GET | `/api/statistics` | no | RESEARCH panel |
| POST | `/api/replay/start` | **yes** | Begin auto-stepping |
| POST | `/api/replay/pause` | **yes** | Halt auto-stepping |
| POST | `/api/replay/step` | **yes** | Advance N candles deterministically |
| POST | `/api/replay/reset` | **yes** | Return to initial state |

#### `GET /healthz` — exists, unchanged

Response `200`:

```json
{ "status": "ok", "engine": "ready", "dataset_loaded": true,
  "replay_state": "paused", "execution_model": "cost_deduction" }
```

`engine: "unavailable"` with `503` when the session cannot be constructed. The
UI must render an engine-unavailable state and **must not fabricate data**.

#### `GET /api/session`

The aggregate read model. One request populates ACCOUNT, MARKET, SIGNAL,
POSITION and REPLAY panels.

Query: none.

Response `200` — the `SessionSnapshot` of §4.9.

Deterministic: yes. Reads current state only.

#### `GET /api/market`

Query: `limit` (int, default 200, max 2000) — number of trailing candles for
the chart.

Response `200`: `{ latest: Candle, window: Candle[], overlays: {...},
data_timestamp: datetime }`.

`overlays` carries `sma20` (`float | null`), served from
`indicators.simple_moving_average` over the trailing closes and flagged
`display_only: true`. Justified: the chart cannot be drawn without a series,
and `dashboard.tsx` already reads a candle array. The UI must not treat
`sma20` as a signal input.

Errors: `400 INVALID_LIMIT` if `limit` out of range; `503 NO_DATA` if no
dataset is loaded.

#### `GET /api/signal`

Response `200`: `{ signal: Signal | null, signal_timestamp: datetime | null,
fill_timestamp: datetime | null }`.

`signal` is `null` before the first step. `fill_timestamp` is the next
candle's timestamp — exposing it makes the one-candle gap auditable from the UI.

#### `GET /api/position`

Response `200`: `{ position: Position | null }`, or `Position` with
`status: "flat"` and null economics. Never 404 — "no position" is a normal
state, not an error.

#### `GET /api/account`

Response `200`: `Account` per §4.6.

#### `GET /api/trades`

Query: `limit` (int, default 100, max 1000), `offset` (int, default 0).

Response `200`: `{ trades: Trade[], total: int, offset: int, limit: int }`,
newest first. Order is stable: journal order reversed, which is deterministic
because the journal is append-only.

#### `GET /api/statistics`

Response `200`: `Statistics` per §4.8, computed from **closed trades only** by
`stats.performance` and `stats.cost_breakdown`.

Note: `performance` excludes unrealized P&L by construction. A `RESEARCH`
panel showing live statistics is therefore a *closed-trades* view. The equity
curve is separate (§4.8).

#### `POST /api/replay/start`

Request: `{ "interval_ms": 1000 }` (int, default 1000, min 100, max 60000;
optional).

Response `200`: `{ state: "running", replay_index: int }`.

Mutates: yes. Idempotent — starting an already-running session returns its
current state without restarting the timer.

Errors: `409 REPLAY_FINISHED`; `409 DATASET_NOT_LOADED`; `400 INVALID_INTERVAL`;
`503 ENGINE_UNAVAILABLE`.

#### `POST /api/replay/pause`

Request: none. Response `200`: `{ state: "paused", replay_index: int }`.
Mutates: yes. Idempotent.

#### `POST /api/replay/step`

Request: `{ "count": 1 }` (int, default 1, min 1, max 5000).

Response `200`: the full `SessionSnapshot` after stepping, plus
`steps_executed: int`.

Mutates: yes. Advances the replay by `count` candles. Refuses when finished.

`count > 1` is justified: stepping to a window of interest one candle at a
time is unusable, and batch stepping is still fully deterministic because it
is literally N calls to the same code path.

Errors: `409 REPLAY_FINISHED`; `503 NO_DATA`; `400 INVALID_COUNT`.

#### `POST /api/replay/reset`

Request: none. Response `200`: the initial `SessionSnapshot` with
`state: "idle"`, `replay_index: start_index`, empty trades.

Mutates: yes. Stops any timer, rebuilds the broker from the stored
`starting_balance` and `TradingCosts`.

Errors: `503 NO_DATA`.

### 4.3 Deliberately excluded

| Rejected | Reason |
|---|---|
| `POST /api/orders` or any order submission | There is no order concept. This is the boundary in §12 |
| `POST /api/position/close` | Manual close is a trading control and breaks the §2.3 invariant |
| `POST /api/position/open` | Same, and it would need a client-supplied size |
| `POST /api/replay/seek` | Backwards seek would require re-running from the start; `reset` + `step(count)` is the deterministic equivalent |
| `PUT/PATCH/DELETE` on any resource | The API is read-mostly. The four replay verbs are the only mutations |
| Any `leverage`, `margin`, `notional` field | See §5.4 |
| Any `confidence` field | **MISSING FROM PYTHON ENGINE** — no such concept exists (§1.2 N3) |
| A dataset-upload endpoint | Datasets are frozen research artifacts, opened read-only |

### 4.4 Conventions

- JSON only. `Content-Type: application/json`.
- All timestamps ISO-8601 with offset, via `format: date-time`. orval's
  `useDates: true` turns these into JS `Date` on the client.
- Floats serialized as JSON numbers. **No rounding in Python.** Rounding, if
  any, happens at the display layer only, so the API can serve full precision
  and the determinism test can compare exactly.
- `null` for "not applicable" — never `0`, never `""`. This preserves the
  Phase 14B convention that `None` and zero are different.

### 4.5 Shared data contracts

Field names are taken from the Python engine. Where the UI's current name
differs, the mapping is given.

#### Candle — `models.Candle`

| Field | Type | Notes |
|---|---|---|
| `timestamp` | datetime | |
| `open`, `high`, `low`, `close`, `volume` | number | |

#### Signal — `models.Signal`

| Field | Type | Notes |
|---|---|---|
| `timestamp` | datetime | Signal-candle time |
| `side` | `"long" \| "short" \| "flat"` | UI currently shows `BUY`/`SELL`/`HOLD` — **map, do not rename** |
| `reason` | string | One of the five fixed strings |
| `price` | number | Reference price; the session overwrites this with the next open before execution |
| `support`, `resistance` | number | |
| `trend` | `"up" \| "down" \| "sideways"` | |
| `breakout`, `retest` | boolean | |
| `signal_close` | number \| null | Phase 14B |
| `trend_state` | `"up"\|"down"\|"sideways"` \| null | Phase 14B |
| `breakout_distance` | number \| null | Phase 14B |
| `retest_distance` | number \| null | Phase 14B |
| `realised_volatility` | number \| null | Phase 14B; **not annualised** |
| `mean_range` | number \| null | Phase 14B; **not ATR** |

UI mapping: `signal.type` → `signal.side`; `signal.confidence` → **deleted**
(MISSING FROM PYTHON ENGINE).

#### Position

Derived from an open `PaperTrade` plus a mark price.

| Field | Type | Source |
|---|---|---|
| `side` | `"long" \| "short"` | `PaperTrade.side` |
| `entry_price` | number | `PaperTrade.entry_price` — the **fill** |
| `raw_entry_price` | number \| null | `PaperTrade.raw_entry_price` |
| `quantity` | number | `PaperTrade.quantity` |
| `opened_at` | datetime | `PaperTrade.entry_time` |
| `bars_held` | int | maintained by the session |
| `current_price` | number | mark price — see §5.3 |
| `unrealized_pnl` | number \| null | §5.2 |
| `entry_signal_reason` | string | `PaperTrade.reason` |
| `signal_close`, `trend_state`, `breakout_distance`, `retest_distance`, `realised_volatility`, `mean_range`, `support_at_entry`, `resistance_at_entry` | number/string/null | Phase 14B, already on the trade |

#### ExecutionCosts — `costs.TradingCosts`

| Field | Type |
|---|---|
| `fee_rate` | number |
| `slippage_rate` | number |
| `spread_rate` | number |
| `execution_model` | `"cost_deduction" \| "fill_price"` |
| `adverse_rate` | number (`spread_rate + slippage_rate`) |
| `config_repr` | string — `repr(TradingCosts)`, so the UI can display the exact frozen object |

#### ReplayState

Per §3.2.

#### Trade, Account, Statistics

§4.6, §4.7, §4.8.

### 4.6 Trade — `models.PaperTrade`

Every stored field, so the UI never has to infer anything:

`side`, `entry_time`, `entry_price`, `quantity`, `exit_time`, `exit_price`,
`reason`, `costs`, `exit_reason`, `bars_held`, `raw_entry_price`,
`raw_exit_price`, `fee_total`, `slippage_total`, `spread_total`, plus the 8
Phase 14B fields.

Plus three **computed properties**, served as values not formulas:
`pnl` (gross), `net_pnl`, `total_friction`.

### 4.7 Account

| Field | Type | Definition |
|---|---|---|
| `starting_balance` | number | `broker.starting_balance` |
| `balance` | number | `broker.cash` — **realized only** |
| `realized_pnl` | number | `broker.cash - starting_balance` |
| `unrealized_pnl` | number | §5.2; `0.0` when flat |
| `equity` | number | `balance + unrealized_pnl` |
| `available_balance` | number | `equity` — see §5.4 |
| `reserved_capital` | number | **`0.0` always** — see §5.4 |
| `open_position` | Position \| null | |
| `accumulated_fees` | number | `stats.total_fees(journal)` |
| `accumulated_slippage` | number | `stats.total_slippage(journal)` |
| `accumulated_spread` | number | `stats.total_spread(journal)` |
| `accumulated_total_friction` | number | `stats.total_friction(journal)` |
| `accumulated_deducted_costs` | number | `sum(t.costs)` — differs from total_friction under `fill_price` |

### 4.8 Statistics

From `stats.performance` (closed trades only) and `stats.cost_breakdown`:

`trades`, `net_pnl`, `win_rate`, `profit_factor`, `average_pnl`,
`max_drawdown`, `ending_balance`; plus `fee_total`, `spread_total`,
`slippage_total`, `total_friction`, `deducted_costs`.

**Finding N1 handled explicitly.** `performance` returns
`float("inf")` when `gross_loss == 0`. `Infinity` is not valid JSON. The
serializer must emit:

```json
{ "profit_factor": null, "profit_factor_infinite": true }
```

and the UI must render "∞ (no losing trades)" rather than a number. Silently
substituting a large finite value would be a fabricated statistic.

`max_drawdown` here is the **realized** drawdown over the closed-trade P&L
sequence. It is *not* the mark-to-market drawdown. If the UI shows a
mark-to-market figure, it must come from
`robustness.mark_to_market_drawdown` and be labelled as such — the two are
different numbers by construction, since one values open positions and the
other does not.

### 4.9 SessionSnapshot

The aggregate of §3.2 + §4.7 + latest candle + last signal + trades +
statistics. One object so the dashboard needs one fetch and cannot
interleave inconsistent states across panels.

---

## 5. Accounting contract

### 5.1 The rule

> Every number the UI displays is **computed in Python** and transported as a
> value. React performs no trading arithmetic.

There is no acceptable middle ground. The existing mock engine's failure was
precisely a second set of arithmetic in TypeScript, and it disagreed with the
research record in four ways at once.

### 5.2 Unrealized P&L

Reuse the engine's existing formula and conventions from
`robustness.equity_curve_mark_to_market` (`robustness.py:127-142`):

```
direction     = 1.0 if side == "long" else -1.0
unrealized    = (mark - entry_price) * quantity * direction
equity        = balance + unrealized
```

with the documented conventions preserved verbatim:

1. **Unrealized P&L is gross** — before fees and slippage. The engine
   recognises all costs at closure, so a net intrabar figure would mix two
   conventions. The UI must label it "gross, excludes exit costs".
2. Marked at **candle close**, never intrabar high/low. No intrabar data
   exists; inventing it would overstate the drawdown.
3. Cash is credited only on close.

### 5.3 Mark price

`current_price` = the close of the most recently consumed candle. Not the
signal's `price` (which is overwritten to the fill reference) and not
intrabar. Deterministic and consistent with the mark-to-market convention.

### 5.4 available_balance and reserved_capital

`reserved_capital` is **always `0.0`** and must never be non-zero.

`available_balance == equity`, because there is no margin and nothing is
reserved. Both fields exist so the API can state that absence as a fact rather
than by omission, and so §14 can assert it. They are **not** an extension
point: adding a non-zero reserved balance would introduce margin, which §12
prohibits.

### 5.5 Fields the engine cannot yet supply

| Needed by UI | Status |
|---|---|
| `bars_held` for an *open* position | **MISSING FROM PYTHON ENGINE** — `PaperTrade.bars_held` is set only at close (`backtest.py:189`). The session must track it; that is session state, not a change to `PaperBroker`. |
| Cumulative running cost totals | Derived, not stored. `stats.total_fees` etc. sum the journal — O(n) per request. Cache in the session if it becomes a concern. |
| Equity curve for a live session | `robustness.equity_curve_mark_to_market` needs the **candle array** and closed trades. Adapting it for a live session is new work and is not required for the minimum dashboard. Omitted. |

---

## 6. Execution model

### 6.1 The application uses `cost_deduction`

**Selected:** `cost_deduction` — the frozen Phase 13 baseline.
Fee `0.001`, slippage `0.0005`, spread `0.0`.

**Why:** it is the model under which every frozen research artifact was
produced. The Phase 14B and 14C equivalence tests reproduce Phase 13's trade
counts and ending balances to within 1e-9 only under this model. Defaulting to
`fill_price` would mean the application's numbers could not be reconciled with
the committed record — the exact class of defect this integration exists to
eliminate.

### 6.2 Relation to Phase 12

Phase 12 found five real execution defects and added `fill_price` to correct
them. It deliberately made the new model **opt-in** so prior results still
reproduce. This design does not undo that.

| Property | `cost_deduction` (app default) | `fill_price` (available, not default) |
|---|---|---|
| Recorded entry/exit price | raw chart price | price actually paid/received |
| Where slippage lives | deducted from P&L | embedded in the fill |
| Where spread lives | not representable (`costs.py:77` rejects `spread_rate > 0`) | embedded in the fill |
| `trade.costs` | `fee_total + slippage_total` | `fee_total` only |
| `trade.total_friction` | same as `costs` | `fee + spread + slippage` |
| Position size denominator | `fill == reference`, so raw | slipped fill |

`TradingCosts.__post_init__` raises if `spread_rate > 0` under
`cost_deduction`, because spread cannot be separated from slippage there and
charging both would double count. The API must surface that as a `400`, not
swallow it.

### 6.3 How costs are represented

Per closed trade, exactly as the engine records them:

- `fee_total = (entry_value + exit_value) * fee_rate`
- `slippage_total = notional * slippage_rate`
- `spread_total = 0.0` under `cost_deduction`
- `costs = fee_total + slippage_total`, deducted from gross P&L
- `net_pnl = pnl - costs`

Session totals come from `stats.cost_breakdown`. The `deducted_costs` versus
`total_friction` distinction is preserved rather than collapsed, because under
`fill_price` they differ and collapsing them would hide that.

### 6.4 Full-position closing

Always full. `PaperBroker.close` has no partial path, and
`open_from_signal` raises if any trade is open, so at most one position can
ever exist. The API must not expose any partial-close or quantity-reduction
field.

Exit reasons the UI may display, matching `backtest.py:13-15` and the Phase 13
artifacts: `opposite_signal` (the only active rule), plus `stop_loss`,
`take_profit`, `max_holding` if those optional configs are ever enabled, and
`end_of_data` at replay end.

### 6.5 No silent switching

The execution model is fixed at session construction and returned in
`/healthz`, `/api/session` and the `ExecutionCosts` block. It must never change
mid-session. `reset()` restores the **stored** model, never a default.

---

## 7. UI data flow

### 7.1 Fetch pattern

One `GET /api/session` populates ACCOUNT, MARKET, SIGNAL, POSITION and REPLAY.
One `GET /api/trades` and one `GET /api/statistics` populate TRADES and
RESEARCH. A single `SessionSnapshot` guarantees the panels cannot show
inconsistent states from interleaved requests.

Recommended orval/react-query setup:

| Query | Refetch |
|---|---|
| `useSession` | after every replay mutation |
| `useTrades` | after every replay mutation |
| `useStatistics` | after every replay mutation |
| `useMarket(limit)` | on `asset`/`timeframe` change only |
| `useHealthCheck` | on an interval, for the engine-unavailable banner |

Auto-run uses the returned `replay_index` to poll, or `start` streams. Either
is acceptable; **the pacing must not influence engine results** (§9).

### 7.2 Panel mapping

| Panel | Source | Notes |
|---|---|---|
| ACCOUNT | `snapshot.account` | All fields computed in Python |
| MARKET | `snapshot.current_candle`, `snapshot.replay` | Mark the price **simulated** |
| SIGNAL | `snapshot.last_signal` | `side`, `reason`, `trend`, levels, distances |
| POSITION | `snapshot.account.open_position` | Render "FLAT" when null |
| TRADES | `useTrades` | Server-paginated |
| RESEARCH | `useStatistics` | Closed trades only; label `profit_factor: null` as ∞ |
| REPLAY | `snapshot.replay` + controls | start / pause / step / reset |

### 7.3 What the UI must never do

- Compute a signal, indicator feeding a decision, size, fill, fee, P&L or
  balance.
- Derive a trade's P&L from entry/exit prices for display. Use the served
  `pnl` / `net_pnl`.
- Treat `sma20` as a signal input — it is `display_only`.
- Keep any local balance, position or trade state as the source of truth. The
  server is authoritative; React state is a cache.

---

## 8. Mock system replacement

Nothing is deleted or modified by this document. This is the mapping to apply
during implementation.

### `mock-data.ts`

| | |
|---|---|
| **Current role** | Generates the candle series the chart and all panels consume |
| **Current problem** | `generateCandles` builds prices from `Math.sin`/`Math.cos` of the timestamp. Not market data. Base price is hardcoded per asset (BTC 65000, ETH 3500). `currentPrice` is additionally jittered by `Math.random()` on a 3s timer in `usePaperEngine`, so **even the mock is not reproducible between renders** |
| **Replacement** | `GET /api/market` → `{ latest, window, overlays }`, served from `data.load_ohlcv_csv` over a frozen dataset |
| **Source of truth** | `crypto_paper_lab.data.load_ohlcv_csv`, hash-verified by `walkforward.validate_dataset_integrity` |

### `signals.ts`

| | |
|---|---|
| **Current role** | Produces the SIGNAL panel's `type`, `confidence`, `reason` |
| **Current problem** | Signal derives from `Math.sin(Date.now()/10000)` — random, time-dependent, non-reproducible. `confidence` is `75 + random % 20`: **fabricated**. `reason` is one of three canned strings unrelated to any market state |
| **Replacement** | `GET /api/signal` → `strategy.analyze` output verbatim |
| **Source of truth** | `crypto_paper_lab.strategy.analyze` |

Deleted outright. There is nothing here to adapt — `confidence` has no Python
counterpart (**MISSING FROM PYTHON ENGINE**) and must disappear from the UI
rather than be reimplemented.

### `analysis.ts`

| | |
|---|---|
| **Current role** | Computes `trend`, `support`, `resistance`, `breakout`, `retest`, `sma20` for the panels |
| **Current problem** | A **different strategy**: SMA20-on-closes with `support = min(close)`, `resistance = max(close)` (closes, not lows/highs), and a ±1%/±2% band. `breakout = current > max * 0.99` is close to tautological given support/resistance are derived from the same window, so it flags constantly. None of it matches `strategy.py` |
| **Replacement** | `GET /api/signal` for trend/levels/breakout/retest; `overlays.sma20` for the chart line |
| **Source of truth** | `crypto_paper_lab.strategy.analyze`, and `indicators.simple_moving_average` for the display-only overlay |

`sma20` is served so the UI stops computing it, but flagged `display_only: true`
and never used as a decision input. Note it is a *different* MA from the
strategy's 5/12 pair.

### `usePaperEngine.ts`

| | |
|---|---|
| **Current role** | Balance, positions, trades, current price, `openPosition`, `closePosition`, `reset` |
| **Current problem** | Cash-reservation accounting (`balance -= size` on entry) that the engine does not use; notional-return P&L instead of quantity-based; **no fees, slippage or spread**; starting balance 100000; unbounded concurrent positions; `Math.random()` trade IDs and price jitter; manual open/close instead of strategy-driven |
| **Replacement** | `GET /api/session` + `GET /api/trades` for display; `POST /api/replay/*` for control |
| **Source of truth** | `crypto_paper_lab.simulator.PaperBroker` |

`openPosition` and `closePosition` are **deleted, not adapted** — they are
manual trading controls and would break the §2.3 invariant. `reset` maps to
`POST /api/replay/reset`. The hook may keep its shape as a thin fetch wrapper.

### Retained unchanged

All ~70 shadcn/ui primitives, `error-boundary.tsx`, `use-toast`, `index.css`,
the layout, and the chart integration. `dashboard.tsx` keeps its structure and
loses its data layer.

---

## 9. Determinism and reproducibility

### 9.1 Requirement

Given an identical dataset, `StrategyConfig`, `TradingCosts`,
`starting_balance` and step sequence, the engine must produce identical
results whether driven:

- **A.** directly in Python (`run_backtest`), or
- **B.** through the replay interface, one `step()` at a time or in batches.

### 9.2 Why this is the central test

It is the only test that proves the UI cannot influence trading outcomes. If
the UI changed a result, this test fails. Everything else in §14 is
supporting evidence.

### 9.3 Requirements on the implementation

1. No randomness anywhere in the session path. Assert by grep: no `random`,
   no `numpy.random`, no `uuid4`, no `time.time()` in a decision path.
2. No wall clock in a decision path. `interval_ms` affects **when** `step()` is
   called, never **what** it does.
3. Auto-run is a loop over the same `step()` used by the manual path. No
   separate code path.
4. `reset()` restores bit-identical state so a replay can be repeated.
5. No float rounding in serialization. Comparison must be exact or 1e-9.

### 9.4 The regression test for the boundary

Required by the brief: *prove React cannot generate a trading signal without
Python engine output.*

Two complementary checks:

**(a) Static — the mock cannot survive.**
Assert that the source tree contains no signal-generation, sizing, fill or
balance arithmetic outside the fetch layer. Concretely: `signals.ts` does not
exist; `analysis.ts` does not exist; `mock-data.ts` does not exist; and
`usePaperEngine` exports no `openPosition`/`closePosition`. A test that greps
for these paths fails if any is reintroduced — which is how a well-meaning
future PR could silently restore fabricated trading.

**(b) Behavioural — the UI cannot alter outcomes.**
Drive a replay through the API and compare against direct Python
`run_backtest` on the same window: identical trade count, identical per-trade
`entry_time`, `entry_price`, `quantity`, `exit_price`, `net_pnl`, identical
ending balance, within 1e-9. If any client-side computation existed, these
would diverge.

(c) **Negative control.** With the engine stopped, `GET /healthz` must return
`503` and the UI must render an engine-unavailable state. A test asserts the UI
issues no trading call and displays no fabricated signal. A UI that silently
falls back to mock data is the specific failure this whole design removes.

---

## 10. Error handling

Errors are **explicit**. There is no fallback to mock data under any
condition — that is the single most important rule in this section.

### 10.1 Error format

RFC 7807 `application/problem+json`, which `custom-fetch.ts` already accepts
(`DEFAULT_JSON_ACCEPT` includes it) and surfaces as `ApiError.status` /
`.data`:

```json
{
  "type": "https://local.invalid/problems/replay-finished",
  "title": "Replay already finished",
  "status": 409,
  "detail": "replay_index 17544 equals candle count 17544",
  "code": "REPLAY_FINISHED",
  "engine_state": "finished"
}
```

`code` is a stable machine-readable enum. `detail` is for humans. The UI
branches on `code`, never on `detail` text.

### 10.2 Error catalogue

| Condition | Status | `code` | UI behaviour |
|---|---|---|---|
| Engine not started / session unconstructable | 503 | `ENGINE_UNAVAILABLE` | **Engine-unavailable banner. No trading data rendered.** |
| Dataset missing or hash mismatch | 503 | `DATASET_INVALID` | Banner naming the file; no fallback |
| Malformed CSV / missing OHLCV column | 503 | `DATASET_MALFORMED` | As above |
| No dataset loaded yet | 409 | `DATASET_NOT_LOADED` | Prompt to load; disable controls |
| Replay index at end | 409 | `REPLAY_FINISHED` | Disable step/start; show "finished" |
| `count` out of range | 400 | `INVALID_COUNT` | Inline field error |
| `limit` out of range | 400 | `INVALID_LIMIT` | Inline field error |
| `interval_ms` out of range | 400 | `INVALID_INTERVAL` | Inline field error |
| `spread_rate > 0` with `cost_deduction` | 400 | `INCOMPATIBLE_COSTS` | Explain the Phase 12 double-count guard |
| Stepping before minimum history | 409 | `INSUFFICIENT_HISTORY` | Show required vs available candles |
| Invalid `StrategyConfig` (e.g. `lookback < 1`) | 400 | `INVALID_CONFIG` | Name the field |
| Unknown route | 404 | `NOT_FOUND` | — |
| Wrong method on a known path | 405 | `METHOD_NOT_ALLOWED` | — |
| Unhandled engine exception | 500 | `INTERNAL_ERROR` | Generic message; log detail server-side only. Never leak a traceback or a file path to the client |
| No open position where one is required | 409 | `NO_OPEN_POSITION` | Should not occur in normal flow; indicates an engine bug |

### 10.3 Rules

1. **Never fabricate.** If Python cannot answer, the API returns an error. It
   does not return a default, a zero, or mock data.
2. **Never partially succeed.** A failed step leaves the session exactly as it
   was. State changes are applied only after the whole step succeeds.
3. **Propagate engine exceptions as typed errors.** `ValueError` from
   `analyze` (insufficient candles) maps to `INSUFFICIENT_HISTORY`, not a 500.
4. **Log server-side, return codes client-side.** Detail goes to the existing
   pino logger.
5. **Validate at the boundary.** `count`, `limit`, `interval_ms` are range-checked
   before touching the session.

---

## 11. Security boundary

| # | Constraint | How it is enforced |
|---|---|---|
| 1 | **Bind to localhost only** | `127.0.0.1`, not `0.0.0.0`. The Express server currently takes `PORT` from env and calls `app.listen(port)` — **which binds all interfaces**. That must become an explicit `127.0.0.1` host. Worth flagging as a required change. |
| 2 | **CORS restricted** | `app.ts` currently calls `app.use(cors())` with no origin restriction, so any page on the machine can call the API. Restrict to the known dev origin. |
| 3 | **No external trading endpoints** | None exist. The only outbound HTTP in the repo is the Phase 9/10 acquisition scripts, which are separate and are not part of the app |
| 4 | **No credentials** | No exchange SDK, no signing, no key storage. `.env.example` already states "This project does not accept exchange trading credentials" |
| 5 | **No API keys for trading** | `MARKET_DATA_API_KEY` is documented as "Optional key for a future **public** market-data provider" and must stay that way |
| 6 | **`AuthTokenGetter` unused** | `custom-fetch.ts` exports it and `orval.config.ts` does not configure it. It must stay unconfigured. A test should assert no auth configuration appears in the generated client |
| 7 | **No real order submission** | No order route (§4.3) and no order concept in the engine |
| 8 | **No leverage / margin** | `risk_fraction` is validated `0 < r <= 1` at `simulator.py:82`. No leverage parameter exists. Assert `reserved_capital == 0.0` and `notional <= cash * risk_fraction * (1 + 1e-9)` |
| 9 | **Datasets read-only** | Opened via `load_ohlcv_csv`; no write path |
| 10 | **No secrets in the repo** | `.gitignore` already covers `.env` |

Two items (1 and 2) are **existing gaps in the current Express scaffold**, not
risks introduced by this design. Both must be fixed when the API is built.

---

## 12. Implementation plan

Ten stages. The order differs slightly from the brief's suggested sequence:
Step 4 (contract tests) moves ahead of Step 5 (client generation) because the
spec must be validated before code is generated from it, and the audit showed
the generated client is disposable (`clean: true`).

| Step | Deliverable | Depends on | Done when |
|---|---|---|---|
| **1** | `MarketDataSource` + `PaperSession` with `step()`, `reset()`, `start()`, `pause()`, snapshot | — | Replays a candle sequence and produces a snapshot |
| **2** | Account/state exposure: equity, unrealized, available, cumulative costs; `bars_held` for open positions | 1 | Snapshot matches hand-computed values |
| **3** | Local API: the 12 endpoints, RFC 7807 errors, localhost + CORS restricted | 2 | All endpoints respond; errors typed |
| **4** | **Contract tests** + determinism harness (direct `run_backtest` vs replay) | 3 | Equivalence to 1e-9 on a Phase 13 window |
| **5** | OpenAPI spec extended; orval regenerates client + zod | 4 | Generated types match the spec; `Infinity` handled |
| **6** | React: replace mock market data with `useMarket` | 5 | Chart renders server candles |
| **7** | React: replace mock signals with `useSignal`; delete `signals.ts`, `analysis.ts` | 5,6 | SIGNAL panel shows real signals; files gone |
| **8** | React: replace mock accounting; delete `usePaperEngine` open/close/balance; wire `useSession`/`useTrades`/`useStatistics` | 7 | Panels show server values; no client arithmetic |
| **9** | Connect the dashboard; replay controls; engine-unavailable state; paper banner; remove manual position controls | 8 | Full loop works end to end |
| **10** | End-to-end deterministic replay tests + the §9.4 boundary regression tests + TS test runner | 9 | §14 all green |

### Dependency notes

- Steps 1–4 are Python-only and independently valuable. They can be completed
  and verified before any frontend work begins, which is the safest order:
  the trading truth is settled before it is displayed.
- Step 4 before step 5 means the spec is proven against a working engine
  before any client is generated from it.
- Step 6 before 7/8 is deliberate: fixing the data source first means the
  signal and accounting panels are reading real numbers while being rewired,
  so each step is visually verifiable.
- No step may be reordered to put UI work earlier.

---

## 13. Test strategy

Design only.

### API schema correctness
- Every response validates against the OpenAPI schema.
- `side`, `trend`, `execution_model`, `replay.state` are closed enums; an
  unknown value fails validation rather than passing through.
- Timestamps are ISO-8601 with offset.
- No `Infinity`, `NaN` or `-Infinity` in any response body — assert by parsing
  with a strict JSON reader. This is finding N1's regression test.
- `null` appears where Python has `None`, and `0` never substitutes for it.

### Deterministic replay
- Same dataset + config, stepped twice from reset → byte-identical snapshots.
- `step(count=N)` equals N × `step(1)`.
- Auto-run (timed) equals manual stepping for the same total count. Proves
  pacing cannot affect results.
- No randomness or wall clock in the session module — enforced by source grep.

### Signal parity
- For each replay step, the served signal equals `strategy.analyze(candles[:i],
  config)` called directly.
- `side`, `reason`, `price`, `support`, `resistance`, `trend`, `breakout`,
  `retest` and all 6 Phase 14B fields match exactly.
- The signal's newest input is `candles[i-1]`; the fill reference is
  `candles[i].open`. Assert both timestamps are exposed and correct.
- **Causality:** mutate candles at index ≥ *i* and assert the signal for *i* is
  unchanged. Reuses the Phase 14B property.

### Account parity
- `balance == broker.cash`.
- `realized_pnl == balance - starting_balance`.
- `unrealized_pnl == (mark - entry_price) * quantity * direction`.
- `equity == balance + unrealized_pnl`.
- `available_balance == equity`; `reserved_capital == 0.0`.
- Opening does **not** change `balance` (no reservation) — the specific
  behaviour that differs from the mock engine.
- Closing credits `net_pnl` exactly once.

### Trade parity
- `trades[]` equals `[asdict(t) for t in broker.journal]` reversed, field for
  field, with `pnl` / `net_pnl` / `total_friction` included as values.
- Trade count equals `stats.performance()["trades"]`.

### Cost parity
- `accumulated_fees == stats.total_fees(journal)`; same for slippage, spread,
  total friction.
- Under `cost_deduction`: `trade.costs == fee_total + slippage_total`,
  `spread_total == 0.0`, and `total_friction == costs`.
- Under `fill_price`: `trade.costs == fee_total` and friction is **not**
  double-counted.
- Directional symmetry: at fixed quantity, long and short friction are equal.

### Reset behaviour
- After `reset()`, every snapshot field equals the initial snapshot.
- A replay after reset reproduces the previous run exactly.
- Reset preserves the configured `starting_balance`, `TradingCosts` and
  `StrategyConfig` — it must not silently revert to defaults.

### Step behaviour
- `replay_index` advances by exactly `count`.
- `bars_processed == replay_index - start_index`.
- `current_candle == candles[replay_index - 1]`.
- Stepping before minimum history returns `409 INSUFFICIENT_HISTORY`, not 500.
- `count` outside `[1, 5000]` returns `400 INVALID_COUNT` and does **not**
  mutate state.

### End-of-data behaviour
- At the final index, state becomes `finished`.
- Any open position is force-closed at the last close with
  `exit_reason == "end_of_data"`.
- Further `step` returns `409 REPLAY_FINISHED` and does not mutate.
- Replaying a full Phase 13 window yields exactly **one** `end_of_data` trade,
  matching the frozen artifact.

### Python / API equivalence
The §9.1 test: replay a Phase 13 window through the API, compare against
`run_backtest`. Identical trade count, per-trade fields, and ending balance
within 1e-9. Additionally assert the count matches the committed
`RESULTS_windows.json`.

### API / UI data mapping
- Every `SessionSnapshot` field is rendered; no orphan fields.
- With a mocked fetch returning a known snapshot, rendered balance and P&L
  equal the mocked values — **not** values recomputed in TypeScript. This is the
  direct guard against reintroducing client-side accounting.
- `profit_factor: null` renders as "∞", never as `0` or a large number.
- Timestamps render in the dataset's timezone, not the browser's, so replay is
  readable.

### The required boundary regression test
Per §9.4: (a) static — the mock files do not exist and no trading arithmetic
lives outside the fetch layer; (b) behavioural — UI cannot alter outcomes;
(c) negative control — engine down yields an engine-unavailable UI and zero
fabricated trading values.

---

## 14. Ambiguities and open questions

Not resolved here; each needs a decision.

1. **Python or TypeScript API host?** I recommend Python (§2.3: it makes a
   second accounting implementation structurally impossible). But the existing
   Express scaffold, orval pipeline and `customFetch` are all TypeScript.
   Express calling Python over localhost adds a process and a serialization
   seam; a Python API discards working scaffolding. This is the single biggest
   open decision and it changes steps 3 and 5.
2. **Auto-run transport.** Server-side timer with polling, or
   server-sent-events/websocket push? Polling is simpler and adequate at 1 h
   bars; SSE is smoother. Both are deterministic per §9.3.
3. **Which dataset is the default?** 2024–2025 has 267 baseline trades and is
   the research narrative's subject; 2026 has 105 trades and is the only genuine
   OOS period but is now documented history. A demo default, chosen
   deliberately.
4. **Should `/api/statistics` include mark-to-market drawdown?** It requires
   adapting `robustness.equity_curve_mark_to_market` for a live session. Omitted
   from the minimum. If wanted, it must be labelled distinctly from the
   realized drawdown in `stats.performance`.
5. **Chart window depth and downsampling.** `limit` up to 2000 is proposed. For
   a full 17,544-candle chart, does the UI need downsampling, and should Python
   own it?
6. **Does the app persist across restarts?** The audit flagged persistence as
   missing from Python. A snapshot-JSON resume with a position open is the
   smallest option, but it is not in the 10-stage plan because it is not needed
   for a replay-based teaching tool. Confirm it is out of scope.
7. **Should `sma20` be served at all?** It has no role in the signal. Serving it
   keeps the UI from computing it; omitting it means removing that chart
   overlay. Slight preference to serving it as `display_only`.
8. **Is `signals.ts`'s `confidence` concept wanted for display only?** It has no
   Python source. Recommendation: delete. If a score is genuinely wanted, it
   must be defined and pre-registered in Python first — inventing it in the UI
   would reintroduce exactly the fabrication this design removes.
9. **Should `stop_loss_pct` / `take_profit_pct` be exposed in the app?** They
   exist in the engine, disabled by default, and Phase 6 found no variant that
   improved on the baseline. Exposing them invites ad-hoc tuning of a strategy
   whose parameters are frozen research artifacts. Recommendation: do not
   expose; `None` only.
10. **Does the UI need a timeframe/asset switch?** `mock-data.ts` offers BTC,
    ETH and others and 15m/1h/4h, but the engine is single-asset,
    single-timeframe. Exposing a switch that the engine cannot honour would be
    misleading. Recommendation: display the configured values read-only.
11. **Which Node/pnpm setup will build the frontend?** `node_modules` is absent
    and `pnpm` is not installed in this environment, so the TypeScript build
    could not be exercised during this audit. Steps 5–10 assume a working
    install.

---

## 15. Verification performed

- Full Python test suite run — see report.
- `git diff --check` run.
- Phase 10–15 artifact digests recomputed and compared.
- Both dataset digests recomputed and compared.
- Python engine source digests compared against the values recorded at the
  start of the architecture audit.
- TypeScript source tree digests compared before and after this document.

No source code, dataset, or Phase 10–15 artifact was modified. No API or UI
implementation file was created. No integration step was implemented. Nothing
was committed or pushed. Phase 16 was not started.

---

*End of integration plan. Design and interface contract only. No implementation.*