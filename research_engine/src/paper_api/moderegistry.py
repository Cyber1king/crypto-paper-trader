"""Registry of isolated per-mode paper sessions, and the AI mode's executor.

Phase 17F built the mapping from mode name to that mode's isolated session.
Phase 17G adds the part that mapping was missing: AI Intelligence cannot be served
by a plain :class:`~crypto_paper_lab.replay.Replay`, because its contract permits
several independent paper positions and ``Replay`` owns exactly one broker with one
open trade.

What the registry holds
-----------------------

Session objects and nothing else. No balance, no cursor, no journal, no position,
no P&L, no AI configuration. Every figure a client sees is read from the session
it was asked about, so there is no aggregate here that could drift out of step
with the state that produced it.

Ownership per mode::

    ModeRegistry
      ├── standard        -> ReplaySession -> Replay     -> PaperBroker
      ├── ai_intelligence -> ReplaySession -> Replay     -> PaperBroker (position 1)
      │                                     AiPaperBook  -> PaperBroker (position N)
      ├── daily_target    -> DailyTargetSession -> Replay -> PaperBroker
      ├── manual          -> ManualSession   -> Replay   -> PaperBroker
      └── (alerts holds no session at all)

Why AI needs a second object, and not a rewritten ``Replay``
------------------------------------------------------------

``Replay`` hard-codes one broker and one ``_entry_index``
(``replay.py:927``, ``replay.py:1031``). Supporting several concurrent positions
means either changing those internals - which would change the object Standard's
frozen 344-trade baseline rests on - or giving AI Intelligence its own position
book. This module takes the second route, and the split is deliberate:

* ``Replay`` remains Standard's executor, untouched.
* ``AiPaperBook`` is AI Intelligence's executor, and the **sole owner** of its
  capital and position state.

The one thing they share is the immutable candle tuple. Two modes reading the same
frozen input is shared *input*, not shared state.

What this module does not do
----------------------------

It dispatches. It never computes a price, a score, a quantity, an exit or a P&L:
AI scoring belongs to :mod:`crypto_paper_lab.intelligence`, fills and costs to
:class:`~crypto_paper_lab.simulator.PaperBroker`, and the entry decision to
:class:`~crypto_paper_lab.execution.IntelligencePolicy`. A registry that started
deciding would be a second accounting truth.
"""
from __future__ import annotations

from crypto_paper_lab.ai_paper import AiAccountState, AiPaperBook, AiPaperConfig
from crypto_paper_lab.daily_target import (
    DAILY_TARGET_POLICY,
    DailyTargetConfig,
    DailyTargetState,
    DailyTargetTracker,
)
from crypto_paper_lab.execution import IntelligencePolicy
from crypto_paper_lab.intelligence import IntelligenceConfig
from crypto_paper_lab.manual_paper import MANUAL_POLICY, ManualConfig
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DAILY_TARGET,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_MODE,
    DEFAULT_THRESHOLD,
    MANUAL,
    MODES,
    ModeNotAvailableError,
    ModeSpec,
    mode_policy,
    mode_spec,
)
from crypto_paper_lab.replay import Replay, ReplayState, STATE_FINISHED
from crypto_paper_lab.walkforward import baseline_config, phase13_costs

from .manualsession import ManualSession
from .marketdata import dataset_identity, load_research_candles
from .replaysession import ReplaySession
from .session import PaperSession

__all__ = [
    "ALERTS",
    "AiSession",
    "DailyTargetSession",
    "MANUAL",
    "ManualSession",
    "ModeRegistry",
]


