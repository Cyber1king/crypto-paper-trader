with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'r') as f:
    content = f.read()

# Replace HighRiskSession load_research_candles
old_hr = '                    load_research_candles(),\n                    config=baseline_config(),\n                    costs=phase13_costs(),\n                    # Standard\'s own policy instance. High-Risk changes no'
new_hr = '                    load_research_candles(dataset_path),\n                    config=baseline_config(),\n                    costs=phase13_costs(),\n                    # Standard\'s own policy instance. High-Risk changes no'
content = content.replace(old_hr, new_hr, 1)

# Replace the ManualSession candles = load_research_candles()
old_manual = '            candles = load_research_candles()\n\n            session = ManualSession'
new_manual = '            candles = load_research_candles(dataset_path)\n\n            session = ManualSession'
content = content.replace(old_manual, new_manual, 1)

# Replace the last ReplaySession constructor
old_session = '            Replay(\n                load_research_candles(),\n                config=baseline_config(),\n                costs=phase13_costs(),\n                policy=mode_policy(mode),\n                dataset_sha256=dataset_identity(),'
new_session = '            Replay(\n                load_research_candles(dataset_path),\n                config=baseline_config(),\n                costs=phase13_costs(),\n                policy=mode_policy(mode),\n                dataset_sha256=dataset_identity(),'
content = content.replace(old_session, new_session, 1)

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'w') as f:
    f.write(content)
print('moderegistry.py updated successfully')