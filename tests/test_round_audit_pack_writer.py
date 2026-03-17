from __future__ import annotations

from tools.council_bridge.round_audit_pack_writer import (
    build_round_audit_pack,
    render_round_audit_summary_md,
)


def test_build_round_audit_pack_complete_round() -> None:
    artifact_paths = {
        "dispatch_ready": "artifacts/council_codex_dispatch_ready.json",
        "feishu_owner_action": "artifacts/council_feishu_owner_action.json",
        "feishu_round_bridge": "artifacts/council_feishu_action_round_bridge.json",
        "round_executor_result": "artifacts/council_bridge_round_executor_result.json",
        "continue_once_result": "artifacts/council_feishu_continue_once_result.json",
        "dispatch_completion": "artifacts/council_codex_dispatch_completion.json",
        "execution_receipt_skeleton": "artifacts/council_codex_execution_receipt_skeleton.json",
        "owner_final_review_summary": "artifacts/council_owner_final_review_summary.json",
    }
    fake = {
        "dispatch_ready": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "dispatch_ready": True},
        "feishu_owner_action": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "owner_action": "dispatch", "action_by": "owner_mobile", "action_at": "2026-03-15T10:00:00+08:00"},
        "feishu_round_bridge": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "round_flow_state": "continue"},
        "round_executor_result": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "execution_status": "executed_continue_success"},
        "continue_once_result": {"inherited_identity": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1"}, "final_status": "executed_continue_success", "completion_check_attempted": True, "receipt_skeleton_attempted": True},
        "dispatch_completion": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "completion_observation_status": "execution_receipt_available"},
        "execution_receipt_skeleton": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "execution_receipt_status": "skeleton_only"},
        "owner_final_review_summary": {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "final_owner_decision": "approved"},
    }

    def _fake_safe_load(path: str):
        for key, p in artifact_paths.items():
            if p == path:
                return fake[key]
        return None

    from tools.council_bridge import round_audit_pack_writer as mod

    original = mod._safe_load
    mod._safe_load = _fake_safe_load
    try:
        pack = build_round_audit_pack(artifact_paths)
    finally:
        mod._safe_load = original

    assert pack["request_id"] == "req-1"
    assert pack["brief_id"] == "brief-1"
    assert pack["handoff_id"] == "handoff-1"
    assert pack["round_status"] == "closed_approved"
    assert pack["completion_state"] == "execution_receipt_available"
    assert pack["receipt_status"] == "skeleton_only"
    assert pack["final_decision"] == "approved"
    assert "owner_action_recorded" in pack["executed_steps"]
    assert any(x["type"] == "final_owner_decision" for x in pack["owner_actions"])

    summary = render_round_audit_summary_md(pack)
    assert "# Council Bridge Round Audit Summary" in summary
    assert "round_status: closed_approved" in summary
    assert "final_decision: approved" in summary
    assert "## Executed Steps" in summary


def test_build_round_audit_pack_degrades_with_missing_artifacts() -> None:
    artifact_paths = {
        "dispatch_ready": "artifacts/a.json",
        "feishu_owner_action": "artifacts/b.json",
        "feishu_round_bridge": "artifacts/c.json",
        "round_executor_result": "artifacts/d.json",
        "continue_once_result": "artifacts/e.json",
        "dispatch_completion": "artifacts/f.json",
        "execution_receipt_skeleton": "artifacts/g.json",
        "owner_final_review_summary": "artifacts/h.json",
    }
    fake = {
        "dispatch_ready": {"request_id": "req-2", "brief_id": "brief-2", "handoff_id": "handoff-2", "dispatch_ready": True},
        "feishu_owner_action": None,
        "feishu_round_bridge": None,
        "round_executor_result": {"request_id": "req-2", "brief_id": "brief-2", "handoff_id": "handoff-2", "execution_status": "paused_no_execution"},
        "continue_once_result": None,
        "dispatch_completion": None,
        "execution_receipt_skeleton": None,
        "owner_final_review_summary": None,
    }

    def _fake_safe_load(path: str):
        for key, p in artifact_paths.items():
            if p == path:
                return fake[key]
        return None

    from tools.council_bridge import round_audit_pack_writer as mod

    original = mod._safe_load
    mod._safe_load = _fake_safe_load
    try:
        pack = build_round_audit_pack(artifact_paths)
    finally:
        mod._safe_load = original

    assert pack["request_id"] == "req-2"
    assert pack["round_status"] == "executor_paused_no_execution"
    assert pack["completion_state"] == "missing"
    assert pack["receipt_status"] == "missing"
    assert pack["final_decision"] == "not_recorded"
    assert any("missing artifacts:" in note for note in pack["audit_notes"])
    assert any("not final-closed yet" in note for note in pack["audit_notes"])

    summary = render_round_audit_summary_md(pack)
    assert "round_status: executor_paused_no_execution" in summary
    assert "completion_state: missing" in summary
    assert "## Key Artifacts" in summary

