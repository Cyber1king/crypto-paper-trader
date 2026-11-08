"""Typed, confirmation-gated tool layer for the future AI assistant.

This module contains no LLM integration or HTTP endpoint. Read tools project
existing application and engine state. Write tools validate and return a
proposal only; execution belongs to a separately confirmed Phase B operation.
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal
from uuid import uuid4

from fastapi.encoders import jsonable_encoder

from paper_api.brokers.base import (
    BrokerUnavailable,
    LiveTradingDisabled,
    OrderRejected,
    OrderRequest,
    is_live_trading_enabled,
)
from paper_api.brokers.binance_live import BinanceEnvironment, BinanceLiveBroker
from paper_api.brokers.live_config import check_live_gate, load_live_config
from paper_api.brokers.mt5_live import MT5LiveBroker
from paper_api.brokers.paper_adapter import PaperBrokerAdapter


@dataclass(frozen=True)
class ToolResult:
    """A tool's returned data, refusal, or confirmation-gated proposal."""

    ok: bool
    data: dict | list | None
    error: str | None = None
    requires_confirmation: bool = False
    confirmation_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for one callable assistant tool."""

    name: str
    description: str
    input_schema: dict
    requires_confirmation: bool
    category: Literal["read", "write_paper", "write_broker"]


ToolFunction = Callable[..., ToolResult]
_TOOLS: dict[str, tuple[ToolSpec, ToolFunction]] = {}


@dataclass
class PendingConfirmation:
    """A short-lived, single-use write proposal awaiting user confirmation."""

    confirmation_id: str
    tool_name: str
    args: dict
    created_at: float


_PENDING_CONFIRMATIONS: dict[str, PendingConfirmation] = {}
_PENDING_TTL_SECONDS: float = 300.0
EXECUTION_LOG: list[tuple[datetime, str, str, dict, ToolResult]] = []


def _prune_pending() -> None:
    now = time.time()
    stale = [
        confirmation_id
        for confirmation_id, pending in _PENDING_CONFIRMATIONS.items()
        if now - pending.created_at > _PENDING_TTL_SECONDS
    ]
    for confirmation_id in stale:
        del _PENDING_CONFIRMATIONS[confirmation_id]


def store_pending(confirmation_id: str, tool_name: str, args: dict) -> None:
    """Store a proposal for five minutes before it must be confirmed."""
    _prune_pending()
    _PENDING_CONFIRMATIONS[confirmation_id] = PendingConfirmation(
        confirmation_id=confirmation_id,
        tool_name=tool_name,
        args=dict(args),
        created_at=time.time(),
    )


def consume_pending(confirmation_id: str) -> PendingConfirmation | None:
    """Remove and return a pending proposal, making confirmation single-use."""
    _prune_pending()
    return _PENDING_CONFIRMATIONS.pop(confirmation_id, None)


def register_tool(spec: ToolSpec, fn: ToolFunction) -> None:
    """Register or replace a tool by its public name."""
    _TOOLS[spec.name] = (spec, fn)


def list_tools() -> list[ToolSpec]:
    """Return registered tool specs in registration order."""
    return [spec for spec, _ in _TOOLS.values()]


def get_tool(name: str) -> tuple[ToolSpec, ToolFunction] | None:
    """Return a tool's metadata and callable, if registered."""
    return _TOOLS.get(name)


