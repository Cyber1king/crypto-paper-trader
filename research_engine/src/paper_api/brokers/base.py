"""Shared contracts for paper and live broker integrations."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
OrderStatus = Literal[
    "requested",
    "sent",
    "acked",
    "partial",
    "filled",
    "rejected",
    "cancelled",
    "expired",
]


@dataclass(frozen=True)
class OrderRequest:
    """An order intent; the caller supplies a unique, stable client order ID."""

    client_order_id: str
    instrument: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    magic: int = 0
    comment: str = ""


@dataclass(frozen=True)
class OrderResult:
    """The broker's outcome for an order request."""

    client_order_id: str
    broker_order_id: str | None
    status: OrderStatus
    filled_quantity: float
    average_fill_price: float | None
    slippage: float | None
    fee: float | None
    message: str
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    """A broker-reported open position."""

    instrument: str
    side: Literal["long", "short"]
    quantity: float
    entry_price: float
    entry_time: datetime
    unrealized_pnl: float | None
    broker_position_id: str | None


@dataclass(frozen=True)
class AccountSnapshot:
    """Account balances and margin at a point in time.

    ``stale_since`` is None for a live snapshot. If set, the snapshot is cached
    and stale, and callers are responsible for checking its age before use.
    """

    broker: str
    account_id: str
    currency: str
    balance: float
    equity: float
    free_margin: float
    used_margin: float
    leverage: int | None
    timestamp: datetime
    stale_since: datetime | None = None


@dataclass(frozen=True)
class Tick:
    """A broker market-data tick."""

    instrument: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: float | None = None


class LiveBroker(ABC):
    """Contract implemented by each broker integration."""

    @abstractmethod
    def broker_name(self) -> str:
        """Return this broker's stable identifier, such as ``paper`` or ``mt5_demo``."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> AccountSnapshot:
        """Return the latest account snapshot.

        A cached snapshot may be returned with ``stale_since`` set; callers must
        inspect that field and decide whether stale account data is acceptable.
        """
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return the broker's currently open positions."""
        raise NotImplementedError

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit an order and return its current result.

        This operation must be idempotent by ``request.client_order_id``. A
        duplicate request must be rejected or return its original result; it
        must never execute the order a second time.
        """
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an order by client order ID; return whether cancellation succeeded."""
        raise NotImplementedError

    @abstractmethod
    def close_position(self, instrument: str) -> OrderResult | None:
        """Close the entire open position for ``instrument``.

        Return the closing order result, or None when there is no position to
        close. Implementations must not partially close the position.
        """
        raise NotImplementedError


class BrokerError(Exception):
    """Base class for broker integration errors."""


class BrokerUnavailable(BrokerError):
    """The broker cannot currently be reached."""


class OrderRejected(BrokerError):
    """The broker rejected an order; ``reason`` carries its explanation."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class LiveTradingDisabled(BrokerError):
    """Real-money execution is not enabled."""


class RiskLimitExceeded(BrokerError):
    """A risk control blocked an action; ``limit_name`` identifies the limit."""

    def __init__(self, limit_name: str) -> None:
        self.limit_name = limit_name
        super().__init__(limit_name)


LIVE_TRADING_ENV_VAR = "LIVE_TRADING_ENABLED"


def is_live_trading_enabled() -> bool:
    """Return whether the live-trading environment switch is exactly ``true``."""
    return os.environ.get(LIVE_TRADING_ENV_VAR, "").strip().lower() == "true"
