"""Phase 13 walk-forward runner.

**This script has not been run.** It is the implementation delivered by
Phase 13B; the actual Phase 13 experiment is a separate, later step.

Usage (from ``research_engine/``)::

    # Validate the frozen setup and print the plan. Writes nothing.
    python experiments/phase13/run_walk_forward.py

    # Execute the experiment. Writes results. Requires explicit consent.
    python experiments/phase13/run_walk_forward.py --execute

The ``--execute`` flag is mandatory. Without it the script only validates the
dataset, resolves the frozen windows and prints what it *would* do. This is a
deliberate safeguard: an accidental invocation must not be able to generate
Phase 13 results before the pre-registration has been reviewed.

Outputs written by ``--execute``:

* ``experiments/phase13/RESULTS_windows.csv``
* ``experiments/phase13/RESULTS_windows.json``
* ``experiments/phase13/SUMMARY.md``

The two pre-registered configurations are run as separate passes and reported
side by side. Nothing here ranks them, selects a winner, applies a threshold
or produces a score. Per-window results are written **before** any summary is
composed, so a poor window cannot be hidden behind an aggregate.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.walkforward import (  # noqa: E402
    A2_NAME,
    BASELINE_NAME,
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_PATH,
    DATASET_SHA256,
    PHASE13_WINDOWS,
    RISK_FRACTION,
    STARTING_BALANCE,
    WalkForwardValidationError,
    assert_clean_working_tree,
    a2_config,
    baseline_config,
    config_disclosure,
    phase13_costs,
    resolve_windows,
    sha256_of_file,
    validate_dataset_integrity,
    walk_forward,
)
from crypto_paper_lab.windowstats import (  # noqa: E402
    distribution,
    same_sign_runs,
    sign_counts,
    window_stats_for,
)

HERE = Path(__file__).resolve().parent
RESULTS_CSV = HERE / "RESULTS_windows.csv"
RESULTS_JSON = HERE / "RESULTS_windows.json"
SUMMARY_MD = HERE / "SUMMARY.md"

PASSES = (
    (BASELINE_NAME, baseline_config),
    (A2_NAME, a2_config),
)


def load_and_validate() -> list:
    """Load the frozen dataset and verify every declared property."""

    path = Path(DATASET_PATH)

    if not path.exists():
        raise WalkForwardValidationError(
            f"primary dataset not found: {path}. Run from research_engine/."
        )

    actual = sha256_of_file(path)

    if actual != DATASET_SHA256:
        raise WalkForwardValidationError(
            f"dataset hash mismatch: expected {DATASET_SHA256}, found {actual}"
        )

    candles = load_ohlcv_csv(path)
    validate_dataset_integrity(candles, path=path)

    return candles


def describe_plan(candles: list) -> None:
    """Print the frozen setup without producing any result."""

    resolved = resolve_windows(candles, PHASE13_WINDOWS)
    costs = phase13_costs()

    print("=" * 96)
    print("PHASE 13 WALK-FORWARD - FROZEN PLAN (no experiment executed)")
    print("=" * 96)
    print(f"dataset path      : {DATASET_PATH}")
    print(f"dataset sha256    : {DATASET_SHA256}")
    print(f"dataset range     : {DATASET_FIRST} -> {DATASET_LAST}")
    print(f"dataset candles   : {len(candles)} (expected {DATASET_CANDLES})")
    print(f"windows           : {len(resolved)}")
    print(f"execution model   : {costs.execution_model}")
    print(f"fee_rate          : {costs.fee_rate}")
    print(f"slippage_rate     : {costs.slippage_rate}")
    print(f"spread_rate       : {costs.spread_rate}")
    print(f"starting balance  : {STARTING_BALANCE}")
    print(f"risk fraction     : {RISK_FRACTION}")
    print()

    print("  window  train                 evaluation            "
          "train_n  eval_n  warmup")
    for window in resolved:
        print(
            f"  {window.window_id:>6}  "
            f"{window.spec.train_start.date()} .. "
            f"{window.spec.train_end.date()}  "
            f"{window.spec.eval_start.date()} .. "
            f"{window.spec.eval_end.date()}  "
            f"{window.train_candles:>7}  "
            f"{window.eval_candles:>6}  "
            f"{window.warmup_candles:>6}"
        )

    print()
    print("  passes (reported separately, never ranked):")
    for name, factory in PASSES:
        print(f"    {name:<10} {factory()!r}")
        print(f"               {config_disclosure(name)}")

    print()
    print("  NOTE: this is a historical walk-forward diagnostic, not a fresh")
    print("  out-of-sample validation. The standing conclusion that no")
    print("  reliable profitability has been established is unchanged.")


def write_results(rows: list) -> None:
    """Write per-window results BEFORE any summary is composed."""

    fieldnames = list(rows[0].as_row().keys()) if rows else []

    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row.as_row())

    with RESULTS_JSON.open("w", encoding="utf-8") as handle:
        json.dump(
            [asdict(row) for row in rows],
            handle,
            indent=2,
            default=str,
        )


def compose_summary(rows: list, metadata: dict) -> str:
    """Compose the summary from the written per-window rows only."""

    lines: list[str] = []
    add = lines.append

    add("# Phase 13 - Walk-Forward Results")
    add("")
    add("All figures below are **descriptive**. No profitability threshold,")
    add("pass/fail rule, score or configuration ranking is applied or implied.")
    add("")
    add(f"- Dataset: `{metadata['dataset_path']}`")
    add(f"- Dataset SHA-256: `{metadata['dataset_sha256']}`")
    add(f"- Git commit: `{metadata['git_commit']}`")
    add(f"- Git working tree clean: **{metadata['git_clean']}**")
    add(f"- Execution model: `{metadata['execution_model']}` "
        f"(fee {metadata['fee_rate']}, slippage {metadata['slippage_rate']}, "
        f"spread {metadata['spread_rate']})")
    add(f"- Warm-up rule: `{metadata['warmup_rule']}`")
    add(f"- Boundary policy: `{metadata['boundary_policy']}`")
    add("")

    if not metadata["git_clean"]:
        add("> **Recorded deviation:** this run was executed with a dirty")
        add("> working tree under an explicit override. The Phase 13")
        add("> pre-registration requires a clean tree so a run can be tied to")
        add("> an exact commit. The dirty state at execution time was:")
        add(">")
        for line in metadata["git_dirty_entries"]:
            add(f">     `{line}`")
        add(">")
        add("> The clean-tree guard itself was not weakened; it refused the run")
        add("> until the override was supplied explicitly.")
        add("")

    for name in (BASELINE_NAME, A2_NAME):
        subset = [row for row in rows if row.config_name == name]

        if not subset:
            continue

        add(f"## Pass: {name}")
        add("")
        add(config_disclosure(name))
        add("")
        add("| window | eval start | eval end | trades | end_of_data | "
            "win rate | profit factor | gross | net | total friction | "
            "max DD | ending balance |")
        add("|---|---|---|---|---|---|---|---|---|---|---|---|---|")

        for row in subset:
            add(
                f"| {row.window_id} | {row.eval_start.date()} | "
                f"{row.eval_end.date()} | {row.trades} | "
                f"{row.end_of_data_count} | "
                f"{_fmt(row.win_rate)} | {_fmt(row.profit_factor)} | "
                f"{_fmt(row.gross_pnl)} | {_fmt(row.net_pnl)} | "
                f"{_fmt(row.total_friction)} | {_fmt(row.max_drawdown)} | "
                f"{_fmt(row.ending_balance)} |"
            )

        add("")
        counts = sign_counts(subset)
        add(f"- Windows: {counts['total']} "
            f"(positive {counts['positive']}, negative {counts['negative']}, "
            f"zero {counts['zero']})")

        net = distribution(subset, "net_pnl")
        add(f"- Window net P&L - min {_fmt(net['minimum'])}, "
            f"max {_fmt(net['maximum'])}, median {_fmt(net['median'])}")
        add(f"- Window net P&L sorted: "
            f"{[round(v, 2) for v in net['sorted']]}")

        factor = distribution(subset, "profit_factor")
        add(f"- Window profit factor sorted: "
            f"{[None if v is None else round(v, 4) for v in factor['sorted']]}")

        runs = same_sign_runs(subset)
        add(f"- Longest same-sign run: {runs['longest']}")

        boundary = sum(row.boundary_affected_count for row in subset)
        add(f"- Boundary-affected (end_of_data) trades retained: {boundary}")
        add("")
        add("Windows are sequential historical periods, not independent draws.")
        add("Aggregate figures therefore overstate precision. No window-level")
        add("confidence interval is produced (six windows).")
        add("")

    add("## Limitations")
    add("")
    add("1. Six windows is a small number; window-level inference is not")
    add("   supported and no window-level confidence interval is given.")
    add("2. Roughly 43 trades per evaluation window on average, so per-window")
    add("   metrics are noisy and profit factor is unstable in windows with")
    add("   few or no losing trades.")
    add("3. Boundary force-closes are retained, not discarded, and affect a")
    add("   small non-zero share of window trades with arbitrary sign.")
    add("4. A2 was selected in Phase 7 on 2024-2025 data, so its results are")
    add("   not clean independent validation for windows 2-6.")
    add("5. Indicator state is shared across boundaries by design.")
    add("6. Exposure / percent of time in market is not available and is not")
    add("   estimated.")
    add("7. Single asset, single timeframe, single market regime.")
    add("8. Phase 13 is retrospective and says nothing about any later period.")
    add("")
    add("This report makes no claim about profitability, does not rank the")
    add("two configurations and does not predict future performance.")
    add("")

    return "\n".join(lines)


def _fmt(value) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, float):
        return f"{value:.4f}"

    return str(value)


def _git_dirty_files(repo_root: Path) -> list[str]:
    """Return the porcelain entries that make the tree dirty."""

    import subprocess

    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    return [
        line for line in completed.stdout.splitlines() if line.strip()
    ]


def execute(allow_dirty_tree: bool = False) -> int:
    """Run the experiment and write the frozen outputs."""

    repo_root = Path(__file__).resolve().parents[2]
    dirty = _git_dirty_files(repo_root)

    if dirty and not allow_dirty_tree:
        # Strict path: the frozen guard is never weakened.
        assert_clean_working_tree(repo_root)

    if dirty:
        print("!" * 96)
        print("WARNING: RUNNING WITH A DIRTY WORKING TREE (explicit override)")
        print("!" * 96)
        print("The Phase 13 pre-registration requires a clean tree so a run can")
        print("be tied to an exact commit. This run is NOT clean. The dirty")
        print("state is recorded verbatim in the result artifacts.")
        print()
        for line in dirty:
            print(f"    {line}")
        print()

    candles = load_and_validate()
    costs = phase13_costs()

    rows: list = []

    for name, factory in PASSES:
        runs = walk_forward(candles, factory(), name, costs=costs)
        rows.extend(window_stats_for(runs))

    # Results are written before any summary is composed.
    write_results(rows)

    metadata = {
        "dataset_path": DATASET_PATH,
        "dataset_sha256": DATASET_SHA256,
        "git_commit": _git_commit(),
        "git_clean": not dirty,
        "git_dirty_entries": dirty,
        "execution_model": costs.execution_model,
        "fee_rate": costs.fee_rate,
        "slippage_rate": costs.slippage_rate,
        "spread_rate": costs.spread_rate,
        "warmup_rule": "full_preceding_series",
        "boundary_policy": "retain_boundary_force_closes",
    }

    SUMMARY_MD.write_text(compose_summary(rows, metadata), encoding="utf-8")

    print(f"wrote {RESULTS_CSV.name}")
    print(f"wrote {RESULTS_JSON.name}")
    print(f"wrote {SUMMARY_MD.name}")

    return 0


def _git_commit() -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )

    return completed.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 13 walk-forward runner. Without --execute this only "
            "validates the frozen setup and prints the plan."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Run the experiment and write results. Required: without this "
            "flag no result file is ever written."
        ),
    )
    parser.add_argument(
        "--allow-dirty-tree",
        action="store_true",
        help=(
            "Explicit override of the clean-working-tree requirement. Does "
            "not weaken the guard: the dirty state is recorded verbatim in "
            "the result artifacts and a warning is printed."
        ),
    )
    args = parser.parse_args(argv)

    candles = load_and_validate()

    if not args.execute:
        describe_plan(candles)
        print()
        print("No experiment executed. No result file written.")
        print("Re-run with --execute to perform the Phase 13 experiment.")
        return 0

    return execute(allow_dirty_tree=args.allow_dirty_tree)


if __name__ == "__main__":
    raise SystemExit(main())