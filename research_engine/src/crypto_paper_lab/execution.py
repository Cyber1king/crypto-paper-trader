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
-----------

:class:`DecisionContext` carries no candle objects at all - only values already
derived from bars the strategy has seen. A policy therefore cannot introduce
future leakage, because the data required to do so is never handed to it. That is
a structural property, not a convention.

Phase 17G added three optional fields for multi-position modes:
``intelligence_score``, ``open_position_count`` and ``available_capital``. All
default to ``None``, so a context built by :class:`~crypto_paper_lab.replay.Replay`
is byte-identical to what it was, and the pre-17G policies read exactly what they
always read. ``intelligence_score`` is a plain number rather than a score object
specifically so a policy cannot reach back into the scorer through it.

Scope
-----

Phase 17E shipped two policies: :class:`AutomaticPolicy`, which reproduces the
existing deterministic behaviour exactly and is the default, and
:class:`DisabledPolicy`, which refuses entries while still honouring exits. The
second exists to prove the seam is a real seam rather than an indirection over
one code path.

Phase 17G adds :class:`IntelligencePolicy`, which trades a signal only when a
deterministic score reaches a threshold. **The score itself is not defined here.**
That was Phase 17E's position and it was right then: the engine defined no such
quantity, so a value invented here would have been fabricated. It stopped being
the engine's job once Phase 17G defined and documented the quantity in
:mod:`crypto_paper_lab.intelligence`, and this module now only *compares* against
it. The score's definition, weights and research status belong with the scorer,
not with the seam.
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
    "IntelligencePolicy",
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

    # -- Phase 17G additions -------------------------------------------------
    #
    # Added for AI Intelligence, which permits several independent paper
    # positions. Every field is optional and defaults to the single-position
    # world, so a context built by ``Replay`` is unchanged and the policies that
    # predate Phase 17G read exactly what they always read.
    #
    # ``intelligence_score`` is a plain number on a fixed 0-100 scale, not an
    # object, deliberately: a policy can compare it and ignore it, but holding a
    # score object would let a policy reach back into the scorer. The score's
    # components live on ``IntelligenceScore`` for reporting.

    #: The deterministic 0-100 qualification score for this signal, or ``None``
    #: when no scorer ran. Read-only, like ``risk_fraction``: it decides
    #: eligibility and nothing else.
    intelligence_score: float | None = None

    #: How many positions the calling mode currently holds open. ``None`` means
    #: "not reported", which a single-position caller cannot meaningfully state.
    open_position_count: int | None = None

    #: Paper capital the calling mode could commit right now. Capital
    #: *bookkeeping*, informational: a policy decides eligibility, never a size.
    available_capital: float | None = None

    @property
    def can_open(self) -> bool:
        """Whether the engine currently permits an entry at all.

        Configuration gates (``allowed_sides``, ``evaluation_start``) are applied
        by the engine before the policy is consulted, so a ``True`` here means the
        engine's own gates passed and the decision is genuinely the policy's.

        This is the **single-position** question: one open trade blocks a new
        entry. A multi-position mode asks its own limit through
        :meth:`has_room` instead, because "no position is open" and "no slot is
        free" are different questions.
        """

        return not self.has_open_position

    def has_room(self, limit: int) -> bool:
        """Whether a mode permitting ``limit`` positions has a free slot.

        Used by multi-position policies. ``open_position_count`` is ``None`` for a
        caller that does not report it, which is treated as **no room** rather than
        as unlimited: a mode that cannot say how many positions it holds must not
        be told it may open more.
        """

        if limit <= 0:
            return False

        if self.open_position_count is None:
            return False

        return self.open_position_count < limit


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
class IntelligencePolicy(ExecutionPolicy):
    """Trades only signals whose intelligence score reaches a threshold (17G).

    The decision layer for :mod:`crypto_paper_lab.ai_paper`. It answers three
    questions and owns no state:

    * is this signal directional at all (``flat`` never trades, Phase 17A §16.2);
    * does its score reach the configured threshold;
    * is a position slot still free under ``max_positions``.

    **The threshold comparison is exact**: ``score >= threshold``. A score exactly
    equal to the threshold qualifies. That is the documented boundary rule rather
    than an incidental one, because it is the boundary a caller tests against.

    ``max_positions`` overrides the base's ``1`` and is honoured by
    :class:`~crypto_paper_lab.ai_paper.AiPaperBook`, which is why that class exists
    instead of a rewritten ``PaperBroker``. The base class's note that a value above
    one is not honoured by the single-position broker still holds; this policy is
    only ever paired with a book that can honour it.

    No stop-loss rule, because Phase 17G defines none. This policy decides
    *entries*; exits belong to the book's profit-target rule.
    """

    name: str = "intelligence"
    threshold: float = 90.0

    #: How many concurrent positions this policy admits. Named ``position_limit``
    #: rather than ``max_positions`` because the base class already exposes
    #: ``max_positions`` as a read-only property; a field of the same name would
    #: shadow that property and turn it into a second, mutable source of truth.
    #: The property below remains the public accessor.
    position_limit: int = 5

    def __post_init__(self) -> None:
        super().__post_init__()

        if not 0 <= self.threshold <= 100:
            raise ValueError(
                f"threshold must be between 0 and 100, got {self.threshold}"
            )

        if self.position_limit < 1:
            raise ValueError(
                f"position_limit must be at least 1, got {self.position_limit}"
            )

    @property
    def max_positions(self) -> int:
        return self.position_limit

    def should_enter(self, context: DecisionContext) -> bool:
        if context.signal_side not in {"long", "short"}:
            return False

        if context.intelligence_score is None:
            # No score means no qualification. Treating an absent score as a pass
            # would make the mode trade every signal whenever scoring was skipped,
            # which is the failure the threshold exists to prevent.
            return False

        if context.intelligence_score < self.threshold:
            return False

        return context.has_room(self.max_positions)

    def select_exit(
        self, context: DecisionContext
    ) -> ExitCandidate | None:
        """Never an engine candidate.

        The AI book's exit rule is its own profit target, evaluated against a
        closed bar per position. Returning an engine candidate here would mean
        closing a position on the engine's single-position rules, which the
        multi-position book does not use.
        """

        return None

    def identity(self) -> dict:
        return {
            "name": self.name,
            "max_positions": self.max_positions,
            "threshold": self.threshold,
        }


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