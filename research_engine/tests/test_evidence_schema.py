"""Phase 47 tests: evidence records for news, events and sentiment.

Entirely synthetic. No provider is contacted, no article is fetched, and no
credential exists in this repository. The tests exist to pin the *discipline*
the records enforce, not to validate any real-world feed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.evidence import (
    EVIDENCE_KINDS,
    FORBIDDEN_FORECAST_FIELDS,
    FRESHNESS_THRESHOLDS,
    EconomicEvent,
    EvidenceCluster,
    EvidenceError,
    EvidenceItem,
    EventKind,
    Freshness,
    SentimentObservation,
    assert_not_a_forecast,
    conflicting_evidence,
    evidence_age_band,
    staleness_window,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def item(**overrides: object) -> EvidenceItem:
    fields: dict[str, object] = {
        "evidence_id": "e1",
        "kind": "news_article",
        "publisher": "Example Wire",
        "canonical_url": "https://example.invalid/news/e1",
        "headline": "Something happened",
        "retrieved_at": NOW,
        "published_at": NOW - timedelta(hours=2),
        "licence_note": "Attribution required; redistribution not permitted.",
    }
    fields.update(overrides)
    return EvidenceItem(**fields)  # type: ignore[arg-type]


def event(**overrides: object) -> EconomicEvent:
    fields: dict[str, object] = {
        "event_id": "ev1",
        "name": "Consumer Price Index",
        "authority": "BLS",
        "kind": EventKind.SCHEDULED,
        "scheduled_at": NOW - timedelta(hours=3),
        "retrieved_at": NOW,
        "timezone_note": "08:30 America/New_York",
        "values_source": "BLS news release",
    }
    fields.update(overrides)
    return EconomicEvent(**fields)  # type: ignore[arg-type]


# ==========================================================================
# required attribution
# ==========================================================================


@pytest.mark.parametrize(
    "field", ["evidence_id", "kind", "publisher", "canonical_url", "headline"]
)
def test_required_fields_refused(field: str) -> None:
    """A missing field must be *refused*, not defaulted.

    The guard is on the blank/None value rather than on presence, so both an
    absent key and an explicitly empty one raise the same way.
    """

    defaults = {
        "evidence_id": "e1", "kind": "news_article", "publisher": "P",
        "canonical_url": "https://example.invalid/x", "headline": "H",
        "retrieved_at": NOW,
    }
    with pytest.raises(EvidenceError, match=field):
        EvidenceItem(**{**defaults, field: ""})  # type: ignore[arg-type]


def test_non_http_url_refused() -> None:
    with pytest.raises(EvidenceError, match="not an http"):
        item(canonical_url="ftp://example.invalid/x")


def test_unknown_kind_refused() -> None:
    """An aggregator must declare itself, not masquerade as original reporting."""

    with pytest.raises(EvidenceError, match="kind"):
        item(kind="market_commentary")


def test_known_kinds_accepted() -> None:
    for kind in EVIDENCE_KINDS:
        assert item(kind=kind).kind == kind


# ==========================================================================
# timestamp handling
# ==========================================================================


def test_naive_timestamp_refused() -> None:
    """A naive timestamp is ambiguous and would corrupt a freshness calculation."""

    with pytest.raises(EvidenceError, match="timezone-aware"):
        item(retrieved_at=datetime(2026, 10, 9, 12, 0))


def test_naive_published_at_refused() -> None:
    with pytest.raises(EvidenceError, match="timezone-aware"):
        item(published_at=datetime(2026, 10, 9, 10, 0))


def test_non_utc_offset_normalised() -> None:
    aware = datetime(2026, 10, 9, 14, 0, tzinfo=timezone(timedelta(hours=2))
                     )
    record = item(retrieved_at=aware)
    assert record.retrieved_at.tzinfo == timezone.utc
    assert record.retrieved_at.hour == 12


def test_undated_item_is_permitted_but_not_usable() -> None:
    """A record may exist without a publication time; it simply cannot be shown fresh."""

    record = item(published_at=None)
    assert record.published_at is None
    assert record.age_hours is None
    assert record.freshness() is Freshness.UNDATED
    assert record.is_usable() is False


def test_undated_time_is_never_invented() -> None:
    assert item(published_at=None).as_record()["published_at"] is None


def test_future_dated_item_not_treated_as_fresh() -> None:
    record = item(published_at=NOW + timedelta(hours=5))
    assert record.freshness(reference=NOW) is Freshness.UNDATED


# ==========================================================================
# freshness and staleness
# ==========================================================================


def test_fresh_item() -> None:
    record = item(published_at=NOW - timedelta(hours=1))
    assert record.freshness() is Freshness.FRESH
    assert record.is_usable() is True


def test_stale_item() -> None:
    record = item(published_at=NOW - timedelta(hours=48))
    assert record.freshness() is Freshness.STALE
    assert record.is_usable() is True


def test_expired_item_not_usable() -> None:
    record = item(published_at=NOW - timedelta(hours=500))
    assert record.freshness() is Freshness.EXPIRED
    assert record.is_usable() is False


def test_freshness_thresholds_are_the_documented_ones() -> None:
    """Pinned so a policy change is a visible edit rather than a silent drift."""

    assert FRESHNESS_THRESHOLDS[Freshness.FRESH] == 24.0
    assert FRESHNESS_THRESHOLDS[Freshness.STALE] == 168.0


def test_freshness_uses_published_not_retrieved() -> None:
    """Age is how old the claim is, not how long we have had it."""

    old = item(published_at=NOW - timedelta(days=30), retrieved_at=NOW)
    assert old.age_hours is not None and old.age_hours > 700
    assert old.freshness() is Freshness.EXPIRED


def test_age_band_helper() -> None:
    assert evidence_age_band(None) == "undated"
    assert evidence_age_band(-1) == "future_dated"
    assert evidence_age_band(1) == "fresh"
    assert evidence_age_band(48) == "stale"
    assert evidence_age_band(1000) == "expired"


def test_staleness_window_is_explicit() -> None:
    cutoff = staleness_window(NOW, 24.0)
    assert cutoff == NOW - timedelta(hours=24)
    assert cutoff < NOW


# ==========================================================================
# licensing and attribution
# ==========================================================================


def test_missing_attribution_refuses() -> None:
    record = item(licence_note=None, attribution_required=True)
    assert record.is_usable() is False


def test_attribution_not_required_is_permitted() -> None:
    record = item(licence_note=None, attribution_required=False)
    assert record.is_usable() is True


def test_public_visibility_is_not_redistribution_right() -> None:
    """A URL proves traceability, not permission to republish."""

    record = item(licence_note=None, attribution_required=True)
    assert record.canonical_url.startswith("https://")
    assert record.is_usable() is False


# ==========================================================================
# syndication and duplicates
# ==========================================================================


def test_syndicated_copy_requires_original_source() -> None:
    with pytest.raises(EvidenceError, match="original_source_id"):
        item(is_syndicated_copy=True)


def test_syndicated_copy_with_origin_permitted() -> None:
    record = item(is_syndicated_copy=True, original_source_id="e0")
    assert record.original_source_id == "e0"


def test_record_cannot_be_its_own_source() -> None:
    with pytest.raises(EvidenceError, match="own source"):
        item(is_syndicated_copy=True, original_source_id="e1")


def test_cluster_representative_not_also_a_member() -> None:
    with pytest.raises(EvidenceError, match="not also appear in members"):
        EvidenceCluster("c1", "e1", members=["e1"])


def test_five_copies_are_one_claim() -> None:
    """Five syndicated copies of one wire story are one claim, not five."""

    cluster = EvidenceCluster(
        "c1", "e1",
        members=["e2", "e3", "e4", "e5"],
        rationale="same wire story",
    )
    assert cluster.independent_count == 1
    assert cluster.has_conflict() is False


def test_conflicting_report_counts_separately() -> None:
    cluster = EvidenceCluster("c1", "e1", members=["e2"], conflicting_ids=["e9"])
    assert cluster.independent_count == 2
    assert cluster.has_conflict() is True


def test_item_cannot_be_member_and_conflict() -> None:
    """A copy of the same story cannot simultaneously contradict itself.

    The distinction this guards is real: a member is a reproduction of the
    representative, while a conflicting report is an independent claim. An id in
    both lists would inflate ``independent_count`` while claiming agreement.
    """

    with pytest.raises(EvidenceError, match="cluster member"):
        EvidenceCluster("c1", "e1", members=["e2"], conflicting_ids=["e2"])


def test_cluster_requires_ids() -> None:
    with pytest.raises(EvidenceError):
        EvidenceCluster("", "e1")


def test_conflicting_evidence_groups_and_flags() -> None:
    items = [
        item(evidence_id="e1", cluster_id="c1", published_at=NOW - timedelta(hours=3)),
        item(
            evidence_id="e2", cluster_id="c1", published_at=NOW - timedelta(hours=2),
            source_credibility_note="conflicting figure reported",
        ),
        item(evidence_id="e9", published_at=NOW - timedelta(hours=1)),
    ]
    clusters = conflicting_evidence(items)
    assert len(clusters) == 1
    assert clusters[0].representative_id == "e1", "earliest published is representative"
    assert clusters[0].has_conflict() is True


def test_unclustered_items_are_not_grouped() -> None:
    assert conflicting_evidence([item(evidence_id="x"), item(evidence_id="y")]) == []


# ==========================================================================
# economic events
# ==========================================================================


@pytest.mark.parametrize(
    "field", ["event_id", "name", "authority", "timezone_note"]
)
def test_event_required_fields_refused(field: str) -> None:
    defaults = {
        "event_id": "e", "name": "n", "authority": "a",
        "kind": EventKind.SCHEDULED, "scheduled_at": NOW,
        "retrieved_at": NOW, "timezone_note": "UTC",
    }
    with pytest.raises(EvidenceError, match=field):
        EconomicEvent(**{**defaults, field: ""})  # type: ignore[arg-type]


def test_event_kind_must_be_enum() -> None:
    with pytest.raises(EvidenceError, match="EventKind"):
        event(kind="scheduled")


def test_scheduled_event_occurred_after_its_time() -> None:
    assert event(scheduled_at=NOW - timedelta(hours=1)).has_occurred is True


def test_scheduled_event_not_yet_occurred() -> None:
    assert event(scheduled_at=NOW + timedelta(hours=1)).has_occurred is False


def test_unscheduled_event_has_no_scheduled_time() -> None:
    """An unscheduled event has no announced time; recording one would invent it."""

    with pytest.raises(EvidenceError, match="must not carry scheduled_at"):
        event(kind=EventKind.UNSCHEDULED, scheduled_at=NOW)


def test_unscheduled_event_never_occurred() -> None:
    assert event(kind=EventKind.UNSCHEDULED, scheduled_at=None).has_occurred is False


def test_values_require_a_source() -> None:
    """A number with no stated provenance is not evidence."""

    with pytest.raises(EvidenceError, match="values_source"):
        event(actual=3.1, values_source=None)


def test_forecast_without_actual_is_permitted() -> None:
    """A release can be scheduled and known in advance without having happened."""

    record = event(actual=None, forecast=3.0, values_source="BLS calendar")
    assert record.actual is None
    assert record.has_occurred is True


def test_actual_omitted_is_never_invented() -> None:
    record = event(actual=None, values_source="BLS calendar")
    assert record.as_record()["actual"] is None


def test_cancellation_requires_a_note() -> None:
    with pytest.raises(EvidenceError, match="postponement_note"):
        event(cancelled=True)


def test_cancellation_with_note_permitted() -> None:
    record = event(cancelled=True, postponement_note="Deferred by the authority.")
    assert record.has_occurred is False


def test_revision_requires_a_note() -> None:
    with pytest.raises(EvidenceError, match="revision_note"):
        event(revised=True)


def test_revision_with_note_permitted() -> None:
    record = event(revised=True, revision_note="Annual revision published.")
    assert record.as_record()["revised"] is True


def test_previous_value_optional() -> None:
    assert event(previous=None).as_record()["previous"] is None


def test_naive_event_timestamp_refused() -> None:
    with pytest.raises(EvidenceError, match="timezone-aware"):
        event(scheduled_at=datetime(2026, 10, 9, 8, 30))


def test_event_values_not_inferred_from_headline() -> None:
    """The schema has no free-text field from which a value could be parsed."""

    record = event(name="CPI came in at 3.1 percent", values_source="BLS release")
    assert record.as_record()["actual"] is None


# ==========================================================================
# sentiment limits
# ==========================================================================


def observation(**overrides: object) -> SentimentObservation:
    fields: dict[str, object] = {
        "observation_id": "s1",
        "instrument_id": "BTC/USDT",
        "source_name": "Example Index",
        "observed_at": NOW - timedelta(hours=1),
        "retrieved_at": NOW,
        "value": 62.0,
        "scale_min": 0.0,
        "scale_max": 100.0,
        "methodology_note": "Published index; construction proprietary.",
    }
    fields.update(overrides)
    return SentimentObservation(**fields)  # type: ignore[arg-type]


def test_sentiment_requires_methodology() -> None:
    with pytest.raises(EvidenceError, match="methodology_note"):
        observation(methodology_note="")


def test_sentiment_value_must_lie_within_scale() -> None:
    with pytest.raises(EvidenceError, match="outside the declared scale"):
        observation(value=150.0)


def test_inverted_scale_refused() -> None:
    with pytest.raises(EvidenceError, match="scale_min"):
        observation(scale_min=100.0, scale_max=0.0)


def test_normalised_is_a_position_not_a_probability() -> None:
    value = observation(value=62.0).normalised
    assert 0.0 <= value <= 1.0
    assert value == pytest.approx(0.62)


def test_stale_sentiment_not_usable() -> None:
    assert observation(observed_at=NOW - timedelta(hours=72)).is_usable() is False


def test_future_sentiment_not_usable() -> None:
    assert observation(observed_at=NOW + timedelta(hours=1)).is_usable() is False


@pytest.mark.parametrize("field", FORBIDDEN_FORECAST_FIELDS)
def test_forecast_fields_refused(field: str) -> None:
    with pytest.raises(EvidenceError, match="as a forecast"):
        assert_not_a_forecast({field: 0.8})


def test_clean_sentiment_record_accepted() -> None:
    assert_not_a_forecast(observation().as_record())


def test_none_forecast_field_is_not_a_violation() -> None:
    assert_not_a_forecast({"probability": None, "expected_return": None})


def test_contrarian_index_flagged() -> None:
    record = observation(is_contrarian_index=True)
    assert record.as_record()["is_contrarian_index"] is True


# ==========================================================================
# records are serialisable and reversible
# ==========================================================================


def test_evidence_record_roundtrips_through_json() -> None:
    import json

    record = item()
    encoded = json.dumps(record.as_record())
    assert json.loads(encoded)["evidence_id"] == "e1"


def test_event_record_roundtrips_through_json() -> None:
    import json

    encoded = json.dumps(event(actual=3.1, forecast=3.0).as_record())
    assert json.loads(encoded)["actual"] == 3.1


def test_sentiment_record_roundtrips_through_json() -> None:
    import json

    encoded = json.dumps(observation().as_record())
    assert json.loads(encoded)["value"] == 62.0


def test_cluster_record_reports_independent_count() -> None:
    cluster = EvidenceCluster("c1", "e1", members=["e2", "e3"], conflicting_ids=["e9"])
    assert cluster.as_record()["independent_count"] == 2