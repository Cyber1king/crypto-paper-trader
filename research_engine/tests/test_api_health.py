"""Phase 16A tests for the local paper-trading API.

Scope is intentionally narrow: liveness only. These tests pin the health
contract, the localhost-only safety property, and the absence of anything
trading-related. The last group matters as much as the first - a route that
appears without a test would be a scope breach, so the route set is asserted
explicitly.
"""
from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient

from paper_api.app import HEALTH_RESPONSE, create_app
from paper_api.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HOST_ENV_VAR,
    LOOPBACK_HOSTS,
    PORT_ENV_VAR,
    SERVICE_NAME,
    ApiConfig,
    UnsafeBindError,
    config_from_env,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(ApiConfig()))


# ---------------------------------------------------------------------------
# 1. the health contract
# ---------------------------------------------------------------------------


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200


def test_healthz_returns_the_exact_expected_payload(
    client: TestClient,
) -> None:
    response = client.get("/healthz")

    assert response.json() == {
        "status": "ok",
        "service": "crypto-paper-lab",
    }


def test_healthz_payload_is_the_declared_constant() -> None:
    """Guards against the constant and the route drifting apart."""

    assert HEALTH_RESPONSE == {"status": "ok", "service": SERVICE_NAME}


def test_healthz_is_byte_deterministic(client: TestClient) -> None:
    """No timestamps, counters or hostnames may leak into the response."""

    first = client.get("/healthz")
    second = client.get("/healthz")

    assert first.content == second.content
    assert first.headers.get("content-type") == (
        second.headers.get("content-type")
    )


def test_healthz_does_not_mutate_the_shared_constant(
    client: TestClient,
) -> None:
    before = dict(HEALTH_RESPONSE)
    client.get("/healthz")
    assert HEALTH_RESPONSE == before


# ---------------------------------------------------------------------------
# 2. localhost-only safety boundary
# ---------------------------------------------------------------------------


def test_default_config_is_loopback() -> None:
    config = ApiConfig()

    assert config.host == DEFAULT_HOST == "127.0.0.1"
    assert config.host in LOOPBACK_HOSTS
    assert config.port == DEFAULT_PORT == 8000


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_non_loopback_binds_are_refused(host: str) -> None:
    """The service must never be reachable off the local machine."""

    with pytest.raises(UnsafeBindError):
        ApiConfig(host=host)


def test_unsafe_bind_error_is_a_value_error() -> None:
    """So a generic handler still catches it."""

    assert issubclass(UnsafeBindError, ValueError)


@pytest.mark.parametrize("port", [0, -1, 65536, 100000])
def test_out_of_range_ports_are_refused(port: int) -> None:
    with pytest.raises(ValueError):
        ApiConfig(port=port)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_permitted_loopback_hosts_are_accepted(host: str) -> None:
    assert ApiConfig(host=host).host == host


# ---------------------------------------------------------------------------
# 3. environment configuration
# ---------------------------------------------------------------------------


def test_env_overrides_host_and_port() -> None:
    config = config_from_env({HOST_ENV_VAR: "::1", PORT_ENV_VAR: "9001"})

    assert config.host == "::1"
    assert config.port == 9001


def test_env_falls_back_to_defaults_when_unset() -> None:
    config = config_from_env({})

    assert config.host == DEFAULT_HOST
    assert config.port == DEFAULT_PORT


def test_unparseable_port_falls_back_rather_than_crashing() -> None:
    config = config_from_env({PORT_ENV_VAR: "not-a-number"})

    assert config.port == DEFAULT_PORT


def test_env_cannot_widen_the_bind_beyond_loopback() -> None:
    """A stray variable must not defeat the safety property."""

    with pytest.raises(UnsafeBindError):
        config_from_env({HOST_ENV_VAR: "0.0.0.0"})


def test_config_reads_no_secret(monkeypatch) -> None:
    """No credential may be read from the environment."""

    monkeypatch.setenv("MARKET_DATA_API_KEY", "should-be-ignored")

    config = config_from_env()

    assert not hasattr(config, "api_key")
    assert "should-be-ignored" not in repr(config)


