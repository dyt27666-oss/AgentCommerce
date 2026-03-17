from __future__ import annotations

from tools.council_bridge.completion_receipt_bridge import build_receipt_prep


def _handoff() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
    }


def _dispatch(status: str = "dispatched") -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_status": status,
    }


def _completion(state: str) -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "completion_observation_status": state,
    }


def test_receipt_prep_ready_when_execution_receipt_available() -> None:
    prep = build_receipt_prep(_handoff(), _dispatch(), _completion("execution_receipt_available"))
    assert prep["receipt_prep_ready"] is True
    assert "Proceed to owner final review" in prep["recommended_next_action"]


def test_receipt_prep_blocked_when_running_no_execution_receipt() -> None:
    prep = build_receipt_prep(_handoff(), _dispatch(), _completion("running_no_execution_receipt"))
    assert prep["receipt_prep_ready"] is False
    assert "still running" in prep["blocking_reason"]


def test_receipt_prep_guidance_when_process_exited_no_execution_receipt() -> None:
    prep = build_receipt_prep(_handoff(), _dispatch(), _completion("process_exited_no_execution_receipt"))
    assert prep["receipt_prep_ready"] is True
    assert "Prepare execution receipt now" in prep["recommended_next_action"]


def test_receipt_prep_blocked_on_identity_mismatch() -> None:
    bad_completion = _completion("execution_receipt_available")
    bad_completion["brief_id"] = "wrong"
    prep = build_receipt_prep(_handoff(), _dispatch(), bad_completion)
    assert prep["receipt_prep_ready"] is False
    assert "identity mismatch" in prep["blocking_reason"]
