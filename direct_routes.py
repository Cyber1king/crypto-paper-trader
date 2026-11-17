with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# Load the registry for dataset_path lookup
import json
from pathlib import Path
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "research_registry.json"
with open(REGISTRY_PATH, 'r') as f:
    REGISTRY = json.load(f)
INSTRUMENT_MAP = {}
for inst in REGISTRY.get("instruments", []):
    INSTRUMENT_MAP[inst["instrument_id"]] = inst


def get_dataset_path(instrument: str | None) -> str | None:
    if instrument is None:
        return None
    inst = INSTRUMENT_MAP.get(instrument)
    if inst is None:
        return None
    return inst.get("dataset_path")


# Now modify the replay_start route to handle instrument directly
# Find the replay_start function body and add instrument handling

# The current replay_start body starts after the docstring and ends before the HTTPException
# I need to add handling for instrument before the _session_of call

# Let me find the exact location and modify
# Current code after _session_of call:
#     name, view = _session_of(mode, instrument=instrument)
# 
# I'll add: if instrument is provided, use the dataset_path directly

# First, let me check the current state
idx = content.find('name, view = _session_of(mode, instrument=instrument)')
if idx >= 0:
    print('replay_start already has instrument pass to _session_of')
    # Print context
    start = max(0, idx-50)
    end = min(len(content), idx+50)
    print(content[start:end])
else:
    print('replay_start does NOT have instrument pass to _session_of')
"