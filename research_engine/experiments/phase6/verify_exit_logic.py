"""Phase 6 Task 1-2: verify exit logic and the holding-period finding.

Uses the exit_reason / bars_held fields recorded by run_backtest, so the
figures come straight from the trade journal rather than a re-implementation.
"""
from collections import defaultdict

from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.strategy import StrategyConfig

DATASET = "data/BTCUSDT_1h_Cleaned (1).csv"

candles = load_ohlcv_csv(DATASET)
validate_dataset(candles)

result = run_backtest(candles)
trades = list(result.trades)

print("=== BASELINE TRADE JOURNAL ===")
print(f"trades            : {len(trades)}")
print(f"ending_balance    : {result.ending_balance:.2f}")
print(f"net_pnl           : {result.ending_balance - result.starting_balance:.2f}")
print(f"exit_counts       : {result.exit_counts}")
print(f"sum bars_held     : {sum(t.bars_held for t in trades)}")
print(f"max bars_held     : {max(t.bars_held for t in trades)}")
print(f"min bars_held     : {min(t.bars_held for t in trades)}")
print(f"trades with bars_held == 0 : {sum(1 for t in trades if t.bars_held == 0)}")


def block(rs, label):
    if not rs:
        print(f"  {label:22s} n=   0")
        return
    nets = [t.net_pnl for t in rs if t.net_pnl is not None]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp, gl = sum(wins), abs(sum(losses))
    bal = peak = 10_000.0
    mdd = 0.0
    for x in nets:
        bal += x
        peak = max(peak, bal)
        mdd = max(mdd, (peak - bal) / peak)
    print(f"  {label:22s} n={len(rs):4d} net={sum(nets):9.2f} "
          f"wr={len(wins) / len(rs):7.2%} "
          f"pf={gp / gl if gl else float('inf'):6.3f} "
          f"avg={sum(nets) / len(rs):7.2f} mdd={mdd:6.2%}")


GROUPS = [(0, 1), (1, 3), (3, 6), (6, 12), (12, 24), (24, 10 ** 6)]

print()
print("=== TASK 2: HOLDING-PERIOD GROUPS (all trades) ===")
print(f"  {'group':22s} {'n':>5s} {'net':>10s} {'wr':>8s} {'pf':>7s} {'avg':>8s} {'mdd':>7s}")
for lo, hi in GROUPS:
    label = f"bars {lo}-{hi if hi < 10 ** 6 else 'inf'}"
    block([t for t in trades if lo <= t.bars_held < hi], label)

print()
print("=== TASK 2: HOLDING-PERIOD GROUPS (long only) ===")
for lo, hi in GROUPS:
    label = f"long {lo}-{hi if hi < 10 ** 6 else 'inf'}"
    block([t for t in trades if t.side == "long" and lo <= t.bars_held < hi], label)

print()
print("=== TASK 2: HOLDING-PERIOD GROUPS (short only) ===")
for lo, hi in GROUPS:
    label = f"short {lo}-{hi if hi < 10 ** 6 else 'inf'}"
    block([t for t in trades if t.side == "short" and lo <= t.bars_held < hi], label)

print()
print("=== EXACT 24-BAR BOUNDARY (tests the '0% win rate' claim) ===")
under = [t for t in trades if t.bars_held < 24]
at24 = [t for t in trades if t.bars_held == 24]
over = [t for t in trades if t.bars_held > 24]
block(under, "bars_held < 24")
block(at24, "bars_held == 24")
block(over, "bars_held > 24")

print()
print("=== BARS_HELD DISTRIBUTION (fine) ===")
hist = defaultdict(int)
for t in trades:
    hist[min(t.bars_held, 60)] += 1
for b in sorted(hist):
    if b <= 30 or b == 60:
        print(f"  bars_held={b:3d}: {hist[b]:4d}")
print(f"  bars_held>60   : {sum(v for k, v in hist.items() if k == 60):4d}")

print()
print("=== EXIT REASON BREAKDOWN ===")
by_reason = defaultdict(list)
for t in trades:
    by_reason[t.exit_reason].append(t)
for reason, rs in sorted(by_reason.items()):
    block(rs, reason)

print()
print("=== SIDE x EXIT-REASON ===")
for side in ("long", "short"):
    for reason, rs in sorted(by_reason.items()):
        block([t for t in rs if t.side == side], f"{side}/{reason}")
