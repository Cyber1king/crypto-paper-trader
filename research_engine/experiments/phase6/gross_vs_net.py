"""Phase 6: is the sub-25-bar 0% win rate structural, or a cost artifact?

Compares gross P&L (before fees/slippage) with net P&L for each holding
group. If gross win rate is also zero the pattern is structural; if gross is
near break-even, costs are flipping marginal winners into losers.
"""
from collections import defaultdict

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.stats import total_friction
from crypto_paper_lab.strategy import StrategyConfig

candles = load_ohlcv_csv("data/BTCUSDT_1h_Cleaned (1).csv")
validate_dataset(candles)

GROUPS = [(1, 13), (13, 19), (19, 25), (25, 10 ** 6)]


def row(rs, label):
    if not rs:
        print(f"  {label:26s} n=   0")
        return
    gross = [t.pnl for t in rs if t.pnl is not None]
    net = [t.net_pnl for t in rs if t.net_pnl is not None]
    gw = sum(1 for x in gross if x > 0)
    nw = sum(1 for x in net if x > 0)
    print(f"  {label:26s} n={len(rs):4d} "
          f"gross={sum(gross):9.2f} gross_wr={gw / len(rs):7.2%} "
          f"net={sum(net):9.2f} net_wr={nw / len(rs):7.2%} "
          f"costs={total_friction(rs):8.2f} "
          f"worst_gross={min(gross):7.2f} best_gross={max(gross):7.2f}")


for label, costs in (
    ("DEFAULT COSTS (fee .1%, slip .05%)", None),
    ("ZERO COSTS (diagnostic)", TradingCosts(0.0, 0.0)),
):
    result = run_backtest(candles, StrategyConfig(), costs=costs)
    trades = list(result.trades)
    print()
    print("=" * 118)
    print(f"{label}   net={result.ending_balance - result.starting_balance:.2f} "
          f"n={result.total_trades}")
    print("=" * 118)
    for lo, hi in GROUPS:
        label_hi = hi if hi < 10 ** 6 else "inf"
        row([t for t in trades if lo <= t.bars_held < hi], f"bars {lo}-{label_hi}")
    row(trades, "ALL")
    for side in ("long", "short"):
        print(f"  -- {side} --")
        for lo, hi in GROUPS:
            label_hi = hi if hi < 10 ** 6 else "inf"
            row([t for t in trades if t.side == side and lo <= t.bars_held < hi],
                f"{side} bars {lo}-{label_hi}")

print()
print("=" * 118)
print("MFE/MAE of the sub-25-bar losers (zero-cost run) - did they ever go in our favour?")
print("=" * 118)
result = run_backtest(candles, StrategyConfig(), costs=TradingCosts(0.0, 0.0))
trades = list(result.trades)
index_of = {c.timestamp: i for i, c in enumerate(candles)}

losers = [t for t in trades if t.bars_held < 25]
favourable = 0
for t in losers:
    entry_i = index_of[t.entry_time]
    window = candles[entry_i + 1: index_of[t.exit_time] + 1] or [candles[entry_i]]
    if t.side == "long":
        best = max(c.high for c in window)
        if best > t.entry_price:
            favourable += 1
    else:
        best = min(c.low for c in window)
        if best < t.entry_price:
            favourable += 1
print(f"  sub-25-bar trades            : {len(losers)}")
print(f"  ... that had ANY favourable excursion: {favourable} "
      f"({favourable / len(losers):.1%})")
print("  (a high count here would mean an earlier/intrabar exit could have helped)")
