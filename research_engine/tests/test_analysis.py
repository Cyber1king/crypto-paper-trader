from datetime import datetime, timezone

import pytest

from crypto_paper_lab.analysis import (
    analyze_trade_directions,
    analyze_trade_signals,
)
from crypto_paper_lab.models import PaperTrade


def make_trade(
    side: str,
    reason: str,
    entry: float,
    exit: float,
    costs: float = 1.0,
) -> PaperTrade:
    trade = PaperTrade(
        side=side,
        entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        entry_price=entry,
        quantity=1,
        exit_time=datetime(2025, 1, 1, 1, tzinfo=timezone.utc),
        exit_price=exit,
        reason=reason,
        costs=costs,
    )
    return trade


def test_analyze_trade_directions() -> None:
    trades = [
        make_trade("long", "uptrend breakout", 100, 110),
        make_trade("long", "bullish retest", 100, 90),
        make_trade("short", "downtrend breakdown", 100, 90),
    ]

    result = analyze_trade_directions(trades)

    assert result["long"]["trades"] == 2
    assert result["short"]["trades"] == 1
    assert result["long"]["net_pnl"] == pytest.approx(-2)
    assert result["short"]["net_pnl"] == pytest.approx(9)


def test_analyze_trade_signals() -> None:
    trades = [
        make_trade("long", "uptrend breakout", 100, 110),
        make_trade("short", "downtrend breakdown", 100, 90),
        make_trade("long", "bullish retest", 100, 105),
        make_trade("short", "bearish retest", 100, 110),
    ]

    result = analyze_trade_signals(trades)

    assert result["breakout"]["trades"] == 2
    assert result["retest"]["trades"] == 2
    assert result["other"]["trades"] == 0

    assert result["breakout"]["net_pnl"] == pytest.approx(18)
    assert result["retest"]["net_pnl"] == pytest.approx(-7)


def test_open_trades_are_ignored() -> None:
    trade = PaperTrade(
        side="long",
        entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        entry_price=100,
        quantity=1,
        reason="uptrend breakout",
    )

    result = analyze_trade_signals([trade])

    assert result["breakout"]["trades"] == 0
