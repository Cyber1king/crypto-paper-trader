from collections.abc import Sequence

from .models import PaperTrade


def total_friction(trades: Sequence[PaperTrade]) -> float:
    """Total execution friction across trades: fees plus spread plus slippage.

    This is the correct figure whenever a report shows cost as the bridge
    between gross and net P&L, because it is the total cost of trading
    regardless of how the execution model distributes it.

    Under the default ``cost_deduction`` model this returns exactly the same
    number as ``sum(trade.costs)``, so existing reports are unchanged.

    Under ``fill_price`` it differs deliberately: ``trade.costs`` then holds
    fees only, because spread and slippage are already inside the recorded
    fill prices and deducting them again would double count. Summing
    ``trade.costs`` there would understate the true cost of the run.
    """

    return sum(
        trade.total_friction
        for trade in trades
        if trade.total_friction is not None
    )


def total_fees(trades: Sequence[PaperTrade]) -> float:
    """Trading fees only, across trades."""

    return sum(trade.fee_total for trade in trades)


def total_spread(trades: Sequence[PaperTrade]) -> float:
    """Spread cost only, across trades. Always zero under ``cost_deduction``."""

    return sum(trade.spread_total for trade in trades)


def total_slippage(trades: Sequence[PaperTrade]) -> float:
    """Slippage cost only, across trades."""

    return sum(trade.slippage_total for trade in trades)


def cost_breakdown(trades: Sequence[PaperTrade]) -> dict[str, float]:
    """Full execution-cost breakdown, for reports that itemise costs."""

    return {
        "fee_total": total_fees(trades),
        "spread_total": total_spread(trades),
        "slippage_total": total_slippage(trades),
        "total_friction": total_friction(trades),
        "deducted_costs": sum(trade.costs for trade in trades),
    }


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
