# Paper-Trading Application — Architecture Audit

**Scope: architecture audit only.** No source code was modified, no strategy
logic or parameter was touched, no execution behaviour changed, no dataset or
Phase 10–15 artifact was altered, no optimization was run, no research phase was
created, and nothing was committed or pushed.

Audit performed at commit `25bd7d0ab651e356240d8148525fb664938562b0`
(working tree dirty from Phase 14B/14C/15 work).

---

## 1. Executive summary

### The finding that matters most

**The repository already contains a local paper-trading application, and it is
built on a completely different accounting model from the research engine —
and it contains no strategy at all.**

`artifacts/crypto-paper-lab` is a working React + Vite dashboard with an
api-server, a Drizzle/Postgres scaffold, an OpenAPI spec and a generated API
client. It is not a stub. It also:

- generates its price data from trigonometric functions of the wall clock
  (`mock-data.ts`), not from any market data;
- derives signals from `Math.sin(Date.now() / 10000)`, so signals are random and
  non-reproducible (`signals.ts`);
- uses a **different strategy** from the research engine — SMA20 on closes with
  support as `min(close)`, versus the research engine's 5/12 MA pair with
  `min(low)`/`max(high)` over a 20-candle window (`analysis.ts` versus
  `strategy.py`);
- uses a **cash-reservation accounting model** that subtracts position size from
  balance on entry and returns it on exit, versus the research engine's
  quantity model that never reserves cash (`usePaperEngine.ts` versus
  `simulator.py`);
- starts at a balance of **100,000**, versus the research engine's 10,000;
- charges **no fees, no slippage and no spread**;
- permits **multiple concurrent positions**, versus the research engine's
  one-at-a-time invariant;
- is driven by **manual button presses**, not by a strategy.

There is **no bridge of any kind** between the TypeScript application and the
Python engine — no HTTP call, no subprocess, no IPC, no shared file format. The
api-server exposes exactly one route, `/healthz`.

### What this means architecturally

The Python research engine is the trustworthy artifact. It is the only
implementation with any validation behind it, and its frozen results are
reproducible to 1e-9. The TypeScript application is a **visual mockup** that
should be treated as a UI design reference, not as an engine.

The correct path is therefore **not** "add a UI to the research engine" — it is
"keep the Python engine as the single source of trading truth, and replace the
mock data/signal/broker layers in the existing dashboard with a thin read-only
view of a Python-owned paper session."

Three divergences must be resolved before anything else, because each one
silently produces different numbers from the research record:

| # | Divergence | Consequence if shipped as-is |
|---|---|---|
| 1 | Random signals vs `strategy.analyze()` | The app shows trades the strategy would never take |
| 2 | Cash-reservation vs quantity sizing | Balances and P&L cannot be reconciled with any research result |
| 3 | No costs vs fee/slippage/spread | Every displayed P&L is wrong; costs were 86.2% and 65.8% of gross |

---

## 2. Current capabilities

Every row cites the responsible file, module and function. Status is
**EXISTS** / **PARTIAL** / **MISSING**.

### 2.1 Python research engine (`research_engine/src/crypto_paper_lab/`)

| Capability | Status | Responsible code |
|---|---|---|
| Load candle data from CSV | **EXISTS** | `data.load_ohlcv_csv(path)` — `data.py`. Case-insensitive column mapping, accepts `timestamp` or `date`, two timestamp formats, raises on missing OHLCV. |
| Validate dataset integrity | **EXISTS** | `walkforward.validate_dataset_integrity(candles, path)` — `walkforward.py`; recomputes SHA-256 against `DATASET_SHA256` and aborts on mismatch. |
| Process candles sequentially | **EXISTS** | `backtest.run_backtest` loop, `backtest.py:135` — `for index in range(minimum_history, len(candles))`, calling `analyze(candles[:index], config)` then filling at `candles[index].open`. One-candle gap enforced by construction. |
| Generate LONG / SHORT / NO-SIGNAL | **EXISTS** | `strategy.analyze(candles, config)` → `Signal.side ∈ {"long","short","flat"}` — `strategy.py`. Fixed reason strings: `bullish retest`, `bearish retest`, `uptrend breakout`, `downtrend breakdown`, `no confirmed breakout or retest`. |
| Maintain one open position | **EXISTS** | `PaperBroker.open_trade` + `journal` — `simulator.py`. Enforces single-position: `open_from_signal` raises `"a paper trade is already open"`. |
| Calculate position size | **EXISTS** | `simulator.py:92` — `quantity = (self.cash * risk_fraction) / fill`, validated `0 < risk_fraction <= 1`. |
| Calculate entry fills | **EXISTS** | `PaperBroker._fill_price(reference, side, entering)` — `simulator.py:47`. Under `fill_price`, adverse on both legs; under `cost_deduction`, returns reference unchanged. |
| Calculate exit fills | **EXISTS** | Same `_fill_price`, called with `entering=False` from `close()` — `simulator.py:146`. |
| Calculate fees | **EXISTS** | `simulator.py:160` — `fee_total = (entry_value + exit_value) * fee_rate`, charged on notional actually transacted. |
| Calculate slippage | **EXISTS** | `simulator.py:186` — deducted from P&L under `cost_deduction`; embedded in the fill under `fill_price` and attributed via `slippage_total`. |
| Calculate spread | **EXISTS** | `costs.TradingCosts.spread_rate` + `adverse_rate` — `costs.py`. **Rejected at validation** under `cost_deduction` to prevent double-counting; requires `fill_price`. |
| Calculate realized P&L | **EXISTS** | `PaperTrade.net_pnl` property — `models.py`; `pnl` for gross. Applied to cash at `simulator.py:191`. |
| Calculate unrealized P&L | **PARTIAL** | Formula exists at `robustness.py:141` — `unrealised = (mark - trade.entry_price) * trade.quantity * direction`, but only inside `equity_curve_mark_to_market(trades, candles, starting_balance)`, which requires a **completed** trade list plus a candle array. There is **no** per-open-position unrealized accessor on `PaperBroker`, and no method to mark an open position. |
| Maintain an account balance | **PARTIAL** | `PaperBroker.cash` — `simulator.py:191`. **Realized only.** Cash is incremented at close and is never debited at entry, never marked to market, and never reserved. There is no equity, no available balance, and no separate realized/unrealized split. |
| Close the full position | **EXISTS** | `PaperBroker.close(price, timestamp)` — `simulator.py:118`. Always full; no partial close path exists. Records `raw_exit_price`, `fee_total`, `spread_total`, `slippage_total`, `costs`. |
| Persist trades | **MISSING** | `journal` is a plain in-memory `list[PaperTrade]`. No serialization, no storage, no file or database write anywhere in the package. |
| Resume state after restart | **MISSING** | No `save_state` / `load_state`, no pickle, no sqlite, no checkpointing. `PaperBroker.__init__` always begins from `starting_balance`. Confirmed by grep across the whole package. |
| Expose state to another application | **MISSING** | `BacktestResult` (`results.py:8`) is a frozen dataclass returned **after** the whole backtest completes. There is no incremental/streaming interface, no callback, no event, and no serializer. Nothing can observe state mid-run. |

