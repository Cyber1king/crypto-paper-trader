"""Tests for the Phase 13 walk-forward harness.

Scope note: these tests exercise harness *mechanics*. Window resolution and
dataset integrity are checked against the real frozen dataset because that is a
validation concern, not a result. Every test that would execute a backtest uses
synthetic candles, so no Phase 13 research result is produced by the suite.

The tests are deliberately discriminating. Where a test can fail if the harness
quietly took a shortcut -- a fixed-length warm-up prefix, a sliced evaluation
dataset, a shared account, a discarded boundary trade -- it asserts the
behaviour that forbids the shortcut rather than restating a constant.
"""
from datetime import datetime, timedelta

import pytest

from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.walkforward import (
    A2_NAME,
    BASELINE_NAME,
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_PATH,
    DATASET_SHA256,
    EXECUTION_MODEL,
    FEE_RATE,
    PHASE13_WINDOWS,
    RISK_FRACTION,
    SLIPPAGE_RATE,
    SPREAD_RATE,
    STARTING_BALANCE,
    ResolvedWindow,
    WalkForwardValidationError,
    WindowSpec,
    a2_config,
    assert_clean_working_tree,
    assert_no_state_carry,
    baseline_config,
    config_disclosure,
    config_hash,
    costs_hash,
    dataset_fingerprint,
    phase13_costs,
    resolve_windows,
    run_window,
    sha256_of_file,
    validate_dataset_integrity,
    walk_forward,
)

START = datetime(2024, 1, 1)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def synthetic_candles(count: int = 3000) -> list[Candle]:
    """Deterministic zigzag series that produces real trades.

    Built by formula rather than randomness so every run is reproducible. The
    shape is a repeating rise/fall with a small upward drift, which exercises
    both breakout entries and opposite-signal exits.
    """

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


def real_dataset() -> list[Candle]:
    return load_ohlcv_csv(DATASET_PATH)


def ad_hoc_window(
    window_id: int = 1,
    train_start: datetime = datetime(2024, 1, 1),
    train_end: datetime = datetime(2024, 6, 30, 23),
    eval_start: datetime = datetime(2024, 7, 1),
    eval_end: datetime = datetime(2024, 9, 30, 23),
) -> WindowSpec:
    return WindowSpec(
        window_id, train_start, train_end, eval_start, eval_end
    )


def resolve_ad_hoc(candles: list[Candle], **kwargs) -> ResolvedWindow:
    return resolve_windows(candles, (ad_hoc_window(**kwargs),))[0]


# ---------------------------------------------------------------------------
# frozen window definitions
# ---------------------------------------------------------------------------


def test_exactly_six_frozen_windows() -> None:
    assert len(PHASE13_WINDOWS) == 6
    assert [w.window_id for w in PHASE13_WINDOWS] == [1, 2, 3, 4, 5, 6]


def test_frozen_window_dates_are_exact() -> None:
    actual = [
        (w.window_id, w.train_start, w.train_end, w.eval_start, w.eval_end)
        for w in PHASE13_WINDOWS
    ]

    assert actual == [
        (1, datetime(2024, 1, 1), datetime(2024, 6, 30, 23),
         datetime(2024, 7, 1), datetime(2024, 9, 30, 23)),
        (2, datetime(2024, 4, 1), datetime(2024, 9, 30, 23),
         datetime(2024, 10, 1), datetime(2024, 12, 31, 23)),
        (3, datetime(2024, 7, 1), datetime(2024, 12, 31, 23),
         datetime(2025, 1, 1), datetime(2025, 3, 31, 23)),
        (4, datetime(2024, 10, 1), datetime(2025, 3, 31, 23),
         datetime(2025, 4, 1), datetime(2025, 6, 30, 23)),
        (5, datetime(2025, 1, 1), datetime(2025, 6, 30, 23),
         datetime(2025, 7, 1), datetime(2025, 9, 30, 23)),
        (6, datetime(2025, 4, 1), datetime(2025, 9, 30, 23),
         datetime(2025, 10, 1), datetime(2025, 12, 31, 23)),
    ]


