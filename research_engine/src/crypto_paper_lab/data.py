import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import Candle


def _parse_timestamp(value: str) -> datetime:
    """Parse timestamps used by supported OHLCV CSV formats.

    All results are returned as **naive UTC**, which is the convention the rest
    of the engine assumes. Phase 41 added the normalisation because ``Z``-suffixed
    input previously produced a timezone-*aware* datetime while plain ISO input
    produced a naive one, so the same file could yield two incompatible types and
    comparison later raised ``TypeError`` instead of a clean refusal.

    Aware input is converted to UTC and stripped; naive input is accepted as
    already-UTC and left alone. Mixing the two forms within one file is now
    rejected by :func:`~crypto_paper_lab.dataset.validate_dataset` rather than
    crashing a comparison.
    """

    value = value.strip()

    if "T" in value:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    else:
        parsed = datetime.strptime(
            value,
            "%d-%m-%Y %H:%M",
        )

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


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
