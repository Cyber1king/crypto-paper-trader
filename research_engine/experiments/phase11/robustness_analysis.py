"""Phase 11: robustness analysis of the Phase 10 out-of-sample results.

Read-only with respect to strategy behaviour. Uses the two frozen Phase 10
configurations and the verified Phase 10 dataset. No tuning, no selection.

Records the input dataset hash and every configuration used.
"""
import sys
from dataclasses import replace, fields
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.acquisition import sha256_of  # noqa: E402
from crypto_paper_lab.backtest import run_backtest  # noqa: E402
from crypto_paper_lab.costs import TradingCosts  # noqa: E402
from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.dataset import validate_dataset  # noqa: E402
from crypto_paper_lab.report import create_report  # noqa: E402
from crypto_paper_lab.robustness import (  # noqa: E402
    block_bootstrap_ci,
    bootstrap_ci,
    concentration_stats,
    mark_to_market_drawdown,
    monthly_breakdown,
    monthly_summary,
    total_pnl_bootstrap_ci,
)
from crypto_paper_lab.strategy import StrategyConfig  # noqa: E402

DATASET = Path("data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv")
WARMUP = 48
START_BALANCE = 10_000.0
COSTS = TradingCosts(0.001, 0.0005)
SEED = 20260101
N_RESAMPLES = 10_000

SPEC_BASELINE = {
    "lookback": 20, "fast_period": 5, "slow_period": 12,
    "breakout_buffer": 0.001, "retest_tolerance": 0.002,
}
SPEC_A2_EXTRA = {"min_breakout_distance": 0.002}


def confirm_frozen() -> None:
    """Stop if stored defaults do not match the frozen specification."""

    stored = {f.name: getattr(StrategyConfig(), f.name) for f in fields(StrategyConfig)}
    problems = []
    for key, expected in SPEC_BASELINE.items():
        if stored[key] != expected:
            problems.append(f"baseline {key}: stored {stored[key]!r} != spec {expected!r}")
    if stored.get("min_breakout_distance") != 0.0:
        problems.append(
            f"baseline min_breakout_distance: stored "
            f"{stored.get('min_breakout_distance')!r} != spec 0.0"
        )
    if problems:
        print("FROZEN CONFIGURATION MISMATCH - STOPPING")
        for problem in problems:
            print(f"  {problem}")
        raise SystemExit(2)
    print("Frozen configuration check: baseline matches specification exactly")
    a2 = replace(StrategyConfig(), **SPEC_A2_EXTRA)
    diff = {k: v for k, v in vars(a2).items() if getattr(StrategyConfig(), k) != v}
    print(f"Frozen configuration check: A2 differs from baseline in {diff}")
    if set(diff) != set(SPEC_A2_EXTRA):
        print("A2 UNEXPECTEDLY DIFFERS - STOPPING")
        raise SystemExit(2)


def describe(name, cfg):
    print(f"  {name}:")
    for f in fields(StrategyConfig):
        print(f"    {f.name:22s} = {getattr(cfg, f.name)!r}")