### 2.2 Supporting Python capabilities worth reusing

| Capability | Status | Responsible code |
|---|---|---|
| Performance statistics | **EXISTS** | `stats.performance(trades, starting_balance)` — `stats.py`. Trade count, win rate, profit factor, average/median P&L, max drawdown, ending balance. |
| Cost attribution | **EXISTS** | `stats.cost_breakdown(trades)`, `total_fees`, `total_spread`, `total_slippage` — `stats.py`. |
| Drawdown, mark-to-market curve | **EXISTS** | `robustness.mark_to_market_drawdown`, `robustness.equity_curve_mark_to_market` — `robustness.py`. Post-hoc over a candle array. |
| Block bootstrap, dependence | **EXISTS** | `robustness.block_bootstrap_ci`, `bootstrap_ci`, `total_pnl_bootstrap_ci` — `robustness.py`. |
| Monthly aggregation | **EXISTS** | `robustness.monthly_breakdown`, `monthly_summary` — `robustness.py`. |
| Entry-time feature instrumentation | **EXISTS** | 6 `Signal` + 8 `PaperTrade` fields, copied at `simulator.py:106-113`. Includes `signal_close`, `trend_state`, `breakout_distance`, `retest_distance`, `realised_volatility`, `mean_range`, `support_at_entry`, `resistance_at_entry`. |
| Report generation | **EXISTS** | `report.create_report(backtest)` — `report.py`, via `experiment.run_experiment`. |
| Walk-forward harness | **EXISTS** | `walkforward.walk_forward`, `resolve_windows`, `run_window` — `walkforward.py`, with 11 raising leakage controls. |

### 2.3 TypeScript application (`artifacts/`)

| Capability | Status | Responsible code |
|---|---|---|
| Local dashboard UI | **EXISTS** | `artifacts/crypto-paper-lab/src/pages/dashboard.tsx` (27.5 KB) — React + Tailwind + shadcn/ui + Recharts. Sections already present: account, market, signal, positions, trade journal, performance. **This is a genuine asset and should be reused, not replaced.** |
| Component library | **EXISTS** | ~70 shadcn/ui primitives under `src/components/ui/` — card, table, badge, tabs, chart, dialog, sidebar. |
| HTTP API server | **PARTIAL** | `artifacts/api-server/src/app.ts` — Express + pino-http + CORS. **Only `/healthz` is implemented.** No trading, account, signal, or data routes. |
| API contract tooling | **EXISTS** | `lib/api-spec/openapi.yaml`, `orval.config.ts`, generated client at `lib/api-client-react/src/generated/api.ts`, zod schemas at `lib/api-zod/`. The pipeline exists; the trading schema does not. |
| Database layer | **MISSING** | `lib/db/src/schema/index.ts` is the unmodified scaffold — `export {}`. No tables. `lib/db/src/index.ts` throws unless `DATABASE_URL` is set. |
| Real market data | **MISSING** | `mock-data.ts:generateCandles` synthesizes candles from `Math.sin`/`Math.cos` of the timestamp. No file, no network, no exchange. |
| Strategy logic | **MISSING** | `analysis.ts:analyzeCandles` is an SMA20-on-closes approximation, not the research strategy. `signals.ts:generateSignal` returns a signal derived from `Math.sin(Date.now()/10000)` — random, non-deterministic, with a fabricated `confidence` score and canned reason strings. |
| Paper broker / accounting | **PARTIAL, and divergent** | `usePaperEngine.ts` — see §2.4. |
| Persistence | **MISSING** | All state is React `useState`. No storage, no API write, no database. |
| Tests | **MISSING** | No test file, no test runner, no test script in any `package.json`. |

**Environment note:** `node_modules` is not installed in any artifact;
`node v22.15.0` is available but `pnpm` is not. Nothing in the TypeScript tree
has been built or executed in this working copy.

### 2.4 The mock broker, precisely

`usePaperEngine.ts` — the exact divergences from `simulator.py`, because these
determine whether the app can ever reconcile with the research record:

