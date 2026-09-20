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


def analyze(candles: Sequence[Candle], config: StrategyConfig = StrategyConfig()) -> Signal:
    if len(candles) < max(config.lookback + 1, config.slow_period):
        raise ValueError("not enough candles for configured strategy")

    current = candles[-1]
    history = candles[:-1]
    support, resistance = support_resistance(history, config.lookback)
    market_trend = trend(candles, config.fast_period, config.slow_period)
    broke_up = current.close > resistance * (1 + config.breakout_buffer)
    broke_down = current.close < support * (1 - config.breakout_buffer)

    previous = history[-1]
    retest_up = (
        previous.close > resistance
        and abs(current.low - resistance) / resistance <= config.retest_tolerance
        and current.close >= resistance
    )
    retest_down = (
        previous.close < support
        and abs(current.high - support) / support <= config.retest_tolerance
        and current.close <= support
    )

    if market_trend == "up" and (broke_up or retest_up):
        side, reason = "long", "uptrend breakout" if broke_up else "bullish retest"
    elif market_trend == "down" and (broke_down or retest_down):
        side, reason = "short", "downtrend breakdown" if broke_down else "bearish retest"
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
