"""Phase 13 walk-forward window definitions, validation and execution.

This module implements the frozen Phase 13 design recorded in
``experiments/phase13/PLAN.md``. It provides:

* the six frozen windows,
* the two pre-registered configurations,
* the frozen execution and account assumptions,
* validation that rejects malformed or contaminated setups,
* single-window and full walk-forward execution.

Design rules enforced here, all taken directly from the pre-registration:

* The backtest always receives the **full candle history** from the start of
  the dataset through the end of the evaluation window, with
  ``evaluation_start`` set at the evaluation boundary. The series is never
  sliced to the evaluation period and no fixed-length warm-up prefix is used,
  because any fixed prefix is an approximation of indicator state.
* Every window gets a **fresh** account via ``run_backtest``; no position,
  cash or indicator state is carried between windows.
* Boundary force-closes (``exit_reason == "end_of_data"``) are **kept** and
  counted, never discarded.
* Nothing here ranks configurations, selects a winner, applies a threshold or
  otherwise scores a result. All outputs are descriptive.
* ``yearly.py`` is never used: it resets warm-up per calendar year and
  force-closes at year boundaries, which is not walk-forward.
"""
from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from .backtest import run_backtest
from .costs import COST_DEDUCTION, TradingCosts
from .models import Candle
from .results import BacktestResult
from .strategy import StrategyConfig

# ---------------------------------------------------------------------------
# Frozen dataset
# ---------------------------------------------------------------------------

#: Repository-relative path of the primary Phase 13 dataset.
DATASET_PATH = "data/BTCUSDT_1h_Cleaned (1).csv"

#: SHA-256 frozen in the pre-registration.
DATASET_SHA256 = (
    "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B"
)

DATASET_FIRST = datetime(2024, 1, 1, 0, 0)
DATASET_LAST = datetime(2025, 12, 31, 23, 0)
DATASET_CANDLES = 17_544

#: Candle spacing the dataset must exhibit.
EXPECTED_INTERVAL_SECONDS = 3600

# ---------------------------------------------------------------------------
# Frozen execution and account assumptions
# ---------------------------------------------------------------------------

EXECUTION_MODEL = COST_DEDUCTION
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
SPREAD_RATE = 0.0

STARTING_BALANCE = 10_000.0
RISK_FRACTION = 0.01

#: Warm-up rule identifier recorded with every run.
WARMUP_RULE = "full_preceding_series"

#: Boundary policy identifier recorded with every run.
BOUNDARY_POLICY = "retain_boundary_force_closes"


def phase13_costs() -> TradingCosts:
    """Return the frozen primary execution costs.

    A fresh value is returned on every call so a caller cannot mutate shared
    state. ``walk_forward`` additionally hashes the value it is given and
    re-checks that hash on every window.
    """

    return TradingCosts(
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
        spread_rate=SPREAD_RATE,
        execution_model=EXECUTION_MODEL,
    )


# ---------------------------------------------------------------------------
# Frozen configurations
# ---------------------------------------------------------------------------

BASELINE_NAME = "baseline"
A2_NAME = "A2"

#: Contamination disclosure that must accompany every A2 record. A2 was
#: selected in Phase 7 using 2024-2025 research data, and five of the six
#: evaluation windows lie inside that period.
A2_SELECTION_DISCLOSURE = (
    "A2 (min_breakout_distance=0.002) was selected during Phase 7 using "
    "2024-2025 research data. Evaluation windows 2-6 fall inside that "
    "selection period, so these results are NOT clean independent validation."
)


def baseline_config() -> StrategyConfig:
    """Pass A: the unmodified V1 configuration."""

    return StrategyConfig()


def a2_config() -> StrategyConfig:
    """Pass B: baseline plus the Phase 7 A2 distance filter."""

    return replace(StrategyConfig(), min_breakout_distance=0.002)


#: The two pre-registered passes, evaluated separately and never ranked.
PHASE13_CONFIGS: dict[str, object] = {
    BASELINE_NAME: baseline_config(),
    A2_NAME: a2_config(),
}


def config_disclosure(name: str) -> str:
    """Return the mandatory selection-history disclosure for a pass."""

    if name == A2_NAME:
        return A2_SELECTION_DISCLOSURE

    return (
        "baseline is the unmodified V1 StrategyConfig(); no Phase 13 result "
        "was used to select it."
    )


