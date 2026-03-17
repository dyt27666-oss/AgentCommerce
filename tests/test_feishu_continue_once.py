from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.council_bridge.feishu_continue_once as mod


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_dispatch_ready() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_ready": True,
    }


def _owner_action(action: str) -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "owner_action": action,
        "source_artifact_path": "artifacts/council_codex_dispatch_ready.json",
        "source_state": "dispatch_ready=True",
        "action_by": "owner_mobile",
        "action_at": "2026-03-15T12:00:00+08:00",
        "notes": "",
    }


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_flow"),
    [
        ("hold", "paused_no_execution", "pause"),
        ("reject", "stopped_no_execution", "stop"),
        ("needs_fix", "loop_back_no_execution", "loop_back"),
    ],
)
def test_actions_non_continue_paths(tmp_path: Path, action: str, expected_status: str, expected_flow: str) -> None:
    source = tmp_path / "source.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    _write_json(source, _source_dispatch_ready())

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action=action,
        owner_id="owner_mobile",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
    )
    assert result["final_status"] == expected_status
    assert result["flow_state"] == expected_flow
    assert continuation_output.exists()
    assert executor_output.exists()


def test_dispatch_continue_executor_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    _write_json(source, _source_dispatch_ready())

    def fake_execute_round(*args, **kwargs):
        return {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        }

    monkeypatch.setattr(mod, "execute_round", fake_execute_round)
    monkeypatch.setattr(
        mod,
        "capture_completion",
        lambda **kwargs: {
            "completion_observation_status": "running_no_execution_receipt",
            "next_action": "Wait for process completion and generate execution receipt.",
        },
    )

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action="dispatch",
        owner_id="owner_mobile",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
    )
    assert result["final_status"] == "executed_continue_success"
    assert result["flow_state"] == "continue"
    assert result["executed_step"] == "tools/council_bridge/codex_dispatch_runner.py"
    assert result["completion_check_attempted"] is False


def test_dispatch_continue_with_check_completion_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    completion_output = tmp_path / "completion.json"
    _write_json(source, _source_dispatch_ready())

    monkeypatch.setattr(
        mod,
        "execute_round",
        lambda *args, **kwargs: {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        },
    )
    monkeypatch.setattr(
        mod,
        "capture_completion",
        lambda **kwargs: {
            "completion_observation_status": "running_no_execution_receipt",
            "next_action": "Wait for process completion and generate execution receipt.",
        },
    )
    monkeypatch.setattr(
        mod,
        "build_execution_receipt_skeleton",
        lambda **kwargs: {
            "identity_linkage_status": "matched",
            "execution_receipt_status": "skeleton_only",
        },
    )
    monkeypatch.setattr(mod, "write_skeleton", lambda *args, **kwargs: None)

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action="dispatch",
        owner_id="owner_mobile",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
        completion_output_path=completion_output,
        check_completion_once=True,
    )
    assert result["completion_check_attempted"] is True
    assert result["completion_artifact"] == completion_output.as_posix()
    assert result["completion_state"] == "running_no_execution_receipt"
    assert "Wait for process completion" in result["post_dispatch_next_manual_action"]
    assert result["receipt_skeleton_attempted"] is False


@pytest.mark.parametrize("action", ["hold", "reject", "needs_fix"])
def test_check_completion_once_ignored_for_non_continue(action: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    _write_json(source, _source_dispatch_ready())

    called = {"capture": False}

    def fake_capture(**kwargs):
        called["capture"] = True
        return {}

    monkeypatch.setattr(mod, "capture_completion", fake_capture)

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action=action,
        owner_id="owner_mobile",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
        check_completion_once=True,
    )
    assert called["capture"] is False
    assert result["completion_check_attempted"] is False
    assert "ignored" in (result["post_dispatch_next_manual_action"] or "")


