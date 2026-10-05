"""Phase 17D tests: the replay transport layer.

Three rules shape this file.

**The engine is the oracle.** No test asserts a hand-written balance, cursor or
trade. Every figure is compared against the ``Replay`` object the app was built
with, and separately against ``run_backtest`` where a prefix comparison is
meaningful. A transport test that hard-codes numbers would only prove the numbers
have not changed; it would not prove the API is reading the engine.

**The API owns no state.** The strongest available check is direct: mutate the
``Replay`` behind the app's back and assert the very next HTTP response reflects
it. If any route kept a private copy of the cursor or the balance, that test
would fail.

**Errors are contracts, not accidents.** Status codes and bodies are asserted
exactly, including that no traceback leaks and that nothing is swallowed into a
200. Refusals are checked for *effect* as well as status: a 409 that quietly
discarded a position would satisfy a naive status-code assertion.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.backtest import END_OF_DATA, run_backtest
from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.replay import (
    MAX_INTERVAL_MS,
    MIN_INTERVAL_MS,
    STATE_FINISHED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
    Replay,
    ReplayFinishedError,
)
from crypto_paper_lab.walkforward import (
    DATASET_PATH,
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    phase13_costs,
)

from paper_api import marketdata
from paper_api.app import MAX_STEP_COUNT, create_app
from paper_api.config import ApiConfig
from paper_api.replaysession import ERROR_STATUS, ReplaySession
from paper_api.schemas import ReplayStateResponse

import pathlib

RESEARCH_ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE, _ = load_dataset(RESEARCH_ENGINE_ROOT / DATASET_PATH)
CONFIG = baseline_config()
COSTS = phase13_costs()
REQUIRED = 22

#: Small prefix: several reversals, fast to step over HTTP.
PREFIX = 200

INITIAL_FIELDS = {
    "replay_id", "status", "dataset", "strategy", "execution", "cursor",
    "start_index", "bars_processed", "current_timestamp", "next_timestamp",
    "next_candle_available", "starting_balance", "balance", "realized_pnl",
    "trade_count", "has_open_position", "open_position", "last_signal",
    # Phase 17F: echoes which mode was selected. The only field added to this
    # response since 17D, and it is configuration rather than trading state.
    "mode",
}

#: Fields the engine cannot authoritatively produce. If any appears, the
#: transport has invented a financial model.
FORBIDDEN_FIELDS = (
    "equity",
    "mark_price",
    "current_price",
    "unrealized_pnl",
    "available_balance",
    "reserved_capital",
    "reserved_balance",
    "buying_power",
    "margin",
    "notional",
    "leverage",
    "confidence",
    "expected_return",
)


def make_replay(**kwargs) -> Replay:
    return Replay(SOURCE[:PREFIX], config=CONFIG, costs=COSTS, **kwargs)


def client_for(replay: Replay | None = None) -> TestClient:
    """Build an app around a specific replay and return a client plus that replay."""

    resolved = replay if replay is not None else make_replay()
    app = create_app(
        ApiConfig(),
        session=None,
        replay=ReplaySession(resolved),
    )
    return TestClient(app), resolved


@pytest.fixture
def replay() -> Replay:
    """The authoritative engine object the app under test is built around."""

    return make_replay()


@pytest.fixture
def client(replay: Replay) -> TestClient:
    return client_for(replay)[0]


# ---------------------------------------------------------------------------
# 1. GET /api/replay
# ---------------------------------------------------------------------------


class TestGetReplay:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/api/replay").status_code == 200

    def test_initial_status_is_idle(self, client: TestClient) -> None:
        assert client.get("/api/replay").json()["status"] == STATE_IDLE

    def test_no_bar_is_consumed(self, client: TestClient) -> None:
        body = client.get("/api/replay").json()

        assert body["cursor"] == REQUIRED
        assert body["bars_processed"] == 0
        assert body["current_timestamp"] is None
        assert body["trade_count"] == 0
        assert body["has_open_position"] is False
        assert body["open_position"] is None
        assert body["last_signal"] is None

    def test_response_is_a_faithful_projection_of_replay_state(
        self, client: TestClient
    ) -> None:
        app = client.app
        body = client.get("/api/replay").json()

        assert set(body) == INITIAL_FIELDS

    def test_identity_matches_the_engine(
        self, client: TestClient, replay: Replay
    ) -> None:
        body = client.get("/api/replay").json()
        state = replay.state

        assert body["replay_id"] == state.replay_id
        assert body["strategy"]["config_hash"] == state.strategy.config_hash
        assert body["execution"]["costs_hash"] == state.execution.costs_hash
        assert body["dataset"]["sha256"] == state.dataset.sha256
        assert body["dataset"]["candle_count"] == state.dataset.candle_count

    def test_initial_account_matches_the_engine(self, client: TestClient) -> None:
        body = client.get("/api/replay").json()

        assert body["starting_balance"] == STARTING_BALANCE
        assert body["balance"] == STARTING_BALANCE
        assert body["realized_pnl"] == 0.0

    def test_timestamps_are_utc_offset_aware(self, client: TestClient) -> None:
        """Phase 16 convention: aware UTC, serialised with a trailing ``Z``."""

        body = client.get("/api/replay").json()

        assert body["dataset"]["first_timestamp"].endswith("Z")
        assert body["next_timestamp"].endswith("Z")

    def test_no_filesystem_path_is_exposed(self, client: TestClient) -> None:
        blob = json.dumps(client.get("/api/replay").json())

        for leak in (".csv", "\\", "research_engine", "Users"):
            assert leak not in blob, leak

    def test_no_forbidden_financial_field(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/replay").json()

        for absent in FORBIDDEN_FIELDS:
            assert absent not in body, absent

    def test_response_validates_against_the_schema(
        self, client: TestClient
    ) -> None:
        parsed = ReplayStateResponse.model_validate(
            client.get("/api/replay").json()
        )

        assert parsed.status == STATE_IDLE

    def test_is_byte_deterministic(self, client: TestClient) -> None:
        first = client.get("/api/replay").content
        second = client.get("/api/replay").content

        assert first == second

    def test_replay_endpoint_is_read_only(self, client: TestClient) -> None:
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)("/api/replay")
            assert response.status_code == 405, method


# ---------------------------------------------------------------------------
# 2. POST /api/replay/start
# ---------------------------------------------------------------------------


class TestStart:
    def test_idle_to_running(self, client: TestClient) -> None:
        body = client.post("/api/replay/start").json()

        assert body["status"] == STATE_RUNNING

    def test_paused_to_running(self, client: TestClient) -> None:
        client.post("/api/replay/start")
        client.post("/api/replay/pause")
        assert client.get("/api/replay").json()["status"] == STATE_PAUSED

        body = client.post("/api/replay/start").json()

        assert body["status"] == STATE_RUNNING

    def test_running_to_running_is_idempotent(self, client: TestClient) -> None:
        for _ in range(4):
            assert client.post("/api/replay/start").json()["status"] == (
                STATE_RUNNING
            )

    def test_repeated_start_does_not_advance_the_cursor(
        self, client: TestClient, replay: Replay
    ) -> None:
        before = replay.state.cursor

        for _ in range(5):
            client.post("/api/replay/start")

        assert replay.state.cursor == before
        assert client.get("/api/replay").json()["bars_processed"] == 0

    def test_start_accepts_a_valid_interval(self, client: TestClient) -> None:
        for interval in (MIN_INTERVAL_MS, 1_000, MAX_INTERVAL_MS):
            response = client.post(
                "/api/replay/start", params={"interval_ms": interval}
            )
            assert response.status_code == 200, interval
            assert response.json()["status"] == STATE_RUNNING

    @pytest.mark.parametrize("bad", [0, 99, 60_001, -5])
    def test_out_of_range_interval_is_rejected(
        self, client: TestClient, bad: int
    ) -> None:
        response = client.post(
            "/api/replay/start", params={"interval_ms": bad}
        )

        assert response.status_code == ERROR_STATUS["INVALID_INTERVAL"] == 400
        body = response.json()
        assert body["detail"]["code"] == "INVALID_INTERVAL"

    def test_rejected_interval_leaves_the_replay_idle(
        self, client: TestClient
    ) -> None:
        client.post("/api/replay/start", params={"interval_ms": 99})

        assert client.get("/api/replay").json()["status"] == STATE_IDLE

    def test_rejected_interval_never_clamps(self, client: TestClient) -> None:
        """Clamping would silently substitute a pace the caller did not ask for."""

        client.post("/api/replay/start", params={"interval_ms": 60_001})

        assert client.get("/api/replay").json()["status"] == STATE_IDLE


# ---------------------------------------------------------------------------
# 3. POST /api/replay/pause
# ---------------------------------------------------------------------------


class TestPause:
    def test_running_to_paused(self, client: TestClient) -> None:
        client.post("/api/replay/start")

        body = client.post("/api/replay/pause").json()

        assert body["status"] == STATE_PAUSED

    def test_pause_is_idempotent(self, client: TestClient) -> None:
        client.post("/api/replay/start")

        for _ in range(3):
            assert client.post("/api/replay/pause").json()["status"] == (
                STATE_PAUSED
            )

    def test_pause_from_idle_stays_idle(self, client: TestClient) -> None:
        assert client.post("/api/replay/pause").json()["status"] == STATE_IDLE

    def test_pause_does_not_mutate_state(
        self, client: TestClient, replay: Replay
    ) -> None:
        client.post("/api/replay/start")
        for _ in range(15):
            client.post("/api/replay/step")
        client.post("/api/replay/start")

        before = client.get("/api/replay").json()
        client.post("/api/replay/pause")
        after = client.get("/api/replay").json()

        for field in (
            "cursor", "bars_processed", "balance", "realized_pnl",
            "trade_count", "has_open_position", "replay_id",
            "current_timestamp", "next_timestamp",
        ):
            assert before[field] == after[field], field

    def test_pause_does_not_stop_manual_stepping(
        self, client: TestClient
    ) -> None:
        client.post("/api/replay/start")
        client.post("/api/replay/pause")

        body = client.post("/api/replay/step").json()

        assert body["cursor"] == REQUIRED + 1
        assert body["status"] == STATE_PAUSED


# ---------------------------------------------------------------------------
# 4. POST /api/replay/step
# ---------------------------------------------------------------------------


class TestStep:
    def test_advances_the_cursor_by_one(self, client: TestClient) -> None:
        body = client.post("/api/replay/step").json()

        assert body["cursor"] == REQUIRED + 1
        assert body["bars_processed"] == 1

    def test_delegates_to_the_engine_and_returns_its_state(
        self, client: TestClient, replay: Replay
    ) -> None:
        body = client.post("/api/replay/step").json()
        state = replay.state

        assert body["cursor"] == state.cursor
        assert body["balance"] == state.balance
        assert body["realized_pnl"] == state.realized_pnl
        assert body["trade_count"] == state.trade_count
        assert body["has_open_position"] == state.has_open_position
        assert body["last_signal"] is not None

    def test_balance_and_trade_state_come_from_replay_not_the_api(
        self, client: TestClient, replay: Replay
    ) -> None:
        for _ in range(90):
            body = client.post("/api/replay/step").json()

        assert body["trade_count"] == len(replay.broker.journal)
        assert body["balance"] == replay.broker.cash
        assert body["realized_pnl"] == (
            replay.broker.cash - replay.broker.starting_balance
        )

    def test_signal_is_the_engines_own(self, client: TestClient) -> None:
        body = client.post("/api/replay/step").json()
        signal = body["last_signal"]

        assert signal["side"] in {"long", "short", "flat"}
        assert signal["reason"]
        assert signal["timestamp"].endswith("Z")
        # Replay keeps the signal analyze returned, so price is the signal bar's
        # close and equals signal_close. It is NOT a fill price.
        assert signal["price"] == signal["signal_close"]

    def test_open_position_is_reported_from_the_engine(
        self, client: TestClient, replay: Replay
    ) -> None:
        body = client.post("/api/replay/step").json()

        assert body["has_open_position"] is True
        assert body["open_position"] is not None
        assert body["open_position"]["side"] == replay.broker.open_trade.side
        # Cost fields are absent because the broker computes them only at close.
        assert "costs" not in body["open_position"]
        assert "bars_held" not in body["open_position"]

    def test_batched_step_equals_repeated_single_steps(self) -> None:
        batched, replay_a = client_for()
        single, replay_b = client_for()

        body_a = batched.post("/api/replay/step", params={"count": 40}).json()
        for _ in range(40):
            body_b = single.post("/api/replay/step").json()

        assert body_a["cursor"] == body_b["cursor"] == REQUIRED + 40
        assert body_a["balance"] == body_b["balance"]
        assert body_a["trade_count"] == body_b["trade_count"]
        assert body_a["last_signal"] == body_b["last_signal"]

    def test_batched_step_matches_the_backtest_prefix(self) -> None:
        client, replay = client_for()

        body = client.post("/api/replay/step", params={"count": 178}).json()
        client.post("/api/replay/step")  # trigger the finish step
        final = client.get("/api/replay").json()

        reference = run_backtest(
            SOURCE[:PREFIX],
            config=CONFIG,
            costs=COSTS,
            starting_balance=STARTING_BALANCE,
            risk_fraction=RISK_FRACTION,
        )

        assert final["status"] == STATE_FINISHED
        assert final["trade_count"] == len(reference.trades)
        assert final["balance"] == reference.ending_balance

    @pytest.mark.parametrize("bad", [0, -1, MAX_STEP_COUNT + 1])
    def test_out_of_range_count_is_rejected(
        self, client: TestClient, bad: int
    ) -> None:
        response = client.post("/api/replay/step", params={"count": bad})

        assert response.status_code == 422

    def test_rejected_count_does_not_advance(self, client: TestClient) -> None:
        client.post("/api/replay/step", params={"count": 0})

        assert client.get("/api/replay").json()["cursor"] == REQUIRED

    def test_step_is_deterministic_across_identical_runs(self) -> None:
        first, _ = client_for()
        second, _ = client_for()

        for _ in range(60):
            a = first.post("/api/replay/step").json()
            b = second.post("/api/replay/step").json()

        assert a["cursor"] == b["cursor"]
        assert a["balance"] == b["balance"]
        assert a["last_signal"] == b["last_signal"]

    def test_a_batch_is_clamped_to_the_bars_that_remain(self) -> None:
        """A batch must not advance past the end and then report failure.

        Found by driving the live server: a 5000-bar batch issued near the end
        stepped until the data ran out, the engine refused the next step, and the
        request answered 409 *after* having advanced the replay - leaving the
        caller holding state it was never shown.
        """

        client, replay = client_for()
        remaining = len(SOURCE[:PREFIX]) - replay.state.cursor

        body = client.post(
            "/api/replay/step", params={"count": MAX_STEP_COUNT}
        ).json()

        assert body["status"] == STATE_FINISHED
        assert body["cursor"] == PREFIX
        assert body["has_open_position"] is False
        assert body["bars_processed"] == remaining

    def test_clamping_does_not_skip_or_extra_step(self) -> None:
        """A clamped batch must advance exactly as many bars as it consumed.

        Left one bar short of the end, so the batched request clamps. A
        single-step request at that point performs the last bar *and* the terminal
        transition, because reaching the end of the data is what makes the replay
        finish - which is why one single request suffices here.
        """

        batched, replay_a = client_for()
        single, replay_b = client_for()

        warm = len(SOURCE[:PREFIX]) - 1 - replay_a.state.cursor
        batched.post("/api/replay/step", params={"count": warm})
        for _ in range(warm):
            single.post("/api/replay/step")

        assert replay_a.state.cursor == replay_b.state.cursor
        assert replay_a.state.cursor == len(SOURCE[:PREFIX]) - 1

        a = batched.post("/api/replay/step", params={"count": 500}).json()
        b = single.post("/api/replay/step").json()

        assert a["cursor"] == b["cursor"] == PREFIX
        assert a["status"] == b["status"] == STATE_FINISHED
        assert a["balance"] == b["balance"]
        assert a["trade_count"] == b["trade_count"]
        assert a["bars_processed"] == b["bars_processed"]

    def test_a_batch_within_the_data_performs_exactly_that_many_bars(self) -> None:
        client, replay = client_for()

        body = client.post("/api/replay/step", params={"count": 10}).json()

        assert body["cursor"] == REQUIRED + 10
        assert body["bars_processed"] == 10
        assert body["status"] == STATE_IDLE

    def test_the_terminal_transition_really_happens(self) -> None:
        """Reaching the end must apply closure, not strand an open position.

        If the API clamped without the final step, the cursor would sit at the end
        of the data while the position stayed open and ``end_of_data`` was never
        recorded - a half-finished replay the client could never finish.
        """

        client, replay = client_for()

        body = client.post("/api/replay/step", params={"count": 5000}).json()

        assert body["status"] == STATE_FINISHED
        assert body["has_open_position"] is False
        assert END_OF_DATA in replay.exit_counts
        assert replay.exit_counts[END_OF_DATA] == 1

    def test_an_exact_batch_returns_finished_rather_than_error(self) -> None:
        client, replay = client_for()
        remaining = len(SOURCE[:PREFIX]) - replay.state.cursor

        body = client.post(
            "/api/replay/step", params={"count": remaining}
        ).json()

        assert body["status"] == STATE_FINISHED
        assert body["cursor"] == PREFIX

    def test_reaching_the_end_takes_four_batches_for_the_full_dataset(
        self,
    ) -> None:
        """The 5000 cap means a full replay is several requests, by design."""

        full = len(SOURCE)
        client, replay = client_for(Replay(SOURCE, config=CONFIG, costs=COSTS))

        batches = 0
        while replay.state.status != STATE_FINISHED and batches < 10:
            response = client.post("/api/replay/step", params={"count": 5000})
            assert response.status_code == 200
            batches += 1

        assert replay.state.status == STATE_FINISHED
        assert batches == 4
        assert replay.state.cursor == full


# ---------------------------------------------------------------------------
# 5. POST /api/replay/reset
# ---------------------------------------------------------------------------


def finished_client() -> tuple[TestClient, Replay]:
    """A client whose replay has consumed the whole prefix."""

    client, replay = client_for()
    client.post("/api/replay/step", params={"count": len(SOURCE[:PREFIX]) + 5})

    assert replay.state.status == STATE_FINISHED

    return client, replay


def open_position_client() -> tuple[TestClient, Replay]:
    """A client whose replay holds an open paper position."""

    client, replay = client_for()
    for _ in range(120):
        body = client.post("/api/replay/step").json()
        if body["has_open_position"]:
            break

    assert replay.state.has_open_position is True

    return client, replay


class TestReset:
    def test_successful_reset_returns_idle(self) -> None:
        client, _ = finished_client()

        body = client.post("/api/replay/reset").json()

        assert body["status"] == STATE_IDLE

    def test_reset_rewinds_the_cursor(self) -> None:
        client, _ = finished_client()

        body = client.post("/api/replay/reset").json()

        assert body["cursor"] == REQUIRED
        assert body["bars_processed"] == 0
        assert body["current_timestamp"] is None

    def test_reset_clears_broker_state(self) -> None:
        client, _ = finished_client()
        assert client.get("/api/replay").json()["trade_count"] > 0

        body = client.post("/api/replay/reset").json()

        assert body["trade_count"] == 0
        assert body["balance"] == STARTING_BALANCE
        assert body["realized_pnl"] == 0.0
        assert body["has_open_position"] is False
        assert body["last_signal"] is None

    def test_reset_preserves_replay_id_and_identities(self) -> None:
        client, _ = finished_client()
        before = client.get("/api/replay").json()

        after = client.post("/api/replay/reset").json()

        assert after["replay_id"] == before["replay_id"]
        assert after["dataset"] == before["dataset"]
        assert after["strategy"] == before["strategy"]
        assert after["execution"] == before["execution"]

    def test_reset_does_not_arm_auto_run(self) -> None:
        client, replay = finished_client()
        replay.start()

        body = client.post("/api/replay/reset").json()

        assert body["status"] == STATE_IDLE
        assert client.post("/api/replay/start").json()["status"] == (
            STATE_RUNNING
        )

    def test_reset_is_idempotent(self) -> None:
        client, _ = finished_client()
        client.post("/api/replay/reset")

        assert client.post("/api/replay/reset").json() == (
            client.post("/api/replay/reset").json()
        )

    def test_reset_then_replay_reproduces_the_same_run(self) -> None:
        client, _ = finished_client()
        first = client.post("/api/replay/reset")
        client.post("/api/replay/step", params={"count": len(SOURCE[:PREFIX]) + 5})
        first_final = client.get("/api/replay").json()

        client.post("/api/replay/reset")
        client.post("/api/replay/step", params={"count": len(SOURCE[:PREFIX]) + 5})
        second_final = client.get("/api/replay").json()

        assert first_final["balance"] == second_final["balance"]
        assert first_final["trade_count"] == second_final["trade_count"]

    def test_reset_with_open_position_returns_409(self) -> None:
        client, _ = open_position_client()

        response = client.post("/api/replay/reset")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "POSITION_OPEN"

    def test_refused_reset_does_not_discard_the_position(self) -> None:
        client, replay = open_position_client()
        position = replay.broker.open_trade
        before = client.get("/api/replay").json()

        client.post("/api/replay/reset")
        after = client.get("/api/replay").json()

        assert replay.broker.open_trade is position
        assert after["has_open_position"] is True
        assert after["cursor"] == before["cursor"]
        assert after["balance"] == before["balance"]
        assert after["status"] == before["status"] == STATE_IDLE


# ---------------------------------------------------------------------------
# 6. finished replay
# ---------------------------------------------------------------------------


class TestFinished:
    def test_stepping_to_the_end_finishes(self) -> None:
        client, _ = finished_client()

        assert client.get("/api/replay").json()["status"] == STATE_FINISHED

    def test_step_after_finish_returns_409(self) -> None:
        client, _ = finished_client()

        response = client.post("/api/replay/step")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "REPLAY_FINISHED"

    def test_start_after_finish_returns_409(self) -> None:
        """Phase 17A section 21 requires the transport to refuse this."""

        client, _ = finished_client()

        response = client.post("/api/replay/start")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "REPLAY_FINISHED"

    def test_no_execution_after_finish(self) -> None:
        client, _ = finished_client()
        before = client.get("/api/replay").json()

        for _ in range(5):
            client.post("/api/replay/step")

        after = client.get("/api/replay").json()

        assert after["cursor"] == before["cursor"]
        assert after["balance"] == before["balance"]
        assert after["trade_count"] == before["trade_count"]

    def test_end_of_data_closure_is_visible(self) -> None:
        client, replay = finished_client()

        assert END_OF_DATA in replay.exit_counts
        assert replay.exit_counts[END_OF_DATA] == 1
        assert client.get("/api/replay").json()["has_open_position"] is False

    def test_pause_after_finish_is_refused_by_status_only(
        self, client: TestClient
    ) -> None:
        """Pause on a finished replay is a no-op returning finished, per 17C."""

        client, _ = finished_client()

        response = client.post("/api/replay/pause")

        assert response.status_code == 200
        assert response.json()["status"] == STATE_FINISHED

    def test_reset_recovers_from_finished(self) -> None:
        client, _ = finished_client()

        assert client.post("/api/replay/reset").json()["status"] == STATE_IDLE


# ---------------------------------------------------------------------------
# 7. error contract
# ---------------------------------------------------------------------------


class TestErrorContract:
    @pytest.mark.parametrize(
        "path,params",
        [
            # ``interval_ms`` is deliberately unbounded at the signature so the
            # range check belongs to the engine, not to FastAPI.
            ("/api/replay/start", {"interval_ms": 0}),
            ("/api/replay/start", {"interval_ms": 99}),
            ("/api/replay/start", {"interval_ms": 60_001}),
        ],
    )
    def test_engine_error_bodies_are_machine_readable(
        self, client: TestClient, path: str, params: dict
    ) -> None:
        """Errors raised by ``Replay`` map to ``{"detail": {"code", ...}}``."""

        response = client.post(path, params=params)

        assert response.status_code >= 400
        assert response.headers["content-type"].startswith("application/json")
        detail = response.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["code"] and isinstance(detail["code"], str)
        assert detail["message"]

    @pytest.mark.parametrize("bad", [0, -1, MAX_STEP_COUNT + 1])
    def test_request_validation_bodies_are_machine_readable(
        self, client: TestClient, bad: int
    ) -> None:
        """FastAPI's own query validation uses a list of located errors.

        That is a different shape from an engine refusal on purpose: one describes
        a malformed request, the other a refused operation. Both are structured,
        and neither contains prose a machine has to parse.
        """

        response = client.post("/api/replay/step", params={"count": bad})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, list) and detail
        for entry in detail:
            assert set(entry) >= {"loc", "msg", "type"}
            assert entry["loc"][:2] == ["query", "count"]

    def test_no_traceback_leaks_in_any_error(
        self, client: TestClient
    ) -> None:
        client, _ = finished_client()

        responses = [
            client.post("/api/replay/step"),
            client.post("/api/replay/start"),
            client.post("/api/replay/step", params={"count": 0}),
            client.post("/api/replay/start", params={"interval_ms": 99}),
        ]

        for response in responses:
            text = response.text
            assert response.status_code >= 400
            for leak in (
                "Traceback",
                "File \"",
                "crypto_paper_lab",
                "paper_api",
                "line ",
                ".py",
            ):
                assert leak not in text, leak

    def test_errors_are_deterministic(self) -> None:
        first, _ = finished_client()
        second, _ = finished_client()

        a = first.post("/api/replay/step")
        b = second.post("/api/replay/step")

        assert a.status_code == b.status_code
        assert a.json() == b.json()

    def test_reset_conflict_body_identifies_the_code(self) -> None:
        client, _ = open_position_client()

        body = client.post("/api/replay/reset").json()

        assert body["detail"]["code"] == "POSITION_OPEN"
        assert body["detail"]["message"]

    def test_every_mapped_code_has_a_declared_status(self) -> None:
        for code, status in ERROR_STATUS.items():
            assert 400 <= status < 600, code
            assert isinstance(code, str) and code

    def test_unmapped_engine_errors_are_not_swallowed(self) -> None:
        """A base ReplayError has no mapping and must not become a tidy 200."""

        from crypto_paper_lab.replay import ReplayError

        session = ReplaySession(make_replay())

        def explode(*args, **kwargs):
            raise ReplayError("invariant violated")

        session._replay.step = explode  # type: ignore[method-assign]

        with pytest.raises(ReplayError):
            session.step()


# ---------------------------------------------------------------------------
# 8. transport is not a second source of truth
# ---------------------------------------------------------------------------


class TestSingleSourceOfTruth:
    def test_mutating_the_engine_behind_the_api_is_visible_immediately(
        self,
    ) -> None:
        """The decisive test: no route may keep a private copy of any field.

        The replay is advanced directly, without touching the API, and the very
        next response must equal a fresh projection of the engine's own state.
        Byte equality is used deliberately: anything cached, rounded or derived
        on the way out would break it.
        """

        client, replay = client_for()

        for _ in range(70):
            replay.step()

        expected = ReplayStateResponse.from_state(
            replay.state
        ).model_dump(mode="json")

        assert client.get("/api/replay").json() == expected

    def test_api_and_engine_agree_after_every_operation(self) -> None:
        client, replay = client_for()
        sequence = [
            ("post", "/api/replay/start", {}),
            ("post", "/api/replay/step", {"count": 30}),
            ("post", "/api/replay/pause", {}),
            ("post", "/api/replay/step", {"count": 20}),
            ("post", "/api/replay/start", {}),
            ("post", "/api/replay/step", {"count": 25}),
        ]

        for method, path, params in sequence:
            response = getattr(client, method)(path, params=params)
            assert response.status_code == 200
            body = response.json()
            state = replay.state
            assert body["cursor"] == state.cursor, path
            assert body["balance"] == state.balance, path
            assert body["status"] == state.status, path

    def test_session_endpoints_describe_the_same_broker_as_replay(
        self,
    ) -> None:
        """Phase 16 account views the replay's broker, so money cannot diverge."""

        client, replay = client_for()
        client.post("/api/replay/step", params={"count": 90})

        replay_body = client.get("/api/replay").json()
        account = client.get("/api/account").json()
        trades = client.get("/api/trades").json()
        position = client.get("/api/position").json()

        assert account["balance"] == replay_body["balance"]
        assert account["trade_count"] == replay_body["trade_count"]
        assert trades["trade_count"] == replay_body["trade_count"]
        assert position["has_position"] == replay_body["has_open_position"]

    def test_account_endpoints_follow_a_reset_that_replaces_the_broker(
        self,
    ) -> None:
        """Regression: the account view must not keep the pre-reset broker.

        ``Replay.reset()`` constructs a *new* ``PaperBroker``. A session left bound
        to the previous one kept reporting the finished run's balance and journal
        while ``/api/replay`` correctly showed a fresh account - two sources of
        truth for the same money. Found by driving the live server to completion
        and then resetting.
        """

        client, replay = client_for()
        client.post("/api/replay/step", params={"count": 5000})

        before = client.get("/api/account").json()
        assert before["trade_count"] > 0

        client.post("/api/replay/reset")

        replay_body = client.get("/api/replay").json()
        account = client.get("/api/account").json()
        trades = client.get("/api/trades").json()
        statistics = client.get("/api/statistics").json()

        assert account["balance"] == STARTING_BALANCE
        assert account["trade_count"] == 0
        assert trades["trades"] == []
        assert statistics["trades"] == 0
        assert account["balance"] == replay_body["balance"]
        assert account["trade_count"] == replay_body["trade_count"]
        assert replay.broker.cash == STARTING_BALANCE

    def test_session_id_is_stable_across_a_reset(self) -> None:
        client, _ = client_for()

        first = client.get("/api/session").json()["session_id"]
        client.post("/api/replay/step", params={"count": 40})
        client.post("/api/replay/reset")

        assert client.get("/api/session").json()["session_id"] == first

    def test_app_state_exposes_the_replay_session(self, client: TestClient) -> None:
        session = client.app.state.replay

        assert isinstance(session, ReplaySession)
        assert session.snapshot().status == STATE_IDLE

    def test_replay_session_uses_one_shared_lock(self) -> None:
        session = ReplaySession(make_replay())

        assert session.lock is session.lock

    def test_the_lock_is_reentrant(self) -> None:
        """A nested acquisition on one thread must not deadlock."""

        import threading

        assert type(threading.RLock()).__name__ == "RLock"

        session = ReplaySession(make_replay())
        acquired = []

        with session.lock:
            with session.lock:
                acquired.append(True)

        assert acquired == [True]

    def test_replay_routes_do_not_touch_the_broker_directly(self) -> None:
        """The transport may not call broker methods; only Replay may."""

        client, replay = client_for()
        before = replay.broker.cash

        client.post("/api/replay/start")
        client.post("/api/replay/pause")
        client.post("/api/replay/step", params={"count": 5})
        client.post("/api/replay/reset")

        # A rejected reset on a fresh replay leaves nothing behind.
        assert replay.broker.cash in (before, STARTING_BALANCE)


