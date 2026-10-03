"""Tests for the Phase 13 descriptive window statistics.

These cover the frozen metric set from ``experiments/phase13/PLAN.md``. Two
properties are guarded deliberately:

* every metric is **descriptive** -- there must be no threshold, score, ranking
  or selection key, and
* metrics that are not available must be reported as ``None`` rather than
  estimated. ``exposure`` in particular must never appear.
"""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from crypto_paper_lab.models import Candle, PaperTrade
from crypto_paper_lab.stats import closed_net_pnls, median_pnl
from crypto_paper_lab.walkforward import (
    A2_NAME,
    BASELINE_NAME,
    STARTING_BALANCE,
    WalkForwardValidationError,
    WindowSpec,
    a2_config,
    baseline_config,
    phase13_costs,
    resolve_windows,
    run_window,
)
from crypto_paper_lab.windowstats import (
    WindowStats,
    distribution,
    same_sign_runs,
    sign_counts,
    window_stats,
    window_stats_for,
)

START = datetime(2024, 1, 1)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def synthetic_candles(count: int = 3000) -> list[Candle]:
    candles: list[Candle] = []

    for i in range(count):
        base = 100.0 + i * 0.02
        phase = i % 40
        price = (
            base + phase * 0.5 if phase < 20 else base + (40 - phase) * 0.5
        )
        candles.append(
            Candle(
                START + timedelta(hours=i),
                open=price,
                high=price + 0.3,
                low=price - 0.3,
                close=price + 0.1,
                volume=10.0,
            )
        )

    return candles


def trade(
    side: str = "long",
    entry: float = 100.0,
    exit_price: float = 110.0,
    quantity: float = 10.0,
    exit_reason: str = "opposite_signal",
    bars_held: int = 5,
    costs: float = 0.0,
    entry_hour: int = 0,
) -> PaperTrade:
    return PaperTrade(
        side=side,
        entry_time=START + timedelta(hours=entry_hour),
        entry_price=entry,
        quantity=quantity,
        exit_time=START + timedelta(hours=entry_hour + bars_held),
        exit_price=exit_price,
        costs=costs,
        exit_reason=exit_reason,
        bars_held=bars_held,
    )


def completed_run(config_name: str = BASELINE_NAME):
    """Run one synthetic window and return the completed WindowRun."""

    candles = synthetic_candles(3000)
    window = resolve_windows(
        candles,
        (
            WindowSpec(
                1,
                START,
                START + timedelta(hours=899),
                START + timedelta(hours=900),
                START + timedelta(hours=2000),
            ),
        ),
    )[0]
    config = a2_config() if config_name == A2_NAME else baseline_config()

    return run_window(
        candles, window, config, config_name, phase13_costs()
    )


# ---------------------------------------------------------------------------
# median_pnl
# ---------------------------------------------------------------------------


def test_median_pnl_matches_the_hand_computed_middle_value() -> None:
    trades = [
        trade(exit_price=101.0, costs=0.0),
        trade(exit_price=102.0, costs=0.0),
        trade(exit_price=103.0, costs=0.0),
    ]
    # net P&L = (exit - 100) * 10 -> 10, 20, 30
    assert median_pnl(trades) == pytest.approx(20.0)


def test_median_pnl_averages_the_middle_pair_for_even_counts() -> None:
    trades = [
        trade(exit_price=101.0),
        trade(exit_price=102.0),
        trade(exit_price=103.0),
        trade(exit_price=104.0),
    ]
    assert median_pnl(trades) == pytest.approx(25.0)


def test_median_pnl_is_none_when_no_trade_is_closed() -> None:
    assert median_pnl([]) is None

    open_trade = PaperTrade(
        side="long", entry_time=START, entry_price=100.0, quantity=1.0
    )
    assert median_pnl([open_trade]) is None


def test_median_pnl_uses_net_not_gross() -> None:
    """Costs must shift the median, proving net P&L is the input."""

    trades = [
        trade(exit_price=110.0, costs=5.0),
        trade(exit_price=110.0, costs=15.0),
    ]
    # net = 100 - 5 = 95 and 100 - 15 = 85 -> median 90
    assert median_pnl(trades) == pytest.approx(90.0)


