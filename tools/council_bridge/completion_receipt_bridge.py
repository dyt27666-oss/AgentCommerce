"""Bridge completion observation to execution-receipt preparation (v0).

This helper is local and semi-manual:
1. reads handoff + dispatch receipt + completion observation
2. decides whether receipt preparation is appropriate now
3. writes a structured receipt-prep artifact

It does not auto-generate execution receipt from Codex output.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
DISPATCH_RECEIPT_PATH = Path("artifacts") / "council_codex_dispatch_receipt.json"
COMPLETION_PATH = Path("artifacts") / "council_codex_dispatch_completion.json"
OUTPUT_PATH = Path("artifacts") / "council_codex_receipt_prep.json"
EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _require_id(doc: dict[str, Any], key: str, prefix: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix}.{key} must be a non-empty string.")
    return value.strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_receipt_prep(
    handoff: dict[str, Any],
    dispatch_receipt: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    h_request = _require_id(handoff, "request_id", "handoff")
    h_brief = _require_id(handoff, "brief_id", "handoff")
    h_handoff = _require_id(handoff, "handoff_id", "handoff")

    d_request = _require_id(dispatch_receipt, "request_id", "dispatch_receipt")
    d_brief = _require_id(dispatch_receipt, "brief_id", "dispatch_receipt")
    d_handoff = _require_id(dispatch_receipt, "handoff_id", "dispatch_receipt")

    c_request = _require_id(completion, "request_id", "completion")
    c_brief = _require_id(completion, "brief_id", "completion")
    c_handoff = _require_id(completion, "handoff_id", "completion")

    if not (h_request == d_request == c_request and h_brief == d_brief == c_brief and h_handoff == d_handoff == c_handoff):
        return {
            "request_id": h_request,
            "brief_id": h_brief,
            "handoff_id": h_handoff,
            "completion_state": completion.get("completion_observation_status"),
            "receipt_prep_ready": False,
            "blocking_reason": "identity mismatch across handoff/dispatch/completion artifacts.",
            "recommended_next_action": "Fix artifact linkage before preparing execution receipt.",
            "source_artifact_paths": {
                "handoff": HANDOFF_PATH.as_posix(),
                "dispatch_receipt": DISPATCH_RECEIPT_PATH.as_posix(),
                "completion_observation": COMPLETION_PATH.as_posix(),
            },
            "generated_at": _now_iso(),
        }

    completion_state = completion.get("completion_observation_status")
    dispatch_status = dispatch_receipt.get("dispatch_status")

    prep_ready = False
    blocking_reason = None
    next_action = ""

    if completion_state == "execution_receipt_available":
        prep_ready = True
        next_action = "Execution receipt is already available. Proceed to owner final review."
    elif completion_state == "process_exited_no_execution_receipt":
        prep_ready = True
        next_action = "Prepare execution receipt now using execution_receipt_writer and dispatch logs."
    elif completion_state == "running_no_execution_receipt":
        prep_ready = False
        blocking_reason = "Codex process is still running; execution receipt should not be finalized yet."
        next_action = "Wait for completion, then run completion capture again."
    elif completion_state == "not_dispatched":
        prep_ready = False
        blocking_reason = completion.get("blocking_reason") or "dispatch was not successful."
        next_action = "Fix dispatch issue before execution receipt preparation."
    else:
        prep_ready = False
        blocking_reason = f"unsupported or unresolved completion state: {completion_state}"
        next_action = "Resolve completion observation state, then retry receipt-prep bridge."

    # Extra safety: if dispatch is explicitly blocked/failed, do not mark ready.
    if dispatch_status in {"blocked", "failed"}:
        prep_ready = False
        blocking_reason = dispatch_receipt.get("blocking_reason") or dispatch_receipt.get("error") or f"dispatch_status={dispatch_status}"
        next_action = "Fix dispatch issue first, then retry completion and receipt-prep bridge."

    artifact: dict[str, Any] = {
        "request_id": h_request,
        "brief_id": h_brief,
        "handoff_id": h_handoff,
        "completion_state": completion_state,
        "receipt_prep_ready": prep_ready,
        "recommended_next_action": next_action,
        "source_artifact_paths": {
            "handoff": HANDOFF_PATH.as_posix(),
            "dispatch_receipt": DISPATCH_RECEIPT_PATH.as_posix(),
            "completion_observation": COMPLETION_PATH.as_posix(),
            "execution_receipt": EXECUTION_RECEIPT_PATH.as_posix(),
        },
        "generated_at": _now_iso(),
    }
    if blocking_reason:
        artifact["blocking_reason"] = blocking_reason
    return artifact


def run_bridge(
    handoff_path: str,
    dispatch_receipt_path: str,
    completion_path: str,
    output_path: str,
) -> dict[str, Any]:
    handoff = _load_json(Path(handoff_path))
    dispatch_receipt = _load_json(Path(dispatch_receipt_path))
    completion = _load_json(Path(completion_path))
    prep = build_receipt_prep(handoff, dispatch_receipt, completion)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(prep, ensure_ascii=False, indent=2), encoding="utf-8")
    return prep


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge completion observation to execution-receipt prep.")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument("--dispatch-receipt", default=str(DISPATCH_RECEIPT_PATH), help="Path to dispatch receipt JSON.")
    parser.add_argument("--completion", default=str(COMPLETION_PATH), help="Path to completion observation JSON.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to output receipt-prep JSON.")
    args = parser.parse_args()

    prep = run_bridge(args.handoff, args.dispatch_receipt, args.completion, args.output)
    print(json.dumps(prep, ensure_ascii=False, indent=2))
    print(f"\n[completion-receipt-bridge] saved: {args.output}")
    if prep.get("receipt_prep_ready") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
