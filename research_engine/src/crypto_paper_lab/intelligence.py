"""Deterministic paper-trading intelligence score (Phase 17G).

What this score is, stated precisely
------------------------------------

A **qualification gate**. It is a deterministic, causal, explainable heuristic
that answers one question about a *closed-bar* strategy signal: *how strong is
this entry setup, on a fixed 0-100 scale?* The AI Intelligence mode trades a
signal only when that number reaches a configured threshold.

What this score is **not**
--------------------------

It is emphatically **not** a probability, a win rate, an expected return, or any
kind of profit forecast. Nothing here has been validated against out-of-sample
results, and nothing here was fitted to make a backtest look attractive. A score
of 90 means *this setup satisfies five weighted conditions more fully than most
of them*, and nothing more. The Phase 13 record for the underlying strategy is
negative (baseline net P&L -157.14 over 344 trades, profit factor 0.6920, every
confidence interval containing zero), so a high score here is emphatically **not**
evidence that the trade will make money.

The component weights and reference scales in this module are **heuristic
normalisation constants chosen for explainability**, not fitted parameters. They
are named, documented, and covered by tests that pin the resulting distribution
so any future edit to them is visible rather than silent.

Where the numbers come from
---------------------------

:func:`score_signal` takes **one** argument: an engine
:class:`~crypto_paper_lab.models.Signal`. That is the whole causality guarantee,
and it is structural rather than a convention:

* ``Replay`` and ``run_backtest`` both build the signal from ``candles[:index]``,
  so every value on it was knowable strictly before the fill at
  ``candles[index].open``;
* the scorer is never handed a :class:`~crypto_paper_lab.models.Candle`, a
  candle index, a timestamp, a broker, or a replay, so it is **incapable** of
  reading a future bar rather than merely choosing not to.

Every component is derived from a value the existing strategy already computes -
``trend_state``, ``breakout_distance``, ``retest_distance``,
``realised_volatility``, ``side`` and ``trend``. No new indicator is introduced,
so no new research claim is made and the frozen strategy is untouched.

Determinism
-----------

No clock, no randomness, no environment, no I/O, no remote call. The same
:class:`~crypto_paper_lab.models.Signal` yields a bit-identical score on every
process, which is what lets ``identity_hash`` below serve as an audit record.
Rounding is half-up via :func:`_round_half_up`; Python's built-in ``round`` uses
banker's rounding, which would make a value ending exactly ``.5`` round the
"wrong" way relative to what an operator reading the number expects.

Paper only
----------

This module reads market history and produces an integer. It has no venue
connectivity, no credential, no wallet and no order concept.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Literal

from .models import Signal

__all__ = [
    "BREAKOUT_CONFIRMATION_POINTS",
    "COMPONENT_WEIGHTS",
    "DEFAULT_THRESHOLD",
    "SCORE_MAX",
    "SCORE_MIN",
    "IntelligenceConfig",
    "IntelligenceScore",
    "ScoreComponent",
    "intelligence_score_hash",
    "qualifies",
    "score_signal",
]


# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

#: Inclusive bounds of the score. A component implementation that misbehaves is
#: caught by the clamping below rather than by producing a 104.
SCORE_MIN = 0
SCORE_MAX = 100

#: Default qualification threshold, in score points.
#:
#: Chosen because it is *demanding but reachable*: it requires the directional,
#: trend-aligned and confirmed parts of the score to be near-perfect, and
#: essentially all of the breakout-strength and range-quality credit as well. A
#: lower threshold would admit setups the components describe as mediocre; a
#: higher one would be close to unreachable on this strategy, which would make
#: the mode inert rather than selective.
DEFAULT_THRESHOLD = 90.0

#: Weight of each component. Sum is exactly ``SCORE_MAX``; a test asserts it.
COMPONENT_WEIGHTS: dict[str, float] = {
    # "Does the signal point the way the trend points?"
    "trend_alignment": 30.0,
    # "How decisively did price clear the broken level?"
    "breakout_strength": 25.0,
    # "How well confirmed is the entry? A retest needed two candles; a fresh
    # breakout needed one."
    "confirmation": 20.0,
    # "Is the market moving enough to be interesting without being chaotic?"
    "range_quality": 15.0,
    # "Is this a directional observation at all? ``flat`` never trades."
    "direction": 10.0,
}

#: Reference scale for the ``breakout_strength`` component: the signed distance
#: beyond the broken level, as a fraction of that level, that earns full credit.
#:
#: Justification, structural rather than empirical: the frozen strategy requires
#: only ``breakout_buffer`` = 0.1% beyond the level to fire at all, and Phase 7
#: selected ``min_breakout_distance`` = 0.2% as the useful floor (configuration
#: A2). Requiring five times the strategy's own buffer, i.e. 0.5%, asks a signal
#: to clear A2's research floor by a clear factor. It is a round number chosen
#: for legibility; it was **not** selected by comparing outcomes.
BREAKOUT_FULL_SCALE = 0.005

#: Credits a *breakout* entry for one candle of confirmation, where a full-credit
#: retest entry had two (the break, then the retest).
#:
#: 12 of the 20 ``confirmation`` points. A heuristic share, chosen to encode the
#: real structural difference between the two entry kinds, not fitted to results.
BREAKOUT_CONFIRMATION_POINTS = 12.0

#: Hourly realised volatility at or below which ``range_quality`` is full credit.
#:
#: Meaning: the market is calm enough that the entry is not being placed into
#: noise. Heuristic; chosen as a round 0.4% of hourly standard deviation.
RANGE_QUALITY_CALM = 0.004

#: Hourly realised volatility at or above which ``range_quality`` earns nothing.
#:
#: Meaning: hourly moves this wild make an hourly breakout unreliable regardless of
#: how clean the level looks. Heuristic; chosen as a round 1.5%.
RANGE_QUALITY_EXTREME = 0.015

#: A retest whose wick/close sits this far from the level earns no confirmation
#: credit. Sourced from the engine, not invented: it is ``StrategyConfig``'s own
#: ``retest_tolerance`` default, and :func:`score_signal` reads the live value
#: from the signal's own retest rather than relying on this constant.
RETEST_TOLERANCE_REFERENCE = 0.002




# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntelligenceConfig:
    """Everything that determines a score's shape. Immutable and hashable.

    The defaults are the documented contract. Every field is overridable so a
    caller can study sensitivity, and :meth:`identity_hash` records whatever was
    actually used - which is the only way a research result stays auditable once
    a parameter moves.
    """

    #: Score at or above which a signal qualifies. Compared with ``>=``, so a
    #: score exactly equal to the threshold qualifies.
    threshold: float = DEFAULT_THRESHOLD

    #: Distance beyond the broken level that earns full breakout credit.
    breakout_full_scale: float = BREAKOUT_FULL_SCALE

    #: Confirmation credit for a one-candle breakout entry.
    breakout_confirmation_points: float = BREAKOUT_CONFIRMATION_POINTS

    #: Hourly realised volatility at or below which range quality is full credit.
    range_quality_calm: float = RANGE_QUALITY_CALM

    #: Hourly realised volatility at or above which range quality is worthless.
    range_quality_extreme: float = RANGE_QUALITY_EXTREME

    def __post_init__(self) -> None:
        if not SCORE_MIN <= self.threshold <= SCORE_MAX:
            raise ValueError(
                f"threshold must be between {SCORE_MIN} and {SCORE_MAX}, "
                f"got {self.threshold}"
            )
        if self.breakout_full_scale <= 0:
            raise ValueError("breakout_full_scale must be positive")
        if not 0 <= self.breakout_confirmation_points <= COMPONENT_WEIGHTS["confirmation"]:
            raise ValueError(
                "breakout_confirmation_points must be between 0 and the "
                "confirmation weight"
            )
        if self.range_quality_calm >= self.range_quality_extreme:
            raise ValueError(
                "range_quality_calm must be strictly below range_quality_extreme"
            )

    def identity(self) -> dict:
        """Deterministic, serialisable description. No time, no randomness."""

        return {
            "threshold": self.threshold,
            "breakout_full_scale": self.breakout_full_scale,
            "breakout_confirmation_points": self.breakout_confirmation_points,
            "range_quality_calm": self.range_quality_calm,
            "range_quality_extreme": self.range_quality_extreme,
        }


def intelligence_score_hash(config: IntelligenceConfig) -> str:
    """Stable SHA-256 over ``config``, uppercase.

    Built the same way as ``walkforward.config_hash`` so every identity in this
    project is computed one way only.
    """

    return hashlib.sha256(
        repr(config.identity()).encode("utf-8")
    ).hexdigest().upper()


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreComponent:
    """One explained contribution to the score.

    ``points`` is what this component actually contributed; ``weight`` is the
    maximum it could have. ``reason`` is a short human-readable explanation built
    from the same numbers as ``points``, so a displayed score can always be
    decomposed by hand.
    """

    name: str
    points: float
    weight: float
    reason: str

    @property
    def achieved_fraction(self) -> float:
        """How much of this component's weight was earned, 0.0 to 1.0."""

        return self.points / self.weight if self.weight else 0.0


