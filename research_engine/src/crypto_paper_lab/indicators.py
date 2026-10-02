from collections.abc import Sequence

from .models import Candle


def simple_moving_average(values: Sequence[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError("period must be positive and no larger than the data")
    return sum(values[-period:]) / period


def trend(
    candles: Sequence[Candle],
    fast: int = 5,
    slow: int = 12,
    strength: float = 0.001,
) -> str:
    """Classify trend from a fast/slow simple-moving-average pair.

    ``strength`` is the minimum relative separation between the two averages
    required before a direction is reported. It is expressed as a fraction of
    the slow average. The default reproduces the original V1 behaviour.
    """

    closes = [c.close for c in candles]
    if len(closes) < slow:
        return "sideways"
    fast_ma = simple_moving_average(closes, fast)
    slow_ma = simple_moving_average(closes, slow)
    tolerance = slow_ma * strength
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