def main() -> int:
    print("=" * 96)
    print("PHASE 11 - ROBUSTNESS RESEARCH")
    print("=" * 96)
    print(f"dataset            : {DATASET.as_posix()}")
    print(f"dataset sha256     : {sha256_of(DATASET)}")
    print(f"starting balance   : {START_BALANCE}")
    print(f"costs              : fee {COSTS.fee_rate}, slippage {COSTS.slippage_rate}")
    print(f"bootstrap seed     : {SEED}")
    print(f"bootstrap resamples: {N_RESAMPLES}")
    print()

    confirm_frozen()

    BASE = StrategyConfig()
    A2 = replace(BASE, **SPEC_A2_EXTRA)
    print()
    print("CONFIGURATIONS USED")
    describe("baseline", BASE)
    describe("A2", A2)

    candles = load_ohlcv_csv(DATASET)
    validate_dataset(candles)
    print()
    print(f"dataset candles    : {len(candles)}")
    print(f"file range         : {candles[0].timestamp} -> {candles[-1].timestamp}")
    print(f"validation window  : {candles[WARMUP].timestamp} -> {candles[-1].timestamp}")
    print(f"validation bars    : {len(candles) - WARMUP}")

    results = {}
    for name, cfg in (("baseline", BASE), ("A2", A2)):
        res = run_backtest(candles, config=cfg, costs=COSTS,
                           evaluation_start=WARMUP,
                           starting_balance=START_BALANCE)
        report = create_report(res)
        results[name] = (res, report)

    # -------- reproduce Phase 10 ----------------------------------------
    print()
    print("=" * 96)
    print("1. PHASE 10 REPRODUCTION (must match before any new analysis)")
    print("=" * 96)
    expected = {
        "baseline": {"trades": 105, "net_pnl": 5.05, "win_rate": 34.29,
                     "profit_factor": 1.0424, "max_drawdown": 0.34,
                     "ending_balance": 10005.05},
        "A2": {"trades": 90, "net_pnl": 14.07, "win_rate": 36.67,
               "profit_factor": 1.1330, "max_drawdown": 0.31,
               "ending_balance": 10014.07},
    }
    all_ok = True
    for name, (res, report) in results.items():
        exp = expected[name]
        got = {
            "trades": res.total_trades,
            "net_pnl": round(report["net_pnl"], 2),
            "win_rate": round(report["win_rate"] * 100, 2),
            "profit_factor": round(report["profit_factor"], 4),
            "max_drawdown": round(report["max_drawdown"] * 100, 2),
            "ending_balance": round(res.ending_balance, 2),
        }
        print(f"\n  {name}")
        for key, want in exp.items():
            have = got[key]
            ok = abs(float(have) - float(want)) < 0.005
            all_ok = all_ok and ok
            print(f"    {key:16s} phase10={want:>10}  now={have:>10}  "
                  f"{'MATCH' if ok else 'MISMATCH'}")
    print(f"\n  PHASE 10 REPRODUCED: {'YES' if all_ok else 'NO'}")
    if not all_ok:
        return 1

    for name, (res, _) in results.items():
        nets = [t.net_pnl for t in res.trades if t.net_pnl is not None]

        # -------- 2. drawdown -------------------------------------------
        print()
        print("=" * 96)
        print(f"2. DRAWDOWN - {name}")
        print("=" * 96)
        dd = mark_to_market_drawdown(res.trades, candles, START_BALANCE)
        print(f"  closed-trade max drawdown   : {dd.closed_trade_max_dd * 100:.4f}%")
        print(f"  mark-to-market max drawdown : {dd.mark_to_market_max_dd * 100:.4f}%")
        print(f"  peak equity (MTM)           : {dd.peak_equity:.2f}")
        print(f"  trough equity (MTM)         : {dd.trough_equity:.2f}")
        print(f"  trough timestamp (MTM)      : {dd.worst_trough_time}")
        print(f"  MTM samples (candles)       : {dd.samples}")
        print(f"  closed-trade samples        : {dd.closed_trade_samples}")
        ratio = (dd.mark_to_market_max_dd / dd.closed_trade_max_dd
                 if dd.closed_trade_max_dd else float("inf"))
        print(f"  MTM / closed ratio          : {ratio:.2f}x")
        print("  NOTE: the existing closed-trade metric is unchanged. The MTM")
        print("        figure is a separate, additional measure.")

        # -------- 3. statistical uncertainty ----------------------------
        print()
        print("=" * 96)
        print(f"3. STATISTICAL UNCERTAINTY - {name}")
        print("=" * 96)
        print(f"  trades: {len(nets)}")
        iid = bootstrap_ci(nets, n_resamples=N_RESAMPLES, seed=SEED)
        print(f"\n  IID bootstrap (seed {SEED}, {N_RESAMPLES} resamples)")
        print(f"    mean per trade : {iid['point']:+.4f}")
        print(f"    95% CI         : [{iid['ci_low']:+.4f}, {iid['ci_high']:+.4f}]")
        print(f"    contains zero  : {iid['ci_low'] <= 0 <= iid['ci_high']}")

        print(f"\n  Block bootstrap sensitivity (mean per trade, 95% CI)")
        print(f"    {'block':>6s} {'ci_low':>10s} {'ci_high':>10s} {'width':>10s} {'zero?':>7s}")
        block_results = {}
        for block in (1, 5, 10, 20, 30):
            r = block_bootstrap_ci(nets, block_length=block,
                                   n_resamples=N_RESAMPLES, seed=SEED)
            block_results[block] = r
            contains = r["ci_low"] <= 0 <= r["ci_high"]
            print(f"    {block:6d} {r['ci_low']:+10.4f} {r['ci_high']:+10.4f} "
                  f"{r['ci_high'] - r['ci_low']:10.4f} {str(contains):>7s}")

        r10 = block_results[10]
        print(f"\n  Reported interval (block length 10, seed {SEED}):")
        print(f"    mean per trade 95% CI : [{r10['ci_low']:+.4f}, {r10['ci_high']:+.4f}]")
        print(f"    contains zero         : {r10['ci_low'] <= 0 <= r10['ci_high']}")
        print(f"    i.i.d. CI width        : {iid['ci_high'] - iid['ci_low']:.4f}")
        print(f"    block(10) CI width     : {r10['ci_high'] - r10['ci_low']:.4f}")

        total_ci = total_pnl_bootstrap_ci(nets, block_length=10,
                                          n_resamples=N_RESAMPLES, seed=SEED)
        print(f"\n  Total P&L of this trade sequence (block 10):")
        print(f"    point estimate   : {total_ci['point']:+.2f}")
        print(f"    95% CI           : [{total_ci['ci_low']:+.2f}, "
              f"{total_ci['ci_high']:+.2f}]")
        print(f"    contains zero   : "
              f"{total_ci['ci_low'] <= 0 <= total_ci['ci_high']}")

        # -------- 4. monthly -------------------------------------------
        print()
        print("=" * 96)
        print(f"4. MONTHLY VARIABILITY - {name}")
        print("=" * 96)
        rows = monthly_breakdown(res.trades, START_BALANCE)
        print(f"  {'month':9s} {'trades':>7s} {'net':>9s} {'ret%':>8s} "
              f"{'gross':>9s} {'costs':>8s} {'w':>3s} {'l':>3s}  sign")
        for row in rows:
            print(f"  {row['month']:9s} {row['trades']:7d} {row['net_pnl']:+9.2f} "
                  f"{row['return_pct']:+8.3f} {row['gross_pnl']:+9.2f} "
                  f"{row['costs']:8.2f} {row['wins']:3d} {row['losses']:3d}  "
                  f"{row['sign']}")
        summary = monthly_summary(rows, START_BALANCE)
        print(f"\n  months with trades   : {summary['months_with_trades']}")
        print(f"  positive months      : {summary['positive_months']}")
        print(f"  negative months      : {summary['negative_months']}")
        print(f"  best month           : {summary['max_month']} "
              f"({summary['max_month_net']:+.2f})")
        print(f"  worst month          : {summary['min_month']} "
              f"({summary['min_month_net']:+.2f})")
        print(f"  range                : {summary['range_pct']:.3f}% of balance")
        print(f"  mean monthly return  : "
              f"{summary['mean_monthly_return_pct']:+.3f}%")
        print(f"  months with no trades: "
              f"8 - {summary['months_with_trades']} = "
              f"{8 - summary['months_with_trades']}")

        # -------- 5. concentration -------------------------------------
        print()
        print("=" * 96)
        print(f"5. TRADE CONCENTRATION AND DEPENDENCE - {name}")
        print("=" * 96)
        conc = concentration_stats(nets)
        print(f"  trades                    : {conc['n']}")
        print(f"  net                       : {conc['net']:+.2f}")
        print(f"  gross profit              : {conc['gross_profit']:+.2f}")
        print(f"  gross loss                : {conc['gross_loss']:.2f}")
        print(f"  largest single win        : {conc['largest_win']:+.2f}")
        print(f"  largest single loss       : {conc['largest_loss']:+.2f}")
        print(f"  net excl. largest win     : {conc['wins_without_top1_net']:+.2f}")
        print(f"  net excl. largest loss    : "
              f"{conc['net'] + conc['largest_loss']:+.2f}")
        print(f"  median trade              : {conc['median']:+.2f}")
        print(f"  mean trade                : {conc['mean']:+.4f}")
        print(f"  stdev of trade            : {conc['stdev']:.4f}")
        for label, key in (("top 1 win", "top1_win_share_of_net"),
                           ("top 3 wins", "top3_win_share_of_net"),
                           ("top 5 wins", "top5_win_share_of_net"),
                           ("worst 1", "bottom1_share_of_net"),
                           ("worst 5", "bottom5_share_of_net")):
            value = conc[key]
            if value is not None:
                print(f"  {label:26s}: {value * 100:+.1f}% of net P&L")

    # -------- 6. side-by-side -------------------------------------------
    print()
    print("=" * 96)
    print("6. BASELINE vs A2 - SIDE BY SIDE (descriptive, not a ranking)")
    print("=" * 96)
    base_res, base_rep = results["baseline"]
    a2_res, a2_rep = results["A2"]
    base_nets = [t.net_pnl for t in base_res.trades if t.net_pnl is not None]
    a2_nets = [t.net_pnl for t in a2_res.trades if t.net_pnl is not None]
    base_rows = monthly_breakdown(base_res.trades, START_BALANCE)
    a2_rows = monthly_breakdown(a2_res.trades, START_BALANCE)
    base_sum = monthly_summary(base_rows, START_BALANCE)
    a2_sum = monthly_summary(a2_rows, START_BALANCE)
    base_dd = mark_to_market_drawdown(base_res.trades, candles, START_BALANCE)
    a2_dd = mark_to_market_drawdown(a2_res.trades, candles, START_BALANCE)
    base_blk = block_bootstrap_ci(base_nets, block_length=10,
                                  n_resamples=N_RESAMPLES, seed=SEED)
    a2_blk = block_bootstrap_ci(a2_nets, block_length=10,
                                n_resamples=N_RESAMPLES, seed=SEED)

    rows = [
        ("trades", base_res.total_trades, a2_res.total_trades),
        ("net P&L", round(base_rep["net_pnl"], 2), round(a2_rep["net_pnl"], 2)),
        ("return %", round((base_res.ending_balance / START_BALANCE - 1) * 100, 3),
         round((a2_res.ending_balance / START_BALANCE - 1) * 100, 3)),
        ("win rate %", round(base_rep["win_rate"] * 100, 2),
         round(a2_rep["win_rate"] * 100, 2)),
        ("profit factor", round(base_rep["profit_factor"], 4),
         round(a2_rep["profit_factor"], 4)),
        ("max DD closed-trade %", round(base_rep["max_drawdown"] * 100, 3),
         round(a2_rep["max_drawdown"] * 100, 3)),
        ("max DD mark-to-market %",
         round(base_dd.mark_to_market_max_dd * 100, 3),
         round(a2_dd.mark_to_market_max_dd * 100, 3)),
        ("positive months", base_sum["positive_months"], a2_sum["positive_months"]),
        ("negative months", base_sum["negative_months"], a2_sum["negative_months"]),
        ("months with trades", base_sum["months_with_trades"],
         a2_sum["months_with_trades"]),
        ("mean/trade 95% CI low", round(base_blk["ci_low"], 4),
         round(a2_blk["ci_low"], 4)),
        ("mean/trade 95% CI high", round(base_blk["ci_high"], 4),
         round(a2_blk["ci_high"], 4)),
        ("CI contains zero",
         str(base_blk["ci_low"] <= 0 <= base_blk["ci_high"]),
         str(a2_blk["ci_low"] <= 0 <= a2_blk["ci_high"])),
    ]
    print(f"  {'measure':26s} {'baseline':>18s} {'A2':>18s}")
    print("  " + "-" * 66)
    for label, b, a in rows:
        print(f"  {label:26s} {str(b):>18s} {str(a):>18s}")

    print()
    print("  Both configurations show positive net P&L on this window, and")
    print("  both have a mean-trade confidence interval that contains zero.")
    print("  These are observations from a single evaluation window. No")
    print("  ranking, score, or selection is expressed or implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
