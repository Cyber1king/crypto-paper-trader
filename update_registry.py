import json

with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\data\\research_registry.json', 'r') as f:
    registry = json.load(f)

instruments = registry.get('instruments', [])
for inst in instruments:
    iid = inst['instrument_id']
    if iid in ['EUR/USD', 'GBP/USD', 'USD/JPY']:
        inst['research_approval'] = 'RESEARCH_CONSUMED'
        print(f'Updated {iid}: research_approval={inst["research_approval"]}')

with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\data\\research_registry.json', 'w') as f:
    json.dump(registry, f, indent=2)

print('Registry updated successfully')