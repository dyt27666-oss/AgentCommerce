"""Policy configuration center v0.1.

Provides unified config loading with layered overrides:
default -> owner -> group -> workspace -> project
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("config") / "policy_center" / "default.json"
OWNER_OVERRIDES_PATH = Path("config") / "policy_center" / "owner_overrides.json"
GROUP_OVERRIDES_PATH = Path("config") / "policy_center" / "group_overrides.json"
WORKSPACE_OVERRIDES_PATH = Path("config") / "policy_center" / "workspace_overrides.json"
PROJECT_OVERRIDES_PATH = Path("config") / "policy_center" / "project_overrides.json"


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else fallback


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)  # type: ignore[arg-type]
        else:
            out[key] = value
    return out


def _pick_override(table: dict[str, Any], key: str) -> dict[str, Any]:
    if not key:
        return {}
    candidate = table.get(key)
    return candidate if isinstance(candidate, dict) else {}


def resolve_policy_config(
    *,
    owner_id: str = "",
    group_id: str = "",
    workspace_id: str = "",
    project_id: str = "",
) -> dict[str, Any]:
    default_cfg = _load_json(
        DEFAULT_CONFIG_PATH,
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
                },
            },
            "scope_defaults": {
                "policy_scope": "default",
                "alias_scope": "default",
            },
        },
    )
    owners = _load_json(OWNER_OVERRIDES_PATH, {})
    groups = _load_json(GROUP_OVERRIDES_PATH, {})
    workspaces = _load_json(WORKSPACE_OVERRIDES_PATH, {})
    projects = _load_json(PROJECT_OVERRIDES_PATH, {})

    merged = default_cfg
    scope_chain: list[str] = ["default"]

    owner_override = _pick_override(owners, owner_id)
    if owner_override:
        merged = _deep_merge(merged, owner_override)
        scope_chain.append(f"owner:{owner_id}")

    group_override = _pick_override(groups, group_id)
    if group_override:
        merged = _deep_merge(merged, group_override)
        scope_chain.append(f"group:{group_id}")

    workspace_override = _pick_override(workspaces, workspace_id)
    if workspace_override:
        merged = _deep_merge(merged, workspace_override)
        scope_chain.append(f"workspace:{workspace_id}")

    project_override = _pick_override(projects, project_id)
    if project_override:
        merged = _deep_merge(merged, project_override)
        scope_chain.append(f"project:{project_id}")

    alias_registry = merged.get("alias_registry") if isinstance(merged.get("alias_registry"), dict) else {}
    active_alias_version = alias_registry.get("active_version") if isinstance(alias_registry, dict) else None
    versions = alias_registry.get("versions") if isinstance(alias_registry.get("versions"), dict) else {}
    alias_path = versions.get(active_alias_version) if isinstance(versions, dict) else None

    result = dict(merged)
    result["owner_id"] = owner_id or None
    result["group_id"] = group_id or None
    result["workspace_id"] = workspace_id or None
    result["project_id"] = project_id or None
    result["policy_scope"] = ">".join(scope_chain)
    result["alias_scope"] = ">".join(scope_chain)
    result["active_alias_version"] = active_alias_version or "owner.intent.alias.v0.1"
    result["active_alias_path"] = str(alias_path or "config/owner_intent_aliases.v0.1.json")
    return result


def load_active_alias_dictionary(policy_config: dict[str, Any]) -> dict[str, Any]:
    alias_path = Path(str(policy_config.get("active_alias_path") or "config/owner_intent_aliases.v0.1.json"))
    return _load_json(alias_path, {})


def list_alias_versions(config_path: Path = DEFAULT_CONFIG_PATH) -> list[str]:
    config = _load_json(config_path, {})
    alias_registry = config.get("alias_registry")
    if not isinstance(alias_registry, dict):
        return []
    versions = alias_registry.get("versions")
    if not isinstance(versions, dict):
        return []
    return sorted(str(k) for k in versions.keys())


def set_active_alias_version(
    version: str,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    config = _load_json(config_path, {})
    alias_registry = config.get("alias_registry")
    if not isinstance(alias_registry, dict):
        raise ValueError("alias_registry missing in policy config")
    versions = alias_registry.get("versions")
    if not isinstance(versions, dict):
        raise ValueError("alias_registry.versions missing in policy config")
    if version not in versions:
        raise ValueError(f"unknown alias version: {version}")

    alias_registry["active_version"] = version
    config["alias_registry"] = alias_registry
    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config
