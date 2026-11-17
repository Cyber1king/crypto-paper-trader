import json

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    reg = json.load(f)

print('Registry loaded successfully')
print(f'Total instruments: {len(reg.get("instruments", []))}')

for i in reg.get('instruments', []):
    iid = i['instrument_id']
    if iid in ['BTC/USDT', 'EUR/USD', 'GBP/USD', 'USD/JPY']:
        approval = i.get('research_approval', 'N/A')
        print(f'  {iid}: approval={approval}')

# Check schema validation - all should have research_approval set
valid_statuses = {'RESEARCH_CONSUMED', 'RESEARCH_APPROVED'}
for i in reg.get('instruments', []):
    approval = i.get('research_approval', '')
    if approval not in valid_statuses:
        print(f'  WARNING: {i["instrument_id"]} has invalid research_approval: {approval}')
    else:
        print(f'  OK: {i["instrument_id"]} has valid research_approval: {approval}')