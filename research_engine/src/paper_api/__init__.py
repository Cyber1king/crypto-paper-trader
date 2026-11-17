"""Local paper-trading HTTP API package.

The full application factory is imported lazily so importing package-level
configuration and schemas does not initialize a trading session.
"""
from __future__ import annotations

HEALTH_RESPONSE: dict[str, str] = {
    "status": "ok",
    "service": "crypto-paper-lab",
}

def create_app(*args, **kwargs):
    """Import and construct the full API only when explicitly requested."""
    from .app import create_app as factory
    return factory(*args, **kwargs)

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
    "DEFAULT_HOST", "DEFAULT_PORT", "HEALTH_RESPONSE", "MODE_PAPER",
    "SERVICE_NAME", "STATE_IDLE", "UNSUPPORTED_FIELDS", "AccountState",
    "ApiConfig", "ExecutionIdentity", "PaperSession", "SessionResponse",
    "SessionView", "StrategyIdentity", "UnsafeBindError", "config_from_env",
    "create_app",
]
