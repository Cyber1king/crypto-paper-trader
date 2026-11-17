with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\lib\\api.ts', 'r') as f:
    content = f.read()

# Add instrument parameter to getMarket
old_get_market = '''  async getMarket(
    query: MarketQuery = {},
    signal?: AbortSignal,
  ): Promise<MarketResponse> {
    return this.request<MarketResponse>("GET", "/api/market", { ...query }, signal);
  }'''

new_get_market = '''  async getMarket(
    query: MarketQuery = {},
    instrument?: string,
    signal?: AbortSignal,
  ): Promise<MarketResponse> {
    return this.request<MarketResponse>("GET", "/api/market", { ...query, instrument }, signal);
  }'''

if old_get_market in content:
    content = content.replace(old_get_market, new_get_market)
    print('getMarket instrument parameter added')
else:
    print('getMarket old string not found')
    # Try to find it
    idx = content.find('async getMarket')
    if idx >= 0:
        print(f'Found at {idx}')
        print(content[idx:idx+150])

with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\lib\\api.ts', 'w') as f:
    f.write(content)
print('API client updated')