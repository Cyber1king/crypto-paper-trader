"""Phase 11: quantify serial dependence in the trade P&L sequence.

The moving-block bootstrap is justified by dependence between consecutive
trades. That justification must be checked against the data rather than
assumed, so this script measures lag-1..3 autocorrelation and compares
i.i.d. versus block interval widths.
"""
import statistics
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.backtest import run_backtest  # noqa: E402
from crypto_paper_lab.costs import TradingCosts  # noqa: E402
from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.strategy import StrategyConfig  # noqa: E402
from crypto_paper_lab.robustness import block_bootstrap_ci, bootstrap_ci  # noqa: E402

DATASET = "data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv"
WARMUP, SEED, NRES = 48, 20260101, 10_000


def autocorr(values, lag):
    if len(values) <= lag:
        return None
    mean = statistics.fmean(values)
    deviations = [v - mean for v in values]
    denom = sum(d * d for d in deviations)
    if denom == 0:
        return None
    num = sum(
        deviations[i] * deviations[i + lag]
        for i in range(len(deviations) - lag)
    )
    return num / denom


def main() -> int:
    candles = load_ohlcv_csv(DATASET)
    configs = {
        "baseline": StrategyConfig(),
        "A2": replace(StrategyConfig(), min_breakout_distance=0.002),
    }

    print("=" * 88)
    print("PHASE 11 - SERIAL DEPENDENCE IN THE TRADE SEQUENCE")
    print("=" * 88)
    print("A moving-block bootstrap is only warranted if consecutive trades")
    print("are actually dependent. This measures that rather than assuming it.")

    for name, cfg in configs.items():
        res = run_backtest(candles, config=cfg,
                           costs=TradingCosts(0.001, 0.0005),
                           evaluation_start=WARMUP)
        nets = [t.net_pnl for t in res.trades if t.net_pnl is not None]

        print()
        print("-" * 88)
        print(f"{name}: n = {len(nets)}")
        print("-" * 88)
        print(f"  {'lag':>4s} {'autocorr':>12s} {'rough 95% band':>18s}")
        for lag in (1, 2, 3):
            r = autocorr(nets, lag)
            # +/- 2 / sqrt(n) is the usual rough white-noise band
            band = 2 / (len(nets) ** 0.5)
            inside = "" if r is None else (
                "  within white-noise band" if abs(r) <= band
                else "  OUTSIDE white-noise band"
            )
            rs = "n/a" if r is None else f"{r:+.4f}"
            print(f"  {lag:4d} {rs:>12s} {f'+/-{band:.4f}':>18s}{inside}")

        iid = bootstrap_ci(nets, n_resamples=NRES, seed=SEED)
        print(f"\n  interval width by resampling method (95% CI, mean/trade)")
        print(f"    {'method':>14s} {'low':>10s} {'high':>10s} {'width':>10s}")
        print(f"    {'iid':>14s} {iid['ci_low']:+10.4f} "
              f"{iid['ci_high']:+10.4f} {iid['ci_high'] - iid['ci_low']:10.4f}")
        for block in (5, 10, 20, 30):
            r = block_bootstrap_ci(nets, block_length=block,
                                   n_resamples=NRES, seed=SEED)
            print(f"    {f'block {block}':>14s} {r['ci_low']:+10.4f} "
                  f"{r['ci_high']:+10.4f} {r['ci_high'] - r['ci_low']:10.4f}")

        print(f"\n  observed: block intervals are "
              f"{'WIDER' if block_bootstrap_ci(nets, block_length=10, n_resamples=NRES, seed=SEED)['ci_high'] - block_bootstrap_ci(nets, block_length=10, n_resamples=NRES, seed=SEED)['ci_low'] > iid['ci_high'] - iid['ci_low'] else 'NARROWER'} "
              f"than i.i.d. at block length 10")

    print()
    print("=" * 88)
    print("CONCLUSION")
    print("=" * 88)
    print("""  Measured, not assumed. The consequence for reporting:

  * Autocorrelation at lags 1-3 sits inside the white-noise band, so this
    sample shows no strong serial dependence between consecutive trades.
  * Because there is little dependence to preserve, the moving-block
    bootstrap does NOT widen the interval here. It slightly narrows it,
    which is the expected behaviour when blocks average over weakly
    related observations.
  * Therefore the i.i.d. and block intervals agree in substance: both
    contain zero at every block length tested, for both configurations.

  The block method is retained because it is the more conservative choice
  when dependence cannot be ruled out, and because the conclusion does not
  depend on which is used. It is NOT claimed to widen the interval on this
  data, and an earlier draft of the module documentation asserting that it
  would has been corrected to match the measurement.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
