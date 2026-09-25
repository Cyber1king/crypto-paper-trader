from collections.abc import Sequence

from .models import PaperTrade


def analyze_trade_directions(
    trades: Sequence[PaperTrade],
) -> dict[str, dict[str, float | int]]:
    """Summarize paper-trade performance by direction."""

    results: dict[str, dict[str, float | int]] = {}

    for side in ("long", "short"):
        side_trades = [
            trade
            for trade in trades
            if trade.side == side and trade.net_pnl is not None
        ]

        pnls = [
            float(trade.net_pnl)
            for trade in side_trades
        ]

        wins = [
            pnl for pnl in pnls
            if pnl > 0
        ]

        losses = [
            pnl for pnl in pnls
            if pnl < 0
        ]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        results[side] = {
            "trades": len(pnls),
            "net_pnl": sum(pnls),
            "win_rate": (
                len(wins) / len(pnls)
                if pnls
                else 0.0
            ),
            "profit_factor": (
                gross_profit / gross_loss
                if gross_loss
                else float("inf")
            ),
            "average_pnl": (
                sum(pnls) / len(pnls)
                if pnls
                else 0.0
            ),
        }

    return results
