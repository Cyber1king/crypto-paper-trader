from collections.abc import Sequence

from .models import Candle, PaperTrade
from .simulator import PaperBroker
from .strategy import StrategyConfig, analyze


def run_backtest(
    candles: Sequence[Candle],
    config: StrategyConfig = StrategyConfig(),
    starting_balance: float = 10_000.0,
    risk_fraction: float = 0.01,
) -> tuple[list[PaperTrade], float]:
    """Run the strategy candle-by-candle using only available historical data.

    This is a paper-only research simulation. It does not connect
    to an exchange or place real orders.
    """
    minimum_history = max(config.lookback + 1, config.slow_period)

    if len(candles) < minimum_history:
        raise ValueError("not enough candles for configured backtest")

    broker = PaperBroker(starting_balance)

    for index in range(minimum_history, len(candles)):
        current = candles[index]

        # Only candles up to the current candle are available.
        signal = analyze(candles[: index + 1], config)

        # Close an existing position when an opposite signal appears.
        if broker.open_trade is not None:
            if (
                signal.side in {"long", "short"}
                and signal.side != broker.open_trade.side
            ):
                broker.close(current.close, current.timestamp)

        # Open a new paper position when there is a valid signal.
        if broker.open_trade is None and signal.side in {"long", "short"}:
            broker.open_from_signal(
                signal,
                risk_fraction=risk_fraction,
            )

    # Close any remaining position at the final historical candle.
    if broker.open_trade is not None:
        last = candles[-1]
        broker.close(last.close, last.timestamp)

    return broker.journal, broker.cash