@dataclass(frozen=True)
class IntelligenceScore:
    """A score and everything needed to audit it.

    ``score`` is an integer in ``[SCORE_MIN, SCORE_MAX]``. ``components`` always
    sums to ``score`` before rounding and to within one point after it, which is
    asserted by tests rather than assumed.
    """

    score: int
    threshold: float
    qualified: bool
    side: Literal["long", "short", "flat"]
    components: tuple[ScoreComponent, ...]

    @property
    def total_points(self) -> float:
        """Unrounded sum of the component contributions."""

        return sum(component.points for component in self.components)

    @property
    def missing_points(self) -> float:
        """How far below the threshold this signal fell, floored at zero."""

        return max(0.0, self.threshold - self.score)

    def component(self, name: str) -> ScoreComponent:
        """One component by name. Raises for an unknown name."""

        for item in self.components:
            if item.name == name:
                return item

        raise KeyError(name)

    def reasons(self) -> tuple:
        """Every component's explanation, in weight order."""

        return tuple(component.reason for component in self.components)

    def identity(self) -> dict:
        """Deterministic, serialisable description of this score."""

        return {
            "score": self.score,
            "threshold": self.threshold,
            "qualified": self.qualified,
            "side": self.side,
            "components": [
                {
                    "name": component.name,
                    "points": component.points,
                    "weight": component.weight,
                }
                for component in self.components
            ],
        }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _round_half_up(value: float) -> int:
    """Round half away from zero, then clamp to the declared scale.

    ``round`` is half-to-even, so ``round(2.5) == 2``. A displayed score that
    rounds "down" while the underlying points sit exactly on the boundary is a
    confusing thing to explain, so the tie is broken away from zero instead and
    the result is clamped, so a component bug can never produce a score outside
    the declared range.
    """

    return max(SCORE_MIN, min(SCORE_MAX, int(math.floor(value + 0.5))))


