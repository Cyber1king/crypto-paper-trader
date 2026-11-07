"""This is a skeleton. It compiles and passes import but the real Binance SDK calls only execute when LIVE_TRADING_ENABLED=true. Real-money production orders are separately gated and refuse to execute even when the environment flag is on. Binance Spot has no positions; the get_positions and close_position implementations are documented stubs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

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


class BinanceEnvironment:
    """Supported Binance endpoint environments."""

    TESTNET = "testnet"
    PRODUCTION = "production"


class BinanceLiveBroker(LiveBroker):
    """Lazy Binance Spot client with explicit live and production safeguards."""

    def __init__(
        self,
        environment: str = BinanceEnvironment.TESTNET,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        self.environment = environment
        self.api_key = api_key or os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")
        self._client = None
        self._positions_cache: list[Position] = []
        self._balance_cache: AccountSnapshot | None = None
        self._order_symbols: dict[str, str] = {}

    def broker_name(self) -> str:
        """Return the identifier for the configured Binance environment."""
        return f"binance_{self.environment}"

    def _ensure_client(self) -> None:
        """Initialize the SDK client only after live access and credentials pass."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; refusing to initialize the Binance client"
            )
        if not self.api_key or not self.api_secret:
            raise BrokerUnavailable("BINANCE_API_KEY / BINANCE_API_SECRET not set")
        if self._client is None:
            try:
                from binance.client import Client

                self._client = Client(
                    self.api_key,
                    self.api_secret,
                    testnet=self.environment == BinanceEnvironment.TESTNET,
                )
            except Exception as exc:
                raise BrokerUnavailable(str(exc)) from exc

    def get_balance(self) -> AccountSnapshot:
        """Fetch and cache the latest USDT balance snapshot from Binance Spot."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; refusing to initialize the Binance client"
            )
        # This adapter's account snapshot is denominated in USDT and targets BTC/USDT.
        check_live_gate(
            instrument="BTC/USDT",
            requested_environment=self.environment,
        )
        self._ensure_client()
        try:
            response = self._client.get_account()
            usdt = next(
                (
                    item
                    for item in response.get("balances", [])
                    if item.get("asset") == "USDT"
                ),
                {},
            )
            free_usdt = float(usdt.get("free", 0.0))
            locked_usdt = float(usdt.get("locked", 0.0))
            total_usdt = free_usdt + locked_usdt
            snapshot = AccountSnapshot(
                broker=self.broker_name(),
                account_id=str(response.get("accountType", "binance")),
                currency="USDT",
                balance=float(total_usdt),
                equity=float(total_usdt),
                free_margin=float(free_usdt),
                used_margin=0.0,
                leverage=None,
                timestamp=datetime.now(timezone.utc),
                stale_since=None,
            )
            self._balance_cache = snapshot
            return snapshot
        except Exception as exc:
            raise BrokerUnavailable(str(exc)) from exc

    def get_positions(self) -> list[Position]:
        """Return no positions because Binance Spot exposes asset balances instead.

        Binance Spot does not expose positions. This method returns [] by design.
        Futures support would require BinanceLiveFuturesBroker.
        """
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; refusing to initialize the Binance client"
            )
        return []

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Place a testnet order; production order execution remains disabled.

        ``risk_state`` is a placeholder. Real risk enforcement requires a
        caller-supplied ``RiskState`` derived from ``AccountSnapshot``. This
        first version is a sanity gate, not a complete risk control.
        """
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; no order was sent"
            )
        if self.environment == BinanceEnvironment.PRODUCTION:
            raise LiveTradingDisabled(
                "Production orders are not yet enabled; this must be explicitly unlocked by the user"
            )
        check_live_gate(
            instrument=request.instrument,
            requested_environment=self.environment,
        )

        # Pre-trade risk check.
        # The state passed in is conservative; it is NOT sourced from a live
        # account snapshot. This is a first-gate sanity check only.
        # When a real AccountSnapshot is available, callers must supply it.
        # RiskState is intentionally instantiated with conservative defaults so
        # that a call without risk context cannot silently bypass the check.
        risk_state = RiskState(
            starting_equity_today=1.0,  # unknown without an account snapshot
            current_equity=1.0,
            realized_pnl_today=0.0,
            open_positions_count=0,
            positions_per_instrument={},
            total_exposure=0.0,
            kill_switch_engaged=False,
        )
        # With a placeholder state, only limits that do not depend on prior state
        # (max_order_notional and, if you supply a real price, max_positions_per_instrument)
        # can be enforced. Enforce those.
        current_price_for_check = request.limit_price if request.limit_price is not None else 0.0
        if current_price_for_check > 0.0:
            check_order(
                state=risk_state,
                limits=RiskLimits(),
                request=request,
                current_price=current_price_for_check,
                equity=risk_state.current_equity,
            )
        self._ensure_client()
        try:
            params: dict[str, Any] = {
                "symbol": request.instrument.replace("/", ""),
                "side": request.side.upper(),
                "type": request.order_type.upper(),
                "quantity": request.quantity,
                "newClientOrderId": request.client_order_id,
            }
            if request.order_type == "limit":
                if request.limit_price is None:
                    raise OrderRejected("limit orders require limit_price")
                params["price"] = request.limit_price
                params["timeInForce"] = "GTC"
            response = self._client.create_order(**params)
        except OrderRejected:
            raise
        except Exception as exc:
            raise OrderRejected(str(exc)) from exc

        self._order_symbols[request.client_order_id] = request.instrument.replace("/", "")
        response_status = str(response.get("status", "")).upper()
        status_map: dict[str, OrderStatus] = {
            "NEW": "acked",
            "PARTIALLY_FILLED": "partial",
            "FILLED": "filled",
            "REJECTED": "rejected",
            "CANCELED": "cancelled",
            "CANCELLED": "cancelled",
            "EXPIRED": "expired",
        }
        status = status_map.get(response_status, "sent")
        filled_quantity = float(response.get("executedQty", 0.0))
        quote_quantity = float(response.get("cummulativeQuoteQty", 0.0))
        average_fill_price = (
            quote_quantity / filled_quantity if filled_quantity else None
        )
        return OrderResult(
            client_order_id=request.client_order_id,
            broker_order_id=(
                str(response["orderId"]) if response.get("orderId") is not None else None
            ),
            status=status,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
            slippage=None,
            fee=None,
            message=(str(response.get("msg", "")) if status == "rejected" else ""),
            raw_response=response,
        )

    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel a known testnet order; report False when it no longer exists."""
        if not is_live_trading_enabled():
            raise LiveTradingDisabled(
                "LIVE_TRADING_ENABLED is not 'true'; no order was sent"
            )
        if self.environment == BinanceEnvironment.PRODUCTION:
            raise LiveTradingDisabled(
                "Production order cancellation is not yet enabled; this must be explicitly unlocked by the user"
            )
        self._ensure_client()
        symbol = self._order_symbols.get(client_order_id)
        if symbol is None:
            return False
        try:
            self._client.cancel_order(
                symbol=symbol,
                origClientOrderId=client_order_id,
            )
            return True
        except Exception as exc:
            if getattr(exc, "code", None) in (-2011, -2013):
                return False
            raise BrokerUnavailable(str(exc)) from exc

    def close_position(self, instrument: str) -> OrderResult | None:
        """Refuse position close because Binance Spot has no position primitive."""
        raise OrderRejected(
            "Binance Spot does not support position close; use place_order with the opposite side"
        )
