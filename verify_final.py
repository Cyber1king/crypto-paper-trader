#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src')

from crypto_paper_lab.dataset import validate_dataset
from crypto_paper_lab.data import load_ohlcv_csv
import pathlib

print('=== Test 1: BTC with market_type=crypto_spot ===')
c = load_ohlcv_csv(pathlib.Path(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\BTCUSDT_1h_Cleaned (1).csv'))
validate_dataset(c, expected_interval_seconds=3600, market_type='crypto_spot')
print('BTC OK')

print()
print('=== Test 2: EUR/USD with market_type=forex_spot ===')
try:
    c = load_ohlcv_csv(pathlib.Path(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\EURUSD_1h_Cleaned.csv'))
    validate_dataset(c, expected_interval_seconds=3600, market_type='forex_spot')
    print('EURUSD OK')
except ValueError as e:
    print(f'ValueError: {e}')