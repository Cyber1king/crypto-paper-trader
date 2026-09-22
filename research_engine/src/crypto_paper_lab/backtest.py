from collections.abc import Sequence

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
    """Run a paper-only historical strategy simulation."""

    minimum_history = max(
        config.lookback + 1,
        config.slow_period,
    )

    if len(candles) < minimum_history:
        raise ValueError(
            "not enough candles for configured backtest"
        )

    broker = PaperBroker(starting_balance)

    for index in range(minimum_history, len(candles)):
        current = candles[index]

        signal = analyze(
            candles[: index + 1],
            config,
        )

        if broker.open_trade is not None:
            if (
                signal.side in {"long", "short"}
                and signal.side != broker.open_trade.side
            ):
                broker.close(
                    current.close,
                    current.timestamp,
                )

        if (
            broker.open_trade is None
            and signal.side in {"long", "short"}
        ):
            broker.open_from_signal(
                signal,
                risk_fraction=risk_fraction,
            )

    if broker.open_trade is not None:
        last = candles[-1]

        broker.close(
            last.close,
            last.timestamp,
        )

    return BacktestResult(
        trades=broker.journal,
        starting_balance=starting_balance,
        ending_balance=broker.cash,
    )
