import csv
import os
from datetime import datetime
from pathlib import Path

from .models import Candle


def load_ohlcv_csv(path: str | Path) -> list[Candle]:
    """Load timestamp, open, high, low, close, volume columns from CSV."""
    candles: list[Candle] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            candles.append(
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    if not candles:
        raise ValueError("OHLCV file contains no candles")
    return candles


def optional_market_data_key() -> str | None:
    """Read an optional public-data API key without logging or exposing it."""
    return os.getenv("MARKET_DATA_API_KEY") or None