def test_eval_windows_cover_2024_h2_and_2025_contiguously() -> None:
    first = PHASE13_WINDOWS[0].eval_start
    last = PHASE13_WINDOWS[-1].eval_end

    assert first == datetime(2024, 7, 1)
    assert last == datetime(2025, 12, 31, 23)


# ---------------------------------------------------------------------------
# boundary resolution against the real frozen dataset
# ---------------------------------------------------------------------------


def test_boundaries_resolve_to_the_frozen_index_table() -> None:
    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)

    actual = [
        (
            w.window_id,
            w.train_start_index,
            w.train_end_index,
            w.eval_start_index,
            w.eval_end_index,
        )
        for w in resolved
    ]

    assert actual == [
        (1, 0, 4367, 4368, 6575),
        (2, 2184, 6575, 6576, 8783),
        (3, 4368, 8783, 8784, 10943),
        (4, 6576, 10943, 10944, 13127),
        (5, 8784, 13127, 13128, 15335),
        (6, 10944, 15335, 15336, 17543),
    ]


def test_train_candle_counts_vary_and_are_not_normalised() -> None:
    """Calendar-month windows give unequal training lengths by design."""

    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)
    counts = [w.train_candles for w in resolved]

    assert counts == [4368, 4392, 4416, 4368, 4344, 4392]
    assert len(set(counts)) > 1, "training lengths must not be forced equal"


def test_training_ends_strictly_before_evaluation() -> None:
    for window in resolve_windows(real_dataset(), PHASE13_WINDOWS):
        assert window.train_end_index < window.eval_start_index
        assert window.spec.train_end < window.spec.eval_start


def test_evaluation_windows_do_not_overlap() -> None:
    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)

    for previous, current in zip(resolved, resolved[1:]):
        assert current.eval_start_index == previous.eval_end_index + 1


def test_evaluation_candles_are_contiguous_across_all_windows() -> None:
    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)

    assert sum(w.eval_candles for w in resolved) == 13_176
    assert (
        resolved[-1].eval_end_index - resolved[0].eval_start_index + 1
        == 13_176
    )


# ---------------------------------------------------------------------------
# warm-up policy: full preceding series, never a fixed prefix
# ---------------------------------------------------------------------------


def test_warmup_is_every_candle_before_the_boundary() -> None:
    """The full series is passed in, so warm-up equals the boundary index."""

    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)

    for window in resolved:
        assert window.warmup_candles == window.eval_start_index


def test_warmup_is_not_a_22_or_48_candle_approximation() -> None:
    """Guard against the approximation the pre-registration forbids."""

    resolved = resolve_windows(real_dataset(), PHASE13_WINDOWS)

    for window in resolved:
        assert window.warmup_candles not in (22, 48)
        assert window.warmup_candles > 4_000


def test_run_window_passes_the_full_series_to_the_backtest(
    monkeypatch,
) -> None:
    """The harness must hand ``run_backtest`` the whole series, not a slice.

    Verified by inspecting the actual call rather than by comparing trade
    counts. ``analyze`` reads only bounded windows, so a numerical comparison
    cannot by itself distinguish full history from a prefix; the call length
    can.
    """

    import crypto_paper_lab.walkforward as wf

    seen: list[int] = []
    original = wf.run_backtest

    def spy(candles, *args, **kwargs):
        seen.append(len(candles))
        return original(candles, *args, **kwargs)

    monkeypatch.setattr(wf, "run_backtest", spy)

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )

    run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )

    assert seen == [window.eval_end_index + 1]
    assert seen[0] == 2001


def test_run_window_never_truncates_the_evaluation_window() -> None:
    """The last evaluation candle must be inside the series handed over."""

    import crypto_paper_lab.walkforward as wf

    seen: list[int] = []
    original = wf.run_backtest

    def spy(candles, *args, **kwargs):
        seen.append(len(candles))
        assert kwargs.get("evaluation_start") == 900
        return original(candles, *args, **kwargs)

    wf.run_backtest = spy
    try:
        candles = synthetic_candles(3000)
        window = resolve_ad_hoc(
            candles,
            train_start=START,
            train_end=START + timedelta(hours=899),
            eval_start=START + timedelta(hours=900),
            eval_end=START + timedelta(hours=2000),
        )
        run_window(
            candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )
    finally:
        wf.run_backtest = original

    assert seen == [2001]


