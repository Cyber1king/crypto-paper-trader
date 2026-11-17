import sys
sys.path.insert(0, r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src')
from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.data import load_ohlcv_csv
import pathlib
import os

# Get the research_engine directory
engine_dir = r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine'

print('=== A) Two Forex pairs ===')
for p in ['data/EURUSD_1h_Cleaned.csv','data/GBPUSD_1h_Cleaned.csv']:
    full = os.path.join(engine_dir, p)
    try:
        c = load_ohlcv_csv(pathlib.Path(full))
        validate_dataset(c, expected_interval_seconds=3600, market_type='forex_spot')
        print(p + ' OK')
    except ValueError as e:
        print(p + ' FAILED: ' + str(e)[:100])

print()

print('=== B) BTC ===')
btc_file = os.path.join(engine_dir, 'data/BTCUSDT_1h_Cleaned (1).csv')
c = load_ohlcv_csv(pathlib.Path(btc_file))
validate_dataset(c, expected_interval_seconds=3600, market_type='crypto_spot')
print('BTC OK')

print()

print('=== C) Registry ===')
from crypto_paper_lab.researchguard import load_registry
r = load_registry()
print('count =', len(r.get('instruments', [])))
for i in r.get('instruments', []):
    print(i['instrument_id'], '->', i['research_approval'])