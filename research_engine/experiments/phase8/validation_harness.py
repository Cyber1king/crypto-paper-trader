"""Phase 8 out-of-sample validation harness.

This harness is prepared for use when genuinely unseen candles are supplied.
It deliberately REFUSES to produce a validation result unless the supplied
file satisfies every requirement:

  * at least ``WARMUP_CANDLES`` candles of leading context;
  * a first *validation-eligible* timestamp strictly after PHASE7_END;
  * contiguous hourly bars with no duplicates or gaps;
  * clean OHLC relationships and positive prices.

When the repository contains no such file, this script reports why validation
could not be completed. It never substitutes in-sample numbers for an
out-of-sample result.

Usage:
    python experiments/phase8/validation_harness.py [path/to/validation.csv]
"""
import sys
from dataclasses import replace
from datetime import datetime, timedelta

from crypto_paper_lab.backtest import END_OF_DATA, run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.report import create_report
from crypto_paper_lab.stats import total_friction
from crypto_paper_lab.strategy import StrategyConfig

PHASE7_FIRST = datetime(2024, 1, 1, 0, 0)
PHASE7_END = datetime(2025, 12, 31, 23, 0)
WARMUP_CANDLES = 48          # > max(lookback + 2, slow_period) = 22
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
START_BALANCE = 10_000.0
RISK_FRACTION = 0.01

BASELINE = StrategyConfig()
A2 = replace(StrategyConfig(), min_breakout_distance=0.002)

CONFIGURATIONS = (
    ("baseline", BASELINE),
    ("A2_min_dist_0.002", A2),
)


def inspect(path):
    """Return (candles, problems). Empty problems means the file is usable."""

    problems = []
    candles = load_ohlcv_csv(path)

    if len(candles) < WARMUP_CANDLES + 24:
        problems.append(
            f"too short: {len(candles)} candles, need at least "
            f"{WARMUP_CANDLES + 24}"
        )

    stamps = [c.timestamp for c in candles]
    if any(b <= a for a, b in zip(stamps, stamps[1:])):
        problems.append("timestamps are not strictly increasing")

    gaps = [
        (a, b) for a, b in zip(stamps, stamps[1:])
        if b - a != timedelta(hours=1)
    ]
    if gaps:
        problems.append(f"{len(gaps)} irregular gaps, first at {gaps[0]}")

    if stamps and stamps[-1] <= PHASE7_END:
        problems.append(
            f"does not extend beyond the Phase 7 window "
            f"(last candle {stamps[-1]} <= {PHASE7_END})"
        )

    # the first validation-eligible bar must be unseen
    eligible_from = stamps[WARMUP_CANDLES] if len(stamps) > WARMUP_CANDLES else None
    if eligible_from is not None and eligible_from <= PHASE7_END:
        problems.append(
            f"first eligible bar {eligible_from} is still inside the "
            f"Phase 7 window"
        )

    try:
        validate_dataset(candles)
    except ValueError as exc:
        problems.append(f"validate_dataset failed: {exc}")

    return candles, problems


def report_configuration(name, candles, config, boundary):
    result = run_backtest(
        candles,
        config=config,
        starting_balance=START_BALANCE,
        risk_fraction=RISK_FRACTION,
        costs=TradingCosts(FEE_RATE, SLIPPAGE_RATE),
        evaluation_start=boundary,
    )
    stats = create_report(result)

    nets = [t.net_pnl for t in result.trades if t.net_pnl is not None]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    longs = [t for t in result.trades if t.side == "long"]
    shorts = [t for t in result.trades if t.side == "short"]

    def side_block(trades):
        if not trades:
            return "n=0"
        side_nets = [t.net_pnl or 0.0 for t in trades]
        side_wins = sum(1 for x in side_nets if x > 0)
        return (
            f"n={len(trades):4d} net={sum(side_nets):9.2f} "
            f"wr={side_wins / len(trades):7.2%} "
            f"avg={sum(side_nets) / len(trades):7.2f}"
        )

    return {
        "name": name,
        "trades": result.total_trades,
        "net_pnl": stats["net_pnl"],
        "return_pct": (result.ending_balance / START_BALANCE - 1) * 100,
        "win_rate": stats["win_rate"] * 100,
        "profit_factor": (
            gross_profit / gross_loss if gross_loss else float("inf")
        ),
        "max_drawdown": stats["max_drawdown"] * 100,
        "ending_balance": result.ending_balance,
        "total_costs": total_friction(result.trades),
        "gross_pnl": sum(t.pnl or 0.0 for t in result.trades),
        "avg_net_per_trade": (sum(nets) / len(nets)) if nets else 0.0,
        "longs": side_block(longs),
        "shorts": side_block(shorts),
        "exit_counts": dict(result.exit_counts),
    }


