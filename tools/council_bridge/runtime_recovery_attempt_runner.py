"""Runtime recovery attempt runner v0.1.

Runs minimal recovery attempt decisioning for runtime failures without changing
business flow semantics.
"""

from __future__ import annotations

import hashlib
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
from tools.council_bridge.runtime_failure_event_normalizer import (
    DEFAULT_RUNTIME_FAILURE_FALLBACK_LOG_PATH,
    FAILURE_TYPE_ARTIFACT_WRITE,
    FAILURE_TYPE_EVENT_LOG_WRITE,
    FAILURE_TYPE_INGRESS_ROUTER,
    FAILURE_TYPE_NORMALIZATION,
    FAILURE_TYPE_PUBLISH_APPLY,
    FAILURE_TYPE_PUBLISH_ROLLBACK,
    FAILURE_TYPE_SNAPSHOT_JOB,
    FAILURE_TYPE_UNKNOWN,
)
from tools.council_bridge.runtime_event_log_degradation_recovery import handle_event_log_degradation

RUNTIME_RECOVERY_SCHEMA_VERSION = "runtime.recovery.v0.1"
DEFAULT_RUNTIME_RECOVERY_ARTIFACT_PATH = Path("artifacts") / "runtime_recovery_attempt.json"
DEFAULT_RUNTIME_RECOVERY_FALLBACK_LOG_PATH = Path("artifacts") / "runtime_recovery_fallback.log"

ACTION_RETRY = "retry"
ACTION_IGNORE = "ignore"
ACTION_MANUAL_REQUIRED = "manual_required"

RESULT_SUCCESS = "success"
RESULT_FAILED_RETRYABLE = "failed_retryable"
RESULT_FAILED_TERMINAL = "failed_terminal"
RESULT_IGNORED = "ignored"
RESULT_MANUAL_REQUIRED = "manual_required"

RETRYABLE_FAILURE_TYPES = {
    FAILURE_TYPE_ARTIFACT_WRITE,
    FAILURE_TYPE_EVENT_LOG_WRITE,
    FAILURE_TYPE_SNAPSHOT_JOB,
}

