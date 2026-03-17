from __future__ import annotations

from datetime import datetime

import pytest

from tools.council_bridge.execution_receipt_writer import build_execution_receipt


def _handoff() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
    }


def test_build_execution_receipt_completed() -> None:
    now = datetime.fromisoformat("2026-03-15T18:00:00+08:00")
    receipt = build_execution_receipt(
        handoff=_handoff(),
        execution_status="completed",
        changed_files=["docs/llm-assisted.md"],
        summary="Updated docs wording.",
        next_step_suggestion="Owner review and approve merge.",
        constraints_compliant=True,
        constraints_note="All edits in allowed files.",
        validation_results=["py -m pytest -q: passed"],
        now=now,
    )
    assert receipt["execution_status"] == "completed"
    assert receipt["request_id"] == "exec-req-001"
    assert receipt["brief_id"] == "council-poc-brief-001"
    assert receipt["handoff_id"] == "handoff-20260315-004"
    assert receipt["constraints_compliance"]["compliant"] is True
    assert receipt["generated_at"] == "2026-03-15T18:00:00+08:00"


def test_build_execution_receipt_partial_requires_partial_notes() -> None:
    with pytest.raises(ValueError, match="partial status requires partial_notes"):
        build_execution_receipt(
            handoff=_handoff(),
            execution_status="partial",
            changed_files=[],
            summary="Partial result.",
            next_step_suggestion="Continue in next round.",
            constraints_compliant=True,
            constraints_note="No boundary issue.",
        )


def test_build_execution_receipt_blocked_requires_blocked_reason() -> None:
    with pytest.raises(ValueError, match="blocked status requires blocked_reason"):
        build_execution_receipt(
            handoff=_handoff(),
            execution_status="blocked",
            changed_files=[],
            summary="Blocked.",
            next_step_suggestion="Fix prerequisite first.",
            constraints_compliant=False,
            constraints_note="Could not proceed due to missing scope.",
        )
