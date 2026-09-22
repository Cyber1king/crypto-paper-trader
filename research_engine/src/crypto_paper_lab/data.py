import csv
import os
from datetime import datetime
from pathlib import Path

from .models import Candle


def _parse_timestamp(value: str) -> datetime:
    """Parse timestamps used by supported OHLCV CSV formats."""

    value = value.strip()

    if "T" in value:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

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

        # Map lowercase names to the actual CSV column names.
        columns = {
            field.strip().lower(): field
            for field in reader.fieldnames
        }

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if "timestamp" in columns:
            timestamp_column = columns["timestamp"]
        elif "date" in columns:
            timestamp_column = columns["date"]
        else:
            raise ValueError(
                "CSV must contain a timestamp or date column"
            )

        if not required.issubset(columns):
            raise ValueError(
                "CSV must contain open, high, low, close, "
                "and volume columns"
            )

        for row in reader:
            candles.append(
                Candle(
                    timestamp=_parse_timestamp(
                        row[timestamp_column]
                    ),
                    open=float(row[columns["open"]]),
                    high=float(row[columns["high"]]),
                    low=float(row[columns["low"]]),
                    close=float(row[columns["close"]]),
                    volume=float(row[columns["volume"]]),
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
