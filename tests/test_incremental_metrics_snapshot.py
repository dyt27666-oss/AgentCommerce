from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge import feishu_message_router as router_mod
from tools.council_bridge.incremental_metrics_snapshot import (
    build_incremental_metrics_snapshot,
    write_incremental_metrics_snapshot,
)
from tools.council_bridge.policy_publish_fsm import (
    STATUS_APPLIED,
    STATUS_CONFIRMED,
    STATUS_REJECTED,
    STATUS_ROLLED_BACK,
    advance_publish_status,
    create_publish_request,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(message_id: str) -> dict:
    return {
        "source": "webhook",
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_scope",
        "sender_id": "owner_001",
        "sender_name": "owner",
        "text": "free text",
        "create_time": "1711111111",
        "workspace_id": "ws_alpha",
        "project_id": "pj_market",
    }


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
                "versions": {"v1": "config/owner_intent_aliases.v0.1.json", "v2": "config/owner_intent_aliases.v0.2.json"},
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


def test_router_scope_events_written(monkeypatch, tmp_path: Path) -> None:
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
    source_artifact = tmp_path / "dispatch_ready.json"
    _write(source_artifact, {"request_id": "req-1", "brief_id": "brief-1", "handoff_id": "handoff-1"})

    router_mod.route_message(
        _payload("m-router-evt"),
        source_artifact=source_artifact.as_posix(),
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "events_dedupe.json",
    )

    lines = [x for x in (tmp_path / "events.log").read_text(encoding="utf-8").splitlines() if x.strip()]
    event_types = [json.loads(x)["event_type"] for x in lines]
    assert "scope_validation_result" in event_types
    assert "router_scope_observe_result" in event_types


def test_publish_applied_rejected_rollback_events_written(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)

    req_path = tmp_path / "req.json"
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"
    audit = tmp_path / "audit.json"
    event_log = tmp_path / "events.log"
    event_dedupe = tmp_path / "events_dedupe.json"

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="event test",
        output_path=req_path,
    )
    advance_publish_status(
        request_path=req_path,
        target_status=STATUS_REJECTED,
        actor="owner_001",
        note="reject",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        governance_event_log_path=event_log,
        governance_dedupe_index_path=event_dedupe,
    )

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="event test 2",
        output_path=req_path,
    )
    advance_publish_status(
        request_path=req_path,
        target_status=STATUS_CONFIRMED,
        actor="owner_001",
        note="confirm",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        governance_event_log_path=event_log,
        governance_dedupe_index_path=event_dedupe,
    )
    advance_publish_status(
        request_path=req_path,
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        governance_event_log_path=event_log,
        governance_dedupe_index_path=event_dedupe,
    )
    advance_publish_status(
        request_path=req_path,
        target_status=STATUS_ROLLED_BACK,
        actor="owner_001",
        note="rollback",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        governance_event_log_path=event_log,
        governance_dedupe_index_path=event_dedupe,
    )

    events = [json.loads(x) for x in (event_log).read_text(encoding="utf-8").splitlines() if x.strip()]
    statuses = [e["status"] for e in events if e["event_type"] == "policy_publish_result"]
    assert "rejected" in statuses
    assert "applied" in statuses
    assert "rolled_back" in statuses


def test_snapshot_from_event_log_and_by_scope(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    lines = [
        {
            "event_id": "e1",
            "event_type": "scope_validation_result",
            "occurred_at": "2026-03-17T10:00:00+08:00",
            "request_id": "req-1",
            "publish_id": None,
            "workspace_id": "ws1",
            "project_id": "pj1",
            "owner_id": "ownerA",
            "source_module": "x",
            "source_artifact": "a",
            "status": "degraded_continue",
            "payload_summary": {},
            "dedupe_key": "k1",
        },
        {
            "event_id": "e2",
            "event_type": "router_scope_observe_result",
            "occurred_at": "2026-03-17T10:01:00+08:00",
            "request_id": "req-1",
            "publish_id": None,
            "workspace_id": "ws1",
            "project_id": "pj1",
            "owner_id": "ownerA",
            "source_module": "x",
            "source_artifact": "a",
            "status": "degraded_continue",
            "payload_summary": {},
            "dedupe_key": "k2",
        },
        {
            "event_id": "e3",
            "event_type": "policy_publish_result",
            "occurred_at": "2026-03-17T10:02:00+08:00",
            "request_id": None,
            "publish_id": "pub-1",
            "workspace_id": "ws1",
            "project_id": "pj1",
            "owner_id": "ownerA",
            "source_module": "x",
            "source_artifact": "a",
            "status": "applied",
            "payload_summary": {},
            "dedupe_key": "k3",
        },
    ]
    log.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")

    snap = build_incremental_metrics_snapshot(event_log_path=log, artifacts_dir=tmp_path)
    assert snap["source"] == "event_log"
    assert snap["scope_validation"]["total"] == 1
    assert snap["router_scope_observe"]["total"] == 1
    assert snap["policy_publish"]["applied"] == 1
    assert "workspace:ws1|project:pj1|owner:ownerA" in snap["by_scope"]

    out = tmp_path / "snapshot.json"
    write_incremental_metrics_snapshot(snap, out)
    assert out.exists()


def test_snapshot_fallback_to_full_scan_when_event_log_empty(tmp_path: Path) -> None:
    _write(tmp_path / "council_feishu_feedback_mapping_result.json", {"is_mapped": True, "ambiguity_flags": []})
    snap = build_incremental_metrics_snapshot(event_log_path=tmp_path / "missing.log", artifacts_dir=tmp_path, fallback_to_full_scan=True)
    assert snap["source"] == "full_scan_fallback"
    assert "summary" in snap
