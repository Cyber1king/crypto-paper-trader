from datetime import datetime, timezone

import pytest

from crypto_paper_lab.analysis import analyze_trade_directions
from crypto_paper_lab.models import PaperTrade


def test_analyze_trade_directions() -> None:
    trades = [
        PaperTrade(
            side="long",
            entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            entry_price=100,
            quantity=1,
            exit_time=datetime(2025, 1, 1, 1, tzinfo=timezone.utc),
            exit_price=110,
            costs=1,
        ),
        PaperTrade(
            side="long",
            entry_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            entry_price=100,
            quantity=1,
            exit_time=datetime(2025, 1, 2, 1, tzinfo=timezone.utc),
            exit_price=90,
            costs=1,
        ),
        PaperTrade(
            side="short",
            entry_time=datetime(2025, 1, 3, tzinfo=timezone.utc),
            entry_price=100,
            quantity=1,
            exit_time=datetime(2025, 1, 3, 1, tzinfo=timezone.utc),
            exit_price=90,
            costs=1,
        ),
    ]

    result = analyze_trade_directions(trades)

    assert result["long"]["trades"] == 2
    assert result["short"]["trades"] == 1

    assert result["long"]["net_pnl"] == pytest.approx(-2)
    assert result["short"]["net_pnl"] == pytest.approx(9)
