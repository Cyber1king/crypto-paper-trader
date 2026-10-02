"""Acquisition and validation of additional historical OHLCV data.

This module prepares genuinely unseen BTC/USDT hourly candles for
out-of-sample validation. It is deliberately strict: anything questionable
is reported and the dataset is **rejected**, never silently repaired.

Nothing here downloads data. A source file must be supplied by the operator.
The module never writes to the original 2024-2025 dataset; callers pass an
explicit output path and :func:`normalize_source` refuses to write inside the
protected research dataset.

Supported source layouts
------------------------
``binance_klines``
    Headerless CSV as published by data.binance.vision, e.g.::

        1735689600000000,4.15070000,4.15870000,4.15060000,4.15540000,539.23,...
        <open time>,<open>,<high>,<low>,<close>,<volume>,<close time>,...

    Open time is epoch seconds, milliseconds, microseconds or nanoseconds;
    the unit is detected from magnitude. Binance switched spot timestamps to
    **microseconds on 2025-01-01**, so unit detection is mandatory rather
    than optional.

``project_native``
    The layout used by ``data/BTCUSDT_1h_Cleaned (1).csv``::

        Date,Open,High,Low,Close,Volume
        01-01-2024 00:00,42314,42603.2,42289.6,42503.5,8459.477

``iso``
    Headered CSV with a ``timestamp``/``date`` column in ISO-8601.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

CANONICAL_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
CANONICAL_DATE_FORMAT = "%d-%m-%Y %H:%M"
HOUR = timedelta(hours=1)

#: Filename of the original 2024-2025 research dataset. Never written to.
PROTECTED_DATASET = "BTCUSDT_1h_Cleaned (1).csv"

#: Expected research window already used for strategy development.
RESEARCH_FIRST = datetime(2024, 1, 1, 0, 0)
RESEARCH_LAST = datetime(2025, 12, 31, 23, 0)


class AcquisitionError(RuntimeError):
    """Raised when a dataset cannot be accepted."""


# --------------------------------------------------------------------- rows


@dataclass(frozen=True)
class RawRow:
    line: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class AcquisitionReport:
    """Everything observed while validating one candidate source file."""

    source_path: str = ""
    source_format: str = ""
    rows_seen: int = 0
    rows_accepted: int = 0

    invalid_rows: list[tuple[int, str]] = field(default_factory=list)
    duplicate_timestamps: list[tuple[datetime, int]] = field(default_factory=list)
    out_of_order_rows: list[tuple[int, datetime]] = field(default_factory=list)
    missing_hours: list[tuple[datetime, datetime]] = field(default_factory=list)
    overlapping_rows: list[datetime] = field(default_factory=list)

    extra_columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    price_min: float | None = None
    price_max: float | None = None
    total_volume: float | None = None

    output_path: str | None = None
    output_sha256: str | None = None
    source_sha256: str | None = None

    @property
    def candle_count(self) -> int:
        return self.rows_accepted

    @property
    def is_clean(self) -> bool:
        return not (
            self.invalid_rows
            or self.duplicate_timestamps
            or self.out_of_order_rows
            or self.missing_hours
            or self.overlapping_rows
            or self.errors
        )

    @property
    def accepted(self) -> bool:
        """True only when the dataset is clean and therefore usable."""

        return self.is_clean and self.rows_accepted > 0

    @property
    def written(self) -> bool:
        """True when a canonical output file was actually produced."""

        return self.output_path is not None

    def summary_lines(self) -> list[str]:
        out = [
            f"source            : {self.source_path}",
            f"source sha256     : {self.source_sha256}",
            f"detected format   : {self.source_format}",
            f"rows seen         : {self.rows_seen}",
            f"rows accepted     : {self.rows_accepted}",
            f"first timestamp   : {self.first_timestamp}",
            f"last timestamp    : {self.last_timestamp}",
            f"candle count      : {self.candle_count}",
        ]
        if self.price_min is not None:
            out.append(f"price range       : {self.price_min} .. {self.price_max}")
        if self.total_volume is not None:
            out.append(f"total volume      : {self.total_volume}")
        out.append(f"invalid rows      : {len(self.invalid_rows)}")
        out.append(f"duplicate stamps  : {len(self.duplicate_timestamps)}")
        out.append(f"out-of-order rows : {len(self.out_of_order_rows)}")
        out.append(f"missing hours     : {len(self.missing_hours)}")
        out.append(f"overlapping rows  : {len(self.overlapping_rows)}")
        out.append(f"errors            : {len(self.errors)}")
        for message in self.errors:
            out.append(f"  error           : {message}")
        if self.extra_columns:
            out.append(f"extra columns     : {', '.join(self.extra_columns)}")
        for note in self.notes:
            out.append(f"note              : {note}")
        out.append(f"output written    : {self.written}")
        if self.output_path:
            out.append(f"output path       : {self.output_path}")
            out.append(f"output sha256     : {self.output_sha256}")
        out.append(f"VERDICT           : {'ACCEPTED' if self.accepted else 'REJECTED'}")
        return out


# --------------------------------------------------------------- utilities


def sha256_of(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def epoch_to_datetime(value: str) -> datetime:
    """Convert an epoch integer of unknown unit to a naive UTC datetime.

    Binance publishes spot timestamps in milliseconds before 2025-01-01 and
    in microseconds from 2025-01-01, so the unit must be inferred.
    """

    raw = int(str(value).strip())
    magnitude = abs(raw)
    if magnitude >= 10 ** 17:
        seconds, remainder = divmod(raw, 10 ** 9)
        micro = remainder // 1000
    elif magnitude >= 10 ** 14:
        seconds, micro = divmod(raw, 10 ** 6)
    elif magnitude >= 10 ** 11:
        seconds, millis = divmod(raw, 1000)
        micro = millis * 1000
    else:
        seconds, micro = raw, 0
    return datetime(1970, 1, 1) + timedelta(seconds=seconds, microseconds=micro)


def _normalise_header_cell(cell: str) -> str:
    return cell.strip().lower().replace(" ", "").replace("_", "")


def detect_format(path: str | Path) -> str:
    """Classify a source file as binance_klines, project_native or iso."""

    path = Path(path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        first = handle.readline()
    if not first.strip():
        raise AcquisitionError("source file is empty")

    raw_cells = next(csv.reader([first]))
    cells = [_normalise_header_cell(c) for c in raw_cells]
    if not cells or not cells[0]:
        raise AcquisitionError("source file has no columns")

    # Binance publishes klines both headerless and with a header row whose
    # first column is "Open time"; both layouts are accepted.
    if cells[0] in {"date", "timestamp", "datetime", "time"}:
        return "project_native" if cells[0] == "date" else "iso"
    if cells[0] in {"opentime", "time", "timestamp"}:
        return "binance_klines"
    if cells[0].lstrip("-").isdigit():
        return "binance_klines"

    raise AcquisitionError(
        f"unrecognised source layout; first line was: {first.strip()[:80]!r}"
    )


def _looks_like_header(cells: list[str]) -> bool:
    first = cells[0].strip() if cells else ""
    return bool(first) and not first.lstrip("-").isdigit()


def _parse_project_native_date(value: str) -> datetime:
    value = value.strip()
    for fmt in (CANONICAL_DATE_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognised timestamp {value!r}")


def _parse_iso_date(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(
        tzinfo=None
    )


def iter_rows(path: str | Path, source_format: str) -> Iterator[RawRow]:
    """Yield parsed rows. Raises on the first structurally broken record."""

    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header_offset = 0
        if source_format in {"project_native", "iso"}:
            next(reader)
            header_offset = 1
        else:
            # Peek at the first record without consuming it: headerless
            # Binance files must not lose their first data row.
            first = next(reader, None)
            if first is not None and _looks_like_header(first):
                header_offset = 1
            else:
                reader = itertools.chain([first], reader) if first else reader

        for index, cells in enumerate(reader, start=header_offset + 1):
            if not cells or all(not c.strip() for c in cells):
                continue

            if source_format == "binance_klines":
                if len(cells) < 6:
                    raise ValueError(
                        f"expected at least 6 columns, found {len(cells)}"
                    )
                stamp = epoch_to_datetime(cells[0])
                values = [float(c) for c in cells[1:6]]
            else:
                stamp = (
                    _parse_project_native_date(cells[0])
                    if source_format == "project_native"
                    else _parse_iso_date(cells[0])
                )
                if len(cells) < 6:
                    raise ValueError(
                        f"expected at least 6 columns, found {len(cells)}"
                    )
                values = [float(c) for c in cells[1:6]]

            yield RawRow(index, stamp, *values)


def _check_row(row: RawRow) -> str | None:
    """Return a rejection reason, or None when the row is acceptable."""

    if row.timestamp.minute or row.timestamp.second or row.timestamp.microsecond:
        return f"timestamp {row.timestamp} is not aligned to a whole hour"
    if min(row.open, row.high, row.low, row.close) <= 0:
        return "non-positive price"
    if row.high < row.low:
        return "high is below low"
    if not (row.low <= row.open <= row.high):
        return "open outside the low-high range"
    if not (row.low <= row.close <= row.high):
        return "close outside the low-high range"
    if row.volume < 0:
        return "negative volume"
    return None


def normalize_source(
    source_path: str | Path,
    output_path: str | Path,
    strict: bool = True,
    allow_overlap_with_research: bool = False,
) -> AcquisitionReport:
    """Validate a source OHLCV file and, only if clean, write canonical CSV.

    The canonical layout matches the existing research dataset exactly:
    ``Date,Open,High,Low,Close,Volume`` with ``dd-mm-yyyy HH:MM`` stamps.

    ``strict=True`` (the default) means a single invalid row, duplicate,
    out-of-order stamp, missing hour or research-window overlap causes the
    dataset to be rejected and **no output file is written**.

    The source file is opened read-only and is never modified. Writing to the
    protected research dataset is refused.
    """

    source_path = Path(source_path)
    output_path = Path(output_path)

    if output_path.name == PROTECTED_DATASET:
        raise AcquisitionError(
            f"refusing to write to the protected dataset {PROTECTED_DATASET!r}"
        )
    if output_path.resolve() == source_path.resolve():
        raise AcquisitionError("output path must differ from the source path")

    report = AcquisitionReport(
        source_path=str(source_path),
        source_sha256=sha256_of(source_path),
    )

    try:
        report.source_format = detect_format(source_path)
    except AcquisitionError as exc:
        report.errors.append(str(exc))
        return report

    rows: list[RawRow] = []
    with source_path.open("r", newline="", encoding="utf-8") as handle:
        first_line = handle.readline()
    header = [c.strip() for c in next(csv.reader([first_line]))]
    if len(header) > 6 and not header[0].lstrip("-").isdigit():
        report.extra_columns = header[6:]

    try:
        for row in iter_rows(source_path, report.source_format):
            report.rows_seen += 1
            reason = _check_row(row)
            if reason is not None:
                report.invalid_rows.append((row.line, reason))
                continue
            rows.append(row)
    except (ValueError, AcquisitionError) as exc:
        report.errors.append(f"structural parse failure: {exc}")

    # duplicates
    counts = Counter(r.timestamp for r in rows)
    for stamp, count in sorted(counts.items()):
        if count > 1:
            report.duplicate_timestamps.append((stamp, count))
    if report.duplicate_timestamps:
        rows = [r for r in rows if counts[r.timestamp] == 1]

    # ordering
    for previous, current in zip(rows, rows[1:]):
        if current.timestamp <= previous.timestamp:
            report.out_of_order_rows.append((current.line, current.timestamp))

    if report.out_of_order_rows:
        rows.sort(key=lambda r: (r.timestamp, r.line))

    # missing hourly intervals
    for previous, current in zip(rows, rows[1:]):
        gap = current.timestamp - previous.timestamp
        if gap != HOUR:
            report.missing_hours.append((previous.timestamp, current.timestamp))

    # overlap with the already-researched window
    if not allow_overlap_with_research:
        for row in rows:
            if RESEARCH_FIRST <= row.timestamp <= RESEARCH_LAST:
                report.overlapping_rows.append(row.timestamp)

    report.rows_accepted = len(rows)
    if rows:
        report.first_timestamp = rows[0].timestamp
        report.last_timestamp = rows[-1].timestamp
        report.price_min = min(r.low for r in rows)
        report.price_max = max(r.high for r in rows)
        report.total_volume = round(sum(r.volume for r in rows), 8)

    if report.source_format == "binance_klines" and rows:
        report.notes.append(
            "binance spot timestamps are microseconds from 2025-01-01 and "
            "milliseconds before; epoch units were inferred per row"
        )

    blocking = (
        report.invalid_rows
        or report.duplicate_timestamps
        or report.out_of_order_rows
        or report.missing_hours
        or report.overlapping_rows
        or report.errors
    )
    if blocking and strict:
        report.notes.append("strict mode: nothing written because issues exist")
        return report

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CANONICAL_COLUMNS)
        for row in rows:
            writer.writerow([
                row.timestamp.strftime(CANONICAL_DATE_FORMAT),
                row.open,
                row.high,
                row.low,
                row.close,
                row.volume,
            ])

    report.output_path = str(output_path)
    report.output_sha256 = sha256_of(output_path)
    return report


def write_report(report: AcquisitionReport, path: str | Path) -> None:
    """Persist a human-readable acquisition report."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ACQUISITION REPORT", "=" * 78, ""]
    lines.extend(report.summary_lines())
    lines.append("")

    def dump(title: str, items: Iterable, limit: int = 20) -> None:
        items = list(items)
        lines.append(f"{title} ({len(items)})")
        lines.append("-" * 78)
        if not items:
            lines.append("  none")
        for item in items[:limit]:
            lines.append(f"  {item}")
        if len(items) > limit:
            lines.append(f"  ... and {len(items) - limit} more")
        lines.append("")

    dump("INVALID ROWS (line, reason)", report.invalid_rows)
    dump(
        "DUPLICATE TIMESTAMPS (timestamp, count)",
        report.duplicate_timestamps,
    )
    dump(
        "OUT-OF-ORDER ROWS (line, timestamp)",
        report.out_of_order_rows,
    )
    dump(
        "MISSING HOURLY INTERVALS (previous, next)",
        report.missing_hours,
    )
    dump("OVERLAPPING WITH 2024-2025 RESEARCH", report.overlapping_rows)
    dump("ERRORS", report.errors)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
