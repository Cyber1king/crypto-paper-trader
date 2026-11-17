from datetime import datetime

path = r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\EURUSD_1h_Cleaned.csv'
with open(path, 'r') as f:
    lines = f.readlines()

# Print last 15 data rows
print("Last 15 data rows:")
for line in lines[-16:-1]:
    date_part = line.strip().split(',')[0]
    dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
    print(f'  {line.strip()} (weekday={dt.weekday()}, hour={dt.hour})')

# Find Sunday rows
print("\nSunday rows:")
for line in lines[1:]:
    date_part = line.strip().split(',')[0]
    try:
        dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
        if dt.weekday() == 6:
            print(f'  Sunday: {line.strip()}')
    except:
        pass

# Find Friday 21:00 and what follows
print("\nFriday 21:00 and next candles:")
for i, line in enumerate(lines[1:], 1):
    date_part = line.strip().split(',')[0]
    try:
        dt = datetime.strptime(date_part, '%d-%m-%Y %H:%M')
        if dt.weekday() == 4 and dt.hour == 21:  # Friday 21:00
            # Print this and next 3 lines
            for j in range(i-1, min(i+4, len(lines))):
                next_date = lines[j].strip().split(',')[0]
                next_dt = datetime.strptime(next_date, '%d-%m-%Y %H:%M') if j < len(lines) else None
                if next_dt:
                    day_name = next_dt.strftime('%A')
                    print(f"  Friday 21:00 ({date_part}) -> next {day_name} {next_date}: {lines[j].strip()}")
    except:
        pass
PYEOF