"""Testing playbook runner v1.

Runs minimum viable validation scenarios for AgentCommerce v1:
A) normal message interaction loop
B) owner feedback + publish FSM loop
C) failure -> recovery loop

This runner is designed for local/dry-run execution and produces auditable
artifacts/events/metrics under artifacts/testing_playbook_v1/<run_id>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge.feishu_message_router import route_message
from tools.council_bridge.governance_event_log import build_governance_event
from tools.council_bridge.governance_metrics_snapshot_job import run_governance_metrics_snapshot_job
from tools.council_bridge.policy_publish_fsm import (
    STATUS_APPLIED,
    STATUS_CONFIRMED,
    advance_publish_status,
    create_publish_request,
)
from tools.council_bridge.runtime_event_log_degradation_recovery import (
    handle_event_log_degradation,
    replay_degraded_events,
)
from tools.council_bridge.runtime_failure_event_normalizer import (
    emit_runtime_failure_event,
    normalize_failure_event,
)
from tools.council_bridge.runtime_publish_reconcile_hook import run_publish_reconcile_hook
from tools.council_bridge.runtime_recovery_attempt_runner import run_and_emit_recovery_attempt


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else None


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict):
            events.append(data)
    return events


def _event_names(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for ev in events:
        event_type = str(ev.get("event_type") or "unknown")
        status = str(ev.get("status") or "unknown")
        out.append(f"{event_type}:{status}")
    return out


def _build_council_plan_artifact(*, artifact_id: str, status: str, request_id: str, brief_id: str) -> dict[str, Any]:
    return {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": "test_playbook",
        "created_at": "2026-03-17T10:00:00+08:00",
        "updated_at": "2026-03-17T10:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "playbook test artifact",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "review",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "objective": "validate testing playbook",
        "scope": ["test"],
        "steps": [{"step_id": "s1", "title": "validate"}],
        "dependencies": [],
        "acceptance_criteria": ["artifact generated"],
        "proposed_execution_boundary": {"execution_allowed": False},
        "expected_outputs": ["route/mapping/validation artifacts"],
    }


@contextmanager
def _temporary_policy_center(config_root: Path):
    default_path = config_root / "default.json"
    owner_path = config_root / "owner_overrides.json"
    group_path = config_root / "group_overrides.json"
    workspace_path = config_root / "workspace_overrides.json"
    project_path = config_root / "project_overrides.json"

    _write_json(
        default_path,
        {
            "policy_version": "policy.center.v0.1",
            "lane_switches": {
                "chat_lane_enabled": True,
                "chat_lane_require_mention": False,
                "chat_lane_only_groups": [],
                "chat_lane_blocked_groups": [],
            },
            "alias_registry": {
                "active_version": "owner.intent.alias.v0.1",
                "versions": {
                    "owner.intent.alias.v0.1": "config/owner_intent_aliases.v0.1.json",
                    "owner.intent.alias.v0.2": "config/owner_intent_aliases.v0.2.json",
                },
            },
            "scope_defaults": {
                "policy_scope": "default",
                "alias_scope": "default",
            },
        },
    )
    for path in [owner_path, group_path, workspace_path, project_path]:
        _write_json(path, {})

    original = {
        "DEFAULT_CONFIG_PATH": pcc.DEFAULT_CONFIG_PATH,
        "OWNER_OVERRIDES_PATH": pcc.OWNER_OVERRIDES_PATH,
        "GROUP_OVERRIDES_PATH": pcc.GROUP_OVERRIDES_PATH,
        "WORKSPACE_OVERRIDES_PATH": pcc.WORKSPACE_OVERRIDES_PATH,
        "PROJECT_OVERRIDES_PATH": pcc.PROJECT_OVERRIDES_PATH,
    }
    try:
        pcc.DEFAULT_CONFIG_PATH = default_path
        pcc.OWNER_OVERRIDES_PATH = owner_path
        pcc.GROUP_OVERRIDES_PATH = group_path
        pcc.WORKSPACE_OVERRIDES_PATH = workspace_path
        pcc.PROJECT_OVERRIDES_PATH = project_path
        yield {
            "default": default_path,
            "owner": owner_path,
            "group": group_path,
            "workspace": workspace_path,
            "project": project_path,
        }
    finally:
        pcc.DEFAULT_CONFIG_PATH = original["DEFAULT_CONFIG_PATH"]
        pcc.OWNER_OVERRIDES_PATH = original["OWNER_OVERRIDES_PATH"]
        pcc.GROUP_OVERRIDES_PATH = original["GROUP_OVERRIDES_PATH"]
        pcc.WORKSPACE_OVERRIDES_PATH = original["WORKSPACE_OVERRIDES_PATH"]
        pcc.PROJECT_OVERRIDES_PATH = original["PROJECT_OVERRIDES_PATH"]


def run_scenario_a(base_dir: Path, governance_event_log: Path, governance_dedupe: Path) -> dict[str, Any]:
    out_dir = base_dir / "scenario_a_normal_message"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_artifact = out_dir / "source_non_council_artifact.json"
    _write_json(source_artifact, {"artifact_type": "chat_context", "note": "non-council source"})

    route_path = out_dir / "route_result.json"
    dedupe_path = out_dir / "dedupe_state.json"
    queue_db = out_dir / "queue.db"

    payload = {
        "source": "feishu_chat",
        "event_id": "tp-a-001",
        "message_id": "tp-a-msg-001",
        "chat_id": "chat_a",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": "帮我总结当前状态，不触发执行",
        "create_time": "1711111111",
        "workspace_id": "ws_alpha",
        "project_id": "pj_market",
    }

    route_result = route_message(
        payload,
        source_artifact=source_artifact.as_posix(),
        stage="auto",
        dedupe_state_path=dedupe_path,
        route_result_path=route_path,
        queue_db_path=queue_db,
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
    )

    events = _load_events(governance_event_log)
    related_events = [
        ev
        for ev in events
        if str(ev.get("event_id") or "").find("tp-a-msg-001") >= 0
        or str(ev.get("event_id") or "").find("tp-a-001") >= 0
    ]
    scenario_passed = route_result.get("result_status") == "queued" and route_result.get("route_type") == "chat"

    evidence = {
        "scenario": "A",
        "inputs": {"message": payload},
        "module_path": [
            "feishu_message_router",
            "scope_validator(observe)",
            "chat_lane_queue",
        ],
        "artifacts": [
            route_path.as_posix(),
            dedupe_path.as_posix(),
            queue_db.as_posix(),
        ],
        "events": _event_names(related_events),
        "metrics": [
            "scope_validation.pass|degraded|blocked",
            "router_scope_observe.observed",
        ],
        "success_criteria": {
            "route_type": "chat",
            "result_status": "queued",
            "event_contains": ["scope_validation_result", "router_scope_observe_result"],
        },
        "actual_outcome": {
            "route_type": route_result.get("route_type"),
            "result_status": route_result.get("result_status"),
            "events_found": _event_names(related_events),
            "passed": scenario_passed,
        },
    }
    evidence_path = out_dir / "evidence_index.json"
    _write_json(evidence_path, evidence)

    return {
        "scenario": "A",
        "description": "普通消息交互闭环（chat lane queue）",
        "input": payload,
        "route_result_path": route_path.as_posix(),
        "route_result": route_result,
        "expected_result_status": "queued",
        "artifact_paths": evidence["artifacts"],
        "event_evidence": evidence["events"],
        "metrics_evidence": evidence["metrics"],
        "evidence_index_path": evidence_path.as_posix(),
        "passed": scenario_passed,
    }


def run_scenario_b(base_dir: Path, governance_event_log: Path, governance_dedupe: Path) -> dict[str, Any]:
    out_dir = base_dir / "scenario_b_owner_feedback_publish"
    out_dir.mkdir(parents=True, exist_ok=True)

    council_dir = out_dir / "council_feedback"
    council_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = council_dir / "source_plan_artifact.json"
    _write_json(
        artifact_path,
        _build_council_plan_artifact(
            artifact_id="plan-test-b-001",
            status="under_review",
            request_id="req-test-b-001",
            brief_id="brief-test-b-001",
        ),
    )

    mapping_path = council_dir / "mapping_result.json"
    validation_path = council_dir / "validation_result.json"
    apply_path = council_dir / "owner_apply_result.json"
    observe_route_path = council_dir / "route_observe.json"
    confirm_route_path = council_dir / "route_confirm.json"

    observe_payload = {
        "source": "feishu_chat",
        "event_id": "tp-b-observe-001",
        "message_id": "tp-b-msg-001",
        "chat_id": "chat_b",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": "风险分析不够，请修改后再给我",
        "create_time": "1711112222",
        "workspace_id": "ws_alpha",
        "project_id": "pj_market",
    }

    observe_result = route_message(
        observe_payload,
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=council_dir / "dedupe_observe.json",
        route_result_path=observe_route_path,
        queue_db_path=council_dir / "queue.db",
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
    )

    confirm_payload = {
        "source": "feishu_action_protocol",
        "event_id": "tp-b-confirm-001",
        "message_id": "tp-b-msg-002",
        "chat_id": "chat_b",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": "apply_suggested_transition",
        "create_time": "1711112233",
        "workspace_id": "ws_alpha",
        "project_id": "pj_market",
    }

    confirm_result = route_message(
        confirm_payload,
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=council_dir / "dedupe_confirm.json",
        route_result_path=confirm_route_path,
        queue_db_path=council_dir / "queue.db",
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
    )

    publish_dir = out_dir / "publish_fsm"
    publish_dir.mkdir(parents=True, exist_ok=True)
    with _temporary_policy_center(publish_dir / "policy_center"):
        req_path = publish_dir / "policy_publish_request.json"
        review_path = publish_dir / "policy_publish_review.json"
        result_path = publish_dir / "policy_publish_result.json"
        audit_path = publish_dir / "policy_change_audit_pack.json"
        regression_report_path = publish_dir / "alias_regression_report.json"

        request = create_publish_request(
            requested_by="owner_001",
            target_scope={"scope_type": "owner", "scope_id": "owner_001"},
            change_set={"active_alias_version_to": "owner.intent.alias.v0.2"},
            reason="testing playbook publish apply",
            output_path=req_path,
        )
        confirmed = advance_publish_status(
            request_path=req_path,
            target_status=STATUS_CONFIRMED,
            actor="owner_001",
            note="confirm for testing playbook",
            review_artifact_path=review_path,
            result_artifact_path=result_path,
            audit_pack_path=audit_path,
            governance_event_log_path=governance_event_log,
            governance_dedupe_index_path=governance_dedupe,
            alias_regression_report_path=regression_report_path,
        )
        applied = advance_publish_status(
            request_path=req_path,
            target_status=STATUS_APPLIED,
            actor="owner_001",
            note="apply for testing playbook",
            review_artifact_path=review_path,
            result_artifact_path=result_path,
            audit_pack_path=audit_path,
            governance_event_log_path=governance_event_log,
            governance_dedupe_index_path=governance_dedupe,
            alias_regression_report_path=regression_report_path,
        )

    mapping = _read_json(mapping_path)
    validation = _read_json(validation_path)
    apply_receipt = _read_json(apply_path)
    events = _load_events(governance_event_log)
    related_events = [
        ev
        for ev in events
        if str(ev.get("event_id") or "").find("tp-b-msg-001") >= 0
        or str(ev.get("event_id") or "").find("tp-b-msg-002") >= 0
        or str(ev.get("publish_id") or "") == str(request.get("publish_id") or "")
    ]
    scenario_passed = bool(
        confirm_result.get("result_status") == "applied"
        and isinstance(apply_receipt, dict)
        and apply_receipt.get("apply_status") == "applied"
        and applied.get("status") == STATUS_APPLIED
    )
    evidence = {
        "scenario": "B",
        "inputs": {
            "owner_feedback_message": observe_payload,
            "owner_confirm_message": confirm_payload,
            "publish_target": {"active_alias_version_to": "owner.intent.alias.v0.2"},
        },
        "module_path": [
            "feishu_message_router",
            "feishu_feedback_mapping_adapter",
            "council_artifact_state_machine.validate_transition",
            "owner_confirmed_transition_apply",
            "policy_publish_fsm",
        ],
        "artifacts": [
            mapping_path.as_posix(),
            validation_path.as_posix(),
            apply_path.as_posix(),
            req_path.as_posix(),
            result_path.as_posix(),
            audit_path.as_posix(),
        ],
        "events": _event_names(related_events),
        "metrics": ["policy_publish.applied", "scope_validation", "router_scope_observe"],
        "success_criteria": {
            "owner_apply_status": "applied",
            "publish_status": "applied",
            "event_contains": ["policy_publish_result:applied"],
        },
        "actual_outcome": {
            "owner_apply_status": (apply_receipt or {}).get("apply_status"),
            "publish_status": applied.get("status"),
            "events_found": _event_names(related_events),
            "passed": scenario_passed,
        },
    }
    evidence_path = out_dir / "evidence_index.json"
    _write_json(evidence_path, evidence)

    return {
        "scenario": "B",
        "description": "Owner feedback + publish flow 闭环",
        "owner_feedback_input": observe_payload,
        "owner_confirm_input": confirm_payload,
        "observe_route_result": observe_result,
        "confirm_route_result": confirm_result,
        "mapping_result": mapping,
        "validation_result": validation,
        "owner_apply_result": apply_receipt,
        "publish_request": request,
        "publish_confirmed": confirmed,
        "publish_applied": applied,
        "paths": {
            "mapping_result": mapping_path.as_posix(),
            "validation_result": validation_path.as_posix(),
            "owner_apply_result": apply_path.as_posix(),
            "policy_publish_request": req_path.as_posix(),
            "policy_publish_result": result_path.as_posix(),
            "policy_change_audit_pack": audit_path.as_posix(),
        },
        "artifact_paths": evidence["artifacts"],
        "event_evidence": evidence["events"],
        "metrics_evidence": evidence["metrics"],
        "evidence_index_path": evidence_path.as_posix(),
        "passed": scenario_passed,
    }


def run_scenario_c(base_dir: Path, governance_event_log: Path, governance_dedupe: Path) -> dict[str, Any]:
    out_dir = base_dir / "scenario_c_failure_recovery"
    out_dir.mkdir(parents=True, exist_ok=True)

    fallback_log = out_dir / "runtime_failure_fallback.log"
    failure_artifact_path = out_dir / "runtime_failure_event.json"
    recovery_artifact_path = out_dir / "runtime_recovery_attempt.json"
    reconcile_artifact_path = out_dir / "runtime_reconcile_report.json"
    degradation_artifact_path = out_dir / "runtime_event_log_degradation.json"
    degradation_queue_path = out_dir / "runtime_event_log_degradation_queue.jsonl"
    snapshot_path = out_dir / "governance_metrics_snapshot.json"

    try:
        raise OSError("simulated artifact write failure for testing playbook")
    except OSError as exc:
        failure_artifact = normalize_failure_event(
            exception=exc,
            failure_type="artifact_write_failure",
            failure_stage="artifact_write",
            source_module="testing_playbook_v1_runner",
            context={
                "related_request_id": "req-test-c-001",
                "workspace_id": "ws_alpha",
                "project_id": "pj_market",
                "owner_id": "owner_001",
                "operator": "system",
            },
        )
        _write_json(failure_artifact_path, failure_artifact)
        failure_emit = emit_runtime_failure_event(
            exception=exc,
            failure_type="artifact_write_failure",
            failure_stage="artifact_write",
            source_module="testing_playbook_v1_runner",
            context={
                "related_request_id": "req-test-c-001",
                "workspace_id": "ws_alpha",
                "project_id": "pj_market",
                "owner_id": "owner_001",
                "source_artifact": failure_artifact_path.as_posix(),
            },
            governance_event_log_path=governance_event_log,
            governance_dedupe_index_path=governance_dedupe,
            fallback_log_path=fallback_log,
        )

    recovery = run_and_emit_recovery_attempt(
        failure_event=failure_artifact,
        recovery_policy={"force_attempt_result": "success"},
        operator="system",
        artifact_output_path=recovery_artifact_path,
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
        event_context={
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "owner_id": "owner_001",
            "source_artifact": recovery_artifact_path.as_posix(),
        },
    )

    publish_result_like = {
        "artifact_type": "policy_publish_result",
        "publish_id": "pub-test-c-001",
        "status": "applied",
        "change_set": {
            "active_alias_version_from": "owner.intent.alias.v0.1",
            "active_alias_version_to": "owner.intent.alias.v0.2",
        },
        "before": {"active_alias_version": "owner.intent.alias.v0.1"},
        "after": {"active_alias_version": "owner.intent.alias.v0.2"},
        "target_scope": {"scope_type": "owner", "scope_id": "owner_001"},
    }
    reconcile = run_publish_reconcile_hook(
        publish_artifact=publish_result_like,
        config_snapshot={"active_alias_version": "owner.intent.alias.v0.1"},
        context={
            "failure_id": failure_artifact.get("failure_id"),
            "publish_id": "pub-test-c-001",
            "source_module": "testing_playbook_v1_runner",
            "workspace_id": "ws_alpha",
            "project_id": "pj_market",
            "owner_id": "owner_001",
            "source_artifact": reconcile_artifact_path.as_posix(),
            "operator": "system",
        },
        output_path=reconcile_artifact_path,
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
        fallback_log_path=out_dir / "runtime_reconcile_fallback.log",
    )

    failed_event = build_governance_event(
        event_id="tp-c-degrade-001",
        event_type="runtime_recovery_attempt",
        occurred_at=_now_iso(),
        request_id="req-test-c-001",
        publish_id="pub-test-c-001",
        workspace_id="ws_alpha",
        project_id="pj_market",
        owner_id="owner_001",
        source_module="testing_playbook_v1_runner",
        source_artifact=recovery_artifact_path.as_posix(),
        status="manual_required",
        payload_summary={"reason": "simulate ingest degradation"},
    )
    degradation = handle_event_log_degradation(
        failed_event=failed_event,
        ingest_result={"ingest_status": "invalid", "errors": ["simulated invalid ingest"]},
        context={
            "related_failure_id": failure_artifact.get("failure_id"),
            "related_request_id": "req-test-c-001",
            "publish_id": "pub-test-c-001",
            "source_module": "testing_playbook_v1_runner",
            "operator": "system",
        },
        artifact_path=degradation_artifact_path,
        queue_path=degradation_queue_path,
        fallback_log_path=out_dir / "runtime_degradation_fallback.log",
    )

    replay = replay_degraded_events(
        queue_path=degradation_queue_path,
        operator="system",
        governance_event_log_path=governance_event_log,
        governance_dedupe_index_path=governance_dedupe,
    )

    snapshot = run_governance_metrics_snapshot_job(
        event_log_path=governance_event_log,
        artifacts_dir=base_dir,
        output_path=snapshot_path,
        fallback_to_full_scan=True,
    )

    failure_loaded = _read_json(failure_artifact_path) or {}
    recovery_loaded = _read_json(recovery_artifact_path) or {}
    reconcile_loaded = _read_json(reconcile_artifact_path) or {}
    degradation_loaded = _read_json(degradation_artifact_path) or {}
    events = _load_events(governance_event_log)
    related_events = [
        ev
        for ev in events
        if str(ev.get("request_id") or "") == "req-test-c-001"
        or str(ev.get("publish_id") or "") == "pub-test-c-001"
    ]

    checks = {
        "failure_type_expected": failure_loaded.get("failure_type") == "artifact_write_failure",
        "failure_status_pending": failure_loaded.get("recovery_status") == "pending",
        "recovery_action_retry": recovery_loaded.get("recovery_action") == "retry",
        "recovery_attempt_result_valid": recovery_loaded.get("attempt_result") in {
            "success",
            "failed_retryable",
            "failed_terminal",
            "ignored",
            "manual_required",
        },
        "reconcile_status_valid": reconcile_loaded.get("reconcile_status") in {
            "reconciled",
            "partially_reconciled",
            "manual_required",
            "no_action_needed",
        },
        "degradation_status_valid": degradation_loaded.get("queue_status") in {
            "queued",
            "replayed",
            "replay_failed",
            "abandoned",
        },
        "replay_completed": replay.get("replay_status") == "completed",
        "snapshot_runtime_failure_total": int(snapshot.get("metrics", {}).get("runtime_failure", {}).get("total") or 0) >= 1,
        "snapshot_runtime_recovery_total": int(snapshot.get("metrics", {}).get("runtime_recovery_attempt", {}).get("total") or 0) >= 1,
        "snapshot_recovery_quality_present": isinstance(snapshot.get("metrics", {}).get("recovery_quality"), dict),
    }
    scenario_passed = all(bool(v) for v in checks.values())
    evidence = {
        "scenario": "C",
        "inputs": {
            "failure_injection": "OSError('simulated artifact write failure for testing playbook')",
            "recovery_policy": {"force_attempt_result": "success"},
            "reconcile_context": {"publish_id": "pub-test-c-001", "config_snapshot.active_alias_version": "owner.intent.alias.v0.1"},
        },
        "module_path": [
            "runtime_failure_event_normalizer",
            "runtime_recovery_attempt_runner",
            "runtime_publish_reconcile_hook",
            "runtime_event_log_degradation_recovery",
            "governance_metrics_snapshot_job",
        ],
        "artifacts": [
            failure_artifact_path.as_posix(),
            recovery_artifact_path.as_posix(),
            reconcile_artifact_path.as_posix(),
            degradation_artifact_path.as_posix(),
            snapshot_path.as_posix(),
        ],
        "events": _event_names(related_events),
        "metrics": [
            "runtime_failure.total",
            "runtime_recovery_attempt.total",
            "runtime_reconcile.*",
            "runtime_event_log_degradation.*",
            "recovery_quality.*",
        ],
        "success_criteria": {
            "failure_type": "artifact_write_failure",
            "recovery_action": "retry",
            "reconcile_status_in": ["reconciled", "partially_reconciled", "manual_required", "no_action_needed"],
            "degradation_queue_status_in": ["queued", "replayed", "replay_failed", "abandoned"],
            "metrics_non_empty": ["runtime_failure.total", "runtime_recovery_attempt.total", "recovery_quality"],
        },
        "actual_outcome": {
            "checks": checks,
            "failure_type": failure_loaded.get("failure_type"),
            "recovery_action": recovery_loaded.get("recovery_action"),
            "reconcile_status": reconcile_loaded.get("reconcile_status"),
            "degradation_queue_status": degradation_loaded.get("queue_status"),
            "snapshot_recovery_quality": snapshot.get("metrics", {}).get("recovery_quality", {}),
            "passed": scenario_passed,
        },
    }
    evidence_path = out_dir / "evidence_index.json"
    _write_json(evidence_path, evidence)

    return {
        "scenario": "C",
        "description": "故意触发 failure -> recovery 闭环",
        "failure_emit": failure_emit,
        "recovery": recovery,
        "reconcile": reconcile,
        "degradation": degradation,
        "replay": replay,
        "snapshot_path": snapshot_path.as_posix(),
        "snapshot_metrics_recovery": snapshot.get("metrics", {}).get("recovery_quality", {}),
        "paths": {
            "runtime_failure_event": failure_artifact_path.as_posix(),
            "runtime_recovery_attempt": recovery_artifact_path.as_posix(),
            "runtime_reconcile_report": reconcile_artifact_path.as_posix(),
            "runtime_event_log_degradation": degradation_artifact_path.as_posix(),
            "governance_metrics_snapshot": snapshot_path.as_posix(),
        },
        "artifact_paths": evidence["artifacts"],
        "event_evidence": evidence["events"],
        "metrics_evidence": evidence["metrics"],
        "field_level_checks": checks,
        "evidence_index_path": evidence_path.as_posix(),
        "passed": scenario_passed,
    }


def run_playbook(*, run_id: str | None = None, output_root: Path = Path("artifacts") / "testing_playbook_v1") -> dict[str, Any]:
    resolved_run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    run_dir = output_root / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    governance_event_log = run_dir / "governance_events.log"
    governance_dedupe = run_dir / "governance_events_dedupe_index.json"

    scenario_a = run_scenario_a(run_dir, governance_event_log, governance_dedupe)
    scenario_b = run_scenario_b(run_dir, governance_event_log, governance_dedupe)
    scenario_c = run_scenario_c(run_dir, governance_event_log, governance_dedupe)

    scenarios = {
        "A": scenario_a,
        "B": scenario_b,
        "C": scenario_c,
    }

    summary = {
        "artifact_type": "testing_playbook_result",
        "schema_version": "testing.playbook.v0.1",
        "run_id": resolved_run_id,
        "generated_at": _now_iso(),
        "output_root": run_dir.as_posix(),
        "governance_event_log": governance_event_log.as_posix(),
        "governance_dedupe_index": governance_dedupe.as_posix(),
        "scenarios": scenarios,
        "all_passed": all(
            [
                bool(scenario_a.get("passed")),
                bool(scenario_b.get("passed")),
                bool(scenario_c.get("passed")),
            ]
        ),
    }

    summary_path = run_dir / "testing_playbook_summary.json"
    _write_json(summary_path, summary)

    demo_ready_summary = {
        "artifact_type": "testing_evidence_index",
        "schema_version": "testing.evidence.v0.1",
        "run_id": resolved_run_id,
        "generated_at": _now_iso(),
        "overall_status": "passed" if summary["all_passed"] else "failed",
        "suggested_demo_order": [
            "A: 普通消息交互闭环",
            "B: Owner feedback + publish 闭环",
            "C: failure -> recovery 闭环",
        ],
        "scenarios_overview": [
            {
                "scenario": key,
                "passed": bool(value.get("passed")),
                "evidence_index_path": value.get("evidence_index_path"),
                "artifacts": value.get("artifact_paths", []),
                "events": value.get("event_evidence", []),
                "metrics": value.get("metrics_evidence", []),
            }
            for key, value in scenarios.items()
        ],
        "key_files": {
            "testing_playbook_summary": summary_path.as_posix(),
            "governance_event_log": governance_event_log.as_posix(),
            "governance_metrics_snapshot_scenario_c": scenario_c.get("paths", {}).get("governance_metrics_snapshot"),
        },
    }
    demo_ready_summary_path = run_dir / "demo_ready_summary.json"
    _write_json(demo_ready_summary_path, demo_ready_summary)

    report_lines = [
        "# Testing Demo Ready Report",
        "",
        f"- run_id: `{resolved_run_id}`",
        f"- overall_status: `{demo_ready_summary['overall_status']}`",
        f"- generated_at: `{demo_ready_summary['generated_at']}`",
        "",
        "## Scenario Results",
        "",
    ]
    for item in demo_ready_summary["scenarios_overview"]:
        report_lines.append(
            f"- {item['scenario']}: passed={item['passed']} | evidence={item.get('evidence_index_path')}"
        )
    report_lines.extend(
        [
            "",
            "## Key Outputs",
            "",
            f"- testing summary: `{summary_path.as_posix()}`",
            f"- demo-ready summary: `{demo_ready_summary_path.as_posix()}`",
            f"- governance events: `{governance_event_log.as_posix()}`",
            f"- scenario C snapshot: `{scenario_c.get('paths', {}).get('governance_metrics_snapshot')}`",
        ]
    )
    report_path = run_dir / "demo_ready_report.md"
    _write_text(report_path, "\n".join(report_lines) + "\n")

    return {
        "summary_path": summary_path.as_posix(),
        "demo_ready_summary_path": demo_ready_summary_path.as_posix(),
        "demo_ready_report_path": report_path.as_posix(),
        "summary": summary,
        "demo_ready_summary": demo_ready_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgentCommerce testing playbook v1 scenarios.")
    parser.add_argument("--run-id", default="", help="Optional run id; default is timestamp-based")
    parser.add_argument(
        "--output-root",
        default=str(Path("artifacts") / "testing_playbook_v1"),
        help="Output root directory",
    )
    args = parser.parse_args()

    result = run_playbook(
        run_id=args.run_id or None,
        output_root=Path(args.output_root),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
