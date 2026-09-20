from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.indicators import support_resistance
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig, analyze


def candles(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(hours=i), value - 0.5, value + 1, value - 1, value, 10)
        for i, value in enumerate(closes)
    ]


def test_support_and_resistance_use_window_extremes() -> None:
    support, resistance = support_resistance(candles([100, 104, 102]), 3)
    assert support == 99
    assert resistance == 105


def test_uptrend_breakout_generates_long_signal() -> None:
    series = candles([100 + i for i in range(20)] + [123])
    signal = analyze(
        series,
        StrategyConfig(lookback=10, fast_period=3, slow_period=8, breakout_buffer=0),
    )
    assert signal.side == "long"
    assert signal.breakout is True


def test_insufficient_history_is_explicit() -> None:
    with pytest.raises(ValueError, match="not enough candles"):
        analyze(candles([100, 101, 102]))
