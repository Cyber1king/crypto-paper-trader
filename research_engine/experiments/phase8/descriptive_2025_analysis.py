"""Phase 8: descriptive 2024 vs 2025 analysis.

DESCRIPTIVE ONLY. No filter is created, tuned, or tested here. The purpose is
to document how the two years differed in already-measurable conditions, so
that the Phase 7 year-inconsistency has a factual basis.

Observed differences are reported as observations. Candidate explanations are
labelled explicitly as hypotheses and are NOT tested.
"""
import statistics
from collections import defaultdict
from dataclasses import replace

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.stats import total_friction
from crypto_paper_lab.strategy import StrategyConfig

BASE = StrategyConfig()
A2 = replace(BASE, min_breakout_distance=0.002)

candles = load_ohlcv_csv("data/BTCUSDT_1h_Cleaned (1).csv")
validate_dataset(candles)

years = defaultdict(list)
for c in candles:
    years[c.timestamp.year].append(c)


def market_profile(year_candles, config):
    """Market conditions already computable from OHLCV."""
    closes = [c.close for c in year_candles]
    rets = [
        (b - a) / a for a, b in zip(closes, closes[1:])
    ]
    ranges = [
        (c.high - c.low) / c.close for c in year_candles
    ]
    bodies = [
        abs(c.close - c.open) / c.open for c in year_candles
    ]

    # trend strength: relative gap between the fast and slow SMA at each bar
    fast, slow = config.fast_period, config.slow_period
    gaps = []
    for i in range(slow, len(closes)):
        f = sum(closes[i - fast:i]) / fast
        s = sum(closes[i - slow:i]) / slow
        gaps.append(abs(f - s) / s)

    return {
        "bars": len(year_candles),
        "first_close": closes[0],
        "last_close": closes[-1],
        "total_return_pct": (closes[-1] / closes[0] - 1) * 100,
        "mean_abs_hourly_ret_pct": statistics.fmean(abs(r) for r in rets) * 100,
        "stdev_hourly_ret_pct": statistics.stdev(rets) * 100,
        "annualised_vol_pct": statistics.stdev(rets) * (24 * 365) ** 0.5 * 100,
        "mean_range_pct": statistics.fmean(ranges) * 100,
        "median_range_pct": statistics.median(ranges) * 100,
        "mean_body_pct": statistics.fmean(bodies) * 100,
        "mean_trend_gap_pct": statistics.fmean(gaps) * 100,
        "median_trend_gap_pct": statistics.median(gaps) * 100,
    }


def trade_profile(result):
    trades = list(result.trades)
    nets = [t.net_pnl for t in trades if t.net_pnl is not None]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp, gl = sum(wins), abs(sum(losses))

    def side(side_name):
        rs = [t for t in trades if t.side == side_name]
        if not rs:
            return f"n=0"
        sn = [t.net_pnl or 0.0 for t in rs]
        sw = sum(1 for x in sn if x > 0)
        return (f"n={len(rs):3d} net={sum(sn):8.2f} "
                f"wr={sw / len(rs):6.1%} avg={sum(sn) / len(rs):6.2f}")

    def kind(kind_name):
        rs = [t for t in trades if kind_name in t.reason]
        if not rs:
            return f"n=0"
        kn = [t.net_pnl or 0.0 for t in rs]
        kw = sum(1 for x in kn if x > 0)
        return (f"n={len(rs):3d} net={sum(kn):8.2f} "
                f"wr={kw / len(rs):6.1%} avg={sum(kn) / len(rs):6.2f}")

    held = [t.bars_held for t in trades]
    short_held = [t.bars_held for t in trades if t.bars_held <= 24]
    long_held = [t.bars_held for t in trades if t.bars_held > 24]

    # entry spacing in bars
    stamps = [t.entry_time for t in trades]
    spacing = [
        (b - a).total_seconds() / 3600.0 for a, b in zip(stamps, stamps[1:])
    ]

    return {
        "trades": len(trades),
        "net_pnl": result.ending_balance - result.starting_balance,
        "win_rate": len(wins) / len(nets) if nets else 0.0,
        "profit_factor": gp / gl if gl else float("inf"),
        "gross_pnl": sum(t.pnl or 0.0 for t in trades),
        "costs": total_friction(trades),
        "trades_per_1000_bars": len(trades) / (len(trades) and 1 or 1),
        "mean_spacing_hours": statistics.fmean(spacing) if spacing else 0.0,
        "median_bars_held": statistics.median(held) if held else 0.0,
        "mean_bars_held": statistics.fmean(held) if held else 0.0,
        "pct_held_le_24": (
            len(short_held) / len(held) * 100 if held else 0.0
        ),
        "net_le_24": sum(
            t.net_pnl or 0.0 for t in trades if t.bars_held <= 24
        ),
        "net_gt_24": sum(
            t.net_pnl or 0.0 for t in trades if t.bars_held > 24
        ),
        "long": side("long"),
        "short": side("short"),
        "long_breakout": kind("breakout") if True else "",
        "short_breakdown": kind("breakdown"),
        "long_retest": kind("retest"),
    }


