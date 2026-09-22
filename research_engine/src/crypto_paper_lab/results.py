from dataclasses import dataclass
from collections.abc import Sequence

from .models import PaperTrade


@dataclass(frozen=True)
class BacktestResult:
    """Immutable summary of a completed paper backtest."""

    trades: Sequence[PaperTrade]
    starting_balance: float
    ending_balance: float

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def net_pnl(self) -> float:
        return self.ending_balance - self.starting_balance
