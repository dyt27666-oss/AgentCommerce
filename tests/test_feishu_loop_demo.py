from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.council_bridge.feishu_loop_demo import run_feishu_loop_demo


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dispatch_ready_sample() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_ready": True,
        "gate_results": [{"gate": "handoff_executable", "passed": True}],
        "prompt_artifact_path": "artifacts/council_codex_prompt.txt",
    }


def _dispatch_completion_sample() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_status": "dispatched",
        "dispatch_attempted": True,
        "completion_observation_status": "running_no_execution_receipt",
        "next_action": "Wait for completion.",
        "dispatch_log_tail": {"stdout": "", "stderr": "error hint"},
        "dispatch_process": {"pid": 1234, "running": True},
    }


def test_dry_run_path_generates_preview(tmp_path: Path) -> None:
    source = tmp_path / "dispatch_ready.json"
    _write_json(source, _dispatch_ready_sample())

    result = run_feishu_loop_demo(source, send_mode="dry-run")
    assert result["notification_result"]["send_mode"] == "dry-run"
    assert "feishu_payload_preview" in result["notification_result"]
    assert result["action_artifact_path"] is None
    assert result["continuation_artifact_path"] is None


def test_detail_mode_summary_contains_expanded_lines(tmp_path: Path) -> None:
    source = tmp_path / "dispatch_completion.json"
    _write_json(source, _dispatch_completion_sample())

    result = run_feishu_loop_demo(source, send_mode="dry-run", level="detail")
    text = result["summary_text"]
    assert "completion_state=running_no_execution_receipt" in text
    assert "state_explanation=Completion observed" in text
    assert "execution_receipt_presence=no_or_pending" in text


@pytest.mark.parametrize(
    ("action", "expected_flow"),
    [
        ("dispatch", "continue"),
        ("hold", "pause"),
        ("needs_fix", "loop_back"),
        ("reject", "stop"),
    ],
)
def test_action_to_continuation_mapping(tmp_path: Path, action: str, expected_flow: str) -> None:
    source = tmp_path / "dispatch_ready.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    _write_json(source, _dispatch_ready_sample())

    result = run_feishu_loop_demo(
        source,
        send_mode="dry-run",
        owner_action=action,
        owner_id="owner_mobile",
        notes=f"test-{action}",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
    )
    assert result["action_artifact_path"] == action_output.as_posix()
    assert result["continuation_artifact_path"] == continuation_output.as_posix()
    assert result["round_flow_state"] == expected_flow
    assert continuation_output.exists()


def test_owner_readable_summary_contains_decision_fields(tmp_path: Path) -> None:
    source = tmp_path / "dispatch_ready.json"
    _write_json(source, _dispatch_ready_sample())

    result = run_feishu_loop_demo(source, send_mode="dry-run", level="detail")
    summary = result["owner_readable_summary"]
    assert summary["task_summary"]["closed_loop"] in {True, False}
    assert isinstance(summary["key_changes"], list)
    assert "successes" in summary["outcome"]
    assert "next_owner_action" in summary
    assert isinstance(summary["concise_technical_evidence"], list)
