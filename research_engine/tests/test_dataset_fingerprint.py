"""Content-based dataset identity.

``dataset_fingerprint`` previously returned ``(count, first, last)``. Two
different series of the same length and endpoints produced the same value, so any
interior mutation -- a changed price, a swapped block -- was invisible.

These tests pin the contract that replaces it.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.models import Candle
from crypto_paper_lab.walkforward import (
    DATASET_FINGERPRINT_SCHEMA_VERSION,
    DatasetContentIdentity,
    DatasetContentIdentityError,
    dataset_fingerprint,
)


BASE = datetime(2024, 1, 1, 0, 0)


def _series(n: int = 6, base: datetime = BASE, close: float = 100.0):
    return [
        Candle(
            timestamp=base + timedelta(hours=i),
            open=close + i,
            high=close + i + 1,
            low=close + i - 1,
            close=close + i + 0.5,
            volume=10.0 + i,
        )
        for i in range(n)
    ]


def _mutate(values, index: int, *, close_delta: float = 0.01):
    """Return a copy with one interior value altered."""
    out = list(values)
    c = out[index]
    out[index] = Candle(
        timestamp=c.timestamp,
        open=c.open,
        high=c.high,
        low=c.low,
        close=c.close + close_delta,
        volume=c.volume,
    )
    return out


# 1. determinism
def test_identical_datasets_produce_identical_digests():
    assert dataset_fingerprint(_series()).content_sha256 == (
        dataset_fingerprint(_series()).content_sha256
    )


def test_identity_is_stable_across_equal_but_distinct_objects():
    a = dataset_fingerprint(_series())
    b = dataset_fingerprint([Candle(**vars(c)) for c in _series()])
    assert a == b


# 2. interior value mutation
def test_interior_value_mutation_changes_the_digest():
    base = _series()
    mutated = _mutate(base, 3)
    assert len(base) == len(mutated)
    assert base[0].timestamp == mutated[0].timestamp
    assert base[-1].timestamp == mutated[-1].timestamp
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(mutated).content_sha256
    )


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
def test_every_field_participates_in_the_digest(field: str):
    base = _series()
    c = base[2]
    altered = Candle(**{**vars(c), field: float(getattr(c, field)) + 0.125})
    changed = list(base)
    changed[2] = altered
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(changed).content_sha256
    )


def test_first_and_last_only_mutation_also_changes_the_digest():
    base = _series()
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(_mutate(base, 0)).content_sha256
    )
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(_mutate(base, len(base) - 1)).content_sha256
    )


# 3. interior row substitution, same count and endpoints
def test_interior_row_substitution_same_shape_changes_digest():
    base = _series(6)
    substituted = list(base)
    donor = _series(6, base=BASE + timedelta(days=400))
    substituted[3] = donor[3]
    assert len(substituted) == len(base)
    assert substituted[0].timestamp == base[0].timestamp
    assert substituted[-1].timestamp == base[-1].timestamp
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(substituted).content_sha256
    )


# 4. ordering
def test_row_reordering_changes_the_digest():
    base = _series()
    reversed_series = list(reversed(base))
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(reversed_series).content_sha256
    )


def test_swap_of_two_interior_rows_changes_the_digest():
    base = _series()
    swapped = list(base)
    swapped[1], swapped[4] = swapped[4], swapped[1]
    assert dataset_fingerprint(base).content_sha256 != (
        dataset_fingerprint(swapped).content_sha256
    )


# 5. version contract
def test_schema_version_is_recorded():
    identity = dataset_fingerprint(_series())
    assert identity.schema_version == DATASET_FINGERPRINT_SCHEMA_VERSION


def test_the_schema_version_actually_participates_in_the_digest(monkeypatch):
    """Changing the version must change the digest, not just the label.

    Previously this assertion was written as ``... or True``, which passed no
    matter what the digest was. It now proves the version is hashed.
    """

    import crypto_paper_lab.walkforward as wf

    baseline = dataset_fingerprint(_series()).content_sha256

    monkeypatch.setattr(
        wf, "DATASET_FINGERPRINT_SCHEMA_VERSION", "candle-series-sha256/999"
    )
    rebased = dataset_fingerprint(_series())

    assert rebased.schema_version == "candle-series-sha256/999"
    assert rebased.content_sha256 != baseline


def test_the_canonical_form_is_reproducible_from_the_documented_layout():
    """Re-derive the digest by hand from the documented canonical form.

    This is the test that makes the docstring a contract rather than a
    description: if the encoding changes and the docstring is not updated with
    it, this fails.
    """

    import hashlib
    import struct

    candles = _series(3)
    digest = hashlib.sha256()
    digest.update(DATASET_FINGERPRINT_SCHEMA_VERSION.encode("ascii"))
    digest.update(b"\n")
    for candle in candles:
        digest.update(candle.timestamp.isoformat().encode("utf-8"))
        digest.update(b"|")
        digest.update(
            struct.pack(
                "<5d",
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
        )
        digest.update(b"\n")

    assert dataset_fingerprint(candles).content_sha256 == digest.hexdigest()


def test_two_different_schema_versions_are_never_interchangeable():
    """A format change must not yield identities that look comparable."""
    base = dataset_fingerprint(_series())
    other = DatasetContentIdentity(
        schema_version="candle-series-sha256/999",
        count=base.count,
        first=base.first,
        last=base.last,
        content_sha256=base.content_sha256,
    )
    assert other.schema_version != base.schema_version
    assert other != base


def test_identity_is_immutable():
    identity = dataset_fingerprint(_series())
    with pytest.raises(Exception):
        identity.count = 99  # type: ignore[misc]


# 6. invalid content
def test_nan_is_rejected():
    base = _series()
    c = base[2]
    broken = list(base)
    broken[2] = Candle(**{**vars(c), "close": math.nan})
    with pytest.raises(DatasetContentIdentityError, match="NaN"):
        dataset_fingerprint(broken)


@pytest.mark.parametrize("bad", [math.inf, -math.inf])
def test_infinities_are_rejected(bad: float):
    base = _series()
    c = base[1]
    broken = list(base)
    broken[1] = Candle(**{**vars(c), "open": bad})
    with pytest.raises(DatasetContentIdentityError, match="infinite"):
        dataset_fingerprint(broken)


def test_non_datetime_timestamp_is_rejected():
    base = _series()
    c = base[1]
    broken = list(base)
    object.__setattr__(broken[1], "timestamp", "2024-01-01")
    with pytest.raises(DatasetContentIdentityError, match="non-datetime"):
        dataset_fingerprint(broken)


# 7. empty series
def test_empty_series_is_described_not_faked():
    identity = dataset_fingerprint([])
    assert identity.count == 0
    assert identity.first is None
    assert identity.last is None
    assert len(identity.content_sha256) == 64


# 8. timezone awareness is distinguished, not normalised away
def test_naive_and_aware_timestamps_digest_differently():
    naive = _series()
    aware = [
        Candle(**{**vars(c), "timestamp": c.timestamp.replace(tzinfo=timezone.utc)})
        for c in naive
    ]
    assert dataset_fingerprint(naive).content_sha256 != (
        dataset_fingerprint(aware).content_sha256
    )


# 9. shape fields remain available for cheap checks
def test_count_and_bounds_are_reported():
    identity = dataset_fingerprint(_series(4))
    assert identity.count == 4
    assert identity.first == BASE
    assert identity.last == BASE + timedelta(hours=3)
    assert len(identity.short()) > 0

# 10. non-numeric fields are refused, not coerced or crashed on
def test_a_non_numeric_field_is_refused_with_the_documented_error():
    base = _series()
    c = base[1]
    broken = list(base)
    broken[1] = Candle(**{**vars(c), "close": "not-a-number"})
    with pytest.raises(DatasetContentIdentityError, match="not a real number"):
        dataset_fingerprint(broken)


def test_a_none_field_is_refused_with_the_documented_error():
    base = _series()
    c = base[1]
    broken = list(base)
    broken[1] = Candle(**{**vars(c), "open": None})
    with pytest.raises(DatasetContentIdentityError, match="not a real number"):
        dataset_fingerprint(broken)


def test_an_int_valued_field_hashes_the_same_as_its_float_equivalent():
    """Ints are exact in binary64, so 3 and 3.0 are the same market value."""

    base = _series()
    as_int = list(base)
    c = base[2]
    as_int[2] = Candle(**{**vars(c), "volume": int(c.volume)})
    as_float = list(base)
    as_float[2] = Candle(**{**vars(c), "volume": float(c.volume)})

    assert (
        dataset_fingerprint(as_int).content_sha256
        == dataset_fingerprint(as_float).content_sha256
    )


def test_validated_and_hashed_values_are_the_same_values(monkeypatch):
    """A Decimal must hash as its float value, not blow up in struct.pack.

    Regression guard for a real inconsistency: the finiteness check converted
    with ``float()`` while the packing used the raw field, so what was
    validated and what was hashed could differ.
    """

    from decimal import Decimal

    base = _series()
    c = base[2]
    with_decimal = list(base)
    with_decimal[2] = Candle(**{**vars(c), "close": Decimal(str(c.close))})

    assert (
        dataset_fingerprint(with_decimal).content_sha256
        == dataset_fingerprint(base).content_sha256
    )
