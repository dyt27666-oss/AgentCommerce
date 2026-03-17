from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.council_bridge.council_artifact_state_machine import (
    TransitionRequest,
    apply_transition,
    validate_transition,
    write_transition_audit,
)


SAMPLES_PATH = Path("docs") / "council_artifact_state_machine_samples_v0.1" / "transition_samples.json"


def _load_cases() -> list[dict]:
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8-sig"))
    return data["cases"]


def _case(case_id: str) -> dict:
    for case in _load_cases():
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing sample case: {case_id}")


def test_legal_transitions_pass() -> None:
    legal_ids = [
        "legal-under_review-to-needs_fix",
        "legal-needs_fix-to-revised",
        "legal-revised-to-resubmitted",
        "legal-ready_for_owner_review-to-owner_approved",
    ]
    for case_id in legal_ids:
        case = _case(case_id)
        req = TransitionRequest.from_dict(case["request"])
        result = validate_transition(case["artifact"], req)
        assert result.is_valid is True, case_id


def test_illegal_transitions_blocked() -> None:
    illegal_ids = [
        "illegal-draft-to-owner_approved",
        "illegal-needs_fix-to-handoff_ready",
        "illegal-owner_rejected-to-owner_approved",
        "illegal-chat-lane-owner_approved",
    ]
    for case_id in illegal_ids:
        case = _case(case_id)
        req = TransitionRequest.from_dict(case["request"])
        result = validate_transition(case["artifact"], req)
        assert result.is_valid is False, case_id
        assert len(result.validation_errors) > 0, case_id


def test_owner_feedback_affects_under_review_to_needs_fix() -> None:
    case = _case("legal-under_review-to-needs_fix")
    artifact = copy.deepcopy(case["artifact"])
    expected_feedback = copy.deepcopy(case["artifact"]["owner_feedback"])
    request = dict(case["request"])
    request["triggering_feedback_id"] = None
    artifact["owner_feedback"] = []

    req = TransitionRequest.from_dict(request)
    blocked = validate_transition(artifact, req)
    assert blocked.is_valid is False
    assert any("owner feedback" in msg for msg in blocked.validation_errors)

    artifact["owner_feedback"] = expected_feedback
    passed = validate_transition(artifact, req)
    assert passed.is_valid is True


def test_lineage_missing_blocks_revised_and_resubmitted() -> None:
    case = _case("legal-revised-to-resubmitted")
    artifact = case["artifact"]
    artifact["parent_artifact_id"] = None
    artifact["derived_from_artifact_ids"] = []
    artifact["lineage"] = {}

    req = TransitionRequest.from_dict(case["request"])
    result = validate_transition(artifact, req)
    assert result.is_valid is False
    assert "lineage.revision_completed" in " ".join(result.required_missing_fields)


def test_handoff_readiness_controls_execution_candidate() -> None:
    not_ready = _case("handoff-owner_approved-not-ready")
    ready = _case("handoff-owner_approved-ready")

    result_not_ready = validate_transition(not_ready["artifact"], TransitionRequest.from_dict(not_ready["request"]))
    assert result_not_ready.is_valid is False
    assert result_not_ready.execution_gate_candidate is False

    result_ready = validate_transition(ready["artifact"], TransitionRequest.from_dict(ready["request"]))
    assert result_ready.is_valid is True
    assert result_ready.execution_gate_candidate is True


def test_chat_lane_cannot_emit_owner_approved() -> None:
    case = _case("illegal-chat-lane-owner_approved")
    req = TransitionRequest.from_dict(case["request"])
    result = validate_transition(case["artifact"], req)
    assert result.is_valid is False
    assert any("chat lane" in msg for msg in result.validation_errors)


def test_apply_transition_updates_status_and_audit(tmp_path: Path) -> None:
    case = _case("legal-needs_fix-to-revised")
    req = TransitionRequest.from_dict(case["request"])
    updated, result = apply_transition(case["artifact"], req)
    assert result.is_valid is True
    assert updated["status"] == "revised"
    assert isinstance(updated["audit_trace"], list)
    assert len(updated["audit_trace"]) >= 1

    out = tmp_path / "transition_result.json"
    write_transition_audit(result, out)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["from_status"] == "needs_fix"
    assert payload["to_status"] == "revised"
