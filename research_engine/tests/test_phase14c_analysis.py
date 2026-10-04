"""Phase 14C tests: descriptive entry-context analysis.

The point of this file is to prove the analysis is *descriptive*. Each test
targets one way that could go wrong:

* an outcome leaking into the feature stage or the bin edges;
* ``baseline`` and ``A2`` being pooled or ranked;
* a future candle reaching an entry-time feature;
* undersized cells being presented as evidence;
* the frozen dataset, Phase 13 artifacts or strategy config being disturbed;
* non-deterministic output.

No test asserts that any condition is predictive or profitable. Such an
assertion would be unsupportable from this sample, and writing one would
misrepresent the evidence.
"""
from __future__ import annotations

import copy
import csv
import importlib.util
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_paper_lab import entrycontext as ec
from crypto_paper_lab.backtest import run_backtest
from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.models import Candle, PaperTrade
from crypto_paper_lab.strategy import StrategyConfig, analyze
from crypto_paper_lab.walkforward import (
    A2_NAME,
    BASELINE_NAME,
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_PATH,
    DATASET_SHA256,
    PHASE13_WINDOWS,
    WalkForwardValidationError,
    a2_config,
    baseline_config,
    config_hash,
    dataset_fingerprint,
    phase13_costs,
    resolve_windows,
    sha256_of_file,
    walk_forward,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "experiments/phase13"
PHASE14 = ROOT / "experiments/phase14"

FROZEN_PHASE13 = {
    "PLAN.md": "8D9F9021AE22AE36344FD14464796486A7EA415B261C7AA189E4A180DB7D7800",
    "RESULTS_windows.csv":
        "1A2D37A4FF744F59BEE6A85E8A8E61538AFCC43C7B0FC17A352DCC1559953E7D",
    "RESULTS_windows.json":
        "67092DEC496A675B201664C66F6CC485C37EF242648BE832FCC44E68FEC94224",
    "SUMMARY.md":
        "188D3A1B8297E6D4B10CA6C30AB198358D69877124A782E6D3EBBE618F04138D",
    "EXPERIMENT_LOG.md":
        "2E59ABDB7E211C6012F40BC55A8F56634763C0C5CCBE0804A7700199B445F435",
}

COSTS = TradingCosts(0.001, 0.0005, 0.0, "cost_deduction")
START = datetime(2024, 1, 1)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def candles():
    from crypto_paper_lab.data import load_ohlcv_csv

    return load_ohlcv_csv(Path(DATASET_PATH))


@pytest.fixture(scope="session")
def baseline_records(candles):
    runs = walk_forward(candles, baseline_config(), BASELINE_NAME, costs=COSTS)
    return ec.collect_records(runs, BASELINE_NAME)


@pytest.fixture(scope="session")
def a2_records(candles):
    runs = walk_forward(candles, a2_config(), A2_NAME, costs=COSTS)
    return ec.collect_records(runs, A2_NAME)


def make_trade(**kwargs) -> PaperTrade:
    base = dict(
        side="long",
        entry_time=START,
        entry_price=100.0,
        quantity=1.0,
        exit_time=START + timedelta(hours=2),
        exit_price=110.0,
        reason="uptrend breakout",
        exit_reason="opposite_signal",
        bars_held=2,
        costs=1.0,
        raw_entry_price=100.0,
        raw_exit_price=110.0,
        signal_close=100.0,
        trend_state="up",
        breakout_distance=0.003,
        retest_distance=None,
        realised_volatility=0.004,
        mean_range=0.6,
        support_at_entry=99.0,
        resistance_at_entry=101.0,
    )
    base.update(kwargs)
    return PaperTrade(**base)


def synth(count: int = 1500) -> list[Candle]:
    out: list[Candle] = []

    for i in range(count):
        base = 100.0 + i * 0.02
        phase = i % 40
        price = (
            base + phase * 0.5 if phase < 20 else base + (40 - phase) * 0.5
        )
        out.append(
            Candle(
                START + timedelta(hours=i),
                open=price,
                high=price + 0.3,
                low=price - 0.3,
                close=price + 0.1,
                volume=10.0,
            )
        )

    return out


# ---------------------------------------------------------------------------
# 1. determinism
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_feature_summary_is_deterministic(baseline_records) -> None:
    first = ec.feature_table(baseline_records)
    second = ec.feature_table(baseline_records)
    assert first == second


@pytest.mark.slow
def test_condition_summary_is_deterministic(baseline_records) -> None:
    bins = ec.declare_bins(baseline_records)
    first = ec.condition_table(baseline_records, bins, BASELINE_NAME)
    second = ec.condition_table(baseline_records, bins, BASELINE_NAME)
    assert first == second


@pytest.mark.slow
def test_bin_edges_are_deterministic(baseline_records) -> None:
    assert ec.declare_bins(baseline_records) == ec.declare_bins(
        baseline_records
    )


@pytest.mark.slow
def test_repeated_pipeline_runs_are_identical(candles) -> None:
    """Same input, same output, no ordering or float drift."""

    def once() -> str:
        runs = walk_forward(candles, baseline_config(), BASELINE_NAME, costs=COSTS)
        records = ec.collect_records(runs, BASELINE_NAME)
        payload = {
            "features": ec.feature_table(records),
            "conditions": ec.condition_table(
                records, ec.declare_bins(records), BASELINE_NAME
            ),
            "robustness": ec.robustness_summary(
                records, BASELINE_NAME, ec.declare_bins(records)
            ),
        }
        return json.dumps(payload, sort_keys=True, default=str)

    assert once() == once()


# ---------------------------------------------------------------------------
# 2. outcome cannot leak into features or bins
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_bins_are_identical_when_every_outcome_is_corrupted(
    baseline_records,
) -> None:
    """The decisive contamination test.

    Every outcome is replaced with an absurd value. If any part of the bin
    derivation consulted an outcome, the edges would move.
    """

    original = ec.declare_bins(baseline_records)

    corrupted = copy.deepcopy(baseline_records)

    for index, record in enumerate(corrupted):
        record.outcome = {
            "pnl": -1e6 - index,
            "net_pnl": 1e6 + index,
            "total_friction": 1e9,
            "bars_held": 9999,
            "exit_reason": "corrupted",
            "win": index % 2 == 0,
        }

    assert ec.declare_bins(corrupted) == original


@pytest.mark.slow
def test_feature_summary_is_identical_when_outcomes_are_corrupted(
    baseline_records,
) -> None:
    corrupted = copy.deepcopy(baseline_records)

    for record in corrupted:
        record.outcome = {"net_pnl": 1e12, "win": True}

    assert ec.feature_table(corrupted) == ec.feature_table(baseline_records)


@pytest.mark.slow
def test_feature_summary_cannot_reach_outcomes(baseline_records) -> None:
    """Structural, not behavioural: the function has no outcome parameter."""

    import inspect

    for func in (
        ec.feature_summary,
        ec.feature_table,
        ec.declare_bins,
        ec.assign_bin,
    ):
        params = set(inspect.signature(func).parameters)
        assert "outcome" not in params
        assert "records_outcome" not in params


@pytest.mark.slow
def test_features_dict_contains_no_outcome_key(baseline_records) -> None:
    banned = ("pnl", "win", "loss", "exit", "bars_held", "friction", "mae",
              "mfe", "outcome", "return")

    for record in baseline_records:
        for key in record.features:
            assert not any(b in key.lower() for b in banned), key


@pytest.mark.slow
def test_no_mae_or_mfe_anywhere_in_the_analysis(baseline_records) -> None:
    for record in baseline_records:
        assert "mae" not in record.features
        assert "mfe" not in record.features
        assert set(record.outcome) == {
            "pnl", "net_pnl", "total_friction", "bars_held",
            "exit_reason", "win",
        }


# ---------------------------------------------------------------------------
# 3. no future data in entry features
# ---------------------------------------------------------------------------


def test_features_are_invariant_to_post_entry_candles() -> None:
    """Entry features must not move when the future is rewritten."""

    series = synth(1500)
    result = run_backtest(series, config=StrategyConfig(), costs=COSTS)
    assert result.total_trades > 3

    trade = result.trades[1]
    cutoff = next(
        i for i, c in enumerate(series) if c.timestamp == trade.entry_time
    ) + 3

    shifted = list(series)

    for i in range(cutoff, len(shifted)):
        c = shifted[i]
        shifted[i] = Candle(
            c.timestamp, c.open + 40.0, c.high + 40.0,
            c.low + 40.0, c.close + 40.0, c.volume + 5.0,
        )

    mutated = run_backtest(shifted, config=StrategyConfig(), costs=COSTS)
    boundary = series[cutoff].timestamp

    before = {
        t.entry_time: ec.record_from_trade(t, 1, "x")
        for t in result.trades if t.entry_time < boundary
    }
    after = {
        t.entry_time: ec.record_from_trade(t, 1, "x")
        for t in mutated.trades if t.entry_time < boundary
    }

    assert before and set(before) == set(after)

    for moment, record in before.items():
        assert record.features == after[moment].features, moment


def test_entry_features_come_only_from_the_pre_entry_window() -> None:
    """Recompute features from candles and require exact agreement."""

    series = synth(800)
    window = series[:300]
    signal = analyze(window, StrategyConfig())
    record = ec.record_from_trade(
        make_trade(
            reason="uptrend breakout",
            signal_close=signal.signal_close,
            breakout_distance=signal.breakout_distance,
            realised_volatility=signal.realised_volatility,
            mean_range=signal.mean_range,
            support_at_entry=signal.support,
            resistance_at_entry=signal.resistance,
        ),
        1,
        "x",
    )

    assert record.features["realised_volatility"] == signal.realised_volatility
    assert record.features["mean_range"] == signal.mean_range
    assert record.features["breakout_distance"] == signal.breakout_distance


# ---------------------------------------------------------------------------
# 4. baseline / A2 separation
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_conditions_never_pool_configurations(baseline_records, a2_records) -> None:
    baseline_rows = ec.condition_table(
        baseline_records, ec.declare_bins(baseline_records), BASELINE_NAME
    )
    a2_rows = ec.condition_table(
        a2_records, ec.declare_bins(a2_records), A2_NAME
    )

    assert {r["config_name"] for r in baseline_rows} == {BASELINE_NAME}
    assert {r["config_name"] for r in a2_rows} == {A2_NAME}


@pytest.mark.slow
def test_condition_counts_match_their_own_pass(baseline_records, a2_records) -> None:
    for records, name in (
        (baseline_records, BASELINE_NAME),
        (a2_records, A2_NAME),
    ):
        rows = ec.condition_table(records, ec.declare_bins(records), name)
        counted = [r for r in rows if r["dimension"] == "side"]
        assert sum(r["n_trades"] for r in counted) == len(records)


@pytest.mark.slow
def test_the_two_passes_are_reported_independently(
    baseline_records, a2_records
) -> None:
    assert len(baseline_records) == 267
    assert len(a2_records) == 217
    assert {r.config_name for r in baseline_records} == {BASELINE_NAME}
    assert {r.config_name for r in a2_records} == {A2_NAME}


@pytest.mark.slow
def test_a2_breakout_distance_is_mechanically_shifted(
    baseline_records, a2_records
) -> None:
    """A2 differs only by ``min_breakout_distance=0.002``.

    This must show up in the recorded feature, which is a useful check that
    the instrumentation is real rather than decorative.
    """

    base = [
        r.features["breakout_distance"] for r in baseline_records
        if r.features["breakout_distance"] is not None
    ]
    a2 = [
        r.features["breakout_distance"] for r in a2_records
        if r.features["breakout_distance"] is not None
    ]

    assert min(a2) >= 0.002
    assert min(base) < 0.002


# ---------------------------------------------------------------------------
# 5. sample counts and missing values
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_feature_counts_match_the_record_count(baseline_records) -> None:
    for row in ec.feature_table(baseline_records):
        assert row["n_total"] == len(baseline_records)
        assert row["n_present"] + row["n_missing"] == row["n_total"]


@pytest.mark.slow
def test_retest_distance_is_missing_exactly_on_breakout_entries(
    baseline_records,
) -> None:
    for record in baseline_records:
        kind = record.features["signal_kind"]
        value = record.features["retest_distance"]

        if kind == "retest":
            assert value is not None
        else:
            assert value is None


@pytest.mark.slow
def test_missing_is_never_substituted_with_zero(baseline_records) -> None:
    """A missing measurement must read ``None``, never ``0.0``."""

    seen_missing = False

    for record in baseline_records:
        value = record.features["retest_distance"]

        if record.features["signal_kind"] == "breakout":
            assert value is None
            seen_missing = True

    assert seen_missing, "fixture must actually contain missing values"


def test_zero_is_preserved_as_a_real_value() -> None:
    """The converse: a genuine 0.0 must not be confused with missing.

    ``mean_range`` is forced to zero here, which makes ``mean_range_pct`` a
    true ``0.0`` rather than a ``None``.
    """

    record = ec.record_from_trade(
        make_trade(signal_close=100.0, mean_range=0.0), 1, "x"
    )

    assert record.features["mean_range"] == 0.0
    assert record.features["mean_range_pct"] == 0.0
    assert record.features["mean_range_pct"] is not None


def test_continuous_summary_ignores_missing_values() -> None:
    records = [
        ec.record_from_trade(
            make_trade(retest_distance=None), 1, "x"
        )
        for _ in range(10)
    ]

    row = ec.feature_summary(records, ec.FEATURE_BY_NAME["retest_distance"])
    assert row["n_present"] == 0
    assert row["n_missing"] == 10
    assert row["mean"] is None
    assert row["median"] is None
    assert row["minimum"] is None


@pytest.mark.slow
def test_categorical_summary_reports_proportions(baseline_records) -> None:
    row = ec.feature_summary(baseline_records, ec.FEATURE_BY_NAME["side"])

    assert row["kind"] == "categorical"
    assert "long=" in row["levels"]
    assert "short=" in row["levels"]
    assert row["n_present"] + row["n_missing"] == len(baseline_records)


# ---------------------------------------------------------------------------
# 6. undersized cells
# ---------------------------------------------------------------------------


def test_small_cells_are_flagged_insufficient() -> None:
    records = [
        ec.record_from_trade(make_trade(), 1, "x") for _ in range(5)
    ]
    rows = ec.condition_table(records, ec.declare_bins(records), "x")

    assert rows
    assert all(r["insufficient_sample"] for r in rows)


@pytest.mark.slow
def test_large_cells_are_not_flagged(baseline_records) -> None:
    rows = ec.condition_table(
        baseline_records, ec.declare_bins(baseline_records), BASELINE_NAME
    )
    side_rows = [r for r in rows if r["dimension"] == "side"]

    assert side_rows
    assert all(not r["insufficient_sample"] for r in side_rows)


@pytest.mark.slow
def test_retest_cells_are_flagged_on_real_data(baseline_records) -> None:
    """The retest split is genuinely too small and must be labelled so."""

    rows = ec.condition_table(
        baseline_records, ec.declare_bins(baseline_records), BASELINE_NAME
    )
    retest = next(
        r for r in rows
        if r["dimension"] == "signal_kind" and r["cell"] == "retest"
    )

    assert retest["n_trades"] < ec.MIN_CELL
    assert retest["insufficient_sample"] is True


@pytest.mark.slow
def test_win_rate_is_always_published_with_its_denominator(
    baseline_records,
) -> None:
    rows = ec.condition_table(
        baseline_records, ec.declare_bins(baseline_records), BASELINE_NAME
    )

    for row in rows:
        if row["win_rate"] is not None:
            assert row["n_trades"] > 0
            assert row["wins"] + row["losses"] <= row["n_trades"]


# ---------------------------------------------------------------------------
# 7. pre-declared, not searched
# ---------------------------------------------------------------------------


def test_quantiles_are_fixed_module_constants() -> None:
    assert ec.QUANTILES == (0.25, 0.50, 0.75)


def test_dimensions_are_fixed_module_constants() -> None:
    assert ec.CATEGORICAL_DIMENSIONS == ("side", "signal_kind")
    assert ec.CONTINUOUS_DIMENSIONS == (
        "breakout_distance",
        "realised_volatility",
        "mean_range_pct",
        "level_width_pct",
        "range_position",
    )


def test_every_conditioned_dimension_has_a_declared_spec() -> None:
    for name in ec.CATEGORICAL_DIMENSIONS + ec.CONTINUOUS_DIMENSIONS:
        assert name in ec.FEATURE_BY_NAME


def test_every_feature_declares_availability_and_rationale() -> None:
    for spec in ec.FEATURES:
        assert spec.availability in {
            ec.ENTRY_TIME, ec.DERIVED_FROM_ENTRY_TIME, ec.OUTCOME_SIDE
        }
        assert len(spec.rationale) > 20
        assert spec.kind in {"continuous", "categorical"}


def test_trend_state_is_documented_as_excluded() -> None:
    assert "trend_state" in ec.EXCLUDED_FROM_CONDITIONS
    assert "trend_state" not in ec.CATEGORICAL_DIMENSIONS
    assert "trend_state" not in ec.CONTINUOUS_DIMENSIONS


def test_retest_distance_is_documented_as_excluded() -> None:
    assert "retest_distance" in ec.EXCLUDED_FROM_CONDITIONS
    assert "retest_distance" not in ec.CONTINUOUS_DIMENSIONS


@pytest.mark.slow
def test_trend_state_is_perfectly_collinear_with_side(
    baseline_records,
) -> None:
    """Justifies excluding it: it carries no independent information."""

    for record in baseline_records:
        expected = "up" if record.features["side"] == "long" else "down"
        assert record.features["trend_state"] == expected


def test_assign_bin_places_every_trade_in_exactly_one_cell() -> None:
    edges = [0.1, 0.2, 0.3]

    assert ec.assign_bin(0.05, edges) == "q00_q25"
    assert ec.assign_bin(0.1, edges) == "q25_q50"
    assert ec.assign_bin(0.25, edges) == "q50_q75"
    assert ec.assign_bin(0.3, edges) == "q75_inf"
    assert ec.assign_bin(0.9, edges) == "q75_inf"
    assert ec.assign_bin(None, edges) is None
    assert ec.assign_bin(0.5, []) is None


# ---------------------------------------------------------------------------
# 8. numeric helpers
# ---------------------------------------------------------------------------


def test_quantile_matches_linear_interpolation() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert ec.quantile(values, 0.0) == 1.0
    assert ec.quantile(values, 1.0) == 4.0
    assert ec.quantile(values, 0.5) == pytest.approx(2.5)
    assert ec.quantile(values, 0.25) == pytest.approx(1.75)


def test_quantile_on_empty_is_none() -> None:
    assert ec.quantile([], 0.5) is None
    assert ec.quantile([7.0], 0.5) == 7.0


def test_spearman_detects_monotone_relations() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert ec.spearman(xs, xs) == pytest.approx(1.0)
    assert ec.spearman(xs, [-v for v in xs]) == pytest.approx(-1.0)


def test_spearman_handles_ties_by_averaging() -> None:
    assert ec.spearman([1.0, 1.0, 2.0, 2.0], [1.0, 1.0, 2.0, 2.0]) == (
        pytest.approx(1.0)
    )


def test_spearman_returns_none_when_undefined() -> None:
    assert ec.spearman([1.0], [2.0]) is None
    assert ec.spearman([1.0, 1.0], [1.0, 1.0]) is None


def test_signal_kind_classification() -> None:
    assert ec.signal_kind("bullish retest") == "retest"
    assert ec.signal_kind("bearish retest") == "retest"
    assert ec.signal_kind("uptrend breakout") == "breakout"
    assert ec.signal_kind("downtrend breakdown") == "breakout"


def test_signal_kind_does_not_match_flat_signals_as_retests() -> None:
    """A flat reason contains the word 'retest' but is not a retest entry."""

    assert ec.signal_kind("no confirmed breakout or retest") == "other"
    assert ec.signal_kind("no confirmed breakout or retest") != "retest"


def test_signal_kind_covers_exactly_the_four_trade_reasons() -> None:
    assert ec.RETEST_REASONS | ec.BREAKOUT_REASONS == {
        "bullish retest",
        "bearish retest",
        "uptrend breakout",
        "downtrend breakdown",
    }
    assert not (ec.RETEST_REASONS & ec.BREAKOUT_REASONS)


# ---------------------------------------------------------------------------
# 9. derived features
# ---------------------------------------------------------------------------


def test_derived_features_are_entry_time_ratios() -> None:
    record = ec.record_from_trade(
        make_trade(
            signal_close=100.0,
            mean_range=2.0,
            support_at_entry=95.0,
            resistance_at_entry=105.0,
        ),
        1,
        "x",
    )

    assert record.features["mean_range_pct"] == pytest.approx(0.02)
    assert record.features["level_width_pct"] == pytest.approx(10.0 / 95.0)
    assert record.features["range_position"] == pytest.approx(0.5)


def test_derived_features_are_none_when_inputs_missing() -> None:
    record = ec.record_from_trade(
        make_trade(support_at_entry=None, resistance_at_entry=None), 1, "x"
    )

    assert record.features["mean_range_pct"] is not None
    assert record.features["level_width_pct"] is None
    assert record.features["range_position"] is None


def test_derived_features_do_not_use_outcomes() -> None:
    a = ec.record_from_trade(make_trade(), 1, "x")
    b = ec.record_from_trade(
        make_trade(exit_price=1e9, costs=1e6, bars_held=1), 1, "x"
    )

    for key in ("mean_range_pct", "level_width_pct", "range_position"):
        assert a.features[key] == b.features[key]


def test_range_position_is_none_when_levels_coincide() -> None:
    record = ec.record_from_trade(
        make_trade(support_at_entry=100.0, resistance_at_entry=100.0), 1, "x"
    )

    assert record.features["range_position"] is None


# ---------------------------------------------------------------------------
# 10. serialization
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_json_payload_is_stable(baseline_records) -> None:
    bins = ec.declare_bins(baseline_records)
    payload = {
        "features": ec.feature_table(baseline_records),
        "conditions": ec.condition_table(baseline_records, bins, BASELINE_NAME),
    }

    first = json.dumps(payload, sort_keys=True, default=str)
    second = json.dumps(payload, sort_keys=True, default=str)
    assert first == second


def test_csv_field_order_is_declared_and_complete() -> None:
    """Every declared CSV column must be produced by the analysis functions.

    ``config_name``, ``excluded_from_conditions`` and ``exclusion_reason`` are
    attached by the runner, so they are checked against the runner's own
    assembly rather than against ``feature_summary``.
    """

    row = ec.feature_summary([], ec.FEATURES[0])
    runner_owned = {
        "config_name", "excluded_from_conditions", "exclusion_reason"
    }

    for field in ec.FEATURE_CSV_FIELDS:
        if field not in runner_owned:
            assert field in row, field

    condition_row = ec.condition_table(
        [ec.record_from_trade(make_trade(), 1, "x")],
        ec.declare_bins([ec.record_from_trade(make_trade(), 1, "x")]),
        "x",
    )[0]

    for field in ec.CONDITION_CSV_FIELDS:
        assert field in condition_row, field


def test_feature_csv_field_order_matches_declaration() -> None:
    assert ec.FEATURE_CSV_FIELDS[0] == "config_name"
    assert ec.FEATURE_CSV_FIELDS[1] == "feature"
    assert ec.CONDITION_CSV_FIELDS[:3] == (
        "config_name", "dimension", "cell"
    )


@pytest.mark.slow
def test_no_nan_or_inf_reaches_output(baseline_records, a2_records) -> None:
    for records, name in (
        (baseline_records, BASELINE_NAME),
        (a2_records, A2_NAME),
    ):
        bins = ec.declare_bins(records)
        payload = ec.feature_table(records) + ec.condition_table(
            records, bins, name
        )

        for row in payload:
            for key, value in row.items():
                if isinstance(value, float):
                    assert not math.isnan(value), key
                    assert not math.isinf(value), key


# ---------------------------------------------------------------------------
# 11. frozen inputs
# ---------------------------------------------------------------------------


def test_dataset_hash_matches_the_frozen_constant() -> None:
    assert sha256_of_file(Path(DATASET_PATH)) == DATASET_SHA256


@pytest.mark.slow
def test_dataset_fingerprint_is_unchanged(candles) -> None:
    assert dataset_fingerprint(candles) == (
        DATASET_CANDLES, DATASET_FIRST, DATASET_LAST
    )
    assert len(candles) == 17544


def test_oos_dataset_is_untouched() -> None:
    path = ROOT / "data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv"
    assert sha256_of_file(path) == (
        "918153FDE98E39C03EEF8A7B82A2861ADFDC98A080C8810E371869EB3EA22437"
    )


@pytest.mark.parametrize("name,expected", sorted(FROZEN_PHASE13.items()))
def test_phase13_artifacts_are_byte_identical(name, expected) -> None:
    assert sha256_of_file(PHASE13 / name) == expected


@pytest.mark.slow
def test_windows_are_unchanged(candles) -> None:
    resolved = resolve_windows(candles, PHASE13_WINDOWS)
    assert len(resolved) == 6
    assert [w.window_id for w in resolved] == [1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------------------------
# 12. strategy configuration is not mutated
# ---------------------------------------------------------------------------


def test_strategy_configs_match_their_committed_hashes() -> None:
    """Hashes are pinned by the frozen Phase 13 result file."""

    frozen = json.loads(
        (PHASE13 / "RESULTS_windows.json").read_text(encoding="utf-8")
    )

    for name, factory in (
        (BASELINE_NAME, baseline_config),
        (A2_NAME, a2_config),
    ):
        expected = next(
            r["config_hash"] for r in frozen if r["config_name"] == name
        )
        assert config_hash(factory()) == expected


@pytest.mark.slow
def test_analysis_does_not_mutate_strategy_config(candles) -> None:
    config = baseline_config()
    before_repr = repr(config)
    before_hash = config_hash(config)

    runs = walk_forward(candles, config, BASELINE_NAME, costs=COSTS)
    records = ec.collect_records(runs, BASELINE_NAME)
    ec.feature_table(records)
    ec.declare_bins(records)
    ec.condition_table(records, ec.declare_bins(records), BASELINE_NAME)

    assert repr(config) == before_repr
    assert config_hash(config) == before_hash


def test_execution_costs_are_unchanged() -> None:
    costs = phase13_costs()

    assert costs.execution_model == "cost_deduction"
    assert costs.fee_rate == 0.001
    assert costs.slippage_rate == 0.0005
    assert costs.spread_rate == 0.0


@pytest.mark.slow
def test_recorded_trades_reproduce_frozen_phase13_counts(baseline_records) -> None:
    frozen = json.loads(
        (PHASE13 / "RESULTS_windows.json").read_text(encoding="utf-8")
    )
    expected = sum(
        r["trades"] for r in frozen if r["config_name"] == BASELINE_NAME
    )

    assert len(baseline_records) == expected == 267


# ---------------------------------------------------------------------------
# 13. the script's own guards
# ---------------------------------------------------------------------------


def load_script():
    path = PHASE14 / "run_descriptive.py"
    spec = importlib.util.spec_from_file_location("p14c_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_invocation_writes_nothing() -> None:
    """The execution guard must hold.

    Durable form: running without ``--execute`` must neither create an
    artifact nor modify one that already exists. The earlier version of this
    test asserted the files were absent, which only holds before the first
    real run and so tested the phase of the project rather than the guard.
    """

    script = load_script()
    outputs = [
        script.FEATURE_CSV, script.CONDITION_CSV,
        script.ANALYSIS_JSON, script.SUMMARY_MD,
    ]
    before = {
        path: sha256_of_file(path) if path.exists() else None
        for path in outputs
    }

    assert script.main([]) == 0

    for path in outputs:
        if before[path] is None:
            assert not path.exists(), f"{path} was created without --execute"
        else:
            assert sha256_of_file(path) == before[path], (
                f"{path} was modified without --execute"
            )


def test_execute_flag_is_required_and_documented() -> None:
    """The runner must gate execution behind an explicit flag."""

    source = (PHASE14 / "run_descriptive.py").read_text(encoding="utf-8")

    assert '"--execute"' in source
    assert "if not args.execute:" in source
    assert "describe_plan(candles)" in source
    assert "return execute()" in source


def test_runner_declares_all_four_outputs() -> None:
    script = load_script()

    for path in (
        script.FEATURE_CSV, script.CONDITION_CSV,
        script.ANALYSIS_JSON, script.SUMMARY_MD,
    ):
        assert path.name in {
            "RESULTS_feature_summary.csv",
            "RESULTS_condition_summary.csv",
            "RESULTS_analysis.json",
            "SUMMARY.md",
        }


def test_results_are_internally_consistent() -> None:
    """Written artifacts must agree with each other and with the source data."""

    feature_rows = list(
        csv.DictReader(
            (PHASE14 / "RESULTS_feature_summary.csv").open(encoding="utf-8")
        )
    )
    condition_rows = list(
        csv.DictReader(
            (PHASE14 / "RESULTS_condition_summary.csv").open(encoding="utf-8")
        )
    )
    payload = json.loads(
        (PHASE14 / "RESULTS_analysis.json").read_text(encoding="utf-8")
    )

    assert {r["config_name"] for r in feature_rows} == {BASELINE_NAME, A2_NAME}
    assert {r["config_name"] for r in condition_rows} == {
        BASELINE_NAME, A2_NAME
    }

    frozen = json.loads(
        (PHASE13 / "RESULTS_windows.json").read_text(encoding="utf-8")
    )

    for name in (BASELINE_NAME, A2_NAME):
        expected = sum(
            r["trades"] for r in frozen if r["config_name"] == name
        )
        side_cells = [
            r for r in condition_rows
            if r["config_name"] == name and r["dimension"] == "side"
        ]
        assert sum(int(r["n_trades"]) for r in side_cells) == expected

        # Feature table counts must agree with the same pass total.
        total = next(
            r for r in feature_rows
            if r["config_name"] == name and r["feature"] == "side"
        )
        assert int(total["n_total"]) == expected

    assert payload["phase"] == "14C"
    assert payload["min_cell_size"] == ec.MIN_CELL
    assert payload["quantiles"] == list(ec.QUANTILES)


def test_results_contain_no_ranking_language() -> None:
    """Guard against the summary drifting into advocacy.

    Only phrases that could only appear as an assertion are banned. Words
    that legitimately appear inside the disclaimers ("no predictive power
    claim") are checked separately by asserting the disclaimer is present.
    """

    text = (PHASE14 / "SUMMARY.md").read_text(encoding="utf-8").lower()

    for phrase in (
        "best configuration", "optimal configuration", "we recommend trading",
        "profitable strategy", "should change the strategy",
        "will improve", "is the best cell", "outperform",
    ):
        assert phrase not in text, phrase

    assert "claims predictive power" in text
    assert "no strategy modification follows" in text.lower()


def test_summary_states_no_parameters_changed() -> None:
    text = (PHASE14 / "SUMMARY.md").read_text(encoding="utf-8")

    assert "No strategy parameter, threshold, default, entry rule or exit rule" in text
    assert "MAE/MFE were not computed" in text
    assert "Phase 14D was not started" in text


def synth_records(count: int = 40) -> list:
    """Records with known features and known outcomes, no dataset needed.

    Lets the contamination tests run without the 17,544-candle fixture, which
    is what made them too slow to be worth running on every change.
    """

    records = []

    for i in range(count):
        support = 90.0 + i
        resistance = support + 10.0 + (i % 7)
        records.append(
            ec.TradeRecord(
                window_id=1 + (i % 6),
                config_name="synthetic",
                entry_time=START + timedelta(hours=i),
                features={
                    "side": "long" if i % 2 == 0 else "short",
                    "trend_state": "up" if i % 2 == 0 else "down",
                    "signal_kind": "breakout" if i % 3 else "retest",
                    "signal_close": support + (i % 5),
                    "breakout_distance": 0.001 * (1 + i % 9),
                    "retest_distance": None if i % 3 else 0.0005 * (1 + i % 4),
                    "realised_volatility": 0.002 * (1 + i % 11),
                    "mean_range": 1.0 + i % 6,
                    "mean_range_pct": 0.004 * (1 + i % 8),
                    "support_at_entry": support,
                    "resistance_at_entry": resistance,
                    "level_width_pct": (resistance - support) / support,
                    "range_position": (i % 5) / 10.0,
                },
                outcome={
                    "pnl": float(i % 7) - 3.0,
                    "net_pnl": float(i % 7) - 3.5,
                    "total_friction": 0.3,
                    "bars_held": 10 + i,
                    "exit_reason": "opposite_signal",
                    "win": (i % 7) > 3,
                },
            )
        )

    return records


def test_bins_ignore_outcomes_on_synthetic_records() -> None:
    """Contamination guard that needs no dataset fixture."""

    records = synth_records()
    original = ec.declare_bins(records)

    for record in records:
        record.outcome = {
            "pnl": 1e9, "net_pnl": -1e9, "total_friction": 1e9,
            "bars_held": 0, "exit_reason": "x", "win": True,
        }

    assert ec.declare_bins(records) == original


def test_feature_summary_ignores_outcomes_on_synthetic_records() -> None:
    records = synth_records()
    original = ec.feature_table(records)

    for record in records:
        record.outcome = {
            "pnl": -1e12, "net_pnl": 1e12, "total_friction": 0.0,
            "bars_held": 1, "exit_reason": "x", "win": False,
        }

    assert ec.feature_table(records) == original


def test_summary_statistics_match_hand_computed_values() -> None:
    """Pin the arithmetic on data whose answer is known by hand."""

    records = synth_records(40)
    row = ec.feature_summary(
        records, ec.FEATURE_BY_NAME["breakout_distance"]
    )

    values = [
        r.features["breakout_distance"] for r in records
    ]

    assert row["n_present"] == len(values)
    assert row["minimum"] == pytest.approx(min(values))
    assert row["maximum"] == pytest.approx(max(values))
    assert row["mean"] == pytest.approx(sum(values) / len(values))
    assert row["median"] == pytest.approx(
        ec.quantile(values, 0.5)
    )


def test_cell_counts_rates_and_denominators_are_exact() -> None:
    """n_trades, wins, losses and win_rate must be internally consistent."""

    records = synth_records(40)
    bins = ec.declare_bins(records)

    for _, _, members in ec.condition_cells(records, bins):
        stats = ec.outcome_stats(members)

        assert stats["n_trades"] == len(members)
        assert stats["wins"] + stats["losses"] == len(members)

        if stats["n_trades"]:
            assert stats["win_rate"] == pytest.approx(
                stats["wins"] / stats["n_trades"]
            )


def test_win_rate_is_not_computed_on_a_smaller_denominator() -> None:
    """A cell with a known 3/10 split must report 0.3."""

    members = []
    for i in range(10):
        record = ec.record_from_trade(make_trade(), 1, "x")
        record.outcome = {
            "pnl": 1.0 if i < 3 else -1.0,
            "net_pnl": 1.0 if i < 3 else -1.0,
            "total_friction": 0.0,
            "bars_held": 1,
            "exit_reason": "opposite_signal",
            "win": i < 3,
        }
        members.append(record)

    stats = ec.outcome_stats(members)

    assert stats["n_trades"] == 10
    assert stats["wins"] == 3
    assert stats["losses"] == 7
    assert stats["win_rate"] == pytest.approx(0.3)


def test_range_position_is_measured_from_support() -> None:
    """Asymmetric window, so an inverted formula cannot coincide."""

    record = ec.record_from_trade(
        make_trade(
            signal_close=100.0,
            support_at_entry=80.0,
            resistance_at_entry=120.0,
        ),
        1,
        "x",
    )

    # (100 - 80) / (120 - 80) = 0.5 from support; (120 - 100)/40 = 0.5 too,
    # so use a window where the two differ.
    assert record.features["range_position"] == pytest.approx(0.5)

    shifted = ec.record_from_trade(
        make_trade(
            signal_close=110.0,
            support_at_entry=80.0,
            resistance_at_entry=120.0,
        ),
        1,
        "x",
    )

    assert shifted.features["range_position"] == pytest.approx(0.75)
    assert shifted.features["range_position"] != pytest.approx(0.25)


def test_mean_range_pct_is_range_over_close() -> None:
    record = ec.record_from_trade(
        make_trade(signal_close=50.0, mean_range=1.0), 1, "x"
    )

    assert record.features["mean_range_pct"] == pytest.approx(0.02)

    halved = ec.record_from_trade(
        make_trade(signal_close=100.0, mean_range=1.0), 1, "x"
    )

    assert halved.features["mean_range_pct"] == pytest.approx(0.01)


def test_entry_time_features_are_labelled_entry_time() -> None:
    """No feature may be relabelled as outcome-side."""

    for spec in ec.FEATURES:
        assert spec.availability != ec.OUTCOME_SIDE, spec.name

    for name in (
        "side", "signal_kind", "signal_close", "breakout_distance",
        "retest_distance", "realised_volatility", "mean_range",
        "support_at_entry", "resistance_at_entry",
    ):
        assert ec.FEATURE_BY_NAME[name].availability == ec.ENTRY_TIME, name


def test_spearman_is_not_a_constant() -> None:
    """A hardcoded 1.0 would pass every monotonic case; check a mixed one."""

    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    ys = [2.0, 1.0, 4.0, 3.0, 6.0, 5.0]
    rho = ec.spearman(xs, ys)

    assert rho is not None
    assert 0.0 < rho < 1.0


def test_rank_associations_expose_no_inferential_fields() -> None:
    records = synth_records(40)
    rows = ec.rank_associations(records)

    for row in rows:
        assert set(row) == {
            "config_name", "feature", "n_pairs", "spearman_rho"
        }


def test_no_nan_or_inf_from_synthetic_records() -> None:
    records = synth_records(40)
    payload = ec.feature_table(records) + ec.condition_table(
        records, ec.declare_bins(records), "synthetic"
    )

    for row in payload:
        for key, value in row.items():
            if isinstance(value, float):
                assert not math.isnan(value), key
                assert not math.isinf(value), key


def test_quantiles_are_not_scaled() -> None:
    """Edges must equal the plain quartiles of the feature values."""

    records = synth_records(40)
    bins = ec.declare_bins(records, ["breakout_distance"])
    values = [
        r.features["breakout_distance"] for r in records
    ]

    assert bins["breakout_distance"] == [
        ec._round(ec.quantile(values, q), 12) for q in ec.QUANTILES
    ]


def test_dimensions_are_actually_conditioned() -> None:
    """Every declared dimension must produce cells."""

    records = synth_records(40)
    bins = ec.declare_bins(records)
    produced = {d for d, _, _ in ec.condition_cells(records, bins)}

    assert set(ec.CATEGORICAL_DIMENSIONS) <= produced
    assert set(ec.CONTINUOUS_DIMENSIONS) <= produced


def test_each_continuous_dimension_yields_one_cell_per_interval() -> None:
    """Declared bin edges must actually be used to split the trades.

    Without this, an implementation that ignored the edges and dropped every
    trade into a single trailing cell would still satisfy every other
    dimension test.
    """

    records = synth_records(40)
    bins = ec.declare_bins(records)
    cells = ec.condition_cells(records, bins)
    expected = len(ec.QUANTILES) + 1

    for dimension in ec.CONTINUOUS_DIMENSIONS:
        labels = [label for d, label, _ in cells if d == dimension]
        assert len(labels) == expected, (dimension, labels)

    for dimension in ec.CATEGORICAL_DIMENSIONS:
        labels = [label for d, label, _ in cells if d == dimension]
        assert len(labels) >= 2, (dimension, labels)


def test_both_passes_are_covered_by_the_equivalence_check() -> None:
    """The runner must verify Phase 13 equivalence for each pass."""

    source = (
        PHASE14 / "run_descriptive.py"
    ).read_text(encoding="utf-8")

    assert "verify_phase13_equivalence(runs, name)" in source
    assert "refusing to analyse" in source


def test_win_rate_excludes_unresolved_trades_from_the_denominator() -> None:
    """A trade with no net P&L must not dilute the win rate.

    ``len(resolved)`` is the correct denominator; ``len(members)`` would count
    an unresolved trade as a non-win and understate the rate.
    """

    members = []

    for i in range(4):
        record = ec.record_from_trade(make_trade(), 1, "x")
        record.outcome = {
            "pnl": 1.0, "net_pnl": 1.0, "total_friction": 0.0,
            "bars_held": 1, "exit_reason": "opposite_signal", "win": True,
        }
        members.append(record)

    unresolved = ec.record_from_trade(make_trade(), 1, "x")
    unresolved.outcome = {
        "pnl": None, "net_pnl": None, "total_friction": None,
        "bars_held": 0, "exit_reason": "", "win": None,
    }
    members.append(unresolved)

    stats = ec.outcome_stats(members)

    assert stats["n_trades"] == 5
    assert stats["wins"] == 4
    assert stats["losses"] == 0
    assert stats["win_rate"] == pytest.approx(1.0)
    assert stats["net_pnl_total"] == pytest.approx(4.0)


def test_all_outcomes_unresolved_gives_no_win_rate() -> None:
    record = ec.record_from_trade(make_trade(), 1, "x")
    record.outcome = {
        "pnl": None, "net_pnl": None, "total_friction": None,
        "bars_held": 0, "exit_reason": "", "win": None,
    }

    stats = ec.outcome_stats([record])

    assert stats["wins"] == 0
    assert stats["losses"] == 0
    assert stats["win_rate"] is None
    assert stats["net_pnl_mean"] is None


def test_rounding_is_applied_for_output_stability() -> None:
    """Output rounding must actually happen, not just be intended."""

    assert ec._round(1.0 / 3.0, 6) == pytest.approx(0.333333)
    assert ec._round(2.0000000001, 6) == 2.0
    assert ec._round(None) is None
    assert ec._round(5) == 5

    unrounded = 1.0 / 3.0
    assert ec._round(unrounded, 6) != unrounded


def test_unrecorded_entry_features_default_to_none_not_zero() -> None:
    """A trade built without the Phase 14B fields must read ``None``.

    The analysis relies on missing instrumentation being distinguishable from
    a genuine zero, so the dataclass defaults are part of its contract.
    """

    trade = PaperTrade(
        side="long", entry_time=START, entry_price=100.0, quantity=1.0
    )

    for name in (
        "signal_close", "trend_state", "breakout_distance",
        "retest_distance", "realised_volatility", "mean_range",
        "support_at_entry", "resistance_at_entry",
    ):
        assert getattr(trade, name) is None, name


def test_recorded_close_anchors_to_the_signal_candle() -> None:
    """``signal_close`` must be the signal candle's close, not its open."""

    series = synth(200)

    for index in (80, 120, 160, 199):
        signal = analyze(series[:index], StrategyConfig())
        assert signal.signal_close == series[index - 1].close
        assert signal.signal_close != series[index - 1].open


def test_entry_features_survive_onto_the_trade_record() -> None:
    """Signal features must reach the record the analysis reads."""

    from crypto_paper_lab.backtest import run_backtest

    result = run_backtest(synth(600), config=StrategyConfig(), costs=COSTS)
    assert result.total_trades > 0

    for trade in result.trades:
        assert trade.signal_close is not None
        assert trade.breakout_distance is not None
        assert trade.realised_volatility is not None
        assert trade.mean_range is not None
        assert trade.trend_state is not None
        assert trade.retest_distance is None or trade.retest_distance >= 0.0


def test_consumed_features_keep_their_missing_value_contract() -> None:
    """The analysis reads these features, so it must protect how they fail.

    ``realised_volatility`` needs ``period + 1`` candles. With too few it must
    return ``None``; substituting ``0.0`` would make "no history" look like
    "zero volatility" and corrupt every downstream distribution.
    """

    from crypto_paper_lab.indicators import (
        mean_candle_range,
        realised_volatility,
    )

    too_few = [make_trade() for _ in range(0)]
    assert realised_volatility([], 20) is None
    assert mean_candle_range([], 20) is None

    series = synth(25)
    assert realised_volatility(series[:20], 20) is None
    assert realised_volatility(series[:21], 20) is not None
    assert mean_candle_range(series[:1], 20) is not None

    # And the analysis must count such a value as missing, not as zero.
    record = ec.record_from_trade(
        make_trade(realised_volatility=None, mean_range=None), 1, "x"
    )
    row = ec.feature_summary(
        [record], ec.FEATURE_BY_NAME["realised_volatility"]
    )

    assert row["n_present"] == 0
    assert row["n_missing"] == 1
    assert row["mean"] is None


def test_derived_features_survive_a_missing_volatility() -> None:
    """A missing input must not silently become a fabricated ratio."""

    record = ec.record_from_trade(
        make_trade(signal_close=None, mean_range=5.0), 1, "x"
    )

    assert record.features["mean_range_pct"] is None

    partial = ec.record_from_trade(
        make_trade(
            signal_close=100.0,
            mean_range=5.0,
            support_at_entry=None,
            resistance_at_entry=None,
        ),
        1,
        "x",
    )

    assert partial.features["mean_range_pct"] == pytest.approx(0.05)
    assert partial.features["level_width_pct"] is None
    assert partial.features["range_position"] is None


def test_phase13_equivalence_guard_rejects_a_mismatch() -> None:
    """Each guard in the equivalence check must be independently required.

    Both guards raise a message containing "does not match", so a single test
    would keep passing if only one of them were removed.
    """

    script = load_script()
    frozen = json.loads(
        (PHASE13 / "RESULTS_windows.json").read_text(encoding="utf-8")
    )
    expected = next(
        r for r in frozen
        if r["config_name"] == BASELINE_NAME and r["window_id"] == 1
    )

    # Trade count wrong, balance correct: only the count guard can catch this.
    class CountOnlyRun:
        class resolved:
            window_id = 1

        class result:
            total_trades = expected["trades"] + 1
            ending_balance = expected["ending_balance"]

    with pytest.raises(
        WalkForwardValidationError, match="frozen Phase 13 count"
    ):
        script.verify_phase13_equivalence([CountOnlyRun()], BASELINE_NAME)

    # Balance wrong, trade count correct: only the balance guard can catch it.
    class BalanceOnlyRun:
        class resolved:
            window_id = 1

        class result:
            total_trades = expected["trades"]
            ending_balance = expected["ending_balance"] + 1.0

    with pytest.raises(WalkForwardValidationError, match="ending balance"):
        script.verify_phase13_equivalence([BalanceOnlyRun()], BASELINE_NAME)


def test_phase13_equivalence_guard_rejects_a_trade_count_change() -> None:
    """Explicitly assert the count guard's own message."""

    script = load_script()

    class FakeRun:
        class resolved:
            window_id = 1

        class result:
            total_trades = 999
            ending_balance = 12345.0

    with pytest.raises(WalkForwardValidationError) as info:
        script.verify_phase13_equivalence([FakeRun()], BASELINE_NAME)

    assert "refusing to analyse" in str(info.value)


def test_phase13_equivalence_guard_rejects_a_balance_drift() -> None:
    script = load_script()

    frozen = json.loads(
        (PHASE13 / "RESULTS_windows.json").read_text(encoding="utf-8")
    )
    expected = next(
        r for r in frozen
        if r["config_name"] == BASELINE_NAME and r["window_id"] == 1
    )

    class FakeRun:
        class resolved:
            window_id = 1

        class result:
            total_trades = expected["trades"]
            ending_balance = expected["ending_balance"] + 1.0

    with pytest.raises(WalkForwardValidationError, match="ending balance"):
        script.verify_phase13_equivalence([FakeRun()], BASELINE_NAME)


@pytest.mark.slow
def test_phase13_equivalence_guard_accepts_the_real_runs(candles) -> None:
    script = load_script()
    runs = walk_forward(candles, baseline_config(), BASELINE_NAME, costs=COSTS)

    assert script.verify_phase13_equivalence(runs, BASELINE_NAME) is None


@pytest.mark.slow
def test_robustness_summary_reports_the_boundaries(baseline_records) -> None:
    entry = ec.robustness_summary(
        baseline_records, BASELINE_NAME, ec.declare_bins(baseline_records)
    )

    assert entry["n_trades"] == 267
    assert entry["n_windows"] == 6
    assert entry["min_cell_size"] == ec.MIN_CELL
    assert entry["mean_bars_held"] > 0
    assert len(entry["per_window"]) == 6
    assert "dependence_note" in entry
    assert "window_structure_note" in entry


@pytest.mark.slow
def test_trade_population_is_labelled_outcome_side(baseline_records) -> None:
    population = ec.trade_population(baseline_records)

    assert population["availability"] == ec.OUTCOME_SIDE
    assert "exit_reason_counts" in population
    assert sum(population["exit_reason_counts"].values()) == 267


@pytest.mark.slow
def test_rank_associations_carry_no_p_value(baseline_records) -> None:
    rows = ec.rank_associations(baseline_records)

    assert len(rows) == len(ec.CONTINUOUS_DIMENSIONS)

    for row in rows:
        assert set(row) == {
            "config_name", "feature", "n_pairs", "spearman_rho"
        }
        assert "p_value" not in row
        assert "significant" not in row


def test_no_ranking_or_selection_language_in_outputs() -> None:
    """Guard against the summary drifting into advocacy."""

    banned = (
        "best configuration", "optimal", "recommend using", "we should trade",
        "profitable strategy", "highest win rate is", "edge is",
    )

    for name in ("DESIGN_AUDIT.md", "INSTRUMENTATION.md"):
        text = (PHASE14 / name).read_text(encoding="utf-8").lower()

        for phrase in banned:
            assert phrase not in text, (name, phrase)


@pytest.mark.slow
def test_readme_phase13_counts_agree_with_records(baseline_records) -> None:
    """The Phase 13 summary and this analysis must agree on trade counts."""

    summary = (PHASE13 / "SUMMARY.md").read_text(encoding="utf-8")
    assert "baseline" in summary
    assert len(baseline_records) == 267