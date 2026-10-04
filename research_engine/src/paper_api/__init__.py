"""Local paper-trading HTTP API.

This package is a **separate top-level package** from ``crypto_paper_lab`` on
purpose. The research engine is the single source of truth for trading
behaviour, and nothing in ``crypto_paper_lab`` may ever import this package.
The API is a thin transport layer: it owns no strategy, sizing, execution,
accounting or cost logic, and it computes no trading value of its own.

Phase 16A scope is liveness only - a single ``GET /healthz`` route. There is
deliberately no session, market-data, signal, position, trade, replay or
statistics endpoint yet, no persistence, and no strategy execution.

**Paper trading only.** There is no exchange connectivity, no order
submission, no wallet, and no credential handling anywhere in this package.
"""

from .app import HEALTH_RESPONSE, create_app
from .config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    SERVICE_NAME,
    ApiConfig,
    UnsafeBindError,
    config_from_env,
)
from .schemas import SessionResponse
from .session import (
    MODE_PAPER,
    STATE_IDLE,
    UNSUPPORTED_FIELDS,
    AccountState,
    ExecutionIdentity,
    PaperSession,
    SessionView,
    StrategyIdentity,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "HEALTH_RESPONSE",
    "MODE_PAPER",
    "SERVICE_NAME",
    "STATE_IDLE",
    "UNSUPPORTED_FIELDS",
    "AccountState",
    "ApiConfig",
    "ExecutionIdentity",
    "PaperSession",
    "SessionResponse",
    "SessionView",
    "StrategyIdentity",
    "UnsafeBindError",
    "config_from_env",
    "create_app",
]