| Property | `usePaperEngine.ts` | `simulator.py` (research) |
|---|---|---|
| Starting balance | `100000` | `10000.0` |
| Sizing | Caller supplies `size`; engine only checks `size <= balance` | `cash * risk_fraction / fill` |
| Cash on entry | `setBalance(b => b - size)` — cash **reserved** | No debit; quantity derived from a fraction |
| Cash on exit | `setBalance(b => b + pos.size + pnl)` | `cash += trade.net_pnl` |
| P&L formula | `((exit - entry) / entry) * size` — notional return | `(exit_fill - entry_fill) * quantity * direction` |
| Short P&L | `((entry - exit) / entry) * size` | quantity-based, sign-correct via `direction` |
| Fees / slippage / spread | **none** | `fee_total`, `slippage_total`, `spread_total` |
| Concurrent positions | `Position[]`, unbounded | exactly 1, enforced by exception |
| Entry trigger | manual `openPosition()` call | strategy signal |
| Trade identity | `Math.random()` string | none assigned |
| Determinism | `Math.random()` per 3s tick | fully deterministic |

---

## 3. Missing capabilities

Consolidated. Everything here is required for a local paper-trading
application and **none of it exists**.

### 3.1 Engine gaps (Python)

1. **A streaming/step interface.** `run_backtest` is a monolithic loop over a
   complete array. There is no `step(candle)`, no `on_candle` callback, no event
   emission. A live or replaying app cannot observe or drive it incrementally.
2. **A paper session abstraction.** No object owns "current balance + open
   position + trade history + latest candle + latest signal" as a coherent,
   inspectable unit.
3. **Unrealized P&L for an open position.** The formula exists but only in a
   post-hoc equity-curve helper that needs closed trades.
4. **Equity / available balance / reserved capital.** `cash` is realized-only.
   There is no `equity`, no `available`, no `reserved`.
5. **Persistence and restart.** No serialization of any broker or session state.
   `PaperBroker` cannot be reconstructed mid-position.
6. **A read-only state serializer.** Needed to serve the UI. `PaperTrade` is a
   dataclass but there is no `to_dict`, no schema, and datetime fields are not
   JSON-safe by default.
7. **A market-data provider abstraction.** `load_ohlcv_csv` reads a file. There
   is no interface a future live adapter could implement, and the strategy is
   coupled to `Sequence[Candle]` — which is acceptable, but no adapter contract
   exists above it.
8. **Exit-decision extraction.** Exit logic is inline in the `run_backtest`
   loop. A session needs it callable per candle, outside the backtest.

### 3.2 Application gaps (TypeScript)

9. **All trading API routes.** `/healthz` is the only endpoint.
10. **An OpenAPI trading schema.** The orval → zod → React client pipeline is
    built and unused.
11. **Any database schema.** Drizzle is configured but empty.
12. **Any frontend test coverage.** Zero tests, no runner.
13. **A real data path.** The dashboard cannot display the frozen datasets.

### 3.3 Correctness gaps (must be resolved before any UI work)

14. **Signal divergence** — `signals.ts` must be deleted or replaced, not
    adapted. It is random.
15. **Strategy divergence** — `analysis.ts` must be deleted or replaced.
16. **Accounting-model divergence** — `usePaperEngine` open/close/balance logic
    must be deleted. It cannot be "corrected" incrementally without becoming a
    second, untested accounting engine.
17. **Balance divergence** — 100,000 vs the frozen 10,000.

---

## 4. Proposed local architecture

Design only. Nothing implemented.

### 4.1 Shape

```
  A. Historical CSV            (exists, frozen, read-only)
            |
            |  load_ohlcv_csv()          <- REUSE UNCHANGED
            v
  B. MarketDataSource           (NEW - thin Protocol/ABC)
            |
            |  iter_candles() / latest   <- streaming, replaceable
            v
  C. Sequential candle/event stream       (NEW - generator)
            |
            |  Candle
            v
  D. PaperSession               (NEW - owns the loop; this is the app)
       |            |
       |            |  analyze(candles[:i], config)   <- REUSE UNCHANGED
       |            v
       |      Signal (long|short|flat)
       |            |
       |            |  open_from_signal(signal, risk_fraction)
       |            v
       |      PaperBroker                      <- REUSE UNCHANGED
       |            |
       |            |  close(price, ts) / exit rule
       |            v
       |      paper account state (cash, open_trade, journal)
       |            |
       |            v
       |      TradeLedger (append-only view of broker.journal)
       |            |
       |            +--> SessionSnapshot (read model for the UI)
       v
  E. Local API (FastAPI)       (NEW - thin; wraps the session, read-mostly)
            |
            |  JSON: account | market | signal | position | trades | research
            v
  F. Local dashboard           (REUSE the existing React app; replace 3 mock libs)
```

### 4.2 What is reused unchanged

| Component | Reused as-is |
|---|---|
| `data.load_ohlcv_csv` | Yes. Already validated, already hash-checked. |
| `strategy.analyze` + `StrategyConfig` | **Yes, untouched.** The strategy must not be rewritten. |
| `indicators.*` | Yes, as called by `analyze`. |
| `models.Candle` / `Signal` / `PaperTrade` | Yes. `Candle` and `Signal` are frozen dataclasses. |
| `simulator.PaperBroker` | **Yes, untouched** — including its single-position invariant and its cost accounting. This is the piece that must not be duplicated. |
| `costs.TradingCosts` | Yes, both execution models. |
| `stats.performance`, `cost_breakdown` | Yes, for the RESEARCH panel. |
| `robustness.mark_to_market_drawdown` | Yes, for the drawdown panel. |
| 14B entry-time feature fields | Yes — free, already on every trade, and useful in the SIGNAL panel. |
| `artifacts/crypto-paper-lab` UI + component library | Yes — the dashboard shell and all shadcn primitives. |
| `artifacts/api-server` Express app | Yes — the Express/cors/logging wiring. Add routes; do not rebuild. |
| `lib/api-spec` orval → zod → client | Yes — extend the spec; the generation pipeline already works. |
| `lib/db` Drizzle instance | Yes, once a schema exists. |

