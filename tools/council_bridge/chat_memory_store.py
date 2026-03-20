"""Minimal per-chat memory store for chat lane."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHAT_MEMORY_DIR = Path("artifacts") / "chat_memory"
MAX_TURNS_DEFAULT = 6


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_name(raw: str) -> str:
    text = str(raw or "").strip() or "unknown_chat"
    return re.sub(r"[^a-zA-Z0-9._-]", "_", text)


def _memory_path(chat_id: str, *, memory_dir: Path = CHAT_MEMORY_DIR) -> Path:
    return memory_dir / f"{_safe_name(chat_id)}.json"


def _load_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"chat_id": "", "messages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"chat_id": "", "messages": []}
    if not isinstance(data, dict):
        return {"chat_id": "", "messages": []}
    messages = data.get("messages")
    if not isinstance(messages, list):
        data["messages"] = []
    return data


def load_recent_messages(
    *,
    chat_id: str,
    max_turns: int = MAX_TURNS_DEFAULT,
    memory_dir: Path = CHAT_MEMORY_DIR,
) -> list[dict[str, str]]:
    path = _memory_path(chat_id, memory_dir=memory_dir)
    payload = _load_raw(path)
    raw_messages = payload.get("messages", [])
    if not isinstance(raw_messages, list):
        return []

    bounded = raw_messages[-max(2, int(max_turns) * 2) :]
    cleaned: list[dict[str, str]] = []
    for item in bounded:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        cleaned.append({"role": role, "text": text})
    return cleaned


def append_turn(
    *,
    chat_id: str,
    user_text: str,
    assistant_text: str,
    max_turns: int = MAX_TURNS_DEFAULT,
    memory_dir: Path = CHAT_MEMORY_DIR,
) -> dict[str, Any]:
    path = _memory_path(chat_id, memory_dir=memory_dir)
    payload = _load_raw(path)
    payload["chat_id"] = chat_id
    messages = payload.get("messages")
    if not isinstance(messages, list):
        messages = []
        payload["messages"] = messages

    user_clean = str(user_text or "").strip()
    assistant_clean = str(assistant_text or "").strip()
    if user_clean:
        messages.append({"role": "user", "text": user_clean, "created_at": _now_iso()})
    if assistant_clean:
        messages.append({"role": "assistant", "text": assistant_clean, "created_at": _now_iso()})

    keep = max(2, int(max_turns) * 2)
    if len(messages) > keep:
        payload["messages"] = messages[-keep:]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "chat_memory_path": str(path),
        "chat_memory_messages": len(payload["messages"]),
        "chat_memory_turns": len(payload["messages"]) // 2,
    }