def execute_confirmed(
    confirmation_id: str, tool_name: str, args: dict
) -> ToolResult:
    """Execute a previously proposed write action after verifying its token.

    The stored proposal is consumed before validation, making every token
    single-use even when the request has expired, mismatched, or later fails.
    Broker gates and market freshness are checked again by the execution helpers.
    """
    pending = consume_pending(confirmation_id)
    if pending is None:
        result = ToolResult(
            ok=False,
            data=None,
            error="confirmation_id not found or expired (5 min TTL)",
        )
        _log_execution(confirmation_id, tool_name, args, result)
        return result
    if pending.tool_name != tool_name:
        result = ToolResult(
            ok=False,
            data=None,
            error=f"tool_name mismatch: expected {pending.tool_name!r}",
        )
        _log_execution(confirmation_id, tool_name, args, result)
        return result
    if pending.args != args:
        result = ToolResult(
            ok=False, data=None, error="args do not match the proposal"
        )
        _log_execution(confirmation_id, tool_name, args, result)
        return result

    dispatch = {
        "set_daily_target": _execute_set_daily_target,
        "set_high_risk_fraction": _execute_set_high_risk_fraction,
        "cancel_manual_action": _execute_cancel_manual_action,
        "place_broker_order": _execute_place_broker_order,
        "cancel_broker_order": _execute_cancel_broker_order,
        "close_broker_position": _execute_close_broker_position,
    }
    fn = dispatch.get(tool_name)
    if fn is None:
        result = ToolResult(
            ok=False,
            data=None,
            error=f"tool {tool_name!r} cannot be executed",
        )
        _log_execution(confirmation_id, tool_name, args, result)
        return result
    try:
        result = fn(args)
    except Exception as exc:
        result = ToolResult(ok=False, data=None, error=str(exc))
    _log_execution(confirmation_id, tool_name, args, result)
    return result


def _log_execution(
    confirmation_id: str, tool_name: str, args: dict, result: ToolResult
) -> None:
    timestamp = datetime.now(timezone.utc)
    logged_args = dict(args)
    EXECUTION_LOG.append(
        (timestamp, confirmation_id, tool_name, logged_args, result)
    )
    print(
        f"[assistant-execution] {timestamp.isoformat()} confirmation_id="
        f"{confirmation_id} tool={tool_name} args={logged_args!r} "
        f"ok={result.ok} error={result.error!r}",
        file=sys.stderr,
        flush=True,
    )


def _app_endpoint(path: str):
    from paper_api.app import app

    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise RuntimeError(f"API route {path!r} is not registered")


def _execute_set_daily_target(args: dict) -> ToolResult:
    from paper_api.schemas import DailyTargetConfigRequest

    endpoint = _app_endpoint("/api/daily-target/config")
    response = endpoint(
        DailyTargetConfigRequest(target_amount=args["target_amount"]),
        mode="daily_target",
    )
    return ToolResult(ok=True, data=jsonable_encoder(response))


def _execute_set_high_risk_fraction(args: dict) -> ToolResult:
    from paper_api.schemas import HighRiskConfigRequest

    endpoint = _app_endpoint("/api/high-risk/config")
    response = endpoint(
        HighRiskConfigRequest(risk_fraction=args["risk_fraction"]),
        mode="high_risk",
    )
    return ToolResult(ok=True, data=jsonable_encoder(response))


def _execute_cancel_manual_action(args: dict) -> ToolResult:
    del args
    response = _app_endpoint("/api/manual/cancel")(mode="manual")
    return ToolResult(ok=True, data=jsonable_encoder(response))


def _execute_place_broker_order(args: dict) -> ToolResult:
    broker = args["broker"]
    instrument = args["instrument"]
    adapter, _environment = _check_broker_gate(broker, instrument)
    _check_market_open(broker, adapter, instrument)

    side = args["side"]
    order_type = args["order_type"]
    quantity = args["quantity"]
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    if order_type not in {"market", "limit"}:
        raise ValueError("order_type must be 'market' or 'limit'")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        raise ValueError("quantity must be a number")
    quantity = float(quantity)
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError("quantity must be finite and greater than 0")

    limit_price = args.get("limit_price")
    if order_type == "limit":
        if isinstance(limit_price, bool) or not isinstance(limit_price, (int, float)):
            raise ValueError("limit orders require a numeric limit_price")
        limit_price = float(limit_price)
        if not math.isfinite(limit_price) or limit_price <= 0:
            raise ValueError("limit_price must be finite and greater than 0")

    request = OrderRequest(
        client_order_id=str(uuid4()),
        instrument=instrument,
        side=side,
        order_type=order_type,
        quantity=quantity,
        limit_price=limit_price,
    )
    result = adapter.place_order(request)
    return ToolResult(ok=True, data=jsonable_encoder(result))


