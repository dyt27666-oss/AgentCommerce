from __future__ import annotations

from pathlib import Path

from tools.council_bridge.bridge_round_executor import execute_round


def _base_continuation(flow_state: str) -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "round_flow_state": flow_state,
        "recommended_next_step": "next-step",
        "source_artifact_path": "artifacts/council_codex_dispatch_ready.json",
        "next_tool_paths": [
            "tools/council_bridge/dispatch_prep_adapter.py",
            "tools/council_bridge/codex_dispatch_runner.py",
        ],
    }


def test_continue_success_executes_supported_dispatch() -> None:
    calls = {}

    def fake_dispatcher(**kwargs):
        calls.update(kwargs)
        return {"dispatch_status": "dispatched"}

    result = execute_round(
        _base_continuation("continue"),
        source_path=Path("artifacts/council_feishu_action_round_bridge.json"),
        dispatcher=fake_dispatcher,
    )
    assert result["execution_status"] == "executed_continue_success"
    assert result["executed_tool"] == "tools/council_bridge/codex_dispatch_runner.py"
    assert "council_codex_dispatch_receipt.json" in result["produced_artifacts"][0]
    assert calls["dispatch_ready_path"] == "artifacts/council_codex_dispatch_ready.json"


def test_pause_does_not_execute() -> None:
    result = execute_round(
        _base_continuation("pause"),
        source_path=Path("artifacts/council_feishu_action_round_bridge.json"),
    )
    assert result["execution_status"] == "paused_no_execution"
    assert result["executed_tool"] is None


def test_stop_does_not_execute() -> None:
    result = execute_round(
        _base_continuation("stop"),
        source_path=Path("artifacts/council_feishu_action_round_bridge.json"),
    )
    assert result["execution_status"] == "stopped_no_execution"
    assert result["executed_tool"] is None


def test_loop_back_does_not_execute() -> None:
    result = execute_round(
        _base_continuation("loop_back"),
        source_path=Path("artifacts/council_feishu_action_round_bridge.json"),
    )
    assert result["execution_status"] == "loop_back_no_execution"
    assert result["executed_tool"] is None


def test_continue_with_unsupported_next_tool_fails_cleanly() -> None:
    continuation = _base_continuation("continue")
    continuation["next_tool_paths"] = ["tools/council_bridge/some_other_tool.py"]
    result = execute_round(
        continuation,
        source_path=Path("artifacts/council_feishu_action_round_bridge.json"),
    )
    assert result["execution_status"] == "failed_unsupported_next_step"
    assert "supports codex_dispatch_runner.py" in result["notes"]

