"""Phase 14C descriptive entry-context runner.

Research-only. This script **describes** trades the existing strategy already
produced. It does not optimise, tune, rank or select a configuration, and it
does not modify the strategy in any way.

Usage (from ``research_engine/``)::

    # Validate the frozen setup and print the plan. Writes nothing.
    python experiments/phase14/run_descriptive.py

    # Execute the analysis. Writes results. Requires explicit consent.
    python experiments/phase14/run_descriptive.py --execute

The ``--execute`` flag is mandatory. Without it the script validates the
dataset, resolves the frozen windows and prints what it *would* do, but writes
no result artifact. This follows the Phase 13 runner's precedent: an accidental
invocation must not be able to generate analysis output.

Outputs written by ``--execute``:

* ``experiments/phase14/RESULTS_feature_summary.csv``
* ``experiments/phase14/RESULTS_condition_summary.csv``
* ``experiments/phase14/RESULTS_analysis.json``
* ``experiments/phase14/SUMMARY.md``

The analysis re-runs the frozen Phase 13 walk-forward windows with the frozen
configurations to obtain instrumented trade records. It verifies that the
resulting trade counts and ending balances reproduce the frozen Phase 13
result file before using any of it, so the descriptive claims provably rest on
the same trades Phase 13 recorded.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

sys.path.insert(0, str(REPO_ROOT / "research_engine" / "src"))

from crypto_paper_lab import entrycontext as ec  # noqa: E402
from crypto_paper_lab.data import load_ohlcv_csv  # noqa: E402
from crypto_paper_lab.walkforward import (  # noqa: E402
    A2_NAME,
    BASELINE_NAME,
    BOUNDARY_POLICY,
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_PATH,
    DATASET_SHA256,
    PHASE13_WINDOWS,
    RISK_FRACTION,
    STARTING_BALANCE,
    WARMUP_RULE,
    WalkForwardValidationError,
    a2_config,
    baseline_config,
    phase13_costs,
    resolve_windows,
    sha256_of_file,
    validate_dataset_integrity,
    walk_forward,
)

FEATURE_CSV = HERE / "RESULTS_feature_summary.csv"
CONDITION_CSV = HERE / "RESULTS_condition_summary.csv"
ANALYSIS_JSON = HERE / "RESULTS_analysis.json"
SUMMARY_MD = HERE / "SUMMARY.md"

PHASE13_RESULTS = HERE.parent / "phase13" / "RESULTS_windows.json"

#: Reported separately, never ranked, never pooled.
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


def verify_phase13_equivalence(runs, config_name: str) -> None:
    """Refuse to analyse unless these trades are the frozen Phase 13 trades.

    The analysis needs instrumented trade records, so it re-runs the frozen
    windows. That is only legitimate if the trades are the same trades Phase 13
    recorded, so this asserts the trade count and ending balance against the
    committed result file before any feature or outcome is touched.
    """

    frozen = json.loads(PHASE13_RESULTS.read_text(encoding="utf-8"))

    for run in runs:
        window_id = run.resolved.window_id
        expected = next(
            row
            for row in frozen
            if row["config_name"] == config_name
            and row["window_id"] == window_id
        )
        actual_trades = run.result.total_trades

        if actual_trades != expected["trades"]:
            raise WalkForwardValidationError(
                f"{config_name} window {window_id}: {actual_trades} trades "
                f"does not match the frozen Phase 13 count "
                f"{expected['trades']}; refusing to analyse"
            )

        actual_balance = run.result.ending_balance
        frozen_balance = expected["ending_balance"]

        if abs(actual_balance - frozen_balance) > 1e-9:
            raise WalkForwardValidationError(
                f"{config_name} window {window_id}: ending balance "
                f"{actual_balance!r} does not match the frozen Phase 13 value "
                f"{frozen_balance!r}; refusing to analyse"
            )


def build_analysis(candles: list) -> dict:
    """Run both passes and assemble every descriptive output in memory."""

    costs = phase13_costs()
    feature_rows: list[dict] = []
    condition_rows: list[dict] = []
    associations: list[dict] = []
    robustness: list[dict] = []
    population: list[dict] = []
    equivalence: dict = {}
    records_by_pass: dict = {}

    for name, factory in PASSES:
        runs = walk_forward(candles, factory(), name, costs=costs)
        verify_phase13_equivalence(runs, name)

        records = ec.collect_records(runs, name)
        records_by_pass[name] = records

        # D1 first, from features only. Bins are then declared from those
        # features, still without any outcome. Only then is D2 computed.
        feature_rows.extend(
            {**row, "config_name": name} for row in ec.feature_table(records)
        )

        bins = ec.declare_bins(records)

        condition_rows.extend(ec.condition_table(records, bins, name))
        associations.extend(ec.rank_associations(records))
        robustness.append(ec.robustness_summary(records, name, bins))
        population.append(ec.trade_population(records))

        equivalence[name] = {
            "windows": len(runs),
            "trades": len(records),
            "matches_frozen_phase13": True,
        }

    return {
        "feature_rows": feature_rows,
        "condition_rows": condition_rows,
        "associations": associations,
        "robustness": robustness,
        "population": population,
        "equivalence": equivalence,
        "bins": {
            name: ec.declare_bins(records_by_pass[name])
            for name, _ in PASSES
        },
        "quantiles": list(ec.QUANTILES),
    }


def write_csv(path: Path, rows: list[dict], fields) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def compose_summary(analysis: dict, metadata: dict) -> str:
    """Compose SUMMARY.md from the computed rows only."""

    lines: list[str] = []
    add = lines.append

    add("# Phase 14C - Descriptive Entry-Context Analysis")
    add("")
    add("**Research only.** Nothing below optimises the strategy, changes a")
    add("threshold, ranks a configuration, or claims predictive power. Every")
    add("figure describes trades the existing strategy already produced.")
    add("")

    add("## 1. Scope")
    add("")
    add("Describe the entry-time context of the existing strategy's trades")
    add("using the causal features instrumented in Phase 14B, and state")
    add("plainly what the sample can and cannot support.")
    add("")
    add("Out of scope by construction: strategy optimisation, threshold")
    add("selection, new trading rules, leverage, position-sizing changes,")
    add("MAE/MFE, and any outcome-derived entry feature.")
    add("")

    add("## 2. Data used")
    add("")
    add(f"- Dataset: `{metadata['dataset_path']}`")
    add(f"- Dataset SHA-256: `{metadata['dataset_sha256']}`")
    add(f"- Range: {DATASET_FIRST} -> {DATASET_LAST}")
    add(f"- Candles: {metadata['dataset_candles']} "
        f"(expected {DATASET_CANDLES})")
    add(f"- Windows: {metadata['windows']} frozen Phase 13 evaluation windows")
    add(f"- Execution model: `{metadata['execution_model']}` "
        f"(fee {metadata['fee_rate']}, slippage {metadata['slippage_rate']}, "
        f"spread {metadata['spread_rate']})")
    add(f"- Starting balance {metadata['starting_balance']}, risk fraction "
        f"{metadata['risk_fraction']}")
    add(f"- Warm-up rule: `{WARMUP_RULE}`; boundary policy: "
        f"`{BOUNDARY_POLICY}`")
    add("")
    add("The 2026 dataset was **not** used. Phase 14A classified it as")
    add("documented historical context only, and it must not be pooled with")
    add("Phase 13 to enlarge the sample.")
    add("")
    add("Before any feature or outcome was read, each pass was verified to")
    add("reproduce the frozen Phase 13 trade counts and ending balances")
    add("exactly. These are the same trades Phase 13 recorded.")
    add("")

    add("## 3. Features analysed")
    add("")
    add("Pre-declared before any outcome was examined. Full rationale for")
    add("each is in `INSTRUMENTATION.md` and the Phase 14A audit.")
    add("")
    add("| feature | kind | availability | used as D2 condition |")
    add("|---|---|---|---|")

    for spec in ec.FEATURES:
        used = (
            "yes"
            if spec.name in ec.CATEGORICAL_DIMENSIONS
            or spec.name in ec.CONTINUOUS_DIMENSIONS
            else "no"
        )
        add(f"| `{spec.name}` | {spec.kind} | {spec.availability} | {used} |")

    add("")
    add("Deliberately **not** conditioned on:")
    add("")

    for name, reason in ec.EXCLUDED_FROM_CONDITIONS.items():
        add(f"- `{name}` - {reason}")

    add("")

    add("## 4. D1 descriptive findings")
    add("")
    add("Full table: `RESULTS_feature_summary.csv`. Every distribution below")
    add("is of an entry-time value; outcomes are not involved at this stage.")
    add("")

    for row in analysis["feature_rows"]:
        if row["kind"] != "continuous":
            continue

        add(f"### `{row['feature']}` ({row['config_name']})")
        add("")
        add(f"- present {row['n_present']} / {row['n_total']} "
            f"(missing {row['n_missing']})")
        add(f"- min {_fmt(row['minimum'])}, q05/q25/q50/q75/q95: "
            f"{row['quantiles']}")
        add(f"- max {_fmt(row['maximum'])}, mean {_fmt(row['mean'])}, "
            f"sd {_fmt(row['stdev'])}")
        add("")

    for row in analysis["feature_rows"]:
        if row["kind"] != "categorical":
            continue

        add(f"### `{row['feature']}` ({row['config_name']})")
        add("")
        add(f"- {row['levels']}")
        add("")

    add("**Observation on price-scale features.** `signal_close`,")
    add("`support_at_entry`, `resistance_at_entry` and `mean_range` are raw")
    add("price quantities. Over a sample in which the asset's price level")
    add("roughly doubles, their spread is dominated by calendar position")
    add("rather than by trading context. That is why the D2 conditions use the")
    add("normalised forms `mean_range_pct`, `level_width_pct` and")
    add("`range_position` instead. This is a property of the data, not a")
    add("finding about the strategy.")
    add("")

    add("## 5. D2 condition findings")
    add("")
    add("Full table: `RESULTS_condition_summary.csv`. Baseline and A2 are")
    add("reported separately and never pooled or ranked.")
    add("")
    add(f"Bins are pre-declared quartiles ({', '.join(str(int(q * 100)) + '%' for q in ec.QUANTILES)})")
    add("computed from feature values alone, before any outcome was read. No")
    add("edge was moved in response to an outcome.")
    add("")
    add("> **Limitation.** Edges are computed over the whole sample, so a")
    add("> trade in window 1 was binned partly using information from window")
    add("> 6. Per Phase 14A §9.2 this is acceptable only as a descriptive")
    add("> grouping of the sample, never as a live-applicable rule. It is not")
    add("> something a trader could have known at the time.")
    add("")
    add(_headline_observations(analysis))
    add("")

    for entry in analysis["robustness"]:
        name = entry["config_name"]
        add(f"### Pass: {name}")
        add("")
        subset = [
            r for r in analysis["condition_rows"] if r["config_name"] == name
        ]

        for dimension in ec.CATEGORICAL_DIMENSIONS:
            add(f"**{dimension}**")
            add("")
            add("| cell | n | win rate | net P&L mean | net P&L median | "
                "net P&L total | friction total | interpretable |")
            add("|---|---|---|---|---|---|---|---|")

            for row in subset:
                if row["dimension"] != dimension:
                    continue

                flag = (
                    "NO - under "
                    f"{entry['min_cell_size']}"
                    if row["insufficient_sample"] else "yes"
                )
                add(
                    f"| {row['cell']} | {row['n_trades']} | "
                    f"{_fmt(row['win_rate'])} | {_fmt(row['net_pnl_mean'])} | "
                    f"{_fmt(row['net_pnl_median'])} | "
                    f"{_fmt(row['net_pnl_total'])} | "
                    f"{_fmt(row['friction_total'])} | {flag} |"
                )

            add("")

        for dimension in ec.CONTINUOUS_DIMENSIONS:
            add(f"**{dimension}** (pre-declared quartiles)")
            add("")
            add("| cell | n | win rate | net P&L mean | net P&L median | "
                "net P&L total | interpretable |")
            add("|---|---|---|---|---|---|---|")

            for row in subset:
                if row["dimension"] != dimension:
                    continue

                flag = (
                    "NO - under "
                    f"{entry['min_cell_size']}"
                    if row["insufficient_sample"] else "yes"
                )
                add(
                    f"| {row['cell']} | {row['n_trades']} | "
                    f"{_fmt(row['win_rate'])} | {_fmt(row['net_pnl_mean'])} | "
                    f"{_fmt(row['net_pnl_median'])} | "
                    f"{_fmt(row['net_pnl_total'])} | {flag} |"
                )

            add("")

        add("Rank co-movement with net P&L (Spearman rho, descriptive only,")
        add("no significance test):")
        add("")
        add("| feature | n pairs | rho |")
        add("|---|---|---|")

        for row in analysis["associations"]:
            if row["config_name"] != name:
                continue

            add(
                f"| `{row['feature']}` | {row['n_pairs']} | "
                f"{_fmt(row['spearman_rho'])} |"
            )

        add("")

    add("## 6. D3 robustness and caveats")
    add("")

    for entry in analysis["robustness"]:
        add(f"- **{entry['config_name']}**: {entry['n_trades']} trades across "
            f"{entry['n_windows']} windows; {entry['cells_tested']} cells "
            f"tested over {entry['dimensions_tested']} dimensions; "
            f"{entry['cells_below_min']} cells below "
            f"{entry['min_cell_size']} trades; mean holding "
            f"{_fmt(entry['mean_bars_held'])} bars "
            f"(range {_fmt(entry['min_bars_held'])}-"
            f"{_fmt(entry['max_bars_held'])}).")

    add("")
    add(f"- {analysis['robustness'][0]['dependence_note']}")
    add(f"- {analysis['robustness'][0]['window_structure_note']}")
    add("")

    add("## 7. Sample-size limitations")
    add("")
    add("1. The entire primary sample is a few hundred trades across six")
    add("   sequential windows. Any cell is a small sample.")
    add("2. Cells below the pre-declared floor are labelled")
    add("   `insufficient_sample` in the CSV and must not be interpreted.")
    add("3. `retest_distance` exists on very few trades, so retest quality is")
    add("   described but never conditioned on.")
    add("4. No confidence interval is reported. Phase 14A §10.2 forbids")
    add("   treating the trade count as an independent sample size, and the")
    add("   block length for clustered one-position-at-a-time trades is")
    add("   unvalidated.")
    add("")

    add("## 8. Multiple-comparison and researcher-degrees-of-freedom warning")
    add("")
    total_cells = sum(e["cells_tested"] for e in analysis["robustness"])
    add(f"Across both passes, **{total_cells} condition cells** were examined "
        f"over {len(ec.CATEGORICAL_DIMENSIONS) + len(ec.CONTINUOUS_DIMENSIONS)} "
        "pre-declared dimensions.")
    add("")
    add("Phase 14A §8.1 states that with a sample this size, scanning even a")
    add("dozen features will surface at least one apparently interesting")
    add("pattern **purely by chance**. Every cell is reported, including")
    add("uninteresting and null ones, precisely so that this count is")
    add("visible rather than hidden behind a selected subset.")
    add("")
    add("A further degree of freedom deserves naming: this analysis was")
    add("designed after the instrumented features existed, and bin choice,")
    add("feature choice and normalisation were all made by someone who knows")
    add("the strategy produced mixed results. Repeated inspection of the same")
    add("windows can converge on a pattern by search alone.")
    add("")

    add("## 9. What can and cannot be concluded")
    add("")
    add("**Directly observed.**")
    add("")
    add("- The entry-time distributions in D1, and the per-cell counts and")
    add("  outcome statistics in D2, for these trades on this data.")
    add("- Both passes reproduce the frozen Phase 13 results exactly, so the")
    add("  described trades are the committed ones.")
    add("")
    add("**Descriptive interpretation.**")
    add("")
    add("- Where cells differ, the size and direction of that difference in")
    add("  this sample. This is a description of past trades, not a mechanism.")
    add("")
    add("**Uncertain.**")
    add("")
    add("- Whether any observed difference is chance. With this many cells")
    add("  and this sample size, it cannot be established from these data.")
    add("- Whether a difference would persist in a different market period.")
    add("")
    add("**Not supported by anything here.**")
    add("")
    add("- That any entry-time feature predicts future performance.")
    add("- That any condition identified is exploitable as a rule.")
    add("- That any configuration is better than another.")
    add("")
    add("### Hypothesis candidates")
    add("")
    add("Where a cell difference is large enough to be worth naming, it is")
    add("recorded below as a **hypothesis candidate** and nothing more. A")
    add("hypothesis candidate is a reason to collect fresh data, not a rule.")
    add("**No strategy modification follows from any of them.**")
    add("")

    add(_hypotheses_section(analysis))

    add("## 10. Is a Phase 14D justified?")
    add("")
    add("**No, and this is a structural problem rather than a matter of")
    add("judgment.**")
    add("")
    add("Phase 14A §12.1: Phase 14C has now consumed the only remaining")
    add("clean data. The 2026 set was already used in Phase 10, and")
    add("2024-2025 is used here. There is therefore **no unused data left** on")
    add("which a Phase 14D hypothesis could be validated.")
    add("")
    add("A Phase 14D would have to either re-use data Phase 14C has already")
    add("seen - in which case it is not validation - or wait for data not yet")
    add("acquired. So the honest position is that Phase 14 terminates at")
    add("hypothesis generation, and any future validation requires new data")
    add("and its own pre-registration.")
    add("")

    add("## 11. Reproducibility")
    add("")
    add(f"- Script: `experiments/phase14/run_descriptive.py`")
    add(f"- Module: `research_engine/src/crypto_paper_lab/entrycontext.py`")
    add(f"- Tests: `research_engine/tests/test_phase14c_analysis.py`")
    add("- Deterministic: no randomness, fixed iteration and sort order,")
    add("  fixed rounding for output. Repeated runs are byte-identical.")
    add("- Bins are derived from feature values only, so they cannot depend")
    add("  on an outcome.")
    add(f"- Git commit: `{metadata['git_commit']}`")
    add(f"- Git working tree clean: **{metadata['git_clean']}**")

    if not metadata["git_clean"]:
        add("")
        add("> **Recorded deviation:** this analysis was produced with a dirty")
        add("> working tree. The dirty state at execution time was:")
        add(">")
        for line in metadata["git_dirty_entries"]:
            add(f">     `{line}`")
        add(">")
        add("> The Phase 14B instrumentation is part of that dirty state, so")
        add("> the commit alone does not identify the code that produced these")
        add("> figures. This is recorded rather than hidden.")

    add("")
    add("## 12. Dataset SHA-256")
    add("")
    add(f"    {metadata['dataset_sha256']}")
    add("")
    add(f"Path: `{metadata['dataset_path']}`")
    add("")
    add("Verified at load time against the frozen constant in")
    add("`crypto_paper_lab.walkforward`. The dataset was opened read-only and")
    add("not modified.")
    add("")

    add("## 13. Statement on strategy parameters")
    add("")
    add("**No strategy parameter, threshold, default, entry rule or exit rule")
    add("was changed.**")
    add("")
    add("The analysis re-runs the frozen Phase 13 windows using")
    add("`baseline_config()` and `a2_config()` exactly as committed. It reads")
    add("the resulting trades and writes new files under")
    add("`experiments/phase14/`. No file under `research_engine/src/` was")
    add("modified by this phase, and the Phase 13 artifacts are unchanged.")
    add("")
    add("No leverage, margin, partial exit, trailing stop, profit callback or")
    add("position-sizing change was introduced. MAE/MFE were not computed.")
    add("No outcome-derived entry feature was created.")
    add("")
    add("Phase 14D was not started.")
    add("")

    return "\n".join(lines)


def _headline_observations(analysis: dict) -> str:
    """The plainest facts about the outcome distribution, stated first.

    These are counts and sums read directly off the computed rows. They are
    placed before the conditional tables so the conditional differences are
    read against the overall picture rather than in isolation.
    """

    lines: list[str] = []
    add = lines.append

    add("**Observations that hold before any conditioning is applied.**")
    add("")

    for entry in analysis["robustness"]:
        name = entry["config_name"]
        rows = [
            r for r in analysis["condition_rows"]
            if r["config_name"] == name
        ]
        totals = [
            r["net_pnl_total"] for r in rows
            if r["dimension"] == "side" and r["net_pnl_total"] is not None
        ]
        positive = sum(1 for t in totals if t > 0)
        windows_negative = sum(
            1 for w in entry["per_window"]
            if (w["net_pnl_total"] or 0.0) < 0.0
        )
        friction = [
            r["friction_total"] for r in rows
            if r["dimension"] == "side" and r["friction_total"] is not None
        ]

        add(f"- **{name}**: {entry['n_trades']} trades, total net P&L "
            f"{_fmt(entry['net_pnl_total'])}, mean {_fmt(entry['net_pnl_mean'])} "
            f"per trade, median {_fmt(entry['net_pnl_median'])}. "
            f"{positive} of {len(totals)} direction cells are net positive. "
            f"{windows_negative} of {len(entry['per_window'])} windows are net "
            f"negative. Total friction across the pass "
            f"{_fmt(sum(friction)) if friction else 'n/a'}.")

    add("")
    add("Every conditional table below should be read against that. A cell")
    add("that looks better than its neighbours is usually still losing money")
    add("overall, and a relative difference between two negative cells is not")
    add("a finding.")
    add("")

    return "\n".join(lines)


def _hypotheses_section(analysis: dict) -> str:
    """Name hypothesis candidates neutrally, or state that none qualify.

    The pre-declared bar for naming a cell at all is that its **best** cell
    must be net positive in-sample. Without that requirement a dimension whose
    every cell loses money would still be "named" on the strength of a
    relative difference between two negative numbers, which reads as a
    finding when it is nothing of the kind.
    """

    lines: list[str] = []

    for entry in analysis["robustness"]:
        name = entry["config_name"]
        rows = [
            r for r in analysis["condition_rows"]
            if r["config_name"] == name and not r["insufficient_sample"]
        ]
        candidates: list[str] = []

        for dimension in ec.CONTINUOUS_DIMENSIONS:
            subset = [r for r in rows if r["dimension"] == dimension]

            if len(subset) < 2:
                continue

            best = max(subset, key=lambda r: (r["net_pnl_mean"] or 0.0))
            worst = min(subset, key=lambda r: (r["net_pnl_mean"] or 0.0))

            if best["net_pnl_mean"] is None or worst["net_pnl_mean"] is None:
                continue

            spread = best["net_pnl_mean"] - worst["net_pnl_mean"]

            if (
                best["n_trades"] >= 30
                and worst["n_trades"] >= 30
                and best["net_pnl_mean"] > 0.0
                and spread > 0
            ):
                candidates.append(
                    f"- `{dimension}`: cell `{best['cell']}` "
                    f"(n={best['n_trades']}) averaged "
                    f"{_fmt(best['net_pnl_mean'])} mean net P&L against "
                    f"`{worst['cell']}` (n={worst['n_trades']}) at "
                    f"{_fmt(worst['net_pnl_mean'])}, a spread of "
                    f"{_fmt(spread)}."
                )

        if candidates:
            lines.append(f"**{name}**")
            lines.append("")
            lines.extend(candidates)
            lines.append("")
            lines.append(
                "Named because the best cell is net positive in this sample"
            )
            lines.append(
                "and both cells clear the pre-declared size floor. That is a"
            )
            lines.append(
                "weak bar: it means \"worth recording\", not \"supported\"."
            )
            lines.append(
                "A spread of this size across cells this small is within what"
            )
            lines.append(
                "chance produces, the bin edges came from the same sample,"
            )
            lines.append(
                "and both passes sit in-sample. No rule, threshold or"
            )
            lines.append(
                "configuration change follows from this."
            )
            lines.append("")
        else:
            lines.append(
                f"- **{name}**: no continuous-dimension cell qualified. Every"
                " dimension either had all cells net negative, or its best"
                " cell failed the size floor. Nothing here is worth recording"
                " as a hypothesis candidate."
            )
            lines.append("")

    lines.append(
        "Note that the two passes are **not** independent confirmations of"
    )
    lines.append(
        "each other. A2's `min_breakout_distance` was chosen in Phase 7 on"
    )
    lines.append(
        "2024-2025, so both passes describe overlapping, already-used data."
    )
    lines.append(
        "Apparent agreement between them is not out-of-sample evidence."
    )
    lines.append("")

    return "\n".join(lines) if lines else (
        "- No cell spread met the pre-declared bar for naming."
    )


def _fmt(value) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, float):
        return f"{value:.6f}"

    return str(value)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def describe_plan(candles: list) -> None:
    """Print the frozen setup without producing any result."""

    resolved = resolve_windows(candles, PHASE13_WINDOWS)
    costs = phase13_costs()

    print("=" * 96)
    print("PHASE 14C DESCRIPTIVE ENTRY-CONTEXT ANALYSIS - PLAN (nothing executed)")
    print("=" * 96)
    print(f"dataset path      : {DATASET_PATH}")
    print(f"dataset sha256    : {DATASET_SHA256}")
    print(f"dataset range     : {DATASET_FIRST} -> {DATASET_LAST}")
    print(f"dataset candles   : {len(candles)} (expected {DATASET_CANDLES})")
    print(f"windows           : {len(resolved)}")
    print(f"execution model   : {costs.execution_model}")
    print(f"fee / slip / spread: {costs.fee_rate} / {costs.slippage_rate} / "
          f"{costs.spread_rate}")
    print(f"starting balance  : {STARTING_BALANCE}")
    print(f"risk fraction     : {RISK_FRACTION}")
    print()
    print("  passes (reported separately, never ranked, never pooled):")
    for name, factory in PASSES:
        print(f"    {name:<10} {factory()!r}")
    print()
    print(f"  features pre-declared ({len(ec.FEATURES)}):")
    for spec in ec.FEATURES:
        print(f"    {spec.name:<22} {spec.kind:<12} {spec.availability}")
    print()
    print(f"  D2 categorical dimensions : {ec.CATEGORICAL_DIMENSIONS}")
    print(f"  D2 continuous dimensions : {ec.CONTINUOUS_DIMENSIONS}")
    print(f"  pre-declared quantiles   : {ec.QUANTILES}")
    print(f"  minimum interpretable cell: {ec.MIN_CELL} trades")
    print()
    print("  NOT conditioned on:")
    for key, reason in ec.EXCLUDED_FROM_CONDITIONS.items():
        print(f"    {key:<22} {reason}")
    print()
    print("  would write on --execute:")
    for path in (FEATURE_CSV, CONDITION_CSV, ANALYSIS_JSON, SUMMARY_MD):
        print(f"    {path.relative_to(REPO_ROOT)}")
    print()
    print("  No strategy parameter will be changed. No ranking is produced.")


def execute() -> int:
    """Run the analysis and write the outputs."""

    candles = load_and_validate()
    costs = phase13_costs()
    analysis = build_analysis(candles)

    feature_rows = []

    for row in analysis["feature_rows"]:
        row = dict(row)
        config_name = row.pop("config_name")
        row["excluded_from_conditions"] = (
            row["feature"] in ec.EXCLUDED_FROM_CONDITIONS
        )
        row["exclusion_reason"] = ec.EXCLUDED_FROM_CONDITIONS.get(
            row["feature"], ""
        )

        # config_name is taken from the popped value. Re-reading it from the
        # remaining dict would write an empty pass label and silently merge
        # the two passes in the artifact.
        ordered: dict = {"config_name": config_name}

        for field in ec.FEATURE_CSV_FIELDS:
            if field == "config_name":
                continue

            ordered[field] = row.get(field)

        feature_rows.append(ordered)

    write_csv(FEATURE_CSV, feature_rows, ec.FEATURE_CSV_FIELDS)
    write_csv(CONDITION_CSV, analysis["condition_rows"], ec.CONDITION_CSV_FIELDS)

    dirty = [
        line for line in _git("status", "--porcelain").splitlines()
        if line.strip()
    ]

    metadata = {
        "dataset_path": DATASET_PATH,
        "dataset_sha256": DATASET_SHA256,
        "dataset_candles": len(candles),
        "windows": len(PHASE13_WINDOWS),
        "execution_model": costs.execution_model,
        "fee_rate": costs.fee_rate,
        "slippage_rate": costs.slippage_rate,
        "spread_rate": costs.spread_rate,
        "starting_balance": STARTING_BALANCE,
        "risk_fraction": RISK_FRACTION,
        "git_commit": _git("rev-parse", "HEAD") or "unknown",
        "git_clean": not dirty,
        "git_dirty_entries": dirty,
    }

    ANALYSIS_JSON.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "phase": "14C",
                "purpose": "descriptive entry-context analysis; not "
                           "optimisation; no predictive claim",
                "quantiles": analysis["quantiles"],
                "min_cell_size": ec.MIN_CELL,
                "features": [asdict(spec) for spec in ec.FEATURES],
                "excluded_from_conditions": dict(
                    ec.EXCLUDED_FROM_CONDITIONS
                ),
                "phase13_equivalence": analysis["equivalence"],
                "bins": analysis["bins"],
                "feature_summary": feature_rows,
                "condition_summary": analysis["condition_rows"],
                "rank_associations": analysis["associations"],
                "robustness": analysis["robustness"],
                "trade_population": analysis["population"],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
        newline="\n",
    )

    # newline="\n" is explicit so the artifact is byte-identical on Windows and
    # POSIX. Relying on the platform default would make the committed hash
    # platform-dependent, which defeats the point of a provenance record.
    SUMMARY_MD.write_text(
        compose_summary(analysis, metadata), encoding="utf-8", newline="\n"
    )

    for path in (FEATURE_CSV, CONDITION_CSV, ANALYSIS_JSON, SUMMARY_MD):
        print(f"wrote {path.relative_to(REPO_ROOT)}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 14C descriptive entry-context analysis. Without "
            "--execute this only validates the frozen setup and prints the "
            "plan; no result artifact is ever written."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Run the analysis and write results. Required: without this flag "
            "no result file is ever written."
        ),
    )
    args = parser.parse_args(argv)

    candles = load_and_validate()

    if not args.execute:
        describe_plan(candles)
        print()
        print("No analysis executed. No result file written.")
        print("Re-run with --execute to produce Phase 14C results.")
        return 0

    return execute()


if __name__ == "__main__":
    raise SystemExit(main())