def _execute_cancel_broker_order(args: dict) -> ToolResult:
    broker = args["broker"]
    _adapter, _environment = _check_broker_gate(
        broker, _default_gate_instrument(broker)
    )
    client_order_id = args["client_order_id"]
    if not isinstance(client_order_id, str) or not client_order_id.strip():
        raise ValueError("client_order_id must be a non-empty string")
    cancelled = _adapter.cancel_order(client_order_id)
    return ToolResult(
        ok=True,
        data={"cancelled": bool(cancelled), "client_order_id": client_order_id},
    )


def _execute_close_broker_position(args: dict) -> ToolResult:
    broker = args["broker"]
    instrument = args["instrument"]
    adapter, _environment = _check_broker_gate(broker, instrument)
    _check_market_open(broker, adapter, instrument)
    result = adapter.close_position(instrument)
    return ToolResult(ok=True, data=jsonable_encoder(result))


def _app_and_registry():
    # Import lazily so importing the tool registry does not load datasets or
    # construct any sessions. The API's registry remains the session authority.
    from paper_api.app import app

    return app, app.state.modes


def _route(path: str):
    from paper_api.app import app

    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise RuntimeError(f"API route {path!r} is not registered")


def _tool_error(exc: Exception) -> ToolResult:
    return ToolResult(ok=False, data=None, error=str(exc))


def _broker_status(exc: Exception) -> ToolResult:
    if isinstance(exc, LiveTradingDisabled):
        status = "disabled"
    elif isinstance(exc, BrokerUnavailable):
        status = "unavailable"
    elif isinstance(exc, OrderRejected):
        status = "error"
    else:
        return _tool_error(exc)
    return ToolResult(ok=True, data={"status": status, "reason": str(exc)})


def get_paper_balance() -> ToolResult:
    """Read the standard paper account through the LiveBroker adapter."""
    try:
        _app, registry = _app_and_registry()
        session = registry.session("standard")
        snapshot = PaperBrokerAdapter(session).get_balance()
        return ToolResult(ok=True, data=jsonable_encoder(snapshot))
    except Exception as exc:
        return _tool_error(exc)


def get_paper_positions() -> ToolResult:
    """Read open positions from the standard paper session."""
    try:
        _app, registry = _app_and_registry()
        positions = PaperBrokerAdapter(registry.session("standard")).get_positions()
        return ToolResult(ok=True, data=jsonable_encoder(positions))
    except Exception as exc:
        return _tool_error(exc)


def get_paper_trades(limit: int = 20) -> ToolResult:
    """Read the last N closed trades using the API's trade projection."""
    try:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        response = _route("/api/trades")()
        data = jsonable_encoder(response)
        return ToolResult(ok=True, data=data.get("trades", [])[-limit:] if limit else [])
    except Exception as exc:
        return _tool_error(exc)


def get_broker_balance(broker: str) -> ToolResult:
    """Read a live broker balance, returning an explicit status when gated."""
    try:
        adapter = _broker_adapter(broker)
        return ToolResult(ok=True, data=jsonable_encoder(adapter.get_balance()))
    except Exception as exc:
        return _broker_status(exc)


def get_broker_positions(broker: str) -> ToolResult:
    """Read positions from a live broker, returning an explicit gate status."""
    try:
        adapter = _broker_adapter(broker)
        return ToolResult(ok=True, data=jsonable_encoder(adapter.get_positions()))
    except Exception as exc:
        return _broker_status(exc)


def _broker_adapter(broker: str):
    if broker == "mt5_demo":
        return MT5LiveBroker()
    if broker == "binance_testnet":
        return BinanceLiveBroker(environment=BinanceEnvironment.TESTNET)
    raise ValueError("broker must be 'mt5_demo' or 'binance_testnet'")


