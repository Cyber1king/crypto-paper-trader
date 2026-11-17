with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# The old string - the function signature ending at ') -> ReplayStateResponse:'
old = '        mode: str | None = Query(\n            default=None, description=\"Paper mode. Omit for Standard.\"\n        ),\n    ) -> ReplayStateResponse:'

# The new string with instrument added
new = '        mode: str | None = Query(\n            default=None, description=\"Paper mode. Omit for Standard.\"\n        ),\n        instrument: str | None = Query(\n            default=None, description=\"Instrument/market identifier. Omit for BTC/USDT.\"\n        ),\n    ) -> ReplayStateResponse:'

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'w') as f:
        f.write(content)
    print('replay_start instrument param added successfully')
else:
    print('old string not found')