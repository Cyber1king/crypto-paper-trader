import statistics
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


def realised_volatility(
    candles: Sequence[Candle], period: int = 20
) -> float | None:
    """Sample standard deviation of the trailing ``period`` simple returns.

    Causal by construction: it reads only the closes inside the trailing
    ``period + 1`` candles supplied by the caller, so a caller passing
    ``candles[:index]`` obtains a value knowable strictly before the fill at
    ``candles[index]``.

    Returns the sample (n-1) standard deviation of simple hourly returns,
    not an annualised figure, and not an ATR. ``None`` is returned when there
    are fewer than ``period + 1`` candles, rather than substituting zero.

    The default ``period`` matches :attr:`StrategyConfig.lookback`, which is
    the repository's existing convention for how much trailing history a
    signal may look at. That is a structural argument, not an empirical one:
    no outcome was examined when choosing it.
    """

    if period < 2:
        raise ValueError("period must be at least 2")

    if len(candles) < period + 1:
        return None

    closes = [candle.close for candle in candles[-(period + 1):]]
    returns = [
        closes[i + 1] / closes[i] - 1.0
        for i in range(len(closes) - 1)
    ]

    return statistics.stdev(returns)


def mean_candle_range(
    candles: Sequence[Candle], lookback: int = 20
) -> float | None:
    """Mean high-low range over the trailing ``lookback`` candles.

    Causal by construction: it reads only the supplied trailing window.

    This is a range proxy, **not** an ATR. True range requires the previous
    close and is not implemented anywhere in this repository; naming it ATR
    would misdescribe it. ``None`` is returned when there are no candles,
    rather than substituting zero.

    The default ``lookback`` matches :attr:`StrategyConfig.lookback` for the
    same structural reason as :func:`realised_volatility`.
    """

    if lookback < 1:
        raise ValueError("lookback must be positive")

    if not candles:
        return None

    window = candles[-lookback:]
    return sum(candle.high - candle.low for candle in window) / len(window)
