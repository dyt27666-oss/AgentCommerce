from __future__ import annotations

from tools.council_bridge.execution_handoff_gate import validate_execution_handoff_gate


def _handoff(status: str = "handoff_ready", readiness: str = "ready") -> dict:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "handoff-gate-001",
        "request_id": "req-gate-001",
        "brief_id": "brief-gate-001",
        "handoff_id": "handoff-gate-001",
        "council_round": 1,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_gate",
        "created_at": "2026-03-16T20:30:00+08:00",
        "updated_at": "2026-03-16T20:30:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": status,
        "summary": "gate test",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "demo"},
        "execution_scope": ["demo"],
        "execution_constraints": ["constraint-a"],
        "no_go_zones": ["no-go-a"],
        "required_receipts": ["receipt-a"],
        "owner_approval_status": "approved",
        "execution_readiness_status": readiness,
    }


def test_execution_handoff_gate_passes_when_all_conditions_met() -> None:
    result = validate_execution_handoff_gate(
        artifact=_handoff(),
        current_stage="execution_gate",
        trigger={"is_trigger": True, "authorized": True, "keyword": "dispatch_execution"},
    )
    assert result["execution_handoff_ready"] is True
    assert result["observe_only"] is True


def test_execution_handoff_gate_blocks_without_ready_status() -> None:
    result = validate_execution_handoff_gate(
        artifact=_handoff(readiness="blocked"),
        current_stage="execution_gate",
        trigger={"is_trigger": True, "authorized": True, "keyword": "dispatch_execution"},
    )
    assert result["execution_handoff_ready"] is False
    assert "execution_readiness_status must be ready" in result["blocked_reason"]


def test_execution_handoff_gate_requires_explicit_trigger() -> None:
    result = validate_execution_handoff_gate(
        artifact=_handoff(),
        current_stage="execution_gate",
        trigger={"is_trigger": False, "authorized": False, "keyword": None, "ignored_reason": "missing"},
    )
    assert result["execution_handoff_ready"] is False
    assert "explicit_execution_trigger" in result["blocked_reason"]

