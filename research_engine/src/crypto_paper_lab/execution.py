"""Execution policy: the seam between a signal and a paper trade (Phase 17E).

This module answers exactly one question - *given what the strategy has already
observed, should this replay act?* - and nothing else.

Why the seam exists
-------------------

Phase 17A §6 recorded the reason, and it is architectural rather than cosmetic.
``run_backtest`` inlines its entry rule, so "observe this signal but do not trade
it" is inexpressible. That single missing expression is what makes a mode that
only *displays* signals impossible to build without forking the engine. With the
decision lifted out here, refusing to trade is a policy choice rather than an
engine modification.

The flow this module sits in::

    candles -> strategy.analyze -> ExecutionPolicy -> Replay -> PaperBroker

What a policy may decide
------------------------

* whether an eligible signal becomes an entry (:meth:`ExecutionPolicy.should_enter`);
* which engine-detected exit reason, if any, is used
  (:meth:`ExecutionPolicy.select_exit`);
* how many positions it permits at all (``max_positions``).

What a policy may **not** do
----------------------------

It owns no trading state and performs no trading arithmetic. It cannot set a
size, a fee, a fill price or a balance, and it is never handed a candle, a broker
or a replay. Everything it needs arrives in an immutable
:class:`DecisionContext` built by :class:`~crypto_paper_lab.replay.Replay` from
authoritative values.

Capital allocation is deliberately **not** a policy concern. Position size is
computed by ``PaperBroker.open_from_signal`` from cash and a risk fraction; a
policy is told the risk fraction for its own decisions but cannot change it.
Letting a policy size positions would be the first step toward a second
accounting engine, which is the outcome this project exists to prevent.

Causality
---------

:class:`DecisionContext` carries no candle objects at all - only values already
derived from bars the strategy has seen. A policy therefore cannot introduce
future leakage, because the data required to do so is never handed to it. That is
a structural property, not a convention.

Scope
-----

Phase 17E ships two policies: :class:`AutomaticPolicy`, which reproduces the
existing deterministic behaviour exactly and is the default, and
:class:`DisabledPolicy`, which refuses entries while still honouring exits. The
second exists to prove the seam is a real seam rather than an indirection over
one code path.

**No intelligence scoring belongs here.** There is no confidence value, score,
threshold or model in this module, and none is planned for it: the engine defines
no such quantity, so any value a policy invented would be fabricated. Where a
later mode needs one, it must be defined and validated as research first.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

__all__ = [
    "AUTOMATIC_POLICY",
    "DEFAULT_POLICY",
    "DecisionContext",
    "DisabledPolicy",
    "ExecutionPolicy",
    "ExitCandidate",
]


@dataclass(frozen=True)
class ExitCandidate:
    """An exit the engine's own rules have already detected.

    Produced by :class:`~crypto_paper_lab.replay.Replay` from the configured exit
    rules and the signal - never by a policy. A policy *selects among* candidates;
    it does not invent them, so it cannot express an exit the engine does not
    support.

    ``reason`` is one of the engine's own labels (``max_holding``, ``stop_loss``,
    ``take_profit``, ``opposite_signal``). Ordering is meaningful: candidates
    appear in engine precedence order, so selecting the first reproduces the
    engine exactly.
    """

    reason: str
    bars_held: int


@dataclass(frozen=True)
class DecisionContext:
    """Everything a policy is allowed to see, and nothing more.

    Immutable by construction. Contains no candle, no broker and no replay, so a
    policy cannot mutate engine state even by accident, and cannot read a bar the
    strategy has not already seen.

    ``risk_fraction`` is provided read-only so a policy can reason about sizing;
    it cannot act on it.
    """

    #: Index of the execution bar the current step will fill against. An index,
    #: never a price or a candle: it locates the decision point without
    #: exposing any bar's contents.
    evaluation_index: int

    #: What the strategy observed, derived from bars up to and including the
    #: signal bar. ``flat`` is a normal outcome, not an error.
    signal_side: Literal["long", "short", "flat"]
    signal_reason: str
    signal_price: float
    signal_timestamp: datetime | None

    #: Engine state, summarised. The policy may read these; it cannot change
    #: them.
    has_open_position: bool
    position_side: Literal["long", "short"] | None
    bars_held: int | None

    #: Exit reasons the engine has already detected, in precedence order.
    exit_candidates: tuple[ExitCandidate, ...] = ()

    #: Informational. Sizing stays with ``PaperBroker``.
    risk_fraction: float = 0.01

    @property
    def can_open(self) -> bool:
        """Whether the engine currently permits an entry at all.

        Configuration gates (``allowed_sides``, ``evaluation_start``) are applied
        by the engine before the policy is consulted, so a ``True`` here means the
        engine's own gates passed and the decision is genuinely the policy's.
        """

        return not self.has_open_position


@dataclass(frozen=True)
class ExecutionPolicy:
    """Base class for a mode's execution policy.

    A policy is a **decision layer**, not a broker. It holds no balances, no
    journal, no position and no cursor, and it is never given one.

    Concrete policies are frozen dataclasses that set ``name`` and implement the
    two decision methods. ``identity`` is derived from immutable fields, so the
    active policy can be identified without inspecting memory or global state.
    """

    #: Stable, human-meaningful identifier. Required and non-empty so a policy
    #: can never be anonymous.
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("execution policy must be named")

    # -- position eligibility ----------------------------------------------

    @property
    def max_positions(self) -> int:
        """How many simultaneous positions this policy permits.

        Always 1 in Phase 17E, matching ``PaperBroker``'s one-position rule. The
        property exists because eligibility is a policy question in principle, and
        a policy declaring fewer than one position refuses to trade - which is how
        :class:`DisabledPolicy` is expressed.

        A value above 1 is **not** honoured by the current broker and must not be
        treated as permission to open several positions.
        """

        return 1

    # -- decisions ----------------------------------------------------------

    def should_enter(self, context: DecisionContext) -> bool:
        """Whether this signal becomes a paper entry."""

        raise NotImplementedError

    def select_exit(
        self, context: DecisionContext
    ) -> ExitCandidate | None:
        """Which engine-detected exit to use, or ``None`` to hold."""

        raise NotImplementedError

    # -- identity -----------------------------------------------------------

    def identity(self) -> dict:
        """Deterministic, serialisable description of this policy.

        Built only from immutable fields. No timestamp, no random identifier and
        nothing environment-dependent, so two processes configuring the same policy
        produce byte-identical output.
        """

        return {"name": self.name, "max_positions": self.max_positions}

    @property
    def identity_hash(self) -> str:
        """Stable hash of :meth:`identity`.

        Uses the same construction as ``walkforward.config_hash`` and
        ``costs_hash`` - uppercase SHA-256 over ``repr`` - so every identity in
        this project is computed the same way.
        """

        return hashlib.sha256(
            repr(self.identity()).encode("utf-8")
        ).hexdigest().upper()


@dataclass(frozen=True)
class AutomaticPolicy(ExecutionPolicy):
    """The default: act on every eligible signal. Reproduces existing behaviour.

    Selects the first engine-detected exit candidate, which is exactly the
    precedence ``run_backtest`` applies. With this policy - the default - a replay
    is behaviourally identical to Phase 17B/17C: same signals, entries, exits,
    ordering, balances, costs and final state.
    """

    name: str = "automatic"

    def should_enter(self, context: DecisionContext) -> bool:
        return (
            self.max_positions > 0
            and context.can_open
            and context.signal_side in {"long", "short"}
        )

    def select_exit(
        self, context: DecisionContext
    ) -> ExitCandidate | None:
        return context.exit_candidates[0] if context.exit_candidates else None


@dataclass(frozen=True)
class DisabledPolicy(ExecutionPolicy):
    """Never opens a position; still honours exits on anything already open.

    Exists to prove the seam is real. It is the mechanism Phase 17A §16 requires
    for a mode that observes without trading: refusing an entry is a policy
    choice, not an engine change.

    Exits are deliberately *not* disabled. A position that cannot be closed would
    be a trap, and honouring the engine's exit rules is the safe behaviour.
    """

    name: str = "disabled"

    @property
    def max_positions(self) -> int:
        return 0

    def should_enter(self, context: DecisionContext) -> bool:
        return False

    def select_exit(
        self, context: DecisionContext
    ) -> ExitCandidate | None:
        return context.exit_candidates[0] if context.exit_candidates else None


#: The default policy. Every ``Replay`` constructed without an explicit policy
#: uses this, so pre- and post-17E behaviour is identical by construction.
AUTOMATIC_POLICY = AutomaticPolicy()

#: Explicit alias. ``DEFAULT_POLICY`` reads better at call sites that mean "the
#: behaviour this project has always had", while ``AUTOMATIC_POLICY`` names the
#: policy itself. They are the same frozen instance.
DEFAULT_POLICY = AUTOMATIC_POLICY