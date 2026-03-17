from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import feishu_message_router as router_mod


def _payload(*, text: str, message_id: str, source: str) -> dict:
    return {
        "source": source,
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_exec_gate",
        "sender_id": "owner_001",
        "sender_name": "owner",
        "text": text,
        "create_time": "1711111111",
    }


def _handoff(*, status: str = "handoff_ready", readiness: str = "ready") -> dict:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "handoff-router-exec-001",
        "request_id": "req-router-exec-001",
        "brief_id": "brief-router-exec-001",
        "handoff_id": "handoff-router-exec-001",
        "council_round": 1,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_exec_gate",
        "created_at": "2026-03-16T21:00:00+08:00",
        "updated_at": "2026-03-16T21:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": status,
        "summary": "execution gate router",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "demo objective", "expected_outputs": ["receipt"]},
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["docs only"],
        "no_go_zones": ["secrets"],
        "required_receipts": ["execution_receipt_v0.1"],
        "owner_approval_status": "approved",
        "execution_readiness_status": readiness,
    }


def test_router_execution_handoff_observe_only_ready(tmp_path: Path) -> None:
    artifact_path = tmp_path / "handoff.json"
    artifact_path.write_text(json.dumps(_handoff(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="dispatch_execution", message_id="m-exec-1", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="execution_gate",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        council_execution_gate_result_path=tmp_path / "gate.json",
        council_execution_brief_path=tmp_path / "brief.json",
    )

    assert result["route_type"] == "council"
    assert result["routed_entrypoint"] == "execution_handoff_observer"
    assert result["observe_only"] is True
    assert result["execution_gate_status"] == "ready"
    assert (tmp_path / "brief.json").exists()
    unchanged = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert unchanged["status"] == "handoff_ready"


def test_router_execution_handoff_blocked_when_not_ready(tmp_path: Path) -> None:
    artifact_path = tmp_path / "handoff.json"
    artifact_path.write_text(json.dumps(_handoff(readiness="blocked"), ensure_ascii=False, indent=2), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="confirm_execution_dispatch", message_id="m-exec-2", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="execution_gate",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        council_execution_gate_result_path=tmp_path / "gate.json",
        council_execution_brief_path=tmp_path / "brief.json",
    )
    assert result["execution_gate_status"] == "blocked"
    assert result["result_status"] == "blocked"
    assert not (tmp_path / "brief.json").exists()


def test_chat_text_cannot_trigger_execution_handoff(tmp_path: Path) -> None:
    artifact_path = tmp_path / "handoff.json"
    artifact_path.write_text(json.dumps(_handoff(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="dispatch_execution", message_id="m-exec-3", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="execution_gate",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        council_execution_gate_result_path=tmp_path / "gate.json",
        council_execution_brief_path=tmp_path / "brief.json",
    )
    assert result["execution_gate_status"] == "blocked"
    assert "no execution dispatch" in result["result_info"]


def test_router_execution_dispatch_stage_calls_real_dispatch_path(monkeypatch, tmp_path: Path) -> None:
    artifact_path = tmp_path / "handoff.json"
    artifact_path.write_text(json.dumps(_handoff(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _fake_dispatch(**kwargs):
        return {
            "dispatch_status": "accepted",
            "dispatch_error": "",
            "execution_status": "started",
            "next_action": "monitor runtime",
        }

    monkeypatch.setattr(
        "tools.council_bridge.feishu_message_router.dispatch_owner_confirmed_execution",
        _fake_dispatch,
    )

    result = router_mod.route_message(
        _payload(text="dispatch_execution", message_id="m-exec-4", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="execution_dispatch",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        council_execution_dispatch_result_path=tmp_path / "dispatch_result.json",
        council_execution_runtime_status_path=tmp_path / "runtime.json",
        council_execution_receipt_path=tmp_path / "receipt.json",
        council_execution_brief_path=tmp_path / "brief.json",
    )
    assert result["routed_entrypoint"] == "owner_confirmed_execution_dispatch"
    assert result["result_status"] == "accepted"


def test_router_execution_dispatch_stage_blocks_chat_source_even_with_keyword(tmp_path: Path) -> None:
    artifact_path = tmp_path / "handoff.json"
    artifact_path.write_text(json.dumps(_handoff(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="dispatch_execution", message_id="m-exec-5", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="execution_dispatch",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        council_execution_dispatch_result_path=tmp_path / "dispatch_result.json",
        council_execution_runtime_status_path=tmp_path / "runtime.json",
        council_execution_receipt_path=tmp_path / "receipt.json",
        council_execution_brief_path=tmp_path / "brief.json",
    )
    assert result["result_status"] == "blocked"
    assert "missing explicit authorized execution trigger" in result["result_info"] or "dispatch_error" not in result