class DailyTargetSession(ReplaySession):
    """Daily Target's session: a cursor plus one day of target bookkeeping.

    Extends :class:`~paper_api.replaysession.ReplaySession`, as
    :class:`AiSession` does, so it inherits the lock, the error mapping and the lazy
    construction. Unlike AI it adds **no second executor**: Daily Target permits one
    position, so ``Replay`` and its ``PaperBroker`` already satisfy the contract and
    remain the sole owners of the cursor, the capital, the journal and the P&L. This
    class adds exactly one thing, the day tracker, and it owns no broker of its own.

    Why not ``AiPaperBook``
    ----------------------

    AI needed its own book because ``PaperBroker`` holds one open trade and AI permits
    five. Daily Target permits **one**, so ``Replay`` is already correct and reusing it
    is what keeps Standard's frozen 344-trade baseline provably untouched by this
    phase.

    The step order, and the edge case it must handle
    --------------------------------------------------

    :meth:`step` overrides the inherited one so the tracker observes each bar *before*
    the replay's own work, not after:

    1. The tracker observes the bar about to be executed: its UTC date, and the
       broker's cash as it stands **at the start of the step**.
    2. ``replay.step()`` runs the engine's exit, then entry, then moves the cursor.
    3. The tracker observes the same bar again with the cash the step produced, so
       ``realized_daily_pnl`` and ``target_reached`` reflect the close that just
       happened.
    4. If the target was reached and auto-run was armed, the replay is paused.

    Step 1 exists for a specific reason, and getting the order wrong is a real bug
    rather than a theoretical one. 343 of the 344 trades in the frozen baseline are
    **same-bar reversals**: one step closes a position and immediately opens another at
    the same execution-bar open. So a step can close a trade, push realized P&L past
    the target, and reach ``_maybe_enter`` in the same iteration.

    If the tracker only observed *after* ``replay.step()``, the policy would ask it
    mid-step, find the pre-close value, and open the replacement position — trading
    again immediately after the day's objective was met. That is precisely the edge
    case Phase 24B calls out, and it was reproduced before this ordering was chosen:
    the step that reached the target still opened a new position.

    Observing *before* the step does not by itself fix it either, because the close
    happens inside the step. So the hook the policy reads is not the tracker's latched
    flag but a **live** recomputation against the broker's current cash
    (:meth:`daily_target_reached`), which the close has already raised by the time
    ``_maybe_enter`` asks. Both are needed: the pre-step observe establishes the day
    and its opening balance, and the live recomputation makes the just-closed P&L
    visible to the very next decision in the same step.

    The tracker's own ``target_reached`` latch is then kept in step for the *next*
    step and for the API, so the flag is stable rather than recomputed per request.

    No forced close
    ---------------

    Reaching the target does **not** close an open position. Open question Q4 records
    that force-closing would be a trading operation and would change the very P&L
    being measured, so the position is left to exit by the engine's own rules. Only
    *new entries* stop.

    Only this mode is touched
    -------------------------

    Pausing on target affects this replay alone. Manual and High-Risk, and Standard
    and AI, have their own sessions with their own tickers, and Phase 17F makes
    isolation structural: no mode holds a reference to another's session.
    """

    def __init__(
        self,
        replay: Replay | None = None,
        tracker: DailyTargetTracker | None = None,
        daily_target_hook=None,
    ) -> None:
        """``daily_target_hook`` is the policy-facing callback.

        Passed in rather than derived from ``tracker`` because the hook must read a
        **live** comparison against the broker's cash, and the broker belongs to the
        replay. Building the closure here, where both the tracker and the replay are
        in scope, removes any chance of the two being wired to different objects -
        which is the failure this wiring is most prone to.

        Left ``None``, the session derives an equivalent hook from its own replay, so
        a test or an injected builder that constructs the session directly still gets
        correct behaviour.
        """

        super().__init__(replay)

        self._tracker = tracker or DailyTargetTracker()
        self._daily_target_hook = daily_target_hook

    @property
    def daily_target_hook(self):
        """The callback injected into the replay for the policy to ask."""

        if self._daily_target_hook is not None:
            return self._daily_target_hook

        return self.daily_target_reached

    def attach_replay(self, replay: Replay) -> None:
        """Install an already-built replay, for registry construction.

        Exists because of a real wiring hazard: the policy's hook has to read
        ``session.replay.broker.cash``, and ``session.replay`` is lazily built. A
        registry that built the replay first and passed it to ``__init__`` would have
        to build a closure over a *local* replay variable, and if that local were ever
        a different object from the session's own the hook would silently read cash
        from a replay nothing steps - producing a mode that appears never to reach its
        target, with no error anywhere.

        Building the session first and attaching afterwards makes the session's
        accessor the single path to the broker, so the two cannot diverge.
        """

        with self._lock:
            self._replay = replay

    # -- introspection ------------------------------------------------------

    @property
    def tracker(self) -> DailyTargetTracker:
        """The day tracker. Created eagerly, because it owns no I/O.

        Unlike :attr:`AiSession.book` this needs no lazy construction: the tracker
        holds no dataset and no broker, so building it costs nothing and a caller
        may read :attr:`daily_state` without forcing the 17,544-candle load that
        ``replay`` would trigger.
        """

        return self._tracker

    @property
    def daily_config(self) -> DailyTargetConfig:
        return self._tracker.config

    @property
    def daily_target_changed_during_day(self) -> bool:
        """Whether the user re-pointed the target while this day was open.

        Reported rather than smoothed over. If the goal moved mid-day then
        ``realized_daily_pnl`` is measured against two different objectives, which is
        legitimate but not something to present as a single clean "target vs
        achieved".
        """

        return self._tracker.target_changed_during_day

    def set_daily_target(self, target_amount: float) -> DailyTargetConfig:
        """Adopt a user-chosen dollar target for subsequent days.

        Validated by :meth:`~crypto_paper_lab.daily_target.DailyTargetTracker.set_target`,
        so a non-finite, zero, negative or absurd value raises ``ValueError`` and
        leaves the previous target in force - never clamped to something the user did
        not ask for.

        Takes no lock, deliberately. It touches only the tracker's own configuration
        and cannot block: a target change must never be refused because a step is in
        flight, or because a position is open. Mutating the tracker mid-step is safe
        because a step only *reads* the target, and the worst interleaving is that a
        step uses the old figure for its entry decision - which is the truthful
        outcome, since the target was still the old one when that step began.

        Returns the new configuration so the caller can echo it back.
        """

        return self._tracker.set_target(target_amount)

    def daily_target_reached(self) -> bool:
        """What the injected ``daily_target`` hook returns.

        A **live** recomputation against the broker's current cash, not the tracker's
        latched flag. That is what makes the Phase 24B edge case correct: the engine
        asks this from inside ``_maybe_enter``, which 343 of the 344 frozen trades
        reach in the *same* step that closed the previous position. By then the close
        has already raised ``broker.cash``, so a target crossed by that very close is
        visible here and the replacement entry is refused.

        Reading the latch instead would answer with the pre-close value and open the
        position, trading again straight after the day's objective was met. That was
        reproduced before this method existed.
        """

        return self._tracker.reached_for(self.replay.broker.cash)

    @property
    def daily_state(self) -> DailyTargetState | None:
        """Today's target projection, or ``None`` before the first step.

        Read from the broker's cash at call time, so it cannot disagree with the
        state that produced it.
        """

        with self._lock:
            return self._tracker.state(self.replay.broker.cash)

    # -- operations ---------------------------------------------------------

    def step(self) -> ReplayState:
        """Advance one bar, then bring the day tracker and auto-run into line.

        See the class docstring for why the replay runs first and the tracker second.
        """

        with self._lock:
            replay = self.replay
            state = replay.state

            if state.status == STATE_FINISHED:
                from .replaysession import _to_http
                from crypto_paper_lab.replay import ReplayFinishedError

                raise _to_http(
                    ReplayFinishedError(
                        "replay has reached the end of the dataset; reset to run "
                        "again"
                    )
                )

            next_date = self._next_bar_date(replay)

            # Before the step, so the day and its opening balance exist before the
            # engine consults the policy. Without this the first step would have no
            # day to measure against.
            if next_date is not None:
                self._tracker.observe(next_date, replay.broker.cash)

            result = replay.step()
            self._sync_session()

            # After the step, so a close that just happened is reflected in
            # ``realized_daily_pnl`` and latches the flag the API reports.
            if next_date is not None:
                self._tracker.observe(
                    next_date,
                    replay.broker.cash,
                    trades_closed=1 if result.closed is not None else 0,
                )

            if self._tracker.target_reached and state.status == "running":
                # Disarm this mode's auto-run only. ``pause`` is idempotent and
                # touches nothing but the status and the ticker, so the cursor, the
                # journal and any open position are exactly as they were.
                self._pause_for_target()

            return replay.state

    def reset(self) -> ReplayState:
        """Rewind the replay and forget every day.

        ``Replay.reset()`` still refuses while a position is open, and that refusal
        is **not** weakened here: force-closing would be a trading operation, and the
        Phase 22 audit established that a reset-time close which is then discarded is
        worse than an honest refusal.

        The tracker is cleared before the replay is reset so that a refusal leaves
        the day history intact alongside the position it would have discarded.

        Delegates through :meth:`ReplaySession.reset` rather than calling
        ``replay.reset()`` directly. That matters: the inherited method funnels the
        engine's typed errors through ``_to_http``, so ``POSITION_OPEN`` becomes a 409.
        Calling the engine here instead would let the exception escape the route and
        surface as a 500 — a real defect this test caught, because the engine-level
        test passes either way.
        """

        with self._lock:
            state = super().reset()

            self._tracker.reset()

            return state

    def snapshot(self) -> ReplayState:
        """Current replay state. Daily figures live on :attr:`daily_state`."""

        with self._lock:
            return self.replay.state

    # -- internals ----------------------------------------------------------

    def _pause_for_target(self) -> None:
        """Stop auto-run because the day's target was met.

        Disarms through ``pause()`` rather than by writing ``_status``, so the
        transition is the engine's own and cannot disagree with it.
        """

        self.replay.pause()

    @staticmethod
    def _next_bar_date(replay: Replay):
        """The UTC date of the bar :meth:`step` is about to execute, or ``None``.

        Taken from ``ReplayState.next_timestamp``, which the engine already publishes
        and which is ``None`` exactly when no bar remains. So the tracker learns the
        day from the same authoritative snapshot the engine acts on, without this
        module reaching into the replay's private candle tuple.

        ``next_candle_available`` is checked as well as the timestamp, because both
        are ``None``/``False`` at the end of the dataset and the timestamp alone would
        raise on the final step rather than returning "no bar". The caller skips
        observation in that case, which is correct: there is no bar whose day could
        change.

        The timestamp is naive and the dataset loader *declares* it UTC, so ``.date()``
        on it is already the UTC date: no localization and no user timezone anywhere in
        this path.
        """

        state = replay.state

        if not state.next_candle_available or state.next_timestamp is None:
            return None

        return state.next_timestamp.date()


