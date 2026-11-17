with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\src\\paper_api\\app.py', 'r') as f:
    content = f.read()

# Find the market_candles function
idx = content.find('def market_candles')
if idx >= 0:
    print('Found market_candles at', idx)
    print(content[idx:idx+600])
else:
    print('market_candles not found')
    # Try finding the route
    for i, line in enumerate(content.split('\n')):
        if 'GET /api/market' in line or '"/api/market"' in line:
            print(f'Line {i+1}: {line.rstrip()[:100]}')
PYEOF