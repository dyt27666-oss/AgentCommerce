"""Semi-manual execution receipt writer for tiny bridge v0.

This helper does not execute Codex and does not call external services.
It only prepares artifacts/council_codex_execution_receipt.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
OUTPUT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _parse_bool(value: str) -> bool:
    text = value.strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError("constraints-compliant must be true/false.")


def _split_csv(values: str | None) -> list[str]:
    if not values:
        return []
    parts = [x.strip() for x in values.split(",")]
    return [x for x in parts if x]


def build_execution_receipt(
    handoff: dict[str, Any],
    execution_status: str,
    changed_files: list[str],
    summary: str,
    next_step_suggestion: str,
    constraints_compliant: bool,
    constraints_note: str,
    blocked_reason: str | None = None,
    partial_notes: str | None = None,
    warnings: list[str] | None = None,
    validation_results: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    status = execution_status.strip()
    if status not in {"completed", "partial", "blocked", "not_executed"}:
        raise ValueError("execution_status must be one of: completed, partial, blocked, not_executed.")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary must be a non-empty string.")
    if not isinstance(next_step_suggestion, str) or not next_step_suggestion.strip():
        raise ValueError("next_step_suggestion must be a non-empty string.")
    if not isinstance(constraints_note, str) or not constraints_note.strip():
        raise ValueError("constraints_note must be a non-empty string.")
    if any(not isinstance(x, str) or not x.strip() for x in changed_files):
        raise ValueError("changed_files must contain only non-empty strings.")

    for key in ["request_id", "brief_id", "handoff_id"]:
        value = handoff.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"handoff.{key} must be a non-empty string.")

    if status == "blocked" and (not blocked_reason or not blocked_reason.strip()):
        raise ValueError("blocked status requires blocked_reason.")
    if status == "partial" and (not partial_notes or not partial_notes.strip()):
        raise ValueError("partial status requires partial_notes.")

    current_time = now or datetime.now(timezone.utc).astimezone()
    receipt: dict[str, Any] = {
        "request_id": handoff["request_id"],
        "brief_id": handoff["brief_id"],
        "handoff_id": handoff["handoff_id"],
        "execution_status": status,
        "changed_files": changed_files,
        "constraints_compliance": {
            "compliant": constraints_compliant,
            "note": constraints_note.strip(),
        },
        "summary": summary.strip(),
        "next_step_suggestion": next_step_suggestion.strip(),
        "generated_at": current_time.isoformat(timespec="seconds"),
    }

    if blocked_reason and blocked_reason.strip():
        receipt["blocked_reason"] = blocked_reason.strip()
    if partial_notes and partial_notes.strip():
        receipt["partial_notes"] = partial_notes.strip()
    if warnings:
        receipt["warnings"] = [x.strip() for x in warnings if isinstance(x, str) and x.strip()]
    if validation_results:
        receipt["validation_results"] = [
            x.strip() for x in validation_results if isinstance(x, str) and x.strip()
        ]

    return receipt


def write_execution_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual execution receipt writer (v0).")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument(
        "--execution-status",
        required=True,
        choices=["completed", "partial", "blocked", "not_executed"],
    )
    parser.add_argument(
        "--changed-files",
        default="",
        help="Comma-separated changed files. Leave empty for no changes.",
    )
    parser.add_argument("--summary", required=True, help="Short execution summary.")
    parser.add_argument("--next-step-suggestion", required=True, help="Owner-facing next step suggestion.")
    parser.add_argument(
        "--constraints-compliant",
        required=True,
        help="true/false",
    )
    parser.add_argument("--constraints-note", required=True, help="Constraint compliance note.")
    parser.add_argument("--blocked-reason", default=None, help="Required when status is blocked.")
    parser.add_argument("--partial-notes", default=None, help="Required when status is partial.")
    parser.add_argument(
        "--warnings",
        default="",
        help="Optional comma-separated warning messages.",
    )
    parser.add_argument(
        "--validation-results",
        default="",
        help="Optional comma-separated validation result lines.",
    )
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output receipt JSON path.")
    args = parser.parse_args()

    handoff = _load_json(Path(args.handoff))
    receipt = build_execution_receipt(
        handoff=handoff,
        execution_status=args.execution_status,
        changed_files=_split_csv(args.changed_files),
        summary=args.summary,
        next_step_suggestion=args.next_step_suggestion,
        constraints_compliant=_parse_bool(args.constraints_compliant),
        constraints_note=args.constraints_note,
        blocked_reason=args.blocked_reason,
        partial_notes=args.partial_notes,
        warnings=_split_csv(args.warnings),
        validation_results=_split_csv(args.validation_results),
    )
    output = Path(args.output)
    write_execution_receipt(output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f"\n[execution-receipt-writer] saved: {output}")


if __name__ == "__main__":
    main()
