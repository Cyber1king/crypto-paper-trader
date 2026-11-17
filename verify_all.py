import sys
sys.path.insert(0, r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src')
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.data import load_ohlcv_csv
import pathlib
from crypto_paper_lab.researchguard import load_registry

print('=== A) Forex CSVs ===')
for p in ['data/EURUSD_1h_Cleaned.csv','data/GBPUSD_1h_Cleaned.csv','data/USDJPY_1h_Cleaned.csv']:
    try:
        c = load_ohlcv_csv(pathlib.Path(p))
        validate_dataset(c, expected_interval_seconds=3600, market_type='forex_spot')
        print(p + ' OK')
    except ValueError as e:
        print(p + ' FAILED: ' + str(e))

print()
print('=== B) BTC CSV ===')
c = load_ohlcv_csv(pathlib.Path('data/BTCUSDT_1h_Cleaned (1).csv'))
validate_dataset(c, expected_interval_seconds=3600, market_type='crypto_spot')
print('BTC OK')

print()
print('=== C) Registry ===')
r = load_registry()
print('registry OK, count =', len(r.get('instruments', [])))