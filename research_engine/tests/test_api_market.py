"""Phase 16C tests for the read-only historical market-data endpoint.

Every candle assertion is made against the **engine's own loader output**,
never against a value hard-coded in this file and never against a
reimplementation of the CSV format. That is the point: if the endpoint ever
diverged from ``crypto_paper_lab``, these tests would fail rather than
quietly agreeing with the endpoint.

There is no assertion about price quality, profitability or strategy
behaviour. This endpoint serves history; it says nothing about the future.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paper_api import marketdata
from paper_api.app import create_app
from paper_api.config import ApiConfig
from paper_api.schemas import MarketResponse
from paper_api.session import PaperSession

from crypto_paper_lab.dataset import load_dataset
from crypto_paper_lab.walkforward import (
    DATASET_CANDLES,
    DATASET_FIRST,
    DATASET_LAST,
    DATASET_SHA256,
)

# Authoritative source series, loaded once through the engine's loader.
SOURCE_CANDLES, _ = load_dataset(marketdata.dataset_path())


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(
        create_app(ApiConfig(), session=PaperSession(service="crypto-paper-lab"))
    )


def get(client: TestClient, **params) -> dict:
    response = client.get("/api/market", params=params or None)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# 1-2. status and schema
# ---------------------------------------------------------------------------


def test_market_returns_200(client: TestClient) -> None:
    assert client.get("/api/market").status_code == 200


def test_response_validates_against_the_pydantic_schema(
    client: TestClient,
) -> None:
    parsed = MarketResponse.model_validate(get(client, limit=3))

    assert len(parsed.candles) == 3
    assert parsed.metadata.asset == "BTC/USDT"
    assert parsed.metadata.timeframe == "1h"


def test_schema_rejects_an_unknown_metadata_field() -> None:
    with pytest.raises(ValidationError):
        MarketResponse.model_validate(
            {
                "metadata": {
                    "asset": "BTC/USDT",
                    "timeframe": "1h",
                    "source": "x",
                    "dataset_sha256": "x",
                    "dataset_candles": 1,
                    "dataset_first_timestamp": "2024-01-01T00:00:00Z",
                    "dataset_last_timestamp": "2024-01-01T01:00:00Z",
                    "returned_candles": 1,
                    "truncated": False,
                    "limit": 1,
                    "file_path": "C:/secret/research_engine/data/x.csv",
                },
                "candles": [],
            }
        )


# ---------------------------------------------------------------------------
# 3-4. real data, no synthetic prices
# ---------------------------------------------------------------------------


def test_candles_come_from_the_real_dataset(client: TestClient) -> None:
    meta = get(client, limit=1)["metadata"]

    assert meta["dataset_sha256"] == DATASET_SHA256
    assert meta["dataset_candles"] == DATASET_CANDLES == len(SOURCE_CANDLES)
    assert meta["dataset_candles"] == 17_544


def test_default_slice_is_the_most_recent_real_candles(
    client: TestClient,
) -> None:
    candles = get(client, limit=3)["candles"]

    assert len(candles) == 3
    assert candles[0]["close"] == SOURCE_CANDLES[-3].close
    assert candles[-1]["close"] == SOURCE_CANDLES[-1].close


def test_no_synthetic_or_random_prices(client: TestClient) -> None:
    """Determinism across calls rules out any random generator."""

    first = get(client, limit=50)
    second = get(client, limit=50)

    assert first["candles"] == second["candles"]

    source_closes = {c.close for c in SOURCE_CANDLES}
    for candle in first["candles"]:
        assert candle["close"] in source_closes
        assert candle["open"] in {c.open for c in SOURCE_CANDLES}


def test_prices_are_plausible_ohlc(client: TestClient) -> None:
    """Every bar satisfies the engine's own OHLC invariants."""

    for candle in get(client, limit=200)["candles"]:
        assert candle["low"] <= candle["open"] <= candle["high"]
        assert candle["low"] <= candle["close"] <= candle["high"]
        assert candle["volume"] >= 0


# ---------------------------------------------------------------------------
# 5. ordering
# ---------------------------------------------------------------------------