### 4.3 The single most important design rule

**There must be exactly one implementation of position sizing, cost
attribution and balance arithmetic in the entire system, and it is
`PaperBroker` in Python.**

The current failure mode is precisely that this rule was already broken once:
the TypeScript app grew its own arithmetic. The architectural defence is that
the API layer exposes **read models only** — it must not accept a size, a
balance mutation, or a price from the client. The client renders; it never
decides.

---

## 5. Data flow

Every arrow, with the payload.

| # | Arrow | Payload | Notes |
|---|---|---|---|
| 1 | Historical CSV → `MarketDataSource` | file path | Read-only. Dataset must not be written. |
| 2 | `MarketDataSource` → session | `Candle` objects | `Candle` is frozen: `timestamp, open, high, low, close, volume`. |
| 3 | Session maintains history | growing `list[Candle]` | The strategy is inherently batch-over-history: `analyze(candles[:i])`. A bounded window is required, not the whole file, or memory grows unbounded. |
| 4 | Session → `analyze` | `candles[:i]`, `StrategyConfig` | **Only closed candles.** `i` is the fill bar; inputs stop at `i-1`. This boundary is the research engine's core leakage control and must be preserved exactly. |
| 5 | `analyze` → session | `Signal` | `side ∈ {long, short, flat}`, `price` (the reference), `timestamp`, `support`, `resistance`, `trend`, `breakout`, `retest`, plus 6 Phase 14B fields. |
| 6 | Session rewrites signal | `replace(signal, timestamp=candles[i].timestamp, price=candles[i].open)` | Exactly what `backtest.py:145` does. The signal is computed on closed candles and **executed at the next open.** |
| 7 | Session → `PaperBroker.open_from_signal` | `Signal`, `risk_fraction` | Broker derives `quantity` itself. Client never supplies size. |
| 8 | `PaperBroker` → account state | mutated `cash`, `open_trade`, appended `journal` | Cash changes **only on close.** |
| 9 | Session evaluates exit | `exit_reason` | Opposite-signal by default. Optional stop/target/max-holding — all currently `None`. Extraction needed from `backtest.py:151-183`. |
| 10 | Session → `PaperBroker.close` | reference price, timestamp | Broker applies fills, fees, spread, slippage and P&L. |
| 11 | Account state → ledger | closed `PaperTrade` | Append-only. `PaperTrade` carries the 14B entry-time fields. |
| 12 | Session → snapshot | `SessionSnapshot` | Read model. Must be JSON-safe: datetimes to ISO-8601, floats rounded at the boundary. |
| 13 | Snapshot → API | JSON | Serve only. No mutation endpoints. |
| 14 | API → dashboard | same JSON | Replace `usePaperEngine`, `analysis.ts`, `signals.ts` with a fetch layer over the generated client. |
| 15 | Dashboard → user | rendered panels | **No order controls.** See §10. |

---

## 6. Account model

### 6.1 Audit of what the current code supports

| Concept | Status | Detail |
|---|---|---|
| starting balance | **EXISTS** | `PaperBroker.starting_balance` / `BacktestResult.starting_balance` |
| current balance | **PARTIAL** | `PaperBroker.cash` exists but is **realized-only** — never reduced at entry, never marked to market |
| available balance | **MISSING** | No concept |
| reserved capital | **MISSING** | Deliberately so: the engine holds no margin and reserves nothing |
| open position | **EXISTS** | `PaperBroker.open_trade`, at most one |
| entry price | **EXISTS** | `PaperTrade.entry_price` (the fill) and `raw_entry_price` (the reference) |
| position size | **EXISTS** | `PaperTrade.quantity`, a quantity in base units |
| unrealized P&L | **PARTIAL** | Formula only, in `robustness.py:141`, requiring closed trades |
| realized P&L | **EXISTS** | `PaperTrade.net_pnl`; cumulative via `broker.cash - starting_balance` |
| cumulative fees | **PARTIAL** | Per-trade `fee_total` exists; a running total does not |
| cumulative slippage | **PARTIAL** | Per-trade `slippage_total` exists; no running total |
| cumulative spread | **PARTIAL** | Per-trade `spread_total` exists; no running total |
| trade history | **EXISTS** | `PaperBroker.journal`, in memory only |

### 6.2 What a session must add (design only)

```
SessionSnapshot
  balance            # broker.cash                     (realized)
  starting_balance   # broker.starting_balance
  equity             # balance + unrealized(open position)     NEW
  available_balance  # equity (no margin, nothing reserved)    NEW
  reserved_capital   # 0.0, stated explicitly                  NEW
  position | None
      side, entry_price (fill), raw_entry_price, quantity,
      opened_at, bars_held, unrealized_pnl, entry-time features
  cumulative         # fees, slippage, spread                NEW (running totals)
  last_signal | None
  last_candle | None
  trades[]           # closed PaperTrade records
  counters           # trades, wins, losses
```

Three constraints on this model:

1. **`reserved_capital` is always 0.0.** It exists in the schema so the UI can
   state "no margin" as a fact rather than by omission. It must never become
   non-zero.
2. **`available_balance == equity`.** With no margin and full-position exits
   there is nothing to reserve. Adding a reserved-capital field implies a
   system that could later use it — that is a design risk, and the field is
   included only to make the absence explicit and testable.
