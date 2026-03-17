from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.policy_config_center as pcc
import tools.council_bridge.runtime_publish_reconcile_hook as hook


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _request(publish_id: str = "pub-1", from_v: str = "v1", to_v: str = "v2") -> dict:
    return {
        "artifact_type": "policy_publish_request",
        "publish_id": publish_id,
        "target_scope": {"scope_type": "owner", "scope_id": "owner_1"},
        "change_set": {"active_alias_version_from": from_v, "active_alias_version_to": to_v},
        "status": "confirmed",
    }


def _result(status: str, publish_id: str = "pub-1", before: str = "v1", after: str = "v2", from_v: str = "v1", to_v: str = "v2") -> dict:
    return {
        "artifact_type": "policy_publish_result",
        "publish_id": publish_id,
        "status": status,
        "target_scope": {"scope_type": "owner", "scope_id": "owner_1"},
        "change_set": {"active_alias_version_from": from_v, "active_alias_version_to": to_v},
        "before": {"active_alias_version": before},
        "after": {"active_alias_version": after},
    }


def _audit(publish_id: str = "pub-1", before: str = "v1", after: str = "v2") -> dict:
    return {
        "artifact_type": "policy_change_audit_pack",
        "publish_id": publish_id,
        "before": {"active_alias_version": before},
        "after": {"active_alias_version": after},
        "status": "applied",
    }


def test_apply_partial_commit_identified() -> None:
    req = _request()
    res = _result("blocked", before="v1", after="v2")
    report = hook.reconcile_publish_failure(
        context={
            "publish_request_artifact": req,
            "publish_result_artifact": res,
            "failure_id": "fail-a",
        },
        config_snapshot={"active_alias_version": "v2"},
    )
    assert report["reconcile_status"] in {"partially_reconciled", "manual_required"}
    assert report["recommended_action"] == "manual_publish_review"


def test_rollback_partial_commit_identified() -> None:
    req = _request(from_v="v1", to_v="v2")
    res = _result("rolled_back", before="v2", after="v1", from_v="v1", to_v="v2")
    report = hook.reconcile_publish_failure(
        context={"publish_request_artifact": req, "publish_result_artifact": res},
        config_snapshot={"active_alias_version": "v2"},
    )
    assert report["reconcile_status"] == "manual_required"
    assert report["recommended_action"] == "manual_rollback_check"


def test_artifact_missing_but_config_changed() -> None:
    req = _request()
    report = hook.reconcile_publish_failure(
        context={"publish_request_artifact": req},
        config_snapshot={"active_alias_version": "v2"},
    )
    assert "policy_publish_result" in report["missing_artifacts"]
    assert report["reconcile_status"] in {"reconciled", "partially_reconciled"}


def test_no_action_needed_when_consistent_and_complete() -> None:
    req = _request()
    res = _result("applied", before="v1", after="v2")
    aud = _audit(before="v1", after="v2")
    report = hook.reconcile_publish_failure(
        context={
            "publish_request_artifact": req,
            "publish_result_artifact": res,
            "publish_audit_artifact": aud,
        },
        config_snapshot={"active_alias_version": "v2"},
    )
    assert report["reconcile_status"] == "no_action_needed"
    assert report["recommended_action"] == "no_action"


def test_applied_but_active_version_mismatch() -> None:
    req = _request()
    res = _result("applied", before="v1", after="v2")
    report = hook.reconcile_publish_failure(
        context={"publish_request_artifact": req, "publish_result_artifact": res},
        config_snapshot={"active_alias_version": "v1"},
    )
    assert report["reconcile_status"] == "manual_required"
    assert report["recommended_action"] == "verify_config"


def test_insufficient_info_returns_partial_or_manual() -> None:
    report = hook.reconcile_publish_failure(
        context={},
        config_snapshot={"active_alias_version": "v1"},
    )
    assert report["reconcile_status"] in {"partially_reconciled", "manual_required"}


def test_recommended_action_backfill_when_only_artifact_missing() -> None:
    req = _request()
    res = _result("applied", before="v1", after="v2")
    report = hook.reconcile_publish_failure(
        context={
            "publish_request_artifact": req,
            "publish_result_artifact": res,
        },
        config_snapshot={"active_alias_version": "v2"},
    )
    assert report["recommended_action"] == "backfill_artifact"


def test_emit_runtime_reconcile_event_fallback(tmp_path: Path, monkeypatch) -> None:
    def _raise_ingest(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(hook, "ingest_governance_event", _raise_ingest)

    rep = hook.reconcile_publish_failure(
        context={"publish_request_artifact": _request(), "publish_result_artifact": _result("applied")},
        config_snapshot={"active_alias_version": "v2"},
    )
    out = hook.emit_runtime_reconcile_event(
        rep,
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert out["emit_status"] == "fallback_logged"
    assert (tmp_path / "fallback.log").exists()


def test_run_publish_reconcile_hook_writes_report_and_event(tmp_path: Path) -> None:
    req = _request()
    res = _result("applied", before="v1", after="v2")
    result = hook.run_publish_reconcile_hook(
        context={"publish_request_artifact": req, "publish_result_artifact": res, "publish_audit_artifact": _audit()},
        config_snapshot={"active_alias_version": "v2"},
        output_path=tmp_path / "report.json",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert (tmp_path / "report.json").exists()
    assert result["event_emit"]["emit_status"] == "event_logged"


def test_reads_policy_config_center_when_snapshot_not_provided(monkeypatch, tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    owner = tmp_path / "owner.json"
    group = tmp_path / "group.json"
    ws = tmp_path / "ws.json"
    project = tmp_path / "project.json"

    _write(
        default,
        {
            "policy_version": "policy.center.v0.1",
            "alias_registry": {
                "active_version": "v2",
                "versions": {
                    "v1": "config/owner_intent_aliases.v0.1.json",
                    "v2": "config/owner_intent_aliases.v0.2.json",
                },
            },
        },
    )
    _write(owner, {})
    _write(group, {})
    _write(ws, {})
    _write(project, {})

    monkeypatch.setattr(pcc, "DEFAULT_CONFIG_PATH", default)
    monkeypatch.setattr(pcc, "OWNER_OVERRIDES_PATH", owner)
    monkeypatch.setattr(pcc, "GROUP_OVERRIDES_PATH", group)
    monkeypatch.setattr(pcc, "WORKSPACE_OVERRIDES_PATH", ws)
    monkeypatch.setattr(pcc, "PROJECT_OVERRIDES_PATH", project)

    req = _request()
    res = _result("applied", before="v1", after="v2")
    aud = _audit(before="v1", after="v2")
    report = hook.reconcile_publish_failure(
        context={
            "publish_request_artifact": req,
            "publish_result_artifact": res,
            "publish_audit_artifact": aud,
        }
    )
    assert report["current_runtime_state"]["active_alias_version"] == "v2"


def test_apply_before_after_same_detected() -> None:
    req = _request()
    res = _result("applied", before="v2", after="v2")
    report = hook.reconcile_publish_failure(
        context={"publish_request_artifact": req, "publish_result_artifact": res},
        config_snapshot={"active_alias_version": "v2"},
    )
    assert report["reconcile_status"] == "manual_required"
    assert report["recommended_action"] == "verify_config"