def test_closed_net_pnls_preserves_journal_order() -> None:
    trades = [
        trade(exit_price=105.0),
        trade(exit_price=101.0),
        trade(exit_price=103.0),
    ]
    assert closed_net_pnls(trades) == [50.0, 10.0, 30.0]


# ---------------------------------------------------------------------------
# window_stats fields
# ---------------------------------------------------------------------------


def test_window_stats_reports_the_frozen_window_identity() -> None:
    stats = window_stats(completed_run())

    assert stats.window_id == 1
    assert stats.config_name == BASELINE_NAME
    assert stats.train_start == START
    assert stats.eval_start == START + timedelta(hours=900)
    assert stats.eval_end == START + timedelta(hours=2000)
    assert stats.eval_candles == 1101
    assert stats.warmup_candles == 900
    assert stats.train_candles == 900


def test_window_stats_reports_trade_and_outcome_counts() -> None:
    stats = window_stats(completed_run())

    assert stats.trades > 0
    assert stats.win_rate is not None
    assert 0.0 <= stats.win_rate <= 1.0
    assert stats.net_pnl is not None
    assert stats.ending_balance is not None


def test_window_stats_separates_costs_from_spread_and_slippage() -> None:
    stats = window_stats(completed_run())

    assert stats.fee_total > 0
    assert stats.slippage_total > 0
    # cost_deduction forbids a spread.
    assert stats.spread_total == 0.0
    assert stats.total_friction == pytest.approx(
        stats.fee_total + stats.spread_total + stats.slippage_total
    )


def test_window_stats_records_median_and_mean_pnl() -> None:
    stats = window_stats(completed_run())

    assert stats.median_pnl is not None
    assert stats.average_pnl is not None
    assert stats.median_pnl == pytest.approx(
        median_pnl(
            [
                t
                for t in completed_run().result.trades
            ]
        )
    )


def test_window_stats_records_bars_held_statistics() -> None:
    stats = window_stats(completed_run())

    assert stats.bars_held_mean is not None
    assert stats.bars_held_median is not None
    assert stats.bars_held_mean >= stats.bars_held_median


def test_window_stats_records_first_entry_and_last_exit() -> None:
    run = completed_run()
    stats = window_stats(run)

    assert stats.first_entry == min(t.entry_time for t in run.result.trades)
    assert stats.last_exit == max(t.exit_time for t in run.result.trades)
    assert stats.first_entry >= stats.eval_start
    assert stats.last_exit <= stats.eval_end


# ---------------------------------------------------------------------------
# boundary policy accounting
# ---------------------------------------------------------------------------


def test_end_of_data_trades_are_counted_not_discarded() -> None:
    run = completed_run()
    stats = window_stats(run)
    expected = sum(
        1 for t in run.result.trades if t.exit_reason == "end_of_data"
    )

    assert expected >= 1, "a closed window must force-close an open position"
    assert stats.end_of_data_count == expected
    assert stats.boundary_affected_count == expected


def test_boundary_counts_agree_with_the_journal() -> None:
    run = completed_run()
    stats = window_stats(run)

    forced = [t for t in run.result.trades if t.exit_reason == "end_of_data"]

    assert all(t in run.result.trades for t in forced)
    assert stats.trades == len(run.result.trades)
    assert stats.exit_counts == dict(sorted(run.result.exit_counts.items()))


def test_exit_counts_include_the_boundary_reason() -> None:
    stats = window_stats(completed_run())

    assert "end_of_data" in stats.exit_counts
    assert stats.exit_counts["end_of_data"] == stats.end_of_data_count


# ---------------------------------------------------------------------------
# config separation and disclosure
# ---------------------------------------------------------------------------


def test_a2_window_carries_the_selection_disclosure() -> None:
    stats = window_stats(completed_run(A2_NAME))

    assert stats.config_name == A2_NAME
    assert "Phase 7" in stats.selection_disclosure
    assert "NOT clean independent validation" in stats.selection_disclosure


