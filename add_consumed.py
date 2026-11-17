import json

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    registry = json.load(f)

# Add RECORD 1 — EUR/USD
eur_record = {
    "instrument_id": "EUR/USD",
    "dataset_path": "data/EURUSD_1h_Cleaned.csv",
    "dataset_sha256": "f1be3dae1abda2fcb01314de9f8643b1f0437a1953f9f0f3a8c0387bf40b0e72",
    "timeframe": "1h",
    "evaluation_first": "2026-05-04T06:00:00",
    "evaluation_last": "2026-10-30T21:00:00",
    "consumed_on": "2026-11-05",
    "preregistration_id": None,
    "outcome": "inconclusive",
    "note": "Yahoo Finance hourly EUR/USD data. Consumed for pipeline validation. Sunday 22:00-23:00 UTC bars are absent by provider limitation; the replay therefore starts each week at Monday 00:00 UTC."
}

# Add RECORD 2 — GBP/USD
gbp_record = {
    "instrument_id": "GBP/USD",
    "dataset_path": "data/GBPUSD_1h_Cleaned.csv",
    "dataset_sha256": "8289cf32d10a163cc72e058b057cfeafc75e3f55970a73145054d30b2704ef6c",
    "timeframe": "1h",
    "evaluation_first": "2026-05-04T06:00:00",
    "evaluation_last": "2026-10-30T21:00:00",
    "consumed_on": "2026-11-05",
    "preregistration_id": None,
    "outcome": "inconclusive",
    "note": "Yahoo Finance hourly GBP/USD data. Consumed for pipeline validation. Sunday 22:00-23:00 UTC bars are absent by provider limitation; the replay therefore starts each week at Monday 00:00 UTC."
}

registry["consumed_windows"].append(eur_record)
registry["consumed_windows"].append(gbp_record)

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'w') as f:
    json.dump(registry, f, indent=2)
    f.write('\n')

print('Two records added to consumed_windows')
print(f'New count: {len(registry["consumed_windows"])}')
for w in registry['consumed_windows']:
    print(f'  {w.get("instrument_id")} -> {w.get("dataset_path")}')