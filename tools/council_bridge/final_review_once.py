"""Owner final decision one-command close helper (v0).

This helper is not an auto-approval engine.
It only wraps the existing final review summary generation into one local entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.council_bridge.final_review_summary_writer import (
    build_final_review_summary,
    write_final_review_summary,
)


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
RECEIPT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"
PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
SUMMARY_OUTPUT_PATH = Path("artifacts") / "council_owner_final_review_summary.json"
RESULT_OUTPUT_PATH = Path("artifacts") / "council_final_review_once_result.json"

CONTINUE_ONCE_PATH = Path("artifacts") / "council_feishu_continue_once_result.json"
COMPLETION_PATH = Path("artifacts") / "council_codex_dispatch_completion.json"
RECEIPT_SKELETON_PATH = Path("artifacts") / "council_codex_execution_receipt_skeleton.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _pick_identity(*sources: dict[str, Any] | None) -> dict[str, str | None]:
    request_id = None
    brief_id = None
    handoff_id = None
    for src in sources:
        if not isinstance(src, dict):
            continue
        request_id = request_id or src.get("request_id")
        brief_id = brief_id or src.get("brief_id")
        handoff_id = handoff_id or src.get("handoff_id")
    return {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
    }


def run_final_review_once(
    *,
    final_decision: str,
    key_reason: str,
    next_action: str,
    notes: str = "",
    handoff_path: Path = HANDOFF_PATH,
    receipt_path: Path = RECEIPT_PATH,
    prompt_path: Path = PROMPT_PATH,
    summary_output_path: Path = SUMMARY_OUTPUT_PATH,
    continue_once_path: Path = CONTINUE_ONCE_PATH,
    completion_path: Path = COMPLETION_PATH,
    receipt_skeleton_path: Path = RECEIPT_SKELETON_PATH,
) -> dict[str, Any]:
    handoff = _load_json(handoff_path)
    receipt = _load_json(receipt_path)

    summary = build_final_review_summary(
        handoff=handoff,
        receipt=receipt,
        final_decision=final_decision,
        key_reason=key_reason,
        next_action=next_action,
        notes=notes,
        prompt_path=prompt_path.as_posix() if prompt_path.exists() else None,
    )
    write_final_review_summary(summary_output_path, summary)

    continue_once = _safe_load(continue_once_path)
    completion = _safe_load(completion_path)
    receipt_skeleton = _safe_load(receipt_skeleton_path)

    inherited_identity = _pick_identity(summary, continue_once, completion, receipt_skeleton, handoff, receipt)
    summary_status = "written"
    if final_decision not in {"approved", "revision_request", "needs_fix", "rejected"}:
        summary_status = "invalid_decision"

    result = {
        "final_decision": final_decision,
        "final_review_summary_artifact": summary_output_path.as_posix(),
        "inherited_identity": inherited_identity,
        "source_artifacts": {
            "handoff": handoff_path.as_posix(),
            "execution_receipt": receipt_path.as_posix(),
            "continue_once_result": continue_once_path.as_posix(),
            "completion": completion_path.as_posix(),
            "execution_receipt_skeleton": receipt_skeleton_path.as_posix(),
        },
        "summary_status": summary_status,
        "next_manual_action": (
            "Round can be closed and archived." if final_decision == "approved" else "Follow decision outcome and start next correction round."
        ),
        "notes": notes.strip(),
        "generated_at": _now_iso(),
    }
    return result


def write_final_review_once_result(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Owner final review one-command close helper (v0).")
    parser.add_argument(
        "--final-decision",
        required=True,
        choices=["approved", "revision_request", "needs_fix", "rejected"],
    )
    parser.add_argument("--key-reason", required=True)
    parser.add_argument("--next-action", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH))
    parser.add_argument("--receipt", default=str(RECEIPT_PATH))
    parser.add_argument("--prompt", default=str(PROMPT_PATH))
    parser.add_argument("--summary-output", default=str(SUMMARY_OUTPUT_PATH))
    parser.add_argument("--output", default=str(RESULT_OUTPUT_PATH))
    parser.add_argument("--continue-once-result", default=str(CONTINUE_ONCE_PATH))
    parser.add_argument("--completion", default=str(COMPLETION_PATH))
    parser.add_argument("--receipt-skeleton", default=str(RECEIPT_SKELETON_PATH))
    args = parser.parse_args()

    result = run_final_review_once(
        final_decision=args.final_decision,
        key_reason=args.key_reason,
        next_action=args.next_action,
        notes=args.notes,
        handoff_path=Path(args.handoff),
        receipt_path=Path(args.receipt),
        prompt_path=Path(args.prompt),
        summary_output_path=Path(args.summary_output),
        continue_once_path=Path(args.continue_once_result),
        completion_path=Path(args.completion),
        receipt_skeleton_path=Path(args.receipt_skeleton),
    )
    output = Path(args.output)
    write_final_review_once_result(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[final-review-once] saved: {output.as_posix()}")


if __name__ == "__main__":
    main()

