from dataclasses import dataclass
from collections.abc import Sequence

from .backtest import run_backtest
from .models import Candle
from .report import create_report
from .strategy import StrategyConfig


@dataclass(frozen=True)
class ExperimentResult:
    config: StrategyConfig
    report: dict[str, float | int]


def run_experiment(
    candles: Sequence[Candle],
    configs: Sequence[StrategyConfig],
    starting_balance: float = 10_000.0,
    risk_fraction: float = 0.01,
) -> list[ExperimentResult]:
    """Run multiple strategy configurations on the same historical data."""

    results: list[ExperimentResult] = []

    for config in configs:
        backtest = run_backtest(
            candles,
            config=config,
            starting_balance=starting_balance,
            risk_fraction=risk_fraction,
        )

        report = create_report(backtest)

        results.append(
            ExperimentResult(
                config=config,
                report=report,
            )
        )

    return results
