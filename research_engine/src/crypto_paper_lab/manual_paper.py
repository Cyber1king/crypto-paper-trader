"""Manual: explicit paper entries and exits, with the engine still authoritative.

The mode contract
------------------

Manual runs the **same** frozen dataset, the **same** :class:`TradingCosts` and the
**same** :class:`~crypto_paper_lab.simulator.PaperBroker` as every other mode. It
differs in exactly one respect: **nothing happens unless the user asks for it.**

* No automatic entries. :meth:`ManualPolicy.should_enter` returns ``False``.
* No automatic exits. :meth:`ManualPolicy.select_exit` returns ``None``.
* The only trades are the ones the user requested.

Why the policy must be inert in BOTH directions
-----------------------------------------------

This is the sharpest correctness requirement in the mode, and Phase 25A found it by
measurement rather than by reading.

``Replay._maybe_exit`` consults the policy whenever ``self._entry_index`` is not
``None``. That field is **private engine state**, set only inside ``Replay._maybe_enter``
— so whether a *user*-opened position is subject to the engine's own exit rules depends
on an incidental detail of how it was opened:

* opening via ``broker.open_from_signal`` alone leaves ``_entry_index`` as ``None``,
  ``_maybe_exit`` returns early, and the position is never closed by anything;
* setting ``_entry_index`` makes the exit path live, and
  :class:`~crypto_paper_lab.execution.AutomaticPolicy` closes on the first
  ``opposite_signal`` — measured at step 39 on the frozen data.

:class:`~crypto_paper_lab.execution.DisabledPolicy` is **not** a substitute. Its
reputation is "never trades", and that is about *entries only*: its ``select_exit``
returns ``exit_candidates[0]``, so it will close a position the user opened as soon as
the strategy produces an opposite signal. Phase 17G built it to prove the seam is real,
not to disable exits.

So this module defines its own policy rather than configuring an existing one. Returning
``None`` from ``select_exit`` makes the mode correct **regardless** of ``_entry_index``,
because the engine may offer an exit candidate and this policy will decline it. That is
deliberate redundancy: the behaviour is guaranteed by the policy rather than by the
absence of a private field.

It is worth stating the cost plainly. Every other mode closes 343 of its 344 frozen
trades via ``opposite_signal``. Manual closes **none** of them that way. That is the
point of the mode and is stated in :data:`MODE_NOTE` so a user is never surprised.

No second accounting engine
---------------------------

Every financial quantity is produced by :class:`PaperBroker`:

============  ===========================================================
Quantity      Owner
============  ===========================================================
fill price    ``PaperBroker._fill_price``
quantity      ``PaperBroker.open_from_signal``
fees          ``PaperBroker.close``
slippage      ``PaperBroker.close``
realized P&L  ``PaperBroker.close``
journal       ``PaperBroker.journal``
============  ===========================================================

This module computes none of them, and neither does the session that executes actions.
A Manual entry is a :class:`~crypto_paper_lab.models.Signal` the session constructs,
passed to the *existing* ``open_from_signal``; a Manual exit is the *existing*
``close``. There is no manual broker, no manual cost model and no manual P&L.

Why sizing is a fraction and not a quantity
-------------------------------------------

``open_from_signal(signal, risk_fraction)`` derives
``quantity = (cash * risk_fraction) / fill``. ``risk_fraction`` is a validated *method
argument*, not policy state, so a user-chosen size is expressible with nothing new:
``0.01`` commits 1% of cash as notional, ``1.0`` commits all of it.

Accepting an arbitrary quantity would require a second entry path into the broker, and
the fill price is the engine's to decide — so a quantity computed in the transport could
disagree with the fill it was priced against. The fraction is the honest interface.

An action is an intent, not an instruction
------------------------------------------

A Manual action fills at the **next execution candle's open**, which does not exist yet
when the user submits it. On the frozen data the cursor-22 execution bar opens at
43,679.7 while the last *visible* bar closed at 43,679.8 — so the fill price is
unknowable in advance, which is exactly what keeps the mode free of future leakage.

The action is therefore recorded as a **pending intent** and consumed by the next
``Replay.step``. The realised fill is whatever the engine reports afterwards, and the
UI is forbidden from presenting the preview as a guaranteed price.

Capital
-------

Capital is neither reserved nor deducted on entry, symmetrically for long and short: the
engine holds no position value, only realised P&L. There is no gearing and no buying
power anywhere in this module, and none is introduced.

A loss can in principle drive cash below zero, and nothing in
:class:`PaperBroker` prevents it. That is unreachable at Standard's 1% sizing but
reachable in principle at 100%, so :func:`~paper_api.manualsession.ManualSession`
refuses a new entry when ``cash <= 0`` rather than inheriting the question by accident.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .execution import ExecutionPolicy

__all__ = [
    "ACTIONS",
    "MANUAL_NOTE",
    "MANUAL_POLICY",
    "MAX_SIZE_PCT",
    "MODE_LABEL",
    "MODE_NOTE",
    "MANUAL_EXIT_REASON",
    "MANUAL_REASON",
    "PREVIEW_NOTE",
    "REVERSAL",
    "ManualAction",
    "ManualActionError",
    "ManualConfig",
    "ManualIntent",
    "ManualPolicy",
    "ManualReversalError",
    "action_requires_position",
    "action_requires_size",
    "coerce_size_pct",
    "parse_action",
]

#: Shown wherever the mode is named. Includes "Paper Trading" so the name can never
#: appear in a UI without the word that says what it is.
MODE_LABEL = "Manual — Paper Trading"

#: The non-guarantee statement, reused verbatim by the API and the UI.
MANUAL_NOTE = (
    "Paper trading only. Actions are simulated fills on historical candles, not "
    "orders, and nothing here is a real position."
)

#: The mode note served by ``/api/modes``. It states the one behaviour that differs
#: from every other mode, because a user who expects strategy-driven exits would
#: otherwise read their position as frozen by a bug.
MODE_NOTE = (
    "Manual paper trading. Nothing opens or closes unless you ask it to: the "
    "strategy's own entry and exit rules are switched off, so a position you open "
    "stays open until you exit it. One paper position, long or short, sized as a "
    "percentage of paper cash with no credit facility. An action fills at the next "
    "candle's open, so the price is set when the replay advances and not before. "
    "Simulation only, not a real position."
)

#: The largest position a user may request, as a fraction of cash.
#:
#: 1.0 means "commit the entire account". It is not gearing: the engine holds no
#: position value and never reserves capital, so the notional is bounded by cash by
#: construction rather than by this ceiling. The ceiling exists so a typo cannot
#: silently ask for a size the user did not mean.
MAX_SIZE_PCT = 1.0

#: What a UI must say beside the execution-price preview.
#:
#: The preview is a real engine value - the open of the bar a pending action would fill
#: against - and it is also the single easiest number in this mode to misread as a
#: quote. The wording is served by the engine rather than written by the client so a UI
#: cannot drop it, and so server and client cannot drift into different claims about
#: what the number means.
PREVIEW_NOTE = "Preview — not a fill price."

#: ``PaperTrade.reason`` for a user entry, and ``exit_reason`` for a user exit.
#:
#: Deliberately not one of the engine's own labels (``opposite_signal``,
#: ``max_holding``, ``stop_loss``, ``take_profit``, ``end_of_data``). Those all mean
#: "a rule fired"; reusing one would make a deliberate user exit indistinguishable from
#: an automatic one, which is the single fact a reader of the journal most needs.
MANUAL_REASON = "manual entry"
MANUAL_EXIT_REASON = "manual"

ManualAction = Literal["ENTER_LONG", "ENTER_SHORT", "EXIT"]

#: The complete set of actions. ``HOLD`` is deliberately absent: it is the absence of
#: an action and needs no endpoint. ``REVERSE`` is deliberately absent: an atomic
#: exit-then-entry at one price would need two fills inside one broker call and would
#: charge a full round of costs on a trade the user never chose to close.
ACTIONS: tuple[ManualAction, ...] = ("ENTER_LONG", "ENTER_SHORT", "EXIT")

#: The reversal a user might reasonably reach for, named so it can be refused
#: specifically rather than reported as an unknown action.
REVERSAL = "REVERSE"


class ManualActionError(ValueError):
    """A manual action was not usable.

    Carries the ``code`` the transport maps to a status, so the engine states the
    refusal and the HTTP layer only chooses the number. Follows the same convention as
    :class:`~crypto_paper_lab.replay.ReplayError` without extending it, because a
    manual action is not a replay transition.
    """

    code = "VALIDATION_ERROR"


class ManualReversalError(ManualActionError):
    """A reversal was requested. Not supported; exit, then enter."""

    code = "UNSUPPORTED_REVERSAL"


@dataclass(frozen=True)
class ManualConfig:
    """Every rule governing Manual paper execution.

    Frozen and validated in :meth:`__post_init__`, matching
    :class:`~crypto_paper_lab.daily_target.DailyTargetConfig` and
    :class:`~crypto_paper_lab.ai_paper.AiPaperConfig`. Nothing here is compiled into an
    execution path, so a caller can change a ceiling without editing the engine.
    """

    #: Largest permitted ``size_pct``.
    max_size_pct: float = MAX_SIZE_PCT

    def __post_init__(self) -> None:
        if not math.isfinite(self.max_size_pct):
            raise ValueError(
                "max_size_pct must be a finite number; NaN and infinity are not a "
                "ceiling"
            )

        if not 0 < self.max_size_pct <= MAX_SIZE_PCT:
            raise ValueError(
                f"max_size_pct must be greater than 0 and at most {MAX_SIZE_PCT}; a "
                "ceiling above 1 would permit committing more than the account holds, "
                "and this engine has no credit facility"
            )

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {"max_size_pct": self.max_size_pct}


@dataclass(frozen=True)
class ManualIntent:
    """One requested action, not yet filled.

    A frozen value object holding only what the session needs to act on the next
    ``Replay.step``. It deliberately holds **no price**: the fill price does not exist
    until the execution bar does, and a field for it would invite someone to fill it
    with a guess.
    """

    action: ManualAction
    size_pct: float | None = None

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ManualActionError(
                f"unknown manual action {self.action!r}; expected one of "
                f"{', '.join(ACTIONS)}"
            )

        if action_requires_size(self.action):
            if self.size_pct is None:
                raise ManualActionError(
                    f"{self.action} requires size_pct"
                )

            coerce_size_pct(self.size_pct, ManualConfig())

        elif self.size_pct is not None:
            # Refused rather than ignored: an EXIT carrying a size suggests the
            # request was not understood, and silently dropping it would hide that.
            raise ManualActionError(
                f"{self.action} takes no size_pct; a size on an exit would be "
                "ignored, and ignoring it would hide a request the user did not mean"
            )

    def identity(self) -> dict:
        return {"action": self.action, "size_pct": self.size_pct}


def parse_action(value: object) -> ManualAction:
    """Validate an action name coming from a caller.

    Case-insensitive, so a user typing ``enter_long`` is understood rather than told
    off, but the **canonical** spelling is always returned, so every downstream
    comparison and every stored intent uses one representation.

    Refuses everything else rather than guessing. A near-miss like ``"LONG"`` is
    rejected instead of being read as an entry, because guessing which trade a user
    meant is not a decision this layer may take.
    """

    if isinstance(value, str):
        upper = value.strip().upper()

        if upper == REVERSAL:
            # Answered specifically rather than as an unknown action, because "not
            # supported" and "no such action" are different answers.
            raise ManualReversalError(
                "reversal is not supported in Manual mode; exit the open position "
                "first, then enter the opposite side. Each fills at its own candle "
                "open and charges its own costs"
            )

        if upper in ACTIONS:
            return upper  # type: ignore[return-value]

    raise ManualActionError(
        f"unknown manual action {value!r}; expected one of {', '.join(ACTIONS)}"
    )


def action_requires_size(action: ManualAction) -> bool:
    """Whether this action carries a ``size_pct``."""

    return action in {"ENTER_LONG", "ENTER_SHORT"}


def action_requires_position(action: ManualAction) -> bool:
    """Whether this action needs an open position to act on."""

    return action == "EXIT"


def coerce_size_pct(value: object, config: ManualConfig | None = None) -> float:
    """Validate a requested position size as a fraction of cash.

    Returns the value as a float, or raises :class:`ManualActionError`.

    **Nothing is clamped.** A silently trimmed size would show the user a position
    they did not ask for, which is the one outcome they cannot detect; and zero is
    rejected rather than treated as a minimum, because a zero-size entry is either
    already met or meaningless, not a small position.
    """

    limits = config or ManualConfig()

    if isinstance(value, bool):
        # Python's bool is an int subclass, so ``True`` would become 1.0 and commit the
        # entire account. A target the user did not type must not become a size.
        raise ManualActionError(
            "size_pct must be a number of dollars' worth of cash, not a boolean"
        )

    if not isinstance(value, (int, float)):
        raise ManualActionError(
            f"size_pct must be a number, got {type(value).__name__}"
        )

    number = float(value)

    if not math.isfinite(number):
        raise ManualActionError(
            "size_pct must be a finite number; NaN and infinity are not a size"
        )

    if number <= 0:
        raise ManualActionError(
            "size_pct must be greater than 0; a zero or negative size is not a "
            "position"
        )

    if number > limits.max_size_pct:
        raise ManualActionError(
            f"size_pct must be at most {limits.max_size_pct}; a value above 1 would "
            "commit more than the paper account holds, and this engine has no credit "
            "facility"
        )

    return number


@dataclass(frozen=True)
class ManualPolicy(ExecutionPolicy):
    """Neither opens nor closes. Every trade in Manual is the user's.

    A **decision layer** like every policy: it holds no balance, no journal, no
    position and no cursor, and it is never given one.

    Both decisions are hard ``False``/``None`` rather than delegations, because there
    is no engine behaviour worth delegating to. Every other policy consults
    ``AUTOMATIC_POLICY`` on entry or exit; doing that here would reintroduce precisely
    the automatic behaviour the mode exists to remove.

    See the module docstring for why :class:`~crypto_paper_lab.execution.DisabledPolicy`
    cannot be used instead. In short: it refuses *entries* but still *selects exits*, so
    it would close a position the user opened on the first ``opposite_signal``.
    """

    name: str = "manual"

    def should_enter(self, context) -> bool:
        """Always ``False``. Manual opens nothing; the user does."""

        return False

    def select_exit(self, context):
        """Always ``None``. Manual closes nothing; the user does.

        The baseline config sets no stop-loss, no take-profit and no max-holding bars,
        so the only exit candidate the engine can ever produce is ``opposite_signal``.
        Selecting it would let the strategy close a position the user chose to open —
        the single failure this policy exists to prevent.
        """

        return None

    def identity(self) -> dict:
        return {"name": self.name, "max_positions": self.max_positions}


#: Manual's policy. A module-level constant, like ``AUTOMATIC_POLICY`` and
#: ``DAILY_TARGET_POLICY``, so ``modes.MODES`` stays a shared constant every process can
#: hold safely.
MANUAL_POLICY = ManualPolicy()