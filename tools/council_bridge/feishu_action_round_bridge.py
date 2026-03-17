"""Semi-manual Feishu action -> round bridge helper (v0).

Reads owner action artifact and prepares a structured next-step bridge summary.
No callbacks, no orchestration, no automatic tool execution.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_PATH = Path("artifacts") / "council_feishu_owner_action.json"
OUTPUT_PATH = Path("artifacts") / "council_feishu_action_round_bridge.json"
ALLOWED_ACTIONS = {"dispatch", "hold", "needs_fix", "reject"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _require_non_empty_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value.strip()


def _action_plan(owner_action: str) -> dict[str, Any]:
    if owner_action == "dispatch":
        return {
            "round_flow_state": "continue",
            "recommended_next_step": "Prepare dispatch-ready artifact, then run local dispatch.",
            "next_tool_paths": [
                "tools/council_bridge/dispatch_prep_adapter.py",
                "tools/council_bridge/codex_dispatch_runner.py",
            ],
            "next_artifact_paths": [
                "artifacts/council_codex_dispatch_ready.json",
                "artifacts/council_codex_dispatch_receipt.json",
            ],
        }
    if owner_action == "hold":
        return {
            "round_flow_state": "pause",
            "recommended_next_step": "Pause this round and wait for owner follow-up action.",
            "next_tool_paths": [],
            "next_artifact_paths": [],
        }
    if owner_action == "needs_fix":
        return {
            "round_flow_state": "loop_back",
            "recommended_next_step": "Return to handoff/input correction and regenerate artifacts.",
            "next_tool_paths": [
                "tools/council_bridge/manual_handoff_writer.py",
                "tools/council_bridge/readonly_stub.py",
            ],
            "next_artifact_paths": [
                "artifacts/council_bridge_dry_run.json",
                "artifacts/council_bridge_handoff.json",
            ],
        }
    return {
        "round_flow_state": "stop",
        "recommended_next_step": "Stop current round and reopen scope/decision with owner.",
        "next_tool_paths": [],
        "next_artifact_paths": [],
    }


def build_round_bridge(action_data: dict[str, Any], source_path: Path) -> dict[str, Any]:
    request_id = _require_non_empty_str(action_data, "request_id")
    brief_id = _require_non_empty_str(action_data, "brief_id")
    handoff_id = _require_non_empty_str(action_data, "handoff_id")
    owner_action = _require_non_empty_str(action_data, "owner_action")
    if owner_action not in ALLOWED_ACTIONS:
        raise ValueError("owner_action must be one of: dispatch, hold, needs_fix, reject.")
    action_by = _require_non_empty_str(action_data, "action_by")

    plan = _action_plan(owner_action)
    return {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "owner_action": owner_action,
        "action_by": action_by,
        "action_at": action_data.get("action_at"),
        "source_action_artifact_path": source_path.as_posix(),
        "source_artifact_path": action_data.get("source_artifact_path"),
        "source_state": action_data.get("source_state"),
        "round_flow_state": plan["round_flow_state"],
        "recommended_next_step": plan["recommended_next_step"],
        "next_tool_paths": plan["next_tool_paths"],
        "next_artifact_paths": plan["next_artifact_paths"],
        "notes": action_data.get("notes", ""),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def write_round_bridge(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual Feishu action round bridge helper (v0).")
    parser.add_argument("--action-artifact", default=str(ACTION_PATH), help="Path to owner action artifact JSON.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output bridge summary JSON path.")
    args = parser.parse_args()

    source = Path(args.action_artifact)
    action_data = _load_json(source)
    result = build_round_bridge(action_data, source_path=source)
    output = Path(args.output)
    write_round_bridge(output, result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[feishu-action-round-bridge] saved: {output.as_posix()}")


if __name__ == "__main__":
    main()