def main(argv):
    print("=" * 100)
    print("PHASE 8 - OUT-OF-SAMPLE VALIDATION HARNESS")
    print("=" * 100)
    print(f"  Phase 7 window      : {PHASE7_FIRST} .. {PHASE7_END}")
    print(f"  warm-up candles     : {WARMUP_CANDLES}")
    print(f"  fee / slippage      : {FEE_RATE} / {SLIPPAGE_RATE}")
    print(f"  starting balance    : {START_BALANCE:.2f}")
    print(f"  risk fraction       : {RISK_FRACTION}")
    print(f"  execution model     : next-candle open, closed candles only")

    if len(argv) < 2:
        print()
        print("  No validation file supplied.")
        print()
        print("  >>> VALIDATION NOT PERFORMED.")
        print("  >>> The repository contains no candles after "
              f"{PHASE7_END}.")
        print("  >>> Supply a CSV of unseen hourly candles, e.g.:")
        print("      python experiments/phase8/validation_harness.py "
              "data/VALIDATION.csv")
        return 2

    path = argv[1]
    print()
    print(f"  supplied file       : {path}")

    try:
        candles, problems = inspect(path)
    except Exception as exc:  # noqa: BLE001
        print(f"  could not read file : {type(exc).__name__}: {exc}")
        print()
        print("  >>> VALIDATION NOT PERFORMED - file is not usable.")
        return 2

    if problems:
        print()
        print("  REJECTED - the supplied file is not a valid unseen dataset:")
        for problem in problems:
            print(f"    - {problem}")
        print()
        print("  >>> VALIDATION NOT PERFORMED.")
        return 2

    boundary = WARMUP_CANDLES
    print()
    print(f"  candles             : {len(candles)}")
    print(f"  full range          : {candles[0].timestamp} .. "
          f"{candles[-1].timestamp}")
    print(f"  warm-up (context)   : {candles[0].timestamp} .. "
          f"{candles[boundary - 1].timestamp}")
    print(f"  validation window   : {candles[boundary].timestamp} .. "
          f"{candles[-1].timestamp}")
    print(f"  validation bars     : {len(candles) - boundary}")
    print()
    print("  Balance methodology : the account starts flat at the validation")
    print("                       boundary with the full starting balance.")
    print("                       Warm-up bars cannot open a position, so no")
    print("                       balance carries over from them.")
    print("  End-of-window       : any open position is closed at the final")
    print("                       candle's close (exit_reason=end_of_data).")

    results = [
        report_configuration(name, candles, config, boundary)
        for name, config in CONFIGURATIONS
    ]

    print()
    print("=" * 100)
    print("VALIDATION RESULTS")
    print("=" * 100)
    for r in results:
        print(f"\n--- {r['name']} ---")
        print(f"  trades              : {r['trades']}")
        print(f"  net P&L             : {r['net_pnl']:.2f}")
        print(f"  return              : {r['return_pct']:.2f}%")
        print(f"  win rate            : {r['win_rate']:.2f}%")
        print(f"  profit factor       : {r['profit_factor']:.4f}")
        print(f"  max drawdown        : {r['max_drawdown']:.2f}%")
        print(f"  ending balance      : {r['ending_balance']:.2f}")
        print(f"  total fees+slippage : {r['total_costs']:.2f}")
        print(f"  gross P&L           : {r['gross_pnl']:.2f}")
        print(f"  avg net per trade   : {r['avg_net_per_trade']:.2f}")
        print(f"  longs               : {r['longs']}")
        print(f"  shorts              : {r['shorts']}")
        print(f"  exits               : {r['exit_counts']}")
        verdict = "POSITIVE" if r["net_pnl"] > 0 else "NEGATIVE"
        print(f"  after costs         : {verdict}")

    a, b = results
    print()
    print("=" * 100)
    print("COMPARISON (baseline -> A2)")
    print("=" * 100)
    for key in ("trades", "net_pnl", "win_rate", "profit_factor",
                "max_drawdown", "ending_balance"):
        print(f"  {key:16s} {a[key]:>14} -> {b[key]:>14}")
    print()
    print("  Note: this comparison is descriptive only. No parameter was")
    print("  selected using these numbers, and one validation window on one")
    print("  asset cannot establish future performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