# ---------------------------------------------------------------------------
# Frozen windows
# ---------------------------------------------------------------------------


class WalkForwardValidationError(ValueError):
    """Raised when a Phase 13 setup violates the frozen design."""


@dataclass(frozen=True)
class WindowSpec:
    """One frozen walk-forward window.

    ``train_*`` and ``eval_*`` are inclusive calendar boundaries. The window is
    used for validation and reporting; execution uses ``evaluation_start`` so
    that training candles only warm the indicators.
    """

    window_id: int
    train_start: datetime
    train_end: datetime
    eval_start: datetime
    eval_end: datetime

    def __post_init__(self) -> None:
        if self.window_id < 1:
            raise WalkForwardValidationError(
                f"window_id must be >= 1, got {self.window_id}"
            )

        if self.eval_start > self.eval_end:
            raise WalkForwardValidationError(
                f"window {self.window_id}: eval_start {self.eval_start} is "
                f"after eval_end {self.eval_end}"
            )

        if self.train_start > self.train_end:
            raise WalkForwardValidationError(
                f"window {self.window_id}: train_start {self.train_start} is "
                f"after train_end {self.train_end}"
            )

        if self.train_end >= self.eval_start:
            raise WalkForwardValidationError(
                f"window {self.window_id}: train_end {self.train_end} is not "
                f"strictly before eval_start {self.eval_start}"
            )


#: The six frozen windows, exactly as pre-registered.
PHASE13_WINDOWS: tuple[WindowSpec, ...] = (
    WindowSpec(1, datetime(2024, 1, 1), datetime(2024, 6, 30, 23),
               datetime(2024, 7, 1), datetime(2024, 9, 30, 23)),
    WindowSpec(2, datetime(2024, 4, 1), datetime(2024, 9, 30, 23),
               datetime(2024, 10, 1), datetime(2024, 12, 31, 23)),
    WindowSpec(3, datetime(2024, 7, 1), datetime(2024, 12, 31, 23),
               datetime(2025, 1, 1), datetime(2025, 3, 31, 23)),
    WindowSpec(4, datetime(2024, 10, 1), datetime(2025, 3, 31, 23),
               datetime(2025, 4, 1), datetime(2025, 6, 30, 23)),
    WindowSpec(5, datetime(2025, 1, 1), datetime(2025, 6, 30, 23),
               datetime(2025, 7, 1), datetime(2025, 9, 30, 23)),
    WindowSpec(6, datetime(2025, 4, 1), datetime(2025, 9, 30, 23),
               datetime(2025, 10, 1), datetime(2025, 12, 31, 23)),
)


@dataclass(frozen=True)
class ResolvedWindow:
    """A :class:`WindowSpec` resolved to dataset indices."""

    spec: WindowSpec
    train_start_index: int
    train_end_index: int
    eval_start_index: int
    eval_end_index: int

    @property
    def window_id(self) -> int:
        return self.spec.window_id

    @property
    def train_candles(self) -> int:
        return self.train_end_index - self.train_start_index + 1

    @property
    def eval_candles(self) -> int:
        return self.eval_end_index - self.eval_start_index + 1

    @property
    def warmup_candles(self) -> int:
        """Candles available before the evaluation boundary for warm-up."""

        return self.eval_start_index


# ---------------------------------------------------------------------------
# Dataset validation
# ---------------------------------------------------------------------------


def sha256_of_file(path: str | Path) -> str:
    """Return the uppercase SHA-256 hex digest of a file."""

    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest().upper()


