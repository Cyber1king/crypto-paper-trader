from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    timestamp: datetime
    side: Literal["long", "short", "flat"]
    reason: str
    price: float
    support: float
    resistance: float
    trend: Literal["up", "down", "sideways"]
    breakout: bool = False
    retest: bool = False


@dataclass
class PaperTrade:
    side: Literal["long", "short"]
    entry_time: datetime
    entry_price: float
    quantity: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    reason: str = ""
    costs: float = 0.0
    exit_reason: str = ""
    bars_held: int = 0

    #: Unadjusted reference prices as seen on the chart. Under the
    #: ``fill_price`` execution model these differ from ``entry_price`` and
    #: ``exit_price``, which record the prices actually paid or received.
    raw_entry_price: float | None = None
    raw_exit_price: float | None = None

    #: Execution friction broken out for reporting. ``costs`` is the amount
    #: actually deducted from the recorded gross P&L; under ``fill_price``
    #: the spread and slippage are already embedded in the fill prices and
    #: are therefore attributed here rather than deducted a second time.
    fee_total: float = 0.0
    slippage_total: float = 0.0
    spread_total: float = 0.0

    @property
    def pnl(self) -> float | None:
        """Return gross P&L at the recorded prices, before fees.

        Under ``cost_deduction`` the recorded prices are the raw chart
        prices, so this is gross before all friction. Under ``fill_price``
        the recorded prices already include spread and slippage, so this is
        gross before fees only. Use ``total_friction`` for the full cost.
        """

        if self.exit_price is None:
            return None

        direction = 1 if self.side == "long" else -1

        return (
            (self.exit_price - self.entry_price)
            * self.quantity
            * direction
        )

    @property
    def net_pnl(self) -> float | None:
        """Return P&L after the deducted portion of trading costs."""

        if self.pnl is None:
            return None

        return self.pnl - self.costs

    @property
    def total_friction(self) -> float | None:
        """Return all execution friction: fees plus spread plus slippage.

        This is the total cost of trading the position regardless of how the
        execution model distributes it between the fill price and ``costs``.
        """

        if self.net_pnl is None:
            return None

        return (
            self.fee_total + self.spread_total + self.slippage_total
        )
