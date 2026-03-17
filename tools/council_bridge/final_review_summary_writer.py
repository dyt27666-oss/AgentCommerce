"""Semi-manual final owner review summary writer for bridge v0.

This helper does not execute Codex or external systems.
It prepares artifacts/council_owner_final_review_summary.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
RECEIPT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"
PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
OUTPUT_PATH = Path("artifacts") / "council_owner_final_review_summary.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _require_non_empty_str(obj: dict[str, Any], key: str, prefix: str = "") -> str:
    value = obj.get(key)
    name = f"{prefix}{key}"
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _build_scope_check(handoff: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    allowed_files = []
    payload = handoff.get("codex_ready_payload")
    if isinstance(payload, dict) and isinstance(payload.get("allowed_files"), list):
        allowed_files = [x for x in payload["allowed_files"] if isinstance(x, str) and x.strip()]
    changed_files = receipt.get("changed_files", [])
    if not isinstance(changed_files, list):
        changed_files = []
    changed_files = [x for x in changed_files if isinstance(x, str) and x.strip()]

    in_allowed_scope = all(x in allowed_files for x in changed_files) if changed_files else True
    cc = receipt.get("constraints_compliance", {})
    constraints_compliant = bool(cc.get("compliant")) if isinstance(cc, dict) else False
    cc_note = cc.get("note", "") if isinstance(cc, dict) else ""

    if in_allowed_scope and constraints_compliant:
        note = "Changed files are in allowed scope and constraints are compliant."
    elif not in_allowed_scope and constraints_compliant:
        note = "Constraint note is compliant, but changed_files include out-of-scope paths."
    elif in_allowed_scope and not constraints_compliant:
        note = "Files are in allowed scope, but constraints are marked non-compliant."
    else:
        note = "Scope and constraints both need owner attention."
    if isinstance(cc_note, str) and cc_note.strip():
        note = f"{note} {cc_note.strip()}"

    return {
        "in_allowed_scope": in_allowed_scope,
        "constraints_compliant": constraints_compliant,
        "note": note,
    }


def build_final_review_summary(
    handoff: dict[str, Any],
    receipt: dict[str, Any],
    final_decision: str,
    key_reason: str,
    next_action: str,
    notes: str | None = None,
    prompt_path: str | None = None,
) -> dict[str, Any]:
    decision = final_decision.strip()
    if decision not in {"approved", "revision_request", "needs_fix", "rejected"}:
        raise ValueError("final_decision must be one of: approved, revision_request, needs_fix, rejected.")
    if not key_reason or not key_reason.strip():
        raise ValueError("key_reason must be non-empty.")
    if not next_action or not next_action.strip():
        raise ValueError("next_action must be non-empty.")

    h_request = _require_non_empty_str(handoff, "request_id", "handoff.")
    h_brief = _require_non_empty_str(handoff, "brief_id", "handoff.")
    h_handoff_id = _require_non_empty_str(handoff, "handoff_id", "handoff.")

    r_request = _require_non_empty_str(receipt, "request_id", "receipt.")
    r_brief = _require_non_empty_str(receipt, "brief_id", "receipt.")
    r_handoff_id = _require_non_empty_str(receipt, "handoff_id", "receipt.")
    r_status = _require_non_empty_str(receipt, "execution_status", "receipt.")

    if (h_request != r_request) or (h_brief != r_brief) or (h_handoff_id != r_handoff_id):
        raise ValueError("Identity mismatch between handoff and receipt.")

    scope_check = _build_scope_check(handoff, receipt)
    result: dict[str, Any] = {
        "request_id": h_request,
        "brief_id": h_brief,
        "handoff_id": h_handoff_id,
        "final_owner_decision": decision,
        "execution_status": r_status,
        "scope_compliance_check": scope_check,
        "key_reason": key_reason.strip(),
        "next_action": next_action.strip(),
        "notes": (notes or "").strip(),
    }

    if prompt_path:
        result["prompt_artifact_path"] = prompt_path
        result["prompt_artifact_used"] = Path(prompt_path).exists()
    return result


def write_final_review_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual final owner review summary writer (v0).")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument("--receipt", default=str(RECEIPT_PATH), help="Path to execution receipt JSON.")
    parser.add_argument(
        "--prompt",
        default=str(PROMPT_PATH),
        help="Optional prompt artifact path to record in summary.",
    )
    parser.add_argument("--final-decision", required=True, choices=["approved", "revision_request", "needs_fix", "rejected"])
    parser.add_argument("--key-reason", required=True, help="1-2 line key reason for final decision.")
    parser.add_argument("--next-action", required=True, help="Owner next action.")
    parser.add_argument("--notes", default="", help="Optional additional notes.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output summary JSON path.")
    args = parser.parse_args()

    handoff = _load_json(Path(args.handoff))
    receipt = _load_json(Path(args.receipt))
    summary = build_final_review_summary(
        handoff=handoff,
        receipt=receipt,
        final_decision=args.final_decision,
        key_reason=args.key_reason,
        next_action=args.next_action,
        notes=args.notes,
        prompt_path=args.prompt if args.prompt else None,
    )
    output = Path(args.output)
    write_final_review_summary(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[final-review-summary-writer] saved: {output}")


if __name__ == "__main__":
    main()