def test_continue_with_check_and_build_receipt_skeleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    action_output = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    completion_output = tmp_path / "completion.json"
    skeleton_output = tmp_path / "receipt_skeleton.json"
    _write_json(source, _source_dispatch_ready())
    _write_json(completion_output, {"completion_observation_status": "execution_receipt_available"})

    monkeypatch.setattr(
        mod,
        "execute_round",
        lambda *args, **kwargs: {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        },
    )
    monkeypatch.setattr(
        mod,
        "capture_completion",
        lambda **kwargs: {
            "completion_observation_status": "execution_receipt_available",
            "next_action": "Proceed with owner final review summary.",
        },
    )
    monkeypatch.setattr(
        mod,
        "build_execution_receipt_skeleton",
        lambda **kwargs: {
            "identity_linkage_status": "matched",
            "execution_receipt_status": "skeleton_only",
        },
    )
    monkeypatch.setattr(mod, "write_skeleton", lambda *args, **kwargs: None)

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action="dispatch",
        owner_id="owner_mobile",
        action_output_path=action_output,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
        completion_output_path=completion_output,
        receipt_skeleton_output_path=skeleton_output,
        check_completion_once=True,
        build_receipt_skeleton=True,
    )
    assert result["receipt_skeleton_attempted"] is True
    assert result["receipt_skeleton_artifact"] == skeleton_output.as_posix()
    assert result["receipt_skeleton_status"] == "generated"
    assert result["owner_review_ready"] is True


def test_continue_build_receipt_skeleton_missing_completion_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    completion_output = tmp_path / "completion_missing.json"
    _write_json(source, _source_dispatch_ready())

    monkeypatch.setattr(
        mod,
        "execute_round",
        lambda *args, **kwargs: {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        },
    )
    monkeypatch.setattr(
        mod,
        "capture_completion",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("completion write failed")),
    )

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action="dispatch",
        owner_id="owner_mobile",
        completion_output_path=completion_output,
        check_completion_once=True,
        build_receipt_skeleton=True,
    )
    assert result["completion_state"] == "check_failed"
    assert result["receipt_skeleton_attempted"] is False
    assert result["receipt_skeleton_status"] == "skipped_missing_completion_artifact"
    assert "missing" in (result["post_receipt_next_manual_action"] or "")


@pytest.mark.parametrize("action,expected_status", [("hold", "pause"), ("reject", "stop"), ("needs_fix", "loop_back")])
def test_build_receipt_skeleton_flag_ignored_for_non_continue_paths(
    action: str, expected_status: str, tmp_path: Path
) -> None:
    source = tmp_path / "source.json"
    _write_json(source, _source_dispatch_ready())
    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action=action,
        owner_id="owner_mobile",
        check_completion_once=True,
        build_receipt_skeleton=True,
    )
    assert result["flow_state"] == expected_status
    assert result["receipt_skeleton_attempted"] is False
    assert result["receipt_skeleton_status"] == "skipped_non_continue_success"


def test_missing_input_fails_cleanly() -> None:
    with pytest.raises(ValueError, match="Either --owner-action-artifact"):
        mod.run_continue_once()


def test_existing_owner_action_artifact_is_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner_action_artifact = tmp_path / "owner_action.json"
    continuation_output = tmp_path / "continuation.json"
    executor_output = tmp_path / "executor_result.json"
    _write_json(owner_action_artifact, _owner_action("dispatch"))

    def fake_execute_round(*args, **kwargs):
        return {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        }

    monkeypatch.setattr(mod, "execute_round", fake_execute_round)

    result = mod.run_continue_once(
        owner_action_artifact_path=owner_action_artifact,
        continuation_output_path=continuation_output,
        executor_result_output_path=executor_output,
    )
    assert result["owner_action_artifact"] == owner_action_artifact.as_posix()
    assert result["flow_state"] == "continue"
    assert continuation_output.exists()


def test_completion_check_failure_is_explainable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.json"
    _write_json(source, _source_dispatch_ready())

    monkeypatch.setattr(
        mod,
        "execute_round",
        lambda *args, **kwargs: {
            "execution_status": "executed_continue_success",
            "executed_tool": "tools/council_bridge/codex_dispatch_runner.py",
            "next_manual_action": "Run dispatch completion capture.",
            "notes": "dispatch_status=dispatched",
        },
    )

    def raise_capture(**kwargs):
        raise RuntimeError("missing dispatch receipt")

    monkeypatch.setattr(mod, "capture_completion", raise_capture)

    result = mod.run_continue_once(
        source_artifact_path=source,
        owner_action="dispatch",
        owner_id="owner_mobile",
        check_completion_once=True,
    )
    assert result["completion_check_attempted"] is True
    assert result["completion_state"] == "check_failed"
    assert "run completion capture manually" in (result["post_dispatch_next_manual_action"] or "")
    assert "completion_check_error=missing dispatch receipt" in result["notes"]
