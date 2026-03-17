"""Runtime failure event normalizer v0.1.

This module standardizes runtime failures into auditable artifacts and emits
corresponding events into governance event log. It does not perform recovery.
"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.governance_event_log import (
    DEFAULT_DEDUPE_INDEX_PATH,
    DEFAULT_EVENT_LOG_PATH,
    build_governance_event,
    ingest_governance_event,
)
from tools.council_bridge.runtime_event_log_degradation_recovery import handle_event_log_degradation

RUNTIME_FAILURE_SCHEMA_VERSION = "runtime.failure.v0.1"
DEFAULT_RUNTIME_FAILURE_FALLBACK_LOG_PATH = Path("artifacts") / "runtime_failure_fallback.log"

FAILURE_TYPE_INGRESS_ROUTER = "ingress_router_failure"
FAILURE_TYPE_NORMALIZATION = "normalization_failure"
FAILURE_TYPE_ARTIFACT_WRITE = "artifact_write_failure"
FAILURE_TYPE_PUBLISH_APPLY = "publish_apply_failure"
FAILURE_TYPE_PUBLISH_ROLLBACK = "publish_rollback_failure"
FAILURE_TYPE_EVENT_LOG_WRITE = "event_log_write_failure"
FAILURE_TYPE_SNAPSHOT_JOB = "snapshot_job_failure"
FAILURE_TYPE_UNKNOWN = "unknown_runtime_failure"

STAGE_INGRESS = "ingress"
STAGE_NORMALIZATION = "normalization"
STAGE_ARTIFACT_WRITE = "artifact_write"
STAGE_PUBLISH_APPLY = "publish_apply"
STAGE_PUBLISH_ROLLBACK = "publish_rollback"
STAGE_EVENT_INGEST = "event_ingest"
STAGE_SNAPSHOT_JOB = "snapshot_job"
STAGE_RUNTIME_UNKNOWN = "runtime_unknown"


FAILURE_TYPE_ALIASES = {
    "ingress_router_failure": FAILURE_TYPE_INGRESS_ROUTER,
    "router_parse_error": FAILURE_TYPE_INGRESS_ROUTER,
    "router_failure": FAILURE_TYPE_INGRESS_ROUTER,
    "normalization_failure": FAILURE_TYPE_NORMALIZATION,
    "mapping_failure": FAILURE_TYPE_NORMALIZATION,
    "artifact_write_failure": FAILURE_TYPE_ARTIFACT_WRITE,
    "artifact_io_error": FAILURE_TYPE_ARTIFACT_WRITE,
    "publish_apply_failure": FAILURE_TYPE_PUBLISH_APPLY,
    "apply_failure": FAILURE_TYPE_PUBLISH_APPLY,
    "publish_rollback_failure": FAILURE_TYPE_PUBLISH_ROLLBACK,
    "rollback_failure": FAILURE_TYPE_PUBLISH_ROLLBACK,
    "event_log_write_failure": FAILURE_TYPE_EVENT_LOG_WRITE,
    "event_ingest_failure": FAILURE_TYPE_EVENT_LOG_WRITE,
    "snapshot_job_failure": FAILURE_TYPE_SNAPSHOT_JOB,
    "unknown_runtime_failure": FAILURE_TYPE_UNKNOWN,
}

STAGE_ALIASES = {
    "ingress": STAGE_INGRESS,
    "router": STAGE_INGRESS,
    "router_ingress": STAGE_INGRESS,
    "normalization": STAGE_NORMALIZATION,
    "mapping": STAGE_NORMALIZATION,
    "artifact_write": STAGE_ARTIFACT_WRITE,
    "artifact": STAGE_ARTIFACT_WRITE,
    "publish_apply": STAGE_PUBLISH_APPLY,
    "apply": STAGE_PUBLISH_APPLY,
    "publish_rollback": STAGE_PUBLISH_ROLLBACK,
    "rollback": STAGE_PUBLISH_ROLLBACK,
    "event_ingest": STAGE_EVENT_INGEST,
    "event_log": STAGE_EVENT_INGEST,
    "snapshot_job": STAGE_SNAPSHOT_JOB,
    "snapshot": STAGE_SNAPSHOT_JOB,
    "runtime_unknown": STAGE_RUNTIME_UNKNOWN,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_stage(failure_stage: str | None) -> str:
    key = _safe_text(failure_stage).lower()
    if not key:
        return STAGE_RUNTIME_UNKNOWN
    return STAGE_ALIASES.get(key, STAGE_RUNTIME_UNKNOWN)


def _infer_failure_type(*, failure_type: str | None, source_module: str | None, stage: str, exception: Exception | None) -> str:
    key = _safe_text(failure_type).lower()
    if key:
        return FAILURE_TYPE_ALIASES.get(key, FAILURE_TYPE_UNKNOWN)

    if stage == STAGE_INGRESS:
        return FAILURE_TYPE_INGRESS_ROUTER
    if stage == STAGE_NORMALIZATION:
        return FAILURE_TYPE_NORMALIZATION
    if stage == STAGE_ARTIFACT_WRITE:
        return FAILURE_TYPE_ARTIFACT_WRITE
    if stage == STAGE_PUBLISH_APPLY:
        return FAILURE_TYPE_PUBLISH_APPLY
    if stage == STAGE_PUBLISH_ROLLBACK:
        return FAILURE_TYPE_PUBLISH_ROLLBACK
    if stage == STAGE_EVENT_INGEST:
        return FAILURE_TYPE_EVENT_LOG_WRITE
    if stage == STAGE_SNAPSHOT_JOB:
        return FAILURE_TYPE_SNAPSHOT_JOB

    module_text = _safe_text(source_module).lower()
    if "router" in module_text:
        return FAILURE_TYPE_INGRESS_ROUTER
    if "normal" in module_text or "mapping" in module_text:
        return FAILURE_TYPE_NORMALIZATION
    if "artifact" in module_text:
        return FAILURE_TYPE_ARTIFACT_WRITE
    if "publish" in module_text and "rollback" in module_text:
        return FAILURE_TYPE_PUBLISH_ROLLBACK
    if "publish" in module_text:
        return FAILURE_TYPE_PUBLISH_APPLY
    if "event" in module_text and "log" in module_text:
        return FAILURE_TYPE_EVENT_LOG_WRITE
    if "snapshot" in module_text:
        return FAILURE_TYPE_SNAPSHOT_JOB

    if exception is not None:
        msg = _safe_text(str(exception)).lower()
        if "parse" in msg or "json" in msg:
            return FAILURE_TYPE_INGRESS_ROUTER

    return FAILURE_TYPE_UNKNOWN


def _default_recovery_action(failure_type: str) -> str:
    if failure_type in {FAILURE_TYPE_EVENT_LOG_WRITE, FAILURE_TYPE_ARTIFACT_WRITE, FAILURE_TYPE_SNAPSHOT_JOB}:
        return "retry"
    if failure_type == FAILURE_TYPE_PUBLISH_APPLY:
        return "rollback"
    if failure_type in {FAILURE_TYPE_PUBLISH_ROLLBACK, FAILURE_TYPE_INGRESS_ROUTER, FAILURE_TYPE_NORMALIZATION}:
        return "manual_required"
    return "ignore"


def _build_audit_trace(exception: Exception | None) -> dict[str, str]:
    if exception is None:
        return {
            "exception_type": "",
            "exception_message": "",
            "stack_hint": "",
        }

    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    stack_hint = ""
    lines = [line.strip() for line in tb.splitlines() if line.strip()]
    if lines:
        stack_hint = lines[-1][:300]

    return {
        "exception_type": type(exception).__name__,
        "exception_message": _safe_text(str(exception)),
        "stack_hint": stack_hint,
    }


def normalize_failure_event(
    exception: Exception | None = None,
    failure_type: str | None = None,
    failure_stage: str | None = None,
    source_module: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}

    stage = _normalize_stage(failure_stage)
    normalized_failure_type = _infer_failure_type(
        failure_type=failure_type,
        source_module=source_module,
        stage=stage,
        exception=exception,
    )
    if not normalized_failure_type:
        normalized_failure_type = FAILURE_TYPE_UNKNOWN

    failure_id = f"fail-{uuid.uuid4().hex}"
    detected_at = _now_iso()

    operator = _safe_text(ctx.get("operator")) or "system"
    recovery_action = _safe_text(ctx.get("recovery_action")) or _default_recovery_action(normalized_failure_type)

    return {
        "artifact_type": "runtime_failure_event",
        "schema_version": RUNTIME_FAILURE_SCHEMA_VERSION,
        "failure_id": failure_id,
        "related_request_id": ctx.get("related_request_id") or ctx.get("request_id"),
        "publish_id": ctx.get("publish_id"),
        "source_module": _safe_text(source_module) or "runtime_unknown",
        "failure_type": normalized_failure_type,
        "failure_stage": stage,
        "detected_at": detected_at,
        "recovery_action": recovery_action,
        "recovery_status": "pending",
        "operator": operator,
        "audit_trace": _build_audit_trace(exception),
    }


def _append_fallback_log(record: dict[str, Any], fallback_log_path: Path) -> None:
    fallback_log_path.parent.mkdir(parents=True, exist_ok=True)
    with fallback_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit_runtime_failure_event(
    exception: Exception | None = None,
    failure_type: str | None = None,
    failure_stage: str | None = None,
    source_module: str | None = None,
    context: dict[str, Any] | None = None,
    *,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    fallback_log_path: Path = DEFAULT_RUNTIME_FAILURE_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    try:
        normalized = normalize_failure_event(
            exception=exception,
            failure_type=failure_type,
            failure_stage=failure_stage,
            source_module=source_module,
            context=context,
        )

        ctx = context if isinstance(context, dict) else {}
        event = build_governance_event(
            event_id=f"runtime_failure:{normalized['failure_id']}",
            event_type="runtime_failure_event",
            occurred_at=normalized["detected_at"],
            request_id=normalized.get("related_request_id"),
            publish_id=normalized.get("publish_id"),
            workspace_id=ctx.get("workspace_id"),
            project_id=ctx.get("project_id"),
            owner_id=ctx.get("owner_id"),
            source_module=normalized.get("source_module") or "runtime_failure_event_normalizer",
            source_artifact=ctx.get("source_artifact") or f"runtime_failure_event:{normalized['failure_id']}",
            status=normalized.get("recovery_status") or "pending",
            payload_summary={
                "failure_type": normalized.get("failure_type"),
                "failure_stage": normalized.get("failure_stage"),
                "recovery_action": normalized.get("recovery_action"),
            },
            dedupe_key=f"runtime_failure:{normalized['failure_id']}",
        )
        ingest_result = ingest_governance_event(
            event,
            log_path=governance_event_log_path,
            dedupe_index_path=governance_dedupe_index_path,
        )

        if ingest_result.get("ingest_status") == "invalid":
            fallback_record = {
                "timestamp": _now_iso(),
                "reason": "governance_event_ingest_invalid",
                "ingest_result": ingest_result,
                "runtime_failure_event": normalized,
            }
            _append_fallback_log(fallback_record, fallback_log_path)
            handle_event_log_degradation(
                failed_event=event,
                ingest_result=ingest_result,
                context={
                    "related_failure_id": normalized.get("failure_id"),
                    "related_request_id": normalized.get("related_request_id"),
                    "publish_id": normalized.get("publish_id"),
                    "source_module": "runtime_failure_event_normalizer",
                    "operator": normalized.get("operator") or "system",
                    "warning": "fallback log written for invalid ingest",
                },
            )
            return {
                "failure_id": normalized["failure_id"],
                "emit_status": "fallback_logged",
                "ingest_result": ingest_result,
            }

        return {
            "failure_id": normalized["failure_id"],
            "emit_status": "event_logged",
            "ingest_result": ingest_result,
        }
    except Exception as emit_exc:
        fallback_event = normalize_failure_event(
            exception=emit_exc,
            failure_type=FAILURE_TYPE_EVENT_LOG_WRITE,
            failure_stage=STAGE_EVENT_INGEST,
            source_module="runtime_failure_event_normalizer",
            context=context,
        )
        fallback_record = {
            "timestamp": _now_iso(),
            "reason": "emit_runtime_failure_event_exception",
            "runtime_failure_event": fallback_event,
        }
        try:
            _append_fallback_log(fallback_record, fallback_log_path)
            handle_event_log_degradation(
                failed_event=None,
                ingest_result={"ingest_status": "invalid", "errors": [str(emit_exc)]},
                context={
                    "related_failure_id": fallback_event.get("failure_id"),
                    "related_request_id": fallback_event.get("related_request_id"),
                    "publish_id": fallback_event.get("publish_id"),
                    "source_module": "runtime_failure_event_normalizer",
                    "operator": fallback_event.get("operator") or "system",
                    "exception": str(emit_exc),
                    "warning": "fallback log written for ingest exception",
                },
            )
        except Exception:
            # Last-resort safety: do not propagate.
            pass
        return {
            "failure_id": fallback_event["failure_id"],
            "emit_status": "fallback_logged",
            "ingest_result": {
                "ingest_status": "invalid",
                "errors": [str(emit_exc)],
            },
        }