def get_market_snapshot(instrument: str) -> ToolResult:
    """Return the latest candle and its instrument metadata from /api/market."""
    try:
        response = _route("/api/market")(
            start=None,
            end=None,
            limit=1,
            instrument=instrument,
        )
        projected = jsonable_encoder(response)
        candles = projected.get("candles", [])
        if not candles:
            raise ValueError(f"no market candles are available for {instrument}")
        metadata = projected["metadata"]
        candle = candles[-1]
        return ToolResult(
            ok=True,
            data={
                "asset": metadata["asset"],
                "market_type": metadata["market_type"],
                "last_candle": {
                    key: candle[key]
                    for key in ("open", "high", "low", "close", "timestamp")
                },
            },
        )
    except Exception as exc:
        return _tool_error(exc)


def get_latest_signal(instrument: str = "BTC/USDT") -> ToolResult:
    """Return the strategy's latest signal for a registered instrument."""
    try:
        if instrument == "BTC/USDT":
            response = _route("/api/signal")()
            signal = jsonable_encoder(response)
            return ToolResult(
                ok=True,
                data={
                    key: signal[key]
                    for key in (
                        "asset", "signal", "reason", "price", "support",
                        "resistance", "trend",
                    )
                },
            )

        from crypto_paper_lab.researchguard import (
            _instrument_entry,
            load_registry,
        )
        from paper_api import marketdata, signals

        registry_data = load_registry()
        instrument_entry = _instrument_entry(registry_data, instrument)
        dataset_path = instrument_entry.get("dataset_path")
        market_type = instrument_entry.get("market_type")
        candles = marketdata.load_research_candles(
            dataset_path, market_type=market_type
        )
        _app, modes = _app_and_registry()
        replay_session = modes.session("standard", instrument=instrument)
        result = signals.resolve_signal(candles, replay_session.config)
        return ToolResult(
            ok=True,
            data={
                "asset": replay_session.config.asset,
                "signal": result.side,
                "reason": result.reason,
                "price": result.price,
                "support": result.support,
                "resistance": result.resistance,
                "trend": result.trend,
            },
        )
    except Exception as exc:
        return _tool_error(exc)


def get_research_status() -> ToolResult:
    """Return registered instruments from the same projection as the API."""
    try:
        from paper_api import research_view

        instruments = [
            view.as_record() for view in research_view.instruments_projection()
        ]
        return ToolResult(
            ok=True,
            data={"instruments": jsonable_encoder(instruments), "count": len(instruments)},
        )
    except Exception as exc:
        return _tool_error(exc)


def get_live_config() -> ToolResult:
    """Return the operator-editable live trading gates as stored."""
    try:
        return ToolResult(ok=True, data=load_live_config())
    except Exception as exc:
        return _tool_error(exc)


def _proposal(data: dict) -> ToolResult:
    return ToolResult(
        ok=True,
        data={"proposed_action": data},
        requires_confirmation=True,
        confirmation_id=str(uuid4()),
    )


def set_daily_target(target_amount: float) -> ToolResult:
    """Propose changing Daily Target's paper-only dollar target."""
    try:
        if isinstance(target_amount, bool) or not isinstance(target_amount, (int, float)):
            raise ValueError("target_amount must be a number")
        target_amount = float(target_amount)
        if not math.isfinite(target_amount) or target_amount <= 0:
            raise ValueError("target_amount must be finite and greater than 0")
        _app, registry = _app_and_registry()
        session = registry.daily_target_session()
        previous = session.tracker.target_amount
        result = _proposal({"target_amount": target_amount, "previously": previous})
        store_pending(
            result.confirmation_id,
            "set_daily_target",
            {"target_amount": target_amount},
        )
        return result
    except Exception as exc:
        return _tool_error(exc)


