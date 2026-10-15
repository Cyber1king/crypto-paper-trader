"""Concurrent budget exhaustion in the offline Stage 0 provider.

Phase 81B/81C found by inspection that the budget check and the budget charge
were not atomic: ``would_exceed`` and ``begin_call`` sit roughly forty lines
apart and neither is under a lock. Under concurrent callers, every thread can
observe the same remaining budget, pass the check, and then all dispatch -- so
``max_calls`` bounds nothing.

This module pins the invariant that ``max_calls`` is a real bound on provider
invocations, and that the meter stays consistent while it holds.

No network, no credentials, no trading-engine imports, and no real provider:
the fake is a deterministic in-process counter. Every assertion is an invariant
rather than a timing observation, so the test cannot pass by getting lucky.
"""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone

import pytest

from crypto_paper_lab.ai_offline import (
    AiBudget,
    OfflineAIStage0,
    OfflineCallStatus,
    OfflineFakeProvider,
)
from crypto_paper_lab.ai_research import ProviderRequest

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

MAX_CALLS = 2
THREADS = 6
ROUNDS = 40


class CountingProvider(OfflineFakeProvider):
    """A fake provider whose invocation count is guarded by its own lock.

    ``OfflineFakeProvider.calls`` is a plain list; counting through it would
    rely on ``list.append`` happening to be atomic. The property under test is
    about admitted invocations, so the counter is explicit about its own
    thread-safety rather than inheriting an accident.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._count = 0

    @property
    def invocations(self) -> int:
        with self._lock:
            return self._count

    def analyse(self, request, *, timeout_seconds=30.0, max_retries=2):
        with self._lock:
            self._count += 1
        return super().analyse(
            request, timeout_seconds=timeout_seconds, max_retries=max_retries
        )


def _request() -> ProviderRequest:
    return ProviderRequest(
        instrument_id="BTC/USDT",
        timeframe="1h",
        market_type="crypto_spot",
        question="What changed in the referenced evidence?",
        evidence_ids=("ev-001",),
    )


def _race(provider, *, threads: int = THREADS, max_calls: int = MAX_CALLS):
    """Release ``threads`` callers simultaneously against a shared stage."""

    stage = OfflineAIStage0(
        provider=provider,
        budget=AiBudget(max_calls=max_calls),
        now_fn=lambda: NOW,
    )
    barrier = threading.Barrier(threads)
    outcomes: list[OfflineCallStatus] = []
    results_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        _, record = stage.run(_request())
        with results_lock:
            outcomes.append(record.status)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()
    return stage, outcomes


@pytest.fixture()
def switch_often():
    """Make the interpreter yield the GIL aggressively.

    The check-then-act window is a handful of bytecodes wide. Without frequent
    context switches a race can go unobserved for thousands of rounds, which
    would make this suite report a green light on a broken invariant.
    """

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_callers_cannot_exceed_max_calls(switch_often) -> None:
    """The core regression: ``max_calls`` must bound real invocations."""

    for _ in range(ROUNDS):
        provider = CountingProvider()
        _, _ = _race(provider)
        assert provider.invocations <= MAX_CALLS, (
            f"admitted {provider.invocations} provider invocations under a "
            f"{MAX_CALLS}-call budget"
        )


def test_the_meter_never_exceeds_the_budget_across_contention(switch_often) -> None:
    """Accounting must stay inside the bound, not merely report it."""

    for _ in range(ROUNDS):
        provider = CountingProvider()
        stage, _ = _race(provider)
        assert stage.meter.calls <= MAX_CALLS, (
            f"meter recorded {stage.meter.calls} calls under a "
            f"{MAX_CALLS}-call budget"
        )
        assert stage.meter.calls == provider.invocations, (
            "the meter and the provider disagree about how many calls "
            f"happened: {stage.meter.calls} vs {provider.invocations}"
        )


def test_excess_callers_are_refused_not_silently_admitted(switch_often) -> None:
    """Callers past the budget get an explicit refusal record."""

    provider = CountingProvider()
    _, outcomes = _race(provider)
    refused = sum(1 for s in outcomes if s is OfflineCallStatus.BUDGET_REFUSED)
    assert refused > 0, "no caller was told the budget was exhausted"
    assert provider.invocations <= MAX_CALLS


def test_every_concurrent_caller_still_leaves_exactly_one_audit_record(
    switch_often,
) -> None:
    """Budget enforcement must not lose audit entries."""

    provider = CountingProvider()
    stage, outcomes = _race(provider)
    assert len(stage.log) == THREADS
    assert len({r.call_id for r in stage.log}) == THREADS
    assert len(outcomes) == THREADS
    assert all(r.is_offline for r in stage.log)


def test_concurrency_does_not_weaken_the_per_step_guarantees() -> None:
    """The fix must not reintroduce duplicate ids or a shared-mutation race."""

    provider = CountingProvider()
    stage = OfflineAIStage0(
        provider=provider,
        budget=AiBudget(max_calls=100),
        now_fn=lambda: NOW,
    )
    barrier = threading.Barrier(THREADS)

    def worker() -> None:
        barrier.wait()
        stage.run(_request())

    workers = [threading.Thread(target=worker) for _ in range(THREADS)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()

    assert len({r.call_id for r in stage.log}) == THREADS
    assert stage.meter.calls == THREADS


def test_timeout_enforcement_survives_concurrent_use() -> None:
    """A slow provider must still be cut off at the deadline."""

    provider = OfflineFakeProvider(delay_seconds=0.5)
    stage = OfflineAIStage0(
        provider=provider,
        budget=AiBudget(max_calls=10),
        now_fn=lambda: NOW,
    )
    barrier = threading.Barrier(3)

    def worker() -> None:
        barrier.wait()
        stage.run(_request(), timeout_seconds=0.05)

    workers = [threading.Thread(target=worker) for _ in range(3)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()

    assert [r.status for r in stage.log] == [OfflineCallStatus.TIMED_OUT] * 3
    assert all(r.work_abandoned for r in stage.log)