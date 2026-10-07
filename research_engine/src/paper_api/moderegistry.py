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
from crypto_paper_lab.execution import IntelligencePolicy
from crypto_paper_lab.intelligence import IntelligenceConfig
from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_MODE,
    DEFAULT_THRESHOLD,
    MODES,
    ModeNotAvailableError,
    ModeSpec,
    mode_policy,
    mode_spec,
)
from crypto_paper_lab.replay import Replay, ReplayState, STATE_FINISHED
from crypto_paper_lab.walkforward import baseline_config, phase13_costs

from .marketdata import dataset_identity, load_research_candles
from .replaysession import ReplaySession
from .session import PaperSession

__all__ = [
    "ALERTS",
    "AiSession",
    "ModeRegistry",
]


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

        return ReplaySession(
            Replay(
                load_research_candles(),
                config=baseline_config(),
                costs=phase13_costs(),
                policy=mode_policy(mode),
                dataset_sha256=dataset_identity(),
            )
        )