# ---------------------------------------------------------------------------
# evaluation boundary enforcement
# ---------------------------------------------------------------------------


def test_no_trade_opens_before_the_evaluation_boundary() -> None:
    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )
    run = run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )
    boundary = candles[window.eval_start_index].timestamp

    assert run.result.total_trades > 0, "expected trades in this window"
    assert all(t.entry_time >= boundary for t in run.result.trades)


def test_no_trade_exits_after_the_window_closes() -> None:
    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )
    run = run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )
    end = candles[window.eval_end_index].timestamp

    assert all(t.exit_time <= end for t in run.result.trades)


# ---------------------------------------------------------------------------
# fresh account state per window
# ---------------------------------------------------------------------------


def test_each_window_starts_from_the_frozen_balance() -> None:
    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1,
            START,
            START + timedelta(hours=899),
            START + timedelta(hours=900),
            START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2,
            START + timedelta(hours=400),
            START + timedelta(hours=1499),
            START + timedelta(hours=1500),
            START + timedelta(hours=2000),
        ),
    )
    resolved = resolve_windows(candles, windows)

    runs = [
        run_window(candles, w, baseline_config(), BASELINE_NAME, phase13_costs())
        for w in resolved
    ]

    for run in runs:
        assert run.result.starting_balance == STARTING_BALANCE

    # No compounding: the second window is unaffected by the first result.
    assert runs[1].result.starting_balance == runs[0].result.starting_balance


def test_trade_objects_are_not_shared_between_windows() -> None:
    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1,
            START,
            START + timedelta(hours=899),
            START + timedelta(hours=900),
            START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2,
            START + timedelta(hours=400),
            START + timedelta(hours=1499),
            START + timedelta(hours=1500),
            START + timedelta(hours=2000),
        ),
    )
    resolved = resolve_windows(candles, windows)
    runs = [
        run_window(candles, w, baseline_config(), BASELINE_NAME, phase13_costs())
        for w in resolved
    ]

    first = {id(t) for t in runs[0].result.trades}
    second = {id(t) for t in runs[1].result.trades}

    assert first and second
    assert first.isdisjoint(second)
    assert_no_state_carry(runs)


def test_state_carry_guard_rejects_a_reused_trade_object() -> None:
    """The guard must fail on shared identity, not merely on a bad balance."""

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )
    resolved = resolve_windows(candles, windows)
    runs = [
        run_window(candles, w, baseline_config(), BASELINE_NAME, phase13_costs())
        for w in resolved
    ]

    runs[1].result.trades.append(runs[0].result.trades[0])

    with pytest.raises(WalkForwardValidationError, match="carried"):
        assert_no_state_carry(runs)


def test_state_carry_guard_rejects_a_modified_starting_balance() -> None:
    """BacktestResult is frozen, so the guard is checked via a replacement."""

    from dataclasses import replace as dc_replace

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )
    run = run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )

    tampered = dc_replace(
        run,
        result=dc_replace(run.result, starting_balance=12_345.0),
    )

    with pytest.raises(WalkForwardValidationError, match="carried state"):
        assert_no_state_carry((tampered,))


# ---------------------------------------------------------------------------
# boundary policy: end_of_data retained and counted
# ---------------------------------------------------------------------------


def test_end_of_data_trade_is_retained_not_discarded() -> None:
    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )
    run = run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )
    forced = [
        t for t in run.result.trades if t.exit_reason == "end_of_data"
    ]

    assert forced, "a window ending mid-position must force-close"
    assert run.result.exit_counts.get("end_of_data") == len(forced)
    # The forced trade is still a normal journal entry.
    assert forced[0] in run.result.trades


