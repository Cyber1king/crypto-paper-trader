"""High-Risk: Standard's strategy with a larger share of paper cash per position.

What this mode is
-----------------

**High-Risk introduces no new signal qualification rule and inherits Standard's
signal set.** It is the frozen breakout/retest strategy, entered on exactly the
signals Standard enters, with a larger fraction of paper cash committed to each
position.

That is the whole difference, and the restraint is the point. Phase 26A measured
every alternative and this is the only one that needs no new machinery:

* **More positions** would require a book, because
  :class:`~crypto_paper_lab.simulator.PaperBroker` holds one
  ``open_trade``. Phase 17G built :class:`~crypto_paper_lab.ai_paper.AiPaperBook`
  for exactly that - its own positions, its own committed capital, its own
  account state - which is a second accounting engine, the outcome this project
  exists to prevent. High-Risk does not copy it.
* **A different entry rule** would be a *qualification rule*. Phase 17A left
  High-Risk's qualification rules as open question Q6, to be pre-registered as
  research before implementation. High-Risk therefore adds none, which makes Q6
  moot rather than bypassed: it inherits the set Standard already trades.
* **New exit rules** were measured, not assumed. Adding ``stop_loss_pct`` to the
  frozen strategy at 25% sizing made results *worse* at every level tried - 2%
  produced 388 trades and ``-3,778.47`` against the baseline's 344 and
  ``-3,354.79``, 1% produced 469 trades. A stop changes which trades exist on a
  dataset never researched with one, and it is redundant: ``opposite_signal``
  already closes 343 of the baseline's 344 trades.

Why sizing is the risk
----------------------

Measured over the full frozen dataset, every risk figure scales linearly with
``risk_fraction`` while the trade sequence stays identical::

    rf      trades   worst trade   max drawdown   ending cash
    0.01       344        -7.2285           174.30      9842.8590   <- Standard
    0.10       344       -73.3855          1650.92      8518.7899
    0.25       344      -187.9115          3771.04      6645.2133   <- default
    0.50       344      -389.8511          6501.97      4303.0840
    1.00       344      -829.5089          9820.37      1674.9022

Entry prices, entry timestamps and signal reasons are byte-identical across that
whole table. Only quantity scales. So the mode adds **no** trading logic at all;
it multiplies an existing sequence by a constant the broker already accepts.

A finding worth stating plainly, because it is what "high risk" actually means
here: at full sizing the frozen strategy's **costs exceed its gross result**.
Realized P&L is ``-8,325.10`` and total fees plus slippage are ``5,224.79``, so
62.8% of the loss is friction rather than price movement. A small-edge,
high-turnover strategy is destroyed by its own costs once position size stops
being trivial. That is a real, paper-only risk characteristic and it required no
invented mechanism to demonstrate.

Where the safety boundary comes from
------------------------------------

High-Risk defines **no** leverage, margin, borrowing or liquidation concept, and
it does not need one: :meth:`PaperBroker.open_from_signal` already refuses any
``risk_fraction`` above ``1.0``, and computes
``quantity = (cash * risk_fraction) / fill``. Exposure is therefore bounded by
cash **by the engine**, before this mode sees it::

    exposure = entry_price * quantity <= cash

That inequality holds structurally, not by a runtime check in this module, so a
bug here cannot violate it - only an edit to the broker could. The ceiling below
is a matching declaration, not the enforcement.

Cash is never debited on entry; the broker holds no position value and moves cash
only on close (``cash += net_pnl``). There is no reserved capital, buying power
or margin to report, and none is invented. :class:`HighRiskState` reports
``exposure`` as an arithmetic identity of two fields the broker already owns.

No policy, and no second broker
-------------------------------

There is deliberately **no** ``HighRiskPolicy``. :class:`AutomaticPolicy` already
decides this mode correctly, because High-Risk changes no decision: same
``should_enter``, same ``select_exit``, same ``max_positions = 1``, same
close-and-reverse on an opposite signal. A subclass overriding every method to
delegate would be pure indirection and a second place for behaviour to drift.

Sizing is not a policy concern in the first place. ``execution.py`` states that a
policy "cannot set a size, a fee, a fill price or a balance", and
:class:`Replay` takes ``risk_fraction`` as a constructor argument it passes
straight to the broker. That seam already exists and is already authoritative.

Paper only. There is no exchange connectivity, no credential, no wallet, no
order concept and no credit facility anywhere in this module.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

__all__ = [
    "DEFAULT_RISK_FRACTION",
    "HIGH_RISK_CAUTION",
    "HIGH_RISK_INHERITS_NOTE",
    "HIGH_RISK_NOTE",
    "MAX_RISK_FRACTION",
    "MODE_LABEL",
    "HighRiskConfig",
    "HighRiskError",
    "coerce_risk_fraction",
]

#: Shown wherever the mode is named. Carries "Paper Trading" so the name can never
#: appear in a UI without the word that says what it is.
MODE_LABEL = "High-Risk — Paper Trading"

#: The scope statement Phase 26A required be explicit, and the one that matters most.
#:
#: "High-Risk" without this sentence invites the reading that the mode admits
#: trades Standard rejects, or trades with borrowed money. It does neither. It
#: enters the *same* signals, with *more of your own paper cash* in each. This
#: note is served by the API so a client cannot quietly drop it.
HIGH_RISK_INHERITS_NOTE = (
    "High-Risk introduces no new signal qualification rule and inherits "
    "Standard's signal set."
)

#: What actually makes the mode riskier, stated in the mode's own terms.
#:
#: Deliberately says "more paper capital per position" rather than any of the
#: words the mode must not be read as using. The distinction is the entire safety
#: argument: the difference is *how much of your own simulated cash is committed*,
#: never the *amount of cash required*.
HIGH_RISK_NOTE = (
    "Standard's own breakout and retest strategy, entered on the same signals, "
    "with a larger share of paper cash committed to each position. High-Risk "
    "introduces no new signal qualification rule and inherits Standard's signal "
    "set. Exposure never exceeds the paper cash you hold: there is no leverage, "
    "no margin, no borrowing and no liquidation. Simulation only, not a real "
    "position."
)

#: A caution worth showing on the panel, because the numbers are counterintuitive.
#:
#: Measured on the frozen dataset: at 100% sizing, fees and slippage total
#: ``$5,224.79`` against a realized result of ``-$8,325.10`` - 62.8% of the loss
#: is friction, not price movement. A user who reads "High-Risk" as "more upside"
#: should meet the number that says otherwise.
HIGH_RISK_CAUTION = (
    "On the frozen dataset, costs grow with position size and at the maximum "
    "setting they exceed the strategy's gross result. More paper capital per "
    "position means more fees and slippage, not a better outcome."
)

#: The share of cash committed to a position when nothing is configured.
#:
#: A **default, not a recommendation**. It commits a quarter of cash to one
#: position, which is 25x Standard's exposure and takes the frozen dataset's
#: measured drawdown from $174.30 to $3,771.04. A visible number rather than a
#: hidden one: a mode called High-Risk that quietly sized itself at Standard's
#: fraction would be dishonest, and one that defaulted to 1.0 would commit the
#: entire account on the first signal.
DEFAULT_RISK_FRACTION = 0.25

#: The largest share of cash a position may commit.
#:
#: **Not this module's rule.** :meth:`PaperBroker.open_from_signal` already
#: refuses any ``risk_fraction`` above ``1.0``, and that refusal is what makes
#: leverage impossible. This constant mirrors the engine's limit so the ceiling
#: can be validated, validated-before-committed and served to a client, rather
#: than discovered as a ``ValueError`` deep inside a broker call.
#:
#: It is not gearing: the engine holds no position value and reserves no capital,
#: so the required capital is bounded by cash by construction. A position at
#: 1.0 needs exactly the cash the account holds and not one dollar more.
MAX_RISK_FRACTION = 1.0


class HighRiskError(ValueError):
    """A requested High-Risk risk fraction was not usable.

    Carries no ``code`` of its own: the transport maps every one of these to a
    single ``VALIDATION_ERROR`` refusal, because they are all the same failure
    from a caller's point of view - the number cannot be used.
    """


@dataclass(frozen=True)
class HighRiskConfig:
    """Every rule that governs High-Risk paper execution.

    Frozen and validated in :meth:`__post_init__`, matching
    :class:`~crypto_paper_lab.daily_target.DailyTargetConfig`,
    :class:`~crypto_paper_lab.ai_paper.AiPaperConfig` and
    :class:`~crypto_paper_lab.manual_paper.ManualConfig`. Nothing here is
    compiled into an execution path, so a caller can study a different size
    without editing an engine file.

    There is exactly one setting, and it is the whole mode.
    """

    #: The share of **current cash** committed to each position, as a fraction.
    #:
    #: Recomputed against cash at every entry rather than against the starting
    #: balance, which is exactly what ``PaperBroker.open_from_signal`` does with
    #: its ``risk_fraction`` argument. Passing this through unchanged is the
    #: entire mechanism: the broker sizes, computes the quantity and books every
    #: cost. This module sizes nothing.
    risk_fraction: float = DEFAULT_RISK_FRACTION

    def __post_init__(self) -> None:
        coerce_risk_fraction(self.risk_fraction)

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {"risk_fraction": self.risk_fraction}

    @property
    def identity_hash(self) -> str:
        """Stable hash of :meth:`identity`.

        Uppercase SHA-256 over ``repr``, the same construction as
        :attr:`ExecutionPolicy.identity_hash` and
        :func:`crypto_paper_lab.walkforward.config_hash`, so every identity in
        this project is computed one way.
        """

        return hashlib.sha256(repr(self.identity()).encode("utf-8")).hexdigest().upper()


def coerce_risk_fraction(value: object) -> float:
    """Validate a requested ``risk_fraction`` and return it as a float.

    Raises :class:`HighRiskError` rather than returning a substitute.

    **Nothing is clamped.** A silently trimmed size would commit a position the
    user did not ask for, which is the one outcome they cannot detect from the
    resulting figures. And zero is rejected rather than treated as a minimum: a
    zero-size position is not a small position, it is no position, and reporting
    it as a fill would be a fiction.

    The ceiling is the broker's own, mirrored here so the refusal is stated before
    any state is touched.
    """

    if isinstance(value, bool):
        # Python's ``bool`` is an ``int`` subclass, so ``True`` would become 1.0
        # and commit the entire paper account. A flag the user did not type as a
        # size must not become a size.
        raise HighRiskError(
            "risk_fraction must be a number of paper cash to commit, not a boolean"
        )

    if not isinstance(value, (int, float)):
        raise HighRiskError(
            f"risk_fraction must be a number, got {type(value).__name__}"
        )

    number = float(value)

    if not math.isfinite(number):
        raise HighRiskError(
            "risk_fraction must be a finite number; NaN and infinity are not a size"
        )

    if number <= 0:
        raise HighRiskError(
            "risk_fraction must be greater than 0; zero or a negative size is not "
            "a position"
        )

    if number > MAX_RISK_FRACTION:
        raise HighRiskError(
            f"risk_fraction must be at most {MAX_RISK_FRACTION}; a larger value "
            "would require more capital than the paper account holds, and this "
            "engine has no credit facility. The broker enforces this too - the "
            "ceiling is the engine's, not a UI convenience"
        )

    return number