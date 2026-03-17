from __future__ import annotations

from tools.council_bridge.bridge_progress_summary_writer import build_progress_summary


def test_build_progress_summary_happy_path() -> None:
    summary = build_progress_summary(
        handoff={"approval_status": "approved"},
        dispatch_ready={"dispatch_ready": True},
        dispatch_receipt={"dispatch_attempted": True, "dispatch_status": "dispatched"},
        completion={"completion_observation_status": "running_no_execution_receipt"},
        execution_receipt={"execution_status": "completed"},
        final_review={"final_owner_decision": "approved"},
        feishu_action={"owner_action": "dispatch"},
        feishu_round_bridge={"round_flow_state": "continue"},
    )
    assert summary["phase"] == "bridge_v1.x"
    assert summary["execution_layer_status"] == "stable_workflow_running"
    assert summary["bridge_status"] == "v1x_semi_manual_usable"
    assert summary["codex_dispatch_status"] == "dispatched"
    assert summary["completion_observation_status"] == "running_no_execution_receipt"
    assert summary["feishu_notification_status"] == "working_verified_live_send"
    assert summary["feishu_action_status"] == "recorded_dispatch"
    assert summary["mobile_review_loop_status"] == "usable_continue"


def test_build_progress_summary_handles_missing_inputs() -> None:
    summary = build_progress_summary(
        handoff=None,
        dispatch_ready=None,
        dispatch_receipt=None,
        completion=None,
        execution_receipt=None,
        final_review=None,
        feishu_action=None,
        feishu_round_bridge=None,
    )
    assert summary["execution_layer_status"] == "partially_prepared"
    assert summary["bridge_status"] == "v1x_partial"
    assert summary["codex_dispatch_status"] == "unknown"
    assert summary["completion_observation_status"] == "unknown"
    assert summary["feishu_action_status"] == "not_recorded"
    assert summary["mobile_review_loop_status"] == "not_ready"
    assert any("execution receipt" in x for x in summary["manual_steps_remaining"])
    assert any("final review summary" in x for x in summary["manual_steps_remaining"])

