"""Phase 7: comparison table, year-agreement analysis, and conclusion data."""
import json

with open("experiments/phase7/RESULTS_data.json", encoding="utf-8") as fh:
    rows = json.load(fh)

base = {r["name"]: r for r in rows}["P0_baseline"]

print("=" * 118)
print("PHASE 7 COMPARISON TABLE  (baseline = P0, all values net of fee 0.001 + slippage 0.0005)")
print("2024 / 2025 are EXPLORATORY and IN-SAMPLE (both studied in Phases 2-6)")
print("=" * 118)
hdr = (f"{'experiment':24s} {'group':6s} {'n':>5s} {'d_n':>6s} {'net_pnl':>9s} "
       f"{'ret%':>7s} {'wr%':>6s} {'pf':>6s} {'mdd%':>6s} {'end_bal':>9s} {'trades_kept':>12s}")
print(hdr)
print("-" * 118)
for r in rows:
    s = r["splits"]["full"]
    b = base["splits"]["full"]
    kept = f"{s['trades'] / b['trades'] * 100:.0f}%"
    print(f"{r['name']:24s} {r['group']:6s} {s['trades']:5d} "
          f"{s['trades'] - b['trades']:+6d} {s['net_pnl']:9.2f} {s['return_pct']:7.2f} "
          f"{s['win_rate']:6.2f} {s['profit_factor']:6.3f} {s['max_drawdown']:6.2f} "
          f"{s['ending_balance']:9.2f} {kept:>12s}")

print()
print("=" * 118)
print("YEAR-BY-YEAR (exploratory, in-sample)")
print("=" * 118)
print(f"{'experiment':24s} {'2024 net':>10s} {'d24':>9s} {'2025 net':>10s} {'d25':>9s} "
      f"{'both_better':>12s} {'verdict':>34s}")
print("-" * 118)


def verdict_for(r):
    d24 = r["splits"]["2024"]["net_pnl"] - base["splits"]["2024"]["net_pnl"]
    d25 = r["splits"]["2025"]["net_pnl"] - base["splits"]["2025"]["net_pnl"]
    pos24 = r["splits"]["2024"]["net_pnl"] > 0
    pos25 = r["splits"]["2025"]["net_pnl"] > 0
    both_better = d24 > 0 and d25 > 0
    if pos24 and pos25:
        v = "positive BOTH years"
    elif pos24 and not pos25:
        v = "2024 only positive"
    elif pos25 and not pos24:
        v = "2025 only positive"
    else:
        v = "negative both years"
    if not both_better:
        v += " (worse in >=1 yr vs base)"
    return d24, d25, both_better, v


for r in rows[1:]:
    d24, d25, both, v = verdict_for(r)
    print(f"{r['name']:24s} {r['splits']['2024']['net_pnl']:10.2f} {d24:+9.2f} "
          f"{r['splits']['2025']['net_pnl']:10.2f} {d25:+9.2f} "
          f"{('YES' if both else 'no'):>12s} {v:>34s}")

print()
print("=" * 118)
print("GROSS vs COST DECOMPOSITION (full period) - is an improvement real or just fewer trades?")
print("=" * 118)
print(f"{'experiment':24s} {'n':>5s} {'gross_pnl':>10s} {'costs':>8s} {'net_pnl':>9s} "
      f"{'cost_per_trade':>15s}")
print("-" * 118)
for r in rows:
    s = r["splits"]["full"]
    cpt = s["total_costs"] / s["trades"] if s["trades"] else 0
    print(f"{r['name']:24s} {s['trades']:5d} {s['gross_pnl']:10.2f} "
          f"{s['total_costs']:8.2f} {s['net_pnl']:9.2f} {cpt:15.4f}")

print()
print("=" * 118)
print("SIGNAL CLASS SHIFTS (full period) - did a filter change WHAT trades are taken?")
print("=" * 118)
print(f"{'experiment':24s} {'lb n':>5s} {'lb net':>8s} {'sb n':>5s} {'sb net':>8s} "
       f"{'lr n':>5s} {'lr net':>8s} {'sr n':>5s} {'sr net':>8s}")
print("-" * 118)
for r in rows:
    s = r["splits"]["full"]
    print(f"{r['name']:24s} {s['n_lb']:5d} {s['lb_net']:8.2f} {s['n_sb']:5d} "
          f"{s['sb_net']:8.2f} {s['n_lr']:5d} {s['lr_net']:8.2f} {s['n_sr']:5d} "
          f"{s['sr_net']:8.2f}")

print()
print("=" * 118)
print("SPREAD OF YEARLY OUTCOMES ACROSS ALL CONFIGURATIONS")
print("=" * 118)
n24 = [r["splits"]["2024"]["net_pnl"] for r in rows]
n25 = [r["splits"]["2025"]["net_pnl"] for r in rows]
print(f"  2024 net range across {len(rows)} configs : {min(n24):8.2f} .. {max(n24):8.2f}"
      f"   spread {max(n24) - min(n24):8.2f}")
print(f"  2025 net range across {len(rows)} configs : {min(n25):8.2f} .. {max(n25):8.2f}"
      f"   spread {max(n25) - min(n25):8.2f}")
print(f"  every config negative in 2025?           : {all(x < 0 for x in n25)}")
print(f"  configs positive in 2024                 : {sum(1 for x in n24 if x > 0)}/{len(n24)}")
print(f"  configs positive in 2025                 : {sum(1 for x in n25 if x > 0)}/{len(n25)}")
print(f"  configs positive in BOTH years           : "
      f"{sum(1 for a, b in zip(n24, n25) if a > 0 and b > 0)}/{len(rows)}")
print(f"  configs with full-period net > 0         : "
      f"{sum(1 for r in rows if r['splits']['full']['net_pnl'] > 0)}/{len(rows)}")