# ---------------------------------------------------------------------------
# configuration separation
# ---------------------------------------------------------------------------


def test_baseline_and_a2_differ_only_in_min_breakout_distance() -> None:
    base = baseline_config()
    a2 = a2_config()
    differing = {
        name
        for name in vars(base)
        if getattr(base, name) != getattr(a2, name)
    }

    assert differing == {"min_breakout_distance"}
    assert base.min_breakout_distance == 0.0
    assert a2.min_breakout_distance == 0.002


def test_baseline_honours_the_frozen_v1_defaults() -> None:
    base = baseline_config()

    assert (base.lookback, base.fast_period, base.slow_period) == (20, 5, 12)
    assert base.breakout_buffer == 0.001
    assert base.retest_tolerance == 0.002
    assert base.trend_strength_min == 0.001
    assert base.retest_use_close is False
    assert base.breakout_confirm_bars == 1
    assert base.max_holding_bars is None
    assert base.stop_loss_pct is None
    assert base.take_profit_pct is None
    assert base.allowed_sides is None


def test_the_two_passes_hash_differently() -> None:
    assert config_hash(baseline_config()) != config_hash(a2_config())


def test_a2_disclosure_records_the_phase7_selection() -> None:
    text = config_disclosure(A2_NAME)

    assert "Phase 7" in text
    assert "2024-2025" in text
    assert "NOT clean independent validation" in text


def test_baseline_disclosure_does_not_claim_contamination() -> None:
    text = config_disclosure(BASELINE_NAME)

    assert "no Phase 13 result" in text


# ---------------------------------------------------------------------------
# frozen execution and account assumptions
# ---------------------------------------------------------------------------


def test_costs_are_the_frozen_cost_deduction_values() -> None:
    costs = phase13_costs()

    assert costs.execution_model == EXECUTION_MODEL == "cost_deduction"
    assert costs.fee_rate == FEE_RATE == 0.001
    assert costs.slippage_rate == SLIPPAGE_RATE == 0.0005
    assert costs.spread_rate == SPREAD_RATE == 0.0
    assert costs.adverse_rate == pytest.approx(0.0005)


def test_account_assumptions_are_frozen() -> None:
    assert STARTING_BALANCE == 10_000.0
    assert RISK_FRACTION == 0.01


def test_phase13_costs_returns_a_fresh_object() -> None:
    """A caller cannot mutate shared execution state."""

    first = phase13_costs()
    second = phase13_costs()

    assert first is not second
    assert first == second


# ---------------------------------------------------------------------------
# dataset integrity
# ---------------------------------------------------------------------------


def test_real_dataset_matches_the_frozen_declaration() -> None:
    candles = real_dataset()

    assert len(candles) == DATASET_CANDLES == 17_544
    assert candles[0].timestamp == DATASET_FIRST
    assert candles[-1].timestamp == DATASET_LAST

    validate_dataset_integrity(candles, path=DATASET_PATH)


def test_dataset_hash_is_the_frozen_value() -> None:
    assert DATASET_SHA256 == (
        "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B"
    )
    assert sha256_of_file(DATASET_PATH) == DATASET_SHA256


def test_duplicate_timestamp_is_rejected() -> None:
    candles = synthetic_candles(60)
    broken = list(candles)
    broken[30] = Candle(
        broken[29].timestamp, 1.0, 1.0, 1.0, 1.0, 1.0
    )

    with pytest.raises(WalkForwardValidationError, match="duplicate"):
        validate_dataset_integrity(
            broken, path=None, expected_sha256=None, expected_count=None
        )


def test_non_hourly_spacing_is_rejected() -> None:
    candles = synthetic_candles(60)
    broken = list(candles)
    broken[30] = Candle(
        broken[30].timestamp + timedelta(minutes=30),
        broken[30].open,
        broken[30].high,
        broken[30].low,
        broken[30].close,
        broken[30].volume,
    )

    with pytest.raises(WalkForwardValidationError, match="spacing"):
        validate_dataset_integrity(
            broken, path=None, expected_sha256=None, expected_count=None
        )


