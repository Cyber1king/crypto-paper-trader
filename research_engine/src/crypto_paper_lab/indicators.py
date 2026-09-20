from collections.abc import Sequence

from .models import Candle


def simple_moving_average(values: Sequence[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError("period must be positive and no larger than the data")
    return sum(values[-period:]) / period


def trend(candles: Sequence[Candle], fast: int = 5, slow: int = 12) -> str:
    closes = [c.close for c in candles]
    if len(closes) < slow:
        return "sideways"
    fast_ma = simple_moving_average(closes, fast)
    slow_ma = simple_moving_average(closes, slow)
    tolerance = slow_ma * 0.001
    if fast_ma > slow_ma + tolerance:
        return "up"
    if fast_ma < slow_ma - tolerance:
        return "down"
    return "sideways"


def support_resistance(
    candles: Sequence[Candle], lookback: int = 20
) -> tuple[float, float]:
    if not candles:
        raise ValueError("at least one candle is required")
    window = candles[-lookback:]
    return min(c.low for c in window), max(c.high for c in window)
