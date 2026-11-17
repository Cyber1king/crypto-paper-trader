with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'r') as f:
    content = f.read()

# The session method currently is:
# def session(self, mode: str, instrument: str | None = None) -> ReplaySession:
#     ...
#     existing = self._sessions.get(mode)
#     if existing is not None:
#         return existing
#     session = self._build(mode)
#     self._sessions[mode] = session
#     return session

# I need to modify it to use the instrument parameter to look up the dataset_path
# and pass it to _build (which calls _default_session)

# However, ModeRegistry doesn't have access to the INSTRUMENT_MAP.
# I need to add a module-level reference or change the approach.

# The simplest fix: modify the session method to pass instrument to _build,
# and then modify _build/_default_session to use it.

# But _build is just _default_session (since no injected builder).
# And _default_session already accepts dataset_path.

# Let me modify the session method to pass instrument through to _default_session
# by looking up the dataset path.

# Actually, the cleanest approach is to modify the API routes to directly
# handle the instrument/dataset_path, rather than trying to thread it through
# ModeRegistry. But let me try one more thing first.

# Modify the session method to accept instrument and pass dataset_path to _build
# I'll add a module-level INSTRUMENT_MAP that can be accessed

# First, let me check if there's already a way to access the registry from moderegistry
idx = content.find('def session(self, mode: str, instrument')
if idx >= 0:
    # Print the full method
    lines = content.split('\n')
    method_lines = []
    in_method = False
    for i in range(idx, min(idx+50, len(lines))):
        method_lines.append(lines[i])
        if 'return session' in lines[i]:
            break
    
    print('Current session method:')
    for line in method_lines:
        print(line, end='')
    print()
    
    # Now replace the session method body to use instrument
    old_body = '''        existing = self._sessions.get(mode)
        if existing is not None:
            return existing

        session = self._build(mode)
        self._sessions[mode] = session

        return session'''

    new_body = '''        existing = self._sessions.get(mode)
        if existing is not None:
            return existing

        # If instrument is provided, look up the dataset path and pass it to the session
        dataset_path = None
        if instrument is not None:
            from crypto_paper_lab.registry import INSTRUMENT_MAP as _IM
            inst = _IM.get(instrument)
            if inst is not None:
                dataset_path = inst.get('dataset_path')

        session = self._build(mode, dataset_path=dataset_path)
        self._sessions[mode] = session

        return session'''

    if old_body in content[idx:idx+200]:
        content = content.replace(old_body, new_body)
        with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'w') as f:
            f.write(content)
        print('moderegistry.py session method updated')
    else:
        print('old body not found - showing actual content:')
        # Print actual content around the session method
        for i in range(idx, min(idx+30, len(lines))):
            print(f'{i+1}: {lines[i]}', end='')
        print()