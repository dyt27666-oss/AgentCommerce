"""Role-targeted rework mapping adapter v0.1.

Maps owner feedback text into role-specific rework hints and transition suggestions.
This adapter is observe-first and does not apply transitions directly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.owner_intent_normalization import normalize_owner_intent

DEFAULT_OUTPUT_PATH = Path("artifacts") / "council_role_rework_mapping_result.json"


@dataclass(slots=True)
class RoleReworkMappingResult:
    is_mapped: bool
    mapping_type: str
    target_role: str | None
    mapping_confidence: float
    owner_feedback: dict[str, Any] | None
    suggested_transition_request: dict[str, Any] | None
    ambiguity_flags: list[str] = field(default_factory=list)
    ignored_reason: str | None = None
    suggested_next_action: str = ""
    dictionary_version: str | None = None
    policy_version: str | None = None
    policy_scope: str | None = None
    alias_scope: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe(v: Any) -> str:
    return str(v or "").strip()


def map_role_rework_hint(raw_payload: dict[str, Any], artifact_context: dict[str, Any] | None = None) -> RoleReworkMappingResult:
    artifact_context = artifact_context or {}
    text = _safe(raw_payload.get("text"))
    source = _safe(raw_payload.get("source"))

    normalized = normalize_owner_intent(
        text,
        owner_id=_safe(raw_payload.get("sender_id")),
        group_id=_safe(raw_payload.get("chat_id")),
        workspace_id=_safe(raw_payload.get("workspace_id") or artifact_context.get("workspace_id")),
        project_id=_safe(raw_payload.get("project_id") or artifact_context.get("project_id")),
    )
    target_role = normalized.target_role
    action = normalized.requested_action

    if normalized.intent_type != "role_rework" or not target_role:
        return RoleReworkMappingResult(
            is_mapped=False,
            mapping_type="ignored",
            target_role=target_role,
            mapping_confidence=normalized.confidence,
            owner_feedback=None,
            suggested_transition_request=None,
            ambiguity_flags=sorted(set(list(normalized.ambiguity_flags) + ["not_role_rework_intent"])),
            ignored_reason=normalized.ignored_reason or "message did not normalize to role_rework intent",
            suggested_next_action="fall back to general council feedback mapping",
            dictionary_version=normalized.alias_version,
            policy_version=normalized.policy_version,
            policy_scope=normalized.policy_scope,
            alias_scope=normalized.alias_scope,
            workspace_id=normalized.workspace_id,
            project_id=normalized.project_id,
            timestamp=_now_iso(),
        )

    artifact_id = _safe(raw_payload.get("current_artifact_id") or artifact_context.get("artifact_id"))
    artifact_type = _safe(raw_payload.get("current_artifact_type") or artifact_context.get("artifact_type"))
    current_status = _safe(raw_payload.get("current_artifact_status") or artifact_context.get("status"))
    request_id = _safe(raw_payload.get("current_request_id") or artifact_context.get("request_id"))
    brief_id = _safe(raw_payload.get("current_brief_id") or artifact_context.get("brief_id"))
    handoff_id = _safe(raw_payload.get("current_handoff_id") or artifact_context.get("handoff_id"))
    message_id = _safe(raw_payload.get("message_id")) or f"msg-{int(datetime.now().timestamp())}"

    missing_context = []
    for key, value in [
        ("current_artifact_id", artifact_id),
        ("current_artifact_type", artifact_type),
        ("current_artifact_status", current_status),
    ]:
        if not value:
            missing_context.append(key)

    if missing_context:
        return RoleReworkMappingResult(
            is_mapped=False,
            mapping_type="role_rework_hint",
            target_role=target_role,
            mapping_confidence=0.35,
            owner_feedback=None,
            suggested_transition_request=None,
            ambiguity_flags=["required_context_missing"],
            ignored_reason=f"missing context: {', '.join(missing_context)}",
            suggested_next_action="hydrate artifact context then retry mapping",
            dictionary_version=normalized.alias_version,
            policy_version=normalized.policy_version,
            policy_scope=normalized.policy_scope,
            alias_scope=normalized.alias_scope,
            workspace_id=normalized.workspace_id,
            project_id=normalized.project_id,
            timestamp=_now_iso(),
        )

    target_status = "needs_fix" if current_status != "needs_fix" else "revised"
    owner_feedback = {
        "feedback_id": f"fb-role-rework-{message_id}",
        "feedback_source": source or "feishu_message",
        "feedback_text": text,
        "feedback_type": "revision_request",
        "target_artifact_id": artifact_id,
        "target_section": f"role:{target_role}",
        "severity": normalized.severity or "medium",
        "requested_change": normalized.requested_change or f"rerun role {target_role}",
        "resolved_status": "open",
        "resolved_by_artifact_id": None,
    }

    requested_by_lane = "owner" if any(x in source.lower() for x in ["action_protocol", "owner_action", "bridge"]) else "chat"

    transition = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "current_status": current_status,
        "target_status": target_status,
        "requested_by": _safe(raw_payload.get("sender_id")) or "feishu_unknown",
        "requested_by_lane": requested_by_lane,
        "reason": f"role rework requested for {target_role} via action={action or 'unspecified'}",
        "triggering_feedback_id": owner_feedback["feedback_id"],
        "triggering_artifact_id": artifact_id,
        "correlated_request_id": request_id or None,
        "correlated_brief_id": brief_id or None,
        "correlated_handoff_id": handoff_id or None,
    }

    return RoleReworkMappingResult(
        is_mapped=True,
        mapping_type="role_rework_hint",
        target_role=target_role,
        mapping_confidence=normalized.confidence,
        owner_feedback=owner_feedback,
        suggested_transition_request=transition,
        ambiguity_flags=normalized.ambiguity_flags,
        ignored_reason=None,
        suggested_next_action="observe validator result; owner confirm required before apply",
        dictionary_version=normalized.alias_version,
        policy_version=normalized.policy_version,
        policy_scope=normalized.policy_scope,
        alias_scope=normalized.alias_scope,
        workspace_id=normalized.workspace_id,
        project_id=normalized.project_id,
        timestamp=_now_iso(),
    )


def write_role_rework_mapping_result(result: RoleReworkMappingResult, path: Path = DEFAULT_OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