# ---------------------------------------------------------------------------
# 4. Phase 16A scope: nothing trading-related exists yet
# ---------------------------------------------------------------------------


def test_only_the_permitted_routes_exist(client: TestClient) -> None:
    """Scope guard, updated deliberately at each phase.

    Phase 16A allowed only ``/healthz``; 16B added ``/api/session``; 16C added
    ``/api/market``; 16D added ``/api/signal``; 16E added ``/api/account``,
    ``/api/position`` and ``/api/trades``; 16F added ``/api/statistics``.
    Phase 17D added the five ``/api/replay`` control routes; 17F added
    ``/api/modes``; 17G added ``/api/ai``. Any further route must be a conscious
    decision with its own tests, not a by-product.
    """

    paths = {
        route.path
        for route in client.app.routes
        if getattr(route, "path", None)
    }

    assert paths == {
        "/healthz",
        "/api/session",
        "/api/market",
        "/api/signal",
        "/api/account",
        "/api/position",
        "/api/trades",
        "/api/statistics",
        "/api/replay",
        "/api/modes",
        "/api/ai",
        "/api/replay/start",
        "/api/replay/pause",
        "/api/replay/step",
        "/api/replay/reset",
    }


@pytest.mark.parametrize(
    "path",
    [
        "/orders",
        "/api/order",
        "/api/execute",
        "/api/alerts",
        "/api/daily",
        "/api/manual",
        "/api/high-risk",
        "/api/equity",
        "/api/position/close",
        "/api/position/close-all",
        "/api/orders",
        "/api/alerts",
        "/api/replay/seek",
        "/api/modes/ai_intelligence",
        "/api/ai/step",
        "/api/ai/reset",
    ],
)
def test_deferred_routes_do_not_exist(client: TestClient, path: str) -> None:
    """Deferred routes stay absent.

    ``/api/statistics``, ``/api/session``, ``/api/market``, ``/api/signal``,
    ``/api/account``, ``/api/position``, ``/api/trades`` and the five
    ``/api/replay`` control routes are deliberately excluded: each was added in its
    own phase with its own tests.

    ``/api/equity`` is listed because the equity curve is *not* a replay or
    statistics endpoint - it needs a live mark price the engine cannot produce.
    ``/api/position/close`` stays absent because Phase 17A decision Q1 declined
    manual close. ``/api/replay/seek`` stays absent because rewinding is
    ``reset`` plus ``step(count)``, and adding a seek would be a second way to do
    one thing.

    Phase 17G adds five more absences, each for a stated reason:

    * ``/api/orders``, ``/api/orders/close``-style paths and ``/api/alerts`` -
      there is no order concept and no notification delivery in this system.
      Alerts has no broker at all (Phase 17A §12.1), so there is nothing for a
      notification to have caused.
    * ``/api/position/close-all`` - declined with Q1.
    * ``/api/modes/ai_intelligence`` - mode *contracts* are discovered through
      ``GET /api/modes``; a per-mode configuration endpoint would be a second
      source for configuration that ``ModeSpec`` already reports.
    * ``/api/ai/step`` and ``/api/ai/reset`` - AI progression uses the same
      ``/api/replay/step`` and ``/api/replay/reset`` routes every other mode uses,
      with ``?mode=ai_intelligence``. Separate verbs would be a second way to do
      one thing.
    """

    assert client.get(path).status_code == 404


def test_session_route_is_read_only(client: TestClient) -> None:
    """No verb other than GET may reach the session route."""

    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/session")
        assert response.status_code == 405, method


def test_no_wildcard_cors_header(client: TestClient) -> None:
    response = client.get("/healthz", headers={"Origin": "http://evil.test"})

    assert "access-control-allow-origin" not in response.headers


def test_interactive_docs_are_disabled(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


# ---------------------------------------------------------------------------
# 5. separation from the research engine
# ---------------------------------------------------------------------------


def _imported_modules(path) -> set[str]:
    """Top-level module names actually imported by a source file.

    Parsed from the AST rather than grepped, because these modules document
    the separation in prose and a text search would match the explanation
    instead of the dependency.
    """

    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])

    return names


