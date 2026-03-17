from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge.policy_publish_fsm import (
    STATUS_APPLIED,
    STATUS_CONFIRMED,
    STATUS_PROPOSED,
    STATUS_REJECTED,
    STATUS_ROLLED_BACK,
    create_publish_request,
    advance_publish_status,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _bootstrap_policy_center(monkeypatch, tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    owner = tmp_path / "owner_overrides.json"
    group = tmp_path / "group_overrides.json"
    workspace = tmp_path / "workspace_overrides.json"
    project = tmp_path / "project_overrides.json"

    _write(
        default,
        {
            "policy_version": "policy.center.v0.1",
            "lane_switches": {},
            "alias_registry": {
                "active_version": "v1",
                "versions": {
                    "v1": "config/owner_intent_aliases.v0.1.json",
                    "v2": "config/owner_intent_aliases.v0.2.json",
                },
            },
        },
    )
    _write(owner, {})
    _write(group, {})
    _write(workspace, {})
    _write(project, {})

    monkeypatch.setattr(pcc, "DEFAULT_CONFIG_PATH", default)
    monkeypatch.setattr(pcc, "OWNER_OVERRIDES_PATH", owner)
    monkeypatch.setattr(pcc, "GROUP_OVERRIDES_PATH", group)
    monkeypatch.setattr(pcc, "WORKSPACE_OVERRIDES_PATH", workspace)
    monkeypatch.setattr(pcc, "PROJECT_OVERRIDES_PATH", project)


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "request": tmp_path / "policy_publish_request.json",
        "review": tmp_path / "policy_publish_review.json",
        "result": tmp_path / "policy_publish_result.json",
        "audit": tmp_path / "policy_change_audit_pack.json",
    }


def test_propose_confirm_apply_success_owner_scope(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)

    req = create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="upgrade alias",
        output_path=p["request"],
    )
    assert req["status"] == STATUS_PROPOSED

    confirm = advance_publish_status(
        request_path=p["request"],
        target_status=STATUS_CONFIRMED,
        actor="owner_001",
        note="confirm publish",
        review_artifact_path=p["review"],
        result_artifact_path=p["result"],
        audit_pack_path=p["audit"],
    )
    assert confirm["status"] == STATUS_CONFIRMED

    applied = advance_publish_status(
        request_path=p["request"],
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply publish",
        review_artifact_path=p["review"],
        result_artifact_path=p["result"],
        audit_pack_path=p["audit"],
    )
    assert applied["status"] == STATUS_APPLIED
    assert applied["before"]["active_alias_version"] == "v1"
    assert applied["after"]["active_alias_version"] == "v2"


def test_propose_reject(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="reject test",
        output_path=p["request"],
    )
    rejected = advance_publish_status(
        request_path=p["request"],
        target_status=STATUS_REJECTED,
        actor="owner_001",
        note="reject",
        review_artifact_path=p["review"],
        result_artifact_path=p["result"],
        audit_pack_path=p["audit"],
    )
    assert rejected["status"] == STATUS_REJECTED


def test_apply_illegal_jump_blocked(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="illegal jump",
        output_path=p["request"],
    )
    result = advance_publish_status(
        request_path=p["request"],
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="skip confirm",
        review_artifact_path=p["review"],
        result_artifact_path=p["result"],
        audit_pack_path=p["audit"],
    )
    assert result["status"] == "blocked"
    assert any("illegal publish transition" in e for e in result["transition_errors"])


def test_rollback_success(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="rollback success",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    advance_publish_status(request_path=p["request"], target_status=STATUS_APPLIED, actor="owner_001", note="apply", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    rollback = advance_publish_status(request_path=p["request"], target_status=STATUS_ROLLED_BACK, actor="owner_001", note="rollback", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert rollback["status"] == STATUS_ROLLED_BACK
    assert rollback["after"]["active_alias_version"] == "v1"


def test_rollback_illegal_source_blocked(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="rollback fail",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    rollback = advance_publish_status(request_path=p["request"], target_status=STATUS_ROLLED_BACK, actor="owner_001", note="rollback", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert rollback["status"] == "blocked"


def test_version_not_found_blocks_apply(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v999"},
        reason="bad version",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    result = advance_publish_status(
        request_path=p["request"],
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=p["review"],
        result_artifact_path=p["result"],
        audit_pack_path=p["audit"],
    )
    assert result["status"] == "blocked_by_regression"


def test_before_after_record_correct(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="before after",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    result = advance_publish_status(request_path=p["request"], target_status=STATUS_APPLIED, actor="owner_001", note="apply", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert result["before"]["active_alias_version"] == "v1"
    assert result["after"]["active_alias_version"] == "v2"


def test_audit_pack_generated_on_apply(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="audit",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    advance_publish_status(request_path=p["request"], target_status=STATUS_APPLIED, actor="owner_001", note="apply", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert p["audit"].exists()
    audit = json.loads(p["audit"].read_text(encoding="utf-8"))
    assert audit["artifact_type"] == "policy_change_audit_pack"


def test_rejected_cannot_be_applied(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="reject then apply",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_REJECTED, actor="owner_001", note="reject", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    result = advance_publish_status(request_path=p["request"], target_status=STATUS_APPLIED, actor="owner_001", note="apply", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert result["status"] == "blocked"


def test_workspace_scope_impact_estimate_placeholder(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    req = create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "workspace", "scope_id": "ws_alpha"},
        change_set={"active_alias_version_to": "v2"},
        reason="workspace publish",
        output_path=p["request"],
    )
    assert req["impact_estimate"].get("method") == "placeholder"


def test_project_scope_apply_success(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    p = _paths(tmp_path)
    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "project", "scope_id": "pj_market"},
        change_set={"active_alias_version_to": "v2"},
        reason="project publish",
        output_path=p["request"],
    )
    advance_publish_status(request_path=p["request"], target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    result = advance_publish_status(request_path=p["request"], target_status=STATUS_APPLIED, actor="owner_001", note="apply", review_artifact_path=p["review"], result_artifact_path=p["result"], audit_pack_path=p["audit"])
    assert result["status"] == STATUS_APPLIED
    assert "project_overrides.json" in result["changed_config_path"]
