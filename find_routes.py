# Modify the replay_start and replay_state routes in app.py
# to accept instrument parameter and use the correct dataset

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

lines = content.split('\n')

# 1. Find and modify the replay_state function
# Current signature:
#     @app.get("/api/replay", response_model=ReplayStateResponse, tags=["replay"])
#     def replay_state(
#         mode: str | None = Query(
#             default=None,
#             description="Paper mode. Omit for Standard.",
#         ),
#     ) -> ReplayStateResponse:
#     """Authoritative replay state for one mode, read from ``Replay.state``."""
#
#     name, view = _session_of(mode)
#
#     return ReplayStateResponse.from_state(view.snapshot(), mode=name)

# I need to add instrument parameter and use it

# Let me find the exact replay_state function
# It starts at line 1113 in the original, but let me find it dynamically

# Find @app.get("/api/replay")
idx_replay_get = content.find('@app.get("/api/replay"')
if idx_replay_get >= 0:
    print('Found /api/replay GET route')
    # Print 60 chars after
    print(content[idx_replay_get:idx_replay_get+200])
else:
    print('/api/replay GET route not found')

# Find the replay_start route
idx_replay_post = content.find('@app.post("/api/replay/start"')
if idx_replay_post >= 0:
    print('Found /api/replay/start POST route')
    # Print 60 chars after
    print(content[idx_replay_post:idx_replay_post+200])
else:
    print('/api/replay/start POST route not found')