class AiSession(ReplaySession):
    """AI Intelligence's session: a cursor plus an isolated position book.

    Extends :class:`~paper_api.replaysession.ReplaySession` rather than replacing
    it, so it inherits the lock, the error mapping and the lazy construction that
    Phase 17D established, and adds exactly what the AI contract needs.

    The two objects have non-overlapping jobs:

    * the inherited ``Replay`` owns the **cursor, status, dataset and strategy
      identity** - the things every mode needs and the Phase 17D routes already
      report;
    * the :class:`~crypto_paper_lab.ai_paper.AiPaperBook` owns **capital,
      positions and realised P&L**.

    The inherited replay's broker stays **permanently flat and its journal
    permanently empty**, and that is asserted by test rather than assumed: the AI
    policy refuses every entry, so the book is the only thing that opens a
    position. Two objects exist here because they answer different questions, not
    because there are two accounts - there is exactly one AI account, and it is
    the book's.

    The inherited ``step()`` is **overridden** so a single call advances both in
    lockstep, in the correct order: exits, then the score, then any entry. Letting
    the transport call ``replay.step()`` and ``book.step()`` separately would let a
    future caller advance one without the other and produce a cursor that disagrees
    with the positions.
    """

    def __init__(
        self,
        replay: Replay | None = None,
        book: AiPaperBook | None = None,
    ) -> None:
        super().__init__(replay)

        self._book = book

    # -- introspection ------------------------------------------------------

    @property
    def book(self) -> AiPaperBook:
        """AI's position and capital book. Constructed on first use.

        Deferred like the replay it sits beside, so creating this session does not
        build a second object graph or read the dataset twice.
        """

        if self._book is None:
            with self._lock:
                if self._book is None:
                    self._book = AiPaperBook(
                        load_research_candles(),
                        config=AiPaperConfig(),
                        strategy=baseline_config(),
                        costs=phase13_costs(),
                    )

        return self._book

    @property
    def ai_state(self) -> AiAccountState:
        """AI's authoritative capital and position accounting."""

        with self._lock:
            return self.book.state

    @property
    def ai_config(self) -> AiPaperConfig:
        return self.book.config

    # -- operations ---------------------------------------------------------

    def step(self) -> ReplayState:
        """Advance one bar, moving the replay and the book together.

        Order matters and is fixed here rather than left to a caller:

        1. the replay advances, which produces the authoritative signal and moves
           the cursor;
        2. the book closes positions whose profit target the last closed bar met;
        3. the book scores the signal and opens a position if it qualifies and
           there is both a free slot and free capital.

        So exits free capital before entries can use it within the same bar, which
        is also the order :class:`~crypto_paper_lab.replay.Replay` uses.

        The signal computed in step 1 is **passed to** the book rather than letting
        the book recompute it, so ``analyze`` runs once per bar and there is exactly
        one signal per index anywhere in this mode.
        """

        with self._lock:
            replay = self.replay
            state = replay.state

            if state.status == STATE_FINISHED:
                # Refuse rather than no-op, matching Replay.step() so the transport
                # maps it to the same 409.
                from .replaysession import _to_http
                from crypto_paper_lab.replay import ReplayFinishedError

                raise _to_http(
                    ReplayFinishedError(
                        "replay has reached the end of the dataset; reset to run again"
                    )
                )

            result = replay.step()

            # One extra call, not a loop: Replay.step() already applied end-of-data
            # closure for itself, and the book closes its own positions at the same
            # bar's close.
            if result.finished:
                self.book.close_open_positions()
            else:
                self.book.step(result.cursor_before, result.signal)

            return replay.state

    def reset(self) -> ReplayState:
        """Rewind AI. Closes open positions, then clears the book.

        ``Replay.reset()`` would refuse while its own position is open - and its
        position is never open, because the AI policy refuses every entry, so that
        refusal cannot fire here. The book has no such refusal: it closes what it
        holds at the final candle's close and only then clears, so capital is never
        left committed against a position that has ceased to exist.

        The close is priced and does record an exit reason and realised P&L, but
        ``AiPaperBook.reset`` clears the journal in the same call, so that record is
        not observable afterwards. Reset is a rewind, not a reporting event; see
        ``AiPaperBook.reset`` for the full statement of what does and does not
        survive.
        """

        with self._lock:
            self.book.reset()
            return self.replay.reset()

    def snapshot(self) -> ReplayState:
        """Current replay state. AI's own accounting lives on :attr:`ai_state`."""

        with self._lock:
            return self.replay.state


