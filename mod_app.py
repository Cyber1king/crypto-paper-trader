with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# Construct the exact old string (the function signature before our modification)
old = """    def replay_start(
        interval_ms: int | None = Query(
            default=None,
            description=(
                "Auto-run pace in milliseconds, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS}. Omit to keep the current \n                interval. Out of range is rejected, never clamped."
            ),
        ),
        mode: str | None = Query(
            default=None, description="Paper mode. Omit for Standard."
        ),
    ) -> ReplayStateResponse:"""

# New string with instrument parameter added
new = """    def replay_start(
        interval_ms: int | None = Query(
            default=None,
            description=(
                "Auto-run pace in milliseconds, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS}. Omit to keep the current \n                interval. Out of range is rejected, never clamped."
            ),
        ),
        mode: str | None = Query(
            default=None, description="Paper mode. Omit for Standard."
        ),
        instrument: str | None = Query(
            default=None, description="Instrument/market identifier. Omit for BTC/USDT."
        ),
    ) -> ReplayStateResponse:"""

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'w') as f:
        f.write(content)
    print('replay_start modified successfully')
else:
    print('old string not found')
    # Debug: print what's actually at that position
    idx = content.find('def replay_start(')
    print(f'Found at {idx}')
    # Print the actual lines
    lines = content.split('\n')
    for i in range(idx//80, min((idx//80)+10, len(lines))):
        print(f'Line {i+1}: {lines[i][:100]}')