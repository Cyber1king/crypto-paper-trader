"""Manual's session: the only layer that executes a user-requested paper action.

Where this lives, and why not in the engine
-------------------------------------------

:class:`~crypto_paper_lab.replay.Replay._advance` always evaluates an exit and then an
entry from *the strategy's* signal. Manual's trades come from the user, so they cannot
be expressed there — and they should not be, because adding a branch to ``_advance``
would put a user-controlled path inside the loop that produces every other mode's
research record.

So this session sits beside the replay, exactly as
:class:`~paper_api.moderegistry.DailyTargetSession` sits beside its tracker, and it does
three things the engine does not:

1. accepts a user action and validates it,
2. holds it as a **pending intent** until the replay reaches a bar to fill against,
3. fills it through the *existing* broker methods.

Every financial quantity still comes from :class:`~crypto_paper_lab.simulator.PaperBroker`:
the fill price from ``_fill_price``, the quantity from ``open_from_signal``, the fees,
slippage, realized P&L and journal entry from ``close``. This module computes no money
value at all.

An action is an intent
----------------------

The user submits a side and a size. The fill price — the **open of the next execution
candle** — does not exist yet, and on the frozen data it is genuinely unknowable: the
cursor-22 execution bar opens at 43,679.7 while the last *visible* bar closed at
43,679.8.

So the action is recorded and consumed by the next :meth:`ManualSession.step`. That is
what keeps the mode causally valid: the fill is the engine's next bar's open, never the
current bar's close, never a later bar, never a price computed here.

Ordering within a step
----------------------

:meth:`step` performs, in order:

1. the pending intent's fill, at ``candles[cursor].open`` — the bar the engine is about
   to execute;
2. the replay's own step, which consumes that same bar.

Filling **before** the step is what makes the preview truthful. The price shown to the
user and the price actually paid are then the same number, because both are
``candles[cursor].open`` read through the engine's own ``state.cursor``.

The alternative — filling after the step, against ``candles[cursor + 1]`` — was measured
and rejected: the preview would then advertise ``candles[cursor].open`` (43,679.70)
while the trade filled at ``candles[cursor + 1].open`` (43,584.00), a 0.2% difference
the user has no way to distinguish from a broken quote. An honest preview is worth more
than a tidier call order.

This is also exactly what the engine itself does. ``Replay._maybe_enter`` fills at
``execution_bar.open`` where ``execution_bar`` is ``candles[cursor]``, having computed
its signal from ``candles[:cursor]``. A manual entry fills at the same bar, at the same
price, with the same causality — it is simply triggered by the user rather than by a
signal.

The user has seen only bars strictly before ``cursor``; ``candles[cursor]``'s *open* is
disclosed as a preview and its high, low and close are not read at all until the engine
consumes the bar.

One pending action
------------------

Exactly one. Two intents on one bar would need two fills at one price and would make
"which one happened" unanswerable in the journal, so a second request while one is
pending replaces it — announced in the response rather than applied silently.

Isolation
---------

One session, one replay, one broker. Nothing here references another mode's session, so
Phase 17F's structural isolation holds by construction rather than by discipline.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from fastapi import HTTPException

from crypto_paper_lab.manual_paper import (
    MANUAL_EXIT_REASON,
    MANUAL_REASON,
    MODE_LABEL,
    ManualAction,
    ManualActionError,
    ManualConfig,
    ManualIntent,
    ManualReversalError,
    action_requires_position,
    action_requires_size,
    coerce_size_pct,
    parse_action,
)
from crypto_paper_lab.models import Candle, Signal
from crypto_paper_lab.replay import (
    STATE_FINISHED,
    ReplayError,
    ReplayFinishedError,
    ReplayState,
)

from .replaysession import ReplaySession, _to_http

__all__ = ["ManualState", "ManualSession", "MANUAL_LABEL"]

#: The mode's own label, re-exported so the transport does not have to reach into the
#: engine module for a cosmetic string.
MANUAL_LABEL = MODE_LABEL

#: How an intent that was pending when the replay ran out of data is reported.
DROPPED_ON_FINISH = "the replay reached the end of the dataset before this action could fill"


@dataclass(frozen=True)
class ManualState:
    """A read-only projection of Manual's paper account and pending action.

    Recomputed on demand from the broker and the session's own intent, never cached, so
    it cannot drift from the state that produced it. Holds no computed money value
    beyond the balance and the outstanding notional, both of which are the broker's own
    figures or an arithmetic identity of them.
    """

    #: What the user may do right now, as action names. Derived, never hard-coded, so
    #: the UI cannot offer a button the engine would refuse.
    available_actions: tuple[ManualAction, ...]

    #: The intent waiting for a bar, or ``None``.
    pending_action: ManualIntent | None

    #: ``broker.cash``. Not equity: the engine values no open position.
    paper_cash: float

    starting_balance: float
    realized_pnl: float
    trade_count: int

    #: The open ``PaperTrade``, or ``None``. Serialised by the transport, never
    #: recomputed here.
    open_position: object | None

    #: Closed trades, newest first.
    journal: tuple

    #: Bars the open position has been held, or ``None`` when flat.
    #:
    #: Computed as ``cursor - entry_index``. The ``PaperTrade.bars_held`` field reads
    #: ``0`` for an open position because the engine writes it only at close, so
    #: reading it here would report a false zero.
    bars_held: int | None

    #: The next execution candle's open: a **preview**, never a fill price.
    execution_price_preview: float | None

    execution_bar_timestamp: object | None

    replay: ReplayState

    #: Set when a pending intent was dropped because the replay finished.
    dropped_intent_reason: str | None = None


class ManualSession(ReplaySession):
    """Manual's paper session. One replay, one broker, one pending intent.

    Extends :class:`ReplaySession`, as :class:`AiSession` and
    :class:`DailyTargetSession` do, so it inherits the serialisation lock, the error
    mapping and the lazy construction of the 17,544-candle dataset.

    Unlike AI, it adds **no second book**. Manual permits one position, so
    ``Replay`` and ``PaperBroker`` already satisfy the contract; this class adds exactly
    one thing, the pending intent, and owns no broker of its own.
    """

    def __init__(
        self,
        replay: Replay | None = None,
        candles: tuple | None = None,
        config: ManualConfig | None = None,
    ) -> None:
        """
        Parameters
        ----------
        candles:
            The **same immutable tuple** the replay was built with. Held so an action
            can be filled at the next execution bar's open without reaching into
            ``Replay._candles``. The engine publishes no public accessor for that
            price, and adding one would modify ``replay.py`` for a mode that is not the
            engine's concern.

            Sharing the tuple is safe because it is immutable: frozen ``Candle``
            dataclasses, copied defensively by ``Replay.__init__``. The index used to
            read it comes from the engine's own published ``state.cursor``, so this
            module cannot address a bar the replay has not reached.
        """

        super().__init__(replay)

        self._config = config or ManualConfig()
        self._pending: ManualIntent | None = None
        self._dropped_reason: str | None = None

        #: The cursor a user entry was filled at, or ``None``.
        #:
        #: Recorded here because the engine's own ``Replay.entry_index`` is set only by
        #: ``_maybe_enter``, which a user action deliberately does not go through. It is
        #: what lets ``bars_held`` be a real number rather than the ``0`` the trade
        #: carries while open.
        self._user_entry_index: int | None = None

        self._lock_manual = threading.RLock()

        self._candles = candles

    # -- introspection ------------------------------------------------------

    @property
    def manual_config(self) -> ManualConfig:
        return self._config

    @property
    def pending_action(self) -> ManualIntent | None:
        """The intent waiting for a bar, or ``None``."""

        with self._lock_manual:
            return self._pending

    def attach_replay(self, replay: Replay) -> None:
        """Install an already-built replay, for registry construction.

        Exists for the same reason it does on
        :class:`~paper_api.moderegistry.DailyTargetSession`: the replay is lazily built,
        so a registry that built one first and passed it to ``__init__`` would have to
        close over a *local* variable. If that local were ever a different object from
        the session's own replay, an action would fill against a candle series nothing
        steps, and the mode would appear to trade at a price from nowhere — with no
        error anywhere.

        The candle tuple is **not** taken from the replay here. ``Replay`` exposes no
        public accessor for its series, and reaching into ``_candles`` would be exactly
        the private coupling this design refused elsewhere. The registry holds the same
        immutable tuple it passed to ``Replay`` and supplies it to ``__init__`` directly,
        so the index this session reads is always the engine's own ``state.cursor``.
        """

        with self._lock:
            with self._lock_manual:
                self._replay = replay

    # -- operations ---------------------------------------------------------

    def request(
        self,
        action: object,
        size_pct: object | None = None,
    ) -> ReplayState:
        """Validate a user action and hold it as a pending intent.

        **Validates everything before mutating anything.** A refused request leaves the
        session exactly as it was, including any intent already pending, because the
        checks all run before the intent is stored.

        Nothing is filled here. The intent is consumed by the next :meth:`step`, because
        the price to fill at does not exist until then.

        Raises
        ------
        HTTPException
            409 ``REPLAY_FINISHED``, ``NO_NEXT_CANDLE``, ``POSITION_ALREADY_OPEN``,
            ``NO_POSITION_OPEN``, ``UNSUPPORTED_REVERSAL`` or ``NO_PAPER_CASH``;
            422 ``VALIDATION_ERROR`` for an unknown action or an unusable size.
        """

        with self._lock:
            with self._lock_manual:
                # Parse and size first: an unknown action, a reversal, a missing size
                # or an unusable size are all refused before any replay state is read,
                # so a validation refusal cannot depend on where the replay happens to
                # be. Both are inside one try because both raise
                # ManualActionError, and letting either escape would surface a 500 for
                # what is plainly a bad request.
                try:
                    parsed = parse_action(action)

                    if action_requires_size(parsed):
                        size = coerce_size_pct(size_pct, self._config)
                    else:
                        if size_pct is not None:
                            raise ManualActionError(
                                f"{parsed} takes no size_pct; a size on an exit "
                                "would be ignored, and ignoring it would hide a "
                                "request the user did not mean"
                            )

                        size = None

                except ManualReversalError as error:
                    raise self._refusal(
                        "UNSUPPORTED_REVERSAL", 409, str(error)
                    ) from error
                except ManualActionError as error:
                    raise self._refusal(
                        "VALIDATION_ERROR", 422, str(error)
                    ) from error

                self._assert_action_is_possible(parsed)

                replaced = self._pending

                self._pending = ManualIntent(parsed, size)

                # Announced rather than applied silently: a second request on the same
                # bar replaces the first, and the user is told which one it was.
                self._dropped_reason = (
                    f"a pending {replaced.action} was replaced by this request"
                    if replaced is not None
                    else None
                )

                return self.replay.state

    def cancel(self) -> ReplayState:
        """Discard the pending intent, if any.

        No automatic expiry, so a request made while the replay sat idle would
        otherwise survive indefinitely. Cancellation is the user's way out, and it is
        idempotent: cancelling with nothing pending is not an error, because a cancel
        button should never fail.
        """

        with self._lock:
            with self._lock_manual:
                self._pending = None
                self._dropped_reason = None

                return self.replay.state

    # The engine's error translation is re-exported so the Manual routes raise the
    # same shape for engine refusals (POSITION_OPEN on reset, REPLAY_FINISHED) as every
    # other route, without each one importing it separately.
    _to_http = staticmethod(_to_http)

    def step(self) -> ReplayState:
        """Fill the pending intent, then advance one bar.

        The order is load-bearing:

        1. the intent fills at ``candles[cursor].open`` — the bar the engine is about
           to execute, which is the same bar the preview advertised;
        2. ``replay.step()`` consumes that bar. ``ManualPolicy`` refuses both directions,
           so this moves market data and trades nothing.

        Filling after the step instead would fill at ``candles[cursor + 1].open`` and
        make the preview wrong by one bar. See the module docstring.
        """

        with self._lock:
            with self._lock_manual:
                filled = self._consume_pending()

                if filled is not None:
                    self._fill(filled)

            return self._call(self.replay.step)

    def reset(self) -> ReplayState:
        """Rewind the replay and forget every Manual action and trade.

        Delegates through :class:`ReplaySession` so the engine's typed errors become
        409s: ``POSITION_OPEN`` is **not** weakened. A reset that closed a position
        would be a trading operation, and the Phase 22 audit found a discarded close
        worse than an honest refusal.

        Clears the journal (the broker is rebuilt by the engine), the realized P&L, the
        pending intent and the dropped-intent note. Preserves :attr:`manual_config`,
        because a size ceiling is a mode property and not a result.
        """

        with self._lock:
            with self._lock_manual:
                # The engine's reset runs first so a refusal leaves the session
                # untouched, including a pending intent.
                state = super().reset()

                self._pending = None
                self._dropped_reason = None
                self._user_entry_index = None

                return state

    def snapshot(self) -> ReplayState:
        """Current replay state. Manual figures live on :meth:`manual_state`."""

        with self._lock:
            return self.replay.state

    # -- projection ---------------------------------------------------------

    def manual_state(self) -> ManualState:
        """The authoritative Manual projection. Never cached."""

        with self._lock:
            with self._lock_manual:
                replay = self.replay
                state = replay.state
                broker = replay.broker

                bar = self._execution_bar(state)

                pending = self._pending

                return ManualState(
                    available_actions=self._available_actions(state),
                    pending_action=pending,
                    paper_cash=broker.cash,
                    starting_balance=broker.starting_balance,
                    realized_pnl=broker.cash - broker.starting_balance,
                    trade_count=len(broker.journal),
                    open_position=broker.open_trade,
                    journal=tuple(reversed(broker.journal)),
                    bars_held=self._bars_held(state),
                    execution_price_preview=(bar.open if bar is not None else None),
                    execution_bar_timestamp=(bar.timestamp if bar is not None else None),
                    replay=state,
                    dropped_intent_reason=self._dropped_reason,
                )

    # -- internals ----------------------------------------------------------

    def _assert_action_is_possible(self, action: ManualAction) -> None:
        """Refuse an action the current state cannot support.

        Every check runs before the intent is stored, so a refusal mutates nothing.
        """

        state = self.replay.state

        if state.status == STATE_FINISHED:
            raise self._refusal(
                "REPLAY_FINISHED",
                409,
                "the manual replay has reached the end of the dataset; reset it "
                "before acting again",
            )

        if not state.next_candle_available:
            raise self._refusal(
                "NO_NEXT_CANDLE",
                409,
                "no execution candle remains, so an action could not fill; reset the "
                "replay to act again",
            )

        if action_requires_position(action):
            if not state.has_open_position:
                raise self._refusal(
                    "NO_POSITION_OPEN",
                    409,
                    "there is no open paper position to exit; an exit is refused "
                    "rather than invented as a flat trade",
                )

            return

        # An entry.
        if state.has_open_position:
            raise self._refusal(
                "POSITION_ALREADY_OPEN",
                409,
                "a paper position is already open; exit it before entering the "
                "opposite side, because a direct reversal is not supported",
            )

        if self.replay.broker.cash <= 0:
            # Reachable only because the user chose the size: Standard's 1% sizing
            # cannot drive cash this low, but 100% can. Refusing here rather than
            # inheriting the question by accident.
            raise self._refusal(
                "NO_PAPER_CASH",
                409,
                "paper cash is zero or below after realised losses; there is no cash "
                "left to commit to a position, and this engine has no credit facility",
            )

    def _consume_pending(self) -> ManualIntent | None:
        """Take the intent this step will fill, or ``None``.

        A replay that has finished, or that has no bar left, cannot fill anything — so
        an intent still pending is dropped rather than silently carried into a session
        that can never step again. The drop is reported, because an action the user
        requested and never received is exactly the kind of thing a paper tool must not
        swallow.
        """

        pending = self._pending

        if pending is None:
            return None

        state = self.replay.state

        self._pending = None

        if state.status == STATE_FINISHED or not state.next_candle_available:
            self._dropped_reason = DROPPED_ON_FINISH
            return None

        self._dropped_reason = None

        return pending

    def _fill(self, intent: ManualIntent) -> None:
        """Fill one intent against the next execution bar, through the broker.

        This is the only place a Manual trade is created, and it calls nothing but the
        engine's own two methods.
        """

        replay = self.replay
        state = replay.state
        bar = self._execution_bar(state)

        if bar is None:  # pragma: no cover - guarded by _consume_pending
            raise self._refusal(
                "NO_NEXT_CANDLE",
                409,
                "no execution candle remains, so the action could not fill",
            )

        broker = replay.broker

        if intent.action == "EXIT":
            held = self._bars_held(state) or 0
            self._user_entry_index = None

            trade = broker.close(bar.open, bar.timestamp)

            # The broker does not write these; Replay._maybe_exit does, and this close
            # happened outside a step.
            trade.exit_reason = MANUAL_EXIT_REASON
            trade.bars_held = held

            return

        side = "long" if intent.action == "ENTER_LONG" else "short"

        signal = Signal(
            timestamp=bar.timestamp,
            side=side,
            reason=f"{MANUAL_REASON} ({intent.action})",
            # The engine's fill price comes from this. Under `cost_deduction` the fill
            # equals it; under `fill_price` the broker applies spread and slippage to
            # it. Either way the broker decides the price actually paid.
            price=bar.open,
            # Support and resistance come from the same bar, so they describe the
            # execution bar rather than asserting a level the engine never computed.
            support=bar.low,
            resistance=bar.high,
            trend=(
                "up" if bar.close >= bar.open
                else "down" if bar.close < bar.open
                else "sideways"
            ),
            # Every strategy feature is left None. A manual entry has no signal behind
            # it, so recording a trend state, a volatility or a breakout distance would
            # be fabricating data the engine never produced. `PaperBroker` already
            # treats None as "not applicable" for a trade.
        )

        broker.open_from_signal(signal, risk_fraction=float(intent.size_pct))

        # The cursor this entry filled against, which is the bar the user acted on.
        self._user_entry_index = state.cursor

        # Replay._entry_index is what makes its own `_maybe_exit` live. It stays None
        # here, which is correct and redundant: `ManualPolicy.select_exit` returns None
        # regardless, so no exit can fire even if a future engine change set it. The
        # field is private and deliberately not touched - reaching into it would be the
        # coupling Phase 25A rejected.

    def _execution_bar(self, state: ReplayState) -> Candle | None:
        """The bar the next step will execute, or ``None`` at the end of the data.

        Addressed as ``candles[state.cursor]``, using the engine's own published
        cursor. That index cannot point at a bar the replay has not reached, because
        ``state.next_candle_available`` is exactly ``cursor < len(candles)`` and is
        checked first.
        """

        if not state.next_candle_available or self._candles is None:
            return None

        index = state.cursor

        if index < 0 or index >= len(self._candles):  # pragma: no cover - defensive
            return None

        return self._candles[index]

    def _bars_held(self, state: ReplayState) -> int | None:
        """Bars the open position has been held, or ``None`` when flat.

        Computed rather than read from the trade: ``PaperTrade.bars_held`` is written
        only when a position closes, so it reports ``0`` for every open position — this
        was measured on Standard, where an open position three bars old still reported
        ``0``.

        A user entry never sets ``Replay.entry_index``, because only
        ``Replay._maybe_enter`` does that and the user did not go through it. The bars
        held are therefore counted from the cursor the entry was filled at, which
        :attr:`_user_entry_index` records.
        """

        if not state.has_open_position:
            return None

        opened_at = self._user_entry_index

        if opened_at is None:  # pragma: no cover - defensive
            return None

        return max(state.cursor - opened_at, 0)

    def _available_actions(self, state: ReplayState) -> tuple:
        """Which actions the engine would accept right now.

        Derived by asking the same predicates :meth:`request` uses, so the UI cannot be
        offered a button the engine would refuse. The position check is duplicated
        rather than extracted because the refusal messages differ by action and
        duplicating two short conditionals is clearer than a shared helper returning a
        message.
        """

        if state.status == STATE_FINISHED or not state.next_candle_available:
            return ()

        if state.has_open_position:
            return ("EXIT",)

        if self.replay.broker.cash <= 0:
            return ()

        return ("ENTER_LONG", "ENTER_SHORT")

    @staticmethod
    def _refusal(code: str, status: int, message: str) -> HTTPException:
        """One shape for every Manual refusal.

        Matches the engine's own convention - ``{"detail": {"code", "message"}}`` - so a
        client parses one error shape for the whole API rather than two.
        """

        return HTTPException(
            status_code=status,
            detail={"code": code, "message": message},
        )