from datetime import datetime, timedelta, timezone

from crypto_paper_lab.backtest import run_backtest
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


def test_backtest_closes_open_trade_at_end() -> None:
    series = candles(
        [100 + i for i in range(20)] + [123, 124, 125]
    )

    result = run_backtest(
        series,
        StrategyConfig(
            lookback=10,
            fast_period=3,
            slow_period=8,
            breakout_buffer=0,
        ),
    )

    assert result.total_trades > 0
    assert result.trades
    assert all(
        trade.exit_price is not None
        for trade in result.trades
    )
    assert result.ending_balance > 10_000
    assert result.net_pnl > 0


def test_backtest_rejects_insufficient_history() -> None:
    series = candles([100, 101, 102])

    config = StrategyConfig(
        lookback=10,
        slow_period=8,
    )

    try:
        run_backtest(series, config)
    except ValueError as exc:
        assert "not enough candles" in str(exc)
    else:
        raise AssertionError(
            "expected ValueError"
        )
