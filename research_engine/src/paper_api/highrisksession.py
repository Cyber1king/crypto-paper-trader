"""High-Risk's session: a replay like every other mode's, plus a settable size.

What lives here, and what does not
----------------------------------

This class adds **one** thing to :class:`~paper_api.replaysession.ReplaySession`:
a mutable ``risk_fraction``. Everything else is inherited.

There is no High-Risk broker, no High-Risk account and no High-Risk P&L. The
session owns a :class:`~crypto_paper_lab.replay.Replay`, which owns a
:class:`~crypto_paper_lab.simulator.PaperBroker`, and that broker books every
fill, quantity, fee, slippage, realized P&L figure and journal entry in the mode.
:class:`HighRiskState` is a **projection** of that broker, recomputed on demand and
never cached, so it cannot drift from the state that produced it.

Why there is no High-Risk policy
--------------------------------

The session does not construct a policy. It reuses
:data:`~crypto_paper_lab.execution.AUTOMATIC_POLICY`, which is the same instance
Standard uses, because High-Risk changes no decision:

* ``should_enter`` - identical. The frozen breakout/retest strategy produces the
  signal and ``AutomaticPolicy`` admits it.
* ``select_exit`` - identical. ``exit_candidates[0]`` is ``opposite_signal`` in
  practice, because the baseline config sets no stop-loss, no take-profit and no
  max-holding bars.
* ``max_positions`` - ``1``, because ``PaperBroker`` holds one ``open_trade``.
* opposite signal - identical close-and-reverse on the same execution bar.

A ``HighRiskPolicy`` overriding all three to delegate would add a class, a
subclassing relationship and a second place for this behaviour to drift, in
exchange for nothing. The registry passes ``AUTOMATIC_POLICY`` so the identity is
literally the same object Standard trades with.

Why changing the size needs a flat session
-------------------------------------------

:meth:`HighRiskSession.set_risk_fraction` refuses while a position is open, with
``409 POSITION_OPEN``.

The reason is consistency, not caution about money. An open position was sized by
the *previous* fraction; changing the setting while it is open would leave a
panel displaying one size above a position committed at another, and nothing in
the broker records which fraction produced the trade. Refusing is the same
contract :meth:`Replay.reset` already uses for the same class of reason - a
refusal the user can see, rather than a state that quietly stops describing
itself.

Sizing applies to the **next** entry. Nothing about the change touches the
cursor, the cash, the journal or the replay identity.

Exposure
--------

:class:`HighRiskState` reports ``paper_exposure`` and ``exposure_fraction``,
derived as ``entry_price * quantity`` from the open trade the broker already
holds.

That is an arithmetic identity over two existing engine fields, computed here so
no client has to. It is deliberately **not** a new broker concept: the engine
holds no position value and reserves no capital, so there is no
reserved-capital or buying-power figure to report. The invariant

    exposure <= paper_cash

holds because :meth:`PaperBroker.open_from_signal` refuses any
``risk_fraction`` above ``1.0`` and computes ``quantity = (cash * fraction) /
fill`` - it is enforced by the broker, before this session sees anything.

Isolation
---------

One session, one replay, one broker, one ``replay_id``. Nothing in this module
references another mode's session, so Phase 17F's structural isolation holds by
construction rather than by discipline. The candle series is immutable and
``lru_cache``d, and is shared as input; no mutable account or replay state is.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace

from fastapi import HTTPException

from crypto_paper_lab.high_risk import (
    DEFAULT_RISK_FRACTION,
    HIGH_RISK_CAUTION,
    HIGH_RISK_INHERITS_NOTE,
    HIGH_RISK_NOTE,
    MAX_RISK_FRACTION,
    MODE_LABEL,
    HighRiskConfig,
    HighRiskError,
    coerce_risk_fraction,
)
from crypto_paper_lab.replay import Replay, ReplayState, STATE_FINISHED

from .replaysession import ReplaySession

__all__ = [
    "HIGH_RISK_LABEL",
    "HighRiskSession",
    "HighRiskState",
]

#: The mode's own label, re-exported so the transport does not have to reach into
#: the engine module for a cosmetic string.
HIGH_RISK_LABEL = MODE_LABEL


@dataclass(frozen=True)
class HighRiskState:
    """A read-only projection of High-Risk's paper account and configuration.

    Recomputed on demand from the broker and this session's own configuration,
    never cached, so it cannot disagree with the state that produced it. Holds no
    computed money value beyond the broker's own balance and the exposure
    identity described in the module docstring.
    """

    #: The share of cash committed per position, right now.
    risk_fraction: float

    #: The engine's hard ceiling, so a client can bound its own input.
    max_risk_fraction: float

    #: ``broker.cash``. Not equity: the engine values no open position.
    paper_cash: float

    starting_balance: float

    #: ``broker.cash - broker.starting_balance`` - the engine's own definition.
    realized_pnl: float

    trade_count: int

    #: The open ``PaperTrade``, or ``None``. Serialised by the transport, never
    #: recomputed here.
    open_position: object | None

    #: ``entry_price * quantity`` of the open trade, or ``0.0`` when flat.
    #:
    #: The identity that makes exposure reportable without inventing a
    #: broker-level concept. Always ``<= paper_cash``.
    exposure: float

    #: ``exposure / paper_cash``, or ``0.0`` when flat or with no cash.
    exposure_fraction: float

    #: Always ``0`` or ``1``. Stated as a count because "how many positions am I
    #: in" is a question a user asks, and the answer is a bounded integer rather
    #: than a derived quantity.
    position_count: int

    #: Exit-reason tally from ``Replay``, which owns it. ``opposite_signal`` and
    #: ``end_of_data`` are the only keys the frozen baseline can produce.
    exit_counts: dict

    last_signal: object | None

    #: ``AUTOMATIC_POLICY.max_positions``, surfaced so the mode's one-position
    #: limit is visible rather than implied.
    max_positions: int

    replay: ReplayState

    #: The scope statement, served so a client cannot drop it.
    inherits_note: str

    #: The caution note. Research documentation made available to the UI.
    caution: str


class HighRiskSession(ReplaySession):
    """High-Risk's paper session. One replay, one broker, one settable size.

    Extends :class:`~paper_api.replaysession.ReplaySession`, as
    :class:`~paper_api.moderegistry.AiSession`,
    :class:`~paper_api.moderegistry.DailyTargetSession` and
    :class:`~paper_api.manualsession.ManualSession` do, so it inherits the
    serialisation lock, the error translation and the lazy construction of the
    17,544-candle dataset.

    Unlike AI, it adds no second book: the mode permits one position, so
    ``Replay`` and ``PaperBroker`` already satisfy the contract. The only thing
    this class owns beyond a session is the size.
    """

    def __init__(
        self,
        replay: Replay | None = None,
        config: HighRiskConfig | None = None,
    ) -> None:
        """
        Parameters
        ----------
        replay:
            Built lazily by the registry and installed by
            :meth:`attach_replay`, exactly as for Manual and Daily Target. A
            registry that built a replay and passed it positionally would have to
            close over a *local* variable; if that local were ever a different
            object from the session's own replay, this mode would appear to trade
            against a candle series nothing steps, with no error anywhere.
        config:
            The mode's configuration. Defaults to
            :class:`~crypto_paper_lab.high_risk.HighRiskConfig`, i.e. a 0.25
            risk fraction.
        """

        super().__init__(replay)

        self._config = config or HighRiskConfig()
        self._lock_high_risk = threading.RLock()

    # -- introspection ------------------------------------------------------

    @property
    def high_risk_config(self) -> HighRiskConfig:
        return self._config

    @property
    def risk_fraction(self) -> float:
        return self._config.risk_fraction

    def attach_replay(self, replay: Replay) -> None:
        """Install an already-built replay, for registry construction.

        Exists for the same reason it does on
        :class:`~paper_api.manualsession.ManualSession` and
        :class:`~paper_api.moderegistry.DailyTargetSession`: the replay is built
        lazily, so a registry that built one first would have to close over a
        local variable.
        """

        with self._lock:
            with self._lock_high_risk:
                self._replay = replay

    # -- operations ---------------------------------------------------------

    def set_risk_fraction(self, value: object) -> HighRiskConfig:
        """Set the share of cash each future position commits.

        **Validates everything before mutating anything.** A refused request
        leaves the session exactly as it was, including its configuration,
        because every check runs before the new configuration is stored.

        Refused while a position is open: the open trade was sized by the
        previous fraction, and nothing in the broker records which fraction
        produced it, so accepting the change would leave the reported
        configuration inconsistent with the position it is displayed above.

        Applies to the **next** entry. The cursor, cash, realized P&L, journal,
        open position and replay identity are all untouched by a successful
        change.

        Raises
        ------
        HTTPException
            ``409 POSITION_OPEN`` if a position is open;
            ``422 VALIDATION_ERROR`` for an unusable value.
        """

        with self._lock:
            with self._lock_high_risk:
                try:
                    fraction = coerce_risk_fraction(value)
                except HighRiskError as error:
                    raise self._refusal(
                        "VALIDATION_ERROR", 422, str(error)
                    ) from error

                if self.replay.state.has_open_position:
                    raise self._refusal(
                        "POSITION_OPEN",
                        409,
                        "risk_fraction cannot be changed while a paper position is "
                        "open: that position was sized by the current fraction, and "
                        "changing it now would report one size above a position "
                        "committed at another. Exit or reset first",
                    )

                self._config = HighRiskConfig(risk_fraction=fraction)

                self._apply_risk_fraction(fraction)

                return self._config

    def _apply_risk_fraction(self, fraction: float) -> None:
        """Push a new fraction into the live :class:`Replay`.

        Why this exists, and why it is safe
        -----------------------------------

        ``Replay`` takes ``risk_fraction`` as a constructor argument and stores it
        once. It has **no public setter**, and Phase 26B must not modify
        ``replay.py``. A session whose configuration could not reach its own
        replay would report a fraction that never affected a single position - the
        one failure a configurable mode cannot have.

        So the value is written to the replay. Three facts make that safe:

        1. **The write happens only while flat.** :meth:`set_risk_fraction` refuses
           above a position being open, so no existing trade was sized by the old
           fraction. There is no position to disagree with the new setting.
        2. **``risk_fraction`` is outside the engine's own immutability
           contract.** ``Replay._assert_identities_unchanged`` re-checks the
           strategy config hash, the costs hash and the dataset fingerprint on
           every step - and deliberately not ``risk_fraction``. The engine treats a
           size as a mode setting rather than as an identity of the run.
        3. **It is read in exactly two places**, both in ``Replay``: passed to
           ``PaperBroker.open_from_signal`` to size a *new* position, and copied
           into ``DecisionContext.risk_fraction`` for a policy to read.
           ``AutomaticPolicy`` reads neither. No fill, price, fee or journal entry
           is affected.

        ``_execution_identity`` is refreshed alongside it so the fraction reported
        by ``/api/replay?mode=high_risk`` cannot silently lag the fraction in force.
        A stale identity here would be a visible contradiction on the dashboard,
        and ``dataclasses.replace`` is how this codebase updates a frozen
        dataclass elsewhere.

        This is the one private touch in the mode, and it is documented as such
        rather than hidden. The alternative - rebuilding the ``Replay`` - is
        worse: ``Replay`` constructs its own broker in ``_reset_runtime``, so a
        rebuild would discard the cash, the journal and the starting balance that
        the contract requires a configuration change to preserve.
        """

        replay = self.replay

        replay._risk_fraction = fraction
        replay._execution_identity = replace(
            replay._execution_identity, risk_fraction=fraction
        )

    def snapshot(self) -> ReplayState:
        """Current replay state. High-Risk figures live on :meth:`high_risk_state`."""

        with self._lock:
            return self.replay.state

    def reset(self) -> ReplayState:
        """Rewind the replay, preserving the configured risk fraction.

        Delegates through :class:`ReplaySession` so the engine's typed errors
        become 409s - ``POSITION_OPEN`` is **not** weakened. A reset that closed
        a position would be a trading operation.

        Preserves :attr:`high_risk_config`, because a size ceiling is a mode
        property and not a result. Clearing it would mean a user who studied a
        size and reset the replay silently got a different experiment.
        """

        with self._lock:
            with self._lock_high_risk:
                return super().reset()

    def available_entries(self) -> bool:
        """Whether a new position could be opened right now.

        ``False`` at the end of the data, and ``False`` with no paper cash.

        The cash check exists because :meth:`PaperBroker.open_from_signal`
        validates only ``risk_fraction``, never the account: with ``cash == 0``
        it computes ``quantity = 0`` and returns a **zero-quantity trade** rather
        than refusing. A position of nothing is not a small position, and letting
        one reach the journal would report a fill that committed no capital while
        still charging its round-trip costs against a later balance.

        So the mode checks what the broker does not. It is unreachable at
        Standard's sizing and was unreachable across a full run at 100% sizing in
        Phase 26A, which is why it is a guard rather than a modelled outcome.
        """

        state = self.replay.state

        if state.status == STATE_FINISHED:
            return False

        if not state.next_candle_available:
            return False

        if state.has_open_position:
            return False

        return self.replay.broker.cash > 0.0

    def _assert_can_trade(self) -> None:
        """Refuse an entry the current state cannot support.

        Every check runs before anything is mutated, so a refusal leaves the
        session exactly as it was.

        ``REPLAY_FINISHED`` and ``NO_NEXT_CANDLE`` are the engine's own refusals,
        restated here in the engine's vocabulary because this is the single place
        a High-Risk entry decision is made. ``NO_PAPER_CASH`` is the one the
        broker does not make for itself - see :meth:`available_entries`.
        """

        state = self.replay.state

        if state.status == STATE_FINISHED:
            raise self._refusal(
                "REPLAY_FINISHED",
                409,
                "the high-risk replay has reached the end of the dataset; reset it "
                "before trading again",
            )

        if not state.next_candle_available:
            raise self._refusal(
                "NO_NEXT_CANDLE",
                409,
                "no execution candle remains, so a position could not be opened; "
                "reset the replay to trade again",
            )

        if self.replay.broker.cash <= 0.0:
            raise self._refusal(
                "NO_PAPER_CASH",
                409,
                "paper cash is zero or below after realised losses; there is no cash "
                "left to commit to a position, and this engine has no credit "
                "facility",
            )

    # -- projection ---------------------------------------------------------

    def high_risk_state(self) -> HighRiskState:
        """The authoritative High-Risk projection. Never cached."""

        with self._lock:
            with self._lock_high_risk:
                replay = self.replay
                state = replay.state
                broker = replay.broker

                trade = broker.open_trade
                cash = broker.cash

                # The identity, not a broker concept. Zero when flat, which is
                # what makes "exposure" read correctly on an empty account
                # instead of reporting `None`.
                exposure = 0.0

                if trade is not None:
                    exposure = trade.entry_price * trade.quantity

                return HighRiskState(
                    risk_fraction=self._config.risk_fraction,
                    max_risk_fraction=MAX_RISK_FRACTION,
                    paper_cash=cash,
                    starting_balance=broker.starting_balance,
                    realized_pnl=cash - broker.starting_balance,
                    trade_count=len(broker.journal),
                    open_position=trade,
                    exposure=exposure,
                    exposure_fraction=(exposure / cash if cash > 0 else 0.0),
                    position_count=(1 if trade is not None else 0),
                    exit_counts=replay.exit_counts,
                    last_signal=state.last_signal,
                    max_positions=replay.policy.max_positions,
                    replay=state,
                    inherits_note=HIGH_RISK_INHERITS_NOTE,
                    caution=HIGH_RISK_CAUTION,
                )

    @staticmethod
    def _refusal(code: str, status: int, message: str) -> HTTPException:
        """One shape for every High-Risk refusal.

        Matches the engine's own convention - ``{"detail": {"code", "message"}}``
        - so a client parses one error shape for the whole API.
        """

        return HTTPException(
            status_code=status,
            detail={"code": code, "message": message},
        )
