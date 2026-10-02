"""Compute deterministic values used to pin baseline-preservation tests."""
from datetime import datetime, timedelta, timezone

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig, analyze

# Deterministic synthetic series (same shape as existing tests)
def series(closes):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=v - 0.5,
            high=v + 1,
            low=v - 1,
            close=v,
            volume=10,
        )
        for i, v in enumerate(closes)
    ]

cfg = StrategyConfig(lookback=10, fast_period=3, slow_period=8, breakout_buffer=0)

a = series([100 + i for i in range(20)] + [123, 124, 125])
sig = analyze(a, cfg)
print("A signal:", sig)

b = series([100 + i for i in range(20)] + [123, 124, 125])
res = run_backtest(b, cfg)
print("A backtest trades:", res.total_trades)
print("A backtest end:", round(res.ending_balance, 6))
print("A backtest net:", round(res.ending_balance - res.starting_balance, 6))

c = series([100 + i for i in range(20)] + [123, 124, 125])
res0 = run_backtest(c, cfg, costs=TradingCosts(0.0, 0.0))
print("A zero-cost trades:", res0.total_trades)
print("A zero-cost end:", round(res0.ending_balance, 6))

# Default config on the same series (for default-gate regression)
d = series([100 + i for i in range(20)] + [123, 124, 125])
resd = run_backtest(d)
print("A default-cfg trades:", resd.total_trades)
print("A default-cfg end:", round(resd.ending_balance, 6))
