"""Phase 7 step 2-4: controlled entry-signal experiments.

Reuses the existing optional gates verified in Phase 5
(``min_breakout_distance``, ``breakout_confirm_bars``) plus the Phase 7
directional diagnostic gate (``allowed_sides``). No new mechanism is
introduced and no default is altered.

Execution model is unchanged throughout: signals from closed candles only,
fills at the next candle's open, fee 0.001 + slippage 0.0005 per trade.

All 2024/2025 figures are EXPLORATORY and in-sample. Both years were
examined in Phases 2-6; neither is an untouched out-of-sample test.
"""
import json
from collections import defaultdict
from dataclasses import replace

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.strategy import StrategyConfig

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"
BASE = StrategyConfig()
START_BALANCE = 10_000.0
COSTS = TradingCosts(0.001, 0.0005)

candles = load_ohlcv_csv(DATASET)
validate_dataset(candles)

years = defaultdict(list)
for candle in candles:
    years[candle.timestamp.year].append(candle)

SPLITS = {"full": candles, "2024": years[2024], "2025": years[2025]}

LONG_ONLY = ("long",)
SHORT_ONLY = ("short",)

EXPERIMENTS = [
    # ---------------- control ----------------
    ("P0_baseline", BASE, "control", "unchanged V1 defaults"),

    # ---------------- Experiment A ----------------
    ("A1_min_dist=0.001", replace(BASE, min_breakout_distance=0.001), "A",
     "require close >=0.1% beyond level (nominally equal to breakout_buffer)"),
    ("A2_min_dist=0.002", replace(BASE, min_breakout_distance=0.002), "A",
     "require close >=0.2% beyond level"),
    ("A3_min_dist=0.003", replace(BASE, min_breakout_distance=0.003), "A",
     "require close >=0.3% beyond level"),
    ("A4_min_dist=0.004", replace(BASE, min_breakout_distance=0.004), "A",
     "require close >=0.4% beyond level"),

    # ---------------- Experiment B ----------------
    ("B2_confirm_2", replace(BASE, breakout_confirm_bars=2), "B",
     "require the last 2 closes to hold beyond the level"),
    ("B3_confirm_3", replace(BASE, breakout_confirm_bars=3), "B",
     "require the last 3 closes to hold beyond the level"),

    # ---------------- Experiment C ----------------
    ("C1_long_only", replace(BASE, allowed_sides=LONG_ONLY), "C",
     "diagnostic: block short ENTRIES only (exits unchanged)"),
    ("C2_short_only", replace(BASE, allowed_sides=SHORT_ONLY), "C",
     "diagnostic: block long ENTRIES only (exits unchanged)"),

    # ---------------- Experiment D ----------------
    ("D1_dist0.002+conf2",
     replace(BASE, min_breakout_distance=0.002, breakout_confirm_bars=2), "D",
     "combination of the two individually-promising A and B filters"),
    ("D2_dist0.002+long_only",
     replace(BASE, min_breakout_distance=0.002, allowed_sides=LONG_ONLY), "D",
     "combination of A2 with the long-only diagnostic"),
    ("D3_conf2+long_only",
     replace(BASE, breakout_confirm_bars=2, allowed_sides=LONG_ONLY), "D",
     "combination of B2 with the long-only diagnostic"),
]


def metrics(result):
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

    def cls_of(t):
        if "retest" in t.reason:
            return f"{t.side}_retest"
        if "breakdown" in t.reason:
            return f"{t.side}_breakdown"
        return f"{t.side}_breakout"

    groups = defaultdict(list)
    for t in result.trades:
        groups[cls_of(t)].append(t)

    def gsum(rs):
        return round(sum(t.net_pnl or 0.0 for t in rs), 2)

    return {
        "trades": result.total_trades,
        "net_pnl": round(result.ending_balance - result.starting_balance, 2),
        "return_pct": round(
            (result.ending_balance / result.starting_balance - 1) * 100, 3
        ),
        "win_rate": round(len(wins) / len(nets) * 100, 3) if nets else 0.0,
        "profit_factor": round(gp / gl, 4) if gl else float("inf"),
        "max_drawdown": round(mdd * 100, 3),
        "ending_balance": round(result.ending_balance, 2),
        "gross_pnl": round(sum(t.pnl or 0.0 for t in result.trades), 2),
        "total_costs": round(sum(t.costs for t in result.trades), 2),
        "n_long": len(longs),
        "n_short": len(shorts),
        "long_net": gsum(longs),
        "short_net": gsum(shorts),
        "long_win_rate": round(
            sum(1 for t in longs if (t.net_pnl or 0) > 0) / len(longs) * 100, 2
        ) if longs else 0.0,
        "short_win_rate": round(
            sum(1 for t in shorts if (t.net_pnl or 0) > 0) / len(shorts) * 100, 2
        ) if shorts else 0.0,
        "n_lb": len(groups["long_breakout"]), "lb_net": gsum(groups["long_breakout"]),
        "n_lr": len(groups["long_retest"]), "lr_net": gsum(groups["long_retest"]),
        "n_sb": len(groups["short_breakdown"]), "sb_net": gsum(groups["short_breakdown"]),
        "n_sr": len(groups["short_retest"]), "sr_net": gsum(groups["short_retest"]),
        "exit_counts": dict(result.exit_counts),
    }


rows = []
for name, cfg, group, why in EXPERIMENTS:
    entry = {"name": name, "group": group, "why": why, "splits": {}}
    for split_name, subset in SPLITS.items():
        entry["splits"][split_name] = metrics(run_backtest(subset, config=cfg))
    rows.append(entry)

# also record the config fields that differ from baseline
for row, (_, cfg, _, _) in zip(rows, EXPERIMENTS):
    row["overrides"] = {
        k: v for k, v in vars(cfg).items()
        if getattr(BASE, k) != v
    }

with open("experiments/phase7/RESULTS_data.json", "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=2, default=str)

print("#" * 108)
print("# PHASE 7 ENTRY-SIGNAL EXPERIMENTS  (fee 0.001, slippage 0.0005, start 10000)")
print("# all 2024/2025 figures are EXPLORATORY and IN-SAMPLE")
print("#" * 108)
for row in rows:
    print()
    print(f"### [{row['group']}] {row['name']}")
    print(f"    why     : {row['why']}")
    print(f"    override: {row['overrides']}")
    for split in ("full", "2024", "2025"):
        s = row["splits"][split]
        b = rows[0]["splits"][split]
        dn = s["trades"] - b["trades"]
        print(f"    {split:5s} n={s['trades']:4d} ({dn:+5d})  net={s['net_pnl']:9.2f}  "
              f"ret={s['return_pct']:7.2f}%  wr={s['win_rate']:6.2f}%  "
              f"pf={s['profit_factor']:6.3f}  mdd={s['max_drawdown']:6.2f}%  "
              f"end={s['ending_balance']:9.2f}")
        print(f"          gross={s['gross_pnl']:8.2f} costs={s['total_costs']:7.2f} | "
              f"L n={s['n_long']:3d} wr={s['long_win_rate']:5.1f}% net={s['long_net']:8.2f} | "
              f"S n={s['n_short']:3d} wr={s['short_win_rate']:5.1f}% net={s['short_net']:8.2f}")
        print(f"          lb n={s['n_lb']:3d} net={s['lb_net']:8.2f} | "
              f"sb n={s['n_sb']:3d} net={s['sb_net']:8.2f} | "
              f"lr n={s['n_lr']:2d} net={s['lr_net']:7.2f} | "
              f"sr n={s['n_sr']:2d} net={s['sr_net']:7.2f}")
