"""Phase 16D tests for the read-only strategy signal endpoint.

The central claim under test is narrow and important: **every trading value in
the response is whatever ``crypto_paper_lab.strategy.analyze`` returned.**

Assertions are therefore made against the engine called directly, never
against literals copied from the endpoint's own output. If the API ever grew
its own trend, breakout, retest or level logic, these comparisons would fail.

There is no assertion about signal quality, profitability or future returns.
The engine expresses no such view and neither does this endpoint.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paper_api import marketdata, signals
from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.schemas import SignalResponse
from paper_api.session import PaperSession

from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.models import Candle
from crypto_paper_lab.strategy import StrategyConfig, analyze
from crypto_paper_lab.walkforward import (
    DATASET_SHA256,
    a2_config,
    baseline_config,
    config_hash,
)

SOURCE, _ = load_dataset(marketdata.dataset_path())
CONFIG = baseline_config()
EXPECTED_HASH = "2FBDB9A8814ABC81062C2B0A61DFDCFAC69C95CF1789D0BAE6BEE4B11ADC3BF7"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(
        create_app(ApiConfig(), session=PaperSession(service="crypto-paper-lab"))
    )


# ---------------------------------------------------------------------------
# 1-2. status and schema
# ---------------------------------------------------------------------------


def test_signal_returns_200(client: TestClient) -> None:
    assert client.get("/api/signal").status_code == 200


def test_response_validates_against_the_schema(client: TestClient) -> None:
    parsed = SignalResponse.model_validate(client.get("/api/signal").json())

    assert parsed.signal in ("long", "short", "flat")
    assert parsed.strategy.config_hash == EXPECTED_HASH


def test_schema_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        SignalResponse.model_validate(
            {
                "service": "crypto-paper-lab",
                "asset": "BTC/USDT",
                "timeframe": "1h",
                "timestamp": "2025-12-31T23:00:00Z",
                "signal": "flat",
                "reason": "x",
                "price": 1.0,
                "support": 1.0,
                "resistance": 1.0,
                "trend": "down",
                "breakout": False,
                "retest": False,
                "signal_close": 1.0,
                "trend_state": "down",
                "realised_volatility": 0.1,
                "mean_range": 1.0,
                "confidence": 0.87,
                "strategy": {"config_hash": "x", "config_repr": "x"},
                "source": {
                    "dataset_sha256": "x",
                    "dataset_first_timestamp": "2024-01-01T00:00:00Z",
                    "dataset_last_timestamp": "2025-12-31T23:00:00Z",
                },
            }
        )


# ---------------------------------------------------------------------------
# 3-4. produced by the real engine; no duplicate algorithm
# ---------------------------------------------------------------------------


def test_default_signal_equals_analyze_called_directly(
    client: TestClient,
) -> None:
    expected = analyze(SOURCE, CONFIG)
    payload = client.get("/api/signal").json()

    assert payload["signal"] == expected.side
    assert payload["reason"] == expected.reason
    assert payload["price"] == expected.price
    assert payload["support"] == expected.support
    assert payload["resistance"] == expected.resistance
    assert payload["trend"] == expected.trend
    assert payload["breakout"] == expected.breakout
    assert payload["retest"] == expected.retest
    assert payload["signal_close"] == expected.signal_close
    assert payload["trend_state"] == expected.trend_state
    assert payload["breakout_distance"] == expected.breakout_distance
    assert payload["retest_distance"] == expected.retest_distance
    assert payload["realised_volatility"] == expected.realised_volatility
    assert payload["mean_range"] == expected.mean_range


@pytest.mark.parametrize(
    "stamp", ["2024-06-15T00:00:00Z", "2025-03-01T00:00:00Z", "2025-11-30T12:00:00Z"]
)
def test_signals_at_chosen_times_match_the_engine(
    client: TestClient, stamp: str
) -> None:
    index = marketdata.candle_index_by_timestamp()[
        _naive(stamp)
    ]
    expected = analyze(SOURCE[: index + 1], CONFIG)
    payload = client.get("/api/signal", params={"at": stamp}).json()

    assert payload["signal"] == expected.side
    assert payload["reason"] == expected.reason
    assert payload["support"] == expected.support
    assert payload["resistance"] == expected.resistance
    assert payload["timestamp"] == stamp


def _naive(stamp: str):
    return marketdata.as_naive_utc(
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    )


def test_api_module_contains_no_strategy_arithmetic() -> None:
    """The API must delegate, not reimplement.

    ``analyze`` is called and its result returned. None of the engine's
    decision vocabulary may be computed in the API layer.
    """

    import pathlib

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent
    forbidden = (
        "support_resistance",
        "simple_moving_average",
        "realised_volatility(",
        "mean_candle_range(",
        "trend(",
        "breakout_buffer",
        "retest_tolerance",
        "min_breakout_distance",
    )

    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name} contains {token!r}"


def test_only_the_signal_module_calls_analyze() -> None:
    import pathlib

    import paper_api

    package = pathlib.Path(paper_api.__file__).parent
    callers = [
        path.name
        for path in sorted(package.glob("*.py"))
        if "analyze(" in path.read_text(encoding="utf-8")
    ]

    assert callers == ["signals.py"]


# ---------------------------------------------------------------------------
# 5-6. authoritative identity
# ---------------------------------------------------------------------------


def test_config_hash_matches_the_phase13_baseline(
    client: TestClient,
) -> None:
    frozen = json.load(
        (
            marketdata.RESEARCH_ENGINE_ROOT
            / "experiments/phase13/RESULTS_windows.json"
        ).open(encoding="utf-8")
    )
    frozen_baseline = next(
        r["config_hash"] for r in frozen if r["config_name"] == "baseline"
    )
    payload = client.get("/api/signal").json()

    assert payload["strategy"]["config_hash"] == frozen_baseline
    assert payload["strategy"]["config_hash"] == EXPECTED_HASH
    assert payload["strategy"]["config_repr"] == repr(CONFIG)


def test_config_is_baseline_not_a2(client: TestClient) -> None:
    """A2 is a Phase 7 selection, not the baseline."""

    assert client.get("/api/signal").json()["strategy"]["config_hash"] != (
        config_hash(a2_config())
    )
    assert client.get("/api/signal").json()["strategy"]["config_hash"] == (
        config_hash(CONFIG)
    )


def test_default_config_is_the_unmodified_baseline() -> None:
    assert CONFIG == StrategyConfig()


def test_dataset_hash_matches_the_authoritative_dataset(
    client: TestClient,
) -> None:
    source = client.get("/api/signal").json()["source"]

    assert source["dataset_sha256"] == DATASET_SHA256
    assert (
        source["dataset_sha256"]
        == "201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B"
    )


# ---------------------------------------------------------------------------
# 7. UTC timestamps
# ---------------------------------------------------------------------------


def test_timestamp_is_utc(client: TestClient) -> None:
    assert client.get("/api/signal").json()["timestamp"].endswith("Z")


def test_default_timestamp_is_the_last_completed_candle(
    client: TestClient,
) -> None:
    payload = client.get("/api/signal").json()

    assert payload["timestamp"] == "2025-12-31T23:00:00Z"
    assert payload["timestamp"] == f"{SOURCE[-1].timestamp.isoformat()}Z"


def test_source_bounds_are_utc(client: TestClient) -> None:
    source = client.get("/api/signal").json()["source"]

    assert source["dataset_first_timestamp"] == "2024-01-01T00:00:00Z"
    assert source["dataset_last_timestamp"] == "2025-12-31T23:00:00Z"


# ---------------------------------------------------------------------------
# 8. causality
# ---------------------------------------------------------------------------


def _shift(candles, from_index: int, amount: float) -> list:
    out = list(candles)
    for i in range(from_index, len(out)):
        c = out[i]
        out[i] = Candle(
            c.timestamp, c.open + amount, c.high + amount,
            c.low + amount, c.close + amount, c.volume + 5.0,
        )
    return out


def test_future_candles_cannot_change_the_signal() -> None:
    """Corrupt the entire future; the signal for a past bar must not move."""

    index = 12_000
    original = signals.signal_at_index(SOURCE, CONFIG, index)

    mutated = _shift(SOURCE, index + 1, amount=5_000.0)
    after = signals.signal_at_index(mutated, CONFIG, index)

    assert after.side == original.side
    assert after.reason == original.reason
    assert after.price == original.price
    assert after.support == original.support
    assert after.resistance == original.resistance
    assert after.trend == original.trend
    assert after.breakout == original.breakout
    assert after.retest == original.retest
    assert after.realised_volatility == original.realised_volatility
    assert after.mean_range == original.mean_range


def test_endpoint_signal_is_unaffected_by_a_mutated_future(
    client: TestClient,
) -> None:
    stamp = "2025-06-01T00:00:00Z"
    index = marketdata.candle_index_by_timestamp()[_naive(stamp)]

    before = client.get("/api/signal", params={"at": stamp}).json()

    # The endpoint slices candles[:index + 1]; a mutated tail is unreachable.
    mutated_tail = _shift(SOURCE, index + 1, amount=-9_000.0)
    after_signal = signals.signal_at_index(mutated_tail, CONFIG, index)

    assert after_signal.side == before["signal"]
    assert after_signal.reason == before["reason"]
    assert after_signal.price == before["price"]
    assert after_signal.timestamp.isoformat() + "Z" == before["timestamp"]


def test_signal_window_is_the_slice_up_to_and_including_the_bar() -> None:
    """The one-candle gap: nothing after the signal bar is visible."""

    index = 5_000
    signal = signals.signal_at_index(SOURCE, CONFIG, index)

    # analyze() treats the last element as `current`; the signal timestamp must
    # therefore be candles[index], never candles[index + 1].
    assert signal.timestamp == SOURCE[index].timestamp
    assert signal.timestamp != SOURCE[index + 1].timestamp
    assert signal.price == SOURCE[index].close


def test_minimum_history_is_derived_from_the_config() -> None:
    assert signals.minimum_history(CONFIG) == 22
    assert signals.minimum_history(a2_config()) == 22


def test_insufficient_history_is_refused_not_guessed() -> None:
    with pytest.raises(signals.InsufficientHistoryError):
        signals.signal_at_index(SOURCE, CONFIG, 10)

    # Exactly 22 candles is enough.
    assert signals.signal_at_index(SOURCE, CONFIG, 21).timestamp == (
        SOURCE[21].timestamp
    )


# ---------------------------------------------------------------------------
# 9. determinism
# ---------------------------------------------------------------------------


def test_repeated_requests_are_identical(client: TestClient) -> None:
    first = client.get("/api/signal").content
    second = client.get("/api/signal").content
    third = client.get("/api/signal").content

    assert first == second == third


def test_requests_at_a_fixed_time_are_identical(client: TestClient) -> None:
    params = {"at": "2025-02-14T06:00:00Z"}

    assert (
        client.get("/api/signal", params=params).content
        == client.get("/api/signal", params=params).content
    )


# ---------------------------------------------------------------------------
# 10-12. nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "banned",
    [
        "confidence",
        "probability",
        "likelihood",
        "score",
        "expected_return",
        "predicted_price",
        "target_price",
        "forecast",
        "profit",
        "edge",
        "win_rate",
        "outcome",
        "guarantee",
    ],
)
def test_no_fabricated_field_is_exposed(
    client: TestClient, banned: str
) -> None:
    raw = client.get("/api/signal").text.lower()

    assert f'"{banned}"' not in raw, banned


def test_engine_signal_model_has_no_confidence() -> None:
    from dataclasses import fields

    from crypto_paper_lab.models import Signal

    names = {f.name for f in fields(Signal)}

    assert "confidence" not in names
    assert names == {
        "timestamp", "side", "reason", "price", "support", "resistance",
        "trend", "breakout", "retest", "signal_close", "trend_state",
        "breakout_distance", "retest_distance", "realised_volatility",
        "mean_range",
    }


def test_exposed_fields_map_one_to_one_onto_the_signal_model(
    client: TestClient,
) -> None:
    """Every Signal field is exposed under its own name, except side -> signal.

    This is what stops the API from quietly becoming a second model: if a
    trading field were added to ``Signal`` and not surfaced here, or surfaced
    under an invented name, this comparison breaks.
    """

    from dataclasses import fields

    from crypto_paper_lab.models import Signal

    payload = set(client.get("/api/signal").json())
    non_signal_keys = {"service", "asset", "timeframe", "strategy", "source"}
    renamed = {"signal"}  # Signal.side

    expected = {f.name for f in fields(Signal)} - {"side"}

    assert payload - non_signal_keys - renamed == expected
    assert payload & non_signal_keys == non_signal_keys


# ---------------------------------------------------------------------------
# 13. unknown / invalid timestamps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stamp",
    [
        "2025-03-01T00:00:30Z",   # between bars
        "2025-03-01T00:00:01Z",   # one second after a real bar
        "2030-01-01T00:00:00Z",   # beyond the dataset
        "2019-01-01T00:00:00Z",   # before the dataset
    ],
)
def test_timestamp_not_in_the_dataset_returns_404(
    client: TestClient, stamp: str
) -> None:
    response = client.get("/api/signal", params={"at": stamp})

    assert response.status_code == 404, stamp
    assert "no candle exists" in response.text


def test_date_only_bound_means_midnight_utc(client: TestClient) -> None:
    """Hourly data means every midnight exists, so a date is a valid instant.

    Documented because it is the one case where a "date" is not ambiguous.
    """

    response = client.get("/api/signal", params={"at": "2025-03-01"})

    assert response.status_code == 200
    assert response.json()["timestamp"] == "2025-03-01T00:00:00Z"


@pytest.mark.parametrize("bad", ["nope", "2025-13-45", ""])
def test_malformed_timestamp_returns_422(
    client: TestClient, bad: str
) -> None:
    assert client.get(
        "/api/signal", params={"at": bad}
    ).status_code == 422


def test_too_early_but_valid_timestamp_returns_422(
    client: TestClient,
) -> None:
    """Inside the dataset, but before the strategy has enough history."""

    response = client.get(
        "/api/signal", params={"at": "2024-01-01T05:00:00Z"}
    )

    assert response.status_code == 422
    assert "needs 22 candles" in response.text


def test_no_interpolation_happens(client: TestClient) -> None:
    """A near miss must not yield a synthesised bar."""

    exact = client.get("/api/signal", params={"at": "2025-03-01T00:00:00Z"})
    between = client.get(
        "/api/signal", params={"at": "2025-03-01T00:00:01Z"}
    )

    assert exact.status_code == 200
    assert between.status_code == 404


# ---------------------------------------------------------------------------
# 14-16. earlier endpoints unchanged
# ---------------------------------------------------------------------------


def test_healthz_unchanged(client: TestClient) -> None:
    assert client.get("/healthz").json() == {
        "status": "ok",
        "service": "crypto-paper-lab",
    }


def test_session_unchanged(client: TestClient) -> None:
    session = client.get("/api/session").json()

    assert session["mode"] == "paper"
    assert session["account"]["starting_balance"] == 10_000.0
    assert session["account"]["trade_count"] == 0
    assert session["has_open_position"] is False


def test_market_unchanged(client: TestClient) -> None:
    market = client.get("/api/market", params={"limit": 3}).json()

    assert market["metadata"]["dataset_candles"] == 17_544
    assert len(market["candles"]) == 3


def test_calling_signal_does_not_disturb_anything(
    client: TestClient,
) -> None:
    before = (
        client.get("/healthz").content,
        client.get("/api/session").content,
        client.get("/api/market", params={"limit": 5}).content,
    )

    client.get("/api/signal")
    client.get("/api/signal", params={"at": "2025-01-01T00:00:00Z"})

    after = (
        client.get("/healthz").content,
        client.get("/api/session").content,
        client.get("/api/market", params={"limit": 5}).content,
    )

    assert before == after


# ---------------------------------------------------------------------------
# read-only, no execution surface
# ---------------------------------------------------------------------------


def test_signal_is_read_only(client: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/signal").status_code == 405, method


def test_no_execution_surface(client: TestClient) -> None:
    raw = client.get("/api/signal").text.lower()

    for banned in ("order", "execute", "fill", "position_size", "leverage"):
        assert banned not in raw, banned


def test_signal_does_not_open_a_position(client: TestClient) -> None:
    """Reading a LONG or SHORT signal must not create a trade."""

    client.get("/api/signal")
    session = client.get("/api/session").json()

    assert session["account"]["trade_count"] == 0
    assert session["has_open_position"] is False
    assert session["account"]["balance"] == session["account"][
        "starting_balance"
    ]


def test_cors_wildcard_absent(client: TestClient) -> None:
    response = client.get("/api/signal", headers={"Origin": "http://evil.test"})

    assert "access-control-allow-origin" not in response.headers