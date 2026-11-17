with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\hooks.ts', 'r') as f:
    content = f.read()

# Modify useReplayControls to accept and pass instrument parameter
old_sig = '''export function useReplayControls(
  mode: ModeInfo | undefined,
  options: ReplayControlOptions = {},
): ReplayControl {'''

new_sig = '''export function useReplayControls(
  mode: ModeInfo | undefined,
  instrument: string | undefined,
  options: ReplayControlOptions = {},
): ReplayControl {'''

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print('useReplayControls signature modified')
else:
    print('useReplayControls signature old string not found')
    # Try to find it
    idx = content.find('export function useReplayControls')
    if idx >= 0:
        print(f'Found at {idx}')
        print(content[idx:idx+100])

# Now modify the start mutation to pass instrument
old_start = '''  const start = useMutation<ReplayState, ApiError, number | undefined>({
    mutationFn: (intervalMs?: number) => {
      requireEnabled();
      return api.startReplay(modeId, intervalMs);
    },
    onSuccess: adopt,
  });'''

new_start = '''  const start = useMutation<ReplayState, ApiError, number | undefined>({
    mutationFn: (intervalMs?: number) => {
      requireEnabled();
      return api.startReplay(modeId, intervalMs, instrument);
    },
    onSuccess: adopt,
  });'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('start mutation modified')
else:
    print('start mutation old string not found')

# Modify the pause mutation to pass instrument
old_pause = '''  const pause = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.pauseReplay(modeId);
    },
    onSuccess: adopt,
  });'''

new_pause = '''  const pause = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.pauseReplay(modeId, instrument);
    },
    onSuccess: adopt,
  });'''

if old_pause in content:
    content = content.replace(old_pause, new_pause)
    print('pause mutation modified')
else:
    print('pause mutation old string not found')

# Modify the step mutation to pass instrument
old_step = '''  const step = useMutation<ReplayState, ApiError, StepQuery | undefined>({
    mutationFn: (query?: StepQuery) => {
      requireEnabled();
      return api.stepReplay(modeId, query?.count ?? 1);
    },
    onSuccess: adopt,
  });'''

new_step = '''  const step = useMutation<ReplayState, ApiError, StepQuery | undefined>({
    mutationFn: (query?: StepQuery) => {
      requireEnabled();
      return api.stepReplay(modeId, query?.count ?? 1, instrument);
    },
    onSuccess: adopt,
  });'''

if old_step in content:
    content = content.replace(old_step, new_step)
    print('step mutation modified')
else:
    print('step mutation old string not found')

# Modify the reset mutation to pass instrument
old_reset = '''  const reset = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.resetReplay(modeId);
    },
    onSuccess: adopt,
  });'''

new_reset = '''  const reset = useMutation<ReplayState, ApiError, void>({
    mutationFn: () => {
      requireEnabled();
      return api.resetReplay(modeId, instrument);
    },
    onSuccess: adopt,
  });'''

if old_reset in content:
    content = content.replace(old_reset, new_reset)
    print('reset mutation modified')
else:
    print('reset mutation old string not found')

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\lib\hooks.ts', 'w') as f:
    f.write(content)
print('hooks.ts modified')