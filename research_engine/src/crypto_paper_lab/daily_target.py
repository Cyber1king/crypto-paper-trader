"""Daily Target: trade each UTC day until its realized paper P&L target is met (24A/24B).

The mode contract
-----------------

Daily Target runs the **same** frozen strategy as every other mode and the **same**
:class:`~crypto_paper_lab.simulator.PaperBroker` as Standard. It differs in exactly
one respect: once a UTC calendar day's **realized** paper P&L reaches a configured
target, the mode stops opening new positions for the rest of that day.

That single difference is an **entry decision**, which is what
:class:`~crypto_paper_lab.execution.ExecutionPolicy` already exists to express. So
this module owns no broker, computes no price, no quantity, no fill and no exit. It
adds day bookkeeping, and it supplies one boolean to the policy.

Why no second execution engine
------------------------------

The architecture anticipated this. Daily Target permits **one** position, so
``PaperBroker``'s single-position rule already satisfies it and ``Replay`` is already
the right executor. AI Intelligence needed
:class:`~crypto_paper_lab.ai_paper.AiPaperBook` because it permits several concurrent
positions, which ``PaperBroker`` cannot hold. Daily Target has no such requirement,
so it reuses ``Replay`` and ``PaperBroker`` untouched, and Standard's frozen
344-trade baseline cannot be affected by anything here.

Realized only, never unrealized
-------------------------------

The target is measured as ``broker.cash - day_starting_balance``, which changes only
when a trade closes. That is the engine's own ``net_pnl`` definition and the value
already exposed as ``/api/account.realized_pnl``.

**No mark-to-market value exists anywhere in this module.** A position with a large
unrealized gain does not move the target, because nothing in this engine values an
open position. Phase 16 established that unrealized P&L is not exposed, and this mode
does not invent one to make a target look reachable.

Because the figure is read from ``cash`` after the broker has deducted fees and
slippage, **costs are already inside the measured P&L**. Nothing is subtracted again
here, so a target cannot be declared met by gross profit that friction erased.

Overshoot is guaranteed, and the mode says so
---------------------------------------------

Realized P&L moves in whole trades. A target of +50 with one trade closing at +180
overshoots by +130. There is no partial close in the engine, no scaling out, and no
mechanism to stop at a threshold; engineering one away would be a new exit rule, which
is a research change. So the overshoot is reported honestly rather than smoothed:
:attr:`DailyTargetState.overshoot_possible` is always true and the UI is required to
present the target as a goal that may be overshot.

Day boundaries are UTC calendar days
------------------------------------

The frozen dataset is UTC and its candle timestamps are **naive** values that the
dataset loader *declares* to be UTC. ``candle.timestamp.date()`` on such a value is
therefore already the UTC date: no localization, no user timezone, and no fabricated
24-hour period. The frozen data holds 731 UTC days of exactly 24 bars each, so the
boundary is unambiguous.

Equity carries across day boundaries
------------------------------------

At a new UTC day, ``day_starting_balance`` becomes the **carried** ``broker.cash``. The
account is never reset to its opening figure: resetting daily would erase the record of
what previous days earned.

The **target does not carry, and is not recomputed from the balance.** It is a fixed
dollar amount the user chose (:attr:`DailyTargetTracker.target_amount`), and it stays
the same across day boundaries.

This is a deliberate correction of the Phase 24B design, which derived the target as
``day_starting_balance * target_pct``. That made the objective a *percentage* and
scaled it with the account, so a growing paper account silently demanded more profit
each day. The product requirement is the opposite: the user picks a number of dollars
and wants *that* number, today. A ``$10,000`` account aiming at ``$50`` on day 1 aims
at ``$50`` on day 2 with a ``$10,052`` balance - not ``$50.26``.

The balance still matters, for a different and honest reason: it is reported as the
day's starting point and is what the realized P&L is measured from. Separating "how
much did this day make" from "how much does the user want" is the whole point.

Positions carry across a boundary too
-------------------------------------

An open position is **not** closed at midnight. Force-closing would be a trading
operation, and it would change the very P&L the day is measuring. A position keeps
running, and its eventual P&L lands in whichever day it closes.

Terminology
-----------

This mode must never imply guaranteed returns. :data:`MODE_LABEL`,
:data:`TARGET_NOTE` and :data:`OVERSHOOT_NOTE` exist so the API and the UI repeat the
same non-guarantee wording rather than each inventing their own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date

from .execution import AUTOMATIC_POLICY, DecisionContext, ExecutionPolicy

__all__ = [
    "DAILY_TARGET_POLICY",
    "DEFAULT_TARGET_AMOUNT",
    "MAX_TARGET_AMOUNT",
    "MODE_LABEL",
    "OVERSHOOT_NOTE",
    "TARGET_NOTE",
    "WAITING_NOTE",
    "DailyResult",
    "DailyTargetConfig",
    "DailyTargetPolicy",
    "DailyTargetState",
    "DailyTargetTracker",
]


#: Shown wherever the mode is named. Includes "Paper Trading" so the name never
#: appears in a UI without the word that says what it is.
MODE_LABEL = "Daily Target — Paper Trading"

#: The non-guarantee statement, reused verbatim by the API and the UI so the two
#: cannot drift into different claims.
TARGET_NOTE = (
    "Simulation objective only. Not a guaranteed return, not a forecast, and "
    "not a promise about any future result."
)

#: Overshoot is structural, not incidental. See the module docstring.
OVERSHOOT_NOTE = (
    "Realized paper P&L moves in whole trades, so the target can be overshot. "
    "It is a goal, not a precise threshold."
)

#: The target is an objective, not a signal. This is the single most important
#: sentence the mode can state, because "daily target" otherwise reads as an
#: instruction to trade until a number is hit.
#:
#: The engine's behaviour backs it: entry still requires the frozen strategy's own
#: breakout/retest rules, trend filter and execution rules. Nothing here weakens any
#: of them, so a day with no valid setup ends at ``$0.00`` with the target unreached,
#: and that is a valid outcome rather than a failure.
WAITING_NOTE = (
    "The strategy may wait for valid signals. It will not trade just to reach the "
    "target."
)

#: The default daily objective, in dollars of realized paper P&L.
#:
#: A **convenience**, not a claim. It happens to equal 0.5% of the frozen ``$10,000``
#: demo balance, which is why it is a plausible first number - but nothing derives it
#: from the balance, and nothing recomputes it as the balance moves.
#:
#: Deliberately not fitted to any historical result: a backtest-derived target would
#: smuggle a research conclusion into a UI phase, which is what open question Q6 warns
#: against for High-Risk. It clears one round trip of frozen ``cost_deduction``
#: friction, so it is reachable in principle rather than tuned to be.
DEFAULT_TARGET_AMOUNT = 50.0

#: The largest target a caller may configure.
#:
#: A sanity bound, not a trading rule. It exists so a typo cannot ask for an absurd
#: objective and then look like a broken mode for an entire UTC day; a bound that
#: silently clamped would instead hide the mistake, so out-of-range values are
#: **rejected** rather than trimmed. Set far above any plausible daily objective.
MAX_TARGET_AMOUNT = 1_000_000.0


@dataclass(frozen=True)
class DailyTargetConfig:
    """Every rule that governs Daily Target paper execution.

    A frozen dataclass validated in :meth:`__post_init__`, matching
    :class:`~crypto_paper_lab.ai_paper.AiPaperConfig`. Nothing here is compiled into
    engine logic, so a caller can study a different objective without editing an
    execution path.
    """

    #: The daily objective, in dollars of realized paper P&L.
    #:
    #: A **fixed amount chosen by the user**, independent of the account balance. The
    #: frozen demo balance of ``$10,000`` is not what sets this.
    target_amount: float = DEFAULT_TARGET_AMOUNT

    def __post_init__(self) -> None:
        #: ``NaN`` fails every comparison, so it is rejected here rather than being
        #: caught later as a permanently-unreachable target.
        if not math.isfinite(self.target_amount):
            raise ValueError(
                "target_amount must be a finite number; NaN and infinity are not "
                "targets"
            )

        if self.target_amount <= 0:
            raise ValueError(
                "target_amount must be greater than 0; zero or a negative objective "
                "is either already met by definition or unreachable, and neither is a "
                "meaningful daily goal"
            )

        if self.target_amount > MAX_TARGET_AMOUNT:
            raise ValueError(
                f"target_amount must be at most {MAX_TARGET_AMOUNT}; a larger "
                "objective is far outside any plausible day of this frozen dataset "
                "and is rejected rather than clamped"
            )

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {"target_amount": self.target_amount}


@dataclass(frozen=True)
class DailyResult:
    """One finalized UTC day's outcome.

    Appended when a day is left behind, so the history records **completed** days
    only. The current day is never in here; that is :class:`DailyTargetState`.
    """

    #: The UTC calendar date this day covered.
    date: date

    #: Equity when the day opened, i.e. the carried ``broker.cash``.
    starting_balance: float

    #: Realized paper P&L for the day. Never includes an unrealized amount.
    realized_pnl: float

    #: The dollar objective that applied **on that day**.
    #:
    #: Recorded per day rather than read from the current configuration, because the
    #: user may change the target mid-run. A history that reported today's setting for
    #: a past day would misstate what that day was measured against.
    target_amount: float

    #: Whether the day's realized P&L reached its target.
    reached: bool

    #: How much more this day needed after it closed. Never negative.
    #:
    #: Computed **here**, in the engine, and not by the transport. A day is finalized in
    #: exactly one place, so its arithmetic belongs beside it: a client that derived
    #: ``remaining`` for a past day would be a second implementation that could
    #: disagree with the live one.
    remaining: float

    #: How many trades closed during the day.
    trades_closed: int

    def identity(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "starting_balance": self.starting_balance,
            "realized_pnl": self.realized_pnl,
            "target_amount": self.target_amount,
            "remaining": self.remaining,
            "reached": self.reached,
            "trades_closed": self.trades_closed,
        }


@dataclass(frozen=True)
class DailyTargetState:
    """A read-only projection of the current day's target state.

    Recomputed on demand from the broker's cash and the tracker rather than cached,
    so it cannot drift from the state that produced it. Every field is broker-owned,
    config-derived, or read from the tracker; none is computed here.
    """

    #: The UTC calendar day currently being tracked.
    current_date: date

    #: Equity when the day opened: the carried ``broker.cash``.
    day_starting_balance: float

    #: Realized paper P&L for the day. Costs already deducted by the broker.
    realized_daily_pnl: float

    #: The configured objective in dollars. Fixed, and independent of the balance.
    target_amount: float

    #: Whether the day's realized P&L has reached ``target_amount``.
    target_reached: bool

    #: Finalized days in chronological order. Empty on the first day.
    days_completed: tuple[DailyResult, ...] = ()

    @property
    def remaining(self) -> float:
        """How much more realized profit the day still needs.

        ``max(target_amount - realized_daily_pnl, 0)``. Floored at zero, so an
        overshot or surpassed day reports ``0.00`` rather than a negative amount,
        which would read as "owed back".
        """

        return max(self.target_amount - self.realized_daily_pnl, 0.0)

    @property
    def progress(self) -> float | None:
        """Realized progress toward the target, as a fraction.

        ``None`` when there is no target amount yet. That cannot happen with a
        validated config, but returning ``None`` is honest where a division would
        otherwise raise.
        """

        if self.target_amount <= 0:
            return None

        return self.realized_daily_pnl / self.target_amount

    @property
    def overshoot_possible(self) -> bool:
        """Always true. See the module docstring."""

        return True


class DailyTargetTracker:
    """Day bookkeeping for one Daily Target session. The only mutable state here.

    Holds no broker, no position and no price. It is *told* the current UTC date and
    the broker's cash, and it decides when a day has ended, what the day achieved and
    what the next day's objective is.

    The broker's cash is passed in per call rather than held, so this object cannot
    reach a fill, an exit or a position. It reads one number.
    """

    def __init__(self, config: DailyTargetConfig | None = None) -> None:
        self._config = config or DailyTargetConfig()

        #: The objective that applied when the current day **opened**.
        #:
        #: Snapshotted separately from :attr:`config` so the day keeps the target it
        #: was measured against even if the user changes the configuration mid-day,
        #: and so :meth:`set_target` can decide what to do about that deliberately
        #: rather than by accident.
        self._day_target_amount: float = self._config.target_amount

        #: Whether :meth:`set_target` was called while a day was open. Cleared when a
        #: day begins, so it describes *this* day only.
        self._target_changed_during_day: bool = False

        self._current_date: date | None = None
        self._day_starting_balance: float | None = None
        self._day_realized: float = 0.0
        self._day_reached: bool = False
        self._trades_closed_today: int = 0
        self._completed: list[DailyResult] = []

    # -- introspection ------------------------------------------------------

    @property
    def config(self) -> DailyTargetConfig:
        """The current configuration. The user's chosen target lives here."""

        return self._config

    def set_target(self, target_amount: float) -> DailyTargetConfig:
        """Adopt a new target, in dollars, without disturbing the day.

        This is the whole of the "user changes the target" contract, and it is worth
        stating what it deliberately does **not** do:

        - it does not touch ``realized_daily_pnl``, so earned profit is never
          rewritten;
        - it does not close, resize or otherwise touch any open position;
        - it does not reset the day, the cursor or the history;
        - it does not change the day's starting balance.

        It **does** re-evaluate the current day against the new number, and that is
        the one behaviour with real consequences: if the new target is already at or
        below the realized P&L, the day is marked reached, which blocks new entries
        and pauses auto-run on the next step. That is the arithmetic of the new goal,
        not a side effect - asking for ``$10`` when ``$37`` is already realized has
        genuinely been achieved.

        Raises ``ValueError`` for a non-finite, non-positive or absurdly large
        amount, by constructing a validated :class:`DailyTargetConfig` first. An
        invalid request therefore leaves the previous target in place; it is never
        clamped, because a silently trimmed target would show the user a number they
        did not ask for.

        Returns the new configuration.
        """

        # Validation happens before any mutation, so a rejected request changes
        # nothing at all.
        new_config = DailyTargetConfig(target_amount=target_amount)

        day_was_open = self._current_date is not None

        self._config = new_config
        self._day_target_amount = new_config.target_amount

        if day_was_open:
            self._target_changed_during_day = True

            # Re-evaluate the day against the new objective. A day already marked
            # reached is left alone: it was achieved, and un-reaching it would be
            # rewriting history.
            if not self._day_reached and self._day_realized >= new_config.target_amount:
                self._day_reached = True

        return new_config

    @property
    def target_changed_during_day(self) -> bool:
        """Whether the target was changed while the current day was open.

        False before any day exists, and false again at each new UTC day.
        """

        return self._target_changed_during_day

    @property
    def current_date(self) -> date | None:
        """The UTC day being tracked, or ``None`` before the first bar."""

        return self._current_date

    @property
    def target_reached(self) -> bool:
        """Whether today's target has been met.

        ``False`` before the first bar, because nothing has been traded yet. This is
        the value the policy reads.
        """

        return self._day_reached

    @property
    def days_completed(self) -> tuple[DailyResult, ...]:
        """Finalized days in chronological order."""

        return tuple(self._completed)

    @property
    def remaining(self) -> float:
        """How much more realized profit the day still needs, floored at zero.

        Available before the first bar, because the target is now a fixed user setting
        rather than something derived from a day-opening balance. On an idle replay it
        is the whole target: nothing has been realized yet.
        """

        return max(self.target_amount - self._day_realized, 0.0)

    @property
    def target_amount(self) -> float:
        """The current day's objective in dollars.

        Fixed and independent of the balance, so unlike Phase 24B this is answerable
        before any bar is processed: a user can set a target on an idle session.
        """

        return self._day_target_amount

    def reached_for(self, cash: float) -> bool:
        """Whether ``cash`` would mean today's target is met, right now.

        A **live** comparison against the broker's cash, rather than the latched
        :attr:`target_reached`. This is what closes the same-step reversal edge case
        (Phase 24B).

        The latch is written once, when the tracker observes a bar. The policy,
        however, is consulted *inside* the step that performed the close, before that
        observation runs. So the policy asks this instead, and by then ``cash`` has
        already been raised by the close that just happened. A step that closes a
        trade, crosses the target and then reaches the entry check therefore sees
        ``True`` and refuses to open a replacement.

        Returns ``False`` before a day exists, which matches
        :attr:`target_reached` and is the right answer: with no day-opening balance
        there is no realized figure to compare, so nothing can have been reached.
        """

        if self._day_starting_balance is None:
            return False

        target = self.target_amount

        if target <= 0:
            return False

        return (cash - self._day_starting_balance) >= target

    # -- progression --------------------------------------------------------

    def observe(
        self,
        candle_date: date,
        cash: float,
        *,
        trades_closed: int = 0,
    ) -> bool:
        """Advance the tracker to the bar on ``candle_date``.

        Returns ``True`` when this call crossed a day boundary, so the caller knows a
        day was finalized. Idempotent within a day: after the first bar of a date,
        further bars of that same date change nothing but the running realized
        figure.

        ``trades_closed`` is how many trades closed on *this* bar. That is what makes
        target detection follow realized P&L: without a close, ``cash`` has not moved
        and no unrealized amount is consulted.
        """

        crossed = self._current_date is not None and candle_date != self._current_date

        if crossed:
            self._finalize()
            self._begin(candle_date, cash)
            return True

        if self._current_date is None:
            self._begin(candle_date, cash)
            return False

        self._current_date = candle_date
        self._day_realized = cash - self._day_starting_balance

        if trades_closed:
            self._trades_closed_today += trades_closed

            # Only a close can reach the target, and the comparison is against cash
            # after costs, so friction cannot be double-counted in the mode's favour.
            if not self._day_reached and self._day_realized >= self.target_amount:
                self._day_reached = True

        return False

    def state(self, cash: float) -> DailyTargetState | None:
        """The current projection, or ``None`` before the first bar.

        ``None`` is honest: before the replay has stepped there is no UTC day and no
        day-opening balance, and inventing either would be a fabricated value.
        """

        if self._current_date is None or self._day_starting_balance is None:
            return None

        return DailyTargetState(
            current_date=self._current_date,
            day_starting_balance=self._day_starting_balance,
            realized_daily_pnl=self._day_realized,
            target_amount=self._day_target_amount,
            target_reached=self._day_reached,
            days_completed=self.days_completed,
        )

    def reset(self) -> None:
        """Forget every day. The next observed bar opens day zero.

        Called on replay reset. The broker is rebuilt by
        :meth:`~crypto_paper_lab.replay.Replay.reset`, so the next day's starting
        balance is read from the fresh broker's cash on the next ``observe`` rather
        than restored from a field held here. That keeps this object from becoming a
        second source of truth for a balance it does not own.

        The **configured target is deliberately preserved**. Reset clears trading
        state - the cursor, the journal, the day history and the P&L - but the target
        is a user setting rather than a result, and a user who resets to start a fresh
        attempt at "$50 today" did not ask for the goal to be forgotten too. Losing it
        would mean re-typing the number after every reset.
        """

        self._current_date = None
        self._day_starting_balance = None
        self._day_realized = 0.0
        self._day_reached = False
        self._trades_closed_today = 0
        self._completed = []
        self._target_changed_during_day = False

        # Re-aligned with the configuration, in case the target was changed while no
        # day was open. Keeping a stale snapshot here would make the first day of a
        # fresh replay report a target the user no longer asked for.
        self._day_target_amount = self._config.target_amount

    # -- internals ----------------------------------------------------------

    def _begin(self, candle_date: date, cash: float) -> None:
        """Open a day at ``cash``.

        ``cash`` is whatever the broker holds: the carried equity at a day boundary,
        or the opening figure at the start of a replay. The account is never reset
        to its opening number; see the module docstring.
        """

        self._current_date = candle_date
        self._day_starting_balance = cash
        self._day_realized = 0.0
        self._day_reached = False
        self._trades_closed_today = 0

        # The new day takes the currently configured target. Not recomputed from the
        # carried balance: the user chose a dollar figure, and that figure applies to
        # every day until they change it.
        self._day_target_amount = self._config.target_amount

        # A fresh day is measured against a single objective, so the mid-day-change
        # flag starts clear again.
        self._target_changed_during_day = False

    def _finalize(self) -> None:
        """Record the day being left behind.

        A no-op before a day exists, because there is nothing to finalize.
        """

        if self._current_date is None or self._day_starting_balance is None:
            return

        self._completed.append(
            DailyResult(
                date=self._current_date,
                starting_balance=self._day_starting_balance,
                realized_pnl=self._day_realized,
                target_amount=self._day_target_amount,
                remaining=max(self._day_target_amount - self._day_realized, 0.0),
                reached=self._day_reached,
                trades_closed=self._trades_closed_today,
            )
        )