class ModeRegistry:
    """Deterministic mode -> isolated session, created once per mode.

    Parameters
    ----------
    session_for:
        Builds the session for a mode. Injectable so tests can supply a prepared
        session without loading the dataset, and so the default construction path
        stays in one place.
    """

    def __init__(self, session_for=None) -> None:
        self._sessions: dict = {}
        self._build = session_for or self._default_session

    # -- introspection ------------------------------------------------------

    def specs(self) -> tuple:
        """Every known mode, available or reserved. Configuration only."""

        return tuple(MODES.values())

    def spec(self, mode: str) -> ModeSpec:
        """Resolve a mode name. Raises for an unknown name."""

        return mode_spec(mode)

    def has_session(self, mode: str) -> bool:
        """Whether a session has been materialised for ``mode`` yet."""

        return mode in self._sessions

    def is_ai(self, mode: str) -> bool:
        """Whether ``mode`` is served by :class:`AiSession`.

        The transport asks this to decide which projection to build, rather than
        testing for a mode name or an attribute. Resolving through
        :func:`mode_spec` means an unknown mode still raises here, as everywhere
        else.
        """

        return mode_spec(mode).mode == AI_INTELLIGENCE

    def is_daily_target(self, mode: str) -> bool:
        """Whether ``mode`` is served by :class:`DailyTargetSession`.

        As with :meth:`is_ai`, the transport asks a question rather than testing for
        a name, and an unknown mode still raises.
        """

        return mode_spec(mode).mode == DAILY_TARGET

    def is_manual(self, mode: str) -> bool:
        """Whether ``mode`` is served by :class:`ManualSession`.

        As with :meth:`is_ai` and :meth:`is_daily_target`: the transport asks a
        question rather than testing for a name, and an unknown mode still raises.
        """

        return mode_spec(mode).mode == MANUAL

    # -- sessions -----------------------------------------------------------

    def session(self, mode: str) -> ReplaySession:
        """The isolated session for ``mode``, created on first use.

        Raises for a reserved mode, and for a brokerless mode - Alerts has no
        session because it has no broker, and manufacturing an empty one would
        imply an execution environment that must not exist.
        """

        spec = self.spec(mode)

        if not spec.available:
            raise ModeNotAvailableError(
                f"mode {mode!r} is reserved: {spec.note}"
            )

        if not spec.supports_execution:
            raise ModeNotAvailableError(
                f"mode {mode!r} has no paper execution session: {spec.note}"
            )

        existing = self._sessions.get(mode)
        if existing is not None:
            return existing

        session = self._build(mode)
        self._sessions[mode] = session

        return session

    def daily_target_session(self) -> "DailyTargetSession":
        """Daily Target's session.

        Raises unless it really is a :class:`DailyTargetSession`, for the same
        reason :meth:`ai_session` does: an injected builder returning a plain session
        would leave the transport with no ``daily_state``, and the failure would
        surface as an ``AttributeError`` inside a route handler — a programming
        error dressed up as a data problem.
        """

        session = self.session(DAILY_TARGET)

        if not isinstance(session, DailyTargetSession):
            raise TypeError(
                f"mode {DAILY_TARGET!r} requires a DailyTargetSession so its daily "
                f"target state has one owner; got {type(session).__name__}"
            )

        return session

    def ai_session(self) -> "AiSession":
        """AI Intelligence's session.

        Raises unless it really is an :class:`AiSession`. A registry built with an
        injected builder that returned a plain session would otherwise hand the
        transport an object with no ``ai_state``, and the failure would surface as
        an ``AttributeError`` inside a route handler - a programming error dressed
        up as a data problem.
        """

        session = self.session(AI_INTELLIGENCE)

        if not isinstance(session, AiSession):
            raise TypeError(
                f"mode {AI_INTELLIGENCE!r} requires an AiSession so its "
                f"positions and capital have one owner; got "
                f"{type(session).__name__}"
            )

        return session

    def manual_session(self) -> "ManualSession":
        """Manual's session.

        Raises unless it really is a :class:`ManualSession`, for the same reason
        :meth:`ai_session` and :meth:`daily_target_session` do: an injected builder
        returning a plain session would leave the transport with no ``manual_state``
        and no way to submit an action, and the failure would surface as an
        ``AttributeError`` inside a route handler - a programming error dressed up as
        a data problem.
        """

        session = self.session(MANUAL)

        if not isinstance(session, ManualSession):
            raise TypeError(
                f"mode {MANUAL!r} requires a ManualSession so its pending action and "
                f"paper state have one owner; got {type(session).__name__}"
            )

        return session

    def standard_session(self) -> ReplaySession:
        """The default mode's session. What the Phase 16/17D routes describe."""

        return self.session(DEFAULT_MODE)

    def paper_session(self) -> PaperSession:
        """The default mode's account projection.

        The Phase 16 endpoints (``/api/account``, ``/api/trades`` and friends) have
        no mode parameter, so they describe Standard. Mode-specific state is read
        from ``/api/replay?mode=...``. The two therefore always agree on the
        default view.
        """

        return self.standard_session().session

    # -- internals ----------------------------------------------------------

    def _default_session(self, mode: str) -> ReplaySession:
        """Build an isolated session for an executable mode.

        Each call constructs a brand-new ``Replay``, and therefore a brand-new
        ``PaperBroker``. Nothing is cloned, copied or shared between modes; the
        only shared object is the immutable candle tuple they all read.
        """

        if self.is_ai(mode):
            return AiSession(
                Replay(
                    load_research_candles(),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    # The policy still has to be passed, because it is what the
                    # replay asks before opening. IntelligencePolicy refuses every
                    # entry - its score gate is evaluated by the book, which owns
                    # the positions - so this replay's own broker stays flat and
                    # the book is the single owner of AI state. See AiSession.
                    policy=IntelligencePolicy(
                        threshold=DEFAULT_THRESHOLD,
                        position_limit=DEFAULT_MAX_POSITIONS,
                    ),
                    dataset_sha256=dataset_identity(),
                )
            )

        if self.is_daily_target(mode):
            # Phase 24B. Tracker first, then the session, then the replay wired to
            # both, so the policy's view and the session's view are the same objects
            # by construction rather than by two closures happening to agree.
            tracker = DailyTargetTracker(DailyTargetConfig())
            session = DailyTargetSession(tracker=tracker)

            # The hook is installed *after* the replay exists, because it reads
            # ``session.replay`` - the deferred, lazily built object. Closing over a
            # local ``Replay`` here would wire the hook to a different object from the
            # one the session steps.
            session.attach_replay(
                Replay(
                    load_research_candles(),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    policy=DAILY_TARGET_POLICY,
                    dataset_sha256=dataset_identity(),
                    # Injected rather than imported, so the replay holds no reference
                    # to the tracker. Reads a **live** comparison against cash, not the
                    # tracker's latch, so a target crossed by this step's own close is
                    # visible to this step's entry check. See ``daily_target_reached``.
                    daily_target=lambda: tracker.reached_for(
                        session.replay.broker.cash
                    ),
                )
            )

            return session

        if self.is_manual(mode):
            # Phase 25B. Manual needs the candle tuple twice: once to build the replay
            # and once for the session to fill an action against the next execution
            # bar, because ``Replay`` publishes no public accessor for that bar's price
            # and reaching into its private series is the coupling this design refused.
            #
            # The tuple is the ``lru_cache``d one every mode already reads, and it is
            # immutable, so handing the same object to both is shared *input* and not
            # shared state. ``load_research_candles`` is not called twice here: the
            # session is built first and given the tuple, then the replay is attached.
            candles = load_research_candles()

            session = ManualSession(
                candles=tuple(candles),
                config=ManualConfig(),
            )
            session.attach_replay(
                Replay(
                    candles,
                    config=baseline_config(),
                    costs=phase13_costs(),
                    # ManualPolicy refuses both an entry and an exit, so this replay
                    # trades nothing on its own and every trade in the mode is the
                    # user's. See crypto_paper_lab.manual_paper for why
                    # DisabledPolicy cannot be used instead.
                    policy=MANUAL_POLICY,
                    dataset_sha256=dataset_identity(),
                )
            )

            return session

        return ReplaySession(
            Replay(
                load_research_candles(),
                config=baseline_config(),
                costs=phase13_costs(),
                policy=mode_policy(mode),
                dataset_sha256=dataset_identity(),
            )
        )