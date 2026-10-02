"""Phase 7 step 1: baseline reproduction and project inventory."""
import time
from pathlib import Path

from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import load_dataset, validate_dataset
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.report import create_report
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.costs import TradingCosts

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"

print("=== PROJECT INVENTORY (research_engine) ===")
root = Path(".")
for path in sorted(root.rglob("*.py")):
    if ".pytest_cache" in str(path):
        continue
    print(f"  {path.as_posix()}")
for path in sorted(root.rglob("*.toml")):
    print(f"  {path.as_posix()}")
print(f"  {DATASET}  (exists={Path(DATASET).exists()})")

candles, summary = load_dataset(DATASET)
validate_dataset(candles)

print()
print("=== DATASET ===")
print(f"  candles : {summary.candles}")
print(f"  start   : {summary.start}")
print(f"  end     : {summary.end}")

config = StrategyConfig()
print()
print("=== ORIGINAL STRATEGY DEFAULTS (all optional filters at defaults) ===")
for field in (
    "lookback", "fast_period", "slow_period",
    "breakout_buffer", "retest_tolerance",
    "min_breakout_distance", "trend_strength_min",
    "retest_use_close", "breakout_confirm_bars",
    "max_holding_bars", "stop_loss_pct", "take_profit_pct",
):
    print(f"  {field:24s}: {getattr(config, field)!r}")

print()
print("=== BASELINE REPRODUCTION (no config argument -> pure defaults) ===")
t0 = time.time()
result = run_backtest(candles)
elapsed = time.time() - t0
report = create_report(result)

actual = {
    "trades": result.total_trades,
    "net_pnl": round(report["net_pnl"], 2),
    "return_pct": round((result.ending_balance / result.starting_balance - 1) * 100, 2),
    "win_rate": round(report["win_rate"] * 100, 3),
    "profit_factor": round(report["profit_factor"], 4),
    "max_drawdown": round(report["max_drawdown"] * 100, 2),
    "ending_balance": round(result.ending_balance, 2),
}
expected = {
    "trades": 344,
    "net_pnl": -157.14,
    "return_pct": -1.57,
    "win_rate": 31.686,
    "profit_factor": 0.6920,
    "max_drawdown": 1.74,
    "ending_balance": 9842.86,
}

print(f"  {'metric':20s} {'expected':>12s} {'actual':>12s}  match")
all_ok = True
for key, exp in expected.items():
    got = actual[key]
    ok = abs(float(got) - float(exp)) < 1e-6
    all_ok = all_ok and ok
    print(f"  {key:20s} {exp:>12} {got:>12}  {'YES' if ok else 'NO'}")
print(f"\n  elapsed: {elapsed:.1f}s")
print(f"  exit_counts: {result.exit_counts}")
print(f"  starting_balance: {result.starting_balance}")
print()
print(f"  BASELINE REPRODUCED: {'YES' if all_ok else 'NO -- DISCREPANCY'}")

print()
print("=== FEE / SLIPPAGE IN FORCE (verified from the trade journal) ===")
costs = TradingCosts()
total_fees = sum(t.costs for t in result.trades)
print(f"  fee_rate            : {costs.fee_rate}")
print(f"  slippage_rate       : {costs.slippage_rate}")
print(f"  total charged       : {total_fees:.2f}")
print(f"  gross P&L           : {sum(t.pnl for t in result.trades):.2f}")
print(f"  net P&L             : {sum(t.net_pnl for t in result.trades):.2f}")
print(f"  gross - costs       : {sum(t.pnl for t in result.trades) - total_fees:.2f}")
