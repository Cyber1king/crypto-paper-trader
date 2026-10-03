"""Phase 8 step 2: confirm baseline and Phase 7 A2 still reproduce."""
from dataclasses import replace

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.report import create_report
from crypto_paper_lab.stats import total_friction
from crypto_paper_lab.strategy import StrategyConfig

candles = load_ohlcv_csv("data/BTCUSDT_1h_Cleaned (1).csv")
validate_dataset(candles)

A2 = replace(StrategyConfig(), min_breakout_distance=0.002)

EXPECTED = {
    "baseline": {
        "trades": 344, "net_pnl": -157.14, "return_pct": -1.57,
        "win_rate": 31.686, "profit_factor": 0.6920,
        "max_drawdown": 1.74, "ending_balance": 9842.86,
    },
    "A2": {
        "trades": 284, "net_pnl": -87.16, "return_pct": -0.87,
        "win_rate": 33.45, "profit_factor": 0.796,
        "max_drawdown": 1.08, "ending_balance": 9912.84,
    },
}

print("=" * 96)
print("PHASE 8 - PRE-VALIDATION REPRODUCTION CHECK")
print("=" * 96)
print(f"dataset: {len(candles)} candles  "
      f"{candles[0].timestamp} .. {candles[-1].timestamp}")

all_ok = True
for label, cfg in (("baseline", StrategyConfig()), ("A2", A2)):
    result = run_backtest(candles, config=cfg)
    report = create_report(result)
    actual = {
        "trades": result.total_trades,
        "net_pnl": round(report["net_pnl"], 2),
        "return_pct": round(
            (result.ending_balance / result.starting_balance - 1) * 100, 2
        ),
        "win_rate": round(report["win_rate"] * 100, 3),
        "profit_factor": round(report["profit_factor"], 4),
        "max_drawdown": round(report["max_drawdown"] * 100, 2),
        "ending_balance": round(result.ending_balance, 2),
    }
    print(f"\n--- {label} ---")
    print(f"  {'metric':18s} {'expected':>12s} {'actual':>12s}  {'reported@dp':>12s}  match")
    for key, exp in EXPECTED[label].items():
        got = actual[key]
        # Compare at the precision the Phase 7 report published, so that a
        # difference in printed decimal places is not reported as a
        # discrepancy in the underlying figure.
        dp = len(str(exp).split(".")[1]) if "." in str(exp) else 0
        shown = round(float(got), dp)
        ok = abs(shown - float(exp)) < 10 ** (-dp) / 2
        all_ok = all_ok and ok
        print(f"  {key:18s} {exp:>12} {got:>12.6f}  {shown:>12}  {'YES' if ok else 'NO'}")

    gross = sum(t.pnl or 0.0 for t in result.trades)
    costs = total_friction(result.trades)
    print(f"  gross_pnl          {gross:12.2f}")
    print(f"  total_costs        {costs:12.2f}")
    print(f"  exits              {result.exit_counts}")

print()
print(f"REPRODUCTION: {'ALL FIGURES MATCH' if all_ok else 'DISCREPANCY - STOP'}")