3. **Unrealized P&L must use the existing formula**
   `(mark - entry_price) * quantity * direction` from `robustness.py:141`, and
   must be labelled **gross** — it excludes fees and exit slippage. Phase 11
   recorded exactly this caveat. Reusing the formula rather than writing a
   second one is the point.

---

## 7. Position-sizing model

### 7.1 As implemented

| Property | Value | Source |
|---|---|---|
| Default risk fraction | **0.01** | `walkforward.RISK_FRACTION = 0.01`; `run_backtest(risk_fraction=0.01)`; `simulator.open_from_signal(risk_fraction=0.01)` |
| Formula | `quantity = (cash * risk_fraction) / fill` | `simulator.py:92` |
| Base | `self.cash` — **realized** balance only | `simulator.py` |
| Validation | `0 < risk_fraction <= 1`, else `ValueError` | `simulator.py:82` |
| Raw or filled price? | **The fill.** Under `fill_price` the denominator is the slipped entry fill; under `cost_deduction` fill == reference, so it is the raw price. | `simulator.py:86-92` |
| Fees considered in sizing? | **No.** Size is fixed before fees are computed. | — |
| Slippage considered? | **Yes, indirectly** — only via the `fill_price` denominator. | `simulator.py:86-92` |
| Leverage assumed? | **No.** Notional = `cash * risk_fraction` = 1% of cash. There is no multiplier. | derived |
| Margin? | **None.** No collateral, no borrowing, no liquidation. | verified absent |
| Partial positions? | **None.** `open_from_signal` raises if any trade is open; `close` always closes in full. | `simulator.py:79-80` |

### 7.2 Assumptions to preserve

The application must remain, unchanged:

- **0× leverage** — notional never exceeds `cash * risk_fraction`.
- **No margin** — no collateral is posted, none is required.
- **Full-position exit** — no partial closes, ever.
- **No real-money execution** — no broker, no venue, no order.

Two subtleties worth stating because they are easy to break:

- Under `cost_deduction` (the frozen default), the *recorded* fill equals the
  raw price and costs are deducted afterwards. Under `fill_price`, the recorded
  fill is the price actually paid. **The same nominal size produces slightly
  different quantities between the two models**, by roughly 5e-4 relative at
  0.05% slippage. The application must pick one and pin it; the research
  default is `cost_deduction`.
- Sizing uses **realized** cash. While a position is open, `cash` does not
  reflect it. This is harmless under a one-position invariant — there can never
  be a second entry sized against stale equity — but it must be understood
  before any multi-position feature is ever contemplated.

---

## 8. Market-data model

Three tiers, kept strictly separate. **No live exchange connection is designed
or implemented.**

### A. Historical file data — **EXISTS, usable now**

- `data.load_ohlcv_csv(path)` — the loader.
- `walkforward.validate_dataset_integrity` + `DATASET_SHA256` — the guard.
- Frozen datasets: research 17,544 candles (2024–2025); OOS 5,832 candles
  (2026-01…08).
- These files are **research artifacts**. The application must open them
  read-only. Hash-verify on load, exactly as the walk-forward harness does.

### B. Replay / simulation — **NEW, the primary mode**

- An iterator over an in-memory or file-backed candle list, advancing one
  candle per `step()`.
- Optionally time-throttled for a human-readable demo, or stepped manually.
- Determinism requirement: given the same dataset and step count, the session
  must produce byte-identical state. No `random`, no wall-clock in any
  decision path. This is precisely the property the current mock engine
  violates via `Math.random()`.

### C. Future live adapter — **DESIGN PLACEHOLDER ONLY, NOT TO BE BUILT**

The only requirement placed on a future adapter is that it satisfy the same
interface as A and B. To keep the strategy provider-agnostic:

```
class MarketDataSource(Protocol):
    def iter_candles(self) -> Iterator[Candle]: ...
    def latest(self) -> Candle | None: ...
```

`strategy.analyze` takes `Sequence[Candle]` and knows nothing about where
candles came from, so a provider swap requires **no strategy change**. That
coupling is already correct and should be preserved deliberately.

`data.optional_market_data_key()` reads `MARKET_DATA_API_KEY`, and `.env.example`
documents it as "Optional key for a future **public** market-data provider" and
states "This project does not accept exchange trading credentials." That
boundary is correct and must be kept: **public price data only, never
trading credentials.**

---

## 9. UI architecture

The existing `dashboard.tsx` already has the right sections. It needs a data
source, not a redesign.

| Panel | Fields | Source |
|---|---|---|
| **ACCOUNT** | balance, available balance, unrealized P&L, realized P&L | session snapshot; `stats.performance` for realized totals |
| **MARKET** | latest candle OHLC, current simulated price, timeframe, data timestamp | `Snapshot.last_candle`; label the price as simulated |
| **SIGNAL** | LONG / SHORT / NO SIGNAL, signal timestamp, reason, trend state, support/resistance, breakout/retest distance | `Signal` + the 6 Phase 14B fields already on it |
| **POSITION** | direction, entry fill, size, current price, unrealized P&L, fees/costs | `broker.open_trade` |
| **TRADES** | history: entry, exit, direction, P&L, costs, exit reason, bars held | `broker.journal` |
| **RESEARCH** | trade count, win rate, profit factor, drawdown, cost breakdown | `stats.performance`, `stats.cost_breakdown`, `robustness.mark_to_market_drawdown` |

### 9.1 Changes required to the existing UI

1. **Delete** `src/lib/signals.ts`, `src/lib/analysis.ts`, `src/lib/mock-data.ts`
   and the open/close/balance logic in `src/lib/usePaperEngine.ts`. Keep the
   hook's shape if convenient, but source all values from the API.