print("=" * 104)
print("PHASE 8 - DESCRIPTIVE 2024 vs 2025 COMPARISON (NOT A VALIDATION, NOT A NEW EXPERIMENT)")
print("=" * 104)

profiles = {y: market_profile(years[y], BASE) for y in (2024, 2025)}

print("\n### A. MARKET CONDITIONS (from OHLCV only)")
print(f"  {'measure':32s} {'2024':>16s} {'2025':>16s}")
print("  " + "-" * 68)
for key, label in (
    ("bars", "hourly candles"),
    ("first_close", "first close"),
    ("last_close", "last close"),
    ("total_return_pct", "total return %"),
    ("mean_abs_hourly_ret_pct", "mean |1h return| %"),
    ("stdev_hourly_ret_pct", "stdev 1h return %"),
    ("annualised_vol_pct", "annualised vol %"),
    ("mean_range_pct", "mean (high-low)/close %"),
    ("median_range_pct", "median (high-low)/close %"),
    ("mean_body_pct", "mean |close-open|/open %"),
    ("mean_trend_gap_pct", "mean |fastMA-slowMA|/slowMA %"),
    ("median_trend_gap_pct", "median |fastMA-slowMA|/slowMA %"),
):
    a, b = profiles[2024][key], profiles[2025][key]
    fmt = (lambda v: f"{v:.2f}") if isinstance(a, float) else (lambda v: f"{v}")
    print(f"  {label:32s} {fmt(a):>16s} {fmt(b):>16s}")

for label, cfg in (("BASELINE", BASE), ("A2", A2)):
    print(f"\n### B. STRATEGY ACTIVITY - {label}")
    print(f"  {'measure':32s} {'2024':>18s} {'2025':>18s}")
    print("  " + "-" * 70)
    tp = {
        y: trade_profile(run_backtest(years[y], config=cfg)) for y in (2024, 2025)
    }
    for key, label2 in (
        ("trades", "trades"),
        ("net_pnl", "net P&L"),
        ("gross_pnl", "gross P&L"),
        ("costs", "costs"),
        ("win_rate", "win rate"),
        ("profit_factor", "profit factor"),
        ("mean_spacing_hours", "mean spacing between entries (h)"),
        ("mean_bars_held", "mean bars held"),
        ("median_bars_held", "median bars held"),
        ("pct_held_le_24", "% trades held <= 24 bars"),
        ("net_le_24", "net P&L of <=24-bar trades"),
        ("net_gt_24", "net P&L of >24-bar trades"),
    ):
        a, b = tp[2024][key], tp[2025][key]
        if key == "win_rate":
            print(f"  {label2:32s} {a:>17.2%} {b:>18.2%}")
        elif isinstance(a, float):
            print(f"  {label2:32s} {a:>18.2f} {b:>18.2f}")
        else:
            print(f"  {label2:32s} {a:>18} {b:>18}")
    print()
    for side_key in ("long", "short", "long_breakout", "short_breakdown",
                     "long_retest"):
        name = side_key.replace("_", " ")
        print(f"    {name:16s} 2024: {tp[2024][side_key]}")
        print(f"    {'':16s} 2025: {tp[2025][side_key]}")

