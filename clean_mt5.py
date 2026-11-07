import pandas as pd
import sys
from crypto_paper_lab.forex_session import is_forex_market_open

def clean_csv(path):
    print(f"Cleaning {path}...")
    df = pd.read_csv(path)
    original_len = len(df)
    
    # Parse the dd-mm-yyyy HH:MM format into datetime
    df['dt'] = pd.to_datetime(df['Date'], format='%d-%m-%Y %H:%M')
    
    # Keep only rows where the market is officially open
    df = df[df['dt'].apply(is_forex_market_open)].copy()
    
    # Drop the helper column and save back
    df = df.drop(columns=['dt'])
    df.to_csv(path, index=False)
    
    print(f"  Rows before: {original_len}, after: {len(df)}")

clean_csv(r"C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\EURUSD_1h_Cleaned.csv")
clean_csv(r"C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\GBPUSD_1h_Cleaned.csv")
print("Done.")
