from collections.abc import Sequence

from .models import PaperTrade


def performance(
    trades: Sequence[PaperTrade],
    starting_balance: float = 10_000.0,
) -> dict[str, float | int]:
    """Calculate performance statistics from closed paper trades."""

    if starting_balance <= 0:
        raise ValueError("starting balance must be positive")

    closed = [
        trade
        for trade in trades
        if trade.net_pnl is not None
    ]

    pnls = [
        float(trade.net_pnl)
        for trade in closed
    ]

    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    balance = starting_balance
    peak_balance = starting_balance
    max_drawdown = 0.0

    for pnl in pnls:
        balance += pnl

        if balance > peak_balance:
            peak_balance = balance

        if peak_balance > 0:
            drawdown = (
                peak_balance - balance
            ) / peak_balance

            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return {
        "trades": len(closed),
        "net_pnl": sum(pnls),
        "win_rate": (
            len(wins) / len(closed)
            if closed
            else 0.0
        ),
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss
            else float("inf")
        ),
        "average_pnl": (
            sum(pnls) / len(closed)
            if closed
            else 0.0
        ),
        "max_drawdown": max_drawdown,
        "ending_balance": balance,
    }
