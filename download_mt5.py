import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os

# We do NOT use path= here. We attach to the running, logged-in terminal.
if not mt5.initialize():
    print("Failed to connect. Make sure MT5 is open and logged in.")
    quit()

print("Connected to account:", mt5.account_info().login)

# We want 1 year of data (approx 12 months back from today)
now = datetime.now()
utc_from = now.replace(year=now.year - 1)

symbols = ["EURUSD", "GBPUSD"]
data_dir = r"C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data"
os.makedirs(data_dir, exist_ok=True)

for symbol in symbols:
    print(f"\nDownloading 1 year of H1 data for {symbol}...")
    
    # Get rates
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, utc_from, now)
    
    if rates is None or len(rates) == 0:
        print(f"  Failed to get data for {symbol}. Error:", mt5.last_error())
        continue
        
    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Format exactly as the engine expects: dd-mm-yyyy HH:MM
    df['Date'] = df['time'].dt.strftime('%d-%m-%Y %H:%M')
    
    # MT5 gives tick_volume, but our engine expects volume. We use 0 to match Yahoo format.
    df['Volume'] = 0
    
    # Rename columns to match engine: Date, Open, High, Low, Close, Volume
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close'
    })
    
    # Select only the required columns
    df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # Save
    out_path = os.path.join(data_dir, f"{symbol}_1h_Cleaned.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    print(f"  First row: {df.iloc[0]['Date']}")
    print(f"  Last row:  {df.iloc[-1]['Date']}")

mt5.shutdown()
print("\nAll done.")
