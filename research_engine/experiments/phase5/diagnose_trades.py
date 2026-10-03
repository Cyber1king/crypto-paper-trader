"""Phase 5 step 2: trade-level diagnostics (mirrors backtest.run_backtest exactly)."""
import time
from collections import defaultdict
from dataclasses import replace

from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.strategy import StrategyConfig, analyze
from crypto_paper_lab.simulator import PaperBroker

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"
CONFIG = StrategyConfig()

candles = load_ohlcv_csv(DATASET)
validate_dataset(candles)

minimum_history = max(CONFIG.lookback + 2, CONFIG.slow_period)


def build_row(trade, meta, exit_kind, entry_i, exit_i):
    trend, support, resistance, sig_price, _ = meta
    if trade.side == "long":
        dist = (sig_price - resistance) / resistance
    else:
        dist = (support - sig_price) / support
    window = candles[entry_i + 1: exit_i + 1] or [candles[entry_i]]
    if trade.side == "long":
        mae = (min(c.low for c in window) - trade.entry_price) * trade.quantity
        mfe = (max(c.high for c in window) - trade.entry_price) * trade.quantity
    else:
        mae = (trade.entry_price - max(c.high for c in window)) * trade.quantity
        mfe = (trade.entry_price - min(c.low for c in window)) * trade.quantity
    reason = trade.reason
    if "retest" in reason:
        kind = "retest"
    elif "breakdown" in reason:
        kind = "breakdown"
    else:
        kind = "breakout"
    return {
        "side": trade.side,
        "reason": trade.reason,
        "cls": f"{trade.side}_{kind}",
        "trend": trend,
        "entry_time": trade.entry_time,
        "bars": exit_i - entry_i,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "qty": trade.quantity,
        "costs": trade.costs,
          # "costs" above is the amount deducted from gross, which keeps the
          # per-trade identity gross - costs == net. Under the default
          # cost_deduction model it is also the total friction; under
          # fill_price it is fees only, so total_friction is reported
          # separately rather than overwriting the reconciled figure.
          "total_friction": trade.total_friction,
        "gross": trade.pnl,
        "net": trade.net_pnl,
        "dist": dist,
        "mae": mae,
        "mfe": mfe,
        "exit_kind": exit_kind,
        "notional": trade.entry_price * trade.quantity,
    }


broker = PaperBroker(10_000)
rows = []
open_meta = None

t0 = time.time()
for index in range(minimum_history, len(candles)):
    current = candles[index]
    signal = analyze(candles[:index], CONFIG)
    exec_signal = replace(signal, timestamp=current.timestamp, price=current.open)

    if broker.open_trade is not None:
        if signal.side in {"long", "short"} and signal.side != broker.open_trade.side:
            trade = broker.close(current.open, current.timestamp)
            rows.append(build_row(trade, open_meta, "reversal", open_meta[4], index))
            open_meta = None

    if broker.open_trade is None and signal.side in {"long", "short"}:
        broker.open_from_signal(exec_signal, risk_fraction=0.01)
        open_meta = (signal.trend, signal.support, signal.resistance, signal.price, index)
elapsed = time.time() - t0

if broker.open_trade is not None:
    last_i = len(candles) - 1
    trade = broker.close(candles[-1].close, candles[-1].timestamp)
    rows.append(build_row(trade, open_meta, "end_of_data", open_meta[4], last_i))
    open_meta = None


