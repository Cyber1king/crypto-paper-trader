import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "research_engine", "src")
if _src not in sys.path and os.path.isdir(_src):
    sys.path.insert(0, _src)


def _log(msg: str) -> None:
    try:
        base = Path(os.environ.get("LOCALAPPDATA", _here)) / "CryptoPaperLab"
        base.mkdir(parents=True, exist_ok=True)
        with (base / "launcher.log").open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except Exception:
        pass


def _start_server():
    try:
        import uvicorn
        from paper_api.app import app

        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", log_config=None)
    except Exception:
        _log("SERVER CRASH: " + traceback.format_exc())


def _wait_for_server(host="127.0.0.1", port=8000, timeout=60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    os.environ.setdefault("LIVE_TRADING_ENABLED", "true")
    os.environ.setdefault("ASSISTANT_FAKE_LLM", "true")
    _log("launcher start")

    thread = threading.Thread(target=_start_server, daemon=True)
    thread.start()
    _log("server thread started")

    start = time.time()
    ready = _wait_for_server()
    elapsed = time.time() - start
    _log(f"server ready={ready} after {elapsed:.1f}s")

    if ready:
        time.sleep(2.0)  # grace: let uvicorn finish ASGI wiring
        ok = False
        for attempt in range(3):
            try:
                ok = webbrowser.open("http://127.0.0.1:8000/")
            except Exception:
                _log("webbrowser exception: " + traceback.format_exc())
                ok = False
            _log(f"webbrowser.open attempt {attempt + 1}: {ok}")
            if ok:
                break
            time.sleep(2.0)
    else:
        _log("server did not become ready within timeout")

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        _log("KeyboardInterrupt")


if __name__ == "__main__":
    main()