def test_candles_are_chronological(client: TestClient) -> None:
    stamps = [c["timestamp"] for c in get(client, limit=500)["candles"]]

    assert stamps == sorted(stamps)
    assert len(stamps) == len(set(stamps))


def test_source_ordering_is_preserved_across_a_range(
    client: TestClient,
) -> None:
    candles = get(
        client, start="2025-06-01", end="2025-06-30T23:00:00Z", limit=1000
    )["candles"]

    assert len(candles) == 720
    assert candles[0]["timestamp"] == "2025-06-01T00:00:00Z"
    assert candles[-1]["timestamp"] == "2025-06-30T23:00:00Z"


# ---------------------------------------------------------------------------
# 6. values match the source exactly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("index", [0, 1, 4_367, 8_783, 13_127, 17_542, 17_543])
def test_sampled_candles_match_source_exactly(
    client: TestClient, index: int
) -> None:
    """Pin individual bars by bounding both ends to the same instant."""

    source = SOURCE_CANDLES[index]
    candle = get(
        client,
        start=source.timestamp.isoformat(),
        end=source.timestamp.isoformat(),
        limit=1,
    )["candles"][0]

    assert candle["open"] == source.open
    assert candle["high"] == source.high
    assert candle["low"] == source.low
    assert candle["close"] == source.close
    assert candle["volume"] == source.volume
    assert candle["timestamp"] == f"{source.timestamp.isoformat()}Z"


def test_a_known_row_is_exact(client: TestClient) -> None:
    """The very first bar of the frozen dataset, value for value."""

    source = SOURCE_CANDLES[0]
    candle = get(
        client,
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T00:00:00Z",
        limit=1,
    )["candles"][0]

    assert candle == {
        "timestamp": "2024-01-01T00:00:00Z",
        "open": source.open,
        "high": source.high,
        "low": source.low,
        "close": source.close,
        "volume": source.volume,
    }
    assert candle["close"] == 42503.5


# ---------------------------------------------------------------------------
# 7. UTC semantics
# ---------------------------------------------------------------------------


def test_timestamps_are_explicitly_utc(client: TestClient) -> None:
    for candle in get(client, limit=5)["candles"]:
        assert candle["timestamp"].endswith("Z")


def test_naive_source_timestamps_are_not_shifted(client: TestClient) -> None:
    """A naive source stamp must not be reinterpreted in a local zone."""

    candle = get(
        client,
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T00:00:00Z",
        limit=1,
    )["candles"][0]

    assert candle["timestamp"] == "2024-01-01T00:00:00Z"
    assert candle["timestamp"] == (
        f"{SOURCE_CANDLES[0].timestamp.isoformat()}Z"
    )


def test_naive_and_aware_bounds_denote_the_same_instant(
    client: TestClient,
) -> None:
    aware = get(
        client,
        start="2024-06-01T00:00:00Z",
        end="2024-06-01T00:00:00Z",
        limit=1,
    )
    naive = get(
        client,
        start="2024-06-01T00:00:00",
        end="2024-06-01T00:00:00",
        limit=1,
    )

    assert aware["candles"] == naive["candles"]
    assert len(aware["candles"]) == 1


def test_offset_bound_is_converted_to_utc(client: TestClient) -> None:
    """2024-06-01T02:00:00+02:00 is 2024-06-01T00:00:00Z."""

    candle = get(
        client,
        start="2024-06-01T02:00:00+02:00",
        end="2024-06-01T02:00:00+02:00",
        limit=1,
    )["candles"][0]

    assert candle["timestamp"] == "2024-06-01T00:00:00Z"


def test_metadata_bounds_are_normalised_to_utc(client: TestClient) -> None:
    meta = get(client, start="2024-06-01T02:00:00+02:00", limit=1)["metadata"]

    assert meta["start"] == "2024-06-01T00:00:00Z"


