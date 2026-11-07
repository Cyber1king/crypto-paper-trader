# Broker Layer

> **Read this before flipping any lock.** This package can place real-money orders the moment all four locks are enabled. Every lock defaults to off. Do not enable any of them without:
> - reading the risk module,
> - testing first on Binance Spot Testnet with a small balance,
> - confirming the kill switch works,
> - and knowing that flipping `production_unlocked` to `true` has real financial consequences.
>
> **Implementation status:** The four locks describe the required policy. The current Binance skeleton does not yet call `check_live_gate` or `check_order`, and production orders remain blocked in its adapter. Do not treat the four-lock policy as enforced end to end until those checks are wired in and verified.

## Purpose

This package defines a single `LiveBroker` interface, a risk module, and per-broker adapters so live trading can be added without changing paper trading or the API layer. The paper adapter exposes replay state without pretending that step-driven paper execution is a live order flow.

## The four locks

| Lock | Where | How to enable | Notes |
|---|---|---|---|
| 1. Environment variable | `LIVE_TRADING_ENABLED=true` in the shell | Set env var before starting uvicorn | Checked by `is_live_trading_enabled()` |
| 2. Per-instrument permission | `data/live_config.json` → `instruments[<id>].live_trading_permitted` | Edit the JSON file | Defaults to `false` for every instrument |
| 3. Environment match | `data/live_config.json` → `instruments[<id>].environment` vs the adapter's requested environment | Match the two values | `testnet` for Binance, `mt5_demo` for MT5 |
| 4. Production unlock | `data/live_config.json` → `global.production_unlocked` | Edit the JSON file | Required in addition to the above for `production` |

All four locks must pass. Any single refusal raises `LiveTradingDisabled` and no order is sent. There is no code path that allows a real-money order to execute with any of these set to false.

That is the required invariant, but the current Binance skeleton has not yet wired in the per-instrument config gate or the risk checks. Its production adapter path refuses orders independently of `production_unlocked`. The invariant must be verified in the adapter before relying on it.

## The `LiveBroker` contract

- `broker_name()` — return the stable identifier for the broker and environment.
- `get_balance()` — return an `AccountSnapshot`; callers must check `stale_since` when present.
- `get_positions()` — return the broker's current positions.
- `place_order(request)` — submit an order idempotently on `client_order_id`; duplicates must not execute twice. Receiving an `OrderResult` does not mean the order filled: inspect `status`.
- `cancel_order(client_order_id)` — request cancellation and report whether it succeeded.
- `close_position(instrument)` — close the entire position for that instrument when supported.

## The risk module

`RiskLimits` holds restrictive pre-trade thresholds and `RiskState` holds the current account risk state. `check_order` checks position counts, order notional, realized daily loss, and total exposure before submission. The kill switch is sticky: it remains engaged until explicitly reset. `check_order` uses `realized_pnl_today` only and does not include unrealized losses; this is a deliberate first-version limitation. The risk module is not yet wired into the Binance adapter.

## Current state

| Broker | File | Paper-tested | Testnet-tested | Production |
|---|---|---|---|---|
| Paper | `paper_adapter.py` | ✅ | n/a | n/a |
| Binance Spot | `binance_live.py` | ✅ skeleton | ❌ not yet wired to testnet | ❌ blocked by design |
| MT5 | not yet implemented | n/a | n/a | n/a |

## How to enable Binance Testnet

1. Create an account at <https://testnet.binance.vision/> and generate an API key and secret.
2. Set environment variables in the shell before starting uvicorn:

   ```powershell
   $env:BINANCE_API_KEY="..."
   $env:BINANCE_API_SECRET="..."
   $env:LIVE_TRADING_ENABLED="true"
   ```

3. Edit `data/live_config.json`: set `instruments["BTC/USDT"].live_trading_permitted` to `true`. Leave `production_unlocked` as `false`.
4. Restart uvicorn.
5. Call `BinanceLiveBroker().get_balance()` — this should now return a real testnet balance, once the adapter is wired to and verified against testnet.
6. Only then attempt a `place_order` on a tiny quantity, after the lock and risk checks have been wired in and verified.

The current adapter lazily imports the Binance SDK and has a testnet client path, but its actual SDK calls have not been verified against testnet. It does not currently enforce the instrument permission or risk module, so the steps above are not an operational authorization flow yet.

## How to DISABLE live trading

- `$env:LIVE_TRADING_ENABLED="false"` (or unset it).
- Set the instrument's `live_trading_permitted` back to `false` in `live_config.json`.
- Restart uvicorn.

## What this layer does NOT do

- It does not store historical orders in a database; that comes in the execution journal.
- It does not implement position sizing; that is the strategy layer's job.
- It does not include unrealized losses in the daily-loss limit.
- It does not implement MT5 yet.
