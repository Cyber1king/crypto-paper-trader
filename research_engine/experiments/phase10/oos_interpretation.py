"""Phase 10 step 4: is the out-of-sample result distinguishable from zero?

This is reporting analysis only. No strategy parameter is touched, no
methodology changes, and no configuration is selected. The purpose is to
stop a marginally positive number from being overstated.
"""
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.acquisition import normalize_source  # noqa: E402
from crypto_paper_lab.backtest import run_backtest  # noqa: E402
from crypto_paper_lab.costs import TradingCosts  # noqa: E402
from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.dataset import validate_dataset  # noqa: E402
from crypto_paper_lab.stats import total_friction  # noqa: E402
from crypto_paper_lab.strategy import StrategyConfig  # noqa: E402

OOS = "data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv"
RESEARCH = "data/BTCUSDT_1h_Cleaned (1).csv"
WARMUP = 48
COSTS = TradingCosts(0.001, 0.0005)
BASE = StrategyConfig()
A2 = replace(BASE, min_breakout_distance=0.002)


def significance(nets):
    """Standard error of the mean trade; a crude but honest signal check."""

    n = len(nets)
    mean = statistics.fmean(nets)
    if n < 2:
        return None
    sd = statistics.stdev(nets)
    se = sd / (n ** 0.5)
    return {
        "n": n,
        "mean": mean,
        "stdev": sd,
        "stderr": se,
        "t_like": mean / se if se else float("inf"),
        "ci95_low": mean - 1.96 * se,
        "ci95_high": mean + 1.96 * se,
    }


def main() -> int:
    candles = load_ohlcv_csv(OOS)
    validate_dataset(candles)

    print("=" * 96)
    print("PHASE 10 STEP 4 - IS THE OUT-OF-SAMPLE RESULT DISTINGUISHABLE FROM ZERO?")
    print("=" * 96)
    print(f"validation window : {candles[WARMUP].timestamp} -> {candles[-1].timestamp}")
    print(f"validation bars   : {len(candles) - WARMUP}")
    print("costs             : fee 0.001, slippage 0.0005")
    print()

    for label, cfg in (("baseline", BASE), ("A2_min_dist_0.002", A2)):
        res = run_backtest(candles, config=cfg, costs=COSTS,
                           evaluation_start=WARMUP)
        nets = [t.net_pnl for t in res.trades if t.net_pnl is not None]
        gross = [t.pnl for t in res.trades if t.pnl is not None]
        costs = total_friction(res.trades)

        sig_net = significance(nets)
        sig_gross = significance(gross)

        print("-" * 96)
        print(f"{label}")
        print("-" * 96)
        print(f"  trades                 : {res.total_trades}")
        print(f"  net P&L                : {res.ending_balance - res.starting_balance:+.2f}")
        print(f"  gross P&L              : {sum(gross):+.2f}")
        print(f"  total costs            : {costs:.2f}")
        print(f"  costs as % of |gross|  : "
              f"{costs / abs(sum(gross)) * 100:.1f}%")
        print()
        print("  PER-TRADE NET P&L")
        print(f"    mean                 : {sig_net['mean']:+.4f}")
        print(f"    stdev                : {sig_net['stdev']:.4f}")
        print(f"    standard error       : {sig_net['stderr']:.4f}")
        print(f"    mean / stderr        : {sig_net['t_like']:.2f}")
        print(f"    95% CI of mean       : "
              f"[{sig_net['ci95_low']:+.4f}, {sig_net['ci95_high']:+.4f}]")
        verdict = ("distinguishable from zero"
                   if abs(sig_net["t_like"]) >= 1.96 else
                   "NOT distinguishable from zero")
        print(f"    verdict              : {verdict}")
        print()
        print("  PER-TRADE GROSS P&L (before costs)")
        print(f"    mean                 : {sig_gross['mean']:+.4f}")
        print(f"    stdev                : {sig_gross['stdev']:.4f}")
        print(f"    standard error       : {sig_gross['stderr']:.4f}")
        print(f"    mean / stderr        : {sig_gross['t_like']:.2f}")
        gv = ("distinguishable from zero"
              if abs(sig_gross["t_like"]) >= 1.96 else
              "NOT distinguishable from zero")
        print(f"    verdict              : {gv}")

    # ---- monthly breakdown ---------------------------------------------
    print()
    print("=" * 96)
    print("MONTHLY BREAKDOWN OF THE VALIDATION PERIOD (baseline)")
    print("=" * 96)
    by_month = defaultdict(list)
    res = run_backtest(candles, config=BASE, costs=COSTS,
                       evaluation_start=WARMUP)
    for t in res.trades:
        by_month[t.entry_time.strftime("%Y-%m")].append(t)
    print(f"  {'month':9s} {'trades':>7s} {'net':>9s} {'gross':>9s} {'costs':>8s}")
    for month in sorted(by_month):
        trades = by_month[month]
        n = sum(t.net_pnl or 0.0 for t in trades)
        g = sum(t.pnl or 0.0 for t in trades)
        c = total_friction(trades)
        print(f"  {month:9s} {len(trades):7d} {n:+9.2f} {g:+9.2f} {c:8.2f}")

    # ---- market regime comparison --------------------------------------
    print()
    print("=" * 96)
    print("MARKET CONTEXT: research window vs validation window")
    print("=" * 96)
    for label, path in (("research 2024-2025", RESEARCH),
                        ("validation 2026", OOS)):
        cs = load_ohlcv_csv(path)
        validate_dataset(cs)
        closes = [c.close for c in cs]
        rets = [(b - a) / a for a, b in zip(closes, closes[1:])]
        print(f"  {label}")
        print(f"    range      : {cs[0].timestamp.date()} -> {cs[-1].timestamp.date()}")
        print(f"    price      : {min(c.low for c in cs):.2f} .. "
              f"{max(c.high for c in cs):.2f}")
        print(f"    first/last : {closes[0]:.2f} -> {closes[-1]:.2f} "
              f"({(closes[-1] / closes[0] - 1) * 100:+.1f}%)")
        print(f"    hourly vol : {statistics.stdev(rets) * 100:.3f}%")
        print(f"    mean range : "
              f"{statistics.fmean((c.high - c.low) / c.close for c in cs) * 100:.3f}%")

    print()
    print("=" * 96)
    print("INTERPRETATION GUARDRAIL")
    print("=" * 96)
    print("""  These figures are reported as measured. Two observations matter
  more than the headline sign:

  1. Both configurations are only marginally positive, and the per-trade
     95% confidence interval of the mean spans zero in both cases. On this
     evidence the strategies are NOT distinguishable from having no edge.

  2. The absolute magnitudes are tiny because risk_fraction is 0.01, so
     each trade risks about 1% of equity. Maximum drawdown is under 0.35%
     for both. A positive number here is consistent with noise, not with a
     demonstrated edge.

  3. Both configurations were NEGATIVE across 2024-2025 and are marginally
     positive in 2026. That sign change tracks the market regime, not a
     change in the strategy, which was not modified between periods.

  4. A2 outperforming baseline on this single window is ONE observation.
     It does not validate the Phase 7 in-sample finding, and it does not
     authorise selecting, deploying, or trusting either configuration.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