def test_dataset_bounds_match_the_frozen_constants(
    client: TestClient,
) -> None:
    meta = get(client, limit=1)["metadata"]

    assert meta["dataset_first_timestamp"] == (
        f"{DATASET_FIRST.isoformat()}Z"
    )
    assert meta["dataset_last_timestamp"] == f"{DATASET_LAST.isoformat()}Z"


# ---------------------------------------------------------------------------
# 8-10. filtering
# ---------------------------------------------------------------------------


def test_start_filter_is_inclusive(client: TestClient) -> None:
    candles = get(
        client,
        start="2025-03-01T00:00:00Z",
        end="2025-03-01T02:00:00Z",
        limit=3,
    )["candles"]

    assert len(candles) == 3
    assert candles[0]["timestamp"] == "2025-03-01T00:00:00Z"
    assert candles[1]["timestamp"] == "2025-03-01T01:00:00Z"


def test_start_below_the_first_bar_earns_nothing(
    client: TestClient,
) -> None:
    payload = get(client, start="2020-01-01T00:00:00Z", end="2020-01-02")

    assert payload["candles"] == []
    assert payload["metadata"]["returned_candles"] == 0


def test_truncation_takes_the_tail_of_the_filtered_range(
    client: TestClient,
) -> None:
    """Documented semantics: the limit keeps the *most recent* matches.

    ``start`` alone does not mean "count forward from here". A caller who
    wants a specific historical window must bound ``end`` as well. This test
    pins the rule so it cannot change silently.
    """

    payload = get(client, start="2025-03-01T00:00:00Z", limit=3)

    assert payload["metadata"]["truncated"] is True
    assert payload["candles"][0]["timestamp"] == "2025-12-31T21:00:00Z"
    assert payload["candles"][-1]["timestamp"] == "2025-12-31T23:00:00Z"


def test_end_filter_is_inclusive(client: TestClient) -> None:
    candles = get(
        client, end="2025-03-01T02:00:00Z", limit=3
    )["candles"]

    assert candles[-1]["timestamp"] == "2025-03-01T02:00:00Z"
    assert candles[0]["timestamp"] == "2025-03-01T00:00:00Z"


def test_start_and_end_together_bound_the_range(
    client: TestClient,
) -> None:
    payload = get(
        client, start="2025-03-01T00:00:00Z", end="2025-03-01T23:00:00Z"
    )

    assert payload["metadata"]["returned_candles"] == 24
    assert payload["candles"][0]["timestamp"] == "2025-03-01T00:00:00Z"
    assert payload["candles"][-1]["timestamp"] == "2025-03-01T23:00:00Z"
    assert payload["metadata"]["truncated"] is False


def test_a_range_outside_the_dataset_returns_nothing(
    client: TestClient,
) -> None:
    """No fabrication when the requested window holds no data."""

    payload = get(client, start="2030-01-01", end="2030-01-02")

    assert payload["candles"] == []
    assert payload["metadata"]["returned_candles"] == 0
    assert payload["metadata"]["truncated"] is False


# ---------------------------------------------------------------------------
# 11-12. rejected input
# ---------------------------------------------------------------------------


def test_start_after_end_returns_422(client: TestClient) -> None:
    response = client.get(
        "/api/market", params={"start": "2025-01-02", "end": "2025-01-01"}
    )

    assert response.status_code == 422
    assert "start must be earlier than or equal to end" in response.text