def set_high_risk_fraction(risk_fraction: float) -> ToolResult:
    """Propose changing High-Risk paper sizing, subject to engine validation."""
    try:
        if isinstance(risk_fraction, bool) or not isinstance(risk_fraction, (int, float)):
            raise ValueError("risk_fraction must be a number")
        risk_fraction = float(risk_fraction)
        if not math.isfinite(risk_fraction) or not 0 < risk_fraction <= 1.0:
            raise ValueError("risk_fraction must be greater than 0 and at most 1.0")
        _app, registry = _app_and_registry()
        previous = registry.high_risk_session().risk_fraction
        result = _proposal({"risk_fraction": risk_fraction, "previously": previous})
        store_pending(
            result.confirmation_id,
            "set_high_risk_fraction",
            {"risk_fraction": risk_fraction},
        )
        return result
    except Exception as exc:
        return _tool_error(exc)


def cancel_manual_action() -> ToolResult:
    """Propose cancelling a pending Manual paper action."""
    try:
        result = _proposal({"cancelled": True})
        store_pending(result.confirmation_id, "cancel_manual_action", {})
        return result
    except Exception as exc:
        return _tool_error(exc)


def place_paper_order(
    instrument: str, side: str, quantity: float
) -> ToolResult:
    """Refuse order-style paper execution because paper replay is step-driven."""
    if not isinstance(instrument, str) or not instrument.strip():
        return _tool_error(ValueError("instrument must be a non-empty string"))
    if side not in {"buy", "sell"}:
        return _tool_error(ValueError("side must be 'buy' or 'sell'"))
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        return _tool_error(ValueError("quantity must be a number"))
    if not math.isfinite(float(quantity)) or float(quantity) <= 0:
        return _tool_error(ValueError("quantity must be finite and greater than 0"))
    return ToolResult(
        ok=False,
        data={
            "note": "paper engine is step-driven; use /api/replay/step to advance"
        },
        error=(
            "paper engine is step-driven; use /api/replay/step to advance. "
            "It does not accept orders through LiveBroker."
        ),
    )


def _validate_broker(broker: str) -> tuple[str, str]:
    if broker == "mt5_demo":
        return "mt5_demo", "mt5_demo"
    if broker == "binance_testnet":
        return BinanceEnvironment.TESTNET, "BTC/USDT"
    raise ValueError("broker must be 'mt5_demo' or 'binance_testnet'")


def _check_broker_gate(broker: str, instrument: str) -> tuple[object, str]:
    environment, _default_instrument = _validate_broker(broker)
    if not is_live_trading_enabled():
        raise LiveTradingDisabled("LIVE_TRADING_ENABLED is not 'true'; live broker is disabled")
    check_live_gate(instrument=instrument, requested_environment=environment)
    return _broker_adapter(broker), environment


def _check_market_open(broker: str, adapter, instrument: str) -> float | None:
    """Require a fresh broker tick before proposing a broker write."""
    if broker == "mt5_demo":
        symbol = adapter.config.symbol_mapping.get(instrument)
        if symbol is None:
            raise OrderRejected(f"no symbol mapping for {instrument}")
        adapter._ensure_mt5()
        tick = adapter._mt5.symbol_info_tick(symbol)
        if tick is None or not getattr(tick, "time", 0):
            raise OrderRejected(f"market closed for {symbol}: no current tick available")
        age = int(time.time()) - int(tick.time)
        if age > 300:
            raise OrderRejected(
                f"market closed for {symbol}: last tick is {age}s old (>300s threshold)"
            )
        symbol_info = adapter._mt5.symbol_info(symbol)
        if symbol_info is None:
            raise OrderRejected(f"symbol {symbol} not found")
        if symbol_info.trade_mode != adapter._mt5.SYMBOL_TRADE_MODE_FULL:
            raise OrderRejected(
                f"market closed for {symbol}: trade_mode={symbol_info.trade_mode}"
            )
        return float(tick.ask or tick.bid)

    adapter._ensure_client()
    symbol = instrument.replace("/", "")
    trades = adapter._client.get_recent_trades(symbol=symbol, limit=1)
    if not trades:
        raise OrderRejected(f"market closed for {symbol}: no recent trade available")
    trade_time = int(trades[-1].get("time", 0))
    age = int(time.time() * 1000) - trade_time
    if not trade_time or age > 300_000:
        raise OrderRejected(
            f"market closed for {symbol}: last trade is {age // 1000}s old (>300s threshold)"
        )
    return float(trades[-1]["price"])


