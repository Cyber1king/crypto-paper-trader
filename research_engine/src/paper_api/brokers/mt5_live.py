"""MT5 adapter. Uses MetaTrader5 Python package (Windows only). Connects to a running, already-logged-in MT5 terminal. LIVE_TRADING_ENABLED=true and the per-instrument gate in live_config.json must both be enabled. Real-money trading on MT5 requires all four locks.

The terminal must already be running and authenticated before this adapter is used. This adapter does not launch MT5.

This adapter targets the running MT5 terminal. It does not launch it. The terminal must be open and logged in for any call to succeed. Real-money execution requires all four locks AND the terminal's own trade authorization.

The broker identifier is ``mt5_demo`` to match the configured demo environment. The balance-only call gates against EUR/USD, the default Forex instrument; order calls gate against the requested instrument.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .base import (
    AccountSnapshot,
    BrokerError,
    BrokerUnavailable,
    LiveBroker,
    LiveTradingDisabled,
    OrderRejected,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    is_live_trading_enabled,
)
from .live_config import check_live_gate
from .risk import RiskLimits, RiskState, check_order


@dataclass(frozen=True)
class MT5Config:
    """MT5 symbol aliases and execution parameters for this system."""

    symbol_mapping: dict[str, str] = field(
        default_factory=lambda: {
            "BTC/USDT": "BTCUSD",
            "EUR/USD": "EURUSD",
            "GBP/USD": "GBPUSD",
        }
    )
    magic: int = 505852
    deviation_points: int = 20


class MT5LiveBroker(LiveBroker):
    """Broker adapter attached to an already running and logged-in MT5 terminal."""

    def __init__(self, config: MT5Config | None = None) -> None:
        self.config = config or MT5Config()
        self._mt5 = None

    def broker_name(self) -> str:
        """Return ``mt5_demo`` to match the live configuration environment."""
        return "mt5_demo"

    def _ensure_mt5(self) -> None:
        """Attach to the running terminal after the global live lock passes."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; MT5 broker is disabled"
            )
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5
            except Exception as exc:
                raise BrokerUnavailable(f"MetaTrader5 package unavailable: {exc}") from exc
            self._mt5 = mt5
        try:
            initialized = self._mt5.initialize()
        except Exception as exc:
            raise BrokerUnavailable(f"MT5 initialize failed: {exc}") from exc
        if not initialized:
            raise BrokerUnavailable(f"MT5 initialize failed: {self._mt5.last_error()}")

    def get_balance(self) -> AccountSnapshot:
        """Return a live account snapshot after the default-instrument gate passes."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; MT5 broker is disabled"
            )
        # Balance has no instrument argument, so EUR/USD is the documented default gate.
        check_live_gate(instrument="EUR/USD", requested_environment="mt5_demo")
        self._ensure_mt5()
        try:
            info = self._mt5.account_info()
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc
        if info is None:
            raise BrokerUnavailable("MT5 account_info returned None")
        return AccountSnapshot(
            broker=self.broker_name(),
            account_id=str(info.login),
            currency=info.currency,
            balance=float(info.balance),
            equity=float(info.equity),
            free_margin=float(info.margin_free),
            used_margin=float(info.margin),
            leverage=int(info.leverage) if info.leverage else None,
            timestamp=datetime.now(timezone.utc),
            stale_since=None,
        )

    def get_positions(self) -> list[Position]:
        """Return positions tagged with this adapter's MT5 magic number."""
        self._ensure_mt5()
        try:
            broker_positions = self._mt5.positions_get()
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc
        if broker_positions is None:
            return []

        reverse_mapping = {
            symbol: instrument
            for instrument, symbol in self.config.symbol_mapping.items()
        }
        positions: list[Position] = []
        for position in broker_positions:
            instrument = reverse_mapping.get(position.symbol)
            if instrument is None or position.magic != self.config.magic:
                continue
            positions.append(
                Position(
                    instrument=instrument,
                    side="long" if position.type == 0 else "short",
                    quantity=float(position.volume),
                    entry_price=float(position.price_open),
                    entry_time=datetime.fromtimestamp(position.time, tz=timezone.utc),
                    unrealized_pnl=float(position.profit),
                    broker_position_id=str(position.ticket),
                )
            )
        return positions

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit a gated MT5 order; risk checks use conservative placeholder state."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; MT5 broker is disabled"
            )
        check_live_gate(
            instrument=request.instrument,
            requested_environment="mt5_demo",
        )
        symbol = self.config.symbol_mapping.get(request.instrument)
        if symbol is None:
            raise OrderRejected(f"no symbol mapping for {request.instrument}")

        risk_state = RiskState(
            starting_equity_today=1.0,
            current_equity=1.0,
            realized_pnl_today=0.0,
            open_positions_count=0,
            positions_per_instrument={},
            total_exposure=0.0,
            kill_switch_engaged=False,
        )
        current_price = request.limit_price if request.limit_price is not None else 0.0
        if current_price > 0:
            check_order(
                state=risk_state,
                limits=RiskLimits(),
                request=request,
                current_price=current_price,
                equity=1.0,
            )

        self._ensure_mt5()
        try:
            symbol_info = self._mt5.symbol_info(symbol)
            if symbol_info is None or not symbol_info.visible:
                raise OrderRejected(f"symbol {symbol} not visible in Market Watch")

            if request.order_type == "market":
                tick = self._mt5.symbol_info_tick(symbol)
                if tick is None:
                    raise BrokerUnavailable(f"MT5 has no current tick for {symbol}")
                action = self._mt5.TRADE_ACTION_DEAL
                order_type = (
                    self._mt5.ORDER_TYPE_BUY
                    if request.side == "buy"
                    else self._mt5.ORDER_TYPE_SELL
                )
                price = float(tick.ask if request.side == "buy" else tick.bid)
            else:
                if request.limit_price is None:
                    raise OrderRejected("limit orders require limit_price")
                action = self._mt5.TRADE_ACTION_PENDING
                order_type = (
                    self._mt5.ORDER_TYPE_BUY_LIMIT
                    if request.side == "buy"
                    else self._mt5.ORDER_TYPE_SELL_LIMIT
                )
                price = float(request.limit_price)

            mt5_request = {
                "action": action,
                "symbol": symbol,
                "volume": float(request.quantity),
                "type": order_type,
                "price": price,
                "deviation": self.config.deviation_points,
                "magic": self.config.magic,
                "comment": request.client_order_id[:31],
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": symbol_info.filling_mode,
            }
            if request.stop_price is not None:
                mt5_request["sl"] = float(request.stop_price)
            result = self._mt5.order_send(mt5_request)
        except (OrderRejected, BrokerUnavailable):
            raise
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc

        if result is None:
            raise OrderRejected("order_send returned None")
        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            raise OrderRejected(f"MT5 retcode {result.retcode}: {result.comment}")
        return OrderResult(
            client_order_id=request.client_order_id,
            broker_order_id=str(result.order),
            status="filled",
            filled_quantity=float(result.volume),
            average_fill_price=float(result.price),
            slippage=None,
            fee=None,
            message="",
            raw_response={
                "retcode": result.retcode,
                "deal": result.deal,
                "order": result.order,
            },
        )

    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel a matching pending order created by this system, if present."""
        self._ensure_mt5()
        try:
            pending_orders = self._mt5.orders_get()
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc
        if pending_orders is None:
            return False
        for order in pending_orders:
            if (
                order.comment == client_order_id[:31]
                and order.magic == self.config.magic
            ):
                reverse_mapping = {
                    mapped_symbol: mapped_instrument
                    for mapped_instrument, mapped_symbol in self.config.symbol_mapping.items()
                }
                instrument = reverse_mapping.get(order.symbol)
                if instrument is None:
                    return False
                check_live_gate(
                    instrument=instrument,
                    requested_environment="mt5_demo",
                )
                try:
                    result = self._mt5.order_send(
                        {
                            "action": self._mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket,
                        }
                    )
                except Exception as exc:
                    raise BrokerUnavailable(str(exc)) from exc
                return bool(
                    result is not None
                    and result.retcode == self._mt5.TRADE_RETCODE_DONE
                )
        return False

    def close_position(self, instrument: str) -> OrderResult | None:
        """Close the first open MT5 position for this system and instrument."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; MT5 broker is disabled"
            )
        check_live_gate(
            instrument=instrument,
            requested_environment="mt5_demo",
        )
        self._ensure_mt5()
        symbol = self.config.symbol_mapping.get(instrument)
        if symbol is None:
            raise OrderRejected(f"no symbol mapping for {instrument}")
        try:
            positions = self._mt5.positions_get(symbol=symbol)
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc
        if positions is None:
            return None
        position = next(
            (item for item in positions if item.magic == self.config.magic),
            None,
        )
        if position is None:
            return None

        try:
            tick = self._mt5.symbol_info_tick(symbol)
            if tick is None:
                raise BrokerUnavailable(f"MT5 has no current tick for {symbol}")
            is_long = position.type == self._mt5.POSITION_TYPE_BUY
            close_type = (
                self._mt5.ORDER_TYPE_SELL if is_long else self._mt5.ORDER_TYPE_BUY
            )
            close_price = float(tick.bid if is_long else tick.ask)
            client_order_id = str(uuid4())
            close_request = {
                "action": self._mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(position.volume),
                "type": close_type,
                "position": position.ticket,
                "price": close_price,
                "deviation": self.config.deviation_points,
                "magic": self.config.magic,
                "comment": f"close-{client_order_id}"[:31],
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": self._mt5.symbol_info(symbol).filling_mode,
            }
            result = self._mt5.order_send(close_request)
        except BrokerUnavailable:
            raise
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc

        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            if result is None:
                raise OrderRejected("MT5 close order_send returned None")
            raise OrderRejected(f"MT5 close retcode {result.retcode}: {result.comment}")
        return OrderResult(
            client_order_id=client_order_id,
            broker_order_id=str(result.order),
            status="filled",
            filled_quantity=float(result.volume),
            average_fill_price=float(result.price),
            slippage=None,
            fee=None,
            message="",
            raw_response={
                "retcode": result.retcode,
                "deal": result.deal,
                "order": result.order,
            },
        )
