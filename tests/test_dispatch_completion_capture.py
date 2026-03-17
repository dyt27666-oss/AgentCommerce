from __future__ import annotations

from tools.council_bridge.dispatch_completion_capture import build_completion_observation


def _dispatch_dispatched() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_attempted": True,
        "dispatch_status": "dispatched",
        "dispatch_process": {"pid": None, "mode": "spawn", "state": "running"},
    }


def _execution_receipt() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "execution_status": "completed",
    }


def test_completion_observation_not_dispatched() -> None:
    obs = build_completion_observation(
        {
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
            "dispatch_attempted": False,
            "dispatch_status": "blocked",
            "blocking_reason": "gate failed",
        }
    )
    assert obs["completion_observation_status"] == "not_dispatched"


def test_completion_observation_execution_receipt_available() -> None:
    obs = build_completion_observation(_dispatch_dispatched(), _execution_receipt())
    assert obs["completion_observation_status"] == "execution_receipt_available"
    assert obs["execution_status"] == "completed"


def test_completion_observation_unknown_without_pid_or_receipt() -> None:
    obs = build_completion_observation(_dispatch_dispatched(), None)
    assert obs["completion_observation_status"] == "unknown_process_state"
