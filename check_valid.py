import sys
sys.path.insert(0, r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src')
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.data import load_ohlcv_csv
import pathlib

files = ['data/EURUSD_1h_Cleaned.csv','data/GBPUSD_1h_Cleaned.csv','data/USDJPY_1h_Cleaned.csv']
for p in files:
    try:
        c = load_ohlcv_csv(pathlib.Path(p))
        try:
            validate_dataset(c, expected_interval_seconds=3600, market_type='forex_spot')
            print(p + ': OK (forex_spot)')
        except ValueError as e:
            try:
                validate_dataset(c, expected_interval_seconds=3600, market_type='crypto_spot')
                print(p + ': OK (crypto_spot)')
            except ValueError as e2:
                print(p + ': FAILED - ' + str(e2)[:60])
    except Exception as e:
        print(p + ': ERROR - ' + str(e)[:40])