import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

# Download EURUSD
data = yf.download('EURUSD=X', interval='1h', progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# Convert index to UTC and strip tz
data_index_utc = data.index.tz_convert('UTC').tz_localize(None)
data = data.copy()
data.index = data_index_utc

# Format Date column
data['Date'] = data.index.strftime('%d-%m-%Y %H:%M')
data['Volume'] = 0

# Desired columns
desired = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
data = data[[c for c in desired if c in data.columns]]

# Apply weekend filter: keep only rows within Forex market hours
# Sunday: 22:00 and 23:00 only
# Mon-Thu: all hours
# Friday: 00:00 through 21:00 only
# Saturday: remove all

kept = []
for ts in data.index:
    hh = ts.hour
    wd = ts.weekday()
    if wd == 6:  # Sunday
        if hh in (22, 23):
            kept.append(True)
        else:
            kept.append(False)
    elif wd == 5:  # Saturday
        kept.append(False)
    elif wd == 4:  # Friday
        if hh <= 21:
            kept.append(True)
        else:
            kept.append(False)
    else:  # Mon-Thu
        kept.append(True)

mask = pd.Series(kept, index=data.index)
filtered = data[mask]

print(f'Original rows: {len(data)}')
print(f'Filtered rows: {len(filtered)}')

# Count by weekday
for wd in range(7):
    wd_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][wd]
    count = sum(1 for d in filtered['Date'] if datetime.strptime(d, '%d-%m-%Y %H:%M').weekday() == wd)
    print(f'  {wd_name}: {count}')

# Now validate
from crypto_paper_lab.dataset import validate_dataset
try:
    validate_dataset(filtered, expected_interval_seconds=3600, market_type='forex_spot')
    print('VALIDATION: PASSED')
except ValueError as e:
    print(f'VALIDATION: FAILED - {str(e)[:80]}')
PYEOF