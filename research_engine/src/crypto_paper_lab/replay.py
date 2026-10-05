"""Deterministic historical paper replay (Phase 17B).

This module is the ``run_backtest`` loop made callable one iteration at a time.
It exists because a *replay* needs pacing, inspection and a cursor, and none of
those belong in a research backtest whose job is to run to completion and return
an aggregate.

Design rules, all inherited from ``experiments/PHASE17_REPLAY_ARCHITECTURE.md``:

* **The engine remains the single source of truth.** Every price, size, fee and
  P&L figure comes from :class:`~crypto_paper_lab.simulator.PaperBroker` or
  :func:`~crypto_paper_lab.strategy.analyze`. This module performs exactly one
  arithmetic operation, ``balance - starting_balance``, which is the engine's own
  ``BacktestResult.net_pnl`` definition (``results.py:21-22``).
* **No new execution semantics.** The step sequence is a statement-for-statement
  transliteration of ``backtest.py:135-213``. The stop/target rule is *imported*
  from that module rather than reimplemented, so the two cannot drift.
* **No unsupported fields.** There is no equity, mark price, unrealized P&L,
  reserved capital or buying power here, because ``PaperBroker`` holds no such
  concept and inventing one is the failure this project exists to avoid.
* **The dataset is never mutated.** Candles are held as a ``tuple`` of frozen
  ``Candle`` dataclasses; there is no mutating operation available on them.

Cursor semantics (Phase 17A §4)
-------------------------------

``cursor = i`` names the **execution bar**: the candle whose ``open`` supplies a
fill price. The signal for that step is computed from ``candles[:i]``, so the
newest bar the strategy sees is ``candles[i - 1]`` - the **signal bar**. The one
bar between them is the causality boundary, and it is enforced by the *slice*
passed to ``analyze`` rather than by convention: the strategy is handed an object
that does not contain later candles.

Note that ``run_backtest`` binds the name ``current`` to the execution bar
(``backtest.py:136``) while ``analyze`` binds ``current`` to the signal bar
(``strategy.py:60``). This module never uses the bare name for either.

Execution policy
----------------

Whether a signal becomes a trade is a *policy*, not a property of the strategy.
Phase 17B ships exactly one policy - :data:`AUTOMATIC_POLICY` - which reproduces
``run_backtest`` so that prefix equivalence can be established. The seam exists
now, deliberately, because a later Manual policy must be able to *decline* to
trade a signal that a High-Risk policy would accept. Inlining the entry rule, the
way ``run_backtest`` does, would make that inexpressible.

Scope
-----

Implemented here: replay state, one deterministic step, and reset.

Deliberately **not** here: the auto-run timer, start/pause, mode policies,
Daily Target, Manual, High-Risk, Alerts, close controls, transport endpoints,
persistence, and any form of live or future data. Alerts in particular must never
be able to execute, which is why this module exposes no "execute this signal"
entry point beyond the single automatic policy.

Paper only. There is no exchange connectivity, no credential, no wallet and no
order concept anywhere in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal
from uuid import uuid4

from .backtest import (
    END_OF_DATA,
    MAX_HOLDING,
    OPPOSITE_SIGNAL,
    STOP_LOSS,
    TAKE_PROFIT,
    _levels_breached,
    _side_allowed,
)
from .costs import TradingCosts
from .models import Candle, PaperTrade, Signal
from .simulator import PaperBroker
from .strategy import StrategyConfig, analyze
from .walkforward import (
    DATASET_SHA256,
    EXPECTED_INTERVAL_SECONDS,
    RISK_FRACTION,
    STARTING_BALANCE,
    config_hash,
    costs_hash,
    dataset_fingerprint,
    phase13_costs,
)

__all__ = [
    "AUTOMATIC_POLICY",
    "DEFAULT_INTERVAL_MS",
    "MAX_INTERVAL_MS",
    "MIN_INTERVAL_MS",
    "STATE_FINISHED",
    "STATE_IDLE",
    "STATE_PAUSED",
    "STATE_RUNNING",
    "DatasetIdentity",
    "ExecutionIdentity",
    "ExecutionPolicy",
    "InvalidIntervalError",
    "InvalidStartIndexError",
    "OnDemandTicker",
    "PositionOpenError",
    "Replay",
    "ReplayError",
    "ReplayFinishedError",
    "ReplayState",
    "StepResult",
    "StrategyIdentity",
    "Ticker",
    "minimum_history",
]

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

#: Created, or returned to by reset. Cursor at ``start_index``, no bars consumed.
STATE_IDLE = "idle"

#: Auto-run timer active. *Not produced in Phase 17B* - there is no timer yet.
#: Declared now because Phase 17A approved exactly these four states, and
#: widening the type later is cheaper than a second contract change.
STATE_RUNNING = "running"

#: Auto-run timer stopped, cursor and broker retained. *Not produced in 17B.*
STATE_PAUSED = "paused"

#: Cursor reached the end of the dataset. Terminal; only ``reset`` exits it.
STATE_FINISHED = "finished"

# ---------------------------------------------------------------------------
# Auto-run pacing
# ---------------------------------------------------------------------------

#: Phase 17A section 7.5. Auto-run is paced in milliseconds between steps.
DEFAULT_INTERVAL_MS = 1_000

#: Bounds are **validated, never clamped**. Clamping would silently substitute a
#: pace the caller did not ask for, which is exactly the kind of quiet
#: reinterpretation this module avoids elsewhere.
MIN_INTERVAL_MS = 100
MAX_INTERVAL_MS = 60_000


def minimum_history(config: StrategyConfig) -> int:
    """Candles ``analyze`` requires before it will produce a signal.

    Mirrors the engine's own guard, ``max(lookback + 2, slow_period)``, which
    ``run_backtest`` computes inline at ``backtest.py:112-115`` and ``analyze``
    enforces at ``strategy.py:53-57``. Twenty-two for the frozen baseline.

    This is the third expression of a one-line formula in the codebase. It is
    duplicated rather than extracted because ``run_backtest``'s copy is inline and
    ``backtest.py`` is a frozen research file whose behaviour Phase 13 depends on;
    refactoring it for style would touch a file this phase must not modify.
    ``paper_api/signals.py:45-53`` carries the same mirror with the same note.
    """

    return max(config.lookback + 2, config.slow_period)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReplayError(Exception):
    """Base class for replay failures.

    Carries a stable ``code`` so a transport layer can map failures to HTTP
    without this module importing any web framework. Phase 17B defines no
    endpoints, so nothing consumes ``code`` yet.
    """

    code = "REPLAY_ERROR"


class InvalidStartIndexError(ReplayError):
    """The requested start point cannot produce a signal."""

    code = "INSUFFICIENT_HISTORY"


class ReplayFinishedError(ReplayError):
    """A step was attempted after the dataset was exhausted.

    Raised rather than returning a silent no-op: a no-op would let a caller
    believe the replay advanced when it did not.
    """

    code = "REPLAY_FINISHED"


class PositionOpenError(ReplayError):
    """Reset was refused because a paper position is still open.

    Phase 17A §8.1 / decision Q2. Recreating the broker would silently discard an
    open trade, and force-closing it first would make reset a trading operation -
    which Phase 17A decision Q1 declined. So reset refuses and says why.
    """

    code = "POSITION_OPEN"


class InvalidIntervalError(ReplayError):
    """An auto-run interval outside the permitted range was requested."""

    code = "INVALID_INTERVAL"


# ---------------------------------------------------------------------------
# Execution policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionPolicy:
    """Whether an eligible signal becomes a paper trade.

    Phase 17A §6 requires this to be an explicit, swappable object rather than an
    inlined block, for two reasons that are both about *future* modes:

    * A **Manual** policy sets ``allow_entry=False``. It would display the signal
      and never trade it. With the rule inlined there is no way to express that.
    * An **Alerts** consumer must be structurally incapable of execution. Keeping
      the decision in a named object is what lets a later phase assert, by
      inspection, that nothing else in the system can open a trade.

    ``allow_entry=False`` is the entire mechanism Manual needs, so it is the
    entire mechanism provided. Adding a richer decision type now would be
    speculative.
    """

    name: str
    allow_entry: bool

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("execution policy must be named")


#: Reproduces ``run_backtest``: any eligible non-flat signal opens a position.
#: The only policy that exists in Phase 17B.
AUTOMATIC_POLICY = ExecutionPolicy(name="automatic", allow_entry=True)


# ---------------------------------------------------------------------------
# Auto-run pacing
# ---------------------------------------------------------------------------


class Ticker:
    """Decides *when* an automatic step happens. Never decides what one does.

    Phase 17A §7.4 requires auto-run to be repeated ``step()`` and nothing else
    (invariant AR-1: "Auto-run must be implemented as repeated ``step()``, not as a
    separate code path with its own timing"). A ticker may therefore answer exactly
    one question - is a step due? - and must not be able to run trading logic,
    choose a fill, or move the cursor.

    Substituting a different ticker may change **pacing only, never results**.
    That is the property the tests rely on: a ticker that fires on a schedule and
    one that fires on command must produce byte-identical journals.

    Why a seam at all, given no clock is used yet: so that adding a real
    wall-clock driver in a later transport phase cannot require touching
    ``Replay``, and so the lifecycle can be tested without sleeping. A test that
    waited on real time would be a flaky test, and a flaky test is a test that
    will eventually be ignored.
    """

    def arm(self, interval_ms: int) -> None:
        """Begin offering ticks. Must be idempotent: arming twice offers one
        tick per request, not two."""

        raise NotImplementedError

    def disarm(self) -> None:
        """Stop offering ticks. Must be idempotent."""

        raise NotImplementedError

    @property
    def armed(self) -> bool:
        raise NotImplementedError

    def take(self) -> bool:
        """Consume at most one due tick.

        Returns ``True`` when a step is due now. Must not perform trading work,
        and must be safe to call when disarmed.
        """

        raise NotImplementedError


class OnDemandTicker(Ticker):
    """Default ticker: a tick is due whenever it is armed and asked for.

    No wall clock, no worker, no sleeping. Two consecutive ``take()`` calls each
    yield one tick, so *N* takes produce exactly *N* steps. That property is what
    makes repeated ``start()`` calls provably harmless - there is no second worker
    to create, so none can be created.
    """

    def __init__(self) -> None:
        self._armed = False
        self._interval_ms = DEFAULT_INTERVAL_MS
        self.takes = 0

    def arm(self, interval_ms: int) -> None:
        self._armed = True
        self._interval_ms = interval_ms

    def disarm(self) -> None:
        self._armed = False

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    def take(self) -> bool:
        if not self._armed:
            return False

        self.takes += 1
        return True


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetIdentity:
    """Which historical dataset is being replayed.

    Carries a hash and declared bounds, never a filesystem path. Mirrors the
    identity Phase 16 already serves on ``/api/market``; defined here rather than
    imported because the engine must not depend on the transport package.
    """

    asset: str
    timeframe: str
    sha256: str
    first_timestamp: datetime
    last_timestamp: datetime
    candle_count: int
    interval_seconds: int

    @classmethod
    def from_candles(
        cls,
        candles: tuple,
        config: StrategyConfig,
        sha256: str = DATASET_SHA256,
    ) -> "DatasetIdentity":
        """Build identity from the series actually loaded.

        The hash is supplied by the caller because hashing is the caller's
        decision; a replay over an arbitrary candle list must not claim the frozen
        dataset's hash. For the frozen research dataset the caller passes
        ``walkforward.DATASET_SHA256``.
        """

        return cls(
            asset=config.asset,
            timeframe=config.timeframe,
            sha256=sha256,
            first_timestamp=candles[0].timestamp,
            last_timestamp=candles[-1].timestamp,
            candle_count=len(candles),
            interval_seconds=EXPECTED_INTERVAL_SECONDS,
        )


@dataclass(frozen=True)
class StrategyIdentity:
    """Which strategy configuration is driving the replay."""

    config_repr: str
    config_hash: str

    @classmethod
    def from_config(cls, config: StrategyConfig) -> "StrategyIdentity":
        return cls(config_repr=repr(config), config_hash=config_hash(config))


@dataclass(frozen=True)
class ExecutionIdentity:
    """Which execution-cost model and account sizing are in force."""

    execution_model: str
    fee_rate: float
    slippage_rate: float
    spread_rate: float
    costs_repr: str
    costs_hash: str
    risk_fraction: float

    @classmethod
    def from_costs(
        cls, costs: TradingCosts, risk_fraction: float
    ) -> "ExecutionIdentity":
        return cls(
            execution_model=costs.execution_model,
            fee_rate=costs.fee_rate,
            slippage_rate=costs.slippage_rate,
            spread_rate=costs.spread_rate,
            costs_repr=repr(costs),
            costs_hash=costs_hash(costs),
            risk_fraction=risk_fraction,
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayState:
    """An immutable snapshot of a replay at one cursor position.

    A snapshot rather than a live view, so two states can be compared exactly and
    determinism is testable by equality.

    Absent by design, because ``PaperBroker`` cannot authoritatively produce them:
    equity, mark price, unrealized P&L, available balance, reserved capital,
    buying power and notional. ``realized_pnl`` is present because it is the
    engine's own definition and is already exposed by ``BacktestResult``.
    """

    replay_id: str
    status: Literal["idle", "running", "paused", "finished"]
    dataset: DatasetIdentity
    strategy: StrategyIdentity
    execution: ExecutionIdentity

    cursor: int = 0
    start_index: int = 0
    bars_processed: int = 0

    current_timestamp: datetime | None = None
    next_timestamp: datetime | None = None
    next_candle_available: bool = False

    starting_balance: float = 0.0
    balance: float = 0.0
    realized_pnl: float = 0.0
    trade_count: int = 0

    has_open_position: bool = False
    open_position: PaperTrade | None = None
    last_signal: Signal | None = None


@dataclass(frozen=True)
class StepResult:
    """What one step did.

    ``closed`` and ``opened`` are **both** frequently non-``None``: 343 of the 344
    trades in the frozen baseline are part of a same-bar reversal, where an
    opposite signal closes one position and immediately opens another at the same
    execution-bar open. A caller that assumes "one event per step" is wrong about
    the common case, not an edge case.

    ``signal`` is the strategy's observation for this step, taken from the signal
    bar. It is returned whether or not anything traded, because a ``flat`` signal
    is a legitimate outcome and not an error.
    """

    cursor_before: int
    cursor_after: int
    signal: Signal | None
    signal_timestamp: datetime | None
    execution_bar: Candle | None
    closed: PaperTrade | None
    opened: PaperTrade | None
    finished: bool


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Replay:
    """A deterministic, step-at-a-time replay of a closed candle series.

    Not thread-safe by itself. A caller driving it from concurrent requests must
    serialise ``step()`` and ``reset()``; Phase 17A §17.2 requires that lock at
    the transport layer, which does not exist yet.

    The broker is created here and owned here. This phase deliberately uses a
    single broker: mode isolation (separate brokers per mode) is Phase 17F, and
    building the registry now would be speculative.
    """

    def __init__(
        self,
        candles,
        config: StrategyConfig | None = None,
        costs: TradingCosts | None = None,
        starting_balance: float = STARTING_BALANCE,
        risk_fraction: float = RISK_FRACTION,
        start_index: int | None = None,
        evaluation_start: int | None = None,
        policy: ExecutionPolicy = AUTOMATIC_POLICY,
        replay_id: str | None = None,
        dataset_sha256: str = DATASET_SHA256,
        ticker: Ticker | None = None,
    ) -> None:
        """
        Parameters
        ----------
        candles:
            The series to replay. Stored as a ``tuple`` of frozen ``Candle``
            dataclasses. A list is accepted and copied precisely so the caller
            cannot mutate the replay's view of history afterwards.
        start_index:
            First execution bar to consume. Defaults to ``minimum_history``.
            May be greater, which is how a walk-forward evaluation boundary is
            replayed: safe because the broker starts flat, so no iteration is
            skipped that would have had to close a position.
        evaluation_start:
            Optional entry gate mirroring ``run_backtest``'s parameter. Entries
            require ``cursor >= evaluation_start``.
        policy:
            Execution policy. Defaults to the automatic policy that reproduces
            ``run_backtest``.
        dataset_sha256:
            Identity hash to record. Supplied rather than computed, because a
            replay over an arbitrary series must not claim the frozen dataset's
            hash.
        ticker:
            Auto-run pacing. Defaults to :class:`OnDemandTicker`, which yields a
            tick whenever it is armed and asked for, so automatic progression is
            fully driven and therefore fully deterministic.
        """

        series = tuple(candles)

        if not series:
            raise ValueError("replay requires at least one candle")

        self._candles = series
        self._config = config if config is not None else StrategyConfig()
        self._costs = costs if costs is not None else phase13_costs()
        self._policy = policy
        self._risk_fraction = risk_fraction
        self._replay_id = replay_id if replay_id is not None else str(uuid4())
        self._evaluation_start = evaluation_start
        self._starting_balance = starting_balance
        self._ticker = ticker if ticker is not None else OnDemandTicker()
        self._interval_ms = DEFAULT_INTERVAL_MS

        required = minimum_history(self._config)

        if start_index is None:
            resolved_start = required
        else:
            resolved_start = start_index

        if resolved_start < required:
            raise InvalidStartIndexError(
                f"start_index {resolved_start} is below the {required} candles "
                f"the configured strategy requires; a signal could not be "
                f"produced there"
            )

        if resolved_start >= len(series):
            raise InvalidStartIndexError(
                f"start_index {resolved_start} is not within a dataset of "
                f"{len(series)} candles"
            )

        if evaluation_start is not None and not (
            required <= evaluation_start < len(series)
        ):
            raise InvalidStartIndexError(
                f"evaluation_start {evaluation_start} must be at least the "
                f"minimum history ({required}) and strictly less than the "
                f"number of candles ({len(series)})"
            )

        self._start_index = resolved_start

        # Frozen identities. Recomputed hashes are re-checked after every step,
        # mirroring walkforward.py:632-648, so mid-run mutation raises instead of
        # silently producing a run whose halves used different assumptions.
        self._dataset_identity = DatasetIdentity.from_candles(
            series, self._config, sha256=dataset_sha256
        )
        self._strategy_identity = StrategyIdentity.from_config(self._config)
        self._execution_identity = ExecutionIdentity.from_costs(
            self._costs, risk_fraction
        )
        self._fingerprint = dataset_fingerprint(series)
        self._config_hash = self._strategy_identity.config_hash
        self._costs_hash = self._execution_identity.costs_hash

        self._reset_runtime()

    # -- introspection ------------------------------------------------------

    @property
    def replay_id(self) -> str:
        """Stable identity of this replay. Retained across ``reset()``."""

        return self._replay_id

    @property
    def broker(self) -> PaperBroker:
        """The authoritative broker, read-only. Never reassigned by ``reset()``;
        a reset constructs a *new* broker rather than mutating this one.
        """

        return self._broker

    @property
    def policy(self) -> ExecutionPolicy:
        return self._policy

    @property
    def config(self) -> StrategyConfig:
        """The strategy configuration driving this replay. Read-only.

        Added in Phase 17D so a transport layer can build an account projection
        that is guaranteed to describe *this* replay's configuration, rather than
        re-declaring a default that could silently disagree with the replay it is
        meant to be viewing.
        """

        return self._config

    @property
    def ticker(self) -> Ticker:
        """The pacing object. Read-only; a replay never swaps it mid-run."""

        return self._ticker

    @property
    def interval_ms(self) -> int:
        """Auto-run interval last requested by :meth:`start`."""

        return self._interval_ms

    @property
    def entry_index(self) -> int | None:
        """Index at which the open trade was entered, or ``None`` when flat.

        Replay-owned bookkeeping and genuinely new state: ``PaperTrade`` records a
        timestamp, not an index, and ``bars_held`` is defined as an index
        difference (``backtest.py:153``). Not part of ``ReplayState`` because it is
        an implementation detail rather than something a caller acts on.
        """

        return self._entry_index

    @property
    def exit_counts(self) -> dict:
        """Close-reason tally, copied so callers cannot mutate replay state.

        Keys match ``run_backtest``'s ``exit_counts`` exactly.
        """

        return dict(self._exit_counts)

    @property
    def state(self) -> ReplayState:
        """An immutable snapshot of the replay right now."""

        broker = self._broker
        cursor = self._cursor
        consumed = cursor > self._start_index

        return ReplayState(
            replay_id=self._replay_id,
            status=self._status,  # type: ignore[arg-type]
            cursor=cursor,
            start_index=self._start_index,
            bars_processed=cursor - self._start_index,
            # The last bar a step actually consumed. ``None`` before the first
            # step: the bar at ``cursor - 1`` is then the *signal* bar waiting to
            # be evaluated, not a consumed bar, and reporting it would suggest
            # the replay had already seen a bar it has not acted on.
            current_timestamp=(
                self._candles[cursor - 1].timestamp if consumed else None
            ),
            next_timestamp=(
                self._candles[cursor].timestamp
                if cursor < len(self._candles)
                else None
            ),
            next_candle_available=cursor < len(self._candles),
            starting_balance=broker.starting_balance,
            balance=broker.cash,
            # The one permitted arithmetic: the engine's own net_pnl definition.
            realized_pnl=broker.cash - broker.starting_balance,
            trade_count=len(broker.journal),
            has_open_position=broker.open_trade is not None,
            open_position=broker.open_trade,
            last_signal=self._last_signal,
            dataset=self._dataset_identity,
            strategy=self._strategy_identity,
            execution=self._execution_identity,
        )

    # -- mutation -----------------------------------------------------------

    def start(self, interval_ms: int | None = None) -> ReplayState:
        """Arm auto-run: ``idle``/``paused`` become ``running``.

        Idempotent. Calling it again while already running re-arms the *same*
        ticker rather than creating another, which is why repeated calls cannot
        produce two steps per tick. It never advances the cursor.

        Arming is also what makes auto-run driveable::

            replay.start()
            while replay.ticker.armed:
                replay.tick()

        ``armed`` goes false on :meth:`pause`, on reaching the end of the data,
        and on :meth:`reset`, so that loop terminates on its own.

        A finished replay is left finished and its ticker stays disarmed. Note
        this is deliberately a quiet no-op rather than an exception: the Phase 17C
        transition table specifies ``finished -> finished``. Phase 17A §21 still
        requires the HTTP layer to answer ``409 REPLAY_FINISHED`` for this case, so
        a transport must inspect ``state.status`` and reject. Keeping the refusal
        in the transport rather than the engine is what lets both documents hold.

        Parameters
        ----------
        interval_ms:
            Requested pace. ``None`` keeps the current interval. Out of range is
            **rejected, never clamped** (Phase 17A §7.5).

        Raises
        ------
        InvalidIntervalError
            If the effective interval is outside ``MIN_INTERVAL_MS``..
            ``MAX_INTERVAL_MS``.
        """

        requested = self._interval_ms if interval_ms is None else interval_ms

        if not MIN_INTERVAL_MS <= requested <= MAX_INTERVAL_MS:
            raise InvalidIntervalError(
                f"interval_ms must be between {MIN_INTERVAL_MS} and "
                f"{MAX_INTERVAL_MS}, got {requested}"
            )

        if self._status == STATE_FINISHED:
            # Terminal. Do not arm, do not restart.
            return self.state

        self._interval_ms = requested
        self._status = STATE_RUNNING
        self._ticker.arm(requested)

        return self.state

    def pause(self) -> ReplayState:
        """Disarm auto-run: ``running`` becomes ``paused``.

        Idempotent, and a no-op from ``idle`` or ``finished`` - those states are
        returned unchanged, matching the Phase 17C transition table. As with
        :meth:`start`, a transport is expected to answer ``409
        INVALID_TRANSITION`` for a pause that did not change anything.

        Nothing else is touched. The cursor, broker, journal, balances and signal
        are exactly as they were, so pausing is always safe to interrupt.
        """

        if self._status == STATE_RUNNING:
            self._status = STATE_PAUSED

        self._ticker.disarm()

        return self.state

    def tick(self) -> StepResult | None:
        """Perform at most one *automatic* step.

        This is the auto-run entry point: it consults the ticker and, when a tick
        is due, delegates to :meth:`step`. It therefore obeys invariant AR-1 -
        there is no second execution path, only a second way of asking for one.

        Returns ``None`` when no tick is due: not running, or already finished.
        Returning ``None`` rather than raising is deliberate. A finished replay
        receiving further ticks is the normal end of an auto-run, not an error;
        the caller can stop as soon as it sees ``None``. :meth:`step` remains the
        strict primitive and still raises when finished.

        Note
        ----
        Ticking a replay that was never started is a **no-op returning ``None``**,
        not an error. Callers must therefore drive auto-run on the armed flag,
        which is what makes the loop terminate::

            replay.start()
            while replay.ticker.armed:      # False once paused or finished
                replay.tick()

        Looping on ``status != finished`` instead would spin forever when the
        replay was never started, because a no-op tick leaves the status alone.
        That asymmetry is intentional: auto-run is gated on being armed, not on
        the cursor still having bars left.
        """

        if self._status != STATE_RUNNING:
            return None

        if not self._ticker.take():
            return None

        if self._status == STATE_FINISHED:
            return None

        return self._advance()

    def step(self) -> StepResult:
        """Advance exactly one execution bar.

        A transliteration of one iteration of ``backtest.py:135-205``, followed by
        the end-of-data block of ``backtest.py:207-213`` when the cursor reaches
        the end of the series.

        Legal from ``idle``, ``paused`` and ``running`` (Phase 17A §7.2). From
        ``running`` it interleaves with the ticker and leaves the status
        ``running``. It is also the only way for a non-running replay to advance:
        pausing does not prevent a deliberate manual step, which is what makes a
        paused replay still explorable.

        Raises
        ------
        ReplayFinishedError
            If the replay has already finished. Never a silent no-op.
        """

        if self._status == STATE_FINISHED:
            raise ReplayFinishedError(
                "replay has reached the end of the dataset; reset to run again"
            )

        return self._advance()

    def _advance(self) -> StepResult:
        """The single-step body, shared by :meth:`step` and :meth:`tick`.

        Kept as a separate method so the auto-run path calls exactly the code the
        manual path calls. That is invariant AR-1 expressed structurally: there is
        no second implementation that could drift.
        """

        index = self._cursor

        if index >= len(self._candles):
            return self._finish()

        execution_bar = self._candles[index]

        # The causality boundary. The strategy receives a slice that structurally
        # cannot contain the execution bar or anything after it.
        signal = analyze(self._candles[:index], self._config)

        closed = self._maybe_exit(index, signal, execution_bar)
        opened = self._maybe_enter(index, signal, execution_bar)

        self._last_signal = signal
        self._cursor = index + 1

        self._assert_identities_unchanged()

        return StepResult(
            cursor_before=index,
            cursor_after=self._cursor,
            signal=signal,
            signal_timestamp=self._candles[index - 1].timestamp,
            execution_bar=execution_bar,
            closed=closed,
            opened=opened,
            finished=False,
        )

    def reset(self) -> ReplayState:
        """Restore the exact initial state.

        Per Phase 17A §8 and decision Q2: refuses while a position is open, so an
        open trade is never silently discarded and reset is never a trading
        operation.

        A fresh broker is constructed rather than the existing one being cleared,
        matching how ``run_backtest`` isolates every walk-forward window
        (``walkforward.py:19-20``) and how ``assert_no_state_carry`` proves no state
        leaked between them. The dataset is not reloaded, and is in any case
        immutably held, so reset cannot mutate it.

        Returns
        -------
        ReplayState
            The snapshot at the initial cursor.
        """

        if self._broker.open_trade is not None:
            raise PositionOpenError(
                "cannot reset while a paper position is open; it would be "
                "discarded without a record. Step until an exit rule fires, or "
                "reset from a flat state"
            )

        self._reset_runtime()
        self._assert_identities_unchanged()

        return self.state

    # -- internals ----------------------------------------------------------

    def _reset_runtime(self) -> None:
        """Rebuild every mutable field to its initial value.

        A brand-new broker each time, never a cleared one, so no field of the
        previous broker can survive by being forgotten. The stored
        ``starting_balance`` and ``costs`` are reused verbatim, which is what
        makes reset reproduce a run exactly.
        """

        self._broker = PaperBroker(
            starting_balance=self._starting_balance,
            costs=self._costs,
        )
        self._cursor = self._start_index
        self._entry_index = None
        self._last_signal = None
        self._exit_counts = {}
        self._status = STATE_IDLE

        # A reset must never leave auto-run armed. Step 7 of the Phase 17C
        # contract: resetting must not create a running ticker.
        self._ticker.disarm()

    def _maybe_exit(
        self, index: int, signal: Signal, execution_bar: Candle
    ) -> PaperTrade | None:
        """Exit evaluation, then entry evaluation order preserved.

        Ordering is load-bearing: after a close clears ``open_trade``, the entry
        check in :meth:`step` runs in the *same* iteration with the *same* signal,
        which is what produces a same-bar reversal.
        """

        broker = self._broker

        if broker.open_trade is None or self._entry_index is None:
            return None

        config = self._config
        trade = broker.open_trade
        bars_held = index - self._entry_index
        exit_reason: str | None = None

        # Exit rules are never evaluated on the entry bar (backtest.py:158).
        if bars_held >= 1:
            closed_bar = self._candles[index - 1]

            if (
                config.max_holding_bars is not None
                and bars_held >= config.max_holding_bars
            ):
                exit_reason = MAX_HOLDING
            elif (
                config.stop_loss_pct is not None
                or config.take_profit_pct is not None
            ):
                # Imported from backtest so the rule cannot drift.
                stop_hit, target_hit = _levels_breached(
                    trade, closed_bar, config
                )
                if stop_hit:
                    exit_reason = STOP_LOSS
                elif target_hit:
                    exit_reason = TAKE_PROFIT

        if exit_reason is None and (
            signal.side in {"long", "short"}
            and signal.side != trade.side
        ):
            exit_reason = OPPOSITE_SIGNAL

        if exit_reason is None:
            return None

        closed = broker.close(execution_bar.open, execution_bar.timestamp)
        # The broker does not write these; run_backtest sets them after the close
        # returns (backtest.py:188-189) and so must replay.
        closed.exit_reason = exit_reason
        closed.bars_held = bars_held

        self._entry_index = None
        self._exit_counts[exit_reason] = (
            self._exit_counts.get(exit_reason, 0) + 1
        )

        return closed

    def _maybe_enter(
        self, index: int, signal: Signal, execution_bar: Candle
    ) -> PaperTrade | None:
        """Entry evaluation. Runs after any close, in the same step."""

        broker = self._broker

        if broker.open_trade is not None:
            return None

        if signal.side not in {"long", "short"}:
            return None

        if not self._policy.allow_entry:
            return None

        if not _side_allowed(signal.side, self._config):
            return None

        if (
            self._evaluation_start is not None
            and index < self._evaluation_start
        ):
            return None

        # ``replace`` is pure, so building this only when an entry will actually
        # happen is equivalent to run_backtest's unconditional construction.
        execution_signal = replace(
            signal,
            timestamp=execution_bar.timestamp,
            price=execution_bar.open,
        )

        opened = broker.open_from_signal(
            execution_signal, risk_fraction=self._risk_fraction
        )
        self._entry_index = index

        return opened

    def _finish(self) -> StepResult:
        """Apply end-of-data closure and mark the replay finished.

        Mirrors ``backtest.py:207-213``: the remaining position is closed at the
        **final candle's close**, not its open.
        """

        broker = self._broker
        closed: PaperTrade | None = None

        if broker.open_trade is not None:
            last = self._candles[-1]
            closed = broker.close(last.close, last.timestamp)
            closed.exit_reason = END_OF_DATA
            # run_backtest computes len(candles) - 1 - entry_index. Here the cursor
            # has reached the end of the series, so cursor - 1 is the final index.
            closed.bars_held = self._cursor - 1 - (self._entry_index or 0)
            self._exit_counts[END_OF_DATA] = (
                self._exit_counts.get(END_OF_DATA, 0) + 1
            )
            self._entry_index = None

        self._status = STATE_FINISHED

        # Nothing more will be stepped, so nothing more may be ticked. Disarming
        # here is what makes the terminal transition happen exactly once: further
        # ticks find no due tick and return None.
        self._ticker.disarm()

        self._assert_identities_unchanged()

        return StepResult(
            cursor_before=self._cursor,
            cursor_after=self._cursor,
            signal=self._last_signal,
            signal_timestamp=(
                self._candles[self._cursor - 1].timestamp
                if self._cursor > 0
                else None
            ),
            execution_bar=None,
            closed=closed,
            opened=None,
            finished=True,
        )

    def _assert_identities_unchanged(self) -> None:
        """Re-check config, costs and dataset after every step.

        Structurally redundant for a tuple of frozen dataclasses, which is exactly
        why it is cheap insurance: a mutation that somehow became possible would
        raise here instead of producing a run whose halves used different
        assumptions. Mirrors ``walkforward.py:632-648``.
        """

        if config_hash(self._config) != self._config_hash:
            raise ReplayError(
                "strategy configuration changed during the replay"
            )

        if costs_hash(self._costs) != self._costs_hash:
            raise ReplayError("execution costs changed during the replay")

        if dataset_fingerprint(self._candles) != self._fingerprint:
            raise ReplayError("dataset changed during the replay")