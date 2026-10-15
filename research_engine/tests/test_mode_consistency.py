"""Phase 77: the six paper modes must be consistent, truthful and paper-only.

These assertions are structural wherever possible. The point of the audit is
not that the notes say the right words -- it is that the engine could not do
something the label forbids, even if a label were wrong.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crypto_paper_lab.modes import (
    AI_INTELLIGENCE,
    ALERTS,
    DAILY_TARGET,
    HIGH_RISK,
    MANUAL,
    MODES,
    STANDARD,
    mode_spec,
)

SRC = Path(__file__).resolve().parents[1] / "src"
ALL_SIX = (STANDARD, AI_INTELLIGENCE, ALERTS, DAILY_TARGET, MANUAL, HIGH_RISK)

#: Claims that would turn a simulation description into a promise about money.
#:
#: "guaranteed" is deliberately absent: the Daily Target note legitimately
#: contains the phrase "not a guaranteed return", and a substring match cannot
#: tell a disclaimer from a claim. Those phrases are asserted positively by
#: the dedicated tests below instead.
PROMISE_WORDS = (
    "risk-free",
    "riskless",
    "will profit",
    "assured return",
    "live trading",
    "real money",
    "verified ai",
)


def _spec(mode: str):
    return mode_spec(mode)


# 1. exactly six modes, all present
def test_there_are_exactly_six_modes():
    assert set(MODES) == set(ALL_SIX)


@pytest.mark.parametrize("mode", ALL_SIX)
def test_every_mode_has_a_label_a_note_and_an_identity(mode: str):
    spec = _spec(mode)
    assert spec.label.strip()
    assert spec.note.strip()
    identity = spec.identity()
    assert identity["mode"] == mode
    assert identity["label"] == spec.label


# 2. execution capability is declared, not implied
@pytest.mark.parametrize("mode", ALL_SIX)
def test_every_mode_declares_whether_it_can_execute(mode: str):
    assert isinstance(_spec(mode).supports_execution, bool)


def test_alerts_is_the_only_observation_only_mode():
    assert _spec(ALERTS).supports_execution is False
    others = [m for m in ALL_SIX if m != ALERTS]
    assert all(_spec(m).supports_execution for m in others)


def test_alerts_holds_no_policy_and_therefore_no_broker():
    """Execution is unrepresentable for Alerts, not merely switched off."""

    assert _spec(ALERTS).policy is None


def test_alerts_note_says_it_cannot_trade():
    note = _spec(ALERTS).note.lower()
    assert "cannot execute" in note or "notification-only" in note


# 3. labels are truthful about what the mode is
@pytest.mark.parametrize(
    "mode", (STANDARD, AI_INTELLIGENCE, DAILY_TARGET, MANUAL, HIGH_RISK)
)
def test_executing_modes_are_labelled_as_paper(mode: str):
    assert "paper" in _spec(mode).label.lower()


def test_ai_intelligence_is_labelled_as_running_no_model():
    label = _spec(AI_INTELLIGENCE).label.lower()
    assert "no model" in label
    assert "runs no ai model" in _spec(AI_INTELLIGENCE).note.lower()


def test_daily_target_is_labelled_as_a_target_not_a_return():
    note = _spec(DAILY_TARGET).note.lower()
    assert "not a guaranteed return" in note
    assert "overshoot" in note or "overshot" in note


def test_manual_states_it_is_a_simulation():
    assert "simulation only" in _spec(MANUAL).note.lower()


def test_high_risk_states_it_cannot_borrow_and_is_a_simulation():
    note = _spec(HIGH_RISK).note.lower()
    assert "simulation only" in note
    assert "no leverage" in note


# 4. no mode's label or note promises money or claims verified capability
@pytest.mark.parametrize("mode", ALL_SIX)
def test_no_mode_promises_a_return(mode: str):
    spec = _spec(mode)
    text = f"{spec.label} {spec.note}".lower()
    for word in PROMISE_WORDS:
        assert word not in text, f"{mode} mentions {word!r}"


# 5. no mode can reach a live venue
@pytest.mark.parametrize(
    "module",
    [
        "crypto_paper_lab/backtest.py",
        "crypto_paper_lab/simulator.py",
        "crypto_paper_lab/replay.py",
        "crypto_paper_lab/modes.py",
        "crypto_paper_lab/costs.py",
        "crypto_paper_lab/ai_paper.py",
        "paper_api/session.py",
    ],
)
def test_no_trading_or_session_module_imports_a_network_client(module: str):
    """Structural paper-only guarantee: no transport is even imported."""

    path = SRC / module
    tree = ast.parse(path.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {"requests", "httpx", "aiohttp", "urllib", "socket", "ccxt", "websockets"}
    offenders = imported & forbidden
    assert offenders == set(), f"{module} imports {offenders}"


def test_no_credential_value_is_hardcoded_anywhere():
    """The real property: no secret *value* is committed.

    Reading an environment variable by name is legitimate -- the data loader
    reads an optional public-data key that way -- so the check is for a string
    literal assigned to a credential-shaped name, not for the word appearing.
    """

    suspicious = ("api_key", "apikey", "api_secret", "secret", "passphrase", "token")
    offenders: list[str] = []

    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                name = target.id.lower()
                if not any(word in name for word in suspicious):
                    continue
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if len(value.value) >= 8:
                        offenders.append(f"{path.name}:{node.lineno} {target.id}")

    assert offenders == [], f"hardcoded credential values: {offenders}"


def test_no_live_trading_endpoint_is_configured():
    """No order-placing venue URL exists anywhere in the source."""

    banned = (
        "api.binance.com",
        "api.kraken.com",
        "api.coinbase.com",
        "fapi.binance.com",  # futures
        "/api/v3/order",
        "create_order",
        "create_order_request",
    )
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in banned:
            assert token not in text, f"{path.name} mentions {token}"


# 6. identity is stable and serialisable
@pytest.mark.parametrize("mode", ALL_SIX)
def test_mode_identity_is_deterministic(mode: str):
    assert _spec(mode).identity() == _spec(mode).identity()


@pytest.mark.parametrize("mode", ALL_SIX)
def test_identity_survives_json(mode: str):
    import json

    payload = _spec(mode).identity()
    assert json.loads(json.dumps(payload)) == payload


def test_high_risk_inherits_standard_policy_and_risk_note():
    """High-Risk must not invent its own signal qualification."""

    assert _spec(HIGH_RISK).policy is _spec(STANDARD).policy
    assert "standard" in _spec(HIGH_RISK).note.lower()