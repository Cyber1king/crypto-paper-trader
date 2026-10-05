"""Paper trading modes: identities, policies and capabilities (17F, contracts in 17G).

A **mode** is a named, isolated paper environment. It owns its own execution
state, and nothing financial is shared between modes.

The *shape* of that state differs by mode, which is the one place 17G departs from
17F's simpler picture:

* **Standard** and any single-position mode run a
  :class:`~crypto_paper_lab.replay.Replay`, which owns one
  :class:`~crypto_paper_lab.simulator.PaperBroker`.
* **AI Intelligence** runs an :class:`~crypto_paper_lab.ai_paper.AiPaperBook`,
  which owns one broker *per position*, because its contract permits several
  independent paper positions at once. ``PaperBroker`` holds exactly one, and
  Phase 17G does not rewrite it - Standard's frozen 344-trade baseline depends on
  its single-position rule.
* **Alerts** owns neither. It has no broker at all (Phase 17A §12.1).

The registry in :mod:`paper_api.moderegistry` is what binds a mode name to the
right one of those. This module itself remains configuration only.

::

    Mode
      ↓  selects a policy
    ExecutionPolicy
      ↓  decides, per signal
    Replay
      ↓  drives, per step
    PaperBroker
      ↓
    Authoritative state

What a mode is
--------------

An identity plus a policy plus a capability flag. That is the whole concept:

* **identity** - a stable string, so a mode can be named in configuration and in
  a request without ambiguity;
* **policy** - the :class:`~crypto_paper_lab.execution.ExecutionPolicy` that mode
  decides with;
* **capability** - whether the mode may execute paper trades at all.

A mode holds **no** balance, cursor, journal, position or P&L. Those belong to
its broker, reachable only through its replay. Keeping configuration free of
mutable state is what makes a mode safe to share as a singleton.

Isolation is structural rather than policed
-------------------------------------------

Two modes cannot interfere because they do not hold references to each other and
cannot reach each other's broker. There is no registry-level aggregate balance to
be inconsistent, because no such aggregate exists. Selecting a different mode is
a different object, not a different flag on one object - so "switching modes"
cannot reset, close or transfer anything.

Alerts is brokerless
--------------------

Phase 17A §12.1 is explicit: the strongest guarantee that alerts cannot execute is
that the alerts component holds **no broker reference at all**. An object that
cannot reach a ``PaperBroker`` is incapable of trading, rather than merely
instructed not to. So ``ALERTS`` is declared ``supports_execution=False`` and
:class:`mode_policy` refuses to hand it an executable policy.

AI Intelligence's contract
-------------------------

Phase 17F left ``AI_INTELLIGENCE`` deliberately inert - a
:class:`~crypto_paper_lab.execution.DisabledPolicy`, so it could not trade by
accident and could not silently behave like Standard. Phase 17G defines what it
actually does, and this module now maps it to that contract:

* **Qualification.** A signal trades only when its deterministic intelligence
  score reaches a threshold (default 90). The score is computed by
  :mod:`crypto_paper_lab.intelligence` and compared by
  :class:`~crypto_paper_lab.execution.IntelligencePolicy`. It is a **research
  heuristic**, not a probability, a win rate or any profit forecast - the
  underlying strategy's Phase 13 record is negative.
* **Several positions.** AI Intelligence may hold up to ``max_positions``
  independent paper positions. Because
  :class:`~crypto_paper_lab.simulator.PaperBroker` holds exactly one, the mode's
  execution lives in :mod:`crypto_paper_lab.ai_paper`, which owns one broker per
  position. **Standard is untouched**: its broker, its single-position rule and
  its 344-trade baseline are exactly as Phase 17B left them.
* **Isolated capital.** Its own pool, its own allocations. Nothing is shared with
  Standard and nothing is on credit: a position's notional can never exceed the
  paper cash committed to it, so the mode has no gearing, no credit and no buying
  power.

What this module does **not** do is hold any of it. A mode is still identity plus
policy plus capability; the pool, the positions and the P&L belong to
``ai_paper``. Keeping configuration free of mutable state is what lets this
mapping stay a module-level constant that every process shares safely.

Reserved modes
--------------

Phase 17A names four product modes: Daily Target, Manual, High-Risk Paper and
Alerts. Three of those - ``daily_target``, ``manual``, ``high_risk`` - are still
*recognised* and *refused* after Phase 17G. Phase 17G defines the Standard, AI
Intelligence and Alerts contracts; it does **not** define these three, and the
architecture is explicit that it should not: High-Risk qualification rules are
recorded as open question Q6 and must be pre-registered as research before they
are implemented, and Daily Target and Manual each have unresolved contract
questions of their own (Q4, Q5). Inventing contracts for them here would smuggle
untested strategy variants into a UI phase, which is the outcome Q6 warns about.

Reserving the names means a typo cannot create a silent new mode, and requesting
one fails explicitly instead of falling back to Standard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .ai_paper import (
    DEFAULT_ALLOCATION_FRACTION,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PROFIT_TARGET_PCT,
)
from .execution import (
    AUTOMATIC_POLICY,
    DisabledPolicy,
    ExecutionPolicy,
    IntelligencePolicy,
)
from .intelligence import DEFAULT_THRESHOLD

__all__ = [
    "AI_INTELLIGENCE",
    "AI_INTELLIGENCE_POLICY",
    "ALERTS",
    "DEFAULT_ALLOCATION_FRACTION",
    "DEFAULT_MAX_POSITIONS",
    "DEFAULT_MODE",
    "DEFAULT_PROFIT_TARGET_PCT",
    "DEFAULT_THRESHOLD",
    "MODES",
    "ModeError",
    "ModeNotAvailableError",
    "ModeSpec",
    "UnknownModeError",
    "is_executable",
    "known_modes",
    "mode_policy",
    "mode_spec",
    "reserved_modes",
]


# ---------------------------------------------------------------------------
# Mode identities
# ---------------------------------------------------------------------------

#: The default paper environment. Behaviourally identical to the pre-17F replay.
STANDARD = "standard"

#: Planned future mode. Isolation boundary only in Phase 17F.
AI_INTELLIGENCE = "ai_intelligence"

#: Notification-only. Holds no broker, by Phase 17A §12.1.
ALERTS = "alerts"

#: Names Phase 17A defined for later phases. Reserved here so they cannot be
#: invented by accident and so requesting one fails loudly.
RESERVED_DAILY_TARGET = "daily_target"
RESERVED_MANUAL = "manual"
RESERVED_HIGH_RISK = "high_risk"


class ModeError(ValueError):
    """Base class for mode resolution failures."""

    code = "MODE_ERROR"


class UnknownModeError(ModeError):
    """The requested mode does not exist. Never falls back to Standard."""

    code = "INVALID_MODE"


class ModeNotAvailableError(ModeError):
    """The mode exists but cannot be used yet.

    Raised for a reserved Phase 17G mode and for Alerts when execution is
    requested. Distinct from :class:`UnknownModeError` because "not built yet" and
    "no such thing" are different answers and a client may want to tell them
    apart.
    """

    code = "MODE_NOT_AVAILABLE"


@dataclass(frozen=True)
class ModeSpec:
    """Immutable configuration for one mode. Contains no trading state.

    Every field is a fact about the mode, not a value that changes as it runs:
    there is no balance, cursor, journal, position or P&L field here, and adding
    one would make a shared singleton unsafe.
    """

    #: Stable identity string.
    mode: str
    #: Human-facing label. Cosmetic only; never used for lookup.
    label: str
    #: Whether this mode may execute paper trades at all.
    supports_execution: bool
    #: Whether the mode is usable in Phase 17F.
    available: bool
    #: Why it is unavailable, or what it will become. Surfaced so a client can
    #: explain itself instead of guessing.
    note: str
    #: The policy this mode decides with. ``None`` only for a brokerless mode,
    #: and that is deliberate rather than a placeholder for a real policy.
    policy: ExecutionPolicy | None

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {
            "mode": self.mode,
            "label": self.label,
            "supports_execution": self.supports_execution,
            "available": self.available,
            "note": self.note,
            "policy": (
                self.policy.identity() if self.policy is not None else None
            ),
        }


#: AI Intelligence's execution policy, as of Phase 17G.
#:
#: Deliberately **not** :data:`AUTOMATIC_POLICY`. Phase 17F used a
#: :class:`~crypto_paper_lab.execution.DisabledPolicy` so the mode could not trade
#: before its contract existed; the contract now exists, and this trades only
#: signals whose deterministic intelligence score reaches the threshold.
#:
#: The threshold and position limit are the mode's defaults here rather than
#: arguments, so ``MODES`` stays a module-level constant every process shares
#: safely. A study of different values configures
#: :class:`~crypto_paper_lab.ai_paper.AiPaperBook` directly instead of mutating
#: this.
AI_INTELLIGENCE_POLICY = IntelligencePolicy(
    threshold=DEFAULT_THRESHOLD,
    position_limit=DEFAULT_MAX_POSITIONS,
)


MODES: Mapping[str, ModeSpec] = {
    spec.mode: spec
    for spec in (
        ModeSpec(
            mode=STANDARD,
            label="Standard",
            supports_execution=True,
            available=True,
            note=(
                "Automatic paper trading on the frozen baseline strategy. The "
                "default, and behaviourally identical to the pre-17F replay."
            ),
            policy=AUTOMATIC_POLICY,
        ),
        ModeSpec(
            mode=AI_INTELLIGENCE,
            label="AI Intelligence",
            supports_execution=True,
            available=True,
            note=(
                "Isolated paper pool. Executes only signals whose deterministic "
                f"intelligence score reaches {DEFAULT_THRESHOLD:g}, holds up to "
                f"{DEFAULT_MAX_POSITIONS} independent paper positions, and "
                f"closes each at a {DEFAULT_PROFIT_TARGET_PCT * 100:g}% profit "
                "target. The score is a research heuristic, not a probability or "
                "a profit forecast. Own pool, own positions, own journal."
            ),
            policy=AI_INTELLIGENCE_POLICY,
        ),
        ModeSpec(
            mode=ALERTS,
            label="Alerts",
            # No broker reference exists at all, so execution is not merely
            # switched off - it is unrepresentable.
            supports_execution=False,
            available=True,
            note=(
                "Notification-only. Holds no broker and cannot execute paper "
                "trades. Notification delivery arrives in a later phase."
            ),
            policy=None,
        ),
        ModeSpec(
            mode=RESERVED_DAILY_TARGET,
            label="Daily Target",
            supports_execution=True,
            available=False,
            note="Reserved. The mode contract is defined in Phase 17G.",
            policy=DisabledPolicy(name="reserved_daily_target"),
        ),
        ModeSpec(
            mode=RESERVED_MANUAL,
            label="Manual",
            supports_execution=True,
            available=False,
            note="Reserved. The mode contract is defined in Phase 17G.",
            policy=DisabledPolicy(name="reserved_manual"),
        ),
        ModeSpec(
            mode=RESERVED_HIGH_RISK,
            label="High-Risk Paper",
            supports_execution=True,
            available=False,
            note="Reserved. The mode contract is defined in Phase 17G.",
            policy=DisabledPolicy(name="reserved_high_risk"),
        ),
    )
}

#: The mode used when a caller does not name one. Preserves pre-17F behaviour.
DEFAULT_MODE = STANDARD


def known_modes() -> tuple:
    """Every recognised mode name, available or reserved."""

    return tuple(MODES)


def reserved_modes() -> tuple:
    """Recognised but not yet usable."""

    return tuple(
        spec.mode for spec in MODES.values() if not spec.available
    )


def is_executable(mode: str) -> bool:
    """Whether ``mode`` may hold a replay and trade."""

    spec = mode_spec(mode)

    return spec.available and spec.supports_execution


def mode_spec(mode: str) -> ModeSpec:
    """Resolve a mode name to its configuration.

    Raises rather than defaulting. An unknown mode must never silently become
    Standard, because that would run the wrong paper environment against real
    expectations about capital and risk.
    """

    try:
        return MODES[mode]
    except KeyError:
        raise UnknownModeError(
            f"unknown mode {mode!r}; known modes: "
            f"{', '.join(sorted(MODES))}"
        ) from None


def mode_policy(mode: str) -> ExecutionPolicy:
    """The policy ``mode`` decides with.

    Raises for a reserved mode, and for a brokerless mode asked to execute.
    """

    spec = mode_spec(mode)

    if not spec.available:
        raise ModeNotAvailableError(
            f"mode {mode!r} is reserved: {spec.note}"
        )

    if spec.policy is None:
        raise ModeNotAvailableError(
            f"mode {mode!r} does not execute paper trades: {spec.note}"
        )

    return spec.policy