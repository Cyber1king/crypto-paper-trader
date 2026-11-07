"""Forex market session validator.

Determines whether a given timestamp falls within Forex spot market open hours.

Forex spot market convention:
  - Open: Sunday 22:00 UTC to Friday 22:00 UTC
  - Closed: Friday 22:00 UTC to Sunday 22:00 UTC (weekend gap)
  - No session/holiday/DST validators are implemented for this release; this
    function provides a basic session check that can be extended later.

Design notes:
  - Timestamps are expected to be naive UTC or UTC-aware (converted to UTC).
  - The market week runs Sunday 22:00 UTC through Friday 22:00 UTC.
  - The "dead zone" Friday 22:00 UTC to Sunday 22:00 UTC is treated as closed.
  - This is a simple time-of-day check; future work may add holiday calendars.
"""


from __future__ import annotations

import datetime

_FX_HOLIDAYS = {
    (12, 25),  # Christmas Day
    (1, 1),    # New Year's Day
}


def _clamp_to_utc(dt: datetime.datetime) -> datetime.datetime:
    """Ensure the datetime is UTC-aware and return as naive UTC."""
    if dt.tzinfo is None:
        # Assume naive timestamps are already UTC
        return dt.replace(tzinfo=datetime.timezone.utc).replace(tzinfo=None)
    return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def is_forex_market_open(timestamp: datetime.datetime) -> bool:
    """Return True when the given timestamp falls within Forex market open hours.

    The Forex spot market is considered open:
      - From Sunday 22:00 UTC inclusive through Friday 22:00 UTC exclusive.
    The market is closed:
      - From Friday 22:00 UTC inclusive through Sunday 22:00 UTC exclusive
        (the weekend gap).

    Parameters
    ----------
    timestamp : datetime.datetime
        The timestamp to check. Should be in UTC or naive (assumed UTC).

    Returns
    -------
    bool
        True if the market is open at the given time, False otherwise.
    """
    ts = _clamp_to_utc(timestamp)

    if (ts.month, ts.day) in _FX_HOLIDAYS:
        return False

    # Use the original timestamp's weekday to avoid issues with UTC conversion
    # getting mangled. The day-of-week is invariant under UTC conversion.
    day_of_week = timestamp.weekday()  # Monday=0 ... Sunday=6
    hour = ts.hour
    minute = ts.minute

    # Friday 22:00 UTC marks the start of the weekend gap.
    # If it's Friday and hour>=22 (or hour==22 and minute>=0), market is closed.
    if day_of_week == 4 and hour >= 22:  # Friday = 4
        return False

    # Saturday is always part of the weekend gap.
    if day_of_week == 5:  # Saturday = 5
        return False

    # Sunday 22:00 UTC marks the end of the weekend gap and start of open.
    # If it's Sunday and hour<22, market is closed.
    if day_of_week == 6 and hour < 22:  # Sunday = 6
        return False

    # All other times are within the open window.
    return True
