import json

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    registry = json.load(f)

# Remove USD/JPY entry
registry['instruments'] = [inst for inst in registry['instruments'] if inst.get('instrument_id') != 'USD/JPY']

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'w') as f:
    json.dump(registry, f, indent=2)
    f.write('\n')

print('USD/JPY entry removed')
print(f'Remaining instruments: {len(registry["instruments"])}')
for inst in registry['instruments']:
    print(f'  {inst["instrument_id"]}')