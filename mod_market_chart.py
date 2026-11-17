with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\components\\market-chart.tsx', 'r') as f:
    content = f.read()

# Add instrument prop to MarketChart interface
old_interface = '''export function MarketChart({
  market,
  isLoading,
  error,
  signal,
  asset,
  timeframe,
  onRetry,
}: {'''

new_interface = '''export function MarketChart({
  market,
  isLoading,
  error,
  signal,
  asset,
  timeframe,
  instrument,
  onRetry,
}: {'''

if old_interface in content:
    content = content.replace(old_interface, new_interface)
    print('MarketChart interface updated')
else:
    print('MarketChart interface old string not found')
    # Try alternative
    idx = content.index('export function MarketChart')
    print(content[idx:idx+100])

# Add instrument to the badge display - change the asset display
old_badge = '''<span className="break-words">{asset ?? "—"} Price History</span>'''

new_badge = '''<span className="break-words">{instrument ?? asset ?? "—"} Price History</span>'''

if old_badge in content:
    content = content.replace(old_badge, new_badge)
    print('MarketChart badge updated')
else:
    print('MarketChart badge old string not found')

# Update the useMarket call in dashboard to pass selectedMarket
# Actually, let me just update the MarketChart usage first, then the API

with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\components\\market-chart.tsx', 'w') as f:
    f.write(content)
print('market-chart.tsx partially updated')