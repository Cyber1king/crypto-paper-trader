from .results import BacktestResult
from .stats import performance


def create_report(result: BacktestResult) -> dict[str, float | int]:
    """Create a performance report from a completed backtest."""

    return performance(
        result.trades,
        starting_balance=result.starting_balance,
    )
