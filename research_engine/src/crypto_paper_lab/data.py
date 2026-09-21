import csv
import os
from datetime import datetime
from pathlib import Path

from .models import Candle


REQUIRED_COLUMNS = {
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def load_ohlcv_csv(path: str | Path) -> list[Candle]:
    """Load and validate OHLCV candles from a CSV file."""

    candles: list[Candle] = []

    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header")

        columns = set(reader.fieldnames)

        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}"
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                timestamp = datetime.fromisoformat(
                    row["timestamp"].replace("Z", "+00:00")
                )

                open_price = float(row["open"])
                high_price = float(row["high"])
                low_price = float(row["low"])
                close_price = float(row["close"])
                volume = float(row["volume"])

            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(
                    f"Invalid data on CSV row {row_number}"
                ) from exc

            if (
                open_price <= 0
                or high_price <= 0
                or low_price <= 0
                or close_price <= 0
                or volume < 0
            ):
                raise ValueError(
                    f"Invalid price or volume on CSV row {row_number}"
                )

            if high_price < low_price:
                raise ValueError(
                    f"High price is below low price on row {row_number}"
                )

            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                )
            )

    if not candles:
        raise ValueError("OHLCV file contains no candles")

    timestamps = [candle.timestamp for candle in candles]

    if len(timestamps) != len(set(timestamps)):
        raise ValueError("OHLCV file contains duplicate timestamps")

    if timestamps != sorted(timestamps):
        raise ValueError("OHLCV candles must be in chronological order")

    return candles


def optional_market_data_key() -> str | None:
    """Read an optional public-data API key without exposing it."""

    return os.getenv("MARKET_DATA_API_KEY") or None