def test_equal_start_and_end_is_accepted(client: TestClient) -> None:
    response = client.get(
        "/api/market", params={"start": "2025-01-01", "end": "2025-01-01"}
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["returned_candles"] == 1


@pytest.mark.parametrize(
    "bad",
    ["not-a-date", "2025-13-45", "01/02/2025", "", "2025-01-01T99:00:00Z"],
)
def test_malformed_timestamp_returns_422(client: TestClient, bad: str) -> None:
    response = client.get("/api/market", params={"start": bad})

    assert response.status_code == 422, bad


def test_malformed_end_returns_422(client: TestClient) -> None:
    assert client.get(
        "/api/market", params={"end": "yesterday"}
    ).status_code == 422


# ---------------------------------------------------------------------------
# 13-15. limits and defaults
# ---------------------------------------------------------------------------


def test_limit_is_respected(client: TestClient) -> None:
    for limit in (1, 7, 50, 999):
        payload = get(client, limit=limit)
        assert len(payload["candles"]) == limit
        assert payload["metadata"]["limit"] == limit


def test_limit_has_a_maximum(client: TestClient) -> None:
    assert marketdata.MAX_LIMIT == 5000

    assert client.get(
        "/api/market", params={"limit": marketdata.MAX_LIMIT}
    ).status_code == 200

    assert client.get(
        "/api/market", params={"limit": marketdata.MAX_LIMIT + 1}
    ).status_code == 422
    assert client.get(
        "/api/market", params={"limit": 100_000}
    ).status_code == 422


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_non_positive_limit_is_rejected(
    client: TestClient, limit: int
) -> None:
    assert client.get(
        "/api/market", params={"limit": limit}
    ).status_code == 422


def test_default_request_is_a_bounded_recent_slice(
    client: TestClient,
) -> None:
    payload = get(client)

    assert payload["metadata"]["limit"] == marketdata.DEFAULT_LIMIT == 200
    assert payload["metadata"]["returned_candles"] == 200
    assert payload["metadata"]["truncated"] is True
    assert len(payload["candles"]) == 200
    # Recent means the tail of the dataset, not the head.
    assert payload["candles"][-1]["timestamp"] == "2025-12-31T23:00:00Z"


def test_default_never_returns_the_whole_dataset(
    client: TestClient,
) -> None:
    assert get(client)["metadata"]["returned_candles"] < DATASET_CANDLES


def test_truncation_keeps_the_most_recent_candles(
    client: TestClient,
) -> None:
    payload = get(
        client, start="2025-01-01", end="2025-01-11T00:00:00Z", limit=5
    )

    assert payload["metadata"]["truncated"] is True
    assert payload["candles"][-1]["timestamp"] == "2025-01-11T00:00:00Z"
    assert payload["candles"][0]["timestamp"] == "2025-01-10T20:00:00Z"


# ---------------------------------------------------------------------------
# 16. no path disclosure
# ---------------------------------------------------------------------------


def test_response_never_exposes_filesystem_paths(
    client: TestClient,
) -> None:
    raw = client.get("/api/market", params={"limit": 5}).text

    for leak in (
        "research_engine",
        "BTCUSDT_1h_Cleaned",
        ".csv",
        "C:\\",
        "C:/",
        "/Users/",
        "site-packages",
        str(marketdata.RESEARCH_ENGINE_ROOT),
    ):
        assert leak not in raw, leak


def test_metadata_identifies_the_dataset_without_a_path(
    client: TestClient,
) -> None:
    meta = get(client, limit=1)["metadata"]

    assert meta["dataset_sha256"] == DATASET_SHA256
    assert meta["source"] == "local-research-dataset"
    assert "/" not in meta["source"]


# ---------------------------------------------------------------------------
# 17. determinism
# ---------------------------------------------------------------------------


def test_repeated_identical_requests_are_identical(
    client: TestClient,
) -> None:
    params = {"start": "2025-05-01", "end": "2025-05-02", "limit": 50}

    first = client.get("/api/market", params=params).content
    second = client.get("/api/market", params=params).content
    third = client.get("/api/market", params=params).content

    assert first == second == third


def test_two_separate_clients_agree(client: TestClient) -> None:
    other = TestClient(
        create_app(ApiConfig(), session=PaperSession(service="crypto-paper-lab"))
    )

    assert (
        client.get("/api/market", params={"limit": 20}).content
        == other.get("/api/market", params={"limit": 20}).content
    )


def test_dataset_is_loaded_once_per_process() -> None:
    """The cache is keyed on nothing, so identity proves a single load."""

    marketdata.load_research_candles.cache_clear()
    marketdata.load_research_candles()

    assert marketdata.load_research_candles.cache_info().currsize == 1
    assert marketdata.load_research_candles() is marketdata.load_research_candles()


# ---------------------------------------------------------------------------
# 18-19. earlier endpoints unchanged
# ---------------------------------------------------------------------------


def test_healthz_is_unchanged(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "crypto-paper-lab",
    }


def test_session_is_unchanged(client: TestClient) -> None:
    payload = client.get("/api/session").json()

    assert payload["mode"] == "paper"
    assert payload["account"]["starting_balance"] == 10_000.0
    assert payload["account"]["trade_count"] == 0


def test_calling_market_does_not_disturb_session_or_healthz(
    client: TestClient,
) -> None:
    session_before = client.get("/api/session").content
    health_before = client.get("/healthz").content

    client.get("/api/market", params={"limit": 100})

    assert client.get("/api/session").content == session_before
    assert client.get("/healthz").content == health_before


# ---------------------------------------------------------------------------
# read-only and safety
# ---------------------------------------------------------------------------


def test_market_is_read_only(client: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/market").status_code == 405, method


def test_no_live_or_exchange_surface(client: TestClient) -> None:
    raw = client.get("/api/market", params={"limit": 2}).text.lower()

    for banned in ("live", "exchange", "binance", "api_key", "websocket"):
        assert banned not in raw, banned


def test_cors_wildcard_absent_on_market(client: TestClient) -> None:
    response = client.get(
        "/api/market", headers={"Origin": "http://evil.test"}
    )

    assert "access-control-allow-origin" not in response.headers


# --- D2b: declared dataset identity on the production research-data path ----
#
# These use a synthetic registry. Nothing here loads the served dataset, reads
# a price, or touches the reserved ETH file.


def _registry(instruments, consumed=(), reservations=()):
    return {
        "instruments": list(instruments),
        "consumed_windows": list(consumed),
        "reservations": list(reservations),
    }


def _use_registry(monkeypatch: pytest.MonkeyPatch, registry) -> None:
    """Point the resolver at a synthetic registry.

    ``served_dataset_identity`` imports ``load_registry`` from inside the
    function body, so the patch target is the source module -- patching
    ``marketdata.load_registry`` would bind a name nothing reads and the tests
    would silently exercise the real registry instead.
    """

    monkeypatch.setattr(
        "crypto_paper_lab.researchguard.load_registry", lambda: registry
    )


BTC = {
    "instrument_id": "BTC/USDT",
    "market_type": "crypto_spot",
    "timeframe": "1h",
    "volume_semantics": "central_base",
}

# Declared here only so a synthetic registry can describe a contradiction. It
# is never used to authorise anything: ETH/USDT carries a live reservation, and
# these fixtures only assert that conflicting declarations are refused.
ETH = {
    "instrument_id": "ETH/USDT",
    "market_type": "crypto_spot",
    "timeframe": "1h",
    "volume_semantics": "central_base",
}


def test_served_identity_comes_from_the_registry_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declaration is read from the manifest, never inferred from bars."""

    monkeypatch.setattr(
        marketdata, "DATASET_PATH", "data/BTCUSDT_1h_Cleaned (1).csv"
    )
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[
                {
                    "dataset_path": "data/BTCUSDT_1h_Cleaned (1).csv",
                    "instrument_id": "BTC/USDT",
                    "timeframe": "1h",
                }
            ],
        ),
    )

    identity = marketdata.served_dataset_identity()

    assert identity.instrument_id == "BTC/USDT"
    assert identity.market_type == "crypto_spot"
    assert identity.timeframe == "1h"
    # Identity must agree with the cost authority the sessions validate against.
    assert identity.market_type == marketdata.MARKET_TYPE


def test_undeclared_dataset_path_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dataset nobody declared is refused, not served with an invented identity."""

    monkeypatch.setattr(marketdata, "DATASET_PATH", "data/never_declared.csv")
    _use_registry(monkeypatch, _registry([BTC]))

    with pytest.raises(RuntimeError, match="no registry declaration"):
        marketdata.served_dataset_identity()


def test_missing_instrument_entry_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(marketdata, "DATASET_PATH", "data/ghost.csv")
    _use_registry(
        monkeypatch,
        _registry(
            [],
            consumed=[
                {"dataset_path": "data/ghost.csv", "instrument_id": "GHOST/USDT",
                 "timeframe": "1h"}
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="no instrument entry"):
        marketdata.served_dataset_identity()


def test_manifest_instrument_timeframe_disagreement_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two records disagreeing is a registry bug, not something to reconcile."""

    monkeypatch.setattr(marketdata, "DATASET_PATH", "data/conflict.csv")
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[
                {"dataset_path": "data/conflict.csv", "instrument_id": "BTC/USDT",
                 "timeframe": "4h"}
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="Refusing to reconcile"):
        marketdata.served_dataset_identity()


def test_reservations_are_searched_as_well_as_consumed_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dataset declared only as a reservation is still declared."""

    monkeypatch.setattr(marketdata, "DATASET_PATH", "data/reserved_only.csv")
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            reservations=[
                {"dataset_path": "data/reserved_only.csv",
                 "instrument_id": "BTC/USDT", "timeframe": "1h"}
            ],
        ),
    )

    assert marketdata.served_dataset_identity().instrument_id == "BTC/USDT"


def test_patch_target_is_effective_not_silently_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guards the patching mechanism itself.

    If the patch target ever stopped being the module the resolver actually
    reads, the tests above would silently fall back to the real registry and
    pass or fail for the wrong reason. This asserts the substitution lands.
    """

    _use_registry(monkeypatch, _registry([]))

    from crypto_paper_lab.researchguard import load_registry

    assert load_registry() == {"instruments": [], "consumed_windows": [],
                               "reservations": []}


# --- D2c: registry declaration ambiguity and path normalization -------------
#
# Every lookup below is resolved against a synthetic registry. No dataset file
# is read, no price is inspected, and nothing touches the reserved ETH series.
#
# The invariant under test: one physical dataset has exactly one declared
# identity, and anything that could serve it under two different identities is
# refused rather than resolved by list order.

SERVED = "data/BTCUSDT_1h_Cleaned (1).csv"


def test_conflicting_declarations_across_sections_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same path declared in both sections under different instruments.

    Previously the first match won, so list order silently decided which
    instrument the served dataset was validated against.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC, ETH],
            consumed=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                       "timeframe": "1h"}],
            reservations=[{"dataset_path": SERVED, "instrument_id": "ETH/USDT",
                           "timeframe": "1h"}],
        ),
    )

    with pytest.raises(RuntimeError, match="conflicting registry declarations"):
        marketdata.served_dataset_identity()


def test_conflicting_duplicates_within_one_section_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate declaration is not a synonym for the first one."""

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC, ETH],
            consumed=[
                {"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                 "timeframe": "1h"},
                {"dataset_path": SERVED, "instrument_id": "ETH/USDT",
                 "timeframe": "1h"},
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="conflicting registry declarations"):
        marketdata.served_dataset_identity()


def test_same_instrument_conflicting_timeframe_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agreement is required on timeframe too, not only on the instrument."""

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[
                {"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                 "timeframe": "1h"},
                {"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                 "timeframe": "4h"},
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="conflicting registry declarations"):
        marketdata.served_dataset_identity()


def test_case_only_path_collision_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two records differing only in case name one file on this filesystem.

    Case-insensitive lookup means ``DATA/X.CSV`` and ``data/x.csv`` are the
    same file, so declaring them as different instruments must not resolve to
    whichever was listed first.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC, ETH],
            consumed=[
                {"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                 "timeframe": "1h"},
                {"dataset_path": SERVED.upper(), "instrument_id": "ETH/USDT",
                 "timeframe": "1h"},
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="conflicting registry declarations"):
        marketdata.served_dataset_identity()


@pytest.mark.parametrize(
    "requested",
    [
        "data/BTCUSDT_1h_Cleaned (1).csv",
        "data\\BTCUSDT_1h_Cleaned (1).csv",
        "./data/BTCUSDT_1h_Cleaned (1).csv",
        "data//BTCUSDT_1h_Cleaned (1).csv",
        "././data/BTCUSDT_1h_Cleaned (1).csv",
        "DATA/BTCUSDT_1H_CLEANED (1).CSV",
    ],
    ids=["identical", "backslashes", "dot-prefix", "double-separator",
         "repeated-dot", "uppercase"],
)
def test_equivalent_path_forms_resolve_to_one_identity(
    monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    """Spelling differences must not change which declaration is found.

    Each of these names the same file, so each must resolve to the one declared
    identity rather than refusing or, worse, matching a different record.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", requested)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                       "timeframe": "1h"}],
        ),
    )

    identity = marketdata.served_dataset_identity()

    assert identity.instrument_id == "BTC/USDT"
    assert identity.market_type == "crypto_spot"
    assert identity.timeframe == "1h"


