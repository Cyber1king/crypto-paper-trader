with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'r') as f:
    content = f.read()

# Exact match from the file
old = 'async getReplay(mode?: ModeName, signal?: AbortSignal): Promise<ReplayState> {\n    return this.request<ReplayState>(\n'

new = 'async getReplay(mode?: ModeName, instrument?: string, signal?: AbortSignal): Promise<ReplayState> {\n    return this.request<ReplayState>(\n'

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'w') as f:
        f.write(content)
    print('API updated successfully')
else:
    print('Old string not found')