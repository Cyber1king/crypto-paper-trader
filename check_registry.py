import json
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    registry = json.load(f)
for inst in registry['instruments']:
    if inst.get('instrument_id') == 'USD/JPY':
        print('Current research_approval:', inst.get('research_approval'))
        print('Current blocker:', inst.get('blocker', 'NOT PRESENT'))