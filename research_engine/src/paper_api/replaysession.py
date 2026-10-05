"""Transport-facing wrapper around exactly one authoritative ``Replay``.

Phase 17D. This module is deliberately thin. It exists for three reasons and no
others:

1. **Injection point.** ``create_app`` can be handed a prepared ``Replay`` so
   tests never pay for dataset loading, and so the same app factory serves both a
   real run and a controlled fixture.
2. **One lock.** Phase 17A §17.2 requires a single re-entrant lock around every
   mutating replay operation, because FastAPI runs non-async ``def`` endpoints in
   a threadpool - two concurrent requests genuinely can interleave between a
   cursor read and a cursor write and corrupt ``entry_index``.
3. **One error mapping.** The engine raises typed errors carrying a stable
   ``code``. Translating them here means the translation is written once instead
   of five times, and it keeps the mapping auditable in one place.

**No trading state lives here.** This module holds a reference to a ``Replay`` and
a lock. It does not cache the cursor, balance, position, journal, status or last
signal; every response is built from ``Replay.state`` read at request time. If a
field appears in a response it came from the engine in that same call.

Transport shape follows the Phase 16 convention: ``FastAPI`` runs these
endpoints in a threadpool, so they are plain ``def`` and the lock - not an event
loop - provides serialisation. There is no background worker, no thread of our
own, and no timer: Phase 17D forbids them, so ``running`` is a lifecycle flag and
the HTTP client drives progression through ``/api/replay/step``.
"""
from __future__ import annotations

import threading

from fastapi import HTTPException

from crypto_paper_lab.replay import (
    InvalidIntervalError,
    InvalidStartIndexError,
    PositionOpenError,
    Replay,
    ReplayError,
    ReplayFinishedError,
    ReplayState,
)
from crypto_paper_lab.walkforward import baseline_config, phase13_costs

from .config import SERVICE_NAME
from .marketdata import dataset_identity, load_research_candles
from .session import PaperSession


#: Phase 17A §21, applied at the transport boundary only.
#:
#: ``InvalidIntervalError`` maps to 400 exactly as the architecture table
#: specifies. Phase 17A §21.1 recommends 422 instead and records that as open
#: question Q9; the architecture's literal mapping is implemented here and the
#: divergence is left open rather than silently resolved.
#:
#: The base ``ReplayError`` is deliberately absent. Anything not listed here
#: propagates and surfaces as a 500 rather than being folded into a tidy
#: response, because a catch-all handler would hide exactly the programming
#: errors it appears to be protecting against.
ERROR_STATUS: dict[str, int] = {
    "REPLAY_FINISHED": 409,
    "POSITION_OPEN": 409,
    "INVALID_TRANSITION": 409,
    "INSUFFICIENT_HISTORY": 422,
    "INVALID_INTERVAL": 400,
    "INVALID_COUNT": 400,
    "INVALID_MODE": 422,
}

#: Engine exception -> HTTP status. Keyed on the exception's ``code`` so the
#: engine stays free of any HTTP knowledge.
ERROR_EXCEPTIONS: dict[str, type[ReplayError]] = {
    ReplayFinishedError.code: ReplayFinishedError,
    PositionOpenError.code: PositionOpenError,
    InvalidStartIndexError.code: InvalidStartIndexError,
    InvalidIntervalError.code: InvalidIntervalError,
}


class ReplaySession:
    """A single in-process paper replay, addressed over HTTP.

    There is exactly one per application process. No authentication, no accounts,
    no multi-user routing and no persistence: Phase 17D is a local single-user
    research tool, and adding session infrastructure for a loopback service would
    be infrastructure answering a problem that cannot occur.
    """

    def __init__(self, replay: Replay | None = None) -> None:
        self._replay = replay
        # Re-entrant so a nested call on the same thread cannot self-deadlock.
        self._lock = threading.RLock()
        self._session = PaperSession(service=SERVICE_NAME)

    # -- introspection ------------------------------------------------------

    @property
    def lock(self) -> threading.RLock:
        """The serialisation lock, exposed so tests can prove it is shared."""

        return self._lock

    @property
    def session(self) -> PaperSession:
        """The Phase 16 account projection, always bound to the current broker.

        Rebound in place rather than replaced, so the object the Phase 16 routes
        captured at start-up stays valid *and* stays current.
        """

        with self._lock:
            self._sync_session()

            return self._session

    def _sync_session(self) -> None:
        """Point the session at whatever broker the replay holds right now."""

        broker = self.replay.broker

        if self._session.broker is not broker:
            self._session.use_broker(broker)

    @property
    def replay(self) -> Replay:
        """The authoritative replay, constructed on first use.

        Construction is deferred rather than done in ``create_app`` so the service
        starts as fast as it did in Phase 16 and ``/healthz`` is available without
        first loading 17,544 candles. The dataset itself is *not* loaded twice:
        this calls the same ``marketdata.load_research_candles`` that
        ``/api/market`` and ``/api/signal`` already use, and that function is
        ``lru_cache``d per process.
        """

        if self._replay is None:
            with self._lock:
                if self._replay is None:
                    # The frozen Phase 13 baseline configuration and costs, so the
                    # replay is the same strategy the research record describes.
                    # Both come from walkforward - no defaults are re-declared
                    # here.
                    self._replay = Replay(
                        load_research_candles(),
                        config=baseline_config(),
                        costs=phase13_costs(),
                        dataset_sha256=dataset_identity(),
                    )

        return self._replay

    # -- operations ---------------------------------------------------------

    def snapshot(self) -> ReplayState:
        """Current authoritative state. Never cached."""

        with self._lock:
            self._sync_session()

            return self.replay.state

    def start(self, interval_ms: int | None = None) -> ReplayState:
        with self._lock:
            return self._call(self.replay.start, interval_ms)

    def pause(self) -> ReplayState:
        with self._lock:
            return self._call(self.replay.pause)

    def step(self) -> ReplayState:
        with self._lock:
            return self._call(self.replay.step)

    def reset(self) -> ReplayState:
        with self._lock:
            return self._call(self.replay.reset)

    # -- internals ----------------------------------------------------------

    def _call(self, method, *args) -> ReplayState:
        """Invoke one engine method and return the state it produced.

        Every mutating route funnels through here so the lock, the error mapping
        and the "always re-read the state" rule are each stated once.
        """

        try:
            method(*args)
        except ReplayError as exc:
            raise _to_http(exc) from exc

        # A reset installs a new broker, so the Phase 16 account view must follow
        # it before any response is built from that view.
        self._sync_session()

        # Re-read after the call. Never reuse a value captured beforehand: the
        # engine is the only thing that knows what just changed.
        return self.replay.state


def _to_http(exc: ReplayError) -> HTTPException:
    """Translate one known engine error into an HTTP response.

    The body is ``{"detail": {"code", "message"}}``: machine-readable, stable
    across versions, and free of any traceback or internal path.

    An error with no declared mapping is **re-raised unchanged**. There is
    deliberately no catch-all: a generic handler that turned every unexpected
    engine failure into a tidy response would hide exactly the programming errors
    it appears to be protecting against, and would make an unmapped invariant
    violation indistinguishable from a designed refusal.
    """

    status = ERROR_STATUS.get(exc.code)

    if status is None:
        raise exc

    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


__all__ = [
    "ERROR_EXCEPTIONS",
    "ERROR_STATUS",
    "ReplaySession",
]