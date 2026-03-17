"""Unified Feishu message router for webhook and polling.

Supports two lanes:
1. action lane (dispatch/approved/... stage-protocol)
2. chat lane (free-text -> queue for chat bridge worker)
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.council_bridge.bridge_config import resolve_runtime_config
from tools.council_bridge.council_artifact_schema import COUNCIL_ARTIFACT_TYPES
from tools.council_bridge.council_artifact_state_machine import (
    TransitionRequest,
    validate_transition,
    write_transition_audit,
)
from tools.council_bridge.execution_task_queue import DEFAULT_DB_PATH, enqueue_task
from tools.council_bridge.execution_handoff_gate import (
    validate_execution_handoff_gate,
    write_execution_handoff_gate_result,
)
from tools.council_bridge.execution_trigger_protocol import extract_execution_trigger
from tools.council_bridge.feishu_feedback_mapping_adapter import map_feishu_feedback, write_mapping_result
from tools.council_bridge.handoff_execution_brief_mapper import build_execution_brief, write_execution_brief
from tools.council_bridge.council_role_rework_adapter import (
    map_role_rework_hint,
    write_role_rework_mapping_result,
)
from tools.council_bridge.owner_confirmed_role_rework_apply import apply_owner_confirmed_role_rework
from tools.council_bridge.owner_confirmed_execution_dispatch import dispatch_owner_confirmed_execution
from tools.council_bridge.owner_confirmed_transition_apply import apply_owner_confirmed_transition
from tools.council_bridge.scope_validator import validate_scope
from tools.council_bridge.governance_event_log import (
    DEFAULT_DEDUPE_INDEX_PATH as GOVERNANCE_DEDUPE_INDEX_PATH,
    DEFAULT_EVENT_LOG_PATH as GOVERNANCE_EVENT_LOG_PATH,
    build_governance_event,
    ingest_governance_event,
)


CONTINUE_ONCE_SCRIPT = Path("tools") / "council_bridge" / "feishu_continue_once.py"
FINAL_REVIEW_ONCE_SCRIPT = Path("tools") / "council_bridge" / "final_review_once.py"

DISPATCH_READY_ACTIONS = {"dispatch", "hold", "needs_fix", "reject"}
REVIEW_READY_ACTIONS = {"approved", "revision_request", "needs_fix", "rejected"}
ACTION_KEYWORDS = tuple(sorted(DISPATCH_READY_ACTIONS | REVIEW_READY_ACTIONS, key=len, reverse=True))

ROUTE_RESULT_PATH = Path("artifacts") / "council_feishu_message_route_result.json"
DEDUPE_STATE_PATH = Path("artifacts") / "council_feishu_message_dedupe_state.json"
COUNCIL_FEEDBACK_MAPPING_RESULT_PATH = Path("artifacts") / "council_feishu_feedback_mapping_result.json"
COUNCIL_TRANSITION_RESULT_PATH = Path("artifacts") / "council_artifact_state_transition_result.json"
COUNCIL_OWNER_APPLY_RESULT_PATH = Path("artifacts") / "council_owner_confirmed_apply_result.json"
COUNCIL_EXECUTION_GATE_RESULT_PATH = Path("artifacts") / "council_execution_handoff_gate_result.json"
COUNCIL_EXECUTION_BRIEF_PATH = Path("artifacts") / "council_execution_brief.json"
COUNCIL_EXECUTION_DISPATCH_RESULT_PATH = Path("artifacts") / "council_execution_dispatch_result.json"
COUNCIL_EXECUTION_RUNTIME_STATUS_PATH = Path("artifacts") / "council_execution_runtime_status.json"
COUNCIL_EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_execution_receipt.json"
COUNCIL_CONFIRM_KEYWORDS = ("confirm_transition", "apply_suggested_transition")
COUNCIL_ROLE_REWORK_CONFIRM_KEYWORDS = ("confirm_role_rework", "apply_role_rework_transition")
COUNCIL_ROLE_REWORK_MAPPING_RESULT_PATH = Path("artifacts") / "council_role_rework_mapping_result.json"
COUNCIL_ROLE_REWORK_TRANSITION_RESULT_PATH = Path("artifacts") / "council_role_rework_transition_result.json"
COUNCIL_ROLE_REWORK_APPLY_RESULT_PATH = Path("artifacts") / "council_owner_confirmed_role_rework_apply_result.json"
COUNCIL_ROLE_REWORK_ADVISORY_PATH = Path("artifacts") / "council_role_rework_advisory_artifact.json"


RunnerFn = Callable[[list[str]], tuple[str, str]]
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_action_from_text(text: str) -> str | None:
    normalized = str(text or "").lower()
    for key in ACTION_KEYWORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])", normalized):
            return key
    return None


def resolve_stage_from_source_artifact(source_artifact: str) -> str:
    path = Path(source_artifact)
    if not path.exists():
        return "dispatch_ready"
    payload = _safe_load_json(path)
    if not isinstance(payload, dict):
        return "dispatch_ready"
    name = path.name
    if name == "council_codex_execution_receipt_skeleton.json":
        return "review_ready"
    if isinstance(payload.get("owner_review_ready"), bool) and payload.get("owner_review_ready"):
        return "review_ready"
    if payload.get("completion_observation_status") == "execution_receipt_available":
        return "review_ready"
    if name == "council_owner_final_review_summary.json":
        return "final_summary"
    return "dispatch_ready"


def allowed_actions_for_stage(stage: str) -> list[str]:
    if stage == "dispatch_ready":
        return sorted(DISPATCH_READY_ACTIONS)
    if stage == "review_ready":
        return sorted(REVIEW_READY_ACTIONS)
    return []


def _run_local_command(command: list[str]) -> tuple[str, str]:
    proc = subprocess.run(command, capture_output=True, text=True)
    status = "success" if proc.returncode == 0 else "failed"
    info = (proc.stdout or proc.stderr or "").strip()[:1200]
    return status, info


def build_continue_once_command(
    *,
    source_artifact: str,
    action: str,
    owner_id: str,
    notes: str,
    check_completion_once: bool,
    build_receipt_skeleton: bool,
    output: str = "artifacts/council_feishu_continue_once_result.json",
) -> list[str]:
    cmd = [
        "py",
        CONTINUE_ONCE_SCRIPT.as_posix(),
        "--source-artifact",
        source_artifact,
        "--owner-action",
        action,
        "--owner-id",
        owner_id,
        "--notes",
        notes,
        "--output",
        output,
    ]
    if check_completion_once:
        cmd.append("--check-completion-once")
    if build_receipt_skeleton:
        cmd.append("--build-receipt-skeleton")
    return cmd


def build_final_review_once_command(
    *,
    final_decision: str,
    source_artifact: str,
    owner_id: str,
    matched_keyword: str,
    notes: str,
    output: str = "artifacts/council_final_review_once_result.json",
) -> list[str]:
    reason_map = {
        "approved": "Feishu mobile review accepted current round result.",
        "revision_request": "Feishu mobile review requests targeted revision.",
        "needs_fix": "Feishu mobile review marks input/contract fix required.",
        "rejected": "Feishu mobile review rejects this round outcome.",
    }
    next_map = {
        "approved": "Close this round and archive artifacts.",
        "revision_request": "Open a revision round with focused fix scope.",
        "needs_fix": "Return to handoff/contract correction before rerun.",
        "rejected": "Stop current round and start a new scoped round if needed.",
    }
    listener_note = (
        f"{notes}; source_artifact={source_artifact}; owner_id={owner_id}; "
        f"keyword={matched_keyword}; listener_route=final_review_once"
    )
    return [
        "py",
        FINAL_REVIEW_ONCE_SCRIPT.as_posix(),
        "--final-decision",
        final_decision,
        "--key-reason",
        reason_map[final_decision],
        "--next-action",
        next_map[final_decision],
        "--notes",
        listener_note,
        "--output",
        output,
    ]


def _normalize_message_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(raw.get("source") or "unknown"),
        "event_id": str(raw.get("event_id") or ""),
        "message_id": str(raw.get("message_id") or ""),
        "chat_id": str(raw.get("chat_id") or ""),
        "sender_id": str(raw.get("sender_id") or "feishu_unknown"),
        "sender_name": str(raw.get("sender_name") or ""),
        "text": str(raw.get("text") or ""),
        "create_time": str(raw.get("create_time") or ""),
        "raw_event_path": str(raw.get("raw_event_path") or ""),
        "workspace_id": str(raw.get("workspace_id") or ""),
        "project_id": str(raw.get("project_id") or ""),
        "scope_validation_mode": str(raw.get("scope_validation_mode") or ""),
    }


def _dedupe_fallback(payload: dict[str, Any]) -> str:
    return "|".join(
        [
            str(payload.get("chat_id") or ""),
            str(payload.get("sender_id") or ""),
            str(payload.get("text") or ""),
            str(payload.get("create_time") or ""),
        ]
    )


def build_dedupe_key(payload: dict[str, Any]) -> tuple[str, str]:
    event_id = str(payload.get("event_id") or "").strip()
    if event_id:
        return "event_id", event_id
    message_id = str(payload.get("message_id") or "").strip()
    if message_id:
        return "message_id", message_id
    return "fallback", _dedupe_fallback(payload)


def _load_dedupe_state(path: Path) -> dict[str, Any]:
    default = {"processed": {}, "updated_at": _now_iso()}
    if not path.exists():
        return default
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        return default
    processed = data.get("processed")
    if not isinstance(processed, dict):
        processed = {}
    return {"processed": processed, "updated_at": data.get("updated_at", _now_iso())}


def check_and_mark_dedupe(payload: dict[str, Any], *, state_path: Path = DEDUPE_STATE_PATH) -> dict[str, Any]:
    state = _load_dedupe_state(state_path)
    processed = state.get("processed", {})
    key_type, key_value = build_dedupe_key(payload)
    dedupe_key = f"{key_type}:{key_value}"
    already = dedupe_key in processed
    if not already:
        processed[dedupe_key] = {
            "first_seen_at": _now_iso(),
            "source": payload.get("source"),
            "message_id": payload.get("message_id"),
            "event_id": payload.get("event_id"),
            "chat_id": payload.get("chat_id"),
        }
        state["processed"] = processed
        _write_json(state_path, state)
    return {
        "dedupe_key": dedupe_key,
        "dedupe_status": "deduped" if already else "fresh",
        "already_processed": already,
    }


def _is_chat_mention_valid(text: str, mention_tokens: list[str]) -> bool:
    return any(token in text for token in mention_tokens)


def _is_council_artifact_context(linked: dict[str, Any] | None) -> bool:
    if not isinstance(linked, dict):
        return False
    artifact_type = linked.get("artifact_type")
    produced_by_lane = linked.get("produced_by_lane")
    schema_version = linked.get("schema_version")
    if isinstance(artifact_type, str) and artifact_type in COUNCIL_ARTIFACT_TYPES:
        return True
    if produced_by_lane == "council":
        return True
    if isinstance(schema_version, str) and schema_version.startswith("council.artifact."):
        return True
    return False


def _summarize_council_observation(
    mapping_type: str,
    feedback_type: str | None,
    target_section: str | None,
    transition_summary: str,
    validation_status: str,
    validation_errors: list[str],
) -> str:
    parts = [
        f"mapping_type={mapping_type}",
        f"feedback_type={feedback_type or 'n/a'}",
        f"target_section={target_section or 'unspecified'}",
        f"suggested_transition={transition_summary}",
        f"validation={validation_status}",
        "observe_only=true (no state change applied)",
    ]
    if validation_errors:
        parts.append(f"errors={'; '.join(validation_errors[:2])}")
    return " | ".join(parts)


def _summarize_execution_handoff_observation(
    *,
    trigger_keyword: str | None,
    gate_ready: bool,
    blocked_reason: str,
    brief_generated: bool,
) -> str:
    if gate_ready:
        return (
            f"execution_trigger={trigger_keyword or 'n/a'} | gate=ready | brief_generated={brief_generated} | "
            "observe_only=true (handoff-ready does not auto-dispatch)"
        )
    return (
        f"execution_trigger={trigger_keyword or 'n/a'} | gate=blocked | "
        f"reason={blocked_reason or 'unknown'} | observe_only=true (no execution dispatch)"
    )


def _extract_council_confirm_signal(payload: dict[str, Any]) -> tuple[bool, str | None]:
    text = str(payload.get("text") or "").lower()
    source = str(payload.get("source") or "").lower()
    for keyword in COUNCIL_CONFIRM_KEYWORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", text):
            if "action_protocol" in source or "owner_action" in source or "bridge" in source:
                return True, keyword
            return False, keyword
    return False, None


def _extract_role_rework_confirm_signal(payload: dict[str, Any]) -> tuple[bool, str | None]:
    text = str(payload.get("text") or "").lower()
    source = str(payload.get("source") or "").lower()
    for keyword in COUNCIL_ROLE_REWORK_CONFIRM_KEYWORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", text):
            if "action_protocol" in source or "owner_action" in source or "bridge" in source:
                return True, keyword
            return False, keyword
    return False, None


def route_message(
    raw_payload: dict[str, Any],
    *,
    source_artifact: str,
    stage: str = "auto",
    check_completion_once: bool = False,
    build_receipt_skeleton: bool = False,
    runner: RunnerFn = _run_local_command,
    dedupe_state_path: Path = DEDUPE_STATE_PATH,
    route_result_path: Path = ROUTE_RESULT_PATH,
    queue_db_path: Path = DEFAULT_DB_PATH,
    council_mapping_result_path: Path = COUNCIL_FEEDBACK_MAPPING_RESULT_PATH,
    council_transition_result_path: Path = COUNCIL_TRANSITION_RESULT_PATH,
    council_owner_apply_result_path: Path = COUNCIL_OWNER_APPLY_RESULT_PATH,
    council_execution_gate_result_path: Path = COUNCIL_EXECUTION_GATE_RESULT_PATH,
    council_execution_brief_path: Path = COUNCIL_EXECUTION_BRIEF_PATH,
    council_execution_dispatch_result_path: Path = COUNCIL_EXECUTION_DISPATCH_RESULT_PATH,
    council_execution_runtime_status_path: Path = COUNCIL_EXECUTION_RUNTIME_STATUS_PATH,
    council_execution_receipt_path: Path = COUNCIL_EXECUTION_RECEIPT_PATH,
    council_role_rework_mapping_result_path: Path = COUNCIL_ROLE_REWORK_MAPPING_RESULT_PATH,
    council_role_rework_transition_result_path: Path = COUNCIL_ROLE_REWORK_TRANSITION_RESULT_PATH,
    council_role_rework_apply_result_path: Path = COUNCIL_ROLE_REWORK_APPLY_RESULT_PATH,
    council_role_rework_advisory_path: Path = COUNCIL_ROLE_REWORK_ADVISORY_PATH,
    governance_event_log_path: Path = GOVERNANCE_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = GOVERNANCE_DEDUPE_INDEX_PATH,
) -> dict[str, Any]:
    payload = _normalize_message_payload(raw_payload)
    resolved_stage = resolve_stage_from_source_artifact(source_artifact) if stage == "auto" else stage
    allowed = allowed_actions_for_stage(resolved_stage)
    action = extract_action_from_text(payload["text"])
    dedupe = check_and_mark_dedupe(payload, state_path=dedupe_state_path)
    try:
        cfg = resolve_runtime_config(
            owner_id=payload["sender_id"],
            chat_id=payload["chat_id"],
            workspace_id=payload["workspace_id"],
            project_id=payload["project_id"],
        )
    except TypeError:
        # Backward compatibility for tests/extensions monkeypatching old signature.
        cfg = resolve_runtime_config(
            owner_id=payload["sender_id"],
            chat_id=payload["chat_id"],
        )

    result: dict[str, Any] = {
        "event_time": _now_iso(),
        "source": payload.get("source"),
        "event_id": payload.get("event_id"),
        "message_id": payload.get("message_id"),
        "chat_id": payload.get("chat_id"),
        "sender_id": payload.get("sender_id"),
        "sender_name": payload.get("sender_name"),
        "text": payload.get("text"),
        "create_time": payload.get("create_time"),
        "source_artifact": source_artifact,
        "workspace_id": payload.get("workspace_id") or cfg.get("workspace_id"),
        "project_id": payload.get("project_id") or cfg.get("project_id"),
        "policy_scope": cfg.get("policy_scope"),
        "alias_scope": cfg.get("alias_scope"),
        "policy_version": cfg.get("policy_version"),
        "active_alias_version": cfg.get("active_alias_version"),
        "action_stage": resolved_stage,
        "allowed_actions": allowed,
        "detected_action": action,
        "message_kind": "action_command" if action else "free_text",
        "route_type": "ignored",
        "routed_entrypoint": "no-op",
        "triggered_command": "",
        "task_id": None,
        "result_status": "ignored",
        "result_info": "",
        "ignored_reason": "",
        "dedupe_status": dedupe["dedupe_status"],
        "dedupe_key": dedupe["dedupe_key"],
        "already_processed": dedupe["already_processed"],
        "correlated_request_id": None,
        "correlated_brief_id": None,
        "correlated_handoff_id": None,
        "mapping_status": "not_applicable",
        "validation_status": "not_applicable",
        "suggested_transition_summary": "",
        "observe_only": False,
        "execution_gate_status": "not_applicable",
        "execution_brief_path": "",
        "scope_validation": {},
    }

    linked = _safe_load_json(Path(source_artifact))
    if isinstance(linked, dict):
        for src_key, dst_key in [
            ("request_id", "correlated_request_id"),
            ("brief_id", "correlated_brief_id"),
            ("handoff_id", "correlated_handoff_id"),
        ]:
            value = linked.get(src_key)
            if isinstance(value, str) and value.strip():
                result[dst_key] = value

    scope_validation_mode = str(cfg.get("scope_validation_mode") or payload.get("scope_validation_mode") or "lenient").lower()
    scope_validation = validate_scope(
        {
            "mode": scope_validation_mode,
            "workspace_id": result.get("workspace_id"),
            "project_id": result.get("project_id"),
            "policy_scope": result.get("policy_scope"),
            "alias_scope": result.get("alias_scope"),
        }
    )
    result["scope_validation"] = scope_validation.to_dict()
    if scope_validation.action != "pass":
        logger.warning(
            "scope validation observe-only warning action=%s errors=%s warnings=%s",
            scope_validation.action,
            scope_validation.errors,
            scope_validation.warnings,
        )
    try:
        scope_event = build_governance_event(
            event_id=f"scope:{payload.get('message_id') or dedupe.get('dedupe_key')}:{scope_validation.action}",
            event_type="scope_validation_result",
            occurred_at=result["event_time"],
            request_id=result.get("correlated_request_id"),
            publish_id=None,
            workspace_id=str(result.get("workspace_id") or ""),
            project_id=str(result.get("project_id") or ""),
            owner_id=str(payload.get("sender_id") or ""),
            source_module="feishu_message_router",
            source_artifact=source_artifact,
            status=scope_validation.action,
            payload_summary={
                "mode": scope_validation.mode,
                "is_valid": scope_validation.is_valid,
                "errors": len(scope_validation.errors),
                "warnings": len(scope_validation.warnings),
            },
        )
        ingest_governance_event(
            scope_event,
            log_path=governance_event_log_path,
            dedupe_index_path=governance_dedupe_index_path,
        )
        observe_event = build_governance_event(
            event_id=f"router_scope_observe:{payload.get('message_id') or dedupe.get('dedupe_key')}:{scope_validation.action}",
            event_type="router_scope_observe_result",
            occurred_at=result["event_time"],
            request_id=result.get("correlated_request_id"),
            publish_id=None,
            workspace_id=str(result.get("workspace_id") or ""),
            project_id=str(result.get("project_id") or ""),
            owner_id=str(payload.get("sender_id") or ""),
            source_module="feishu_message_router",
            source_artifact=source_artifact,
            status=scope_validation.action,
            payload_summary={"observe_only": True},
        )
        ingest_governance_event(
            observe_event,
            log_path=governance_event_log_path,
            dedupe_index_path=governance_dedupe_index_path,
        )
    except Exception as exc:  # observe-only logging must not break routing
        logger.warning("governance event logging failed in router observe mode: %s", exc)

    if dedupe["already_processed"]:
        result["result_status"] = "deduped"
        result["result_info"] = "event/message already processed; skip re-trigger."
        _write_json(route_result_path, result)
        return result

    if _is_council_artifact_context(linked):
        exec_trigger = extract_execution_trigger(payload)
        if exec_trigger["is_trigger"]:
            if resolved_stage == "execution_dispatch":
                dispatch_result = dispatch_owner_confirmed_execution(
                    handoff_artifact_path=Path(source_artifact),
                    trigger=exec_trigger,
                    confirmed_by=str(payload.get("sender_id") or "feishu_unknown"),
                    confirmed_by_lane=str(exec_trigger.get("requested_by_lane") or "chat"),
                    current_stage=resolved_stage,
                    reason=f"owner confirmed via {exec_trigger.get('keyword')}",
                    dispatch_result_path=council_execution_dispatch_result_path,
                    runtime_status_path=council_execution_runtime_status_path,
                    execution_receipt_path=council_execution_receipt_path,
                    execution_brief_path=council_execution_brief_path,
                )
                result["route_type"] = "council"
                result["routed_entrypoint"] = "owner_confirmed_execution_dispatch"
                result["observe_only"] = False
                result["execution_gate_status"] = "ready" if dispatch_result.get("dispatch_status") == "accepted" else "blocked"
                result["execution_brief_path"] = council_execution_brief_path.as_posix() if council_execution_brief_path.exists() else ""
                result["result_status"] = str(dispatch_result.get("dispatch_status") or "blocked")
                result["result_info"] = (
                    f"dispatch_status={dispatch_result.get('dispatch_status')} | "
                    f"execution_status={dispatch_result.get('execution_status')} | "
                    f"next_action={dispatch_result.get('next_action')} | "
                    f"error={dispatch_result.get('dispatch_error') or 'none'}"
                )
                if dispatch_result.get("dispatch_error"):
                    result["ignored_reason"] = str(dispatch_result.get("dispatch_error"))
                _write_json(route_result_path, result)
                return result

            gate_result = validate_execution_handoff_gate(
                artifact=linked,
                current_stage=resolved_stage,
                trigger=exec_trigger,
            )
            write_execution_handoff_gate_result(gate_result, council_execution_gate_result_path)
            result["route_type"] = "council"
            result["routed_entrypoint"] = "execution_handoff_observer"
            result["observe_only"] = True
            result["execution_gate_status"] = "ready" if gate_result.get("execution_handoff_ready") else "blocked"

            if gate_result.get("execution_handoff_ready"):
                brief = build_execution_brief(linked, gate_result)
                write_execution_brief(brief, council_execution_brief_path)
                result["execution_brief_path"] = council_execution_brief_path.as_posix()
                result["result_status"] = "observed"
                result["result_info"] = _summarize_execution_handoff_observation(
                    trigger_keyword=exec_trigger.get("keyword"),
                    gate_ready=True,
                    blocked_reason="",
                    brief_generated=True,
                )
            else:
                result["result_status"] = "blocked"
                result["ignored_reason"] = str(gate_result.get("blocked_reason") or "")
                result["result_info"] = _summarize_execution_handoff_observation(
                    trigger_keyword=exec_trigger.get("keyword"),
                    gate_ready=False,
                    blocked_reason=result["ignored_reason"],
                    brief_generated=False,
                )
            _write_json(route_result_path, result)
            return result

        confirm_allowed, confirm_keyword = _extract_council_confirm_signal(payload)
        if confirm_keyword is not None:
            if not confirm_allowed:
                result["route_type"] = "council"
                result["routed_entrypoint"] = "council_owner_confirmed_apply"
                result["observe_only"] = True
                result["mapping_status"] = "not_applicable"
                result["validation_status"] = "not_applicable"
                result["result_status"] = "ignored"
                result["ignored_reason"] = "confirm keyword detected but source is not owner/bridge protocol."
                result["result_info"] = (
                    "confirm signal ignored: plain chat text cannot confirm apply; "
                    "use owner action protocol signal."
                )
                _write_json(route_result_path, result)
                return result

            apply_receipt = apply_owner_confirmed_transition(
                source_artifact_path=Path(source_artifact),
                mapping_result_path=council_mapping_result_path,
                validation_result_path=council_transition_result_path,
                confirmed_by=str(payload.get("sender_id") or "feishu_unknown"),
                confirmed_by_lane="owner",
                reason=f"owner confirmed via {confirm_keyword}",
                output_path=council_owner_apply_result_path,
                observe_only_source=route_result_path.as_posix(),
                current_stage=resolved_stage,
            )
            result["route_type"] = "council"
            result["routed_entrypoint"] = "council_owner_confirmed_apply"
            result["observe_only"] = False
            result["mapping_status"] = "mapped" if apply_receipt.get("apply_status") == "applied" else "blocked"
            result["validation_status"] = "applied" if apply_receipt.get("apply_status") == "applied" else "blocked"
            result["suggested_transition_summary"] = str(apply_receipt.get("applied_transition") or "none")
            result["result_status"] = str(apply_receipt.get("apply_status") or "blocked")
            result["result_info"] = (
                f"owner_confirmed_apply={apply_receipt.get('apply_status')} | "
                f"transition={apply_receipt.get('applied_transition') or 'none'} | "
                f"before={apply_receipt.get('before_status')} | after={apply_receipt.get('after_status')} | "
                f"error={apply_receipt.get('apply_error') or 'none'}"
            )
            result["ignored_reason"] = ""
            _write_json(route_result_path, result)
            return result

        mapping_input = {
            "source": payload.get("source"),
            "message_id": payload.get("message_id"),
            "chat_id": payload.get("chat_id"),
            "sender_id": payload.get("sender_id"),
            "sender_name": payload.get("sender_name"),
            "text": payload.get("text"),
            "current_stage": resolved_stage,
            "current_artifact_id": result.get("correlated_handoff_id") or linked.get("artifact_id"),
            "current_artifact_type": linked.get("artifact_type"),
            "current_artifact_status": linked.get("status"),
            "current_request_id": result.get("correlated_request_id"),
            "current_brief_id": result.get("correlated_brief_id"),
            "current_handoff_id": result.get("correlated_handoff_id"),
            "workspace_id": result.get("workspace_id"),
            "project_id": result.get("project_id"),
            "policy_scope": result.get("policy_scope"),
            "alias_scope": result.get("alias_scope"),
        }

        role_confirm_allowed, role_confirm_keyword = _extract_role_rework_confirm_signal(payload)
        if role_confirm_keyword is not None:
            if not role_confirm_allowed:
                result["route_type"] = "council"
                result["routed_entrypoint"] = "council_role_rework_apply"
                result["observe_only"] = True
                result["result_status"] = "ignored"
                result["ignored_reason"] = "role rework confirm keyword detected but source is not owner/bridge protocol."
                result["result_info"] = "confirm ignored: plain chat text cannot apply role rework."
                _write_json(route_result_path, result)
                return result

            apply_receipt = apply_owner_confirmed_role_rework(
                source_artifact_path=Path(source_artifact),
                mapping_result_path=council_role_rework_mapping_result_path,
                validation_result_path=council_role_rework_transition_result_path,
                confirmed_by=str(payload.get("sender_id") or "feishu_unknown"),
                confirmed_by_lane="owner",
                reason=f"owner confirmed role rework via {role_confirm_keyword}",
                output_path=council_role_rework_apply_result_path,
                advisory_artifact_path=council_role_rework_advisory_path,
            )
            result["route_type"] = "council"
            result["routed_entrypoint"] = "council_role_rework_apply"
            result["observe_only"] = False
            result["mapping_status"] = "mapped" if apply_receipt.get("apply_status") == "applied" else "blocked"
            result["validation_status"] = "applied" if apply_receipt.get("apply_status") == "applied" else "blocked"
            result["suggested_transition_summary"] = f"role_rework->{apply_receipt.get('target_role') or 'unknown'}"
            result["result_status"] = str(apply_receipt.get("apply_status") or "blocked")
            result["result_info"] = (
                f"role_rework_apply={apply_receipt.get('apply_status')} | "
                f"target_role={apply_receipt.get('target_role') or 'n/a'} | "
                f"before={apply_receipt.get('before_status')} | after={apply_receipt.get('after_status')} | "
                f"advisory={apply_receipt.get('advisory_artifact_id') or 'none'} | "
                f"error={apply_receipt.get('apply_error') or 'none'}"
            )
            if apply_receipt.get("apply_error"):
                result["ignored_reason"] = str(apply_receipt.get("apply_error"))
            _write_json(route_result_path, result)
            return result

        role_mapping = map_role_rework_hint(mapping_input, artifact_context=linked)
        if role_mapping.is_mapped:
            write_role_rework_mapping_result(role_mapping, council_role_rework_mapping_result_path)
            result["route_type"] = "council"
            result["routed_entrypoint"] = "council_role_rework_observer"
            result["observe_only"] = True
            result["mapping_status"] = "mapped"

            transition_summary = "none"
            validation_status = "skipped_no_transition"
            validation_errors: list[str] = []
            if role_mapping.suggested_transition_request:
                transition = TransitionRequest.from_dict(role_mapping.suggested_transition_request)
                validation = validate_transition(linked, transition)
                write_transition_audit(validation, council_role_rework_transition_result_path)
                validation_status = "valid" if validation.is_valid else "invalid"
                validation_errors = validation.validation_errors
                transition_summary = f"{transition.current_status}->{transition.target_status}"

            result["validation_status"] = validation_status
            result["suggested_transition_summary"] = f"target_role={role_mapping.target_role}; transition={transition_summary}"
            result["result_status"] = "observed"
            result["result_info"] = (
                f"role_rework_hint=matched | target_role={role_mapping.target_role} | "
                f"suggested_transition={transition_summary} | validation={validation_status} | "
                "observe_only=true (no state change applied)"
            )
            if validation_errors:
                result["result_info"] += f" | errors={'; '.join(validation_errors[:2])}"
            _write_json(route_result_path, result)
            return result

        mapping_result = map_feishu_feedback(mapping_input, artifact_context=linked)
        write_mapping_result(mapping_result, council_mapping_result_path)

        result["route_type"] = "council"
        result["routed_entrypoint"] = "council_feedback_observer"
        result["observe_only"] = True
        result["mapping_status"] = "mapped" if mapping_result.is_mapped else "ignored"
        result["ignored_reason"] = mapping_result.ignored_reason or ""

        transition_summary = "none"
        validation_status = "skipped"
        validation_errors: list[str] = []
        if mapping_result.suggested_transition_request:
            transition = TransitionRequest.from_dict(mapping_result.suggested_transition_request)
            validation = validate_transition(linked, transition)
            write_transition_audit(validation, council_transition_result_path)
            validation_status = "valid" if validation.is_valid else "invalid"
            validation_errors = validation.validation_errors
            transition_summary = f"{transition.current_status}->{transition.target_status}"
        else:
            validation_status = "skipped_no_transition"

        result["validation_status"] = validation_status
        result["suggested_transition_summary"] = transition_summary
        result["result_status"] = "observed"
        result["result_info"] = _summarize_council_observation(
            mapping_type=mapping_result.mapping_type,
            feedback_type=mapping_result.feedback_type,
            target_section=mapping_result.target_section,
            transition_summary=transition_summary,
            validation_status=validation_status,
            validation_errors=validation_errors,
        )
        _write_json(route_result_path, result)
        return result

    if action is None:
        # chat lane
        if not bool(cfg.get("chat_lane_enabled", True)):
            result["ignored_reason"] = "chat lane disabled by configuration."
            result["result_info"] = result["ignored_reason"]
            _write_json(route_result_path, result)
            return result

        only_groups = cfg.get("chat_lane_only_groups", [])
        blocked_groups = cfg.get("chat_lane_blocked_groups", [])
        if isinstance(only_groups, list) and only_groups and payload["chat_id"] not in only_groups:
            result["ignored_reason"] = "chat lane blocked: chat not in allow-list."
            result["result_info"] = result["ignored_reason"]
            _write_json(route_result_path, result)
            return result
        if isinstance(blocked_groups, list) and payload["chat_id"] in blocked_groups:
            result["ignored_reason"] = "chat lane blocked: chat in block-list."
            result["result_info"] = result["ignored_reason"]
            _write_json(route_result_path, result)
            return result

        require_mention = bool(cfg.get("chat_lane_require_mention", False))
        mention_tokens = cfg.get("chat_lane_mention_tokens", ["@bot", "@机器人", "@AgentCommerce", "@bridge"])
        if require_mention and isinstance(mention_tokens, list):
            if not _is_chat_mention_valid(payload["text"], [str(x) for x in mention_tokens]):
                result["ignored_reason"] = "chat message ignored: bot mention required."
                result["result_info"] = result["ignored_reason"]
                _write_json(route_result_path, result)
                return result

        task_payload = {
            "route_type": "chat",
            "source": payload["source"],
            "message_payload": payload,
            "source_artifact": source_artifact,
            "correlated_request_id": result["correlated_request_id"],
            "correlated_brief_id": result["correlated_brief_id"],
            "correlated_handoff_id": result["correlated_handoff_id"],
        }
        task_id = enqueue_task(task_payload, db_path=queue_db_path, route_type="chat")
        result["route_type"] = "chat"
        result["routed_entrypoint"] = "chat_bridge_queue"
        result["task_id"] = task_id
        result["result_status"] = "queued"
        result["result_info"] = "free text queued for chat bridge worker."
        _write_json(route_result_path, result)
        return result

    # action lane
    owner_id = str(payload.get("sender_id") or "feishu_unknown")
    notes = f"feishu_{payload.get('source')} message_id={payload.get('message_id')} keyword={action}"
    command: list[str] | None = None

    if resolved_stage == "dispatch_ready":
        if action in DISPATCH_READY_ACTIONS:
            command = build_continue_once_command(
                source_artifact=source_artifact,
                action=action,
                owner_id=owner_id,
                notes=notes,
                check_completion_once=check_completion_once,
                build_receipt_skeleton=build_receipt_skeleton,
            )
            result["routed_entrypoint"] = "feishu_continue_once"
        else:
            result["ignored_reason"] = f"action '{action}' is not valid for stage '{resolved_stage}'. valid={allowed}"
    elif resolved_stage == "review_ready":
        if action in REVIEW_READY_ACTIONS:
            command = build_final_review_once_command(
                final_decision=action,
                source_artifact=source_artifact,
                owner_id=owner_id,
                matched_keyword=action,
                notes=notes,
            )
            result["routed_entrypoint"] = "final_review_once"
        else:
            result["ignored_reason"] = f"action '{action}' is not valid for stage '{resolved_stage}'. valid={allowed}"
    else:
        result["ignored_reason"] = f"stage '{resolved_stage}' does not accept action routing."

    if command is None:
        result["route_type"] = "ignored"
        result["result_status"] = "ignored"
        result["result_info"] = result["ignored_reason"] or "not routed"
        _write_json(route_result_path, result)
        return result

    result["route_type"] = "action"
    result["triggered_command"] = " ".join(command)
    status, info = runner(command)
    result["result_status"] = status
    result["result_info"] = info
    _write_json(route_result_path, result)
    return result
