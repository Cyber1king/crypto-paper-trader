import json, os

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    registry = json.load(f)

instruments = registry.get('instruments', [])
instrument_map = {}
for inst in instruments:
    instrument_map[inst['instrument_id']] = inst

print('Instrument map:')
for k, v in instrument_map.items():
    print(f'  {k}: dataset_path={v.get("dataset_path", "N/A")}, market_type={v.get("market_type", "N/A")}')