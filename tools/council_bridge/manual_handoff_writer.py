"""Semi-manual handoff artifact writer for tiny bridge v0.

This helper does not execute Codex or trigger automation.
It only prepares artifacts/council_bridge_handoff.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DRY_RUN_PATH = Path("artifacts") / "council_bridge_dry_run.json"
TEMPLATE_PATH = Path("docs") / "council-bridge-handoff-template.json"
OUTPUT_PATH = Path("artifacts") / "council_bridge_handoff.json"

APPROVED_BY_PATTERN = re.compile(r"^[a-z0-9_-]{3,32}$")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _next_handoff_id(output_path: Path, now: datetime) -> str:
    date_part = now.strftime("%Y%m%d")
    prefix = f"handoff-{date_part}-"
    next_seq = 1

    if output_path.exists():
        try:
            existing = _load_json(output_path)
            existing_id = existing.get("handoff_id")
            if isinstance(existing_id, str) and existing_id.startswith(prefix):
                tail = existing_id.removeprefix(prefix)
                if tail.isdigit():
                    next_seq = int(tail) + 1
        except Exception:
            next_seq = 1

    return f"{prefix}{next_seq:03d}"


def build_handoff_artifact(
    dry_run: dict[str, Any],
    template: dict[str, Any],
    approval_status: str,
    approved_by: str,
    notes: str,
    output_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    status = approval_status.strip()
    if status not in {"approved", "needs_fix", "rejected"}:
        raise ValueError("approval_status must be one of: approved, needs_fix, rejected.")
    if not APPROVED_BY_PATTERN.match(approved_by):
        raise ValueError("approved_by must match ^[a-z0-9_-]{3,32}$.")
    if not notes.strip():
        raise ValueError("notes must be non-empty.")

    current_time = now or datetime.now(timezone.utc).astimezone()
    artifact = copy.deepcopy(template)

    artifact["handoff_id"] = _next_handoff_id(output_path, current_time)
    artifact["request_id"] = dry_run.get("request_id")
    artifact["brief_id"] = dry_run.get("brief_id")
    artifact["approval_status"] = status
    artifact["approved_by"] = approved_by
    artifact["approved_at"] = current_time.isoformat(timespec="seconds")
    artifact["notes"] = notes.strip()
    artifact["validation_snapshot"] = {
        "dry_run_status": dry_run.get("status"),
        "dry_run_errors": dry_run.get("errors"),
    }

    dry_status = dry_run.get("status")
    dry_errors = dry_run.get("errors")
    dry_payload = dry_run.get("codex_ready_payload")

    if status == "approved":
        if dry_status != "valid":
            raise ValueError("approved requires dry_run status == valid.")
        if not isinstance(dry_errors, list) or len(dry_errors) != 0:
            raise ValueError("approved requires dry_run errors == [].")
        if not isinstance(dry_payload, dict):
            raise ValueError("approved requires non-null codex_ready_payload from dry_run.")
        artifact["codex_ready_payload"] = dry_payload
    else:
        artifact["codex_ready_payload"] = None

    return artifact


def write_handoff_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual handoff artifact writer (v0).")
    parser.add_argument("--approval-status", required=True, choices=["approved", "needs_fix", "rejected"])
    parser.add_argument("--approved-by", required=True, help="Reviewer id: ^[a-z0-9_-]{3,32}$.")
    parser.add_argument("--notes", required=True, help="Short audit note.")
    parser.add_argument("--dry-run", default=str(DRY_RUN_PATH), help="Path to dry-run artifact JSON.")
    parser.add_argument("--template", default=str(TEMPLATE_PATH), help="Path to handoff template JSON.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to output handoff artifact JSON.")
    args = parser.parse_args()

    dry_run = _load_json(Path(args.dry_run))
    template = _load_json(Path(args.template))
    output = Path(args.output)

    artifact = build_handoff_artifact(
        dry_run=dry_run,
        template=template,
        approval_status=args.approval_status,
        approved_by=args.approved_by,
        notes=args.notes,
        output_path=output,
    )
    write_handoff_artifact(output, artifact)

    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    print(f"\n[handoff-writer] saved: {output}")


if __name__ == "__main__":
    main()