def test_baseline_and_a2_stats_carry_different_config_hashes() -> None:
    base = window_stats(completed_run(BASELINE_NAME))
    a2 = window_stats(completed_run(A2_NAME))

    assert base.config_hash != a2.config_hash
    assert base.costs_hash == a2.costs_hash


# ---------------------------------------------------------------------------
# descriptive-only guarantees
# ---------------------------------------------------------------------------


def test_stats_expose_no_threshold_score_or_ranking_field() -> None:
    """Guard against future contamination of the metric set."""

    forbidden = (
        "threshold", "pass", "fail", "score", "rank", "winner", "best",
        "grade", "verdict", "approve", "reject", "selected", "signal",
    )
    fields = set(WindowStats.__dataclass_fields__)

    for name in fields:
        assert not any(bad in name.lower() for bad in forbidden), name


def test_as_row_omits_the_verbose_reprs_but_keeps_hashes() -> None:
    row = window_stats(completed_run()).as_row()

    assert "config_repr" not in row
    assert "costs_repr" not in row
    assert row["config_hash"]
    assert row["costs_hash"]
    assert row["window_id"] == 1


def test_as_row_flattens_exit_counts_deterministically() -> None:
    row = window_stats(completed_run()).as_row()

    assert isinstance(row["exit_counts"], str)
    assert "=" in row["exit_counts"]


def test_provenance_fields_are_frozen_strings() -> None:
    stats = window_stats(completed_run())

    assert stats.warmup_rule == "full_preceding_series"
    assert stats.boundary_policy == "retain_boundary_force_closes"


def test_exposure_is_not_computed() -> None:
    """Exposure must stay absent rather than be estimated."""

    fields = set(WindowStats.__dataclass_fields__)

    assert not any("exposure" in name for name in fields)
    assert not any("market_time" in name for name in fields)


def test_starting_balance_is_not_mistaken_for_a_return_threshold() -> None:
    stats = window_stats(completed_run())

    assert stats.ending_balance is not None
    assert stats.ending_balance > 0


# ---------------------------------------------------------------------------
# dataset_sha256 provenance (PLAN.md section 13)
#
# Phase 13C audit found this field missing from every result record. These
# tests pin its presence, its value, its serialisation, and the guard that
# stops it disappearing from a future result set.
# ---------------------------------------------------------------------------

EXPECTED_DATASET_SHA256 = (
    "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B"
)


def test_dataset_sha256_field_exists_on_window_stats() -> None:
    assert "dataset_sha256" in WindowStats.__dataclass_fields__


def test_dataset_sha256_equals_the_authoritative_constant() -> None:
    from crypto_paper_lab.walkforward import DATASET_SHA256

    assert DATASET_SHA256 == EXPECTED_DATASET_SHA256

    stats = window_stats(completed_run())

    assert stats.dataset_sha256 == DATASET_SHA256
    assert stats.dataset_sha256 == EXPECTED_DATASET_SHA256


def test_dataset_sha256_defaults_to_empty_not_to_a_guess() -> None:
    """An empty default is what makes silent disappearance detectable."""

    default = WindowStats.__dataclass_fields__["dataset_sha256"].default

    assert default == "", (
        "dataset_sha256 must not default to a plausible-looking value, or a "
        "removed propagation step would go unnoticed"
    )


def test_dataset_sha256_is_present_in_the_csv_row() -> None:
    """The CSV serialiser is exercised through as_row()."""

    row = window_stats(completed_run()).as_row()

    assert "dataset_sha256" in row
    assert row["dataset_sha256"] == EXPECTED_DATASET_SHA256


def test_dataset_sha256_survives_a_real_csv_round_trip(tmp_path) -> None:
    """Write with csv.DictWriter and read back, as the runner does."""

    import csv as csv_module

    row = window_stats(completed_run()).as_row()
    target = tmp_path / "probe.csv"

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv_module.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv_module.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["dataset_sha256"] == EXPECTED_DATASET_SHA256