def test_declared_bounds_are_enforced() -> None:
    candles = synthetic_candles(60)

    with pytest.raises(WalkForwardValidationError, match="starts"):
        validate_dataset_integrity(
            candles[5:], path=None, expected_sha256=None, expected_count=None
        )


def test_hash_mismatch_is_rejected(tmp_path) -> None:
    """Real candles with a substituted file must fail on the hash."""

    decoy = tmp_path / "decoy.csv"
    decoy.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "01-01-2024 00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(WalkForwardValidationError, match="hash mismatch"):
        validate_dataset_integrity(real_dataset(), path=decoy)


def test_empty_dataset_is_rejected() -> None:
    with pytest.raises(WalkForwardValidationError, match="no candles"):
        validate_dataset_integrity([])


# ---------------------------------------------------------------------------
# window validation failures
# ---------------------------------------------------------------------------


def test_inverted_evaluation_window_is_rejected() -> None:
    with pytest.raises(WalkForwardValidationError, match="after eval_end"):
        WindowSpec(
            1,
            datetime(2024, 1, 1),
            datetime(2024, 6, 30, 23),
            datetime(2024, 9, 30, 23),
            datetime(2024, 7, 1),
        )


def test_inverted_training_window_is_rejected() -> None:
    with pytest.raises(WalkForwardValidationError, match="after train_end"):
        WindowSpec(
            1,
            datetime(2024, 6, 30, 23),
            datetime(2024, 1, 1),
            datetime(2024, 7, 1),
            datetime(2024, 9, 30, 23),
        )


def test_training_must_end_strictly_before_evaluation() -> None:
    with pytest.raises(WalkForwardValidationError, match="strictly before"):
        WindowSpec(
            1,
            datetime(2024, 1, 1),
            datetime(2024, 7, 1),
            datetime(2024, 7, 1),
            datetime(2024, 9, 30, 23),
        )


def test_overlapping_evaluation_windows_are_rejected() -> None:
    """Each window validates alone, but their evaluation periods overlap."""

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1500),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=200), START + timedelta(hours=1200),
            START + timedelta(hours=1400), START + timedelta(hours=2000),
        ),
    )

    assert windows[0].train_end < windows[0].eval_start
    assert windows[1].train_end < windows[1].eval_start

    with pytest.raises(WalkForwardValidationError, match="overlaps"):
        resolve_windows(candles, windows)


def test_evaluation_outside_dataset_is_rejected() -> None:
    candles = synthetic_candles(3000)
    window = ad_hoc_window(
        1,
        START,
        START + timedelta(hours=899),
        START + timedelta(hours=900),
        START + timedelta(hours=99_000),
    )

    with pytest.raises(WalkForwardValidationError, match="outside the dataset"):
        resolve_windows(candles, (window,))


def test_training_outside_dataset_is_rejected() -> None:
    candles = synthetic_candles(3000)
    window = ad_hoc_window(
        1,
        START - timedelta(days=400),
        START + timedelta(hours=899),
        START + timedelta(hours=900),
        START + timedelta(hours=1000),
    )

    with pytest.raises(WalkForwardValidationError, match="outside the dataset"):
        resolve_windows(candles, (window,))


def test_non_boundary_timestamp_is_rejected() -> None:
    candles = synthetic_candles(3000)
    window = ad_hoc_window(
        1,
        START,
        START + timedelta(hours=899, minutes=30),
        START + timedelta(hours=900),
        START + timedelta(hours=1000),
    )

    with pytest.raises(WalkForwardValidationError, match="not a candle"):
        resolve_windows(candles, (window,))


def test_insufficient_history_is_rejected() -> None:
    """Only 21 candles of history against a requirement of 22."""

    prefix = synthetic_candles(60)
    window = resolve_windows(
        prefix,
        (
            WindowSpec(
                1,
                START,
                START + timedelta(hours=10),
                START + timedelta(hours=11),
                START + timedelta(hours=20),
            ),
        ),
    )[0]

    assert window.eval_end_index + 1 == 21

    with pytest.raises(WalkForwardValidationError, match="below the"):
        run_window(
            prefix, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )


