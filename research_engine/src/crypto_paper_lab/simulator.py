from datetime import datetime

from .costs import TradingCosts
from .models import PaperTrade, Signal


class PaperBroker:
    """In-memory simulator with configurable paper-trading costs."""

    def __init__(
        self,
        starting_balance: float = 10_000.0,
        costs: TradingCosts | None = None,
    ) -> None:
        if starting_balance <= 0:
            raise ValueError("starting balance must be positive")

        self.starting_balance = starting_balance
        self.cash = starting_balance
        self.costs = costs or TradingCosts()
        self.open_trade: PaperTrade | None = None
        self.journal: list[PaperTrade] = []

    def open_from_signal(
        self,
        signal: Signal,
        risk_fraction: float = 0.01,
    ) -> PaperTrade:
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

    def close(
        self,
        price: float,
        timestamp: datetime,
    ) -> PaperTrade:
        if not self.open_trade:
            raise ValueError("no paper trade is open")

        trade = self.open_trade

        trade.exit_price = price
        trade.exit_time = timestamp

        entry_value = trade.entry_price * trade.quantity
        exit_value = trade.exit_price * trade.quantity

        entry_fee = entry_value * self.costs.fee_rate
        exit_fee = exit_value * self.costs.fee_rate

        total_fees = entry_fee + exit_fee

        slippage_cost = (
            entry_value + exit_value
        ) * self.costs.slippage_rate

        trade.costs = total_fees + slippage_cost

        self.cash += trade.net_pnl or 0.0

        self.journal.append(trade)
        self.open_trade = None

        return trade
