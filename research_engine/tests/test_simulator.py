from datetime import datetime, timezone

import pytest

from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Signal
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.stats import performance


def signal(side: str = "long") -> Signal:
    return Signal(
        datetime.now(timezone.utc),
        side,
        "test",
        100,
        90,
        110,
        "up",
        True,
        False,
    )


def test_paper_broker_records_profitable_long() -> None:
    broker = PaperBroker(10_000)

    broker.open_from_signal(
        signal(),
        risk_fraction=0.1,
    )

    trade = broker.close(
        110,
        datetime.now(timezone.utc),
    )

    assert trade.pnl == pytest.approx(100)
    assert performance(broker.journal)["win_rate"] == 1


def test_flat_signal_cannot_open_trade() -> None:
    broker = PaperBroker()

    with pytest.raises(ValueError, match="flat"):
        broker.open_from_signal(signal("flat"))


def test_trading_costs_can_be_configured() -> None:
    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
    )

    broker = PaperBroker(
        10_000,
        costs=costs,
    )

    assert broker.costs.fee_rate == pytest.approx(0.001)
    assert broker.costs.slippage_rate == pytest.approx(0.0005)
