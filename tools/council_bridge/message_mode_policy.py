"""Message mode decision policy for Feishu/Codex control chain."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MODE_CHAT = "chat"
MODE_WORKFLOW_REQUEST = "workflow_request"
MODE_OWNER_ACTION = "owner_action"
MODE_SYSTEM_CONTROL = "system_control"

WORKFLOW_REQUEST_KEYWORDS = (
    "请开始执行",
    "开始执行",
    "执行一下",
    "运行测试",
    "run tests",
    "execute",
    "start workflow",
)

SYSTEM_CONTROL_KEYWORDS = (
    "允许本地权限",
    "仅允许读",
    "允许修改仓库文件",
    "允许修改并执行本地测试",
    "允许访问联网能力",
    "禁止 destructive",
    "mode:",
)


@dataclass(slots=True)
class ModeDecision:
    detected_mode: str
    detection_reason: str
    confidence: float
    rule_hit: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def decide_message_mode(
    *,
    text: str,
    source: str,
    detected_action: str | None,
    execution_trigger_detected: bool,
    council_confirm_keyword: str | None,
    role_rework_confirm_keyword: str | None,
) -> ModeDecision:
    normalized_text = str(text or "").strip()
    normalized_source = str(source or "").lower()

    if _contains_any(normalized_text, SYSTEM_CONTROL_KEYWORDS):
        return ModeDecision(
            detected_mode=MODE_SYSTEM_CONTROL,
            detection_reason="Message contains explicit mode/permission control statement.",
            confidence=0.95,
            rule_hit="system_control_permission_statement",
        )

    if council_confirm_keyword or role_rework_confirm_keyword:
        return ModeDecision(
            detected_mode=MODE_OWNER_ACTION,
            detection_reason="Owner confirm keyword is present; this is owner approval channel.",
            confidence=0.98,
            rule_hit="owner_action_confirm_signal",
        )

    if detected_action and ("action_protocol" in normalized_source or "owner_action" in normalized_source):
        return ModeDecision(
            detected_mode=MODE_OWNER_ACTION,
            detection_reason="Action keyword detected in owner/action protocol source.",
            confidence=0.92,
            rule_hit="owner_action_protocol_source",
        )

    if execution_trigger_detected or detected_action is not None:
        return ModeDecision(
            detected_mode=MODE_WORKFLOW_REQUEST,
            detection_reason="Execution/action keyword detected and requires workflow handling.",
            confidence=0.88,
            rule_hit="workflow_request_action_keyword",
        )

    if _contains_any(normalized_text, WORKFLOW_REQUEST_KEYWORDS):
        return ModeDecision(
            detected_mode=MODE_WORKFLOW_REQUEST,
            detection_reason="Explicit execution intent found in free-text request.",
            confidence=0.82,
            rule_hit="workflow_request_intent_keyword",
        )

    return ModeDecision(
        detected_mode=MODE_CHAT,
        detection_reason="No action/approval/control signal detected; fallback to chat mode.",
        confidence=0.8,
        rule_hit="chat_fallback",
    )

