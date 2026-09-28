
from collections.abc import Sequence
from dataclasses import replace

from .models import Candle
from .results import BacktestResult
from .simulator import PaperBroker
from .strategy import StrategyConfig, analyze


def run_backtest(
    candles: Sequence[Candle],
    config: StrategyConfig = StrategyConfig(),
    starting_balance: float = 10_000.0,
    risk_fraction: float = 0.01,
) -> BacktestResult:
    """Run a paper-only backtest using next-candle open execution."""

    minimum_history = max(
        config.lookback + 2,
        config.slow_period,
    )

    if len(candles) <= minimum_history:
        raise ValueError(
            "not enough candles for configured backtest"
        )

    broker = PaperBroker(starting_balance)

    for index in range(minimum_history, len(candles)):
        current = candles[index]

        # Generate the signal using only candles that have closed.
        signal = analyze(
            candles[:index],
            config,
        )

        # Simulate execution at the next candle's open.
        execution_signal = replace(
            signal,
            timestamp=current.timestamp,
            price=current.open,
        )

        if broker.open_trade is not None:
            if (
                signal.side in {"long", "short"}
                and signal.side != broker.open_trade.side
            ):
                broker.close(
                    current.open,
                    current.timestamp,
                )

        if (
            broker.open_trade is None
            and signal.side in {"long", "short"}
        ):
            broker.open_from_signal(
                execution_signal,
                risk_fraction=risk_fraction,
            )

    # Close any remaining position at the final candle's close.
    if broker.open_trade is not None:
        last = candles[-1]
        broker.close(last.close, last.timestamp)

    return BacktestResult(
        trades=broker.journal,
        starting_balance=starting_balance,
        ending_balance=broker.cash,
    )
