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
    evaluation_start: int | None = None,
    research_context: object | None = None,
) -> list[ExperimentResult]:
    """Run multiple strategy configurations on the same historical data.

    ``evaluation_start`` and ``research_context`` are forwarded to every
    ``run_backtest`` call, so a multi-configuration sweep cannot lose the guard
    that a single run would have applied. Every configuration is run against the
    same series, so one caller-declared boundary describes all of them.

    ``evaluation_start`` is an index into ``candles``. It is never derived here.
    A caller that supplies a non-``None`` ``research_context`` must also supply a
    valid ``evaluation_start``: ``run_backtest`` refuses an evaluation whose
    scored window is undeclared, so a context sent without a boundary is
    rejected rather than quietly evaluated against the whole series.
    """

    results: list[ExperimentResult] = []

    for config in configs:
        backtest = run_backtest(
            candles,
            config=config,
            starting_balance=starting_balance,
            risk_fraction=risk_fraction,
            evaluation_start=evaluation_start,
            research_context=research_context,
        )

        report = create_report(backtest)

        results.append(
            ExperimentResult(
                config=config,
                report=report,
            )
        )

    return results
