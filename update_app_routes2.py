# Read the app.py file
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# First, let me check the current state of the replay_start and replay_state functions
# and the _session_of function

# Check if instrument parameter is already in replay_start
if 'instrument: str | None = Query' in content:
    print('instrument parameter already present in app.py')
else:
    print('instrument parameter NOT found - need to add it')
    
# Check _session_of
if 'def _session_of(mode: str | None, instrument' in content:
    print('_session_of already has instrument parameter')
else:
    print('_session_of does NOT have instrument parameter')

# Check if the INSTRUMENT_MAP import exists
if 'INSTRUMENT_MAP' in content:
    print('INSTRUMENT_MAP already imported')
else:
    print('INSTRUMENT_MAP not imported')