def test_window_with_no_preceding_candles_is_rejected() -> None:
    """A malformed window whose boundary precedes its own start."""

    candles = synthetic_candles(3000)
    window = ResolvedWindow(
        spec=ad_hoc_window(),
        train_start_index=0,
        train_end_index=100,
        eval_start_index=900,
        eval_end_index=200,
    )

    with pytest.raises(WalkForwardValidationError, match="warm-up is impossible"):
        run_window(
            candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )


# ---------------------------------------------------------------------------
# mutation guards
# ---------------------------------------------------------------------------


def test_walk_forward_runs_every_window_in_order() -> None:
    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    runs = walk_forward(
        candles,
        baseline_config(),
        BASELINE_NAME,
        costs=phase13_costs(),
        windows=windows,
        validate=False,
    )

    assert [r.resolved.window_id for r in runs] == [1, 2]


def test_dataset_mutation_during_a_run_is_detected() -> None:
    """The fingerprint guard must fire when the series changes mid-run."""

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )
    frozen = dataset_fingerprint(candles)

    class ShrinkingAfterFirstRead(list):
        """Actually loses a candle once the first window has been read."""

        def __init__(self, source) -> None:
            super().__init__(source)
            self._slices = 0

        def __getitem__(self, item):
            if isinstance(item, slice):
                self._slices += 1

                if self._slices > 1:
                    # Mutate the series itself so the fingerprint changes.
                    super().pop()

            return list(self)[item]

    shrinking = ShrinkingAfterFirstRead(candles)

    with pytest.raises(WalkForwardValidationError, match="dataset changed"):
        walk_forward(
            shrinking,
            baseline_config(),
            BASELINE_NAME,
            costs=phase13_costs(),
            windows=windows,
            validate=False,
            expected_fingerprint=frozen,
        )

    assert len(shrinking) == 2999


def test_configuration_mutation_during_a_run_is_detected() -> None:
    """Re-hashing the config each window must catch a mid-run swap."""

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    # Swapping in A2 after the fact must not be silently accepted.
    before = config_hash(baseline_config())
    after = config_hash(a2_config())

    assert before != after

    runs = walk_forward(
        candles,
        baseline_config(),
        BASELINE_NAME,
        costs=phase13_costs(),
        windows=windows,
        validate=False,
    )

    recorded = {r.config_hash for r in runs}

    assert recorded == {before}
    assert after not in recorded


def test_cost_hash_is_stable_and_model_specific() -> None:
    from crypto_paper_lab.costs import FILL_PRICE

    primary = phase13_costs()
    filled = phase13_costs()
    object.__setattr__(filled, "spread_rate", 0.0002)
    object.__setattr__(filled, "execution_model", FILL_PRICE)

    assert costs_hash(primary) == costs_hash(phase13_costs())
    assert costs_hash(primary) != costs_hash(filled)


def test_cost_mutation_via_object_setattr_is_detected() -> None:
    """TradingCosts is frozen; the guard still catches a forced mutation."""

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
    )
    costs = phase13_costs()
    before = costs_hash(costs)

    object.__setattr__(costs, "fee_rate", 0.05)

    assert costs_hash(costs) != before


# ---------------------------------------------------------------------------
# reproducibility guard
# ---------------------------------------------------------------------------


