"""Minimal permission policy for Codex-Feishu bridge actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


LEVEL_READ_ONLY = "read_only"
LEVEL_SAFE_WRITE = "safe_write"
LEVEL_LOCAL_EXECUTION = "local_execution"
LEVEL_EXTERNAL_NETWORK = "external_network"
LEVEL_DESTRUCTIVE_ACTION = "destructive_action"

_LEVEL_RANK = {
    LEVEL_READ_ONLY: 0,
    LEVEL_SAFE_WRITE: 1,
    LEVEL_LOCAL_EXECUTION: 2,
    LEVEL_EXTERNAL_NETWORK: 3,
    LEVEL_DESTRUCTIVE_ACTION: 4,
}

_DEFAULT_GRANT_PHRASE = {
    LEVEL_SAFE_WRITE: "允许修改仓库文件但不要运行",
    LEVEL_LOCAL_EXECUTION: "允许修改并执行本地测试",
    LEVEL_EXTERNAL_NETWORK: "允许访问联网能力",
    LEVEL_DESTRUCTIVE_ACTION: "允许 destructive 操作（仅本次）",
}


@dataclass(slots=True)
class PermissionDecision:
    requested_permission_level: str
    granted_permission_level: str
    permission_source: str
    confirmation_required: bool
    missing_permission_reason: str
    recommended_grant_phrase: str
    destructive_action_detected: bool
    destructive_matches: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _max_level(a: str, b: str) -> str:
    return a if _LEVEL_RANK[a] >= _LEVEL_RANK[b] else b


def _contains(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _detect_requested_level(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    destructive_markers = [
        marker
        for marker in (
            "git reset --hard",
            "rewrite history",
            "删除大量文件",
            "覆盖关键配置",
            "修改系统级配置",
            "不可逆",
        )
        if marker.lower() in lowered
    ]
    if destructive_markers:
        return LEVEL_DESTRUCTIVE_ACTION, destructive_markers
    if _contains(lowered, ("联网", "web search", "curl ", "wget ", "访问外网", "browser")):
        return LEVEL_EXTERNAL_NETWORK, []
    if _contains(lowered, ("运行测试", "run tests", "执行命令", "本地执行", "tasklist", "process")):
        return LEVEL_LOCAL_EXECUTION, []
    if _contains(lowered, ("修改", "patch", "重构", "写入文件", "update code")):
        return LEVEL_SAFE_WRITE, []
    return LEVEL_READ_ONLY, []


def _detect_explicit_grant_level(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if _contains(lowered, ("仅允许读", "只读", "read only")):
        return LEVEL_READ_ONLY, "prompt_explicit_grant"
    if _contains(lowered, ("允许修改仓库文件但不要运行", "allow safe write")):
        return LEVEL_SAFE_WRITE, "prompt_explicit_grant"
    if _contains(lowered, ("允许修改并执行本地测试", "可以直接修改并运行", "允许本地权限：", "查:")):
        return LEVEL_LOCAL_EXECUTION, "prompt_explicit_grant"
    if _contains(lowered, ("允许访问联网能力", "可以联网", "allow network")):
        return LEVEL_EXTERNAL_NETWORK, "prompt_explicit_grant"
    if _contains(lowered, ("允许 destructive 操作", "allow destructive")):
        return LEVEL_DESTRUCTIVE_ACTION, "prompt_explicit_grant"
    return LEVEL_READ_ONLY, "default_read_only"


def evaluate_permission_context(text: str, *, session_grant_level: str | None = None) -> PermissionDecision:
    requested_level, destructive_matches = _detect_requested_level(str(text or ""))
    explicit_level, explicit_source = _detect_explicit_grant_level(str(text or ""))

    granted_level = explicit_level
    permission_source = explicit_source
    if session_grant_level in _LEVEL_RANK:
        granted_level = _max_level(granted_level, session_grant_level)
        if _LEVEL_RANK[session_grant_level] > _LEVEL_RANK[explicit_level]:
            permission_source = "session_level_grant"

    if requested_level == LEVEL_DESTRUCTIVE_ACTION and granted_level != LEVEL_DESTRUCTIVE_ACTION:
        return PermissionDecision(
            requested_permission_level=requested_level,
            granted_permission_level=granted_level,
            permission_source=permission_source,
            confirmation_required=True,
            missing_permission_reason="Destructive action is denied by default and needs explicit one-time authorization.",
            recommended_grant_phrase=_DEFAULT_GRANT_PHRASE[LEVEL_DESTRUCTIVE_ACTION],
            destructive_action_detected=True,
            destructive_matches=destructive_matches,
        )

    needs_confirmation = _LEVEL_RANK[requested_level] > _LEVEL_RANK[granted_level]
    missing_reason = ""
    recommended_phrase = ""
    if needs_confirmation:
        missing_reason = f"Requested {requested_level} but granted {granted_level}."
        recommended_phrase = _DEFAULT_GRANT_PHRASE.get(requested_level, _DEFAULT_GRANT_PHRASE[LEVEL_SAFE_WRITE])

    return PermissionDecision(
        requested_permission_level=requested_level,
        granted_permission_level=granted_level,
        permission_source=permission_source,
        confirmation_required=needs_confirmation,
        missing_permission_reason=missing_reason,
        recommended_grant_phrase=recommended_phrase,
        destructive_action_detected=bool(destructive_matches),
        destructive_matches=destructive_matches,
    )

