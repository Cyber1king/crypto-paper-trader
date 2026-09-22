from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .data import load_ohlcv_csv
from .models import Candle


@dataclass(frozen=True)
class DatasetSummary:
    candles: int
    start: datetime
    end: datetime


def load_dataset(
    path: str | Path,
) -> tuple[list[Candle], DatasetSummary]:
    """Load an OHLCV CSV and return its candles with a summary."""

    candles = load_ohlcv_csv(path)

    summary = DatasetSummary(
        candles=len(candles),
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
    )

    return candles, summary


def validate_dataset(candles: Sequence[Candle]) -> None:
    """Validate that a dataset is usable for historical research."""

    if not candles:
        raise ValueError("dataset contains no candles")

    for candle in candles:
        if candle.high < candle.low:
            raise ValueError(
                "dataset contains an invalid high/low range"
            )

        if not (
            candle.low
            <= candle.open
            <= candle.high
        ):
            raise ValueError(
                "dataset contains an invalid open price"
            )

        if not (
            candle.low
            <= candle.close
            <= candle.high
        ):
            raise ValueError(
                "dataset contains an invalid close price"
            )

        if candle.volume < 0:
            raise ValueError(
                "dataset contains a negative volume"
            )

    for previous, current in zip(candles, candles[1:]):
        if current.timestamp <= previous.timestamp:
            raise ValueError(
                "dataset timestamps must be strictly increasing"
            )