@dataclass(frozen=True)
class DailyTargetPolicy(ExecutionPolicy):
    """Act on eligible signals until this UTC day's realized target is met.

    A **decision layer**, like every policy: it holds no balance, no journal, no
    position and no cursor, and it is never given one.

    Entry and exit are deliberately **delegated** to
    :data:`~crypto_paper_lab.execution.AUTOMATIC_POLICY` rather than reimplemented.
    Exit selection in particular is exactly Standard's, so Daily Target closes
    positions on the engine's own rules and never invents an exit. The only thing
    added is one refusal before an entry.

    ``context.daily_target_reached`` is ``None`` for every other mode, and ``None``
    means "the caller is not reporting daily state", so the policy then behaves
    exactly like Standard. Treating an unknown as reached would stop every mode
    unaware of the field; treating it as unreached would make an optional field
    load-bearing.
    """

    name: str = "daily_target"

    def should_enter(self, context: DecisionContext) -> bool:
        if context.daily_target_reached is True:
            return False

        return AUTOMATIC_POLICY.should_enter(context)

    def select_exit(self, context: DecisionContext):
        """Standard's exit selection, unchanged. See the class docstring."""

        return AUTOMATIC_POLICY.select_exit(context)

    def identity(self) -> dict:
        identity = super().identity()
        identity["target_amount"] = DEFAULT_TARGET_AMOUNT
        return identity


#: Daily Target's policy. A module-level constant, like ``AUTOMATIC_POLICY`` and
#: ``AI_INTELLIGENCE_POLICY``, so ``modes.MODES`` stays a shared constant that every
#: process can hold safely.
DAILY_TARGET_POLICY = DailyTargetPolicy()