def test_dataset_sha256_is_present_in_serialised_json() -> None:
    import json as json_module

    payload = json_module.loads(
        json_module.dumps(window_stats(completed_run()).as_row(), default=str)
    )

    assert "dataset_sha256" in payload
    assert payload["dataset_sha256"] == EXPECTED_DATASET_SHA256


def test_dataset_sha256_is_present_on_every_produced_record() -> None:
    """Both configurations, every window."""

    for name in (BASELINE_NAME, A2_NAME):
        stats = window_stats(completed_run(name))
        assert stats.dataset_sha256 == EXPECTED_DATASET_SHA256, name


def test_window_stats_for_refuses_records_without_the_fingerprint(
    monkeypatch,
) -> None:
    """The guard makes disappearance impossible at runtime.

    ``window_stats`` is stubbed to return a record with an empty
    fingerprint, simulating a removed propagation step. ``window_stats_for``
    must reject it rather than emit a record that silently omits required
    provenance.
    """

    import crypto_paper_lab.windowstats as ws

    run = completed_run()
    stripped = replace(window_stats(run), dataset_sha256="")

    monkeypatch.setattr(ws, "window_stats", lambda _run: stripped)

    with pytest.raises(ValueError, match="dataset_sha256"):
        ws.window_stats_for([run])


def test_window_stats_for_returns_records_carrying_the_fingerprint() -> None:
    """The happy path of the same guard."""

    from crypto_paper_lab.windowstats import window_stats_for

    rows = window_stats_for([completed_run()])

    assert len(rows) == 1
    assert rows[0].dataset_sha256 == EXPECTED_DATASET_SHA256


def test_provenance_fields_are_all_present_together() -> None:
    """The fingerprint must sit alongside the other required provenance."""

    row = window_stats(completed_run()).as_row()

    for field in (
        "dataset_sha256",
        "config_hash",
        "costs_hash",
        "warmup_rule",
        "boundary_policy",
        "selection_disclosure",
    ):
        assert field in row, field
        assert row[field] not in (None, ""), field


def test_adding_the_field_did_not_disturb_existing_metrics() -> None:
    """The remediation must be metadata-only."""

    stats = window_stats(completed_run())

    assert stats.trades > 0
    assert stats.net_pnl is not None
    assert stats.ending_balance is not None
    assert stats.total_friction > 0
    assert stats.exit_counts


# ---------------------------------------------------------------------------
# aggregation helpers
# ---------------------------------------------------------------------------


def make_row(window_id: int, net: float) -> WindowStats:
    return WindowStats(
        window_id=window_id,
        config_name=BASELINE_NAME,
        config_repr="x",
        config_hash="h",
        costs_repr="c",
        costs_hash="ch",
        train_start=START,
        train_end=START,
        eval_start=START,
        eval_end=START,
        train_candles=1,
        eval_candles=1,
        warmup_candles=1,
        trades=1,
        end_of_data_count=0,
        boundary_affected_count=0,
        net_pnl=net,
        profit_factor=net,
    )


def test_sign_counts_separates_positive_negative_and_zero() -> None:
    rows = [make_row(1, 5.0), make_row(2, -3.0), make_row(3, 0.0),
            make_row(4, 2.0)]

    assert sign_counts(rows) == {
        "positive": 2,
        "negative": 1,
        "zero": 1,
        "total": 4,
    }


def test_sign_counts_on_an_empty_series() -> None:
    assert sign_counts([]) == {
        "positive": 0, "negative": 0, "zero": 0, "total": 0,
    }


def test_distribution_returns_every_value_sorted() -> None:
    rows = [make_row(i, v) for i, v in
            enumerate([3.0, -1.0, 2.0, -4.0, 5.0], start=1)]

    result = distribution(rows, "net_pnl")

    assert result["count"] == 5
    assert result["sorted"] == [-4.0, -1.0, 2.0, 3.0, 5.0]
    assert result["minimum"] == -4.0
    assert result["maximum"] == 5.0
    assert result["median"] == pytest.approx(2.0)


