"""Capture post-dispatch completion-side observations for bridge v0.

This helper does not execute Codex. It only observes local state and
normalizes a completion observation artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISPATCH_RECEIPT_PATH = Path("artifacts") / "council_codex_dispatch_receipt.json"
EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"
OUTPUT_PATH = Path("artifacts") / "council_codex_dispatch_completion.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _tail(path: str | None, limit: int = 300) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8", errors="ignore")
    return txt[-limit:].strip()


def _is_process_running(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
        )
        out = (result.stdout or "").strip()
        if not out:
            return False
        if "No tasks are running" in out:
            return False
        if "INFO:" in out:
            return False
        return True

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def build_completion_observation(
    dispatch_receipt: dict[str, Any],
    execution_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    request_id = dispatch_receipt.get("request_id")
    brief_id = dispatch_receipt.get("brief_id")
    handoff_id = dispatch_receipt.get("handoff_id")
    dispatch_status = dispatch_receipt.get("dispatch_status")
    attempted = bool(dispatch_receipt.get("dispatch_attempted"))

    result: dict[str, Any] = {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "dispatch_status": dispatch_status,
        "dispatch_attempted": attempted,
        "observed_at": observed_at,
    }

    if dispatch_status != "dispatched":
        result["completion_observation_status"] = "not_dispatched"
        result["blocking_reason"] = dispatch_receipt.get("blocking_reason") or dispatch_receipt.get("error") or "dispatch not successful"
        result["next_action"] = "Fix dispatch issue first, then retry dispatch."
        return result

    proc = dispatch_receipt.get("dispatch_process")
    pid = None
    process_running = None
    if isinstance(proc, dict) and isinstance(proc.get("pid"), int):
        pid = proc["pid"]
        process_running = _is_process_running(pid)

    logs = dispatch_receipt.get("dispatch_log_paths") if isinstance(dispatch_receipt.get("dispatch_log_paths"), dict) else {}
    stdout_tail = _tail(logs.get("stdout") if isinstance(logs, dict) else None)
    stderr_tail = _tail(logs.get("stderr") if isinstance(logs, dict) else None)

    result["dispatch_process"] = {
        "pid": pid,
        "running": process_running,
    }
    result["dispatch_log_tail"] = {
        "stdout": stdout_tail,
        "stderr": stderr_tail,
    }

    if execution_receipt and isinstance(execution_receipt, dict):
        ids_match = (
            execution_receipt.get("request_id") == request_id
            and execution_receipt.get("brief_id") == brief_id
            and execution_receipt.get("handoff_id") == handoff_id
        )
        if ids_match:
            result["execution_receipt_detected"] = True
            result["execution_status"] = execution_receipt.get("execution_status")
            result["completion_observation_status"] = "execution_receipt_available"
            result["next_action"] = "Proceed with owner final review summary."
            return result

    if process_running is True:
        result["completion_observation_status"] = "running_no_execution_receipt"
        result["next_action"] = "Wait for process completion and generate execution receipt."
        return result

    if process_running is False:
        result["completion_observation_status"] = "process_exited_no_execution_receipt"
        result["next_action"] = "Prepare execution receipt manually or inspect logs for failure."
        return result

    result["completion_observation_status"] = "unknown_process_state"
    result["next_action"] = "Check local process state manually and then prepare execution receipt."
    return result


def capture_completion(
    dispatch_receipt_path: str,
    execution_receipt_path: str | None,
    output_path: str,
) -> dict[str, Any]:
    dispatch_receipt = _load_json(Path(dispatch_receipt_path))
    execution_receipt = None
    if execution_receipt_path:
        p = Path(execution_receipt_path)
        if p.exists():
            execution_receipt = _load_json(p)

    observation = build_completion_observation(dispatch_receipt, execution_receipt)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(observation, ensure_ascii=False, indent=2), encoding="utf-8")
    return observation


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture post-dispatch completion-side observations.")
    parser.add_argument("--dispatch-receipt", default=str(DISPATCH_RECEIPT_PATH), help="Path to dispatch receipt JSON.")
    parser.add_argument(
        "--execution-receipt",
        default=str(EXECUTION_RECEIPT_PATH),
        help="Path to execution receipt JSON (optional if not exists).",
    )
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to completion observation JSON.")
    args = parser.parse_args()

    observation = capture_completion(args.dispatch_receipt, args.execution_receipt, args.output)
    print(json.dumps(observation, ensure_ascii=False, indent=2))
    print(f"\n[dispatch-completion-capture] saved: {args.output}")


if __name__ == "__main__":
    main()
