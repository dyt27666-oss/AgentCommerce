from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import feishu_message_router as router_mod


def _payload(*, text: str, message_id: str, source: str = "feishu_chat") -> dict:
    return {
        "source": source,
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_role",
        "sender_id": "owner_001",
        "sender_name": "owner",
        "text": text,
        "create_time": "1711111111",
    }


def _write_plan(path: Path, status: str = "under_review") -> None:
    data = {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "plan-role-001",
        "request_id": "req-role-001",
        "brief_id": "brief-role-001",
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": "oc_role",
        "created_at": "2026-03-16T21:00:00+08:00",
        "updated_at": "2026-03-16T21:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "role rework test",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "owner review",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "objective": "x",
        "scope": ["x"],
        "steps": [{"step_id": "s1", "title": "x"}],
        "dependencies": [],
        "acceptance_criteria": ["x"],
        "proposed_execution_boundary": {"execution_allowed": False},
        "expected_outputs": ["x"],
        "role_metadata": {
            "role": "planner",
            "role_round": 1,
            "role_run_id": "planner-r1",
            "depends_on_roles": [],
            "upstream_artifact_ids": [],
            "owner_feedback_ids": [],
            "rerun_of_role_run_id": None,
            "execution_authority": False,
            "generated_at": "2026-03-16T21:00:00+08:00",
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_router_role_rework_observe_only(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan.json"
    _write_plan(artifact_path)

    result = router_mod.route_message(
        _payload(text="让 strategist 重写", message_id="m-role-obs", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
        council_role_rework_mapping_result_path=tmp_path / "role_mapping.json",
        council_role_rework_transition_result_path=tmp_path / "role_validation.json",
        council_role_rework_apply_result_path=tmp_path / "role_apply.json",
        council_role_rework_advisory_path=tmp_path / "role_advisory.json",
    )

    assert result["route_type"] == "council"
    assert result["routed_entrypoint"] == "council_role_rework_observer"
    assert result["observe_only"] is True
    assert result["mapping_status"] == "mapped"
    assert result["validation_status"] == "valid"
    assert "target_role=strategist" in result["suggested_transition_summary"]

    after = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert after["status"] == "under_review"


def test_router_role_rework_confirm_apply_and_generate_advisory(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan.json"
    _write_plan(artifact_path)

    router_mod.route_message(
        _payload(text="让 strategist 重写", message_id="m-role-obs2", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe1.json",
        route_result_path=tmp_path / "route1.json",
        queue_db_path=tmp_path / "queue.db",
        council_role_rework_mapping_result_path=tmp_path / "role_mapping.json",
        council_role_rework_transition_result_path=tmp_path / "role_validation.json",
        council_role_rework_apply_result_path=tmp_path / "role_apply.json",
        council_role_rework_advisory_path=tmp_path / "role_advisory.json",
    )

    confirm = router_mod.route_message(
        _payload(text="confirm_role_rework", message_id="m-role-confirm", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe2.json",
        route_result_path=tmp_path / "route2.json",
        queue_db_path=tmp_path / "queue.db",
        council_role_rework_mapping_result_path=tmp_path / "role_mapping.json",
        council_role_rework_transition_result_path=tmp_path / "role_validation.json",
        council_role_rework_apply_result_path=tmp_path / "role_apply.json",
        council_role_rework_advisory_path=tmp_path / "role_advisory.json",
    )

    assert confirm["routed_entrypoint"] == "council_role_rework_apply"
    assert confirm["result_status"] == "applied"

    updated = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert updated["status"] == "needs_fix"

    advisory = json.loads((tmp_path / "role_advisory.json").read_text(encoding="utf-8"))
    assert advisory["produced_by_role"] == "strategist"
    assert advisory["status"] == "under_review"


def test_router_chat_cannot_confirm_role_rework(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan.json"
    _write_plan(artifact_path)

    result = router_mod.route_message(
        _payload(text="confirm_role_rework", message_id="m-role-chat-confirm", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
        council_role_rework_mapping_result_path=tmp_path / "role_mapping.json",
        council_role_rework_transition_result_path=tmp_path / "role_validation.json",
        council_role_rework_apply_result_path=tmp_path / "role_apply.json",
        council_role_rework_advisory_path=tmp_path / "role_advisory.json",
    )

    assert result["result_status"] == "ignored"
    assert "plain chat text" in result["result_info"]
    unchanged = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert unchanged["status"] == "under_review"
