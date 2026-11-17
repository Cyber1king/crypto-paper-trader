import json

with open(r"C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json", "r") as f:
    registry = json.load(f)

for inst in registry["instruments"]:
    if inst["instrument_id"] in ["EUR/USD", "GBP/USD", "USD/JPY"]:
        print(f"=== {inst['instrument_id']} ===")
        for k, v in inst.items():
            print(f"  {k}: {v!r}")
        print()