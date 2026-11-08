"""Persistent storage for the assistant chat panel's conversation history.

Messages are stored in ``research_engine/data/assistant_history.json``. The
file is read on demand and atomically rewritten after each append. Its shape is
``{"messages": [{"role": "user" | "assistant", "content": str,
"timestamp": iso8601_str, "pending_action": dict | null,
"tool_calls": list | null}, ...]}``. Only the last 200 messages are retained
to keep the file small.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


HISTORY_PATH = Path(__file__).resolve().parents[3] / "data" / "assistant_history.json"
MAX_MESSAGES = 200
_HISTORY_LOCK = threading.Lock()


def _read_messages_unlocked() -> list[dict]:
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as history_file:
            document = json.load(history_file)
        messages = document.get("messages", [])
        if not isinstance(messages, list):
            return []
        return [message for message in messages if isinstance(message, dict)]
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return []


def load_history() -> list[dict]:
    """Read the stored messages; return [] if the file is missing or unreadable."""
    with _HISTORY_LOCK:
        return _read_messages_unlocked()


def append_message(
    role: str,
    content: str,
    pending_action: dict | None = None,
    tool_calls: list | None = None,
) -> None:
    """Append one message and atomically rewrite the file, trimmed to MAX_MESSAGES."""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pending_action": pending_action,
        "tool_calls": tool_calls,
    }
    with _HISTORY_LOCK:
        messages = _read_messages_unlocked()
        messages.append(message)
        document = {"messages": messages[-MAX_MESSAGES:]}
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = HISTORY_PATH.with_suffix(".json.tmp")
        with temporary_path.open("w", encoding="utf-8", newline="\n") as history_file:
            json.dump(document, history_file, ensure_ascii=False, indent=2)
            history_file.write("\n")
        os.replace(temporary_path, HISTORY_PATH)


def clear_history() -> None:
    """Delete the history file. Idempotent."""
    with _HISTORY_LOCK:
        try:
            HISTORY_PATH.unlink()
        except FileNotFoundError:
            pass