def test_distribution_never_hides_a_bad_window_behind_a_mean() -> None:
    rows = [make_row(i, v) for i, v in
            enumerate([100.0, 100.0, 100.0, -95.0], start=1)]

    result = distribution(rows, "net_pnl")

    assert result["sorted"][0] == -95.0
    assert result["mean"] > 0, "a positive mean must not conceal the loser"


def test_distribution_handles_missing_values() -> None:
    rows = [make_row(1, 1.0), make_row(2, 0.0)]
    object.__setattr__(rows[1], "net_pnl", None)

    result = distribution(rows, "net_pnl")

    assert result["count"] == 1
    assert result["sorted"] == [1.0]


def test_distribution_on_empty_rows() -> None:
    result = distribution([], "net_pnl")

    assert result["count"] == 0
    assert result["sorted"] == []
    assert result["minimum"] is None


def test_same_sign_runs_finds_the_longest_consecutive_run() -> None:
    rows = [
        make_row(1, 1.0), make_row(2, 2.0), make_row(3, 3.0),
        make_row(4, -1.0), make_row(5, -2.0), make_row(6, 4.0),
    ]

    result = same_sign_runs(rows)

    assert result["longest"] == 3
    assert result["runs"][0] == {"sign": 1, "length": 3}


def test_same_sign_runs_on_empty_rows() -> None:
    assert same_sign_runs([]) == {"longest": 0, "runs": []}


def test_same_sign_runs_treats_zero_as_its_own_sign() -> None:
    rows = [make_row(1, 0.0), make_row(2, 0.0), make_row(3, 1.0)]

    result = same_sign_runs(rows)

    assert result["runs"][0] == {"sign": 0, "length": 2}
    assert result["longest"] == 2


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_window_stats_is_deterministic_across_repeated_runs() -> None:
    first = window_stats(completed_run()).as_row()
    second = window_stats(completed_run()).as_row()

    assert first == second


def test_window_stats_for_preserves_window_order() -> None:
    candles = synthetic_candles(4000)
    windows = (
        WindowSpec(1, START, START + timedelta(hours=899),
                   START + timedelta(hours=900),
                   START + timedelta(hours=1400)),
        WindowSpec(2, START + timedelta(hours=400),
                   START + timedelta(hours=1499),
                   START + timedelta(hours=1500),
                   START + timedelta(hours=2000)),
    )
    resolved = resolve_windows(candles, windows)
    runs = [
        run_window(candles, w, baseline_config(), BASELINE_NAME,
                   phase13_costs())
        for w in resolved
    ]

    stats = window_stats_for(runs)

    assert [s.window_id for s in stats] == [1, 2]
    assert all(s.config_name == BASELINE_NAME for s in stats)
    assert all(s.ending_balance is not None for s in stats)


def test_infinite_profit_factor_is_reported_as_none_not_infinity(
    monkeypatch,
) -> None:
    """A window with no losing trade must stay serialisable.

    ``performance`` returns ``inf`` in that case. The normalisation in
    ``windowstats`` is what keeps the result JSON-writable, so the test forces
    an all-winning window and checks the actual field.
    """

    import crypto_paper_lab.walkforward as wf

    winners = [
        PaperTrade(
            side="long",
            entry_time=START + timedelta(hours=900 + i),
            entry_price=100.0,
            quantity=10.0,
            exit_time=START + timedelta(hours=901 + i),
            exit_price=110.0,
            costs=1.0,
            exit_reason="opposite_signal",
            bars_held=1,
        )
        for i in range(4)
    ]

    from crypto_paper_lab.results import BacktestResult

    fake = BacktestResult(
        trades=winners,
        starting_balance=STARTING_BALANCE,
        ending_balance=STARTING_BALANCE + sum(t.net_pnl for t in winners),
        exit_counts={"opposite_signal": 4},
    )

    monkeypatch.setattr(
        wf, "run_backtest", lambda *a, **k: fake
    )

    stats = window_stats(completed_run())

    assert stats.trades == 4
    assert stats.win_rate == 1.0
    assert stats.profit_factor is None, "inf must be normalised to None"

    row = stats.as_row()
    assert row["profit_factor"] is None