
from dataclasses import dataclass
from typing import Sequence

from .indicators import support_resistance, trend
from .models import Candle, Signal


@dataclass(frozen=True)
class StrategyConfig:
    asset: str = "BTC/USDT"
    timeframe: str = "1h"
    lookback: int = 20
    fast_period: int = 5
    slow_period: int = 12
    breakout_buffer: float = 0.001
    retest_tolerance: float = 0.002


def analyze(
    candles: Sequence[Candle],
    config: StrategyConfig = StrategyConfig(),
) -> Signal:
    minimum = max(config.lookback + 2, config.slow_period)

    if len(candles) < minimum:
        raise ValueError(
            "not enough candles for configured strategy"
        )

    current = candles[-1]
    previous = candles[-2]

    # Calculate levels without including the previous
    # or current candle.
    history = candles[:-2]

    support, resistance = support_resistance(
        history,
        config.lookback,
    )

    market_trend = trend(
        candles,
        config.fast_period,
        config.slow_period,
    )

    # Check whether the previous candle broke a level.
    previous_broke_up = (
        previous.close
        > resistance * (1 + config.breakout_buffer)
    )

    previous_broke_down = (
        previous.close
        < support * (1 - config.breakout_buffer)
    )

    # Check whether the current candle retested that level.
    retest_up = (
        previous_broke_up
        and abs(current.low - resistance) / resistance
        <= config.retest_tolerance
        and current.close >= resistance
    )

    retest_down = (
        previous_broke_down
        and abs(current.high - support) / support
        <= config.retest_tolerance
        and current.close <= support
    )

    # Check for a new breakout on the current candle.
    broke_up = (
        current.close
        > resistance * (1 + config.breakout_buffer)
    )

    broke_down = (
        current.close
        < support * (1 - config.breakout_buffer)
    )

    if market_trend == "up" and retest_up:
        side, reason = "long", "bullish retest"
    elif market_trend == "down" and retest_down:
        side, reason = "short", "bearish retest"
    elif market_trend == "up" and broke_up:
        side, reason = "long", "uptrend breakout"
    elif market_trend == "down" and broke_down:
        side, reason = "short", "downtrend breakdown"
    else:
        side, reason = "flat", "no confirmed breakout or retest"

    return Signal(
        timestamp=current.timestamp,
        side=side,
        reason=reason,
        price=current.close,
        support=support,
        resistance=resistance,
        trend=market_trend,
        breakout=broke_up or broke_down,
        retest=retest_up or retest_down,
    )
