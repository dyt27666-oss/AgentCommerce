"""Convert approved handoff artifact into a Codex-ready prompt text.

This utility is semi-manual only:
1. reads handoff artifact
2. validates executable approved status
3. writes a prompt text file for owner copy/use

It does not execute Codex or trigger any runtime automation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import json
from typing import Any


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
OUTPUT_PATH = Path("artifacts") / "council_codex_prompt.txt"


def load_handoff(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("handoff artifact root must be a JSON object.")
    return data


def _required_non_empty_string(obj: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    value = obj.get(key)
    name = f"{prefix}{key}"
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string.")


def _required_string_list(obj: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    value = obj.get(key)
    name = f"{prefix}{key}"
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty list of strings.")
        return
    if any(not isinstance(v, str) or not v.strip() for v in value):
        errors.append(f"{name} must contain only non-empty strings.")


def validate_executable_handoff(handoff: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    _required_non_empty_string(handoff, "request_id", errors)
    _required_non_empty_string(handoff, "brief_id", errors)
    _required_non_empty_string(handoff, "handoff_id", errors)
    _required_non_empty_string(handoff, "approval_status", errors)
    _required_non_empty_string(handoff, "notes", errors)

    status = handoff.get("approval_status")
    if status != "approved":
        errors.append(
            "handoff is not executable: approval_status must be 'approved'."
        )

    snapshot = handoff.get("validation_snapshot")
    if not isinstance(snapshot, dict):
        errors.append("validation_snapshot must be an object.")
    else:
        if snapshot.get("dry_run_status") != "valid":
            errors.append("dry_run_status must be 'valid' for executable handoff.")
        dry_errors = snapshot.get("dry_run_errors")
        if not isinstance(dry_errors, list) or len(dry_errors) != 0:
            errors.append("dry_run_errors must be an empty list for executable handoff.")

    payload = handoff.get("codex_ready_payload")
    if not isinstance(payload, dict):
        errors.append("codex_ready_payload must be non-null for approved handoff.")
        return errors

    _required_non_empty_string(payload, "goal", errors, prefix="codex_ready_payload.")
    _required_string_list(payload, "allowed_files", errors, prefix="codex_ready_payload.")
    _required_string_list(payload, "constraints", errors, prefix="codex_ready_payload.")
    _required_string_list(payload, "validation_steps", errors, prefix="codex_ready_payload.")
    _required_string_list(payload, "delivery_format", errors, prefix="codex_ready_payload.")

    return errors


def build_codex_prompt(handoff: dict[str, Any]) -> str:
    errors = validate_executable_handoff(handoff)
    if errors:
        raise ValueError("Cannot build Codex prompt from handoff:\n- " + "\n- ".join(errors))

    payload = handoff["codex_ready_payload"]
    request_id = handoff["request_id"]
    brief_id = handoff["brief_id"]
    handoff_id = handoff["handoff_id"]
    notes = handoff["notes"]

    def _lines(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items)

    prompt = (
        "You are executing an approved semi-manual bridge handoff.\n\n"
        f"Execution IDs:\n- request_id: {request_id}\n- brief_id: {brief_id}\n- handoff_id: {handoff_id}\n\n"
        "Objective:\n"
        f"- {payload['goal']}\n\n"
        "Allowed Files (hard boundary):\n"
        f"{_lines(payload['allowed_files'])}\n\n"
        "Constraints (hard boundary):\n"
        f"{_lines(payload['constraints'])}\n\n"
        "Validation Steps:\n"
        f"{_lines(payload['validation_steps'])}\n\n"
        "Delivery Format:\n"
        f"{_lines(payload['delivery_format'])}\n\n"
        "Owner Notes / Boundaries:\n"
        f"- {notes}\n\n"
        "Important:\n"
        "- Do not operate outside allowed_files.\n"
        "- If blocked by constraints or missing scope, stop and report clearly.\n"
        "- Return an execution receipt-style summary after work."
    )
    return prompt


def export_codex_prompt(handoff_path: str, output_path: str) -> str:
    handoff = load_handoff(handoff_path)
    prompt = build_codex_prompt(handoff)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding="utf-8")
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Codex-ready prompt from approved handoff artifact.")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to output prompt text file.")
    parser.add_argument("--print", action="store_true", dest="print_prompt", help="Print prompt content.")
    args = parser.parse_args()

    prompt = export_codex_prompt(args.handoff, args.output)
    print(f"[prompt-adapter] saved: {args.output}")
    if args.print_prompt:
        print("\n" + prompt)


if __name__ == "__main__":
    main()
