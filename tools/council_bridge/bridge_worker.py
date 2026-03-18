"""Lightweight worker for chat-lane tasks."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.execution_task_queue import (
    DEFAULT_DB_PATH,
    fetch_next_pending_task,
    init_queue,
    mark_task_done,
    mark_task_failed,
    mark_task_running,
)
from tools.council_bridge.feishu_chat_bridge import process_chat_task


WORKER_RESULT_PATH = Path("artifacts") / "council_bridge_worker_result.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_worker_once(*, db_path: Path = DEFAULT_DB_PATH, webhook_url: str | None = None) -> dict[str, Any]:
    init_queue(db_path)
    task = fetch_next_pending_task(db_path=db_path)
    if task is None:
        result = {
            "event_time": _now_iso(),
            "execution_status": "idle",
            "task_id": None,
            "reply_status": "none",
            "error_message": "",
        }
        _write_json(WORKER_RESULT_PATH, result)
        return result

    task_id = str(task.get("task_id"))
    mark_task_running(task_id, db_path=db_path)
    try:
        bridge_result = process_chat_task(task, webhook_url=webhook_url)
        if bridge_result.get("execution_status") == "completed":
            mark_task_done(task_id, db_path=db_path)
        else:
            mark_task_failed(task_id, bridge_result.get("error_message", "chat bridge failed"), db_path=db_path)
        result = {
            "event_time": _now_iso(),
            "execution_status": bridge_result.get("execution_status"),
            "task_id": task_id,
            "reply_status": bridge_result.get("reply_status"),
            "error_message": bridge_result.get("error_message", ""),
            "route_type": "chat",
        }
    except Exception as exc:
        mark_task_failed(task_id, str(exc), db_path=db_path)
        result = {
            "event_time": _now_iso(),
            "execution_status": "failed",
            "task_id": task_id,
            "reply_status": "failed",
            "error_message": str(exc),
            "route_type": "chat",
        }
    _write_json(WORKER_RESULT_PATH, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge chat worker.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--max-iterations", type=int, default=0, help="0 means unlimited in loop mode.")
    parser.add_argument("--webhook-url", default="")
    args = parser.parse_args()

    db = Path(args.db_path)
    if not args.loop:
        result = run_worker_once(db_path=db, webhook_url=args.webhook_url or None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    count = 0
    while True:
        count += 1
        result = run_worker_once(db_path=db, webhook_url=args.webhook_url or None)
        print(json.dumps(result, ensure_ascii=False))
        if args.max_iterations > 0 and count >= args.max_iterations:
            break
        time.sleep(max(0.2, float(args.interval_sec)))


if __name__ == "__main__":
    main()
