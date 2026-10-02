"""Phase 5 step 3-5: controlled experiments, one modification at a time.

Every run uses the same dataset and the same default paper-trading costs
(fee_rate=0.001, slippage_rate=0.0005). Modifications are optional
StrategyConfig fields whose defaults reproduce the V1 baseline exactly.
"""
import time
from collections import defaultdict
from dataclasses import replace

from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.analysis import analyze_trade_directions, analyze_trade_signals

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"
BASE = StrategyConfig()

candles = load_ohlcv_csv(DATASET)
validate_dataset(candles)

years = defaultdict(list)
for candle in candles:
    years[candle.timestamp.year].append(candle)

SPLITS = {
    "full": candles,
    "2024": years[2024],
    "2025": years[2025],
}

# name -> (config, one-line justification)
EXPERIMENTS = [
    ("baseline", BASE, "unchanged V1 default configuration"),
    ("E1_min_breakout_distance=0.002",
     replace(BASE, min_breakout_distance=0.002),
     "require close >=0.2% beyond the broken level (q1/q2 breakouts had 13-29% WR)"),
    ("E1_min_breakout_distance=0.004",
     replace(BASE, min_breakout_distance=0.004),
     "require close >=0.4% beyond the broken level"),
    ("E2_trend_strength_min=0.003",
     replace(BASE, trend_strength_min=0.003),
     "require fast/slow SMA separation >=0.3% (baseline 0.1%) to call a trend"),
    ("E2_trend_strength_min=0.006",
     replace(BASE, trend_strength_min=0.006),
     "require fast/slow SMA separation >=0.6% to call a trend"),
    ("E3_retest_use_close=True",
     replace(BASE, retest_use_close=True),
     "require the retest candle close (not wick) to sit within tolerance of the level"),
    ("E4_breakout_confirm_bars=2",
     replace(BASE, breakout_confirm_bars=2),
     "require the last 2 closes to hold beyond the broken level"),
]

results = {}
for name, cfg, why in EXPERIMENTS:
    row = {"why": why, "splits": {}}
    for split_name, subset in SPLITS.items():
        res = run_backtest(subset, config=cfg)
        net = res.ending_balance - res.starting_balance
        nets = [t.net_pnl for t in res.trades if t.net_pnl is not None]
        wins = [x for x in nets if x > 0]
        losses = [x for x in nets if x < 0]
        gp, gl = sum(wins), abs(sum(losses))
        bal = peak = res.starting_balance
        mdd = 0.0
        for x in nets:
            bal += x
            peak = max(peak, bal)
            mdd = max(mdd, (peak - bal) / peak)
        longs = [t for t in res.trades if t.side == "long"]
        shorts = [t for t in res.trades if t.side == "short"]
        cls = defaultdict(list)
        for t in res.trades:
            kind = ("retest" if "retest" in t.reason
                    else "breakdown" if "breakdown" in t.reason
                    else "breakout")
            cls[f"{t.side}_{kind}"].append(t)
        row["splits"][split_name] = {
            "trades": res.total_trades,
            "net_pnl": net,
            "win_rate": len(wins) / len(nets) if nets else 0.0,
            "profit_factor": gp / gl if gl else float("inf"),
            "average_pnl": sum(nets) / len(nets) if nets else 0.0,
            "max_drawdown": mdd,
            "ending_balance": res.ending_balance,
            "n_long": len(longs),
            "n_short": len(shorts),
            "long_net": sum(t.net_pnl or 0.0 for t in longs),
            "short_net": sum(t.net_pnl or 0.0 for t in shorts),
            "n_lb": len(cls["long_breakout"]),
            "n_lr": len(cls["long_retest"]),
            "n_sb": len(cls["short_breakdown"]),
            "n_sr": len(cls["short_retest"]),
            "lb_net": sum(t.net_pnl or 0.0 for t in cls["long_breakout"]),
            "lr_net": sum(t.net_pnl or 0.0 for t in cls["long_retest"]),
            "sb_net": sum(t.net_pnl or 0.0 for t in cls["short_breakdown"]),
            "sr_net": sum(t.net_pnl or 0.0 for t in cls["short_retest"]),
        }
    results[name] = row

print("#" * 78)
print("# RESULTS (default costs: fee 0.001, slippage 0.0005)")
print("#" * 78)
for name, row in results.items():
    print()
    print(f"### {name}")
    print(f"    why: {row['why']}")
    b = results["baseline"]["splits"]
    for split_name, s in row["splits"].items():
        d = s["trades"] - b[split_name]["trades"]
        print(f"    {split_name:5s} n={s['trades']:4d} ({d:+4d})  net={s['net_pnl']:9.2f}  "
              f"wr={s['win_rate']:7.2%}  pf={s['profit_factor']:6.3f}  "
              f"avg={s['average_pnl']:6.2f}  mdd={s['max_drawdown']:6.2%}  "
              f"end={s['ending_balance']:9.2f}")
        print(f"          sides: long n={s['n_long']:3d} net={s['long_net']:8.2f} | "
              f"short n={s['n_short']:3d} net={s['short_net']:8.2f}")
        print(f"          class: lb n={s['n_lb']:3d} net={s['lb_net']:8.2f} | "
              f"sb n={s['n_sb']:3d} net={s['sb_net']:8.2f} | "
              f"lr n={s['n_lr']:2d} net={s['lr_net']:7.2f} | "
              f"sr n={s['n_sr']:2d} net={s['sr_net']:7.2f}")

print()
print("#" * 78)
print("# ZERO-COST DIAGNOSTIC (same config, fee=0, slippage=0)")
print("#" * 78)
for split_name, subset in SPLITS.items():
    res = run_backtest(subset, config=BASE, costs=TradingCosts(0.0, 0.0))
    res_cost = run_backtest(subset, config=BASE)
    nets = [t.net_pnl for t in res.trades if t.net_pnl is not None]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp, gl = sum(wins), abs(sum(losses))
    bal = peak = res.starting_balance
    mdd = 0.0
    for x in nets:
        bal += x
        peak = max(peak, bal)
        mdd = max(mdd, (peak - bal) / peak)
    total_costs = sum(t.costs for t in res.trades)
    print(f"  {split_name:5s} n={res.total_trades:4d}  "
          f"gross_net(0 cost)={res.ending_balance - res.starting_balance:9.2f}  "
          f"wr={len(wins) / len(nets):7.2%}  pf={gp / gl if gl else float('inf'):6.3f}  "
          f"mdd={mdd:6.2%}")
    print(f"        with default costs  net={res_cost.ending_balance - res_cost.starting_balance:9.2f}  "
          f"total costs charged={total_costs:8.2f}")
