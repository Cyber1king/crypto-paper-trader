with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'r') as f:
    content = f.read()

# Add instrument parameter to startReplay
old_start = '''  async startReplay(
    mode: ModeName | undefined,
    intervalMs?: number,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/start",
      { mode, interval_ms: intervalMs },
      signal,
    );
  }'''

new_start = '''  async startReplay(
    mode: ModeName | undefined,
    intervalMs?: number,
    instrument?: string,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/start",
      { mode, interval_ms: intervalMs, instrument },
      signal,
    );
  }'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('startReplay modified')
else:
    print('startReplay old string not found')

# Add instrument parameter to pauseReplay
old_pause = '''  async pauseReplay(
    mode?: ModeName,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/pause",
      { mode },
      signal,
    );
  }'''

new_pause = '''  async pauseReplay(
    mode?: ModeName,
    instrument?: string,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/pause",
      { mode, instrument },
      signal,
    );
  }'''

if old_pause in content:
    content = content.replace(old_pause, new_pause)
    print('pauseReplay modified')
else:
    print('pauseReplay old string not found')

# Add instrument parameter to stepReplay
old_step = '''  async stepReplay(
    mode?: ModeName,
    count?: number,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/step",
      { mode, count },
      signal,
    );
  }'''

new_step = '''  async stepReplay(
    mode?: ModeName,
    count?: number,
    instrument?: string,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/step",
      { mode, count, instrument },
      signal,
    );
  }'''

if old_step in content:
    content = content.replace(old_step, new_step)
    print('stepReplay modified')
else:
    print('stepReplay old string not found')

# Add instrument parameter to resetReplay
old_reset = '''  async resetReplay(
    mode?: ModeName,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/reset",
      { mode },
      signal,
    );
  }'''

new_reset = '''  async resetReplay(
    mode?: ModeName,
    instrument?: string,
    signal?: AbortSignal,
  ): Promise<ReplayState> {
    return this.request<ReplayState>(
      "POST",
      "/api/replay/reset",
      { mode, instrument },
      signal,
    );
  }'''

if old_reset in content:
    content = content.replace(old_reset, new_reset)
    print('resetReplay modified')
else:
    print('resetReplay old string not found')

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\api.ts', 'w') as f:
    f.write(content)
print('API client modified')