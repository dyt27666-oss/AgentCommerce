"""Local single-step bridge round executor (v0).

This is not an orchestration engine.
It executes at most one controlled local next step from a continuation artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.council_bridge.codex_dispatch_runner import run_dispatch


CONTINUATION_PATH = Path("artifacts") / "council_feishu_action_round_bridge.json"
RESULT_PATH = Path("artifacts") / "council_bridge_round_executor_result.json"
DEFAULT_PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
DEFAULT_DISPATCH_RECEIPT_PATH = Path("artifacts") / "council_codex_dispatch_receipt.json"


DispatcherFn = Callable[..., dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _require_non_empty_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value.strip()


def _base_result(continuation: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return {
        "source_continuation_artifact": source_path.as_posix(),
        "request_id": continuation.get("request_id"),
        "brief_id": continuation.get("brief_id"),
        "handoff_id": continuation.get("handoff_id"),
        "flow_state": continuation.get("round_flow_state"),
        "execution_status": "not_executed",
        "executed_tool": None,
        "executed_command": None,
        "produced_artifacts": [],
        "next_manual_action": continuation.get("recommended_next_step", ""),
        "notes": "",
        "generated_at": _now_iso(),
    }


def _is_supported_continue_target(continuation: dict[str, Any]) -> bool:
    next_tool_paths = continuation.get("next_tool_paths", [])
    if not isinstance(next_tool_paths, list):
        return False
    return any(isinstance(x, str) and x.endswith("codex_dispatch_runner.py") for x in next_tool_paths)


def execute_round(
    continuation: dict[str, Any],
    source_path: Path,
    *,
    dispatcher: DispatcherFn = run_dispatch,
    prompt_path: Path = DEFAULT_PROMPT_PATH,
    dispatch_receipt_path: Path = DEFAULT_DISPATCH_RECEIPT_PATH,
    codex_command: str = "codex.cmd",
    dispatch_mode: str = "spawn",
    timeout_sec: int = 120,
) -> dict[str, Any]:
    _require_non_empty_str(continuation, "request_id")
    _require_non_empty_str(continuation, "brief_id")
    _require_non_empty_str(continuation, "handoff_id")
    flow_state = _require_non_empty_str(continuation, "round_flow_state")

    result = _base_result(continuation, source_path)

    if flow_state == "pause":
        result["execution_status"] = "paused_no_execution"
        result["notes"] = "Flow is pause; no local tool executed."
        return result

    if flow_state == "stop":
        result["execution_status"] = "stopped_no_execution"
        result["notes"] = "Flow is stop; round terminated without execution."
        return result

    if flow_state == "loop_back":
        result["execution_status"] = "loop_back_no_execution"
        result["notes"] = "Flow is loop_back; owner should correct inputs and restart round."
        return result

    if flow_state != "continue":
        result["execution_status"] = "failed_invalid_flow_state"
        result["notes"] = f"Unsupported flow_state: {flow_state}"
        return result

    if not _is_supported_continue_target(continuation):
        result["execution_status"] = "failed_unsupported_next_step"
        result["notes"] = "Continue flow only supports codex_dispatch_runner.py in v0."
        return result

    dispatch_ready_path_raw = continuation.get("source_artifact_path")
    if not isinstance(dispatch_ready_path_raw, str) or not dispatch_ready_path_raw.strip():
        result["execution_status"] = "failed_missing_source_artifact"
        result["notes"] = "Continue flow requires source_artifact_path to dispatch-ready artifact."
        return result
    dispatch_ready_path = Path(dispatch_ready_path_raw)

    receipt = dispatcher(
        dispatch_ready_path=dispatch_ready_path.as_posix(),
        prompt_path=prompt_path.as_posix(),
        output_path=dispatch_receipt_path.as_posix(),
        codex_command=codex_command,
        codex_args=None,
        dispatch_mode=dispatch_mode,
        stdout_log_path=None,
        stderr_log_path=None,
        timeout_sec=timeout_sec,
    )
    dispatch_status = receipt.get("dispatch_status")
    success = dispatch_status == "dispatched"

    result["executed_tool"] = "tools/council_bridge/codex_dispatch_runner.py"
    result["executed_command"] = f"run_dispatch(dispatch_ready={dispatch_ready_path.as_posix()}, prompt={prompt_path.as_posix()})"
    result["produced_artifacts"] = [dispatch_receipt_path.as_posix()]
    result["execution_status"] = "executed_continue_success" if success else "executed_continue_failed"
    result["next_manual_action"] = (
        "Run dispatch completion capture."
        if success
        else "Inspect dispatch receipt/logs and decide hold/needs_fix/retry."
    )
    result["notes"] = f"dispatch_status={dispatch_status}"
    return result


def write_result(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local single-step bridge round executor (v0).")
    parser.add_argument("--continuation", default=str(CONTINUATION_PATH), help="Continuation artifact JSON path.")
    parser.add_argument("--output", default=str(RESULT_PATH), help="Executor result JSON path.")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH), help="Prompt artifact path.")
    parser.add_argument("--dispatch-receipt", default=str(DEFAULT_DISPATCH_RECEIPT_PATH), help="Dispatch receipt output path.")
    parser.add_argument("--codex-command", default="codex.cmd", help="Local Codex command for dispatch.")
    parser.add_argument("--dispatch-mode", default="spawn", choices=["spawn", "run"], help="Dispatch mode for codex runner.")
    parser.add_argument("--timeout-sec", type=int, default=120, help="Dispatch timeout seconds.")
    args = parser.parse_args()

    source = Path(args.continuation)
    continuation = _load_json(source)
    result = execute_round(
        continuation,
        source_path=source,
        prompt_path=Path(args.prompt),
        dispatch_receipt_path=Path(args.dispatch_receipt),
        codex_command=args.codex_command,
        dispatch_mode=args.dispatch_mode,
        timeout_sec=args.timeout_sec,
    )
    output = Path(args.output)
    write_result(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[bridge-round-executor] saved: {output.as_posix()}")

    if result.get("execution_status") not in {"executed_continue_success", "paused_no_execution", "stopped_no_execution", "loop_back_no_execution"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