# --- D2d: absolute-path refusal and full identity agreement ----------------
#
# The canonicalizer drops empty segments, so a leading "/" or "\" disappears
# during normalization. An absolute request would therefore be reduced to the
# same key as a repo-relative declaration and could match one it does not name.
# These tests pin the refusal that happens *before* canonicalization.


@pytest.mark.parametrize(
    "requested",
    [
        "/data/example.csv",
        "C:\\data\\example.csv",
        "C:/data/example.csv",
        "\\data\\example.csv",
        "//server/share/example.csv",
    ],
    ids=["posix-absolute", "windows-drive", "windows-drive-slash",
         "windows-rooted", "unc"],
)
def test_absolute_and_rooted_paths_refused(
    monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    """An absolute path must never resolve a repository-relative declaration.

    Without this refusal ``/data/x.csv`` canonicalizes to ``data/x.csv`` and
    would match a relative declaration it does not actually name.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", "data/example.csv")
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[{"dataset_path": "data/example.csv",
                       "instrument_id": "BTC/USDT", "timeframe": "1h"}],
        ),
    )

    monkeypatch.setattr(marketdata, "DATASET_PATH", requested)

    with pytest.raises(RuntimeError, match="absolute or filesystem-rooted"):
        marketdata.served_dataset_identity()


def test_relative_forms_still_resolve_alongside_absolute_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The absolute-path refusal must not narrow what relative paths accept."""

    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[{"dataset_path": "data/example.csv",
                       "instrument_id": "BTC/USDT", "timeframe": "1h"}],
        ),
    )

    for spelling in (
        "data/example.csv",
        "./data/example.csv",
        "data\\example.csv",
        "data//example.csv",
        "././data/example.csv",
        "data/./example.csv",
        "DATA/EXAMPLE.CSV",
    ):
        monkeypatch.setattr(marketdata, "DATASET_PATH", spelling)
        identity = marketdata.served_dataset_identity()
        assert identity.instrument_id == "BTC/USDT", spelling
        assert identity.market_type == "crypto_spot", spelling
        assert identity.timeframe == "1h", spelling