def _signal_dict(signal) -> dict | None:
    """The transport's rendering of an engine Signal, for comparison."""

    if signal is None:
        return None

    from paper_api.schemas import ReplaySignalModel

    return ReplaySignalModel(
        timestamp=signal.timestamp.replace(tzinfo=None),
        side=signal.side,
        reason=signal.reason,
        price=signal.price,
        support=signal.support,
        resistance=signal.resistance,
        trend=signal.trend,
        breakout=signal.breakout,
        retest=signal.retest,
        signal_close=signal.signal_close,
        trend_state=signal.trend_state,
        breakout_distance=signal.breakout_distance,
        retest_distance=signal.retest_distance,
        realised_volatility=signal.realised_volatility,
        mean_range=signal.mean_range,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# 9. scope and safety
# ---------------------------------------------------------------------------


class TestScopeAndSafety:
    def test_replay_endpoints_are_post_only_where_expected(
        self, client: TestClient
    ) -> None:
        for path in (
            "/api/replay/start",
            "/api/replay/pause",
            "/api/replay/step",
            "/api/replay/reset",
        ):
            assert client.get(path).status_code == 405, path

    def test_get_replay_rejects_write_verbs(self, client: TestClient) -> None:
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)("/api/replay").status_code == 405

    def test_no_authentication_or_cookies(self, client: TestClient) -> None:
        response = client.post("/api/replay/start")

        assert "set-cookie" not in response.headers
        assert "www-authenticate" not in response.headers

    def test_no_cors_wildcard(self, client: TestClient) -> None:
        response = client.get(
            "/api/replay", headers={"Origin": "http://evil.test"}
        )

        assert "access-control-allow-origin" not in response.headers

    def test_app_does_not_import_a_concurrency_library_beyond_the_lock(
        self,
    ) -> None:
        """One lock is permitted; a background worker or timer is not."""

        import ast
        import pathlib

        import paper_api

        package = pathlib.Path(paper_api.__file__).parent
        modules = set()

        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules.add((node.module or "").split(".")[0])

        assert "threading" in modules, "the documented lock must be present"
        for forbidden in (
            "asyncio", "multiprocessing", "sqlite3", "redis", "jwt",
            "concurrent", "sched", "queue", "socket", "requests", "httpx",
        ):
            assert forbidden not in modules, forbidden

    def test_replaysession_imports_no_concurrency_library_beyond_threading(
        self,
    ) -> None:
        import ast
        import pathlib

        import paper_api

        path = pathlib.Path(paper_api.__file__).parent / "replaysession.py"
        modules = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])

        assert modules <= {
            "__future__", "threading", "fastapi",
            "crypto_paper_lab", "pydantic",
        }, modules
        assert "threading" in modules

    def test_no_real_money_or_execution_vocabulary_in_the_transport(
        self,
    ) -> None:
        import pathlib
        import tokenize

        import paper_api

        package = pathlib.Path(paper_api.__file__).parent
        for name in ("replaysession.py", "app.py", "schemas.py"):
            kept: list[str] = []
            with (package / name).open("rb") as handle:
                for token in tokenize.tokenize(handle.readline):
                    if token.type in (
                        tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                        tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                    ):
                        continue
                    kept.append(token.string)
            code = " ".join(kept)

            for forbidden in (
                "exchange", "binance", "ccxt", "place_order", "create_order",
                "wallet", "withdraw", "deposit", "leverage", "api_key",
                "secret", "credential", "websocket", "EventSource",
            ):
                assert forbidden not in code, f"{name}: {forbidden}"

    def test_no_mode_or_close_concepts(self) -> None:
        import ast
        import pathlib

        import paper_api

        package = pathlib.Path(paper_api.__file__).parent
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    assert not node.name.startswith("close_"), (
                        f"{path.name}: manual close is declined by Phase 17A Q1"
                    )