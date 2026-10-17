"""The two-level dataset-integrity guard in :class:`Replay`.

Making the dataset fingerprint content-based turned a per-step guard into an
O(n) one, which made a full replay quadratic. The guard was split: O(1) on every
step, and one O(n) content digest when the series is exhausted.

Splitting a safety check weakens it unless the weaker level is pinned, so these
tests hold both levels to their stated contract. They use a small synthetic
series so the O(n) level is actually exercised without a multi-minute run.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from crypto_paper_lab.walkforward import baseline_config, phase13_costs
from crypto_paper_lab.models import Candle
from crypto_paper_lab.replay import Replay, ReplayError, ReplayFinishedError

BASE = datetime(2024, 1, 1)
COUNT = 400


def series(count: int = COUNT) -> list[Candle]:
    """A drifting synthetic series with enough bars to trade on."""

    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=100.0 + i * 0.1,
            high=101.0 + i * 0.1,
            low=99.0 + i * 0.1,
            close=100.5 + i * 0.1,
            volume=10.0 + i,
        )
        for i in range(count)
    ]


def new_replay(candles: list[Candle] | None = None) -> Replay:
    return Replay(
        series() if candles is None else candles,
        config=baseline_config(),
        costs=phase13_costs(),
    )


def exhaust(replay: Replay) -> None:
    """Step to the end of the series.

    Stops on ``ReplayFinishedError`` rather than on ``ReplayError``, because
    ``ReplayFinishedError`` subclasses it -- catching the parent here would
    swallow the dataset-mutation error these tests exist to observe.
    """

    for _ in range(len(replay._candles) + 5):
        try:
            replay.step()
        except ReplayFinishedError:
            return


# 1. the cheap per-step level
def test_a_clean_run_raises_nothing():
    exhaust(new_replay())


def test_replacing_the_identity_record_is_caught_on_the_next_step():
    """Swapping the provenance record is tampering, and is O(1) to catch."""

    replay = new_replay()
    replay.step()
    replay._fingerprint = ("tampered",)  # type: ignore[assignment]
    with pytest.raises(ReplayError, match="dataset identity changed"):
        replay.step()


def test_mutating_a_frozen_candle_in_place_is_caught_on_the_next_step():
    """A frozen dataclass is not immutable, only difficult.

    ``object.__setattr__`` writes around the frozen guard. That is the one way
    the series can change under a replay that owns an immutable snapshot of it,
    so it is the case the per-step check exists for.
    """

    replay = new_replay()
    replay.step()
    first = replay._candles[0]
    object.__setattr__(first, "close", first.close + 5.0)

    with pytest.raises(ReplayError, match="dataset changed"):
        replay.step()


def test_mutating_the_last_candle_in_place_is_caught_on_the_next_step():
    replay = new_replay()
    replay.step()
    last = replay._candles[-1]
    object.__setattr__(last, "close", last.close + 5.0)

    with pytest.raises(ReplayError, match="dataset changed"):
        replay.step()


def test_the_caller_cannot_reach_the_replays_own_copy():
    """The series is snapshotted, so external mutation cannot occur at all.

    This is why the guard exists as defence in depth rather than as the primary
    protection: the primary protection is that there is nothing to mutate.
    """

    candles = series()
    replay = new_replay(candles)
    original_close = replay._candles[200].close

    candles[200] = replace(candles[200], close=-999.0)
    candles.pop()

    assert replay._candles[200].close == original_close
    assert len(replay._candles) == COUNT


# 2. the full content level at end of series
def test_an_interior_mutation_is_caught_when_the_series_is_exhausted():
    """The interior is invisible to the O(1) level by construction.

    This is the guarantee that makes the split acceptable: what the cheap check
    cannot see, the single end-of-data digest does.
    """

    replay = new_replay()
    candle = replay._candles[200]
    object.__setattr__(candle, "close", candle.close + 7.0)

    with pytest.raises(ReplayError, match="dataset changed"):
        exhaust(replay)


def test_a_tiny_interior_change_is_still_caught():
    """The digest covers the exact bits, not a rounded approximation."""

    replay = new_replay()
    candle = replay._candles[150]
    object.__setattr__(candle, "volume", candle.volume + 1e-12)

    with pytest.raises(ReplayError, match="dataset changed"):
        exhaust(replay)


def test_each_field_is_covered_by_the_end_of_series_digest():
    for field in ("open", "high", "low", "close", "volume"):
        replay = new_replay()
        candle = replay._candles[250]
        object.__setattr__(candle, field, float(getattr(candle, field)) + 0.5)
        with pytest.raises(ReplayError, match="dataset changed"):
            exhaust(replay)


# 3. the documented tolerance
def test_an_interior_mutation_reverted_before_completion_is_tolerated():
    """Documented behaviour, pinned so it cannot change silently.

    Altering the future and restoring it cannot affect any result, because a
    signal at step *i* reads only candles before *i*. Detecting it would cost a
    full digest per step to guard a case that is provably harmless.
    """

    replay = new_replay()
    candle = replay._candles[200]
    original = candle.close
    object.__setattr__(candle, "close", original + 99.0)
    object.__setattr__(candle, "close", original)

    exhaust(replay)  # must not raise


# 4. cost of the split
def test_the_per_step_check_does_not_digest_the_series():
    """A per-step digest would be O(n); assert it is not happening.

    Patching the fingerprint function to count calls makes the contract
    observable: one call at construction, one at end of series, none between.
    """

    import crypto_paper_lab.replay as replay_module

    calls = {"n": 0}
    original = replay_module.dataset_fingerprint

    def counting(seq):
        calls["n"] += 1
        return original(seq)

    replay_module.dataset_fingerprint = counting
    try:
        replay = new_replay()
        assert calls["n"] == 1, "construction must digest once"

        for _ in range(50):
            replay.step()
        assert calls["n"] == 1, "stepping must not re-digest"

        exhaust(replay)
        assert calls["n"] == 2, "end of series must digest exactly once more"
    finally:
        replay_module.dataset_fingerprint = original
