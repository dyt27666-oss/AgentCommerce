"""Semi-manual Feishu owner action writer (v0).

This helper prepares artifacts/council_feishu_owner_action.json.
It does not execute Codex or trigger orchestration.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_ARTIFACT = Path("artifacts") / "council_codex_dispatch_ready.json"
DEFAULT_OUTPUT_PATH = Path("artifacts") / "council_feishu_owner_action.json"
OWNER_ID_PATTERN = re.compile(r"^[a-z0-9_-]{3,32}$")
ALLOWED_ACTIONS = {"dispatch", "hold", "needs_fix", "reject"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def infer_source_state(source_data: dict[str, Any]) -> str:
    if "dispatch_ready" in source_data:
        return f"dispatch_ready={bool(source_data.get('dispatch_ready'))}"
    if "completion_observation_status" in source_data:
        return f"completion_observation_status={source_data.get('completion_observation_status')}"
    if "dispatch_status" in source_data and "dispatch_attempted" in source_data:
        return f"dispatch_status={source_data.get('dispatch_status')}"
    if "approval_status" in source_data:
        return f"approval_status={source_data.get('approval_status')}"
    return "unknown_source_state"


def build_owner_action_artifact(
    source_data: dict[str, Any],
    source_artifact_path: Path,
    owner_action: str,
    owner_id: str,
    notes: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    action = owner_action.strip()
    if action not in ALLOWED_ACTIONS:
        raise ValueError("owner_action must be one of: dispatch, hold, needs_fix, reject.")
    if not OWNER_ID_PATTERN.match(owner_id):
        raise ValueError("owner_id must match ^[a-z0-9_-]{3,32}$.")

    request_id = source_data.get("request_id")
    brief_id = source_data.get("brief_id")
    handoff_id = source_data.get("handoff_id")
    if request_id is None and brief_id is None and handoff_id is None:
        raise ValueError("source artifact must provide at least one identity field.")

    current_time = now or datetime.now(timezone.utc).astimezone()
    artifact = {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "owner_action": action,
        "source_artifact_path": source_artifact_path.as_posix(),
        "source_state": infer_source_state(source_data),
        "action_by": owner_id,
        "action_at": current_time.isoformat(timespec="seconds"),
        "notes": notes.strip(),
    }
    return artifact


def write_owner_action_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual Feishu owner action writer (v0).")
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--owner-id", required=True, help="Owner id: ^[a-z0-9_-]{3,32}$.")
    parser.add_argument("--notes", default="", help="Optional notes.")
    parser.add_argument("--source-artifact", default=str(DEFAULT_SOURCE_ARTIFACT), help="Source artifact path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Output action artifact path.")
    args = parser.parse_args()

    source_path = Path(args.source_artifact)
    source_data = _load_json(source_path)
    output = Path(args.output)

    artifact = build_owner_action_artifact(
        source_data=source_data,
        source_artifact_path=source_path,
        owner_action=args.action,
        owner_id=args.owner_id,
        notes=args.notes,
    )
    write_owner_action_artifact(output, artifact)

    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    print(f"\n[feishu-owner-action-writer] saved: {output.as_posix()}")


if __name__ == "__main__":
    main()

