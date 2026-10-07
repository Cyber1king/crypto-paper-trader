"""Isolated multi-position paper execution for AI Intelligence (Phase 17G).

Why this module exists
----------------------

Phase 17F gave every mode its own ``PaperBroker``, which is correct and stays
exactly as it is. But one broker holds **one** position: ``open_from_signal``
refuses when ``open_trade`` is set (``simulator.py:79-80``). AI Intelligence's
contract requires several independent paper positions at once, so
:mod:`crypto_paper_lab.ai_paper` is the isolated component that provides them,
rather than a generalised rewrite of ``PaperBroker``.

That is the decision this phase makes explicit, because the alternative was
considered and rejected: making ``PaperBroker`` multi-position would change the
object Standard's frozen results depend on, in the one class whose single-position
rule is what Standard's 344-trade baseline rests on. Standard therefore keeps its
own broker, untouched, and this module owns a *different* shape of position
book. Two components, two jobs, neither a reimplementation of the other.

What is reused, and why that is the important part
-------------------------------------------------

Phase 17A M-4 forbids a mode reimplementing signal generation, sizing, fills or
costs. So this module reuses all of them and adds only the thing that was missing:

* **Signals** come from ``strategy.analyze(candles[:index], config)`` - the
  engine's own function, with the engine's own ``StrategyConfig``. The
  configuration identity recorded here is byte-identical to Standard's, which is
  Phase 17A §9.2's explicit requirement that the strategy is shared.
* **Fills and costs** come from ``PaperBroker``, one broker **per position**.
  Each position's broker is constructed with ``starting_balance`` equal to that
  position's allocated capital and ``risk_fraction`` equal to the allocation
  fraction, so the engine's own ``_fill_price`` and fee arithmetic decide the fill
  price, the quantity, the fees and the P&L. This module never computes a fill.
* **The exit level test** is ``backtest._levels_breached``, *imported* rather than
  reimplemented, for the same reason ``replay.py:76`` imports it.
* **The entry decision** belongs to :class:`IntelligencePolicy`, the Phase 17E
  seam, so "should this signal trade" stays a policy question rather than an
  ``if`` inside an execution loop.

The one thing genuinely new here is *several positions at once*, and the
arithmetic that follows from holding several allocations at once.

Accounting, and why there is exactly one truth
----------------------------------------------

Each position owns a ``PaperBroker`` whose ``starting_balance`` **is** that
position's allocation. So the position's result is the engine's own definition,
``broker.cash - broker.starting_balance``, and :meth:`AiPaperBook.state` reports:

===========================  =========================================
``starting_capital``         configured; unchanged for the book's life
``committed_capital``        sum of allocations held by *open* positions
``realized_balance``         starting capital plus every closed position's
                             net P&L, each read from its own broker
``available_capital``        realized balance minus committed
``realized_pnl``             realized balance minus starting capital
===========================  =========================================

Capital is **committed, never on credit**. A position may only be opened when
``available_capital >= allocation``, and the allocation fraction is capped at
``1.0``, so a position's notional can never exceed the paper cash backing it.
The configuration validator refuses a fraction above ``1.0`` rather than trusting
the caller.

The capital vocabulary is deliberately narrow. ``committed_capital`` is cash
*reserved against an open position*; ``available_capital`` is uncommitted paper
cash. Neither is on-loan funds or venue credit, and neither implies a multiplier
on the cash held. The engine has no live price feed, so anything requiring a mark -
equity, unrealized P&L - would have to be invented, and Phase 17A §5.1 lists those
as fields that must not appear.

No gearing, no credit, no adding to a position
----------------------------------------------

``allocation_fraction > 1.0`` raises. Repeated entries into an existing position
direction are not expressible: every open creates a distinct position with its own
identity, and nothing merges or adds to one. There is no exchange connectivity,
no credential, no wallet and no order concept anywhere in this file.

Paper only. Every figure here is simulated.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

from .backtest import END_OF_DATA, _levels_breached
from .costs import TradingCosts
from .execution import DecisionContext, IntelligencePolicy
from .intelligence import IntelligenceConfig, IntelligenceScore, score_signal
from .models import Candle, PaperTrade, Signal
from .simulator import PaperBroker
from .strategy import StrategyConfig, analyze
from .walkforward import STARTING_BALANCE, phase13_costs

__all__ = [
    "AI_EXIT_END_OF_DATA",
    "AI_EXIT_PROFIT_TARGET",
    "DEFAULT_ALLOCATION_FRACTION",
    "DEFAULT_MAX_POSITIONS",
    "DEFAULT_PROFIT_TARGET_PCT",
    "AiAccountState",
    "AiPaperBook",
    "AiPaperConfig",
    "AiPosition",
    "IntelligenceConfig",
    "IntelligencePolicy",
    "IntelligenceScore",
]

#: Exit reason recorded when the configured profit target is reached on a closed
#: bar. Distinct from the engine's own labels so an AI close is never mistaken for
#: an ``opposite_signal`` or ``take_profit`` in a shared journal. Phase 17A §2.3d
#: notes ``exit_reason`` is an unconstrained ``str``, so no model change is needed.
AI_EXIT_PROFIT_TARGET = "ai_profit_target"

#: Exit reason for a position still open when the dataset ends. Mirrors
#: ``backtest.END_OF_DATA`` for the same situation in the engine.
AI_EXIT_END_OF_DATA = "ai_end_of_data"

#: Default maximum concurrent positions. A documented default, not a constant
#: compiled into the engine: it lives on :class:`AiPaperConfig` and every caller
#: may override it.
DEFAULT_MAX_POSITIONS = 5

#: Fraction of a position's allocation committed as notional.
#:
#: ``1.0`` means "the whole allocation is the position", which is the plainest
#: reading of *allocated paper capital* and involves no credit. The cap is the
#: point: a value above ``1.0`` would commit more notional than the paper cash
#: backing it, and :meth:`AiPaperConfig.__post_init__` refuses it.
DEFAULT_ALLOCATION_FRACTION = 1.0

#: Default profit target, as a fraction of the entry fill price.
#:
#: Justified from the frozen cost model rather than chosen for appearance. Under
#: ``cost_deduction`` with ``phase13_costs()``, a round trip pays fees on both
#: notionals at 0.001 and slippage on both at 0.0005, so total friction is
#: ``2 * (0.001 + 0.0005) = 0.003`` of notional - **0.30%**. Any target at or
#: below that could be reached and still realise a net loss, which would make
#: "close at a profit" untrue. ``0.005`` is the smallest round figure that clears
#: the friction with room to spare. It was not chosen by comparing outcomes, and
#: changing it changes the recorded behaviour, which is why it is configured
#: rather than baked in.
DEFAULT_PROFIT_TARGET_PCT = 0.005


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AiPaperConfig:
    """Every rule that governs AI paper execution. Immutable and hashable.

    None of these defaults is compiled into the engine's logic: each is a field
    here, so a caller can study the mode's sensitivity without editing an
    execution path. :meth:`identity` is what an audit record should carry.
    """

    #: Paper capital allocated to this mode's pool. Its own pool, never carved
    #: out of Standard's (Phase 17A §13). Defaults to the frozen engine figure so
    #: the mode starts where the research record starts.
    starting_capital: float = STARTING_BALANCE

    #: Maximum simultaneously open positions. A qualifying signal beyond this
    #: limit opens nothing; it is not queued, and it is not merged into an
    #: existing position.
    max_positions: int = DEFAULT_MAX_POSITIONS

    #: Close an open position once a closed bar has moved this far in its favour.
    #: See :data:`DEFAULT_PROFIT_TARGET_PCT` for why this default and not another.
    profit_target_pct: float = DEFAULT_PROFIT_TARGET_PCT

    #: Fraction of a position's allocation committed as notional. Capped at 1.0,
    #: because anything higher would commit more notional than cash backs it.
    allocation_fraction: float = DEFAULT_ALLOCATION_FRACTION

    #: Score configuration: the qualification threshold and the component scales.
    intelligence: IntelligenceConfig = field(default_factory=IntelligenceConfig)

    def __post_init__(self) -> None:
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")

        if self.max_positions < 1:
            raise ValueError("max_positions must be at least 1")

        if self.profit_target_pct <= 0:
            raise ValueError("profit_target_pct must be positive")

        # The gearing guard, enforced rather than documented.
        if not 0 < self.allocation_fraction <= 1:
            raise ValueError(
                "allocation_fraction must be between 0 and 1 inclusive; a "
                "fraction above 1 would commit more notional than the paper cash "
                "backing it, and this engine has no credit facility"
            )

        if self.position_allocation <= 0:
            raise ValueError(
                "the capital left for one position must be positive; raise "
                "starting_capital or lower max_positions"
            )

    @property
    def position_allocation(self) -> float:
        """Capital allocated to each position: an equal split of the pool.

        Equal division rather than an arbitrary fixed amount, so the pool is
        always exactly ``max_positions`` allocations wide and the last one cannot
        be starved by an awkward remainder. With five positions and ten thousand,
        that is 2000 each.
        """

        return self.starting_capital / self.max_positions

    @property
    def threshold(self) -> float:
        """Convenience accessor for the intelligence threshold."""

        return self.intelligence.threshold

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {
            "starting_capital": self.starting_capital,
            "max_positions": self.max_positions,
            "profit_target_pct": self.profit_target_pct,
            "allocation_fraction": self.allocation_fraction,
            "position_allocation": self.position_allocation,
            "intelligence": self.intelligence.identity(),
        }

    @property
    def identity_hash(self) -> str:
        """Stable hash of :meth:`identity`, in this project's usual construction."""

        import hashlib

        return hashlib.sha256(
            repr(self.identity()).encode("utf-8")
        ).hexdigest().upper()

    def exit_config(self, strategy: StrategyConfig) -> StrategyConfig:
        """The engine config used **only** for the profit-target level test.

        ``take_profit_pct`` carries the target so ``_levels_breached`` - the
        engine's own function - decides the level, and ``stop_loss_pct`` stays
        ``None`` because Phase 17G defines no stop. The returned config is used
        for nothing except that comparison; the strategy identity this mode
        *records* remains the unmodified one.
        """

        return replace(
            strategy, take_profit_pct=self.profit_target_pct, stop_loss_pct=None
        )


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AiPosition:
    """One AI paper position, open or closed.

    A *snapshot*, like ``ReplayState``: immutable, so two points in time can be
    compared exactly and determinism is testable by equality. The live truth is
    the position's own ``PaperBroker``; this dataclass reports it and adds only
    what a broker does not know - which bar it was entered on, and how much
    capital it holds.
    """

    #: Stable identity. A monotonic counter (``ai-1``, ``ai-2``, ...) rather than a
    #: UUID, so a run is reproducible and a journal can be read in order. Phase 17E
    #: uses ``uuid4`` for a *process* identity, which has nothing to do with being
    #: able to re-derive a position list from the same candles.
    position_id: str

    side: Literal["long", "short"]
    state: Literal["open", "closed"]

    entry_index: int
    entry_timestamp: datetime
    entry_price: float
    quantity: float

    #: Paper capital this position holds. Becomes available again on close.
    allocated_capital: float

    #: What the engine recorded about why this trade opened.
    reason: str

    #: The score that admitted this signal, and the threshold it was judged
    #: against. Retained so a closed position can be audited after the fact
    #: without re-deriving the score from data that has since moved on.
    intelligence_score: int
    qualification_threshold: float

    #: The position's own broker. ``None`` once closed and released, because a
    #: closed position no longer holds capital.
    trade: PaperTrade | None = None

    exit_index: int | None = None
    exit_timestamp: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    bars_held: int | None = None

    #: The engine's own definitions, copied rather than recomputed.
    realized_pnl: float | None = None
    costs: float | None = None

    @property
    def is_open(self) -> bool:
        return self.state == "open"


