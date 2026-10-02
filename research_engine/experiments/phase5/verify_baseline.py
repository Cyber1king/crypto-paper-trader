"""Phase 5 step 1: verify baseline + dataset facts independently."""
import time
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import load_dataset, validate_dataset
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.report import create_report
from crypto_paper_lab.strategy import StrategyConfig

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"

candles, summary = load_dataset(DATASET)
validate_dataset(candles)

print("=== DATASET ===")
print(f"candles        : {summary.candles}")
print(f"start          : {summary.start}")
print(f"end            : {summary.end}")
print(f"first ohlcv    : {candles[0].open} {candles[0].high} {candles[0].low} {candles[0].close}")
print(f"last ohlcv     : {candles[-1].open} {candles[-1].high} {candles[-1].low} {candles[-1].close}")

print()
print("=== DEFAULT CONFIG (from StrategyConfig signature) ===")
d = StrategyConfig()
for field in ("asset", "timeframe", "lookback", "fast_period", "slow_period",
              "breakout_buffer", "retest_tolerance"):
    print(f"{field:18s}: {getattr(d, field)!r}")

print()
print("=== BASELINE BACKTEST (defaults, no explicit config) ===")
t0 = time.time()
result = run_backtest(candles)
t1 = time.time()
report = create_report(result)

print(f"elapsed         : {t1 - t0:.1f}s")
print(f"trades          : {result.total_trades}")
print(f"net_pnl         : {report['net_pnl']:.2f}")
print(f"win_rate        : {report['win_rate']:.4%}")
print(f"profit_factor   : {report['profit_factor']:.4f}")
print(f"average_pnl     : {report['average_pnl']:.2f}")
print(f"max_drawdown    : {report['max_drawdown']:.4%}")
print(f"ending_balance  : {report['ending_balance']:.2f}")
print(f"starting_balance: {result.starting_balance}")
print()
print("=== EXPECTED (from task brief) ===")
print("trades=344 net_pnl=-157.14 win_rate=31.69% pf=0.692 mdd=1.74% start=10000")
