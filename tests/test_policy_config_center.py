from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import policy_config_center as pcc


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_policy_config_override_order(monkeypatch, tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    owners = tmp_path / "owners.json"
    groups = tmp_path / "groups.json"
    workspaces = tmp_path / "workspaces.json"
    projects = tmp_path / "projects.json"

    _write(
        default,
        {
            "policy_version": "policy.center.v0.1",
            "lane_switches": {"chat_lane_enabled": True, "chat_lane_require_mention": False},
            "alias_registry": {
                "active_version": "owner.intent.alias.v0.1",
                "versions": {"owner.intent.alias.v0.1": "config/owner_intent_aliases.v0.1.json"},
            },
        },
    )
    _write(owners, {"ownerX": {"lane_switches": {"chat_lane_enabled": False}}})
    _write(groups, {"groupX": {"lane_switches": {"chat_lane_require_mention": True}}})
    _write(workspaces, {"wsX": {"lane_switches": {"chat_lane_enabled": True}}})
    _write(projects, {"pjX": {"lane_switches": {"chat_lane_blocked_groups": ["g1"]}}})

    monkeypatch.setattr(pcc, "DEFAULT_CONFIG_PATH", default)
    monkeypatch.setattr(pcc, "OWNER_OVERRIDES_PATH", owners)
    monkeypatch.setattr(pcc, "GROUP_OVERRIDES_PATH", groups)
    monkeypatch.setattr(pcc, "WORKSPACE_OVERRIDES_PATH", workspaces)
    monkeypatch.setattr(pcc, "PROJECT_OVERRIDES_PATH", projects)

    cfg = pcc.resolve_policy_config(owner_id="ownerX", group_id="groupX", workspace_id="wsX", project_id="pjX")
    lane = cfg["lane_switches"]
    assert lane["chat_lane_enabled"] is True
    assert lane["chat_lane_require_mention"] is True
    assert lane["chat_lane_blocked_groups"] == ["g1"]
    assert cfg["policy_scope"].endswith("project:pjX")
    assert cfg["active_alias_version"] == "owner.intent.alias.v0.1"


def test_alias_version_publish_and_rollback(monkeypatch, tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    _write(
        default,
        {
            "policy_version": "policy.center.v0.1",
            "lane_switches": {},
            "alias_registry": {
                "active_version": "v1",
                "versions": {
                    "v1": "config/owner_intent_aliases.v0.1.json",
                    "v2": "config/owner_intent_aliases.v0.2.json",
                },
            },
        },
    )
    monkeypatch.setattr(pcc, "DEFAULT_CONFIG_PATH", default)
    versions = pcc.list_alias_versions(default)
    assert versions == ["v1", "v2"]

    updated = pcc.set_active_alias_version("v2", config_path=default)
    assert updated["alias_registry"]["active_version"] == "v2"

    rolled = pcc.set_active_alias_version("v1", config_path=default)
    assert rolled["alias_registry"]["active_version"] == "v1"
