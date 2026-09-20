from collections.abc import Sequence

from .models import PaperTrade


def performance(trades: Sequence[PaperTrade]) -> dict[str, float | int]:
    closed = [trade for trade in trades if trade.pnl is not None]
    pnls = [float(trade.pnl) for trade in closed]
    wins = [pnl for pnl in pnls if pnl > 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
    return {
        "trades": len(closed),
        "net_pnl": sum(pnls),
        "win_rate": len(wins) / len(closed) if closed else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "average_pnl": sum(pnls) / len(closed) if closed else 0.0,
    }
