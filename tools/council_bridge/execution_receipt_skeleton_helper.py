"""Execution receipt skeleton helper (v0).

This helper pre-fills a skeleton artifact only.
It does not generate final execution receipt, review decision, or approval.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISPATCH_RECEIPT_PATH = Path("artifacts") / "council_codex_dispatch_receipt.json"
COMPLETION_PATH = Path("artifacts") / "council_codex_dispatch_completion.json"
CONTINUE_ONCE_PATH = Path("artifacts") / "council_feishu_continue_once_result.json"
HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
OUTPUT_PATH = Path("artifacts") / "council_codex_execution_receipt_skeleton.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _pick_identity(*sources: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    request_id = None
    brief_id = None
    handoff_id = None
    for src in sources:
        if not isinstance(src, dict):
            continue
        request_id = request_id or src.get("request_id")
        brief_id = brief_id or src.get("brief_id")
        handoff_id = handoff_id or src.get("handoff_id")
    return request_id, brief_id, handoff_id


def _identity_status(
    request_id: str | None,
    brief_id: str | None,
    handoff_id: str | None,
    *sources: dict[str, Any] | None,
) -> str:
    present = [x for x in (request_id, brief_id, handoff_id) if isinstance(x, str) and x.strip()]
    if len(present) < 3:
        return "partial_missing"
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key, val in [("request_id", request_id), ("brief_id", brief_id), ("handoff_id", handoff_id)]:
            src_val = src.get(key)
            if isinstance(src_val, str) and src_val.strip() and src_val != val:
                return "mismatch_detected"
    return "matched"


def build_execution_receipt_skeleton(
    *,
    dispatch_receipt: dict[str, Any] | None,
    completion: dict[str, Any] | None,
    continue_once_result: dict[str, Any] | None,
    handoff: dict[str, Any] | None,
    source_paths: dict[str, str],
) -> dict[str, Any]:
    request_id, brief_id, handoff_id = _pick_identity(
        handoff, continue_once_result, dispatch_receipt, completion
    )
    identity_status = _identity_status(
        request_id, brief_id, handoff_id, continue_once_result, completion, dispatch_receipt, handoff
    )

    dispatch_status = None
    completion_state = None
    notes: list[str] = []

    if isinstance(dispatch_receipt, dict):
        dispatch_status = dispatch_receipt.get("dispatch_status")
    else:
        notes.append("dispatch receipt missing; dispatch_status not prefilled.")

    if isinstance(completion, dict):
        completion_state = completion.get("completion_observation_status")
    else:
        notes.append("completion artifact missing; completion_state not prefilled.")

    if isinstance(continue_once_result, dict) and continue_once_result.get("completion_check_attempted") is False:
        notes.append("continue_once did not run completion check in this round.")

    if identity_status == "partial_missing":
        notes.append("identity linkage is partial; owner should verify request_id/brief_id/handoff_id manually.")
    elif identity_status == "mismatch_detected":
        notes.append("identity mismatch detected across source artifacts; owner must resolve before final receipt.")

    source_artifacts = {
        "dispatch_receipt": {
            "path": source_paths["dispatch_receipt"],
            "exists": isinstance(dispatch_receipt, dict),
        },
        "completion": {
            "path": source_paths["completion"],
            "exists": isinstance(completion, dict),
        },
        "continue_once_result": {
            "path": source_paths["continue_once_result"],
            "exists": isinstance(continue_once_result, dict),
        },
        "handoff": {
            "path": source_paths["handoff"],
            "exists": isinstance(handoff, dict),
        },
    }

    skeleton = {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "dispatch_status": dispatch_status,
        "completion_state": completion_state,
        "execution_receipt_status": "skeleton_only",
        "source_artifacts": source_artifacts,
        "identity_linkage_status": identity_status,
        "suggested_owner_fill_fields": [
            "execution_status",
            "changed_files",
            "constraints_compliance.compliant",
            "constraints_compliance.note",
            "summary",
            "next_step_suggestion",
            "validation_results (optional)",
            "warnings (optional)",
            "blocked_reason / partial_notes (when applicable)",
        ],
        "notes": notes,
        "generated_at": _now_iso(),
    }
    return skeleton


def write_skeleton(path: Path, skeleton: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate execution receipt skeleton artifact (v0).")
    parser.add_argument("--dispatch-receipt", default=str(DISPATCH_RECEIPT_PATH))
    parser.add_argument("--completion", default=str(COMPLETION_PATH))
    parser.add_argument("--continue-once-result", default=str(CONTINUE_ONCE_PATH))
    parser.add_argument("--handoff", default=str(HANDOFF_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    dispatch_receipt_path = Path(args.dispatch_receipt)
    completion_path = Path(args.completion)
    continue_once_path = Path(args.continue_once_result)
    handoff_path = Path(args.handoff)

    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt=_safe_load(dispatch_receipt_path),
        completion=_safe_load(completion_path),
        continue_once_result=_safe_load(continue_once_path),
        handoff=_safe_load(handoff_path),
        source_paths={
            "dispatch_receipt": dispatch_receipt_path.as_posix(),
            "completion": completion_path.as_posix(),
            "continue_once_result": continue_once_path.as_posix(),
            "handoff": handoff_path.as_posix(),
        },
    )
    output = Path(args.output)
    write_skeleton(output, skeleton)
    print(json.dumps(skeleton, ensure_ascii=False, indent=2))
    print(f"\n[execution-receipt-skeleton-helper] saved: {output.as_posix()}")


if __name__ == "__main__":
    main()