2. **Add** a typed fetch layer over the existing generated client
   (`lib/api-client-react`), extended from the OpenAPI spec.
3. **Keep** all ~70 shadcn primitives, the layout, the chart integration and the
   error boundary.
4. **Add** an explicit persistent banner: **PAPER TRADING — SIMULATED —
   NO REAL ORDERS.** Not decoration; it is the safety boundary made visible.

### 9.2 Explicitly excluded

No order-submission control. No buy/sell button. No size input. No leverage
selector. No deposit or withdrawal control. No "connect exchange" affordance.
If the current `PositionControls` component exists to open and close positions
by hand, that component is **removed**, not adapted — a manual close is a real
trading control regardless of whether money is involved.

---

## 10. State and persistence model

### 10.1 Required session state

| State | Held where today | Assessment |
|---|---|---|
| current balance | `PaperBroker.cash` | Exists, realized-only |
| open position | `PaperBroker.open_trade` | Exists |
| latest candle | nowhere | **New** — session field |
| latest signal | nowhere | **New** — session field |
| trade history | `PaperBroker.journal` | Exists, memory-only |
| cumulative costs | per-trade only | **New** — running totals |
| session identity/config | nowhere | **New** |

### 10.2 Does the repository have suitable persistence?

**No.** Verified by grep across `research_engine/src/crypto_paper_lab/`: no
pickle, no sqlite, no `json.dump` of state, no `save_state`/`load_state`, no
`__getstate__`, no checkpointing. The only JSON in the project is
**experiment output** written by `experiments/phase*/run_*.py`.

Two partial scaffolds exist but neither is usable as-is:

- `lib/db` — Drizzle + `pg` configured, schema empty, requires `DATABASE_URL`.
  Postgres for a single-user local paper session is heavier than needed.
- React `useState` — not persistence.

### 10.3 Options (design only)

| Option | Shape | Assessment |
|---|---|---|
| **Snapshot JSON** | Serialize the whole session — balance, open trade, journal, last candle index, config — to one file after each step; reload on start | **Recommended.** Smallest thing that works, human-inspectable, trivially testable, no dependency. Restoring mid-position is the hard case and is why a snapshot must include the open trade, not just cash. |
| SQLite | One table per concept via stdlib `sqlite3` | More robust for large journals; unnecessary at 267-trade scale |
| Drizzle/Postgres | Reuse `lib/db` | Heaviest. Justified only if the app becomes multi-user or the TS side owns storage |

Whatever is chosen, three requirements apply:

1. A snapshot must be sufficient to **resume with a position open** —
   otherwise restart silently flattens the account.
2. `StrategyConfig` and `TradingCosts` must be stored with the session, or the
   resumed session may not be the session that was saved.
3. Persisted state must round-trip exactly. A resume test is mandatory (§13).

---

## 11. Paper-trading safety boundary

These are architectural constraints, not preferences.

| # | Constraint | Enforcement |
|---|---|---|
| 1 | **Paper trading only** | No order-routing code path exists in any language. Nothing to disable, because nothing is there. |
| 2 | **No exchange authentication** | No exchange SDK, no signing, no credential use anywhere in the repository |
| 3 | **No API keys for trading** | `.env.example` already states: "This project does not accept exchange trading credentials." Preserve that comment verbatim. |
| 4 | **No deposits / withdrawals** | No transfer, funding or balance-top-up primitive. Starting balance is set once at construction. |
| 5 | **No real orders** | The only "execution" is `PaperBroker`, which mutates a Python float. |
| 6 | **No real-money execution** | No venue connection, no wallet, no custody. |
| 7 | **No leverage** | Notional is `cash * risk_fraction`. No multiplier exists. Assert `quantity * price <= cash * risk_fraction * (1+ε)` in tests. |
| 8 | **No margin** | No collateral, no borrowing, no liquidation, no funding. Assert `reserved_capital == 0.0`. |
| 9 | **No partial positions** | Assert `open_trade` is `None` or exactly one trade. |

### 11.1 How the architecture could accidentally become real

Four concrete risks, each with its mitigation:

1. **A future "live" market-data adapter acquires trade credentials.**
   *Mitigation:* the adapter contract returns `Candle` only. It has no method
   that can place an order. Credentials cannot help if there is nothing to sign.
2. **The API grows a `POST /orders` route because the UI wants a button.**
   *Mitigation:* the API is read-only by construction. It exposes snapshots and
   read-only controls (replay speed, reset). A `POST` that mutates account state
   is a design-review failure.
3. **The manual `PositionControls` UI is kept "for testing".**
   *Mitigation:* delete it. A manual close is a trading control even when the
   money is fictional, and it is also the component that would let a user
   contradict the strategy.
4. **A future "what if" mode reuses the sizing code with a leverage argument.**
   *Mitigation:* `risk_fraction` is validated `0 < r <= 1` and validated again at
   the broker. There is no leverage parameter to set. Do not add one.

**Positive control:** the strongest guarantee is structural. If every trade
originates from `PaperBroker.open_from_signal(signal_from_strategy)`, then the
set of trades in the application is a subset of the trades the research engine
could have produced. Adding a manual override breaks that property
immediately.

---

## 12. Reuse vs new work

