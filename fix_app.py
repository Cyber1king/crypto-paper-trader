#!/usr/bin/env python
import json
from pathlib import Path

# Load the registry once at module level
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


# Now modify app.py
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# 1. Add the INSTRUMENT_MAP and get_dataset_path after the imports
# Find a good place to add - after the fastapi import line or after the crypto_paper_lab imports
import_section_end = content.find('from crypto_paper_lab.replay import')
if import_section_end >= 0:
    # Find the end of the replay imports
    rest = content[import_section_end:]
    # Find the next import block
    next_import = rest.find('from ')
    if next_import >= 0:
        # Insert after the replay imports
        insert_pos = import_section_end + len('from crypto_paper_lab.replay import')
        # Actually, let me just add the INSTRUMENT_MAP loading after the existing module-level code
        # Find a good insertion point - after the mode_registry initialization
        
# Let me find the mode_registry initialization
idx = content.find('mode_registry = ModeRegistry()')
if idx >= 0:
    print(f'mode_registry initialization at line {idx//content.split(chr(10)).__len__()+1 approx}')
    # Print context
    lines = content.split('\n')
    for i in range(max(0, idx-5), min(len(lines), idx+10)):
        print(f'{i+1}: {lines[i]}')
else:
    print('mode_registry initialization not found')

# Let me just take a different approach - replace the _session_of function 
# to accept instrument and use it

# First, let me find the exact _session_of function
old_session_of = """    def _session_of(mode: str | None, instrument: str | None = None) -> tuple:
        \"\"\"Resolve a mode to its isolated session, or refuse with HTTP.

        An unknown mode and a reserved or brokerless mode are both refusals, but
        with different codes so a client can tell "no such mode" from "not built
        yet" from "that mode does not trade".

        If ``instrument`` is provided, the corresponding dataset path from the
        registry is loaded so the replay uses the correct candle data.
        \"\"\"

        name = _mode_of(mode)

        try:
            return name, mode_registry.session(name, instrument=instrument)
        except ModeError as exc:"""

# Check if old_session_of exists
if old_session_of in content:
    print('_session_of with instrument found')
else:
    print('_session_of with instrument NOT found')
    # Print what _session_of looks like
    idx = content.find('def _session_of')
    if idx >= 0:
        print(content[idx:idx+300])