# ---------------------------------------------------------------------------
# Account state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AiAccountState:
    """Coherent AI paper accounting. Every figure traces to a broker.

    Deliberately absent, because the engine cannot authoritatively produce them:
    ``equity``, ``mark_price``, ``unrealized_pnl``, ``buying_power`` and any
    gearing multiplier. What is here instead is the capital *bookkeeping* the mode
    genuinely owns: what is committed, what is free, what has been realised.
    """

    starting_capital: float
    committed_capital: float
    realized_balance: float
    available_capital: float
    realized_pnl: float

    open_position_count: int
    max_positions: int
    position_allocation: float

    #: Total qualifying signals that found no room: the position limit reached, or
    #: no free capital. Counted rather than logged, because a mode that silently
    #: drops signals is indistinguishable from one that saw none.
    signals_qualified: int = 0
    signals_admitted: int = 0
    signals_declined: int = 0

    @property
    def free_positions(self) -> int:
        """Remaining concurrent slots under the configured limit."""

        return max(0, self.max_positions - self.open_position_count)


# ---------------------------------------------------------------------------
# The book
# ---------------------------------------------------------------------------


class AiPaperBook:
    """The **sole owner** of AI Intelligence position and capital state.

    Holds one ``PaperBroker`` per position, each funded with exactly that
    position's allocation, plus the capital bookkeeping that holding several at
    once implies. Every P&L figure in this class is read out of a broker; none is
    computed here.

    Deterministic by construction: no clock, no randomness, no environment, no
    I/O. The same candles and configuration produce the same positions, in the
    same order, with the same ids, on every process.

    Not thread-safe by itself. A caller driving it from concurrent requests must
    serialise ``step()`` and ``reset()``, exactly as with
    :class:`~crypto_paper_lab.replay.Replay`.
    """

    def __init__(
        self,
        candles,
        config: AiPaperConfig | None = None,
        strategy: StrategyConfig | None = None,
        costs: TradingCosts | None = None,
    ) -> None:
        """
        Parameters
        ----------
        candles:
            The series to walk. Held as a ``tuple`` of frozen ``Candle``
            dataclasses and never mutated, matching ``Replay``.
        config:
            AI execution rules. Defaults to :class:`AiPaperConfig`, which is the
            documented contract.
        strategy:
            The strategy configuration producing signals. Defaults to the frozen
            baseline, so this mode's signal identity is identical to Standard's
            (Phase 17A §9.2).
        costs:
            Execution costs. Defaults to ``phase13_costs()``, the frozen model, so
            the AI mode's fills are costed exactly as the research record's are.
        """

        series = tuple(candles)

        if not series:
            raise ValueError("AI paper execution requires at least one candle")

        self._candles = series
        self._config = config if config is not None else AiPaperConfig()
        self._strategy = strategy if strategy is not None else StrategyConfig()
        self._costs = costs if costs is not None else phase13_costs()
        self._exit_config = self._config.exit_config(self._strategy)

        self._reset_runtime()

    # -- introspection ------------------------------------------------------

    @property
    def config(self) -> AiPaperConfig:
        return self._config

    @property
    def strategy(self) -> StrategyConfig:
        """The shared strategy configuration. Identical to Standard's by design."""

        return self._strategy

    @property
    def policy(self) -> IntelligencePolicy:
        """The policy that decides entries. Phase 17E seam, not an ``if``."""

        return IntelligencePolicy(
            threshold=self._config.intelligence.threshold,
            position_limit=self._config.max_positions,
        )

    @property
    def exit_config(self) -> StrategyConfig:
        """Config used solely for the profit-target level comparison."""

        return self._exit_config

    @property
    def open_positions(self) -> tuple:
        """Open positions in entry order. A snapshot, so it cannot be mutated."""

        return tuple(
            position
            for position in self._order
            if position.state == "open"
        )

    @property
    def positions(self) -> tuple:
        """Every position in entry order, open or closed."""

        return tuple(self._order)

    @property
    def journal(self) -> tuple:
        """Closed positions in close order - the AI equivalent of a journal.

        Appended by :meth:`_close`, which is the only writer, so there is no
        shadow ledger.
        """

        return tuple(self._closed)

    @property
    def last_score(self) -> IntelligenceScore | None:
        """The most recent signal's score, or ``None`` before the first step."""

        return self._last_score

    @property
    def state(self) -> AiAccountState:
        """Capital and position accounting, recomputed from the brokers."""

        open_positions = self.open_positions

        committed = sum(position.allocated_capital for position in open_positions)
        realized = self._config.starting_capital + sum(
            self._broker_for(position).cash - position.allocated_capital
            for position in self._closed
        )

        return AiAccountState(
            starting_capital=self._config.starting_capital,
            committed_capital=committed,
            realized_balance=realized,
            available_capital=realized - committed,
            realized_pnl=realized - self._config.starting_capital,
            open_position_count=len(open_positions),
            max_positions=self._config.max_positions,
            position_allocation=self._config.position_allocation,
            signals_qualified=self._signals_qualified,
            signals_admitted=self._signals_admitted,
            signals_declined=self._signals_declined,
        )

    def broker_for(self, position: AiPosition) -> PaperBroker:
        """The authoritative broker behind one position. Read-only access."""

        return self._broker_for(position)

    # -- mutation -----------------------------------------------------------

    def step(
        self,
        index: int,
        signal: Signal | None = None,
    ) -> AiStepResult:
        """Advance to execution bar ``index``, exiting before entering.

        The caller supplies the index rather than this class holding a cursor, so
        there is exactly one cursor in a mode: the owning session's. Two cursors
        for one series would be two answers to "which bar are we on", and they
        could disagree.

        The ordering is load-bearing and mirrors ``Replay._maybe_exit`` then
        ``Replay._maybe_enter``: exits are evaluated first, so capital freed by a
        close is available to a qualifying signal in the same bar.

        Causality is enforced by the *slice* handed to ``analyze``, exactly as in
        ``Replay._advance``: ``candles[:index]`` cannot contain the execution bar
        or anything after it.

        Parameters
        ----------
        signal:
            The authoritative signal for this bar, when the caller already
            computed one. Supplying it avoids evaluating ``analyze`` twice per bar
            when a :class:`~crypto_paper_lab.replay.Replay` is driving this book.
            Omit it to let the book compute it, which is what makes this class
            usable standalone.

            A supplied signal is **trusted, not verified**: this class does not
            re-derive it to check it matches ``analyze(candles[:index])``, because
            doing so would defeat the reason for accepting it. The only caller that
            supplies one is the AI session, which passes the very signal its replay
            produced for this index.
        """

        if index < 0 or index >= len(self._candles):
            raise IndexError(f"execution bar {index} is outside the series")

        execution_bar = self._candles[index]

        if signal is None:
            signal = analyze(self._candles[:index], self._strategy)

        # The engine's exit rules are never evaluated on the entry bar, and
        # neither are these: a position cannot have moved favourably yet.
        closed = self._maybe_exit(index)

        # ``analyze`` always returns a Signal; ``flat`` is its default branch and
        # is a normal outcome, not an error.
        scored = score_signal(signal, self._config.intelligence)
        self._last_score = scored

        opened = self._maybe_enter(index, signal, scored, execution_bar)

        return AiStepResult(
            execution_index=index,
            signal=signal,
            score=scored,
            execution_bar=execution_bar,
            closed=closed,
            opened=opened,
        )

    def close_open_positions(self) -> tuple:
        """Close every still-open position at the final candle's **close**.

        The end-of-data convention the engine already uses
        (``backtest.py:207-213``, ``replay.py:1098``): the last known price is the
        final bar's close, not its open. Returns the closed positions in close
        order.

        Each closed position also lands in :attr:`journal`, so a caller that wants the
        record must read this return value *or* the journal before anything clears
        them. :meth:`reset` calls this and then clears the journal in the same
        operation, so after a reset the return value is the only surviving account of
        what was closed.
        """

        closed: list[AiPosition] = []
        last = self._candles[-1]

        for position in self.open_positions:
            closed.append(
                self._close(
                    position,
                    price=last.close,
                    timestamp=last.timestamp,
                    index=len(self._candles) - 1,
                    reason=AI_EXIT_END_OF_DATA,
                )
            )

        return tuple(closed)

    def reset(self) -> AiAccountState:
        """Restore the initial allocation with nothing open.

        Two distinct acts, and the second is what makes the first worth doing:

        1. **Every open position is closed first**, at the final candle's close via
           :meth:`close_open_positions`, through the same broker and cost model any
           other exit uses. This releases the capital each position was holding.
           Skipping it would leave ``committed_capital`` outstanding against
           positions that no longer exist.
        2. **The runtime state is then cleared**, by :meth:`_reset_runtime`.

        The close in step 1 is a real, priced close - it computes an exit price, an
        exit reason (``AI_EXIT_END_OF_DATA``) and net realised P&L through
        :meth:`_close` - and all of that lands in :attr:`journal`. **Step 2 then
        discards it**, because it clears ``_closed`` along with everything else.

        So the record of a reset-time close exists for exactly as long as it takes to
        clear the journal, and is not observable afterwards. That is deliberate and
        not a bug: reset is a rewind, and a rewound book has no history. The close is
        performed because *capital accounting* requires it, not because the trade is
        being reported.

        Callers that need to know what a reset closed must read
        :meth:`close_open_positions`'s return value, or capture ``self.state`` before
        calling ``reset``. Nothing is promised to survive this call.

        The dataset is not reloaded and is immutably held, so reset cannot mutate
        it.
        """

        self.close_open_positions()
        self._reset_runtime()

        return self.state

    # -- internals ----------------------------------------------------------

    def _reset_runtime(self) -> None:
        self._order: list[AiPosition] = []
        self._brokers: dict[str, PaperBroker] = {}
        self._closed: list[AiPosition] = []
        self._next_position = 1
        self._last_score: IntelligenceScore | None = None
        self._signals_qualified = 0
        self._signals_admitted = 0
        self._signals_declined = 0

    def _broker_for(self, position: AiPosition) -> PaperBroker:
        return self._brokers[position.position_id]

    def _maybe_exit(self, index: int) -> tuple:
        """Close every open position whose profit target the last closed bar met.

        Only the qualifying positions close. Each is closed on its own evidence, at
        the same execution-bar open every engine exit uses, and other positions are
        left untouched.
        """

        closed: list[AiPosition] = []
        execution_bar = self._candles[index]

        for position in list(self.open_positions):
            bars_held = index - position.entry_index

            # Never on the entry bar: the position cannot have moved yet, and
            # firing on bar one would be the "close whenever price is green"
            # behaviour this phase explicitly rules out.
            if bars_held < 1:
                continue

            # Detection uses the bar that has already closed; the fill is this
            # bar's open. Intrabar fills are never assumed.
            closed_bar = self._candles[index - 1]
            _, target_hit = _levels_breached(
                self._trade_of(position), closed_bar, self._exit_config
            )

            if not target_hit:
                continue

            closed.append(
                self._close(
                    position,
                    price=execution_bar.open,
                    timestamp=execution_bar.timestamp,
                    index=index,
                    reason=AI_EXIT_PROFIT_TARGET,
                )
            )

        return tuple(closed)

    def _maybe_enter(
        self,
        index: int,
        signal: Signal,
        scored: IntelligenceScore | None,
        execution_bar: Candle,
    ) -> AiPosition | None:
        """Open a position if the policy admits this signal and there is room.

        The gates in order, each a question the policy or the capital book
        answers: is the signal directional, does its score reach the threshold, is
        a slot free, is there capital to commit.
        """

        if signal.side not in {"long", "short"}:
            return None

        context = DecisionContext(
            evaluation_index=index,
            signal_side=signal.side,
            signal_reason=signal.reason,
            signal_price=signal.price,
            signal_timestamp=signal.timestamp,
            has_open_position=len(self.open_positions) > 0,
            position_side=None,
            bars_held=None,
            exit_candidates=(),
            risk_fraction=self._config.allocation_fraction,
            intelligence_score=float(scored.score),
            open_position_count=len(self.open_positions),
            available_capital=self.state.available_capital,
        )

        if not scored.qualified:
            return None

        self._signals_qualified += 1

        if not self.policy.should_enter(context):
            self._signals_declined += 1
            return None

        allocation = self._config.position_allocation

        if self.state.available_capital < allocation:
            # No free capital for a whole allocation. Not queued, not partially
            # sized: a fraction of an allocation would be a different contract.
            self._signals_declined += 1
            return None

        return self._open(
            signal=signal,
            scored=scored,
            index=index,
            execution_bar=execution_bar,
            allocation=allocation,
        )

    def _open(
        self,
        signal: Signal,
        scored: IntelligenceScore,
        index: int,
        execution_bar: Candle,
        allocation: float,
    ) -> AiPosition:
        """Open one position on its own broker.

        The broker is funded with exactly this position's allocation, and the
        engine's ``open_from_signal`` computes the fill price, the quantity and
        every downstream cost. Nothing financial is decided in this method.
        """

        broker = PaperBroker(starting_balance=allocation, costs=self._costs)

        # The established execution timing: the signal's price is replaced by the
        # execution bar's open, and its timestamp by that bar's. Identical to
        # ``Replay._maybe_enter`` and ``run_backtest``.
        execution_signal = replace(
            signal,
            timestamp=execution_bar.timestamp,
            price=execution_bar.open,
        )

        trade = broker.open_from_signal(
            execution_signal,
            risk_fraction=self._config.allocation_fraction,
        )

        position = AiPosition(
            position_id=f"ai-{self._next_position}",
            side=trade.side,
            state="open",
            entry_index=index,
            entry_timestamp=trade.entry_time,
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            allocated_capital=allocation,
            reason=trade.reason,
            intelligence_score=scored.score,
            qualification_threshold=scored.threshold,
            trade=trade,
        )

        self._next_position += 1
        self._order.append(position)
        self._brokers[position.position_id] = broker
        self._signals_admitted += 1

        return position

    def _close(
        self,
        position: AiPosition,
        price: float,
        timestamp: datetime,
        index: int,
        reason: str,
    ) -> AiPosition:
        """Close one position and release its capital.

        The broker performs the close and computes every cost; the exit reason and
        bars held are recorded here because the broker does not set them, which is
        the same division of labour ``Replay._maybe_exit`` uses.
        """

        broker = self._broker_for(position)
        trade = broker.close(price, timestamp)

        trade.exit_reason = reason
        trade.bars_held = index - position.entry_index

        closed = replace(
            position,
            state="closed",
            trade=None,
            exit_index=index,
            exit_timestamp=trade.exit_time,
            exit_price=trade.exit_price,
            exit_reason=reason,
            bars_held=trade.bars_held,
            realized_pnl=trade.net_pnl,
            costs=trade.costs,
        )

        # Replace in place so ``positions`` keeps entry order and the open/closed
        # distinction stays derivable from one ordered list.
        for order_index, candidate in enumerate(self._order):
            if candidate.position_id == closed.position_id:
                self._order[order_index] = closed
                break

        self._closed.append(closed)

        return closed

    def _trade_of(self, position: AiPosition) -> PaperTrade:
        """The live trade behind an open position, as the broker holds it."""

        return self._broker_for(position).open_trade


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AiStepResult:
    """What one AI step did.

    ``closed`` and ``opened`` are both frequently populated, for the same reason
    they are in ``Replay``: exits are evaluated before entries, so a bar that
    closes one position can open another from the same bar's signal.
    """

    execution_index: int
    signal: Signal
    score: IntelligenceScore
    execution_bar: Candle
    closed: tuple
    opened: AiPosition | None