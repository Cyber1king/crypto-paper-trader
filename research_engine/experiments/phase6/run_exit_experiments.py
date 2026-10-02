"""Phase 6 Task 3-5: controlled exit-rule experiments.

Pre-registered experiment set (chosen from reasoning about the measured
holding-period structure and typical BTC 1h range, NOT by scanning for the
best result). Entry signals are never modified: only exit behaviour changes.

Execution model for all new rules: detection on a bar that has already
closed, fill at the open of the following bar. No intrabar fills assumed.
"""
from collections import defaultdict
from dataclasses import replace

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.strategy import StrategyConfig

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"
BASE = StrategyConfig()

candles = load_ohlcv_csv(DATASET)
validate_dataset(candles)

years = defaultdict(list)
for c in candles:
    years[c.timestamp.year].append(c)

SPLITS = {"full": candles, "2024": years[2024], "2025": years[2025]}

EXPERIMENTS = [
    # A. unchanged baseline
    ("A_baseline", BASE,
     "opposite-signal exit only (unchanged V1)"),
    # B. maximum holding period
    ("B_maxhold=12", replace(BASE, max_holding_bars=12),
     "force exit 12 bars after entry"),
    ("B_maxhold=24", replace(BASE, max_holding_bars=24),
     "force exit 24 bars after entry (last losing bucket)"),
    ("B_maxhold=48", replace(BASE, max_holding_bars=48),
     "force exit 48 bars after entry"),
    # C. fixed stop-loss
    ("C_stop=0.5%", replace(BASE, stop_loss_pct=0.005),
     "stop 0.5% from entry (approx one 1h bar)"),
    ("C_stop=1.0%", replace(BASE, stop_loss_pct=0.01),
     "stop 1.0% from entry"),
    ("C_stop=2.0%", replace(BASE, stop_loss_pct=0.02),
     "stop 2.0% from entry"),
    # D. fixed take-profit
    ("D_target=0.5%", replace(BASE, take_profit_pct=0.005),
     "target 0.5% from entry"),
    ("D_target=1.0%", replace(BASE, take_profit_pct=0.01),
     "target 1.0% from entry"),
    ("D_target=2.0%", replace(BASE, take_profit_pct=0.02),
     "target 2.0% from entry"),
    # E. combined (pre-registered pairs, not chosen by result)
    ("E_stop1.0+target1.0", replace(BASE, stop_loss_pct=0.01, take_profit_pct=0.01),
     "symmetric 1% stop / 1% target"),
    ("E_stop1.0+target2.0", replace(BASE, stop_loss_pct=0.01, take_profit_pct=0.02),
     "asymmetric 1% stop / 2% target (1:2 reward:risk)"),
]


def summarise(result):
    nets = [t.net_pnl for t in result.trades if t.net_pnl is not None]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp, gl = sum(wins), abs(sum(losses))
    bal = peak = result.starting_balance
    mdd = 0.0
    for x in nets:
        bal += x
        peak = max(peak, bal)
        mdd = max(mdd, (peak - bal) / peak)
    longs = [t for t in result.trades if t.side == "long"]
    shorts = [t for t in result.trades if t.side == "short"]

    def side_net(rs):
        return sum(t.net_pnl or 0.0 for t in rs)

    return {
        "n": result.total_trades,
        "net": result.ending_balance - result.starting_balance,
        "wr": len(wins) / len(nets) if nets else 0.0,
        "pf": gp / gl if gl else float("inf"),
        "avg": sum(nets) / len(nets) if nets else 0.0,
        "mdd": mdd,
        "end": result.ending_balance,
        "n_long": len(longs),
        "n_short": len(shorts),
        "long_net": side_net(longs),
        "short_net": side_net(shorts),
        "exits": dict(result.exit_counts),
    }


table = {}
for name, cfg, why in EXPERIMENTS:
    table[name] = {"why": why, "splits": {}}
    for split_name, subset in SPLITS.items():
        table[name]["splits"][split_name] = summarise(
            run_backtest(subset, config=cfg)
        )

print("#" * 100)
print("# PHASE 6 EXIT EXPERIMENTS  (default costs: fee 0.001, slippage 0.0005)")
print("#" * 100)
for name, _, why in EXPERIMENTS:
    row = table[name]
    print()
    print(f"### {name}")
    print(f"    why: {why}")
    b = table["A_baseline"]["splits"]
    for split_name in ("full", "2024", "2025"):
        s = row["splits"][split_name]
        d = s["n"] - b[split_name]["n"]
        print(f"    {split_name:5s} n={s['n']:4d} ({d:+4d})  net={s['net']:9.2f}  "
              f"wr={s['wr']:7.2%}  pf={s['pf']:6.3f}  avg={s['avg']:6.2f}  "
              f"mdd={s['mdd']:6.2%}  end={s['end']:9.2f}")
        print(f"          long n={s['n_long']:3d} net={s['long_net']:8.2f} | "
              f"short n={s['n_short']:3d} net={s['short_net']:8.2f}")
        print(f"          exits: {s['exits']}")

print()
print("#" * 100)
print("# YEAR-AGREEMENT CHECK (does the change help in BOTH years?)")
print("#" * 100)
base = table["A_baseline"]["splits"]
print(f"{'experiment':24s} {'2024 delta':>12s} {'2025 delta':>12s} {'both better':>12s}")
for name, _, _ in EXPERIMENTS[1:]:
    d24 = table[name]["splits"]["2024"]["net"] - base["2024"]["net"]
    d25 = table[name]["splits"]["2025"]["net"] - base["2025"]["net"]
    verdict = "YES" if d24 > 0 and d25 > 0 else ("no" if d24 <= 0 and d25 <= 0 else "MIXED")
    print(f"{name:24s} {d24:+12.2f} {d25:+12.2f} {verdict:>12s}")