def place_broker_order(
    broker: str,
    instrument: str,
    side: str,
    order_type: str,
    quantity: float,
    limit_price: float | None = None,
) -> ToolResult:
    """Propose a gated live order after validating the current market tick."""
    try:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if order_type not in {"market", "limit"}:
            raise ValueError("order_type must be 'market' or 'limit'")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            raise ValueError("quantity must be a number")
        quantity = float(quantity)
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("quantity must be finite and greater than 0")
        if order_type == "limit":
            if isinstance(limit_price, bool) or not isinstance(limit_price, (int, float)):
                raise ValueError("limit orders require a numeric limit_price")
            limit_price = float(limit_price)
            if not math.isfinite(limit_price) or limit_price <= 0:
                raise ValueError("limit_price must be finite and greater than 0")

        adapter, _environment = _check_broker_gate(broker, instrument)
        market_price = _check_market_open(broker, adapter, instrument)
        request = OrderRequest(
            client_order_id=str(uuid4()),
            instrument=instrument,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )
        result = _proposal(
            {
                "broker": broker,
                "request": jsonable_encoder(request),
                "market_price": market_price,
            }
        )
        pending_args = {
            "broker": broker,
            "instrument": instrument,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
        }
        if limit_price is not None:
            pending_args["limit_price"] = limit_price
        store_pending(result.confirmation_id, "place_broker_order", pending_args)
        return result
    except Exception as exc:
        return _tool_error(exc)


def cancel_broker_order(broker: str, client_order_id: str) -> ToolResult:
    """Propose cancelling a gated broker order; does not send a cancellation."""
    try:
        if not isinstance(client_order_id, str) or not client_order_id.strip():
            raise ValueError("client_order_id must be a non-empty string")
        _adapter, _environment = _check_broker_gate(broker, _default_gate_instrument(broker))
        result = _proposal({"broker": broker, "client_order_id": client_order_id})
        store_pending(
            result.confirmation_id,
            "cancel_broker_order",
            {"broker": broker, "client_order_id": client_order_id},
        )
        return result
    except Exception as exc:
        return _tool_error(exc)


def close_broker_position(broker: str, instrument: str) -> ToolResult:
    """Propose closing a gated broker position; does not send a close order."""
    try:
        if not isinstance(instrument, str) or not instrument.strip():
            raise ValueError("instrument must be a non-empty string")
        if broker == "binance_testnet":
            raise OrderRejected(
                "Binance Spot does not support position close; use place_order with the opposite side"
            )
        adapter, _environment = _check_broker_gate(broker, instrument)
        _check_market_open(broker, adapter, instrument)
        result = _proposal({"broker": broker, "instrument": instrument})
        store_pending(
            result.confirmation_id,
            "close_broker_position",
            {"broker": broker, "instrument": instrument},
        )
        return result
    except Exception as exc:
        return _tool_error(exc)


def _default_gate_instrument(broker: str) -> str:
    if broker == "mt5_demo":
        return "EUR/USD"
    if broker == "binance_testnet":
        return "BTC/USDT"
    raise ValueError("broker must be 'mt5_demo' or 'binance_testnet'")


_EMPTY_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
_BROKER_SCHEMA = {
    "type": "object",
    "properties": {
        "broker": {"type": "string", "enum": ["mt5_demo", "binance_testnet"]}
    },
    "required": ["broker"],
    "additionalProperties": False,
}


def _register(
    name: str,
    description: str,
    schema: dict,
    category: Literal["read", "write_paper", "write_broker"],
    fn: ToolFunction,
) -> None:
    register_tool(
        ToolSpec(
            name=name,
            description=description,
            input_schema=schema,
            requires_confirmation=category != "read",
            category=category,
        ),
        fn,
    )


