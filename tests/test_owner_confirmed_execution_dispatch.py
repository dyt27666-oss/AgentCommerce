from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.owner_confirmed_execution_dispatch import dispatch_owner_confirmed_execution


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _handoff(*, readiness: str = "ready") -> dict:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "handoff-dispatch-001",
        "request_id": "req-dispatch-001",
        "brief_id": "brief-dispatch-001",
        "handoff_id": "handoff-dispatch-001",
        "council_round": 1,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_dispatch",
        "created_at": "2026-03-16T22:00:00+08:00",
        "updated_at": "2026-03-16T22:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": "handoff_ready",
        "summary": "dispatch test",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "dispatch",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "run task", "expected_outputs": ["receipt"]},
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["no destructive commands"],
        "no_go_zones": ["secrets"],
        "required_receipts": ["execution.receipt.v0.1"],
        "owner_approval_status": "approved",
        "execution_readiness_status": readiness,
    }


def test_valid_dispatch_success(monkeypatch, tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.json"
    _write(handoff_path, _handoff(readiness="ready"))

    monkeypatch.setattr(
        "tools.council_bridge.owner_confirmed_execution_dispatch.dispatch_from_execution_brief",
        lambda **kwargs: {"dispatch_status": "dispatched"},
    )

    result = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_path,
        trigger={"is_trigger": True, "authorized": True, "keyword": "dispatch_execution", "requested_by_lane": "owner"},
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed",
        dispatch_result_path=tmp_path / "dispatch_result.json",
        runtime_status_path=tmp_path / "runtime.json",
        execution_receipt_path=tmp_path / "receipt.json",
        execution_brief_path=tmp_path / "brief.json",
    )
    assert result["dispatch_status"] == "accepted"
    assert result["execution_status"] == "started"
    assert (tmp_path / "receipt.json").exists()


def test_blocked_dispatch_when_readiness_not_ready(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.json"
    _write(handoff_path, _handoff(readiness="blocked"))

    result = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_path,
        trigger={"is_trigger": True, "authorized": True, "keyword": "dispatch_execution", "requested_by_lane": "owner"},
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed",
        dispatch_result_path=tmp_path / "dispatch_result.json",
        runtime_status_path=tmp_path / "runtime.json",
        execution_receipt_path=tmp_path / "receipt.json",
        execution_brief_path=tmp_path / "brief.json",
    )
    assert result["dispatch_status"] == "blocked"
    assert "execution_readiness_status" in result["dispatch_error"]


def test_invalid_source_chat_lane_blocked(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.json"
    _write(handoff_path, _handoff(readiness="ready"))

    result = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_path,
        trigger={"is_trigger": True, "authorized": False, "keyword": "dispatch_execution", "requested_by_lane": "chat"},
        confirmed_by="owner_001",
        confirmed_by_lane="chat",
        current_stage="execution_dispatch",
        reason="chat text",
        dispatch_result_path=tmp_path / "dispatch_result.json",
        runtime_status_path=tmp_path / "runtime.json",
        execution_receipt_path=tmp_path / "receipt.json",
        execution_brief_path=tmp_path / "brief.json",
    )
    assert result["dispatch_status"] == "blocked"
    assert "owner/bridge" in result["dispatch_error"]


def test_missing_brief_generation_failure_blocks(monkeypatch, tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.json"
    _write(handoff_path, _handoff(readiness="ready"))

    def _boom(*args, **kwargs):
        raise RuntimeError("brief fail")

    monkeypatch.setattr("tools.council_bridge.owner_confirmed_execution_dispatch.build_execution_brief", _boom)
    result = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_path,
        trigger={"is_trigger": True, "authorized": True, "keyword": "dispatch_execution", "requested_by_lane": "owner"},
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed",
        dispatch_result_path=tmp_path / "dispatch_result.json",
        runtime_status_path=tmp_path / "runtime.json",
        execution_receipt_path=tmp_path / "receipt.json",
        execution_brief_path=tmp_path / "brief.json",
    )
    assert result["dispatch_status"] == "blocked"
    assert "brief generation failed" in result["dispatch_error"]

