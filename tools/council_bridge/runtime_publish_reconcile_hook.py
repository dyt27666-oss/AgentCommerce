"""Runtime publish reconcile hook v0.1.

Detects publish-related partial commits and inconsistency between artifacts and
current config state. Produces reconcile report only; no auto-fix.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.governance_event_log import (
    DEFAULT_DEDUPE_INDEX_PATH,
    DEFAULT_EVENT_LOG_PATH,
    build_governance_event,
    ingest_governance_event,
)
import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge.runtime_event_log_degradation_recovery import handle_event_log_degradation

RUNTIME_RECONCILE_SCHEMA_VERSION = "runtime.reconcile.v0.1"
DEFAULT_RUNTIME_RECONCILE_ARTIFACT_PATH = Path("artifacts") / "runtime_reconcile_report.json"
DEFAULT_RUNTIME_RECONCILE_FALLBACK_LOG_PATH = Path("artifacts") / "runtime_reconcile_fallback.log"

STATUS_RECONCILED = "reconciled"
STATUS_PARTIALLY_RECONCILED = "partially_reconciled"
STATUS_MANUAL_REQUIRED = "manual_required"
STATUS_NO_ACTION_NEEDED = "no_action_needed"

ACTION_BACKFILL_ARTIFACT = "backfill_artifact"
ACTION_VERIFY_CONFIG = "verify_config"
ACTION_MANUAL_ROLLBACK_CHECK = "manual_rollback_check"
ACTION_MANUAL_PUBLISH_REVIEW = "manual_publish_review"
ACTION_NO_ACTION = "no_action"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _append_fallback_log(record: dict[str, Any], fallback_log_path: Path) -> None:
    fallback_log_path.parent.mkdir(parents=True, exist_ok=True)
    with fallback_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_scope_id(scope: dict[str, Any] | None, scope_type: str) -> str:
    if not isinstance(scope, dict):
        return ""
    if _safe_text(scope.get("scope_type")) != scope_type:
        return ""
    return _safe_text(scope.get("scope_id"))


def _resolve_scope_from_artifacts(request_artifact: dict[str, Any] | None, result_artifact: dict[str, Any] | None) -> dict[str, str]:
    scope = None
    if isinstance(result_artifact, dict) and isinstance(result_artifact.get("target_scope"), dict):
        scope = result_artifact.get("target_scope")
    elif isinstance(request_artifact, dict) and isinstance(request_artifact.get("target_scope"), dict):
        scope = request_artifact.get("target_scope")

    return {
        "owner_id": _extract_scope_id(scope, "owner"),
        "workspace_id": _extract_scope_id(scope, "workspace"),
        "project_id": _extract_scope_id(scope, "project"),
    }


def _resolve_current_active_version(
    *,
    config_snapshot: dict[str, Any] | None,
    request_artifact: dict[str, Any] | None,
    result_artifact: dict[str, Any] | None,
) -> str:
    if isinstance(config_snapshot, dict):
        return _safe_text(config_snapshot.get("active_alias_version"))

    scope = _resolve_scope_from_artifacts(request_artifact, result_artifact)
    cfg = pcc.resolve_policy_config(
        owner_id=scope["owner_id"],
        workspace_id=scope["workspace_id"],
        project_id=scope["project_id"],
    )
    return _safe_text(cfg.get("active_alias_version"))


def _pick_artifact(
    publish_artifact: dict[str, Any] | None,
    context: dict[str, Any],
    key_obj: str,
    key_path: str,
) -> dict[str, Any] | None:
    direct = context.get(key_obj)
    if isinstance(direct, dict):
        return direct

    path_value = context.get(key_path)
    if _safe_text(path_value):
        loaded = _load_json(Path(str(path_value)))
        if isinstance(loaded, dict):
            return loaded

    if isinstance(publish_artifact, dict):
        at = _safe_text(publish_artifact.get("artifact_type"))
        if key_obj == "publish_result_artifact" and at == "policy_publish_result":
            return publish_artifact
        if key_obj == "publish_request_artifact" and at == "policy_publish_request":
            return publish_artifact
        if key_obj == "publish_audit_artifact" and at == "policy_change_audit_pack":
            return publish_artifact
    return None


def reconcile_publish_failure(
    publish_artifact: dict | None = None,
    config_snapshot: dict | None = None,
    context: dict | None = None,
) -> dict:
    ctx = context if isinstance(context, dict) else {}

    request_artifact = _pick_artifact(publish_artifact, ctx, "publish_request_artifact", "publish_request_artifact_path")
    result_artifact = _pick_artifact(publish_artifact, ctx, "publish_result_artifact", "publish_result_artifact_path")
    audit_artifact = _pick_artifact(publish_artifact, ctx, "publish_audit_artifact", "publish_audit_artifact_path")

    failure_id = _safe_text(ctx.get("failure_id"))
    publish_id = (
        _safe_text((result_artifact or {}).get("publish_id"))
        or _safe_text((request_artifact or {}).get("publish_id"))
        or _safe_text((audit_artifact or {}).get("publish_id"))
        or _safe_text(ctx.get("publish_id"))
    )

    source_module = _safe_text(ctx.get("source_module")) or "runtime_publish_reconcile_hook"

    change_set = {}
    if isinstance(result_artifact, dict) and isinstance(result_artifact.get("change_set"), dict):
        change_set = result_artifact.get("change_set")
    elif isinstance(request_artifact, dict) and isinstance(request_artifact.get("change_set"), dict):
        change_set = request_artifact.get("change_set")

    from_version = _safe_text(change_set.get("active_alias_version_from"))
    to_version = _safe_text(change_set.get("active_alias_version_to"))

    before_version = _safe_text(((result_artifact or {}).get("before") or {}).get("active_alias_version"))
    after_version = _safe_text(((result_artifact or {}).get("after") or {}).get("active_alias_version"))

    if not before_version:
        before_version = _safe_text(((audit_artifact or {}).get("before") or {}).get("active_alias_version"))
    if not after_version:
        after_version = _safe_text(((audit_artifact or {}).get("after") or {}).get("active_alias_version"))

    result_status = _safe_text((result_artifact or {}).get("status"))
    current_active_version = _resolve_current_active_version(
        config_snapshot=config_snapshot,
        request_artifact=request_artifact,
        result_artifact=result_artifact,
    )

    missing_artifacts: list[str] = []
    repaired_artifacts: list[str] = []
    residual_risk: list[str] = []

    if request_artifact is None:
        missing_artifacts.append("policy_publish_request")
    if result_artifact is None:
        missing_artifacts.append("policy_publish_result")
    if audit_artifact is None and result_status in {"applied", "rolled_back"}:
        missing_artifacts.append("policy_change_audit_pack")

    recommended_action = ACTION_NO_ACTION
    reconcile_status = STATUS_NO_ACTION_NEEDED

    has_critical_mismatch = False
    has_partial_info = False

    if result_status == "applied" and to_version and current_active_version and current_active_version != to_version:
        has_critical_mismatch = True
        residual_risk.append("publish result is applied but active alias version mismatch")
        recommended_action = ACTION_VERIFY_CONFIG

    if result_status == "rolled_back" and from_version and current_active_version and current_active_version != from_version:
        has_critical_mismatch = True
        residual_risk.append("rollback result recorded but active alias version mismatch")
        recommended_action = ACTION_MANUAL_ROLLBACK_CHECK

    if result_status not in {"applied", "rolled_back"} and to_version and current_active_version == to_version:
        has_partial_info = True
        residual_risk.append("config appears changed to target version while publish is not finalized")
        recommended_action = ACTION_MANUAL_PUBLISH_REVIEW

    if result_status == "applied" and to_version and before_version and after_version and before_version == after_version:
        has_critical_mismatch = True
        residual_risk.append("before/after versions are identical for applied result")
        recommended_action = ACTION_VERIFY_CONFIG

    if missing_artifacts and not has_critical_mismatch:
        if current_active_version and (current_active_version in {to_version, from_version}):
            reconcile_status = STATUS_RECONCILED
            recommended_action = ACTION_BACKFILL_ARTIFACT
            repaired_artifacts = []
            residual_risk.append("artifact missing; backfill needed for full audit chain")
        else:
            has_partial_info = True
            if recommended_action == ACTION_NO_ACTION:
                recommended_action = ACTION_MANUAL_PUBLISH_REVIEW

    if not publish_id:
        has_partial_info = True
        residual_risk.append("publish_id missing; cannot fully correlate artifacts")

    if has_critical_mismatch:
        reconcile_status = STATUS_MANUAL_REQUIRED
        if recommended_action == ACTION_NO_ACTION:
            recommended_action = ACTION_MANUAL_PUBLISH_REVIEW
    elif has_partial_info and reconcile_status != STATUS_RECONCILED:
        reconcile_status = STATUS_PARTIALLY_RECONCILED
        if recommended_action == ACTION_NO_ACTION:
            recommended_action = ACTION_VERIFY_CONFIG

    if reconcile_status == STATUS_NO_ACTION_NEEDED and not residual_risk:
        recommended_action = ACTION_NO_ACTION

    report = {
        "artifact_type": "runtime_reconcile_report",
        "schema_version": RUNTIME_RECONCILE_SCHEMA_VERSION,
        "failure_id": failure_id or None,
        "publish_id": publish_id or None,
        "source_module": source_module,
        "reconcile_scope": "publish_failure",
        "detected_at": _now_iso(),
        "reconcile_status": reconcile_status,
        "before": {
            "active_alias_version": before_version or (from_version or None),
            "publish_status": result_status or None,
        },
        "after": {
            "expected_active_alias_version": to_version or None,
            "reported_after_active_alias_version": after_version or None,
        },
        "current_runtime_state": {
            "active_alias_version": current_active_version or None,
            "result_status": result_status or None,
            "config_snapshot_provided": isinstance(config_snapshot, dict),
        },
        "missing_artifacts": missing_artifacts,
        "repaired_artifacts": repaired_artifacts,
        "residual_risk": residual_risk,
        "recommended_action": recommended_action,
        "audit_trace": {
            "request_artifact_present": request_artifact is not None,
            "result_artifact_present": result_artifact is not None,
            "audit_artifact_present": audit_artifact is not None,
            "comparison_fields": {
                "change_set.from": from_version or None,
                "change_set.to": to_version or None,
                "artifact.before": before_version or None,
                "artifact.after": after_version or None,
                "config.active": current_active_version or None,
            },
        },
    }
    return report


def write_runtime_reconcile_report(
    report: dict[str, Any],
    output_path: Path = DEFAULT_RUNTIME_RECONCILE_ARTIFACT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def emit_runtime_reconcile_event(
    report: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    fallback_log_path: Path = DEFAULT_RUNTIME_RECONCILE_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    try:
        publish_id = _safe_text(report.get("publish_id"))
        failure_id = _safe_text(report.get("failure_id"))
        event = build_governance_event(
            event_id=f"runtime_reconcile:{publish_id or 'unknown'}:{failure_id or 'none'}",
            event_type="runtime_reconcile_report",
            occurred_at=_safe_text(report.get("detected_at")) or _now_iso(),
            request_id=ctx.get("related_request_id"),
            publish_id=report.get("publish_id"),
            workspace_id=ctx.get("workspace_id"),
            project_id=ctx.get("project_id"),
            owner_id=ctx.get("owner_id"),
            source_module=_safe_text(report.get("source_module")) or "runtime_publish_reconcile_hook",
            source_artifact=ctx.get("source_artifact") or f"runtime_reconcile_report:{publish_id or 'unknown'}",
            status=_safe_text(report.get("reconcile_status")) or "unknown",
            payload_summary={
                "recommended_action": report.get("recommended_action"),
                "missing_artifact_count": len(report.get("missing_artifacts") or []),
                "residual_risk_count": len(report.get("residual_risk") or []),
            },
            dedupe_key=f"runtime_reconcile:{publish_id or 'unknown'}:{failure_id or 'none'}",
        )
        ingest_result = ingest_governance_event(
            event,
            log_path=governance_event_log_path,
            dedupe_index_path=governance_dedupe_index_path,
        )
        if ingest_result.get("ingest_status") == "invalid":
            _append_fallback_log(
                {
                    "timestamp": _now_iso(),
                    "reason": "governance_event_ingest_invalid",
                    "ingest_result": ingest_result,
                    "runtime_reconcile_report": report,
                },
                fallback_log_path,
            )
            handle_event_log_degradation(
                failed_event=event,
                ingest_result=ingest_result,
                context={
                    "related_failure_id": report.get("failure_id"),
                    "related_request_id": ctx.get("related_request_id"),
                    "publish_id": report.get("publish_id"),
                    "source_module": "runtime_publish_reconcile_hook",
                    "operator": ctx.get("operator") or "system",
                    "warning": "fallback log written for invalid ingest",
                },
            )
            return {"emit_status": "fallback_logged", "ingest_result": ingest_result}
        return {"emit_status": "event_logged", "ingest_result": ingest_result}
    except Exception as exc:
        try:
            _append_fallback_log(
                {
                    "timestamp": _now_iso(),
                    "reason": "emit_runtime_reconcile_event_exception",
                    "error": str(exc),
                    "runtime_reconcile_report": report,
                },
                fallback_log_path,
            )
            handle_event_log_degradation(
                failed_event=None,
                ingest_result={"ingest_status": "invalid", "errors": [str(exc)]},
                context={
                    "related_failure_id": report.get("failure_id"),
                    "related_request_id": ctx.get("related_request_id"),
                    "publish_id": report.get("publish_id"),
                    "source_module": "runtime_publish_reconcile_hook",
                    "operator": ctx.get("operator") or "system",
                    "exception": str(exc),
                    "warning": "fallback log written for ingest exception",
                },
            )
        except Exception:
            pass
        return {
            "emit_status": "fallback_logged",
            "ingest_result": {"ingest_status": "invalid", "errors": [str(exc)]},
        }


def run_publish_reconcile_hook(
    publish_artifact: dict | None = None,
    config_snapshot: dict | None = None,
    context: dict | None = None,
    *,
    output_path: Path = DEFAULT_RUNTIME_RECONCILE_ARTIFACT_PATH,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    fallback_log_path: Path = DEFAULT_RUNTIME_RECONCILE_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    report = reconcile_publish_failure(
        publish_artifact=publish_artifact,
        config_snapshot=config_snapshot,
        context=context,
    )
    write_runtime_reconcile_report(report, output_path=output_path)
    emit_result = emit_runtime_reconcile_event(
        report,
        context=context,
        governance_event_log_path=governance_event_log_path,
        governance_dedupe_index_path=governance_dedupe_index_path,
        fallback_log_path=fallback_log_path,
    )
    return {
        "report": report,
        "report_path": output_path.as_posix(),
        "event_emit": emit_result,
    }
