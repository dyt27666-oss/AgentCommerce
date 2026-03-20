from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import feishu_message_router as router_mod


def _runner_recorder(calls: list[list[str]]):
    def _run(command: list[str]):
        calls.append(command)
        return "success", "ok"

    return _run


def _payload(*, text: str, message_id: str, source: str = "feishu_chat", chat_id: str = "oc_test") -> dict:
    return {
        "source": source,
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": chat_id,
        "sender_id": "owner_001",
        "sender_name": "owner",
        "text": text,
        "create_time": "1711111111",
    }


def _write_plan_artifact(path: Path, status: str, include_context: bool = True) -> None:
    artifact = {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "plan-router-001",
        "request_id": "req-router-001" if include_context else "",
        "brief_id": "brief-router-001" if include_context else "",
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": "oc_test",
        "created_at": "2026-03-16T16:00:00+08:00",
        "updated_at": "2026-03-16T16:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "router test",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
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
    }
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def test_router_council_feedback_triggers_mapping_and_validation_observe_only(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan.json"
    mapping_path = tmp_path / "mapping.json"
    transition_path = tmp_path / "transition.json"
    route_path = tmp_path / "route.json"
    dedupe_path = tmp_path / "dedupe.json"
    queue_db = tmp_path / "queue.db"
    _write_plan_artifact(artifact_path, status="under_review", include_context=True)

    result = router_mod.route_message(
        _payload(text="needs_fix", message_id="m-council-1", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=dedupe_path,
        route_result_path=route_path,
        queue_db_path=queue_db,
        council_mapping_result_path=mapping_path,
        council_transition_result_path=transition_path,
    )

    assert result["route_type"] == "council"
    assert result["observe_only"] is True
    assert result["mapping_status"] == "mapped"
    assert result["validation_status"] == "valid"
    assert "no state change applied" in result["result_info"]
    assert mapping_path.exists()
    assert transition_path.exists()

    after = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert after["status"] == "under_review"


def test_router_council_feedback_missing_context_returns_ambiguity(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan_missing_context.json"
    mapping_path = tmp_path / "mapping.json"
    route_path = tmp_path / "route.json"
    _write_plan_artifact(artifact_path, status="under_review", include_context=False)

    result = router_mod.route_message(
        _payload(text="这个不太行", message_id="m-council-2", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=route_path,
        queue_db_path=tmp_path / "queue.db",
        council_mapping_result_path=mapping_path,
        council_transition_result_path=tmp_path / "transition.json",
    )

    assert result["route_type"] == "council"
    assert result["mapping_status"] == "ignored"
    assert result["validation_status"].startswith("skipped")

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert "required_context_missing" in mapping["ambiguity_flags"]


def test_router_council_illegal_suggested_transition_blocked(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan_draft.json"
    transition_path = tmp_path / "transition.json"
    _write_plan_artifact(artifact_path, status="draft", include_context=True)

    result = router_mod.route_message(
        _payload(text="needs_fix", message_id="m-council-3", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
        council_mapping_result_path=tmp_path / "mapping.json",
        council_transition_result_path=transition_path,
    )

    assert result["route_type"] == "council"
    assert result["validation_status"] == "invalid"
    transition = json.loads(transition_path.read_text(encoding="utf-8"))
    assert transition["is_valid"] is False


def test_action_and_chat_lane_not_regressed_by_council_observer(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    dispatch_artifact = tmp_path / "dispatch_ready.json"
    dispatch_artifact.write_text(
        json.dumps({"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1", "dispatch_ready": True}),
        encoding="utf-8",
    )

    action_result = router_mod.route_message(
        _payload(text="dispatch", message_id="m-action-1", source="webhook"),
        source_artifact=dispatch_artifact.as_posix(),
        stage="dispatch_ready",
        runner=_runner_recorder(calls),
        dedupe_state_path=tmp_path / "dedupe1.json",
        route_result_path=tmp_path / "route1.json",
        queue_db_path=tmp_path / "q1.db",
    )
    assert action_result["route_type"] == "action"
    assert len(calls) == 1

    chat_result = router_mod.route_message(
        _payload(text="请总结进展", message_id="m-chat-1", source="webhook"),
        source_artifact=dispatch_artifact.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe2.json",
        route_result_path=tmp_path / "route2.json",
        queue_db_path=tmp_path / "q2.db",
    )
    assert chat_result["route_type"] == "chat"
    assert chat_result["result_status"] == "queued"


def test_router_owner_confirm_signal_applies_transition_after_observe(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan_apply.json"
    mapping_path = tmp_path / "mapping.json"
    validation_path = tmp_path / "validation.json"
    apply_path = tmp_path / "apply.json"
    _write_plan_artifact(artifact_path, status="under_review", include_context=True)

    observe = router_mod.route_message(
        _payload(text="风险分析不够", message_id="m-observe-1", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe1.json",
        route_result_path=tmp_path / "route_observe.json",
        queue_db_path=tmp_path / "queue.db",
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
    )
    assert observe["observe_only"] is True
    assert observe["validation_status"] == "valid"

    confirm = router_mod.route_message(
        _payload(text="apply_suggested_transition", message_id="m-confirm-1", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe2.json",
        route_result_path=tmp_path / "route_confirm.json",
        queue_db_path=tmp_path / "queue.db",
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
    )
    assert confirm["route_type"] == "council"
    assert confirm["result_status"] == "applied"
    updated = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert updated["status"] == "needs_fix"


def test_router_chat_confirm_keyword_does_not_apply(tmp_path: Path) -> None:
    artifact_path = tmp_path / "plan_no_apply.json"
    _write_plan_artifact(artifact_path, status="under_review", include_context=True)

    result = router_mod.route_message(
        _payload(text="confirm_transition", message_id="m-chat-confirm", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
        council_mapping_result_path=tmp_path / "mapping.json",
        council_transition_result_path=tmp_path / "validation.json",
        council_owner_apply_result_path=tmp_path / "apply.json",
    )
    assert result["result_status"] == "ignored"
    unchanged = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert unchanged["status"] == "under_review"


def test_router_records_mode_detection_fields_for_plain_chat(tmp_path: Path) -> None:
    dispatch_artifact = tmp_path / "dispatch_ready.json"
    dispatch_artifact.write_text(json.dumps({"request_id": "req-1"}), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="今天先同步进度", message_id="m-mode-chat", source="feishu_chat"),
        source_artifact=dispatch_artifact.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
    )
    assert result["detected_mode"] == "chat"
    assert result["detection_reason"]
    assert result["rule_hit"] == "chat_fallback"
    assert result["response_profile"] == "chat_conversation"
    assert result["artifact_visibility"] == "owner_visible"


def test_router_explicit_workflow_request_not_treated_as_idle_chat(tmp_path: Path) -> None:
    dispatch_artifact = tmp_path / "dispatch_ready.json"
    dispatch_artifact.write_text(json.dumps({"request_id": "req-1"}), encoding="utf-8")

    result = router_mod.route_message(
        _payload(text="请开始执行并运行测试", message_id="m-mode-workflow", source="feishu_chat"),
        source_artifact=dispatch_artifact.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "queue.db",
    )
    assert result["detected_mode"] == "workflow_request"
    assert result["route_type"] == "workflow_request"
    assert result["result_status"] == "needs_owner_action_protocol"
    assert result["response_profile"] == "workflow_control"
