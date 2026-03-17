from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.council_bridge.council_artifact_state_machine import TransitionRequest, validate_transition
from tools.council_bridge.feishu_feedback_mapping_adapter import (
    map_feishu_feedback,
    write_mapping_result,
)


SAMPLES_PATH = Path("docs") / "feishu_feedback_mapping_samples_v0.1" / "mapping_samples.json"


def _load_cases() -> list[dict]:
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8-sig"))
    return data["cases"]


def _case(case_id: str) -> dict:
    for case in _load_cases():
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing sample case: {case_id}")


def _build_artifact_from_payload(payload: dict) -> dict:
    base = {
        "artifact_type": payload["current_artifact_type"],
        "schema_version": "council.artifact.v0.1",
        "artifact_id": payload["current_artifact_id"],
        "request_id": payload["current_request_id"],
        "brief_id": payload["current_brief_id"],
        "handoff_id": payload.get("current_handoff_id") or None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": payload["chat_id"],
        "created_at": "2026-03-16T15:00:00+08:00",
        "updated_at": "2026-03-16T15:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": payload["current_artifact_status"],
        "summary": "sample",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
    }
    if payload["current_artifact_type"] == "plan":
        base.update(
            {
                "objective": "x",
                "scope": ["x"],
                "steps": [{"step_id": "s1", "title": "x"}],
                "dependencies": [],
                "acceptance_criteria": ["x"],
                "proposed_execution_boundary": {"execution_allowed": False},
                "expected_outputs": ["x"],
            }
        )
    elif payload["current_artifact_type"] == "risk":
        base.update(
            {
                "risk_items": [{"risk_id": "r1", "description": "x"}],
                "severity": "medium",
                "likelihood": "medium",
                "mitigation": ["x"],
                "blocked_actions": [],
                "escalation_conditions": [],
            }
        )
    elif payload["current_artifact_type"] == "decision":
        base.update(
            {
                "recommended_path": "x",
                "rejected_alternatives": [],
                "decision_rationale": "x",
                "tradeoffs": [],
                "confidence": 0.8,
                "council_recommendation": "x",
            }
        )
    elif payload["current_artifact_type"] == "handoff":
        base.update(
            {
                "approved_execution_brief": {"goal": "x"},
                "execution_scope": ["x"],
                "execution_constraints": ["x"],
                "no_go_zones": ["x"],
                "required_receipts": ["x"],
                "owner_approval_status": "approved",
                "execution_readiness_status": "blocked",
            }
        )
    else:
        raise AssertionError("unsupported artifact type in sample")
    return base


def test_action_keyword_maps_to_feedback_and_transition() -> None:
    payload = _case("action-needs_fix")["payload"]
    result = map_feishu_feedback(payload)
    assert result.is_mapped is True
    assert result.mapping_type == "action_keyword"
    assert result.feedback_type == "needs_fix"
    assert result.owner_feedback is not None
    assert result.suggested_transition_request is not None
    assert result.suggested_transition_request["target_status"] == "needs_fix"
    assert result.dictionary_version is not None
    assert result.policy_version is not None


def test_action_approved_and_rejected_mapping() -> None:
    approved = map_feishu_feedback(_case("action-approved")["payload"])
    rejected = map_feishu_feedback(_case("action-rejected")["payload"])
    assert approved.feedback_type == "approval_note"
    assert approved.suggested_transition_request is not None
    assert approved.suggested_transition_request["target_status"] == "owner_approved"
    assert rejected.feedback_type == "reject"
    assert rejected.suggested_transition_request is not None
    assert rejected.suggested_transition_request["target_status"] == "owner_rejected"


def test_section_alias_rules_are_hit() -> None:
    risk_result = map_feishu_feedback(_case("nl-risk-not-enough")["payload"])
    scope_result = map_feishu_feedback(_case("nl-scope-too-wide")["payload"])
    receipt_result = map_feishu_feedback(_case("nl-receipt-not-clear")["payload"])
    assert risk_result.target_section == "risk"
    assert scope_result.target_section == "scope"
    assert receipt_result.target_section == "receipts"


def test_ambiguous_text_not_misclassified_as_approval() -> None:
    result = map_feishu_feedback(_case("ambiguous-xingba")["payload"])
    assert result.feedback_type == "comment"
    assert result.suggested_transition_request is None
    assert "ambiguous_acknowledgement" in result.ambiguity_flags


def test_missing_context_returns_required_context_missing() -> None:
    payload = copy.deepcopy(_case("action-needs_fix")["payload"])
    payload["current_artifact_id"] = ""
    result = map_feishu_feedback(payload)
    assert result.is_mapped is False
    assert "required_context_missing" in result.ambiguity_flags
    assert "current_artifact_id" in result.required_context_missing


def test_adapter_output_can_be_consumed_by_state_machine_validator() -> None:
    payload = _case("action-needs_fix")["payload"]
    result = map_feishu_feedback(payload)
    assert result.suggested_transition_request is not None
    artifact = _build_artifact_from_payload(payload)
    artifact["owner_feedback"] = [result.owner_feedback]

    transition = TransitionRequest.from_dict(result.suggested_transition_request)
    validation = validate_transition(artifact, transition)
    assert validation.is_valid is True


def test_illegal_suggested_transition_is_blocked_by_state_machine() -> None:
    payload = copy.deepcopy(_case("action-needs_fix")["payload"])
    payload["current_artifact_status"] = "draft"
    result = map_feishu_feedback(payload)
    assert result.suggested_transition_request is not None

    artifact = _build_artifact_from_payload(payload)
    artifact["status"] = "draft"
    artifact["owner_feedback"] = [result.owner_feedback]

    transition = TransitionRequest.from_dict(result.suggested_transition_request)
    validation = validate_transition(artifact, transition)
    assert validation.is_valid is False
    assert any("illegal state transition" in err for err in validation.validation_errors)


def test_mapping_result_artifact_can_be_written(tmp_path: Path) -> None:
    payload = _case("nl-comment-not-approval")["payload"]
    result = map_feishu_feedback(payload)
    out = tmp_path / "mapping_result.json"
    write_mapping_result(result, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["message_id"] == payload["message_id"]
