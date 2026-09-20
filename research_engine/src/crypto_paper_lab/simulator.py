from datetime import datetime

from .models import PaperTrade, Signal


class PaperBroker:
    """In-memory simulator. It has no exchange client and cannot place real orders."""

    def __init__(self, starting_balance: float = 10_000.0) -> None:
        if starting_balance <= 0:
            raise ValueError("starting balance must be positive")
        self.starting_balance = starting_balance
        self.cash = starting_balance
        self.open_trade: PaperTrade | None = None
        self.journal: list[PaperTrade] = []

    def open_from_signal(self, signal: Signal, risk_fraction: float = 0.01) -> PaperTrade:
        if signal.side == "flat":
            raise ValueError("flat signals cannot open a paper trade")
        if self.open_trade:
            raise ValueError("a paper trade is already open")
        if not 0 < risk_fraction <= 1:
            raise ValueError("risk_fraction must be between 0 and 1")
        quantity = (self.cash * risk_fraction) / signal.price
        self.open_trade = PaperTrade(
            side=signal.side,
            entry_time=signal.timestamp,
            entry_price=signal.price,
            quantity=quantity,
            reason=signal.reason,
        )
        return self.open_trade

    def close(self, price: float, timestamp: datetime) -> PaperTrade:
        if not self.open_trade:
            raise ValueError("no paper trade is open")
        trade = self.open_trade
        trade.exit_price = price
        trade.exit_time = timestamp
        self.cash += trade.pnl or 0
        self.journal.append(trade)
        self.open_trade = None
        return trade