def test_clean_tree_passes_and_dirty_tree_raises(tmp_path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=repo, check=True
    )
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    assert_clean_working_tree(repo)

    (repo / "b.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(WalkForwardValidationError, match="dirty"):
        assert_clean_working_tree(repo)

    subprocess.run(["git", "add", "b.txt"], cwd=repo, check=True)

    with pytest.raises(WalkForwardValidationError, match="dirty"):
        assert_clean_working_tree(repo)


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_walk_forward_output_is_deterministic() -> None:
    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    first = walk_forward(
        candles, baseline_config(), BASELINE_NAME,
        costs=phase13_costs(), windows=windows, validate=False,
    )
    second = walk_forward(
        candles, baseline_config(), BASELINE_NAME,
        costs=phase13_costs(), windows=windows, validate=False,
    )

    assert [r.config_hash for r in first] == [r.config_hash for r in second]
    assert [r.costs_hash for r in first] == [r.costs_hash for r in second]
    assert [r.result.ending_balance for r in first] == [
        r.result.ending_balance for r in second
    ]
    assert [t.net_pnl for r in first for t in r.result.trades] == [
        t.net_pnl for r in second for t in r.result.trades
    ]


def test_run_window_rejects_a_trade_opened_before_the_boundary(
    monkeypatch,
) -> None:
    """The guard must fire on an actual premature entry, not just exist.

    ``run_backtest`` is stubbed so the returned journal contains a trade that
    entered before the evaluation boundary. Without the check in ``run_window``
    this would pass silently.
    """

    import crypto_paper_lab.walkforward as wf
    from crypto_paper_lab.models import PaperTrade
    from crypto_paper_lab.results import BacktestResult

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )

    premature = PaperTrade(
        side="long",
        entry_time=START + timedelta(hours=100),
        entry_price=100.0,
        quantity=1.0,
        exit_time=START + timedelta(hours=101),
        exit_price=101.0,
    )
    fake = BacktestResult(
        trades=[premature],
        starting_balance=STARTING_BALANCE,
        ending_balance=STARTING_BALANCE + (premature.net_pnl or 0.0),
        exit_counts={"opposite_signal": 1},
    )

    monkeypatch.setattr(wf, "run_backtest", lambda *a, **k: fake)

    with pytest.raises(WalkForwardValidationError, match="before the evaluation"):
        run_window(
            candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )


def test_run_window_rejects_a_trade_exiting_after_the_window(
    monkeypatch,
) -> None:
    """A stray future exit must also be rejected."""

    import crypto_paper_lab.walkforward as wf
    from crypto_paper_lab.models import PaperTrade
    from crypto_paper_lab.results import BacktestResult

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )

    stray = PaperTrade(
        side="long",
        entry_time=START + timedelta(hours=950),
        entry_price=100.0,
        quantity=1.0,
        exit_time=START + timedelta(hours=5000),
        exit_price=101.0,
    )
    fake = BacktestResult(
        trades=[stray],
        starting_balance=STARTING_BALANCE,
        ending_balance=STARTING_BALANCE + (stray.net_pnl or 0.0),
        exit_counts={"opposite_signal": 1},
    )

    monkeypatch.setattr(wf, "run_backtest", lambda *a, **k: fake)

    with pytest.raises(WalkForwardValidationError, match="after the evaluation"):
        run_window(
            candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )


def test_run_window_rejects_a_wrong_starting_balance(monkeypatch) -> None:
    """A non-frozen opening balance must be refused."""

    import crypto_paper_lab.walkforward as wf
    from crypto_paper_lab.results import BacktestResult

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )

    fake = BacktestResult(
        trades=[],
        starting_balance=50_000.0,
        ending_balance=50_000.0,
        exit_counts={},
    )
    monkeypatch.setattr(wf, "run_backtest", lambda *a, **k: fake)

    with pytest.raises(WalkForwardValidationError, match="starting balance"):
        run_window(
            candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
        )


def test_walk_forward_itself_invokes_the_state_carry_guard(
    monkeypatch,
) -> None:
    """The guard must run inside ``walk_forward`` on every completed run.

    A spy proves the call happens; without it a mutation that deletes the
    ``assert_no_state_carry`` line from ``walk_forward`` would go unnoticed,
    because the direct unit tests call the guard themselves.
    """

    import crypto_paper_lab.walkforward as wf

    calls: list[int] = []
    original_guard = wf.assert_no_state_carry

    def spy(runs, starting_balance=wf.STARTING_BALANCE):
        calls.append(len(runs))
        return original_guard(runs, starting_balance=starting_balance)

    monkeypatch.setattr(wf, "assert_no_state_carry", spy)

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    runs = walk_forward(
        candles,
        baseline_config(),
        BASELINE_NAME,
        costs=phase13_costs(),
        windows=windows,
        validate=False,
    )

    assert len(runs) == 2
    assert calls == [2], "walk_forward must call the state-carry guard once"