def validate_dataset_integrity(
    candles: Sequence[Candle],
    path: str | Path | None = None,
    expected_sha256: str | None = DATASET_SHA256,
    expected_count: int | None = DATASET_CANDLES,
) -> None:
    """Validate the Phase 13 dataset, raising on any violation.

    Checks, in order: non-empty, strictly increasing timestamps (duplicate
    rejection), exact 3600 s spacing, declared bounds and count, and the file
    hash when a path is supplied.
    """

    if not candles:
        raise WalkForwardValidationError("dataset contains no candles")

    stamps = [candle.timestamp for candle in candles]

    for previous, current in zip(stamps, stamps[1:]):
        if current == previous:
            raise WalkForwardValidationError(
                f"duplicate timestamp in dataset: {current}"
            )

        if current < previous:
            raise WalkForwardValidationError(
                f"timestamps are not strictly increasing at {current}"
            )

        step = (current - previous).total_seconds()

        if step != EXPECTED_INTERVAL_SECONDS:
            raise WalkForwardValidationError(
                f"expected {EXPECTED_INTERVAL_SECONDS}s candle spacing, "
                f"found {step}s between {previous} and {current}"
            )

    if stamps[0] != DATASET_FIRST:
        raise WalkForwardValidationError(
            f"dataset starts {stamps[0]}, expected {DATASET_FIRST}"
        )

    if stamps[-1] != DATASET_LAST:
        raise WalkForwardValidationError(
            f"dataset ends {stamps[-1]}, expected {DATASET_LAST}"
        )

    if expected_count is not None and len(candles) != expected_count:
        raise WalkForwardValidationError(
            f"dataset has {len(candles)} candles, expected {expected_count}"
        )

    if path is not None and expected_sha256 is not None:
        actual = sha256_of_file(path)

        if actual != expected_sha256:
            raise WalkForwardValidationError(
                f"dataset hash mismatch for {path}: expected "
                f"{expected_sha256}, found {actual}"
            )


def _index_of(
    stamps: Sequence[datetime],
    moment: datetime,
    window_id: int,
    label: str,
) -> int:
    try:
        return stamps.index(moment)
    except ValueError as exc:
        raise WalkForwardValidationError(
            f"window {window_id}: {label} {moment} is not a candle timestamp"
        ) from exc


def resolve_windows(
    candles: Sequence[Candle],
    windows: Sequence[WindowSpec] = PHASE13_WINDOWS,
) -> tuple[ResolvedWindow, ...]:
    """Resolve frozen windows to dataset indices, validating every rule.

    Rejects malformed boundaries, evaluation outside the dataset, evaluation
    windows that overlap each other, and windows whose training period is not
    strictly earlier than its evaluation period.
    """

    if not candles:
        raise WalkForwardValidationError("dataset contains no candles")

    stamps = [candle.timestamp for candle in candles]
    resolved: list[ResolvedWindow] = []
    previous_eval_end_index: int | None = None

    for spec in windows:
        if spec.eval_end > stamps[-1] or spec.eval_start < stamps[0]:
            raise WalkForwardValidationError(
                f"window {spec.window_id}: evaluation window "
                f"{spec.eval_start}..{spec.eval_end} falls outside the dataset"
            )

        if spec.train_start < stamps[0] or spec.train_end > stamps[-1]:
            raise WalkForwardValidationError(
                f"window {spec.window_id}: training window "
                f"{spec.train_start}..{spec.train_end} falls outside the "
                f"dataset"
            )

        train_start_index = _index_of(
            stamps, spec.train_start, spec.window_id, "train_start"
        )
        train_end_index = _index_of(
            stamps, spec.train_end, spec.window_id, "train_end"
        )
        eval_start_index = _index_of(
            stamps, spec.eval_start, spec.window_id, "eval_start"
        )
        eval_end_index = _index_of(
            stamps, spec.eval_end, spec.window_id, "eval_end"
        )

        if train_end_index >= eval_start_index:
            raise WalkForwardValidationError(
                f"window {spec.window_id}: training ends at index "
                f"{train_end_index} which is not before eval_start index "
                f"{eval_start_index}"
            )

        if eval_end_index < eval_start_index:
            raise WalkForwardValidationError(
                f"window {spec.window_id}: evaluation range is inverted"
            )

        if (
            previous_eval_end_index is not None
            and eval_start_index <= previous_eval_end_index
        ):
            raise WalkForwardValidationError(
                f"window {spec.window_id}: evaluation window overlaps the "
                f"previous evaluation window"
            )

        previous_eval_end_index = eval_end_index
        resolved.append(
            ResolvedWindow(
                spec=spec,
                train_start_index=train_start_index,
                train_end_index=train_end_index,
                eval_start_index=eval_start_index,
                eval_end_index=eval_end_index,
            )
        )

    return tuple(resolved)