_register("get_paper_balance", "Read the standard paper account balance.", _EMPTY_SCHEMA, "read", get_paper_balance)
_register("get_paper_positions", "Read open positions in the standard paper session.", _EMPTY_SCHEMA, "read", get_paper_positions)
_register("get_paper_trades", "Read the most recent closed paper trades.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20, "minimum": 0}}, "additionalProperties": False}, "read", get_paper_trades)
_register("get_broker_balance", "Read a live broker balance, including gate status.", _BROKER_SCHEMA, "read", get_broker_balance)
_register("get_broker_positions", "Read positions from a live broker.", _BROKER_SCHEMA, "read", get_broker_positions)
_register("get_market_snapshot", "Read the latest available candle for an instrument.", {"type": "object", "properties": {"instrument": {"type": "string"}}, "required": ["instrument"], "additionalProperties": False}, "read", get_market_snapshot)
_register("get_latest_signal", "Read the latest strategy signal for an instrument.", {"type": "object", "properties": {"instrument": {"type": "string", "default": "BTC/USDT"}}, "additionalProperties": False}, "read", get_latest_signal)
_register("get_research_status", "Read registered instrument research status.", _EMPTY_SCHEMA, "read", get_research_status)
_register("get_live_config", "Read the current live trading gates.", _EMPTY_SCHEMA, "read", get_live_config)
_register("set_daily_target", "Propose a Daily Target paper goal change.", {"type": "object", "properties": {"target_amount": {"type": "number", "exclusiveMinimum": 0}}, "required": ["target_amount"], "additionalProperties": False}, "write_paper", set_daily_target)
_register("set_high_risk_fraction", "Propose a High-Risk paper sizing change.", {"type": "object", "properties": {"risk_fraction": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}}, "required": ["risk_fraction"], "additionalProperties": False}, "write_paper", set_high_risk_fraction)
_register("cancel_manual_action", "Propose cancelling a pending manual paper action.", _EMPTY_SCHEMA, "write_paper", cancel_manual_action)
_register("place_paper_order", "Refuse order-style paper execution; paper replay is step-driven.", {"type": "object", "properties": {"instrument": {"type": "string"}, "side": {"type": "string", "enum": ["buy", "sell"]}, "quantity": {"type": "number", "exclusiveMinimum": 0}}, "required": ["instrument", "side", "quantity"], "additionalProperties": False}, "write_paper", place_paper_order)
_register("place_broker_order", "Propose a live broker order only after all gates and tick freshness pass.", {"type": "object", "properties": {"broker": {"type": "string", "enum": ["mt5_demo", "binance_testnet"]}, "instrument": {"type": "string"}, "side": {"type": "string", "enum": ["buy", "sell"]}, "order_type": {"type": "string", "enum": ["market", "limit"]}, "quantity": {"type": "number", "exclusiveMinimum": 0}, "limit_price": {"type": "number", "exclusiveMinimum": 0}}, "required": ["broker", "instrument", "side", "order_type", "quantity"], "additionalProperties": False}, "write_broker", place_broker_order)
_register("cancel_broker_order", "Propose a gated live broker order cancellation.", {"type": "object", "properties": {"broker": {"type": "string", "enum": ["mt5_demo", "binance_testnet"]}, "client_order_id": {"type": "string", "minLength": 1}}, "required": ["broker", "client_order_id"], "additionalProperties": False}, "write_broker", cancel_broker_order)
_register("close_broker_position", "Propose closing a live broker position after gate and tick checks.", {"type": "object", "properties": {"broker": {"type": "string", "enum": ["mt5_demo", "binance_testnet"]}, "instrument": {"type": "string"}}, "required": ["broker", "instrument"], "additionalProperties": False}, "write_broker", close_broker_position)


MAX_READ_TOOLS = len([tool for tool in _TOOLS.values() if tool[0].category == "read"])
MAX_WRITE_TOOLS = len([tool for tool in _TOOLS.values() if tool[0].category != "read"])