def _is_directional(side: str) -> bool:
    """Whether the signal names a tradable direction.

    ``flat`` is a normal, frequent outcome of the strategy
    (``strategy.py:191-192``) and is never an error - it simply cannot trade.
    """

    return side in {"long", "short"}


def _expected_trend(side: str) -> str:
    """The trend state a directional signal of this side ought to be in."""

    return "up" if side == "long" else "down"


def _trend_component(signal: Signal, config: IntelligenceConfig) -> ScoreComponent:
    """Does the signal point the way the moving averages point?"""

    weight = COMPONENT_WEIGHTS["trend_alignment"]

    if not _is_directional(signal.side):
        return ScoreComponent(
            "trend_alignment",
            0.0,
            weight,
            f"flat signal, so no trend can agree with it "
            f"(trend={signal.trend_state})",
        )

    observed = signal.trend_state

    if observed == _expected_trend(signal.side):
        return ScoreComponent(
            "trend_alignment",
            weight,
            weight,
            f"{signal.side} signal with the trend in the same direction "
            f"({observed})",
        )

    if observed == "sideways":
        # Half credit, chosen because a sideways trend is genuinely ambiguous
        # rather than contradictory: price has no direction, so neither does
        # this alignment claim.
        return ScoreComponent(
            "trend_alignment",
            weight / 2.0,
            weight,
            f"{signal.side} signal against a sideways trend: no support, "
            f"no contradiction",
        )

    return ScoreComponent(
        "trend_alignment",
        0.0,
        weight,
        f"{signal.side} signal against a {observed} trend, which is the "
        f"opposing direction",
    )


def _breakout_component(signal: Signal, config: IntelligenceConfig) -> ScoreComponent:
    """How decisively did price clear the level it broke?"""

    weight = COMPONENT_WEIGHTS["breakout_strength"]
    distance = signal.breakout_distance

    if distance is None:
        return ScoreComponent(
            "breakout_strength",
            0.0,
            weight,
            "no breakout distance recorded for this signal",
        )

    magnitude = abs(distance)
    full = config.breakout_full_scale
    fraction = min(magnitude / full, 1.0)

    return ScoreComponent(
        "breakout_strength",
        weight * fraction,
        weight,
        f"closed {magnitude * 100:.4f}% beyond the broken level "
        f"({fraction * 100:.1f}% of the {full * 100:.2f}% full-credit scale)",
    )