#: The only engine modules the API is permitted to consume. Phase 16A imported
#: none; 16B introduced ``/api/session`` and 16C introduced ``/api/market``,
#: which needs the authoritative broker, the frozen strategy/cost identities,
#: and the existing dataset loader and validator.
ALLOWED_ENGINE_IMPORTS = {
    "simulator",     # PaperBroker - the authoritative account state
    "walkforward",   # frozen STARTING_BALANCE, RISK_FRACTION, config/cost,
                     # dataset path, SHA-256 and the integrity validator
    "strategy",      # StrategyConfig and analyze() - the only signal source
    "costs",         # TradingCosts type
    "dataset",       # load_dataset - the ONLY data loader; never reimplemented
    "models",        # Signal and PaperTrade types
    "stats",         # performance and cost_breakdown - the ONLY statistics
                     # source; Phase 16F recomputes none of it
    "replay",       # Replay - the ONLY replay engine; Phase 17D adds no
                     # lifecycle, step or accounting logic of its own
    "modes",        # Mode identities and the mode -> policy mapping; holds
                     # configuration only, never trading state
    "execution",    # IntelligencePolicy - the Phase 17E seam. Phase 17G's
                     # registry names it explicitly when building the AI session's
                     # replay, because that replay must refuse every entry so the
                     # book stays AI's single owner
    "intelligence", # IntelligenceScore - the deterministic 0-100 qualification
                     # score. Phase 17G reads it to report; it never recomputes it
    "ai_paper",     # AiPaperBook - the SOLE owner of AI capital and position
                     # state. Phase 17G added it because AI permits several
                     # concurrent positions and PaperBroker holds exactly one;
                     # Standard's broker and baseline are untouched
}


def test_api_imports_only_permitted_engine_interfaces() -> None:
    """Separation with a deliberate, enumerated exception.

    The API may read the engine through the modules listed in
    ``ALLOWED_ENGINE_IMPORTS``. Anything else - private helpers, indicators,
    backtest internals - would couple the transport layer to engine internals.
    """

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent

    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level != 0 or not node.module:
                continue
            parts = node.module.split(".")
            if parts[0] != "crypto_paper_lab":
                continue
            if len(parts) == 1:
                # ``from crypto_paper_lab import stats`` binds the submodule
                # directly, so the allowlist check applies to each bound name.
                for alias in node.names:
                    assert alias.name in ALLOWED_ENGINE_IMPORTS, (
                        f"{path.name} imports crypto_paper_lab.{alias.name}"
                    )
                continue
            assert len(parts) > 1, f"{path.name}:{node.lineno}"
            assert parts[1] in ALLOWED_ENGINE_IMPORTS, (
                f"{path.name} imports {node.module!r}"
            )


def test_api_does_not_reach_into_engine_internals() -> None:
    """No relative/private engine import and no ``import *``."""

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent

    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                # A relative import inside paper_api is fine; anything else
                # would be reaching outside the package.
                assert path.parent == package, f"{path.name}:{node.lineno}"
            if isinstance(node, ast.ImportFrom):
                assert any(
                    alias.name != "*" for alias in node.names
                ), f"{path.name}:{node.lineno} uses import *"


def test_research_engine_does_not_import_the_api() -> None:
    """One-way dependency: nothing in the engine may reach for the API."""

    package = (
        pathlib.Path(__file__).resolve().parents[1] / "src/crypto_paper_lab"
    )

    for path in sorted(package.glob("*.py")):
        assert "paper_api" not in _imported_modules(path), path.name


def test_the_two_packages_are_separate_top_level_packages() -> None:
    """Guards the physical separation the architecture rules require."""

    import crypto_paper_lab
    import paper_api

    engine = pathlib.Path(crypto_paper_lab.__file__).parent
    api = pathlib.Path(paper_api.__file__).parent

    assert engine.name == "crypto_paper_lab"
    assert api.name == "paper_api"
    assert engine.parent == api.parent
    assert engine != api