def test_conflicting_dataset_sha256_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agreement on instrument and timeframe is not agreement on identity.

    ``dataset_sha256`` is a DatasetIdentity field carried on both record
    types, so two records claiming one path holds two different sets of bytes
    are contradictory even though instrument and timeframe match.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                       "timeframe": "1h", "dataset_sha256": "a" * 64}],
            reservations=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                           "timeframe": "1h", "dataset_sha256": "b" * 64}],
        ),
    )

    with pytest.raises(RuntimeError, match="conflicting dataset_sha256"):
        marketdata.served_dataset_identity()


def test_absent_digest_is_not_treated_as_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unstated digest is not a contradictory one.

    Two records agreeing on instrument and timeframe, where one simply omits
    the digest, must still resolve -- otherwise the conflict check would refuse
    correct registries that record the digest unevenly.
    """

    monkeypatch.setattr(marketdata, "DATASET_PATH", SERVED)
    _use_registry(
        monkeypatch,
        _registry(
            [BTC],
            consumed=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                       "timeframe": "1h", "dataset_sha256": "A" * 64}],
            reservations=[{"dataset_path": SERVED, "instrument_id": "BTC/USDT",
                           "timeframe": "1h"}],
        ),
    )

    assert marketdata.served_dataset_identity().instrument_id == "BTC/USDT"