| Component | Current status | Reuse? | New work required |
|---|---|---|---|
| `data.load_ohlcv_csv` | EXISTS | **Yes, unchanged** | Wrap in a `MarketDataSource` implementation |
| `strategy.analyze` / `StrategyConfig` | EXISTS | **Yes, unchanged** | **None.** Must not be rewritten. |
| `indicators` (5 functions) | EXISTS | **Yes, unchanged** | None |
| `models.Candle` / `Signal` | EXISTS, frozen | **Yes, unchanged** | JSON serialization for the API |
| `models.PaperTrade` | EXISTS | **Yes, unchanged** | JSON serialization |
| `simulator.PaperBroker` | EXISTS | **Yes, unchanged** | Do **not** add unrealized P&L here; compute it in the read model |
| `costs.TradingCosts` | EXISTS, 2 models | **Yes, unchanged** | Pin one model for the app |
| Position sizing | EXISTS in broker | **Yes** | None. Must stay broker-owned. |
| Execution costs | EXISTS | **Yes** | None |
| `stats.performance`, `cost_breakdown` | EXISTS | **Yes** | None |
| `robustness` MTM / bootstrap | EXISTS | **Yes** | None |
| Entry-time features (14B) | EXISTS | **Yes** | Surface them in the SIGNAL panel |
| Backtest loop (`run_backtest`) | EXISTS | **Partial** | Extract the per-candle body into a callable `step()`; keep `run_backtest` as a thin wrapper so all frozen results still reproduce |
| Account state | PARTIAL — realized cash only | **Partial** | Equity, available balance, unrealized P&L, cumulative cost totals |
| Trade ledger | EXISTS in memory | **Partial** | Durable store + running aggregates |
| MarketDataSource abstraction | MISSING | **New** | Protocol + file + replay implementations |
| PaperSession | MISSING | **New** | Core application object |
| Snapshot / read model | MISSING | **New** | Dataclass + `to_dict` |
| Persistence | MISSING | **New** | Snapshot JSON (recommended) |
| Exit-decision extraction | INLINE in backtest | **New** | Extract to a callable function |
| Local API | PARTIAL — `/healthz` only | **Partial** | Express or FastAPI routes; extend the OpenAPI spec |
| API client generation | EXISTS, unused | **Yes** | Extend spec, regenerate via orval |
| `lib/db` | MISSING schema | **Defer** | Only if persistence moves to Postgres |
| Dashboard UI | EXISTS | **Yes** | Replace 3 mock libs with a fetch layer; add the paper banner; remove manual position controls |
| Component library (~70 primitives) | EXISTS | **Yes, unchanged** | None |
| Configuration | EXISTS — `StrategyConfig`, `TradingCosts` | **Yes** | A session/app config that references them rather than redefining them |
| Python tests | 528 passing | **Yes** | Add session, persistence and API tests |
| TypeScript tests | **MISSING** | **New** | Runner + component tests for the data layer |
| CI | EXISTS — Python only | **Partial** | Add TS typecheck/build once the app is real |

---

## 13. Implementation order

Smallest sequence that produces a working local paper-trading app. Each step
is independently verifiable.

| Step | Deliverable | Why it must come here |
|---|---|---|
| 1 | **`MarketDataSource` + `PaperSession` skeleton** — loads a frozen CSV, holds a growing candle list, exposes `step()` and a snapshot, no strategy yet | Establishes the streaming seam. Nothing else can be tested without it. |
| 2 | **Strategy wiring** — `analyze(candles[:i])` → `replace(..., price=candles[i].open)` → `open_from_signal` | Reuses the engine untouched. Verify: replay reproduces frozen Phase 13 exactly. |
| 3 | **Exit-decision extraction** — pull the opposite-signal rule (and optional rules) out of `run_backtest` into a callable | The session cannot manage positions while exit logic is trapped in a loop. `run_backtest` must still produce identical results. |
| 4 | **Read model** — `SessionSnapshot` with equity, available balance, unrealized P&L, cumulative costs, position, trades | The UI needs something to render. Reuse the `robustness.py:141` formula for unrealized P&L. |
| 5 | **Trade ledger + persistence** — durable journal, snapshot save/load, resume with a position open | Without this, restarting silently flattens the account — the most dangerous possible bug in a trading app. |
| 6 | **Local API** — read-only routes + extended OpenAPI; regenerate the TS client | Keeps the boundary one-way. No mutation endpoints, ever. |
| 7 | **Dashboard wiring** — delete the 3 mock libs, add the fetch layer, keep the UI, add the paper banner, remove manual position controls | The UI is already built; it needs a real data source and the removal of the divergent logic. |
| 8 | **Tests** — the plan in §14 | Retrofitting tests after each layer is why the mock engine went unchallenged. |

**Deliberately excluded from this sequence:** live data adapter, database
persistence, multi-asset, multi-timeframe, any new strategy, any optimization.
Each is a separate, separately-justified piece of work.

---

## 14. Testing plan

Design only. Every test below is a *design* for a test to be written during
implementation.

### 14.1 Sequential candle processing

- A candle stream advances one candle per `step()`; the index increments by
  exactly one.
- The session never calls `analyze` with a window containing the fill bar.
  **Test:** mutate candles at index ≥ *i* and assert the signal for *i* is
  bit-identical. This is the Phase 14B causality test, re-used verbatim.
- Feeding the same dataset twice produces identical state.

### 14.2 Signal propagation

- `flat` signals never open a position.
- `long` / `short` produce a position with the matching side.
- The executed reference price is `candles[i].open`, not the signal close.
  **Test:** assert `trade.raw_entry_price == candles[i].open`.
- `allowed_sides` gating is honoured.
- Phase 14B feature fields reach the trade record.

### 14.3 Paper execution and account balance

- Opening does **not** change `cash` (no reservation). This is the behaviour
  that differs from the mock engine and must be pinned.
- Closing credits `net_pnl` exactly once.
- Cumulative fee / slippage / spread equal the sum of per-trade values.
- `quantity * entry_price == cash_at_entry * risk_fraction` (within float
  tolerance), and notional never exceeds `cash * risk_fraction * (1 + 1e-9)`.
  **This is the leverage assertion.**
