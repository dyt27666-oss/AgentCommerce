from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.owner_confirmed_transition_apply import apply_owner_confirmed_transition


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _plan_artifact(status: str, *, revision_done: bool = False) -> dict:
    lineage = {"revision_completed": True} if revision_done else {}
    parent = "plan-parent-1" if revision_done else None
    derived = ["plan-parent-1"] if revision_done else []
    return {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "plan-apply-001",
        "request_id": "req-apply-001",
        "brief_id": "brief-apply-001",
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": parent,
        "derived_from_artifact_ids": derived,
        "owner_id": "owner_001",
        "chat_id": "oc_apply",
        "created_at": "2026-03-16T19:00:00+08:00",
        "updated_at": "2026-03-16T19:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "apply test",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": lineage,
        "objective": "x",
        "scope": ["x"],
        "steps": [{"step_id": "s1", "title": "x"}],
        "dependencies": [],
        "acceptance_criteria": ["x"],
        "proposed_execution_boundary": {"execution_allowed": False},
        "expected_outputs": ["x"],
    }


def _mapping(target_status: str, current_status: str) -> dict:
    return {
        "is_mapped": True,
        "mapping_type": "natural_language",
        "owner_feedback": {
            "feedback_id": "fb-apply-001",
            "feedback_source": "feishu_chat",
            "feedback_text": "demo",
            "feedback_type": "needs_fix",
            "target_artifact_id": "plan-apply-001",
            "target_section": "scope",
            "severity": "medium",
            "requested_change": "demo",
            "resolved_status": "open",
            "resolved_by_artifact_id": None,
        },
        "suggested_transition_request": {
            "artifact_id": "plan-apply-001",
            "artifact_type": "plan",
            "current_status": current_status,
            "target_status": target_status,
            "requested_by": "owner_001",
            "requested_by_lane": "chat",
            "reason": "mapped from message",
            "triggering_feedback_id": "fb-apply-001",
            "triggering_artifact_id": None,
            "correlated_request_id": "req-apply-001",
            "correlated_brief_id": "brief-apply-001",
            "correlated_handoff_id": None,
        },
    }


def _validation(is_valid: bool, from_status: str, to_status: str) -> dict:
    return {
        "is_valid": is_valid,
        "artifact_id": "plan-apply-001",
        "artifact_type": "plan",
        "from_status": from_status,
        "to_status": to_status,
        "validation_errors": [] if is_valid else ["illegal state transition"],
    }


def test_owner_confirm_apply_success_under_review_to_needs_fix(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    mapping_path = tmp_path / "mapping.json"
    validation_path = tmp_path / "validation.json"
    output_path = tmp_path / "apply_result.json"
    _write(artifact_path, _plan_artifact("under_review"))
    _write(mapping_path, _mapping("needs_fix", "under_review"))
    _write(validation_path, _validation(True, "under_review", "needs_fix"))

    result = apply_owner_confirmed_transition(
        source_artifact_path=artifact_path,
        mapping_result_path=mapping_path,
        validation_result_path=validation_path,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        reason="owner confirm apply",
        output_path=output_path,
        current_stage="council_review",
    )
    assert result["apply_status"] == "applied"
    assert result["before_status"] == "under_review"
    assert result["after_status"] == "needs_fix"
    updated = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert updated["status"] == "needs_fix"


def test_owner_confirm_apply_success_revised_to_resubmitted(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    mapping_path = tmp_path / "mapping.json"
    validation_path = tmp_path / "validation.json"
    _write(artifact_path, _plan_artifact("revised", revision_done=True))
    _write(mapping_path, _mapping("resubmitted", "revised"))
    _write(validation_path, _validation(True, "revised", "resubmitted"))

    result = apply_owner_confirmed_transition(
        source_artifact_path=artifact_path,
        mapping_result_path=mapping_path,
        validation_result_path=validation_path,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        reason="owner confirm resubmit",
        output_path=tmp_path / "apply_result.json",
        current_stage="council_review",
    )
    assert result["apply_status"] == "applied"
    assert result["after_status"] == "resubmitted"


def test_invalid_validation_blocks_apply_and_writes_receipt(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    mapping_path = tmp_path / "mapping.json"
    validation_path = tmp_path / "validation.json"
    output_path = tmp_path / "apply_result.json"
    _write(artifact_path, _plan_artifact("owner_approved"))
    _write(mapping_path, _mapping("needs_fix", "owner_approved"))
    _write(validation_path, _validation(False, "owner_approved", "needs_fix"))

    result = apply_owner_confirmed_transition(
        source_artifact_path=artifact_path,
        mapping_result_path=mapping_path,
        validation_result_path=validation_path,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        reason="force apply",
        output_path=output_path,
        current_stage="council_review",
    )
    assert result["apply_status"] == "blocked"
    assert "validation_status is not valid" in result["apply_error"]
    assert output_path.exists()
    unchanged = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert unchanged["status"] == "owner_approved"


def test_chat_lane_cannot_confirm_apply(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    mapping_path = tmp_path / "mapping.json"
    validation_path = tmp_path / "validation.json"
    _write(artifact_path, _plan_artifact("under_review"))
    _write(mapping_path, _mapping("needs_fix", "under_review"))
    _write(validation_path, _validation(True, "under_review", "needs_fix"))

    result = apply_owner_confirmed_transition(
        source_artifact_path=artifact_path,
        mapping_result_path=mapping_path,
        validation_result_path=validation_path,
        confirmed_by="owner_001",
        confirmed_by_lane="chat",
        reason="chat says apply",
        output_path=tmp_path / "apply_result.json",
        current_stage="council_review",
    )
    assert result["apply_status"] == "blocked"
    assert "only owner/bridge can confirm apply" in result["apply_error"]

