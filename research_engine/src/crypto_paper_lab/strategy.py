
from dataclasses import dataclass
from typing import Sequence

from .indicators import (
    mean_candle_range,
    realised_volatility,
    support_resistance,
    trend,
)
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

    # Optional research gates added in Phase 5. Every default below reproduces
    # the original V1 signal logic exactly, so the baseline is unchanged.
    min_breakout_distance: float = 0.0
    trend_strength_min: float = 0.001
    retest_use_close: bool = False
    breakout_confirm_bars: int = 1

    # Optional exit rules added in Phase 6. ``None`` disables each rule, which
    # reproduces the original V1 exit behaviour (opposite-signal exit only).
    #
    # Execution model: a rule is *detected* on a bar that has already closed
    # and is *filled* at the open of the following bar. No intrabar fills are
    # assumed, so no future candle information is ever used.
    max_holding_bars: int | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None

    # Optional directional diagnostic added in Phase 7. ``None`` allows both
    # sides, which reproduces the original V1 behaviour. Restricting the sides
    # only gates *entries*; an open position still exits on an opposite-side
    # signal exactly as before. This exists for diagnostics only and is not a
    # recommendation to trade one direction.
    allowed_sides: tuple[str, ...] | None = None


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
        strength=config.trend_strength_min,
    )

    def distance_above(close: float, level: float) -> float:
        """Signed distance by which ``close`` exceeds ``level``, as a fraction.

        Phase 14B: this expression already existed inside the gate below and
        was discarded. It is now named so the numeric value can be recorded.
        The arithmetic is unchanged, so the gate result is bit-identical.
        """

        return (close - level) / level

    def distance_below(close: float, level: float) -> float:
        """Signed distance by which ``close`` falls below ``level``."""

        return (level - close) / level

    def broke_level_up(close: float, level: float) -> bool:
        return (
            close > level * (1 + config.breakout_buffer)
            and distance_above(close, level)
            >= config.min_breakout_distance
        )

    def broke_level_down(close: float, level: float) -> bool:
        return (
            close < level * (1 - config.breakout_buffer)
            and distance_below(close, level)
            >= config.min_breakout_distance
        )

    # Check whether the previous candle broke a level.
    previous_broke_up = broke_level_up(previous.close, resistance)

    previous_broke_down = broke_level_down(previous.close, support)

    # Check whether the current candle retested that level.
    # Baseline uses the candle wick; retest_use_close uses the candle close.
    if config.retest_use_close:
        retest_up = (
            previous_broke_up
            and abs(current.close - resistance) / resistance
            <= config.retest_tolerance
            and current.close >= resistance
        )

        retest_down = (
            previous_broke_down
            and abs(current.close - support) / support
            <= config.retest_tolerance
            and current.close <= support
        )
    else:
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

    # Check for a new breakout on the current candle, optionally requiring
    # the level to be held by the last `breakout_confirm_bars` closes.
    confirm = max(1, config.breakout_confirm_bars)
    recent_closes = [candle.close for candle in candles[-confirm:]]

    broke_up = all(
        broke_level_up(close, resistance) for close in recent_closes
    )

    broke_down = all(
        broke_level_down(close, support) for close in recent_closes
    )

    # Phase 14B instrumentation. These assignments are observational only:
    # the decision chain below is unchanged, and every value is derived from
    # ``current`` or ``previous``, which are candles strictly before the fill.
    #
    # For a retest entry the breakout belongs to ``previous``, so that is
    # where the breakout distance is measured. For a breakout entry the
    # breakout is on the signal candle itself.
    #
    # ``None`` means "not applicable for this signal kind". It is never a
    # substituted zero.
    breakout_distance: float | None = None
    retest_distance: float | None = None

    if config.retest_use_close:
        long_retest_distance = abs(current.close - resistance) / resistance
        short_retest_distance = abs(current.close - support) / support
    else:
        long_retest_distance = abs(current.low - resistance) / resistance
        short_retest_distance = abs(current.high - support) / support

    if market_trend == "up" and retest_up:
        side, reason = "long", "bullish retest"
        breakout_distance = distance_above(previous.close, resistance)
        retest_distance = long_retest_distance
    elif market_trend == "down" and retest_down:
        side, reason = "short", "bearish retest"
        breakout_distance = distance_below(previous.close, support)
        retest_distance = short_retest_distance
    elif market_trend == "up" and broke_up:
        side, reason = "long", "uptrend breakout"
        breakout_distance = distance_above(current.close, resistance)
    elif market_trend == "down" and broke_down:
        side, reason = "short", "downtrend breakdown"
        breakout_distance = distance_below(current.close, support)
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
        signal_close=current.close,
        trend_state=market_trend,
        breakout_distance=breakout_distance,
        retest_distance=retest_distance,
        realised_volatility=realised_volatility(
            candles, config.lookback
        ),
        mean_range=mean_candle_range(candles, config.lookback),
    )
