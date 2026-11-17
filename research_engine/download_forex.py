#!/usr/bin/env python3
"""Download and clean Forex data from Yahoo Finance with strict weekend filtering.

Applies a strict Forex week filter using Python's datetime.weekday():
  Mon=0 .. Thu=3: keep all hours (0-23)
  Fri=4:          keep hours 0-21 only
  Sat=5:          keep nothing
  Sun=6:          keep nothing

This ensures every CSV has uniform 1-hour intervals compatible with
validate_dataset(expected_interval_seconds=3600, market_type='forex_spot').
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import os


def is_kept_by_forex_filter(dt):
    """Return True if a UTC datetime passes the strict Forex week filter.
    
    Rules:
      - Monday through Thursday (weekday 0-3): keep all hours
      - Friday (weekday 4): keep hours 0-21 only (market closes 22:00 UTC)
      - Saturday (weekday 5): keep nothing
      - Sunday (weekday 6): keep nothing
    """
    wd = dt.weekday()   # Mon=0 .. Sun=6
    hh = dt.hour
    
    if wd <= 3:       # Monday-Thursday
        return True
    elif wd == 4:     # Friday
        return hh <= 21
    else:             # Saturday or Sunday
        return False


def download_pair(ticker, output_path):
    """Download 1h data from Yahoo Finance and apply strict Forex week filter."""
    print(f"Downloading {ticker}...")
    
    # Download 1-hour data
    data = yf.download(ticker, interval="1h", progress=False)
    if data.empty:
        print(f"  WARNING: No data downloaded for {ticker}")
        return False
    
    # yfinance returns DataFrame with DatetimeIndex (Europe/London timezone)
    # Convert index to UTC and strip tz info
    data_index_utc = data.index.tz_convert('UTC').tz_localize(None)
    data = data.copy()
    data.index = data_index_utc
    
    # Format timestamps as dd-mm-yyyy HH:MM (in UTC)
    data['Date'] = data.index.strftime('%d-%m-%Y %H:%M')
    
    # Set Volume = 0 for forex spot
    data['Volume'] = 0
    
    # Ensure we have OHLC columns with correct names
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Apply strict Forex week filter
    mask = pd.Series(
        [is_kept_by_forex_filter(ts) for ts in data.index],
        index=data.index
    )
    data = data[mask]
    
    # Sort ascending by timestamp
    data = data.sort_index()
    
    # Desired column order: Date, Open, High, Low, Close, Volume
    desired = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    # Rebuild DataFrame with only desired columns in order
    data = data[[c for c in desired if c in data.columns]]
    
    # Save to CSV (without index)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    data.to_csv(output_path, index=False)
    print(f"  Saved {len(data)} rows to {output_path}")
    
    # Count rows per weekday
    weekday_counts = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    counts = {name: 0 for name in weekday_counts.values()}
    for d in data['Date']:
        try:
            dt = datetime.strptime(d, '%d-%m-%Y %H:%M')
            counts[weekday_counts[dt.weekday()]] += 1
        except:
            pass
    
    print(f"  Weekday counts: Mon={counts['Mon']}, Tue={counts['Tue']}, Wed={counts['Wed']}, "
          f"Thu={counts['Thu']}, Fri={counts['Fri']}, Sat={counts['Sat']}, Sun={counts['Sun']}")
    
    # Print first 2 and last 2 rows (verbatim)
    lines = data.to_csv(index=False).strip().split('\\n')
    print(f"  First 2 rows:")
    for line in lines[1:3]:
        print(f"    {line}")
    print(f"  Last 2 rows:")
    for line in lines[-3:-1]:
        print(f"    {line}")
    
    return True


if __name__ == "__main__":
    pairs = [
        ("EURUSD=X", "data/EURUSD_1h_Cleaned.csv"),
        ("GBPUSD=X", "data/GBPUSD_1h_Cleaned.csv"),
        ("JPY=X", "data/USDJPY_1h_Cleaned.csv"),
    ]
    
    for ticker, path in pairs:
        success = download_pair(ticker, path)
        if not success:
            print(f"  FAILED to download {ticker}")