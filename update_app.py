with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# 1. Modify replay_start to accept instrument parameter
old_start = """def replay_start(
        interval_ms: int | None = Query(
            default=None,
            description=(
                "Auto-run pace in milliseconds, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS}. Omit to keep the current "
                "interval. Out of range is rejected, never clamped."
            ),
        ),
        mode: str | None = Query(
            default=None, description="Paper mode. Omit for Standard."
        ),
    ) -> ReplayStateResponse:"""

new_start = """def replay_start(
        interval_ms: int | None = Query(
            default=None,
            description=(
                "Auto-run pace in milliseconds, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS}. Omit to keep the current "
                "interval. Out of range is rejected, never clamped."
            ),
        ),
        mode: str | None = Query(
            default=None, description="Paper mode. Omit for Standard."
        ),
        instrument: str | None = Query(
            default=None, description="Instrument/market identifier. Omit for BTC/USDT."
        ),
    ) -> ReplayStateResponse:"""

if old_start in content:
    content = content.replace(old_start, new_start)
    print('replay_start modified')
else:
    print('replay_start old string not found')

# 2. Modify replay_state to accept instrument parameter
old_state = """def replay_state(
        mode: str | None = Query(
            default=None,
            description="Paper mode. Omit for Standard.",
        ),
    ) -> ReplayStateResponse:"""

new_state = """def replay_state(
        mode: str | None = Query(
            default=None,
            description="Paper mode. Omit for Standard.",
        ),
        instrument: str | None = Query(
            default=None, description="Instrument/market identifier. Omit for BTC/USDT."
        ),
    ) -> ReplayStateResponse:"""

if old_state in content:
    content = content.replace(old_state, new_state)
    print('replay_state modified')
else:
    print('replay_state old string not found')

# 3. Now modify the replay_start function body to use instrument
# Find the body and add instrument handling
# The function calls _session_of(mode) - we need to also pass instrument

# Let me find the _session_of call within replay_start
idx = content.find("name, view = _session_of(mode)")
if idx >= 0:
    # Print context
    start = max(0, idx-100)
    end = min(len(content), idx+200)
    print("replay_start _session_of context:")
    print(content[start:end])
else:
    print("_session_of not found in replay_start")

# Find where _session_of is defined
idx2 = content.find("def _session_of")
if idx2 >= 0:
    print(f"\n_session_of defined at {idx2}")
    start = max(0, idx2-20)
    end = min(len(content), idx2+100)
    print(content[start:end])