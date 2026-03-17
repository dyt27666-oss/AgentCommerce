from __future__ import annotations

from tools.council_bridge.execution_receipt_v0_1 import build_execution_receipt_v0_1


def test_build_execution_receipt_v0_1_contains_required_fields() -> None:
    receipt = build_execution_receipt_v0_1(
        execution_id="exec-001",
        source_handoff_id="handoff-001",
        before_execution_state="handoff_ready",
        execution_status="not_executed",
        executed_actions_summary=["observe-only gate passed"],
        changed_files=[],
        touched_resources=["artifacts/council_execution_brief.json"],
        risk_flags=["execution_not_dispatched_in_phase5"],
        receipt_status="recorded",
        next_action="owner-confirmed dispatch in next step",
    )
    assert receipt["execution_id"] == "exec-001"
    assert receipt["source_handoff_id"] == "handoff-001"
    assert receipt["execution_status"] == "not_executed"
    assert "timestamp" in receipt

