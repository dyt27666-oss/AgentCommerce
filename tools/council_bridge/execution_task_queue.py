"""Lightweight local execution task queue (SQLite, artifact-first)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_DB_PATH = Path("artifacts") / "council_bridge_tasks.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()


def init_queue(db_path: Path = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                route_type TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                message_id TEXT,
                event_id TEXT,
                chat_id TEXT,
                owner_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT
            )
            """
        )
        conn.commit()


def enqueue_task(payload: dict[str, Any], *, db_path: Path = DEFAULT_DB_PATH, route_type: str = "chat") -> str:
    init_queue(db_path)
    task_id = f"task-{uuid.uuid4().hex[:10]}"
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                task_id, route_type, source, status, message_id, event_id, chat_id, owner_id,
                payload_json, created_at, updated_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                route_type,
                str(payload.get("source") or "unknown"),
                "pending",
                str(payload.get("message_id") or ""),
                str(payload.get("event_id") or ""),
                str(payload.get("chat_id") or ""),
                str(payload.get("sender_id") or ""),
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
                "",
            ),
        )
        conn.commit()
    return task_id


def fetch_next_pending_task(*, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    init_queue(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT task_id, route_type, source, status, message_id, event_id, chat_id, owner_id, payload_json
            FROM tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return {
            "task_id": row[0],
            "route_type": row[1],
            "source": row[2],
            "status": row[3],
            "message_id": row[4],
            "event_id": row[5],
            "chat_id": row[6],
            "owner_id": row[7],
            "payload": json.loads(row[8]),
        }


def mark_task_running(task_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute("UPDATE tasks SET status='running', updated_at=? WHERE task_id=?", (now, task_id))
        conn.commit()


def mark_task_done(task_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute("UPDATE tasks SET status='done', updated_at=?, error_message='' WHERE task_id=?", (now, task_id))
        conn.commit()


def mark_task_failed(task_id: str, error_message: str, *, db_path: Path = DEFAULT_DB_PATH) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET status='failed', updated_at=?, error_message=? WHERE task_id=?",
            (now, str(error_message or "")[:1000], task_id),
        )
        conn.commit()

