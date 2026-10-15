"""Phase 96: Standard and Manual must not share mutable state.

An earlier probe appeared to show that stepping Standard cleared a Manual
pending action. That was observed once and never confirmed, and the two probes
disagreed. These tests settle the question by construction: each one puts the
two modes in a known state and asserts the other's state is untouched, so the
answer is the same on every run rather than dependent on ordering.

Sessions are process-wide singletons, so every test begins by flattening the
books it touches. Without that, one test's open position decides another test's
result -- which is how the original ambiguity arose.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from paper_api.app import app

    return TestClient(app)


def _reset_both(c: TestClient) -> None:
    """Put both modes in a known state before every test.

    Sessions are process-wide singletons, so a shared ``TestClient`` carries
    state between tests. The engine refuses to reset while a position is open
    (deliberately: a reset-time close would be a trading operation), so an open
    Manual book is exited first and the replay stepped until the fill lands.
    """

    for _ in range(20):
        state = c.get("/api/manual").json()
        if state.get("pending_action") is None and state.get("open_position") is None:
            break
        if state.get("pending_action") is None and state.get("open_position"):
            c.post("/api/manual/action", json={"action": "EXIT"})
        c.post("/api/replay/step?mode=manual", json={"interval": 1})
    else:
        raise AssertionError("the manual book would not flatten")

    c.post("/api/replay/reset?mode=manual", json={})
    c.post("/api/replay/reset", json={})


def _manual_state(c: TestClient) -> dict:
    return c.get("/api/manual").json()


def _standard_state(c: TestClient) -> dict:
    return c.get("/api/replay").json()


# 1. a Manual order is Manual's own
def test_a_manual_order_is_pending_until_manual_steps(client: TestClient) -> None:
    _reset_both(client)
    response = client.post(
        "/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05}
    )
    assert response.status_code == 200
    assert _manual_state(client)["pending_action"]["action"] == "ENTER_LONG"
    assert _manual_state(client)["open_position"] is None


def test_stepping_manual_fills_the_pending_action(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    client.post("/api/replay/step?mode=manual", json={"interval": 1})
    state = _manual_state(client)
    assert state["pending_action"] is None
    assert state["open_position"] is not None


# 2. Standard's steps must not touch Manual
def test_stepping_standard_leaves_a_manual_pending_action_untouched(
    client: TestClient,
) -> None:
    """The question the earlier probe left open, asked deterministically.

    Each session owns its own ``_pending`` and its own locks, so a Standard
    step has no path to it. Asserted explicitly because an earlier,
    order-dependent observation suggested the opposite.
    """

    _reset_both(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    assert _manual_state(client)["pending_action"] is not None

    for _ in range(5):
        client.post("/api/replay/step", json={"interval": 1})  # Standard

    state = _manual_state(client)
    assert state["pending_action"] is not None, "a Standard step consumed it"
    assert state["open_position"] is None, "a Standard step filled it"


# 3. Manual's steps must not touch Standard
def test_stepping_manual_leaves_the_standard_cursor_alone(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/replay/reset", json={})
    before = _standard_state(client)["cursor"]

    for _ in range(5):
        client.post("/api/replay/step?mode=manual", json={"interval": 1})

    assert _standard_state(client)["cursor"] == before


def test_manual_steps_do_not_change_the_standard_book(client: TestClient) -> None:
    """The property is "unchanged", not "flat".

    Standard may legitimately hold a position of its own; asserting it is flat
    would be asserting something about Standard's strategy rather than about
    isolation. What must hold is that Manual activity leaves it exactly as it
    was.
    """

    _reset_both(client)
    for _ in range(4):
        client.post("/api/replay/step", json={"interval": 1})
    before = _standard_state(client)

    for _ in range(6):
        client.post("/api/replay/step?mode=manual", json={"interval": 1})

    after = _standard_state(client)
    assert after["cursor"] == before["cursor"]
    assert after["has_open_position"] == before["has_open_position"]
    assert after["trade_count"] == before["trade_count"]


# 4. position and history isolation
def test_each_mode_keeps_its_own_position(client: TestClient) -> None:
    _reset_both(client)
    standard_before = _standard_state(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    client.post("/api/replay/step?mode=manual", json={"interval": 1})

    assert _manual_state(client)["open_position"] is not None
    # Standard's book is untouched by a Manual entry, open or closed.
    assert _standard_state(client)["trade_count"] == standard_before["trade_count"]
    assert (
        _standard_state(client)["has_open_position"]
        == standard_before["has_open_position"]
    )


def test_standard_position_is_reported_only_for_standard(client: TestClient) -> None:
    """The Phase 93 defect guard, restated as an isolation property."""

    _reset_both(client)
    assert client.get("/api/position?mode=manual").status_code == 409
    assert client.get("/api/position").status_code == 200


# 5. reset is per-mode
def test_resetting_manual_does_not_rewind_standard(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/replay/step", json={"interval": 1})
    client.post("/api/replay/step", json={"interval": 1})
    standard_cursor = _standard_state(client)["cursor"]

    client.post("/api/replay/reset?mode=manual", json={})

    assert _standard_state(client)["cursor"] == standard_cursor


def test_resetting_standard_does_not_clear_a_manual_order(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    client.post("/api/replay/reset", json={})
    assert _manual_state(client)["pending_action"] is not None


# 6. repeated and interleaved steps
def test_interleaved_steps_advance_only_the_requested_mode(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/replay/reset", json={})
    client.post("/api/replay/reset?mode=manual", json={})

    client.post("/api/replay/step", json={"interval": 1})
    client.post("/api/replay/step?mode=manual", json={"interval": 1})
    client.post("/api/replay/step", json={"interval": 1})

    standard = _standard_state(client)
    manual = _standard_state_manual(client)
    assert standard["cursor"] > 0
    assert manual["cursor"] > 0


def _standard_state_manual(client: TestClient) -> dict:
    return client.get("/api/replay?mode=manual").json()


def test_repeated_manual_steps_do_not_double_fill(client: TestClient) -> None:
    _reset_both(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    for _ in range(4):
        client.post("/api/replay/step?mode=manual", json={"interval": 1})

    journal = _manual_state(client)["journal"]
    # One entry intent must produce at most one open position, and no
    # additional open entries from repeated stepping.
    assert len(journal) == 0
    assert _manual_state(client)["pending_action"] is None


def test_a_manual_position_holds_its_entry_price_across_many_steps(
    client: TestClient,
) -> None:
    _reset_both(client)
    client.post("/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.05})
    client.post("/api/replay/step?mode=manual", json={"interval": 1})
    entry = _manual_state(client)["open_position"]["entry_price"]
    for _ in range(5):
        client.post("/api/replay/step?mode=manual", json={"interval": 1})
    assert _manual_state(client)["open_position"]["entry_price"] == entry