print()
print("=" * 104)
print("OBSERVED DIFFERENCES (facts)")
print("=" * 104)
b24, b25 = (trade_profile(run_backtest(years[y], config=BASE)) for y in (2024, 2025))
m24, m25 = profiles[2024], profiles[2025]
print(f"  1. 2024 returned {m24['total_return_pct']:+.1f}% over the year; "
      f"2025 returned {m25['total_return_pct']:+.1f}%.")
print(f"  2. Annualised realised volatility was "
      f"{m24['annualised_vol_pct']:.0f}% in 2024 vs "
      f"{m25['annualised_vol_pct']:.0f}% in 2025.")
print(f"  3. Mean hourly bar range was {m24['mean_range_pct']:.3f}% of close in "
      f"2024 vs {m25['mean_range_pct']:.3f}% in 2025.")
print(f"  4. Median |fastMA-slowMA|/slowMA was "
      f"{m24['median_trend_gap_pct']:.3f}% in 2024 vs "
      f"{m25['median_trend_gap_pct']:.3f}% in 2025.")
print(f"  5. Baseline trades: {b24['trades']} in 2024 vs {b25['trades']} in "
      f"2025 on almost identical bar counts.")
print(f"  6. Mean entry spacing: {b24['mean_spacing_hours']:.1f} h in 2024 vs "
      f"{b25['mean_spacing_hours']:.1f} h in 2025.")
print(f"  7. Share of trades closed within 24 bars: "
      f"{b24['pct_held_le_24']:.1f}% in 2024 vs {b25['pct_held_le_24']:.1f}% in 2025.")
print(f"  8. P&L from <=24-bar trades: {b24['net_le_24']:+.2f} (2024) vs "
      f"{b25['net_le_24']:+.2f} (2025).")
print(f"  9. P&L from >24-bar trades:  {b24['net_gt_24']:+.2f} (2024) vs "
      f"{b25['net_gt_24']:+.2f} (2025).")
print(f" 10. Baseline gross P&L before costs: {b24['gross_pnl']:+.2f} (2024) vs "
      f"{b25['gross_pnl']:+.2f} (2025); costs were "
      f"{b24['costs']:.2f} and {b25['costs']:.2f}.")
print(f" 11. Long net: {b24['long']} (2024) | {b25['long']} (2025)")
print(f" 12. Short net: {b24['short']} (2024) | {b25['short']} (2025)")

print()
print("=" * 104)
print("CANDIDATE EXPLANATIONS - HYPOTHESES ONLY, NOT TESTED IN THIS PHASE")
print("=" * 104)
print("""  The observations above are consistent with several mutually
  incompatible explanations. None has been established here:

  H1  The strategy may be directionally dependent, i.e. its edge (if any)
      may exist only in one trend direction. Observed: long P&L differed
      sharply between the two years while short P&L did not.
      NOT TESTED - distinguishing this needs more than two years.

  H2  Cost drag may bind differently across regimes. Observed: 2024 gross
      P&L was much closer to breakeven than 2025 gross P&L, while costs
      were nearly identical (51.89 vs 51.33). The gross difference, not the
      cost difference, accounts for most of the gap.
      NOT TESTED - no maker/taker or volume-tier analysis was performed.

  H3  The 20-bar support/resistance window may behave differently at
      different volatility levels. Observed: bar range and trend-gap
      statistics differ between the years. A window that is tight in a
      calm regime and wide in a volatile regime would change how often
      levels are broken and how far price travels after a break.
      NOT TESTED - would require a volatility-conditioned study.

  H4  The difference may be ordinary sampling noise. With roughly 170
      trades per year and a baseline profit factor below 1.0, a swing of
      this size is within the range that two samples can produce by
      chance.
      NOT TESTED - no significance test or bootstrap was performed.

  Note explicitly: none of H1-H4 is a cause. A correlation between a
  measured market statistic and a P&L difference does not establish that
  the statistic produced the difference.""")

print()
print("=" * 104)
print("CONCLUSION FOR SECTION 6")
print("=" * 104)
print("""  Descriptive analysis is complete and recorded above. No filter,
  threshold, or configuration was created or tuned from these findings, in
  line with the Phase 8 restriction. The single clearest measured fact is
  that the strategy's gross (pre-cost) P&L differed between the two years
  (-15.63 in 2024 vs -40.63 in 2025) while costs were almost identical,
  which points at signal quality rather than cost assumptions as the
  difference. Establishing why remains open.""")
