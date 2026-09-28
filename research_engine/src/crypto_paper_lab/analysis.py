
from collections.abc import Sequence

from .models import PaperTrade


def _summarize(trades: list[PaperTrade]) -> dict[str, float | int]:
    """Calculate statistics for a group of closed trades."""

    pnls = [
        float(trade.net_pnl)
        for trade in trades
        if trade.net_pnl is not None
    ]

    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "trades": len(pnls),
        "net_pnl": sum(pnls),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
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


def analyze_trade_directions(
    trades: Sequence[PaperTrade],
) -> dict[str, dict[str, float | int]]:
    """Summarize paper-trade performance by direction."""

    return {
        side: _summarize([
            trade for trade in trades
            if trade.side == side and trade.net_pnl is not None
        ])
        for side in ("long", "short")
    }


def analyze_trade_signals(
    trades: Sequence[PaperTrade],
) -> dict[str, dict[str, float | int]]:
    """Summarize performance by breakout or retest signal."""

    groups = {
        "breakout": [],
        "retest": [],
        "other": [],
    }

    for trade in trades:
        if trade.net_pnl is None:
            continue

        reason = trade.reason.lower()

        if "breakout" in reason or "breakdown" in reason:
            groups["breakout"].append(trade)
        elif "retest" in reason:
            groups["retest"].append(trade)
        else:
            groups["other"].append(trade)

    return {
        name: _summarize(group)
        for name, group in groups.items()
    }
