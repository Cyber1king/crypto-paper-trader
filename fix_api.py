with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'r') as f:
    content = f.read()

old = '  async getReplay(mode?: ModeName, signal?: AbortSignal): Promise<ReplayState> {\n    return this.request<ReplayState>("GET", "/api/replay", { mode }, signal);\n  }'

new = '  async getReplay(mode?: ModeName, instrument?: string, signal?: AbortSignal): Promise<ReplayState> {\n    return this.request<ReplayState>("GET", "/api/replay", { mode, instrument }, signal);\n  }'

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'w') as f:
        f.write(content)
    print('API updated successfully')
else:
    print('Old string not found')
    idx = content.find('async getReplay')
    if idx >= 0:
        print('Found at', idx)
        print('Context:', repr(content[idx:idx+80]))