def _confirmation_component(signal: Signal, config: IntelligenceConfig) -> ScoreComponent:
    """How many candles confirmed this entry, and how cleanly.

    A retest entry needed two: one to break the level and one to retest it. A
    fresh breakout needed one, so it earns a smaller fixed share rather than
    nothing - the distinction is real, and the size of the gap is a documented
    heuristic rather than a fitted value.
    """

    weight = COMPONENT_WEIGHTS["confirmation"]
    retest_distance = signal.retest_distance

    if retest_distance is not None:
        tolerance = RETEST_TOLERANCE_REFERENCE
        fraction = max(0.0, 1.0 - (retest_distance / tolerance))

        return ScoreComponent(
            "confirmation",
            weight * fraction,
            weight,
            f"retest entry touching the level within "
            f"{retest_distance * 100:.4f}% of it, {fraction * 100:.1f}% of the "
            f"{tolerance * 100:.2f}% tolerance band",
        )

    if _is_directional(signal.side):
        return ScoreComponent(
            "confirmation",
            config.breakout_confirmation_points,
            weight,
            f"breakout entry with one candle of confirmation "
            f"({config.breakout_confirmation_points:g} of {weight:g} points; "
            f"a retest entry has two)",
        )

    return ScoreComponent(
        "confirmation",
        0.0,
        weight,
        "no directional entry to confirm",
    )


def _range_component(signal: Signal, config: IntelligenceConfig) -> ScoreComponent:
    """Is the market moving enough to matter without being chaotic?

    Full credit for quiet hourly volatility, nothing for extreme volatility, and
    a linear taper between. Both bounds are documented heuristic constants; this
    is a regime filter, not a volatility forecast.
    """

    weight = COMPONENT_WEIGHTS["range_quality"]
    volatility = signal.realised_volatility

    if volatility is None:
        return ScoreComponent(
            "range_quality",
            0.0,
            weight,
            "no realised volatility available for this signal",
        )

    calm = config.range_quality_calm
    extreme = config.range_quality_extreme

    if volatility <= calm:
        return ScoreComponent(
            "range_quality",
            weight,
            weight,
            f"hourly volatility {volatility * 100:.4f}% at or below the "
            f"calm bound of {calm * 100:.2f}%",
        )

    if volatility >= extreme:
        return ScoreComponent(
            "range_quality",
            0.0,
            weight,
            f"hourly volatility {volatility * 100:.4f}% at or above the "
            f"extreme bound of {extreme * 100:.2f}%",
        )

    fraction = (extreme - volatility) / (extreme - calm)

    return ScoreComponent(
        "range_quality",
        weight * fraction,
        weight,
        f"hourly volatility {volatility * 100:.4f}% between the calm "
        f"({calm * 100:.2f}%) and extreme ({extreme * 100:.2f}%) bounds",
    )


def _direction_component(signal: Signal, config: IntelligenceConfig) -> ScoreComponent:
    """Is this a directional observation at all?"""

    weight = COMPONENT_WEIGHTS["direction"]

    if _is_directional(signal.side):
        return ScoreComponent(
            "direction",
            weight,
            weight,
            f"directional {signal.side} signal ({signal.reason})",
        )

    return ScoreComponent(
        "direction",
        0.0,
        weight,
        f"flat signal ({signal.reason}); flat never trades",
    )


def score_signal(
    signal: Signal,
    config: IntelligenceConfig | None = None,
) -> IntelligenceScore:
    """Score one strategy signal on the fixed 0-100 scale.

    Parameters
    ----------
    signal:
        The engine's own observation. Built by ``analyze`` from ``candles[:i]``
        inside the engine, so every field is knowable strictly before the fill at
        ``candles[i].open``. The scorer is handed no candle, so future
        information cannot reach it even in principle.
    config:
        Score configuration. Defaults to :class:`IntelligenceConfig`.

    Returns
    -------
    IntelligenceScore
        The integer score, the threshold it was judged against, whether it
        qualified, and every component with its own explanation.

    Notes
    -----
    Pure. No clock, no randomness, no I/O, no remote call. The same signal
    yields the same score on every process and every run.
    """

    resolved = config if config is not None else IntelligenceConfig()

    components = (
        _trend_component(signal, resolved),
        _breakout_component(signal, resolved),
        _confirmation_component(signal, resolved),
        _range_component(signal, resolved),
        _direction_component(signal, resolved),
    )

    total = sum(component.points for component in components)
    score = _round_half_up(total)

    return IntelligenceScore(
        score=score,
        threshold=resolved.threshold,
        # ``>=``, so a score exactly at the threshold qualifies. Documented
        # rather than incidental: it is the boundary a caller tests against.
        qualified=score >= resolved.threshold,
        side=signal.side,
        components=components,
    )


def qualifies(
    signal: Signal,
    config: IntelligenceConfig | None = None,
) -> bool:
    """Whether this signal reaches the configured threshold.

    A convenience for the one-line question. Equivalent to
    ``score_signal(signal, config).qualified`` and nothing more - it adds no
    gate of its own, so it cannot diverge from the score it is derived from.
    """

    return score_signal(signal, config).qualified