# ---------------------------------------------------------------------------
# Mutation guards
# ---------------------------------------------------------------------------


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        repr(payload).encode("utf-8")
    ).hexdigest().upper()


def config_hash(config: StrategyConfig) -> str:
    """Stable hash of a frozen strategy configuration."""

    return _stable_hash(config)


def costs_hash(costs: TradingCosts) -> str:
    """Stable hash of a frozen execution-cost configuration."""

    return _stable_hash(costs)


def dataset_fingerprint(candles: Sequence[Candle]) -> tuple[int, datetime, datetime]:
    """Cheap fingerprint used to detect dataset mutation mid-run."""

    if not candles:
        return (0, DATASET_FIRST, DATASET_LAST)

    return (len(candles), candles[0].timestamp, candles[-1].timestamp)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowRun:
    """The outcome of one evaluation window. Descriptive only."""

    resolved: ResolvedWindow
    config_name: str
    result: BacktestResult
    config_repr: str
    config_hash: str
    costs_repr: str
    costs_hash: str
    warmup_rule: str = WARMUP_RULE
    boundary_policy: str = BOUNDARY_POLICY


def run_window(
    candles: Sequence[Candle],
    resolved: ResolvedWindow,
    config: StrategyConfig,
    config_name: str,
    costs: TradingCosts,
    starting_balance: float = STARTING_BALANCE,
    risk_fraction: float = RISK_FRACTION,
) -> WindowRun:
    """Run one evaluation window with the frozen warm-up and account rules.

    The backtest receives ``candles[:eval_end_index + 1]`` — the full history
    from the start of the dataset through the evaluation window's last candle
    — together with ``evaluation_start``. Indicators are therefore warmed by
    every preceding candle and no entry can occur before the boundary.
    """

    history = list(candles[: resolved.eval_end_index + 1])

    minimum = max(
        config.lookback + 2,
        config.slow_period,
    )

    if len(history) < minimum:
        raise WalkForwardValidationError(
            f"window {resolved.window_id}: {len(history)} candles of history "
            f"is below the {minimum} required by the backtest"
        )

    if len(history) <= resolved.eval_start_index:
        raise WalkForwardValidationError(
            f"window {resolved.window_id}: no candles precede the evaluation "
            f"boundary, so warm-up is impossible"
        )

    result = run_backtest(
        history,
        config=config,
        starting_balance=starting_balance,
        risk_fraction=risk_fraction,
        costs=costs,
        evaluation_start=resolved.eval_start_index,
    )

    eval_start = candles[resolved.eval_start_index].timestamp
    eval_end = candles[resolved.eval_end_index].timestamp

    premature = [
        trade
        for trade in result.trades
        if trade.entry_time is not None and trade.entry_time < eval_start
    ]

    if premature:
        raise WalkForwardValidationError(
            f"window {resolved.window_id}: {len(premature)} trade(s) opened "
            f"before the evaluation boundary {eval_start}"
        )

    stray = [
        trade
        for trade in result.trades
        if trade.exit_time is not None and trade.exit_time > eval_end
    ]

    if stray:
        raise WalkForwardValidationError(
            f"window {resolved.window_id}: {len(stray)} trade(s) exited after "
            f"the evaluation window ended {eval_end}"
        )

    if result.starting_balance != starting_balance:
        raise WalkForwardValidationError(
            f"window {resolved.window_id}: starting balance "
            f"{result.starting_balance} does not match the frozen "
            f"{starting_balance}"
        )

    return WindowRun(
        resolved=resolved,
        config_name=config_name,
        result=result,
        config_repr=repr(config),
        config_hash=config_hash(config),
        costs_repr=repr(costs),
        costs_hash=costs_hash(costs),
    )


def assert_no_state_carry(
    runs: Sequence[WindowRun],
    starting_balance: float = STARTING_BALANCE,
) -> None:
    """Reject any sign that account state was carried between windows.

    Each window must begin from the frozen starting balance and must own a
    disjoint set of trade objects. Identities are compared so that a shared
    ``PaperTrade`` instance cannot pass unnoticed.
    """

    seen: set[int] = set()

    for run in runs:
        if run.result.starting_balance != starting_balance:
            raise WalkForwardValidationError(
                f"window {run.resolved.window_id}: starting balance "
                f"{run.result.starting_balance} indicates carried state"
            )

        for trade in run.result.trades:
            if id(trade) in seen:
                raise WalkForwardValidationError(
                    f"window {run.resolved.window_id}: trade object reused "
                    f"from an earlier window; state was carried"
                )

            seen.add(id(trade))


