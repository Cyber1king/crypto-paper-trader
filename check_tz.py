from datetime import datetime

# Check: what day is Oct 4, 2026?
dt = datetime.strptime('04-10-2026', '%d-%m-%Y')
print(f'Oct 4, 2026: weekday={dt.weekday()} (0=Mon, 6=Sun)')

dt = datetime.strptime('11-10-2026', '%d-%m-%Y')
print(f'Oct 11, 2026: weekday={dt.weekday()}')

dt = datetime.strptime('18-10-2026', '%d-%m-%Y')
print(f'Oct 18, 2026: weekday={dt.weekday()}')

# These are all Sundays. And the times are 23:00 in the CSV.
# The requirement says: "Sunday: KEEP hours 22:00 and 23:00 (market opens at 22:00 UTC)"
# 
# If CSV timestamps are in UTC:
#   - Sunday 22:00 UTC -> hour=22, kept ✓
#   - Sunday 23:00 UTC -> hour=23, kept ✓
#
# If CSV timestamps are in BST (UTC+1, summer):
#   - Sunday 22:00 BST = 21:00 UTC -> hour=21, filtered out ✗ (should be kept)
#   - Sunday 23:00 BST = 22:00 UTC -> hour=22, kept ✓
#
# The requirement says keep BOTH 22:00 and 23:00 on Sunday.
# So the CSV timestamps MUST be in UTC for the filter to work correctly.

# Let me verify by checking the actual data download
import yfinance as yf
data = yf.download('EURUSD=X', interval='1h', progress=False)
# The index timezone
print(f"\nyfinance index tz: {data.index.tz}")

# Convert a sample to UTC
sample = data.index[0]
print(f"Sample timestamp: {sample}")
sample_utc = sample.tz_convert('UTC')
print(f"UTC: {sample_utc}")

# Format as dd-mm-yyyy HH:MM
formatted = sample_utc.strftime('%d-%m-%Y %H:%M')
print(f"Formatted UTC: {formatted}")