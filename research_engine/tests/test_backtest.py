from datetime import datetime, timedelta, timezone

from crypto_paper_lab.experiment import run_experiment
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig


def candles(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    return [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=value - 0.5,
            high=value + 1,
            low=value - 1,
            close=value,
            volume=10,
        )
        for i, value in enumerate(closes)
    ]


def test_run_experiment_returns_result_for_each_config() -> None:
    series = candles(
        [100 + i for i in range(20)] + [123, 124, 125]
    )

    configs = [
        StrategyConfig(
            lookback=10,
            fast_period=3,
            slow_period=8,
            breakout_buffer=0,
        ),
        StrategyConfig(
            lookback=12,
            fast_period=4,
            slow_period=8,
            breakout_buffer=0,
        ),
    ]

    results = run_experiment(
        series,
        configs,
    )

    assert len(results) == len(configs)

    for result in results:
        assert result.config in configs
        assert "net_pnl" in result.report
        assert "win_rate" in result.report
        assert "max_drawdown" in result.report
