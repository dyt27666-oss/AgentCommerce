from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import feishu_message_router as router_mod


def _payload(
    *,
    text: str,
    message_id: str,
    source: str = "webhook",
    chat_id: str = "oc_scope",
    workspace_id: str = "ws_alpha",
    project_id: str = "pj_market",
    scope_validation_mode: str = "",
) -> dict:
    return {
        "source": source,
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": chat_id,
        "sender_id": "owner_001",
        "sender_name": "owner",
        "text": text,
        "create_time": "1711111111",
        "workspace_id": workspace_id,
        "project_id": project_id,
        "scope_validation_mode": scope_validation_mode,
    }


def _runner_ok(_calls: list[list[str]]):
    def _run(command: list[str]):
        _calls.append(command)
        return "success", "ok"

    return _run


def _write_dispatch_artifact(path: Path) -> None:
    path.write_text(
        json.dumps({"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_plan_artifact(path: Path, *, status: str = "under_review") -> None:
    artifact = {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "plan-scope-001",
        "request_id": "req-scope-001",
        "brief_id": "brief-scope-001",
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": "oc_scope",
        "created_at": "2026-03-16T21:00:00+08:00",
        "updated_at": "2026-03-16T21:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "scope test",
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


def test_scope_validation_strict_pass_chat_route_unchanged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "default>workspace:ws_alpha>project:pj_market",
            "alias_scope": "default>workspace:ws_alpha>project:pj_market",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "scope_validation_mode": "strict",
        },
    )
    dispatch = tmp_path / "dispatch.json"
    _write_dispatch_artifact(dispatch)
    result = router_mod.route_message(
        _payload(text="free text", message_id="m1"),
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "d1.json",
        route_result_path=tmp_path / "r1.json",
        queue_db_path=tmp_path / "q1.db",
    )
    assert result["route_type"] == "chat"
    assert result["scope_validation"]["is_valid"] is True
    assert result["scope_validation"]["action"] == "pass"


def test_scope_validation_lenient_missing_workspace_degraded_chat_unchanged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "default",
            "alias_scope": "default",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": None,
            "project_id": None,
            "scope_validation_mode": "lenient",
        },
    )
    dispatch = tmp_path / "dispatch.json"
    _write_dispatch_artifact(dispatch)
    result = router_mod.route_message(
        _payload(text="free text", message_id="m2", workspace_id="", project_id=""),
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "d2.json",
        route_result_path=tmp_path / "r2.json",
        queue_db_path=tmp_path / "q2.db",
    )
    assert result["route_type"] == "chat"
    assert result["scope_validation"]["is_valid"] is True
    assert result["scope_validation"]["action"] == "degraded_continue"


def test_scope_validation_strict_blocked_does_not_change_action_route(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "bad_scope",
            "alias_scope": "bad_scope",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "",
            "project_id": "",
            "scope_validation_mode": "strict",
        },
    )
    dispatch = tmp_path / "dispatch.json"
    _write_dispatch_artifact(dispatch)
    result = router_mod.route_message(
        _payload(text="dispatch", message_id="m3", workspace_id="", project_id=""),
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        runner=_runner_ok(calls),
        dedupe_state_path=tmp_path / "d3.json",
        route_result_path=tmp_path / "r3.json",
        queue_db_path=tmp_path / "q3.db",
    )
    assert result["route_type"] == "action"
    assert result["scope_validation"]["action"] == "blocked"
    assert len(calls) == 1


def test_scope_validation_alias_mismatch_strict_observe_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "default>workspace:ws_alpha>project:pj_market",
            "alias_scope": "default>workspace:ws_alpha>project:pj_other",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "scope_validation_mode": "strict",
        },
    )
    artifact = tmp_path / "plan.json"
    _write_plan_artifact(artifact)
    result = router_mod.route_message(
        _payload(text="needs_fix", message_id="m4", source="feishu_action_protocol"),
        source_artifact=artifact.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "d4.json",
        route_result_path=tmp_path / "r4.json",
        queue_db_path=tmp_path / "q4.db",
        council_mapping_result_path=tmp_path / "m4.json",
        council_transition_result_path=tmp_path / "t4.json",
    )
    assert result["route_type"] == "council"
    assert result["scope_validation"]["action"] == "blocked"


def test_scope_validation_invalid_scope_chain_strict_observe_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "default>>workspace:ws_alpha",
            "alias_scope": "default>>workspace:ws_alpha",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "scope_validation_mode": "strict",
        },
    )
    artifact = tmp_path / "plan.json"
    _write_plan_artifact(artifact)
    result = router_mod.route_message(
        _payload(text="needs_fix", message_id="m5", source="feishu_action_protocol"),
        source_artifact=artifact.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "d5.json",
        route_result_path=tmp_path / "r5.json",
        queue_db_path=tmp_path / "q5.db",
        council_mapping_result_path=tmp_path / "m5.json",
        council_transition_result_path=tmp_path / "t5.json",
    )
    assert result["route_type"] == "council"
    assert result["scope_validation"]["is_valid"] is False


def test_scope_validation_lenient_invalid_chain_degraded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "bad_scope",
            "alias_scope": "bad_scope",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "scope_validation_mode": "lenient",
        },
    )
    artifact = tmp_path / "plan.json"
    _write_plan_artifact(artifact)
    result = router_mod.route_message(
        _payload(text="needs_fix", message_id="m6", source="feishu_action_protocol"),
        source_artifact=artifact.as_posix(),
        stage="council_review",
        dedupe_state_path=tmp_path / "d6.json",
        route_result_path=tmp_path / "r6.json",
        queue_db_path=tmp_path / "q6.db",
        council_mapping_result_path=tmp_path / "m6.json",
        council_transition_result_path=tmp_path / "t6.json",
    )
    assert result["route_type"] == "council"
    assert result["scope_validation"]["action"] == "degraded_continue"


def test_scope_validation_present_on_deduped_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": "default",
            "alias_scope": "default",
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "scope_validation_mode": "strict",
        },
    )
    dispatch = tmp_path / "dispatch.json"
    _write_dispatch_artifact(dispatch)
    payload = _payload(text="free text", message_id="m7")

    _ = router_mod.route_message(
        payload,
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "d7.json",
        route_result_path=tmp_path / "r7a.json",
        queue_db_path=tmp_path / "q7.db",
    )
    second = router_mod.route_message(
        payload,
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "d7.json",
        route_result_path=tmp_path / "r7b.json",
        queue_db_path=tmp_path / "q7.db",
    )
    assert second["result_status"] == "deduped"
    assert second["scope_validation"]["mode"] == "strict"


def test_scope_validation_null_inputs_lenient_degraded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda **kwargs: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": [],
            "policy_scope": None,
            "alias_scope": None,
            "policy_version": "policy.center.v0.1",
            "active_alias_version": "owner.intent.alias.v0.1",
            "workspace_id": None,
            "project_id": None,
            "scope_validation_mode": "lenient",
        },
    )
    dispatch = tmp_path / "dispatch.json"
    _write_dispatch_artifact(dispatch)
    result = router_mod.route_message(
        _payload(text="free text", message_id="m8", workspace_id="", project_id=""),
        source_artifact=dispatch.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "d8.json",
        route_result_path=tmp_path / "r8.json",
        queue_db_path=tmp_path / "q8.db",
    )
    assert result["route_type"] == "chat"
    assert result["scope_validation"]["action"] == "degraded_continue"
