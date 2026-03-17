"""Bridge runtime config adapter on top of policy configuration center."""

from __future__ import annotations

from typing import Any

from tools.council_bridge.policy_config_center import resolve_policy_config

def ensure_default_configs() -> None:
    # Kept for backward compatibility with existing callers.
    resolve_policy_config()


def resolve_runtime_config(
    *,
    owner_id: str,
    chat_id: str,
    workspace_id: str = "",
    project_id: str = "",
) -> dict[str, Any]:
    ensure_default_configs()
    cfg = resolve_policy_config(
        owner_id=owner_id,
        group_id=chat_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    lane = cfg.get("lane_switches") if isinstance(cfg.get("lane_switches"), dict) else {}
    result: dict[str, Any] = {
        "chat_lane_enabled": bool(lane.get("chat_lane_enabled", True)),
        "chat_lane_require_mention": bool(lane.get("chat_lane_require_mention", False)),
        "chat_lane_only_groups": list(lane.get("chat_lane_only_groups", [])) if isinstance(lane.get("chat_lane_only_groups"), list) else [],
        "chat_lane_blocked_groups": list(lane.get("chat_lane_blocked_groups", [])) if isinstance(lane.get("chat_lane_blocked_groups"), list) else [],
        "policy_version": str(cfg.get("policy_version") or "policy.center.v0.1"),
        "policy_scope": str(cfg.get("policy_scope") or "default"),
        "alias_scope": str(cfg.get("alias_scope") or "default"),
        "workspace_id": cfg.get("workspace_id"),
        "project_id": cfg.get("project_id"),
        "active_alias_version": str(cfg.get("active_alias_version") or "owner.intent.alias.v0.1"),
    }
    return result
