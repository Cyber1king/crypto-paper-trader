from collections.abc import Sequence
from datetime import datetime

from .backtest import run_backtest
from .models import Candle
from .report import create_report
from .strategy import StrategyConfig


def split_by_year(
    candles: Sequence[Candle],
) -> dict[int, list[Candle]]:
    """Split historical candles into calendar years."""

    years: dict[int, list[Candle]] = {}

    for candle in candles:
        year = candle.timestamp.year
        years.setdefault(year, []).append(candle)

    return years


def run_yearly_backtests(
    candles: Sequence[Candle],
    config: StrategyConfig = StrategyConfig(),
    starting_balance: float = 10_000.0,
    risk_fraction: float = 0.01,
    research_context: object | None = None,
) -> dict[int, dict[str, float | int]]:
    """Run the same paper strategy separately for each calendar year.

    ``research_context`` is forwarded. Note that per-year splitting produces
    windows no single reservation can describe, so a research evaluation over
    this function is refused by the guard rather than half-evaluated.
    """

    yearly_results: dict[int, dict[str, float | int]] = {}

    for year, year_candles in split_by_year(candles).items():
        if len(year_candles) < max(
            config.lookback + 1,
            config.slow_period,
        ):
            continue

        result = run_backtest(
            year_candles,
            config=config,
            starting_balance=starting_balance,
            risk_fraction=risk_fraction,
            research_context=research_context,
        )

        yearly_results[year] = create_report(result)

    return yearly_results