MANUAL_REQUIRED_FAILURE_TYPES = {
    FAILURE_TYPE_INGRESS_ROUTER,
    FAILURE_TYPE_NORMALIZATION,
    FAILURE_TYPE_PUBLISH_APPLY,
    FAILURE_TYPE_PUBLISH_ROLLBACK,
    FAILURE_TYPE_UNKNOWN,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _append_fallback_log(record: dict[str, Any], fallback_log_path: Path) -> None:
    fallback_log_path.parent.mkdir(parents=True, exist_ok=True)
    with fallback_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _default_action_for_failure(failure_type: str) -> str:
    if failure_type in RETRYABLE_FAILURE_TYPES:
        return ACTION_RETRY
    if failure_type in MANUAL_REQUIRED_FAILURE_TYPES:
        return ACTION_MANUAL_REQUIRED
    return ACTION_MANUAL_REQUIRED


def _max_attempts_for_action(*, action: str, failure_type: str, recovery_policy: dict[str, Any]) -> int:
    if action != ACTION_RETRY:
        return 0
    configured = recovery_policy.get("max_attempts")
    if isinstance(configured, int) and configured > 0:
        return configured
    if failure_type in RETRYABLE_FAILURE_TYPES:
        return 3
    return 0


def _resolve_attempt_no(failure_event: dict[str, Any], recovery_policy: dict[str, Any]) -> int:
    if isinstance(recovery_policy.get("attempt_no"), int) and recovery_policy["attempt_no"] >= 1:
        return int(recovery_policy["attempt_no"])
    previous = recovery_policy.get("previous_attempt_no")
    if not isinstance(previous, int):
        previous = failure_event.get("last_attempt_no")
    if not isinstance(previous, int):
        previous = 0
    return max(1, int(previous) + 1)


def _build_idempotency_key(*, failure_id: str, attempt_no: int, action: str) -> str:
    base = f"{failure_id}:{attempt_no}:{action}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:32]


def _execute_retry_stub(*, failure_event: dict[str, Any], recovery_policy: dict[str, Any]) -> tuple[bool, str]:
    # v0.1 stub executor: no real external invocation.
    forced = _safe_text(recovery_policy.get("force_attempt_result")).lower()
    if forced == RESULT_SUCCESS:
        return True, "stub executor forced success"
    if forced in {RESULT_FAILED_RETRYABLE, RESULT_FAILED_TERMINAL}:
        return False, f"stub executor forced {forced}"

    fail_stub = bool(recovery_policy.get("stub_should_fail"))
    if fail_stub:
        return False, "stub executor simulated retry failure"

    failure_type = _safe_text(failure_event.get("failure_type"))
    if failure_type == FAILURE_TYPE_EVENT_LOG_WRITE:
        return False, "stub executor cannot validate event log replay in v0.1"

    return True, "stub executor simulated successful retry"


def _build_attempt_result(*, action: str, attempt_no: int, max_attempts: int, retry_success: bool, retry_message: str) -> tuple[str, str]:
    if action == ACTION_IGNORE:
        return RESULT_IGNORED, "ignored by policy"
    if action == ACTION_MANUAL_REQUIRED:
        return RESULT_MANUAL_REQUIRED, "manual intervention required"
    if action != ACTION_RETRY:
        return RESULT_FAILED_TERMINAL, "unknown recovery action"

    if attempt_no > max_attempts:
        return RESULT_FAILED_TERMINAL, "max retry attempts exceeded"

    if retry_success:
        return RESULT_SUCCESS, retry_message

    if attempt_no < max_attempts:
        return RESULT_FAILED_RETRYABLE, retry_message
    return RESULT_FAILED_TERMINAL, retry_message


def run_recovery_attempt(
    failure_event: dict,
    recovery_policy: dict | None = None,
    operator: str = "system",
) -> dict:
    policy = recovery_policy if isinstance(recovery_policy, dict) else {}

    failure_id = _safe_text(failure_event.get("failure_id"))
    if not failure_id:
        failure_id = f"missing-failure-id-{hashlib.sha1(json.dumps(failure_event, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]}"

    failure_type = _safe_text(failure_event.get("failure_type")) or FAILURE_TYPE_UNKNOWN
    if failure_type == FAILURE_TYPE_PUBLISH_APPLY:
        action = ACTION_MANUAL_REQUIRED
    else:
        action = _safe_text(policy.get("recovery_action")) or _safe_text(failure_event.get("recovery_action")) or _default_action_for_failure(failure_type)

    if action not in {ACTION_RETRY, ACTION_IGNORE, ACTION_MANUAL_REQUIRED}:
        action = ACTION_MANUAL_REQUIRED

    attempt_no = _resolve_attempt_no(failure_event, policy)
    max_attempts = _max_attempts_for_action(action=action, failure_type=failure_type, recovery_policy=policy)

    retry_success = False
    retry_message = ""
    if action == ACTION_RETRY:
        retry_success, retry_message = _execute_retry_stub(failure_event=failure_event, recovery_policy=policy)

    attempt_result, error_detail = _build_attempt_result(
        action=action,
        attempt_no=attempt_no,
        max_attempts=max_attempts,
        retry_success=retry_success,
        retry_message=retry_message,
    )

    recovery_status = "completed" if attempt_result in {RESULT_SUCCESS, RESULT_IGNORED} else "pending"
    idempotency_key = _build_idempotency_key(failure_id=failure_id, attempt_no=attempt_no, action=action)

    return {
        "artifact_type": "runtime_recovery_attempt",
        "schema_version": RUNTIME_RECOVERY_SCHEMA_VERSION,
        "failure_id": failure_id,
        "related_request_id": failure_event.get("related_request_id"),
        "publish_id": failure_event.get("publish_id"),
        "source_module": _safe_text(failure_event.get("source_module")) or "runtime_unknown",
        "failure_type": failure_type,
        "failure_stage": _safe_text(failure_event.get("failure_stage")) or "runtime_unknown",
        "detected_at": _safe_text(failure_event.get("detected_at")) or _now_iso(),
        "recovery_action": action,
        "recovery_status": recovery_status,
        "operator": _safe_text(operator) or "system",
        "attempt_no": attempt_no,
        "max_attempts": max_attempts,
        "idempotency_key": idempotency_key,
        "attempt_result": attempt_result,
        "error_detail": error_detail,
        "audit_trace": {
            "runner": "runtime_recovery_attempt_runner.v0.1",
            "executor_mode": "stub",
            "policy_applied": {
                "retryable_failure_types": sorted(RETRYABLE_FAILURE_TYPES),
                "manual_required_failure_types": sorted(MANUAL_REQUIRED_FAILURE_TYPES),
            },
            "source_failure_audit_trace": failure_event.get("audit_trace") if isinstance(failure_event.get("audit_trace"), dict) else {},
        },
    }


def write_runtime_recovery_attempt_artifact(
    artifact: dict[str, Any],
    output_path: Path = DEFAULT_RUNTIME_RECOVERY_ARTIFACT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def emit_runtime_recovery_attempt_event(
    artifact: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    fallback_log_path: Path = DEFAULT_RUNTIME_RECOVERY_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    try:
        event = build_governance_event(
            event_id=f"runtime_recovery:{_safe_text(artifact.get('failure_id'))}:{artifact.get('attempt_no')}",
            event_type="runtime_recovery_attempt",
            occurred_at=_safe_text(artifact.get("detected_at")) or _now_iso(),
            request_id=artifact.get("related_request_id"),
            publish_id=artifact.get("publish_id"),
            workspace_id=ctx.get("workspace_id"),
            project_id=ctx.get("project_id"),
            owner_id=ctx.get("owner_id"),
            source_module=_safe_text(artifact.get("source_module")) or "runtime_recovery_attempt_runner",
            source_artifact=ctx.get("source_artifact") or f"runtime_recovery_attempt:{artifact.get('failure_id')}:{artifact.get('attempt_no')}",
            status=_safe_text(artifact.get("attempt_result")) or "unknown",
            payload_summary={
                "recovery_action": artifact.get("recovery_action"),
                "recovery_status": artifact.get("recovery_status"),
                "attempt_no": artifact.get("attempt_no"),
                "max_attempts": artifact.get("max_attempts"),
            },
            dedupe_key=f"runtime_recovery:{_safe_text(artifact.get('failure_id'))}:{artifact.get('attempt_no')}",
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
                    "runtime_recovery_attempt": artifact,
                },
                fallback_log_path,
            )
            handle_event_log_degradation(
                failed_event=event,
                ingest_result=ingest_result,
                context={
                    "related_failure_id": artifact.get("failure_id"),
                    "related_request_id": artifact.get("related_request_id"),
                    "publish_id": artifact.get("publish_id"),
                    "source_module": "runtime_recovery_attempt_runner",
                    "operator": artifact.get("operator") or "system",
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
                    "reason": "emit_runtime_recovery_attempt_event_exception",
                    "error": str(exc),
                    "runtime_recovery_attempt": artifact,
                },
                fallback_log_path,
            )
            handle_event_log_degradation(
                failed_event=None,
                ingest_result={"ingest_status": "invalid", "errors": [str(exc)]},
                context={
                    "related_failure_id": artifact.get("failure_id"),
                    "related_request_id": artifact.get("related_request_id"),
                    "publish_id": artifact.get("publish_id"),
                    "source_module": "runtime_recovery_attempt_runner",
                    "operator": artifact.get("operator") or "system",
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


def run_and_emit_recovery_attempt(
    failure_event: dict,
    recovery_policy: dict | None = None,
    operator: str = "system",
    *,
    artifact_output_path: Path = DEFAULT_RUNTIME_RECOVERY_ARTIFACT_PATH,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    fallback_log_path: Path = DEFAULT_RUNTIME_FAILURE_FALLBACK_LOG_PATH,
    event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = run_recovery_attempt(
        failure_event=failure_event,
        recovery_policy=recovery_policy,
        operator=operator,
    )
    write_runtime_recovery_attempt_artifact(artifact, artifact_output_path)
    emit_result = emit_runtime_recovery_attempt_event(
        artifact,
        context=event_context,
        governance_event_log_path=governance_event_log_path,
        governance_dedupe_index_path=governance_dedupe_index_path,
        fallback_log_path=fallback_log_path,
    )
    return {
        "artifact": artifact,
        "artifact_path": artifact_output_path.as_posix(),
        "event_emit": emit_result,
    }
