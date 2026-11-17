import yfinance as yf
import pandas as pd
from datetime import datetime

# Download and process
data = yf.download('EURUSD=X', interval='1h', progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# Convert index to UTC and strip tz
data_index_utc = data.index.tz_convert('UTC').tz_localize(None)
data = data.copy()
data.index = data_index_utc

# Format timestamps
data['Date'] = data.index.strftime('%d-%m-%Y %H:%M')
data['Volume'] = 0

# Apply filter mask
def filter_mask(index):
    mask = pd.Series(True, index=index)
    for i, ts in enumerate(index):
        wd = ts.weekday()
        hh = ts.hour
        if wd == 6:  # Sunday
            if hh not in (22, 23):
                mask.iloc[i] = False
        elif wd == 5:  # Saturday
            mask.iloc[i] = False
        elif wd == 4:  # Friday
            if hh > 21:
                mask.iloc[i] = False
    return mask

mask = filter_mask(data.index)
filtered = data[mask]

print(f'Total rows: {len(data)}')
print(f'Filtered rows: {len(filtered)}')

# Count Sunday rows
sunday_count = 0
sunday_rows = []
for d in filtered['Date']:
    try:
        dt = datetime.strptime(d, '%d-%m-%Y %H:%M')
        if dt.weekday() == 6:  # Sunday
            sunday_count += 1
            sunday_rows.append(d)
    except:
        pass

print(f'Sunday rows in filtered data: {sunday_count}')
for s in sunday_rows[:10]:
    print(f'  {s}')