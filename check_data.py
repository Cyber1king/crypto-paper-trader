from datetime import datetime
import os

path = r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\EURUSD_1h_Cleaned.csv'
with open(path, 'r') as f:
    lines = f.readlines()

# Print last 10 data rows
print("Last 10 data rows:")
for line in lines[-11:-1]:
    date_part = line.strip().split(',')[0]
    dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
    print(f'  {line.strip()} (weekday={dt.weekday()})')

# Check for Sunday rows
print("\nSunday rows (weekday=6):")
sundays = []
for line in lines[1:]:
    date_part = line.strip().split(',')[0]
    try:
        dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
        if dt.weekday() == 6:
            sundays.append(line.strip())
    except:
        pass
print(f'Total Sunday rows: {len(sundays)}')
for s in sundays[:10]:
    print(f'  {s}')

# Check the last few non-Sunday rows
print("\nLast few non-Sunday rows:")
count = 0
for line in lines[-1:-11:-1]:
    date_part = line.strip().split(',')[0]
    dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
    print(f'  {line.strip()} (weekday={dt.weekday()})')
    count += 1
    if count >= 5:
        break

# Check the pair before the end
print(f"\nLast 3 rows:")
for line in lines[-3:]:
    date_part = line.strip().split(',')[0]
    dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
    print(f'  {line.strip()} (weekday={dt.weekday()})')
PYEOF