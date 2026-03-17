"""Feishu feedback -> owner_feedback + TransitionRequest mapping adapter v0.1.

This adapter translates messages into structured artifacts and suggested transitions.
Authorization is handled by governance/state-machine layers, not by this adapter.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.owner_intent_normalization import normalize_owner_intent

OUTPUT_PATH = Path("artifacts") / "council_feishu_feedback_mapping_result.json"

ACTION_KEYWORDS = {
    "needs_fix": "needs_fix",
    "revision_request": "revision_request",
    "rejected": "reject",
    "reject": "reject",
    "approved": "approval_note",
}
OWNER_SIGNAL_LANES = {"owner", "bridge"}


@dataclass(slots=True)
class FeedbackMappingResult:
    is_mapped: bool
    mapping_type: str
    owner_feedback: dict[str, Any] | None
    suggested_transition_request: dict[str, Any] | None
    target_artifact_id: str | None
    target_section: str | None
    feedback_type: str | None
    requested_change: str | None
    severity: str | None
    confidence: float
    ambiguity_flags: list[str] = field(default_factory=list)
    required_context_missing: list[str] = field(default_factory=list)
    ignored_reason: str | None = None
    suggested_next_action: str = ""
    message_id: str | None = None
    sender_id: str | None = None
    text: str | None = None
    correlated_artifact_id: str | None = None
    correlated_request_id: str | None = None
    correlated_brief_id: str | None = None
    correlated_handoff_id: str | None = None
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


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_payload(raw: dict[str, Any], artifact_context: dict[str, Any] | None = None) -> dict[str, Any]:
    artifact_context = artifact_context or {}
    return {
        "source": _safe_str(raw.get("source") or "unknown"),
        "message_id": _safe_str(raw.get("message_id")),
        "chat_id": _safe_str(raw.get("chat_id")),
        "sender_id": _safe_str(raw.get("sender_id")),
        "sender_name": _safe_str(raw.get("sender_name")),
        "text": _safe_str(raw.get("text")),
        "current_stage": _safe_str(raw.get("current_stage")),
        "current_artifact_id": _safe_str(raw.get("current_artifact_id") or artifact_context.get("artifact_id")),
        "current_artifact_type": _safe_str(raw.get("current_artifact_type") or artifact_context.get("artifact_type")),
        "current_artifact_status": _safe_str(raw.get("current_artifact_status") or artifact_context.get("status")),
        "current_request_id": _safe_str(raw.get("current_request_id") or artifact_context.get("request_id")),
        "current_brief_id": _safe_str(raw.get("current_brief_id") or artifact_context.get("brief_id")),
        "current_handoff_id": _safe_str(raw.get("current_handoff_id") or artifact_context.get("handoff_id")),
        "workspace_id": _safe_str(raw.get("workspace_id") or artifact_context.get("workspace_id")),
        "project_id": _safe_str(raw.get("project_id") or artifact_context.get("project_id")),
        "policy_scope": _safe_str(raw.get("policy_scope") or artifact_context.get("policy_scope")),
        "alias_scope": _safe_str(raw.get("alias_scope") or artifact_context.get("alias_scope")),
    }


def _detect_action_keyword(text: str) -> str | None:
    lowered = text.lower()
    for keyword in ACTION_KEYWORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", lowered):
            return keyword
    return None


def _infer_requested_by_lane(source: str) -> str:
    lowered = source.lower()
    if "action_protocol" in lowered or "owner_action" in lowered or "bridge" in lowered:
        return "owner"
    return "chat"


def _infer_feedback_type(
    *,
    action_keyword: str | None,
    normalized_action: str | None,
    normalized_intent_type: str,
) -> str:
    if action_keyword:
        return ACTION_KEYWORDS[action_keyword]
    if normalized_action in {"recheck", "rewrite", "redo", "refine", "tighten", "clarify"}:
        return "needs_fix"
    if normalized_action == "resubmit":
        return "revision_request"
    if normalized_action == "summarize":
        return "comment"
    if normalized_intent_type == "section_feedback":
        return "needs_fix"
    return "comment"


def _infer_target_status(
    *,
    current_status: str,
    feedback_type: str,
    requested_by_lane: str,
    action_keyword: str | None,
    normalized_action: str | None,
) -> tuple[str | None, list[str]]:
    flags: list[str] = []

    if feedback_type in {"needs_fix", "revision_request"}:
        if normalized_action == "resubmit":
            if current_status == "revised":
                return "resubmitted", flags
            if current_status == "resubmitted":
                return "ready_for_owner_review", flags
            flags.append("resubmit_intent_without_revised_status")
            return "ready_for_owner_review", flags
        return "needs_fix", flags

    if feedback_type == "reject":
        if current_status == "ready_for_owner_review" and requested_by_lane in OWNER_SIGNAL_LANES:
            return "owner_rejected", flags
        flags.append("reject_without_owner_review_context")
        return "needs_fix", flags

    if feedback_type == "approval_note":
        if action_keyword == "approved":
            if current_status == "ready_for_owner_review" and requested_by_lane in OWNER_SIGNAL_LANES:
                return "owner_approved", flags
            flags.append("approval_requires_owner_protocol_and_ready_for_owner_review")
            return None, flags

    return None, flags


def _build_owner_feedback(payload: dict[str, Any], *, feedback_type: str, target_section: str | None, severity: str | None) -> dict[str, Any]:
    message_id = payload["message_id"] or f"msg-{int(datetime.now().timestamp())}"
    feedback_id = f"fb-{message_id}"
    return {
        "feedback_id": feedback_id,
        "feedback_source": payload["source"] or "feishu_message",
        "feedback_text": payload["text"],
        "feedback_type": feedback_type,
        "target_artifact_id": payload["current_artifact_id"],
        "target_section": target_section or "unspecified",
        "severity": severity or "medium",
        "requested_change": payload["text"],
        "resolved_status": "open",
        "resolved_by_artifact_id": None,
    }


def _build_transition_request(
    payload: dict[str, Any],
    *,
    target_status: str,
    requested_by_lane: str,
    triggering_feedback_id: str | None,
) -> dict[str, Any]:
    return {
        "artifact_id": payload["current_artifact_id"],
        "artifact_type": payload["current_artifact_type"],
        "current_status": payload["current_artifact_status"],
        "target_status": target_status,
        "requested_by": payload["sender_id"] or "feishu_unknown",
        "requested_by_lane": requested_by_lane,
        "reason": f"mapped from feishu message {payload['message_id']}",
        "triggering_feedback_id": triggering_feedback_id,
        "triggering_artifact_id": None,
        "correlated_request_id": payload["current_request_id"] or None,
        "correlated_brief_id": payload["current_brief_id"] or None,
        "correlated_handoff_id": payload["current_handoff_id"] or None,
    }


def map_feishu_feedback(raw_payload: dict[str, Any], *, artifact_context: dict[str, Any] | None = None) -> FeedbackMappingResult:
    payload = _normalize_payload(raw_payload, artifact_context)
    text = payload["text"]

    missing_context = [
        key
        for key in [
            "current_artifact_id",
            "current_artifact_type",
            "current_artifact_status",
            "current_request_id",
            "current_brief_id",
        ]
        if not payload[key]
    ]

    action_keyword = _detect_action_keyword(text)
    normalized = normalize_owner_intent(
        text,
        owner_id=payload["sender_id"],
        group_id=payload["chat_id"],
        workspace_id=payload["workspace_id"],
        project_id=payload["project_id"],
    )
    requested_by_lane = _infer_requested_by_lane(payload["source"])

    feedback_type = _infer_feedback_type(
        action_keyword=action_keyword,
        normalized_action=normalized.requested_action,
        normalized_intent_type=normalized.intent_type,
    )
    target_status, status_flags = _infer_target_status(
        current_status=payload["current_artifact_status"],
        feedback_type=feedback_type,
        requested_by_lane=requested_by_lane,
        action_keyword=action_keyword,
        normalized_action=normalized.requested_action,
    )

    mapping_type = "action_keyword" if action_keyword else "natural_language"
    ambiguity_flags = sorted(set(list(normalized.ambiguity_flags) + status_flags))
    if any(token in text for token in ["行吧", "ok", "okay"]):
        ambiguity_flags.append("ambiguous_acknowledgement")

    if feedback_type == "approval_note" and requested_by_lane == "chat":
        ambiguity_flags.append("approval_from_chat_lane_not_authoritative")
        target_status = None

    is_mapped = True
    ignored_reason = normalized.ignored_reason
    if missing_context:
        is_mapped = False
        ambiguity_flags.append("required_context_missing")
        ignored_reason = ignored_reason or "required artifact context missing for structured mapping"

    owner_feedback: dict[str, Any] | None = None
    transition_request: dict[str, Any] | None = None
    if is_mapped:
        owner_feedback = _build_owner_feedback(
            payload,
            feedback_type=feedback_type,
            target_section=normalized.target_section,
            severity=normalized.severity,
        )
        if target_status:
            transition_request = _build_transition_request(
                payload,
                target_status=target_status,
                requested_by_lane=requested_by_lane,
                triggering_feedback_id=owner_feedback["feedback_id"],
            )

    suggested_next_action = "run council_artifact_state_machine.validate_transition on suggested transition"
    if not is_mapped:
        suggested_next_action = "collect missing context or ask owner to provide clearer feedback"
    elif transition_request is None:
        suggested_next_action = "record owner_feedback as comment and keep current status"

    return FeedbackMappingResult(
        is_mapped=is_mapped,
        mapping_type=mapping_type,
        owner_feedback=owner_feedback,
        suggested_transition_request=transition_request,
        target_artifact_id=payload["current_artifact_id"] or None,
        target_section=normalized.target_section,
        feedback_type=feedback_type,
        requested_change=normalized.requested_change or text or None,
        severity=normalized.severity,
        confidence=normalized.confidence,
        ambiguity_flags=sorted(set(ambiguity_flags)),
        required_context_missing=missing_context,
        ignored_reason=ignored_reason,
        suggested_next_action=suggested_next_action,
        message_id=payload["message_id"] or None,
        sender_id=payload["sender_id"] or None,
        text=payload["text"] or None,
        correlated_artifact_id=payload["current_artifact_id"] or None,
        correlated_request_id=payload["current_request_id"] or None,
        correlated_brief_id=payload["current_brief_id"] or None,
        correlated_handoff_id=payload["current_handoff_id"] or None,
        dictionary_version=normalized.alias_version,
        policy_version=normalized.policy_version,
        policy_scope=payload["policy_scope"] or normalized.policy_scope,
        alias_scope=payload["alias_scope"] or normalized.alias_scope,
        workspace_id=payload["workspace_id"] or normalized.workspace_id,
        project_id=payload["project_id"] or normalized.project_id,
        timestamp=_now_iso(),
    )


def write_mapping_result(result: FeedbackMappingResult, output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Map Feishu feedback to owner_feedback + TransitionRequest (v0.1).")
    parser.add_argument("--message", required=True, help="Path to Feishu message payload JSON.")
    parser.add_argument("--artifact", default="", help="Optional path to current artifact JSON for context.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output mapping result artifact path.")
    args = parser.parse_args()

    message = _load_json(Path(args.message))
    artifact_context = _load_json(Path(args.artifact)) if args.artifact else None
    result = map_feishu_feedback(message, artifact_context=artifact_context)
    write_mapping_result(result, Path(args.output))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
