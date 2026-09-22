import csv
import os
from datetime import datetime
from pathlib import Path

from .models import Candle


def _parse_timestamp(value: str) -> datetime:
    """Parse timestamps used by supported OHLCV CSV formats."""

    value = value.strip()

    # ISO format, e.g. 2024-01-01T00:00:00Z
    if "T" in value:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    # Dataset format, e.g. 01-01-2024 00:00
    return datetime.strptime(
        value,
        "%d-%m-%Y %H:%M",
    )


def load_ohlcv_csv(path: str | Path) -> list[Candle]:
    """Load OHLCV candles from a CSV file."""

    candles: list[Candle] = []

    with Path(path).open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("OHLCV file has no header")

        fields = {
            field.strip().lower()
            for field in reader.fieldnames
        }

        required = {
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        required_timestamp = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if required_timestamp.issubset(fields):
            timestamp_column = "timestamp"
        elif required.issubset(fields):
            timestamp_column = "date"
        else:
            raise ValueError(
                "CSV must contain timestamp/date, open, high, "
                "low, close, and volume columns"
            )

        for row in reader:
            candles.append(
                Candle(
                    timestamp=_parse_timestamp(
                        row[timestamp_column]
                    ),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )

    if not candles:
        raise ValueError(
            "OHLCV file contains no candles"
        )

    return candles


def optional_market_data_key() -> str | None:
    """Read an optional public-data API key."""

    return os.getenv("MARKET_DATA_API_KEY") or None