def stats(rs, label):
    if not rs:
        print(f"  {label:26s} n=0")
        return
    n = len(rs)
    nets = [r["net"] for r in rs]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp, gl = sum(wins), abs(sum(losses))
    wr = len(wins) / n
    pf = gp / gl if gl else float("inf")
    avg = sum(nets) / n
    med = sorted(nets)[n // 2]
    b = peak = 10_000.0
    mdd = 0.0
    for x in nets:
        b += x
        peak = max(peak, b)
        mdd = max(mdd, (peak - b) / peak)
    print(f"  {label:26s} n={n:4d} net={sum(nets):9.2f} wr={wr:7.2%} pf={pf:6.3f} "
          f"avg={avg:7.2f} med={med:7.2f} mdd={mdd:6.2%}")


print(f"replay elapsed {elapsed:.1f}s   trades={len(rows)}")
print()
print("=== 1. BASELINE BY CLASS (net = after fees+slippage) ===")
by_cls = defaultdict(list)
for r in rows:
    by_cls[r["cls"]].append(r)
tot = 0.0
for k in ("long_breakout", "long_retest", "short_breakdown", "short_retest"):
    stats(by_cls[k], k)
    tot += sum(r["net"] for r in by_cls[k])
print(f"  {'sum of classes':26s}          net={tot:9.2f}")

print()
print("=== 2. HOLDING PERIOD (bars) ===")
for lo, hi in ((0, 1), (1, 3), (3, 6), (6, 12), (12, 24), (24, 10 ** 6)):
    stats([r for r in rows if lo <= r["bars"] < hi], f"all {lo}-{hi if hi < 10 ** 6 else 'inf'}")
print("  -- short only --")
shorts = [r for r in rows if r["side"] == "short"]
for lo, hi in ((0, 1), (1, 3), (3, 6), (6, 12), (12, 24), (24, 10 ** 6)):
    stats([r for r in shorts if lo <= r["bars"] < hi], f"short {lo}-{hi if hi < 10 ** 6 else 'inf'}")

print()
print("=== 3. TREND AT ENTRY ===")
for t in ("up", "down", "sideways"):
    stats([r for r in rows if r["trend"] == t], f"all/{t}")
for t in ("up", "down", "sideways"):
    stats([r for r in shorts if r["trend"] == t], f"short/{t}")

print()
print("=== 4. EXIT REASON ===")
for k in ("reversal", "end_of_data"):
    stats([r for r in rows if r["exit_kind"] == k], k)
    stats([r for r in shorts if r["exit_kind"] == k], f"short/{k}")

print()
print("=== 5. BREAKOUT DISTANCE QUINTILES (all breakouts) ===")
bk = sorted([r for r in rows if r["cls"].endswith("breakout")], key=lambda r: r["dist"])
n = len(bk)
for d in range(5):
    grp = bk[d * n // 5:(d + 1) * n // 5]
    stats(grp, f"q{d + 1} [{grp[0]['dist']:.4f},{grp[-1]['dist']:.4f}]")

print()
print("=== 6. SHORT BREAKOUT: dist quartiles ===")
sb = sorted(by_cls["short_breakdown"], key=lambda r: r["dist"])
n = len(sb)
for d in range(4):
    grp = sb[d * n // 4:(d + 1) * n // 4]
    stats(grp, f"q{d + 1} [{grp[0]['dist']:.4f},{grp[-1]['dist']:.4f}]")

print()
print("=== 7. MAE / MFE + notional (diagnostic; MAE/MFE use post-entry bars) ===")
for k in ("long_breakout", "long_retest", "short_breakdown", "short_retest"):
    g = by_cls[k]
    m = len(g)
    print(f"  {k:16s} MAE={sum(r['mae'] for r in g) / m:7.2f} "
          f"MFE={sum(r['mfe'] for r in g) / m:7.2f} "
          f"net={sum(r['net'] for r in g) / m:7.2f} "
          f"notional={sum(r['notional'] for r in g) / m:9.2f} "
          f"costs={sum(r['costs'] for r in g) / m:6.3f} "
          f"costs%={sum(r['costs'] for r in g) / sum(r['notional'] for r in g):.4%}")

print()
print("=== 8. LOSS CONCENTRATION (shorts) ===")
snets = sorted((r["net"] for r in shorts))
acc = 0.0
for frac in (0.05, 0.10, 0.20, 0.50):
    k = max(1, int(len(snets) * frac))
    acc = sum(snets[:k])
    print(f"  worst {frac:5.0%} of short trades ({k:3d}) contribute {acc:9.2f} "
          f"({acc / sum(snets):6.1%} of total short loss)")