- `reserved_capital == 0.0` at all times. **This is the margin assertion.**

### 14.4 Open-position state

- At most one open position; a second `open_from_signal` raises.
- `unrealized_pnl == (mark - entry_price) * quantity * direction`.
- Unrealized P&L is gross: it excludes fees and exit slippage, and the API says so.
- `equity == cash + unrealized_pnl`; `available_balance == equity`.

### 14.5 Full-position closing

- `close` always clears the whole position.
- No partial-close method exists. **Test:** assert the public API exposes none.
- Exit reasons are recorded: `opposite_signal`, and optionally `stop_loss`,
  `take_profit`, `max_holding`, `end_of_data`.

### 14.6 Fees, slippage, spread

- Under `cost_deduction`: `fee_total + slippage_total == costs`, and
  `spread_total == 0.0`.
- Under `fill_price`: `costs == fee_total`, and spread/slippage are embedded in
  the fills and **not** deducted twice.
- Both models charge adversely on every leg: a long buys above and sells below;
  a short sells below and buys back above.
- Directional symmetry: at fixed quantity, long and short friction are equal.
  *(Phase 12 verified this; it should stay pinned.)*

### 14.7 Deterministic replay

- Replay the frozen Phase 13 baseline window and assert the resulting trade
  count and ending balance equal the committed result file to within 1e-9.
  **This is the single most important test in the plan** — it is the same
  equivalence proof already used in Phases 14B and 14C.
- No wall-clock or randomness influences any decision path.
  **Test:** grep the session module for `random`, `datetime.now`, `time.time`.

### 14.8 Persistence and restart

- Save mid-position → reload → the open position, its entry fill, quantity, and
  the trade journal are identical.
- Balance survives a restart exactly.
- Config survives: a resumed session uses the stored `StrategyConfig` and
  `TradingCosts`.
- A resumed session continues producing the same trades as an uninterrupted
  one over the same remaining candles.

### 14.9 UI / API consistency

- The API is read-only: assert no mutating verb exists on any route.
- Every snapshot field maps to a rendered panel field; assert no orphan fields.
- The dashboard renders API values, not locally computed ones.
  **Test:** with a mocked fetch returning a known snapshot, the rendered balance
  equals the mocked value — not a value recomputed in TypeScript. This is the
  direct guard against reintroducing client-side accounting.
- `Object.is` / rounding at the API boundary is deterministic.

### 14.10 Safety invariants

- No module in the application imports an exchange SDK or reads a trading
  credential. Assert by test, so it cannot regress silently.
- No leverage or margin parameter exists on any public constructor.
- No order-submission route exists.

---

## 15. Open questions

Genuine ambiguities found during the audit. Each needs a decision before
implementation, and none should be resolved by guessing.

1. **Should the local API be Python or TypeScript?**
   The existing `api-server` is Express; the engine is Python. A Python API
   keeps one process and one language but replaces proven Express scaffolding.
   An Express API proxying Python adds a process, an IPC boundary and a
   serialization seam. **This audit does not choose.** The deciding factor is
   §16 item 2 below.

2. **Where does the session live?**
   If Python owns the session, the API is a thin read wrapper and the TypeScript
   side can never become a second source of trading truth. If TypeScript owns
   it, the accounting divergence returns. **Strongly favouring Python**, but it
   is a decision, not a finding.

3. **Which execution model should the app pin?**
   `cost_deduction` reproduces all frozen research; `fill_price` is more
   realistic but reproduces none of it. Using `fill_price` in the app while the
   research used `cost_deduction` means displayed numbers will differ from the
   record by roughly 5e-4 relative. Either is defensible; mixing them silently
   is not.

4. **Should the app show the 2024–2025 or the 2026 dataset by default?**
   The research narrative centres on 2024–2025 (267 baseline trades). The 2026
   set is the only genuine OOS period but has only 105 trades and is already
   documented history. A demo default is a presentation choice with no research
   consequence — but it should be a deliberate one.

5. **Is the app a teaching tool or a research tool?**
   A teaching tool wants clean, legible panels and fast replay. A research tool
   wants the ability to reproduce frozen results on demand. The first can be
   built without §14.7; the second cannot. This changes the priority of the
   equivalence test.

6. **Should `run_backtest` be refactored, or wrapped?**
   Extracting the loop body risks changing frozen behaviour. Wrapping it leaves
   awkward coupling. The audit recommends extract-then-prove-equivalent, but
   the risk is real and must be managed by the §14.7 test, not by care.

7. **What is the intended fate of the existing mock engine?**
   Delete it (recommended — it is wrong in four ways), or keep it behind a
   "demo data" flag for screenshots. Keeping it risks someone treating mock
   output as engine output.

8. **Does `durable` persistence need to survive a crash mid-step?**
   Snapshot-after-step is simple and can lose at most one step. Write-ahead
   logging is more robust and considerably more work. For a single-user local
   educational app, snapshot-after-step is probably sufficient — but this is a
   requirement decision, not a technical one.

9. **Should the UI show a "paper" watermark on every panel, or one banner?**
   Purely a design question. One prominent persistent banner is the minimum
   acceptable.

10. **Is there any expectation of multi-asset or multi-timeframe support?**
    The engine is structurally single-asset, single-timeframe
    (`StrategyConfig.asset`, `.timeframe` are scalars). Supporting more is a
    larger change than it appears and is not implied by anything in the
    repository.

---

*End of architecture audit. Documentation only. No source code modified, no
strategy or parameter changed, no dataset or Phase 10–15 artifact altered, no
optimization run, no research phase created, nothing committed or pushed.*