"""Configuration for the local paper-trading API.

Configuration is deliberately tiny: a bind address and a port. There is no
secret, token, API key or credential in this module, and none is read from the
environment. ``MARKET_DATA_API_KEY`` exists elsewhere in the project for a
future *public* price-data provider and is deliberately **not** consumed here.

The bind address is constrained to loopback. This is a safety property, not a
convenience: a service bound to ``0.0.0.0`` would be reachable from the local
network, and the architecture audit already flagged the existing Express
scaffold for binding every interface. Refusing a non-loopback address at
construction time is cheaper than discovering it in production.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

#: Loopback-only. ``127.0.0.1`` is the default because it is unambiguous;
#: ``localhost`` resolves to either IPv4 or IPv6 depending on the host.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

#: Reported by ``/healthz``. Fixed so the response is byte-deterministic.
SERVICE_NAME = "crypto-paper-lab"

#: Environment variable names. Documented in ``.env.example``; never in a
#: real ``.env``, which is git-ignored.
HOST_ENV_VAR = "PAPER_API_HOST"
PORT_ENV_VAR = "PAPER_API_PORT"

#: The only bind addresses this service will accept.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

MIN_PORT = 1
MAX_PORT = 65535


class UnsafeBindError(ValueError):
    """Raised when a non-loopback bind address is requested.

    A distinct type so a caller can tell "you asked for something unsafe"
    apart from "that is not a valid port".
    """


@dataclass(frozen=True)
class ApiConfig:
    """Validated, immutable API configuration."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    service: str = SERVICE_NAME

    def __post_init__(self) -> None:
        if self.host not in LOOPBACK_HOSTS:
            raise UnsafeBindError(
                f"refusing to bind {self.host!r}: this service is "
                f"localhost-only. Permitted hosts: "
                f"{', '.join(sorted(LOOPBACK_HOSTS))}"
            )

        if not MIN_PORT <= self.port <= MAX_PORT:
            raise ValueError(
                f"port must be between {MIN_PORT} and {MAX_PORT}, "
                f"got {self.port!r}"
            )

    @property
    def bind_description(self) -> str:
        """Human-readable origin, for logs and documentation."""

        return f"http://{self.host}:{self.port}"


def config_from_env(env: Mapping[str, str] | None = None) -> ApiConfig:
    """Build a config from environment variables, falling back to defaults.

    ``env`` is injectable so tests do not have to mutate ``os.environ``.
    An unparseable port is ignored in favour of the default rather than
    raising, so a stray variable cannot stop the service from starting -
    though a non-loopback host *is* rejected outright, because that is a
    safety property rather than a convenience.
    """

    source = os.environ if env is None else env

    raw_port = source.get(PORT_ENV_VAR, "").strip()

    try:
        port = int(raw_port) if raw_port else DEFAULT_PORT
    except ValueError:
        port = DEFAULT_PORT

    return ApiConfig(
        host=source.get(HOST_ENV_VAR, "").strip() or DEFAULT_HOST,
        port=port,
    )