def walk_forward(
    candles: Sequence[Candle],
    config: StrategyConfig,
    config_name: str,
    costs: TradingCosts | None = None,
    windows: Sequence[WindowSpec] = PHASE13_WINDOWS,
    starting_balance: float = STARTING_BALANCE,
    risk_fraction: float = RISK_FRACTION,
    validate: bool = True,
    expected_fingerprint: tuple[int, datetime, datetime] | None = None,
) -> tuple[WindowRun, ...]:
    """Run every frozen window for one pre-registered configuration.

    The configuration and execution costs are hashed before the first window
    and re-checked after every window, so a mid-run mutation raises rather than
    silently producing a mixed run. The dataset fingerprint is likewise
    re-checked.
    """

    if validate:
        validate_dataset_integrity(candles)

    frozen_costs = costs if costs is not None else phase13_costs()
    frozen_config_hash = config_hash(config)
    frozen_costs_hash = costs_hash(frozen_costs)

    fingerprint = (
        expected_fingerprint
        if expected_fingerprint is not None
        else dataset_fingerprint(candles)
    )

    resolved = resolve_windows(candles, windows)
    runs: list[WindowRun] = []

    for window in resolved:
        run = run_window(
            candles,
            window,
            config,
            config_name,
            frozen_costs,
            starting_balance=starting_balance,
            risk_fraction=risk_fraction,
        )
        runs.append(run)

        if config_hash(config) != frozen_config_hash:
            raise WalkForwardValidationError(
                f"window {window.window_id}: strategy configuration changed "
                f"during the walk-forward run"
            )

        if costs_hash(frozen_costs) != frozen_costs_hash:
            raise WalkForwardValidationError(
                f"window {window.window_id}: execution costs changed during "
                f"the walk-forward run"
            )

        if dataset_fingerprint(candles) != fingerprint:
            raise WalkForwardValidationError(
                f"window {window.window_id}: dataset changed during the "
                f"walk-forward run"
            )

    assert_no_state_carry(runs, starting_balance=starting_balance)

    return tuple(runs)


# ---------------------------------------------------------------------------
# Reproducibility guard
# ---------------------------------------------------------------------------


def assert_clean_working_tree(repo_root: str | Path = ".") -> None:
    """Raise when the Git working tree is dirty.

    The pre-registration requires a clean tree so a run can be tied to an
    exact commit. The repository root is a parameter so this can be exercised
    against a controlled temporary repository in tests rather than against the
    live working tree.
    """

    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise WalkForwardValidationError(
            "could not determine Git working-tree cleanliness: "
            f"{completed.stderr.strip()}"
        )

    if completed.stdout.strip():
        raise WalkForwardValidationError(
            "Git working tree is dirty; a Phase 13 run requires a clean tree "
            f"for reproducibility:\n{completed.stdout.strip()}"
        )


__all__ = [
    "A2_NAME",
    "A2_SELECTION_DISCLOSURE",
    "BASELINE_NAME",
    "BOUNDARY_POLICY",
    "DATASET_CANDLES",
    "DATASET_FIRST",
    "DATASET_LAST",
    "DATASET_PATH",
    "DATASET_SHA256",
    "EXECUTION_MODEL",
    "EXPECTED_INTERVAL_SECONDS",
    "FEE_RATE",
    "PHASE13_CONFIGS",
    "PHASE13_WINDOWS",
    "RISK_FRACTION",
    "SLIPPAGE_RATE",
    "SPREAD_RATE",
    "STARTING_BALANCE",
    "WARMUP_RULE",
    "ResolvedWindow",
    "WalkForwardValidationError",
    "WindowRun",
    "WindowSpec",
    "a2_config",
    "assert_clean_working_tree",
    "assert_no_state_carry",
    "baseline_config",
    "config_disclosure",
    "config_hash",
    "costs_hash",
    "dataset_fingerprint",
    "phase13_costs",
    "resolve_windows",
    "run_window",
    "sha256_of_file",
    "validate_dataset_integrity",
    "walk_forward",
]