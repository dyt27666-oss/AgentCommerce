"""One-command local continue entrypoint after Feishu owner confirmation (v0).

This helper is not orchestration/callback/daemon.
It only chains:
1) owner action artifact
2) action round bridge artifact
3) single-step round executor
4) optional one-time completion check (no polling)
5) optional receipt skeleton prefill (no auto review)
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

from tools.council_bridge.bridge_round_executor import (
    DEFAULT_DISPATCH_RECEIPT_PATH,
    DEFAULT_PROMPT_PATH,
    execute_round,
    write_result,
)
from tools.council_bridge.feishu_action_round_bridge import build_round_bridge, write_round_bridge
from tools.council_bridge.dispatch_completion_capture import capture_completion
from tools.council_bridge.execution_receipt_skeleton_helper import (
    build_execution_receipt_skeleton,
    write_skeleton,
)
from tools.council_bridge.feishu_owner_action_writer import (
    _load_json,
    build_owner_action_artifact,
    write_owner_action_artifact,
)


DEFAULT_OWNER_ACTION_PATH = Path("artifacts") / "council_feishu_owner_action.json"
DEFAULT_CONTINUATION_PATH = Path("artifacts") / "council_feishu_action_round_bridge.json"
DEFAULT_EXECUTOR_RESULT_PATH = Path("artifacts") / "council_bridge_round_executor_result.json"
DEFAULT_COMPLETION_PATH = Path("artifacts") / "council_codex_dispatch_completion.json"
DEFAULT_EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_codex_execution_receipt.json"
DEFAULT_RECEIPT_SKELETON_PATH = Path("artifacts") / "council_codex_execution_receipt_skeleton.json"
DEFAULT_RESULT_PATH = Path("artifacts") / "council_feishu_continue_once_result.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_non_empty(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be non-empty.")
    return value.strip()


def run_continue_once(
    *,
    owner_action_artifact_path: Path | None = None,
    source_artifact_path: Path | None = None,
    owner_action: str | None = None,
    owner_id: str | None = None,
    notes: str = "",
    action_output_path: Path = DEFAULT_OWNER_ACTION_PATH,
    continuation_output_path: Path = DEFAULT_CONTINUATION_PATH,
    executor_result_output_path: Path = DEFAULT_EXECUTOR_RESULT_PATH,
    prompt_path: Path = DEFAULT_PROMPT_PATH,
    dispatch_receipt_path: Path = DEFAULT_DISPATCH_RECEIPT_PATH,
    completion_output_path: Path = DEFAULT_COMPLETION_PATH,
    execution_receipt_path: Path = DEFAULT_EXECUTION_RECEIPT_PATH,
    receipt_skeleton_output_path: Path = DEFAULT_RECEIPT_SKELETON_PATH,
    codex_command: str = "codex.cmd",
    dispatch_mode: str = "spawn",
    timeout_sec: int = 120,
    check_completion_once: bool = False,
    build_receipt_skeleton: bool = False,
) -> dict[str, Any]:
    if owner_action_artifact_path:
        action_artifact = _load_json(owner_action_artifact_path)
        action_artifact_path_used = owner_action_artifact_path
        source_artifact_used = action_artifact.get("source_artifact_path")
    else:
        source_path = source_artifact_path
        if source_path is None:
            raise ValueError(
                "Either --owner-action-artifact OR (--source-artifact + --owner-action + --owner-id) is required."
            )
        action = _ensure_non_empty(owner_action, "owner_action")
        oid = _ensure_non_empty(owner_id, "owner_id")
        source_data = _load_json(source_path)
        action_artifact = build_owner_action_artifact(
            source_data=source_data,
            source_artifact_path=source_path,
            owner_action=action,
            owner_id=oid,
            notes=notes,
        )
        write_owner_action_artifact(action_output_path, action_artifact)
        action_artifact_path_used = action_output_path
        source_artifact_used = source_path.as_posix()

    continuation = build_round_bridge(action_artifact, source_path=action_artifact_path_used)
    write_round_bridge(continuation_output_path, continuation)

    executor_result = execute_round(
        continuation,
        source_path=continuation_output_path,
        prompt_path=prompt_path,
        dispatch_receipt_path=dispatch_receipt_path,
        codex_command=codex_command,
        dispatch_mode=dispatch_mode,
        timeout_sec=timeout_sec,
    )
    write_result(executor_result_output_path, executor_result)

    final_status = executor_result.get("execution_status", "unknown")
    flow_state = continuation.get("round_flow_state", "unknown")

    result = {
        "source_artifact": source_artifact_used,
        "owner_action_artifact": action_artifact_path_used.as_posix(),
        "continuation_artifact": continuation_output_path.as_posix(),
        "executor_result_artifact": executor_result_output_path.as_posix(),
        "final_status": final_status,
        "executed_step": executor_result.get("executed_tool"),
        "flow_state": flow_state,
        "next_manual_action": executor_result.get("next_manual_action", ""),
        "notes": executor_result.get("notes", ""),
        "completion_check_attempted": False,
        "completion_artifact": None,
        "completion_state": None,
        "post_dispatch_next_manual_action": None,
        "receipt_skeleton_attempted": False,
        "receipt_skeleton_artifact": None,
        "receipt_skeleton_status": None,
        "owner_review_ready": False,
        "post_receipt_next_manual_action": None,
        "generated_at": _now_iso(),
    }

    if check_completion_once:
        if flow_state == "continue" and final_status == "executed_continue_success":
            try:
                completion = capture_completion(
                    dispatch_receipt_path=dispatch_receipt_path.as_posix(),
                    execution_receipt_path=execution_receipt_path.as_posix(),
                    output_path=completion_output_path.as_posix(),
                )
                result["completion_check_attempted"] = True
                result["completion_artifact"] = completion_output_path.as_posix()
                result["completion_state"] = completion.get("completion_observation_status")
                result["post_dispatch_next_manual_action"] = completion.get("next_action")
            except Exception as exc:
                result["completion_check_attempted"] = True
                result["completion_artifact"] = completion_output_path.as_posix()
                result["completion_state"] = "check_failed"
                result["post_dispatch_next_manual_action"] = "Inspect dispatch receipt and run completion capture manually."
                result["notes"] = f"{result['notes']} | completion_check_error={exc}".strip(" |")
        else:
            # explicit non-execution in non-continue paths, to keep behavior auditable.
            result["completion_check_attempted"] = False
            result["post_dispatch_next_manual_action"] = "Completion check ignored: flow is not continue-success."

    if build_receipt_skeleton:
        if flow_state != "continue" or final_status != "executed_continue_success":
            result["receipt_skeleton_attempted"] = False
            result["receipt_skeleton_status"] = "skipped_non_continue_success"
            result["post_receipt_next_manual_action"] = (
                "Receipt skeleton skipped: run path is not continue-success."
            )
        elif not result.get("completion_check_attempted"):
            result["receipt_skeleton_attempted"] = False
            result["receipt_skeleton_status"] = "skipped_completion_check_not_attempted"
            result["post_receipt_next_manual_action"] = (
                "Run continue-once with --check-completion-once before skeleton prefill."
            )
        else:
            completion_artifact = result.get("completion_artifact")
            completion_path = Path(completion_artifact) if isinstance(completion_artifact, str) and completion_artifact else None
            if completion_path is None or not completion_path.exists():
                result["receipt_skeleton_attempted"] = False
                result["receipt_skeleton_status"] = "skipped_missing_completion_artifact"
                result["post_receipt_next_manual_action"] = (
                    "Completion artifact missing; run completion capture once and retry skeleton prefill."
                )
            else:
                try:
                    skeleton = build_execution_receipt_skeleton(
                        dispatch_receipt=_load_json(dispatch_receipt_path) if dispatch_receipt_path.exists() else None,
                        completion=_load_json(completion_path) if completion_path.exists() else None,
                        continue_once_result=result,
                        handoff=_load_json(Path("artifacts/council_bridge_handoff.json"))
                        if Path("artifacts/council_bridge_handoff.json").exists()
                        else None,
                        source_paths={
                            "dispatch_receipt": dispatch_receipt_path.as_posix(),
                            "completion": completion_path.as_posix(),
                            "continue_once_result": "in_memory_continue_once_result",
                            "handoff": "artifacts/council_bridge_handoff.json",
                        },
                    )
                    write_skeleton(receipt_skeleton_output_path, skeleton)
                    result["receipt_skeleton_attempted"] = True
                    result["receipt_skeleton_artifact"] = receipt_skeleton_output_path.as_posix()
                    result["receipt_skeleton_status"] = "generated"
                    result["owner_review_ready"] = skeleton.get("identity_linkage_status") == "matched"
                    result["post_receipt_next_manual_action"] = (
                        "Review skeleton, fill final execution receipt fields, then run owner final review."
                    )
                except Exception as exc:
                    result["receipt_skeleton_attempted"] = True
                    result["receipt_skeleton_artifact"] = receipt_skeleton_output_path.as_posix()
                    result["receipt_skeleton_status"] = "generation_failed"
                    result["owner_review_ready"] = False
                    result["post_receipt_next_manual_action"] = (
                        "Skeleton generation failed; inspect artifacts and run helper manually."
                    )
                    result["notes"] = f"{result['notes']} | receipt_skeleton_error={exc}".strip(" |")
    return result


def write_continue_once_result(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command local continue entrypoint after Feishu confirmation (v0).")
    parser.add_argument("--owner-action-artifact", default="", help="Existing owner action artifact path.")
    parser.add_argument("--source-artifact", default="", help="Source artifact path for creating owner action.")
    parser.add_argument("--owner-action", default="", choices=["", "dispatch", "hold", "needs_fix", "reject"])
    parser.add_argument("--owner-id", default="", help="Owner id for action creation.")
    parser.add_argument("--notes", default="", help="Optional notes for action creation.")
    parser.add_argument("--action-output", default=str(DEFAULT_OWNER_ACTION_PATH), help="Owner action artifact output path.")
    parser.add_argument("--continuation-output", default=str(DEFAULT_CONTINUATION_PATH), help="Continuation artifact output path.")
    parser.add_argument("--executor-result-output", default=str(DEFAULT_EXECUTOR_RESULT_PATH), help="Round executor result output path.")
    parser.add_argument("--output", default=str(DEFAULT_RESULT_PATH), help="Continue-once summary output path.")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH), help="Prompt path used by round executor.")
    parser.add_argument("--dispatch-receipt", default=str(DEFAULT_DISPATCH_RECEIPT_PATH), help="Dispatch receipt output path.")
    parser.add_argument("--completion-output", default=str(DEFAULT_COMPLETION_PATH), help="Completion observation artifact output path.")
    parser.add_argument("--execution-receipt", default=str(DEFAULT_EXECUTION_RECEIPT_PATH), help="Existing execution receipt path (optional).")
    parser.add_argument(
        "--receipt-skeleton-output",
        default=str(DEFAULT_RECEIPT_SKELETON_PATH),
        help="Execution receipt skeleton output path.",
    )
    parser.add_argument("--codex-command", default="codex.cmd", help="Local Codex command for continue dispatch case.")
    parser.add_argument("--dispatch-mode", default="spawn", choices=["spawn", "run"])
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument(
        "--check-completion-once",
        action="store_true",
        help="After continue-success dispatch, perform one completion capture check (single-shot, no polling).",
    )
    parser.add_argument(
        "--build-receipt-skeleton",
        action="store_true",
        help="After continue-success (+completion check), build execution receipt skeleton once.",
    )
    args = parser.parse_args()

    owner_action_artifact = Path(args.owner_action_artifact) if args.owner_action_artifact else None
    source_artifact = Path(args.source_artifact) if args.source_artifact else None

    result = run_continue_once(
        owner_action_artifact_path=owner_action_artifact,
        source_artifact_path=source_artifact,
        owner_action=args.owner_action or None,
        owner_id=args.owner_id or None,
        notes=args.notes,
        action_output_path=Path(args.action_output),
        continuation_output_path=Path(args.continuation_output),
        executor_result_output_path=Path(args.executor_result_output),
        prompt_path=Path(args.prompt),
        dispatch_receipt_path=Path(args.dispatch_receipt),
        completion_output_path=Path(args.completion_output),
        execution_receipt_path=Path(args.execution_receipt),
        receipt_skeleton_output_path=Path(args.receipt_skeleton_output),
        codex_command=args.codex_command,
        dispatch_mode=args.dispatch_mode,
        timeout_sec=args.timeout_sec,
        check_completion_once=args.check_completion_once,
        build_receipt_skeleton=args.build_receipt_skeleton,
    )
    output = Path(args.output)
    write_continue_once_result(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[feishu-continue-once] saved: {output.as_posix()}")

    if result.get("final_status") not in {
        "executed_continue_success",
        "paused_no_execution",
        "stopped_no_execution",
        "loop_back_no_execution",
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
