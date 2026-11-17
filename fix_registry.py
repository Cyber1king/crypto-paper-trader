#!/usr/bin/env python3
import json

# Read the file as string and add dataset_note manually
with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\data\\research_registry.json', 'r') as f:
    content = f.read()

note = ', \"dataset_note\": \"Yahoo Finance does not publish Sunday 22:00-23:00 UTC bars at the start of each forex week. The replay therefore starts each week at Monday 00:00 UTC. This is a provider limitation, not data loss.\"'

# Add after dataset_path in each of the three Forex entries
# Pattern: "dataset_path": "data/EURUSD_1h_Cleaned.csv"
# We need to add , "dataset_note": ... after the dataset_path line

# For EUR/USD
content = content.replace(
    '"dataset_path": "data/EURUSD_1h_Cleaned.csv"',
    '"dataset_path": "data/EURUSD_1h_Cleaned.csv",\n      "dataset_note": "Yahoo Finance does not publish Sunday 22:00-23:00 UTC bars at the start of each forex week. The replay therefore starts each week at Monday 00:00 UTC. This is a provider limitation, not data loss."'
)

# For GBP/USD
content = content.replace(
    '"dataset_path": "data/GBPUSD_1h_Cleaned.csv"',
    '"dataset_path": "data/GBPUSD_1h_Cleaned.csv",\n      "dataset_note": "Yahoo Finance does not publish Sunday 22:00-23:00 UTC bars at the start of each forex week. The replay therefore starts each week at Monday 00:00 UTC. This is a provider limitation, not data loss."'
)

# For USD/JPY
content = content.replace(
    '"dataset_path": "data/USDJPY_1h_Cleaned.csv"',
    '"dataset_path": "data/USDJPY_1h_Cleaned.csv",\n      "dataset_note": "Yahoo Finance does not publish Sunday 22:00-23:00 UTC bars at the start of each forex week. The replay therefore starts each week at Monday 00:00 UTC. This is a provider limitation, not data loss."'
)

with open(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\data\\research_registry.json', 'w') as f:
    f.write(content)

print('Registry updated')