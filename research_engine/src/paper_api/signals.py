"""Read-only strategy signals from the authoritative engine.

This module calls :func:`crypto_paper_lab.strategy.analyze` and nothing else.
It contains **no** breakout detection, no retest detection, no trend
detection, no support/resistance calculation, no distance thresholds, no
sizing and no cost logic. Every trading value in the response originates in
the ``Signal`` object that ``analyze`` returned.

Candle semantics
----------------
``analyze(candles, config)`` treats the **last** element of the sequence as
``current`` - the signal candle - and ``candles[-2]`` as ``previous``. Levels
come from ``candles[:-2]``. Passing ``candles[:index + 1]`` therefore makes
``candles[index]`` the signal candle, and nothing after ``index`` is visible to
the strategy. That one-candle gap is the same boundary the walk-forward
harness relies on, and it is preserved here unchanged.

Note the deliberate distinction from execution: in ``run_backtest`` the signal
produced from ``candles[:index]`` is then filled at ``candles[index].open``.
This module evaluates the signal *for* a chosen candle and performs no fill,
so it never rewrites ``Signal.price``. For the signal candle,
``price`` and ``signal_close`` are therefore equal.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from crypto_paper_lab.models import Signal
from crypto_paper_lab.strategy import StrategyConfig, analyze


class SignalLookupError(Exception):
    """Base class for signal-resolution failures."""


class UnknownTimestampError(SignalLookupError):
    """The requested instant is not a bar in the dataset."""


class InsufficientHistoryError(SignalLookupError):
    """Too few preceding candles for the configured strategy."""


def minimum_history(config: StrategyConfig) -> int:
    """Candles ``analyze`` requires, derived from the config rather than fixed.

    Mirrors the engine's own guard: ``max(lookback + 2, slow_period)``. For the
    frozen baseline that is 22. Reading it from the config means a different
    configuration cannot silently disagree with the engine.
    """

    return max(config.lookback + 2, config.slow_period)


def signal_at_index(
    candles: Sequence,
    config: StrategyConfig,
    index: int,
) -> Signal:
    """Run the real strategy with ``candles[index]`` as the signal candle."""

    if index < 0 or index >= len(candles):
        raise IndexError(f"candle index {index} is out of range")

    required = minimum_history(config)

    if index + 1 < required:
        raise InsufficientHistoryError(
            f"a signal at index {index} needs {required} candles of history; "
            f"only {index + 1} available"
        )

    # The slice is the causality boundary. Everything after `index` is
    # structurally unreachable from here.
    return analyze(candles[: index + 1], config)


def resolve_signal(
    candles: Sequence,
    config: StrategyConfig,
    at: datetime | None = None,
    index_of: dict | None = None,
) -> Signal:
    """Resolve the signal for ``at``, or for the latest completed candle.

    ``at`` must match a bar **exactly**. A near miss is an error, never an
    interpolation: fabricating a bar the market did not produce would be worse
    than refusing to answer.
    """

    if at is None:
        return signal_at_index(candles, config, len(candles) - 1)

    if index_of is None:
        raise UnknownTimestampError(
            "an exact timestamp lookup table is required to resolve `at`"
        )

    from .marketdata import as_naive_utc

    key = as_naive_utc(at)

    if key not in index_of:
        raise UnknownTimestampError(
            f"no candle exists at the requested timestamp in this dataset"
        )

    return signal_at_index(candles, config, index_of[key])