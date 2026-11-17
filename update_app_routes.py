import json, os
from pathlib import Path

# Load the registry at module level (or we could load it each time, but once is fine)
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "research_registry.json"
with open(REGISTRY_PATH, 'r') as f:
    REGISTRY = json.load(f)

INSTRUMENT_MAP = {}
for inst in REGISTRY.get("instruments", []):
    INSTRUMENT_MAP[inst["instrument_id"]] = inst


def get_dataset_path(instrument: str | None) -> str | None:
    """Look up the dataset path for a given instrument from the registry."""
    if instrument is None:
        return None
    inst = INSTRUMENT_MAP.get(instrument)
    if inst is None:
        return None
    return inst.get("dataset_path")


# Now modify the replay_start route
# First, let me find and replace the replay_start function

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# 1. Modify replay_start to accept instrument parameter and use it
# The current function signature and body needs to be updated

# Find the replay_start function
import re

# Let me find the exact location and content
idx = content.find('def replay_start(')
if idx >= 0:
    # Print 50 chars after
    print("replay_start found at: ", idx)
    # Print the function signature line
    lines = content.split('\n')
    for i in range(idx, min(idx+10, len(lines))):
        print(f'Line {i+1}: {lines[i]}')"