import sys
sys.path.insert(0, r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src')
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.data import load_ohlcv_csv
from datetime import datetime
import pathlib

path = r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\USDJPY_1h_Cleaned.csv'
with open(path, 'r') as f:
    lines = f.readlines()

print("Last 20 data rows:")
for line in lines[-16:-1]:
    date_part = line.strip().split(',')[0]
    dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
    print(f'  {line.strip()} (weekday={dt.weekday()}, hour={dt.hour})')

print("\nFriday 21:00 and next:")
for i, line in enumerate(lines[1:], 1):
    date_part = line.strip().split(',')[0]
    try:
        dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
        if dt.weekday() == 4 and dt.hour == 21:
            for j in range(i-1, min(i+5, len(lines))):
                next_date = lines[j].strip().split(',')[0]
                next_dt = datetime.strptime(next_date, '%d-%m-%Y %H:%M') if j < len(lines) else None
                if next_dt:
                    print(f"  Friday 21:00 ({date_part}) -> next {next_dt.strftime('%A %H:%M')}: {lines[j].strip()}")
    except:
        pass

print("\nSunday rows:")
sundays = []
for line in lines[1:]:
    date_part = line.strip().split(',')[0]
    try:
        dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
        if dt.weekday() == 6:
            sundays.append(line.strip())
    except:
        pass
print(f'Sunday rows found: {len(sundays)}')
for s in sundays[:5]:
    print(f'  {s}')
PYEOF