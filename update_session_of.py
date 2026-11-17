with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# 1. Modify _session_of to accept instrument parameter
old_session_of = """    def _session_of(mode: str | None) -> tuple:
        \"\"\"Resolve a mode to its isolated session, or refuse with HTTP.

        An unknown mode and a reserved or brokerless mode are both refusals, but
        with different codes so a client can tell "no such mode" from "not built
        yet" from "that mode does not trade".

        \"\"\"

        name = _mode_of(mode)

        try:
            return name, mode_registry.session(name)
        except ModeError as exc:
            status = (
                422
                if getattr(exc, "code", "") == "INVALID_MODE"
                else 409
            )
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc"""

new_session_of = """    def _session_of(mode: str | None, instrument: str | None = None) -> tuple:
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
        except ModeError as exc:
            status = (
                422
                if getattr(exc, "code", "") == "INVALID_MODE"
                else 409
            )
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc"""

if old_session_of in content:
    content = content.replace(old_session_of, new_session_of)
    print('_session_of modified')
else:
    print('_session_of old string not found')

# 2. Modify mode_registry.session() to accept instrument parameter
# First, find the session method in moderegistry.py and add instrument param
# But we're in app.py, so we need to also import or reference the moderegistry

# Actually, let me check if mode_registry.session is already imported/modified
# The mode_registry is just ModeRegistry() - it uses _default_session which we already modified

# Let me check the ModeRegistry.session method signature
idx = content.find("def session(self, mode: str)")
if idx >= 0:
    # Print the method
    lines = content[idx:idx+300].split('\n')
    print("ModeRegistry.session method:")
    for i, line in enumerate(lines[:30]):
        print(f'  {i+1}: {line}')
else:
    print("ModeRegistry.session not found in app.py")