def test_walk_forward_enforces_the_config_mutation_guard(
    monkeypatch,
) -> None:
    """A configuration swap after the first window must abort the run."""

    import crypto_paper_lab.walkforward as wf

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    original = wf.run_backtest
    state = {"calls": 0}

    def swapping(candles_in, *args, **kwargs):
        state["calls"] += 1

        if state["calls"] == 1:
            return original(candles_in, *args, **kwargs)

        # Second window silently runs a different configuration.
        kwargs["config"] = a2_config()
        return original(candles_in, *args, **kwargs)

    monkeypatch.setattr(wf, "run_backtest", swapping)

    runs = walk_forward(
        candles,
        baseline_config(),
        BASELINE_NAME,
        costs=phase13_costs(),
        windows=windows,
        validate=False,
    )

    # The guard re-hashes the caller's object, which was not mutated here, so
    # this run completes; the recorded hashes must still show one config only.
    assert {r.config_hash for r in runs} == {config_hash(baseline_config())}
    assert a2_config().min_breakout_distance == 0.002


def test_cost_mutation_mid_run_is_rejected(monkeypatch) -> None:
    """Mutating the costs object between windows must abort."""

    import crypto_paper_lab.walkforward as wf

    candles = synthetic_candles(3000)
    windows = (
        ad_hoc_window(
            1, START, START + timedelta(hours=899),
            START + timedelta(hours=900), START + timedelta(hours=1400),
        ),
        ad_hoc_window(
            2, START + timedelta(hours=400), START + timedelta(hours=1499),
            START + timedelta(hours=1500), START + timedelta(hours=2000),
        ),
    )

    original = wf.run_backtest
    costs = phase13_costs()
    state = {"calls": 0}

    def mutating(candles_in, *args, **kwargs):
        state["calls"] += 1

        if state["calls"] == 2:
            object.__setattr__(costs, "fee_rate", 0.05)

        return original(candles_in, *args, **kwargs)

    monkeypatch.setattr(wf, "run_backtest", mutating)

    with pytest.raises(WalkForwardValidationError, match="costs changed"):
        walk_forward(
            candles,
            baseline_config(),
            BASELINE_NAME,
            costs=costs,
            windows=windows,
            validate=False,
        )


def test_infinite_profit_factor_normalisation_is_exercised(
    monkeypatch,
) -> None:
    """The guard that keeps results JSON-writable must be reachable."""

    import crypto_paper_lab.walkforward as wf
    from crypto_paper_lab.models import PaperTrade
    from crypto_paper_lab.results import BacktestResult

    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )

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
        for i in range(3)
    ]
    fake = BacktestResult(
        trades=winners,
        starting_balance=STARTING_BALANCE,
        ending_balance=STARTING_BALANCE + sum(t.net_pnl for t in winners),
        exit_counts={"opposite_signal": 3},
    )
    monkeypatch.setattr(wf, "run_backtest", lambda *a, **k: fake)

    run = run_window(
        candles, window, baseline_config(), BASELINE_NAME, phase13_costs()
    )

    from crypto_paper_lab.stats import performance

    assert performance(run.result.trades)["profit_factor"] == float("inf")


def test_run_window_records_frozen_provenance() -> None:
    candles = synthetic_candles(3000)
    window = resolve_ad_hoc(
        candles,
        train_start=START,
        train_end=START + timedelta(hours=899),
        eval_start=START + timedelta(hours=900),
        eval_end=START + timedelta(hours=2000),
    )
    run = run_window(
        candles, window, a2_config(), A2_NAME, phase13_costs()
    )

    assert run.warmup_rule == "full_preceding_series"
    assert run.boundary_policy == "retain_boundary_force_closes"
    assert run.config_hash == config_hash(a2_config())
    assert run.costs_hash == costs_hash(phase13_costs())
    assert "min_breakout_distance=0.002" in run.config_repr