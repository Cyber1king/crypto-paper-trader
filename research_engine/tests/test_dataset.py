from datetime import datetime, timezone

import pytest

from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.models import Candle


def candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100,
        high=105,
        low=95,
        close=102,
        volume=10,
    )


def test_valid_dataset_passes() -> None:
    candles = [
        candle(datetime(2026, 1, 1, 0, tzinfo=timezone.utc)),
        candle(datetime(2026, 1, 1, 1, tzinfo=timezone.utc)),
        candle(datetime(2026, 1, 1, 2, tzinfo=timezone.utc)),
    ]

    validate_dataset(candles)


def test_duplicate_timestamps_are_rejected() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    candles = [
        candle(timestamp),
        candle(timestamp),
    ]

    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        validate_dataset(candles)


def test_invalid_high_low_is_rejected() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    invalid = Candle(
        timestamp=timestamp,
        open=100,
        high=90,
        low=95,
        close=92,
        volume=10,
    )

    with pytest.raises(
        ValueError,
        match="high/low",
    ):
        validate_dataset([invalid])
