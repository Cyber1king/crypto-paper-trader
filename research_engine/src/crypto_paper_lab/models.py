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

    @property
    def pnl(self) -> float | None:
        """Return gross P&L before trading costs."""

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
        """Return P&L after trading costs."""

        if self.pnl is None:
            return None

        return self.pnl - self.costs
