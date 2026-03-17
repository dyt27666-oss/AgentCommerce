"""Owner-confirmed execution dispatch engine v0.1."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.execution_dispatch_adapter import dispatch_from_execution_brief
from tools.council_bridge.execution_handoff_gate import validate_execution_handoff_gate
from tools.council_bridge.execution_receipt_v0_1 import build_execution_receipt_v0_1, write_execution_receipt_v0_1
from tools.council_bridge.handoff_execution_brief_mapper import build_execution_brief, write_execution_brief


DEFAULT_DISPATCH_RESULT_PATH = Path("artifacts") / "council_execution_dispatch_result.json"
DEFAULT_RUNTIME_STATUS_PATH = Path("artifacts") / "council_execution_runtime_status.json"
DEFAULT_EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_execution_receipt.json"
DEFAULT_EXECUTION_BRIEF_PATH = Path("artifacts") / "council_execution_brief.json"

ALLOWED_CONFIRM_LANES = {"owner", "bridge"}
ALLOWED_STAGES = {"execution_dispatch"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def dispatch_owner_confirmed_execution(
    *,
    handoff_artifact_path: Path,
    trigger: dict[str, Any],
    confirmed_by: str,
    confirmed_by_lane: str,
    current_stage: str,
    reason: str,
    dispatch_result_path: Path = DEFAULT_DISPATCH_RESULT_PATH,
    runtime_status_path: Path = DEFAULT_RUNTIME_STATUS_PATH,
    execution_receipt_path: Path = DEFAULT_EXECUTION_RECEIPT_PATH,
    execution_brief_path: Path = DEFAULT_EXECUTION_BRIEF_PATH,
    codex_command: str = "codex.cmd",
    codex_args: list[str] | None = None,
    dispatch_mode: str = "spawn",
    timeout_sec: int = 120,
    dispatch_func=None,
    brief_builder=None,
) -> dict[str, Any]:
    dispatch_func = dispatch_func or dispatch_from_execution_brief
    brief_builder = brief_builder or build_execution_brief
    execution_id = f"exec-{uuid.uuid4().hex[:10]}"
    ts = _now_iso()
    dispatch_result: dict[str, Any] = {
        "execution_id": execution_id,
        "source_handoff_id": None,
        "execution_brief_id": None,
        "dispatch_status": "blocked",
        "dispatch_error": "",
        "execution_status": "not_started",
        "executed_actions_summary": [],
        "changed_files": [],
        "touched_resources": [],
        "risk_flags": [],
        "next_action": "",
        "confirmed_by": confirmed_by,
        "confirmed_by_lane": confirmed_by_lane,
        "reason": reason,
        "timestamp": ts,
    }

    def block(msg: str, next_action: str) -> dict[str, Any]:
        dispatch_result["dispatch_status"] = "blocked"
        dispatch_result["dispatch_error"] = msg
        dispatch_result["execution_status"] = "not_started"
        dispatch_result["next_action"] = next_action
        _write_json(dispatch_result_path, dispatch_result)
        runtime = {
            "execution_id": execution_id,
            "source_handoff_id": dispatch_result["source_handoff_id"],
            "dispatch_status": "blocked",
            "execution_status": "not_started",
            "status_note": msg,
            "timestamp": _now_iso(),
        }
        _write_json(runtime_status_path, runtime)
        receipt = build_execution_receipt_v0_1(
            execution_id=execution_id,
            source_handoff_id=str(dispatch_result["source_handoff_id"] or ""),
            before_execution_state="blocked_before_start",
            execution_status="not_executed",
            executed_actions_summary=[],
            changed_files=[],
            touched_resources=[],
            risk_flags=["dispatch_blocked"],
            receipt_status="recorded",
            next_action=next_action,
        )
        write_execution_receipt_v0_1(receipt, execution_receipt_path)
        return dispatch_result

    if confirmed_by_lane not in ALLOWED_CONFIRM_LANES:
        return block("confirmed_by_lane must be owner/bridge.", "Use owner/bridge protocol confirmation.")
    if current_stage not in ALLOWED_STAGES:
        return block(f"stage {current_stage} not allowed for execution dispatch.", "Switch to execution_dispatch stage.")
    if not trigger.get("is_trigger") or not trigger.get("authorized"):
        return block("missing explicit authorized execution trigger.", "Send confirm_execution_dispatch via owner protocol.")

    handoff = _load_json(handoff_artifact_path)
    dispatch_result["source_handoff_id"] = handoff.get("handoff_id")

    gate = validate_execution_handoff_gate(artifact=handoff, current_stage="execution_gate", trigger=trigger)
    if not gate.get("execution_handoff_ready"):
        return block(
            str(gate.get("blocked_reason") or "execution handoff gate failed."),
            "Fix gate blockers then re-dispatch.",
        )

    try:
        brief = brief_builder(handoff, gate)
        write_execution_brief(brief, execution_brief_path)
    except Exception as exc:
        return block(f"execution brief generation failed: {exc}", "Fix handoff/brief fields and retry.")

    dispatch_result["execution_brief_id"] = str(brief.get("source_handoff_id") or handoff.get("handoff_id"))
    dispatch_result["touched_resources"] = [execution_brief_path.as_posix()]
    dispatch_result["executed_actions_summary"].append("execution brief generated")

    try:
        receipt = dispatch_func(
            brief=brief,
            codex_command=codex_command,
            codex_args=codex_args,
            dispatch_mode=dispatch_mode,
            timeout_sec=timeout_sec,
        )
    except Exception as exc:
        return block(f"execution dispatch adapter failed: {exc}", "Inspect adapter/runtime and retry.")

    dispatch_status = str(receipt.get("dispatch_status") or "failed")
    dispatch_result["dispatch_status"] = "accepted" if dispatch_status == "dispatched" else "failed"
    dispatch_result["execution_status"] = "started" if dispatch_status == "dispatched" else "failed"
    dispatch_result["dispatch_error"] = "" if dispatch_status == "dispatched" else str(receipt.get("error") or receipt.get("blocking_reason") or "dispatch failed")
    dispatch_result["executed_actions_summary"].append(f"dispatch_status={dispatch_status}")
    dispatch_result["touched_resources"].append("artifacts/council_execution_dispatch_receipt.json")
    dispatch_result["next_action"] = (
        "Monitor runtime and produce final execution receipt."
        if dispatch_status == "dispatched"
        else "Inspect dispatch logs/errors and retry with corrected inputs."
    )
    if dispatch_status != "dispatched":
        dispatch_result["risk_flags"].append("dispatch_failed")

    _write_json(dispatch_result_path, dispatch_result)

    runtime = {
        "execution_id": execution_id,
        "source_handoff_id": dispatch_result["source_handoff_id"],
        "dispatch_status": dispatch_result["dispatch_status"],
        "execution_status": dispatch_result["execution_status"],
        "status_note": dispatch_result["next_action"],
        "timestamp": _now_iso(),
    }
    _write_json(runtime_status_path, runtime)

    receipt_v01 = build_execution_receipt_v0_1(
        execution_id=execution_id,
        source_handoff_id=str(dispatch_result["source_handoff_id"] or ""),
        before_execution_state="dispatch_accepted" if dispatch_status == "dispatched" else "dispatch_failed",
        execution_status="started" if dispatch_status == "dispatched" else "failed",
        executed_actions_summary=dispatch_result["executed_actions_summary"],
        changed_files=[],
        touched_resources=dispatch_result["touched_resources"],
        risk_flags=dispatch_result["risk_flags"],
        receipt_status="recorded",
        next_action=dispatch_result["next_action"],
    )
    write_execution_receipt_v0_1(receipt_v01, execution_receipt_path)
    return dispatch_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Owner-confirmed execution dispatch v0.1")
    parser.add_argument("--handoff", required=True, help="Path to handoff artifact JSON.")
    parser.add_argument("--confirmed-by", required=True)
    parser.add_argument("--confirmed-by-lane", required=True, choices=sorted(ALLOWED_CONFIRM_LANES))
    parser.add_argument("--trigger-keyword", required=True, choices=["confirm_execution_dispatch", "dispatch_execution"])
    parser.add_argument("--current-stage", default="execution_dispatch")
    parser.add_argument("--reason", default="owner confirmed execution dispatch")
    parser.add_argument("--dispatch-mode", default="spawn", choices=["spawn", "run"])
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--codex-command", default="codex.cmd")
    parser.add_argument("--output-dispatch", default=str(DEFAULT_DISPATCH_RESULT_PATH))
    parser.add_argument("--output-runtime", default=str(DEFAULT_RUNTIME_STATUS_PATH))
    parser.add_argument("--output-receipt", default=str(DEFAULT_EXECUTION_RECEIPT_PATH))
    parser.add_argument("--output-brief", default=str(DEFAULT_EXECUTION_BRIEF_PATH))
    args = parser.parse_args()

    trigger = {
        "is_trigger": True,
        "keyword": args.trigger_keyword,
        "authorized": True,
        "requested_by_lane": args.confirmed_by_lane,
        "ignored_reason": "",
    }
    result = dispatch_owner_confirmed_execution(
        handoff_artifact_path=Path(args.handoff),
        trigger=trigger,
        confirmed_by=args.confirmed_by,
        confirmed_by_lane=args.confirmed_by_lane,
        current_stage=args.current_stage,
        reason=args.reason,
        dispatch_result_path=Path(args.output_dispatch),
        runtime_status_path=Path(args.output_runtime),
        execution_receipt_path=Path(args.output_receipt),
        execution_brief_path=Path(args.output_brief),
        codex_command=args.codex_command,
        dispatch_mode=args.dispatch_mode,
        timeout_sec=args.timeout_sec,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
