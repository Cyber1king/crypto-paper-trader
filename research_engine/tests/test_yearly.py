from datetime import datetime, timezone

from crypto_paper_lab.models import Candle
from crypto_paper_lab.yearly import split_by_year


def candle(year: int, hour: int) -> Candle:
    return Candle(
        timestamp=datetime(
            year,
            1,
            1,
            hour,
            tzinfo=timezone.utc,
        ),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1000.0,
    )


def test_split_by_year() -> None:
    candles = [
        candle(2024, 0),
        candle(2024, 1),
        candle(2025, 0),
    ]

    result = split_by_year(candles)

    assert list(result.keys()) == [2024, 2025]
    assert len(result[2024]) == 2
    assert len(result[2025]) == 1
