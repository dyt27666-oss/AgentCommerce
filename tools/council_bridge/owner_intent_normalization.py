"""Owner intent normalization v0.1.

This module normalizes owner free-text into a structured intent used by:
- feedback mapping adapter
- role rework adapter
- transition suggestion helpers

It does not perform authorization or state applying.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tools.council_bridge.policy_config_center import load_active_alias_dictionary, resolve_policy_config

DEFAULT_ALIAS_CONFIG_PATH = Path("config") / "owner_intent_aliases.v0.1.json"


@dataclass(slots=True)
class NormalizedOwnerIntent:
    intent_type: str
    target_role: str | None
    target_section: str | None
    requested_action: str | None
    requested_change: str | None
    severity: str | None
    confidence: float
    ambiguity_flags: list[str] = field(default_factory=list)
    ignored_reason: str | None = None
    source_text: str = ""
    alias_version: str = "owner.intent.alias.v0.1"
    policy_version: str = "policy.center.v0.1"
    policy_scope: str = "default"
    alias_scope: str = "default"
    workspace_id: str | None = None
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe(text: Any) -> str:
    return str(text or "").strip()


def load_owner_intent_alias_config(path: Path = DEFAULT_ALIAS_CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)
    if not isinstance(config, dict):
        raise ValueError("owner intent alias config root must be object")
    return config


def _detect_single_target(
    text: str,
    aliases: dict[str, list[str]],
    *,
    ambiguity_flag: str,
) -> tuple[str | None, list[str]]:
    lowered = text.lower()
    hits: list[str] = []
    for canonical, words in aliases.items():
        for word in words:
            if _safe(word).lower() and _safe(word).lower() in lowered:
                hits.append(canonical)
                break
    uniq: list[str] = []
    seen: set[str] = set()
    for item in hits:
        if item not in seen:
            uniq.append(item)
            seen.add(item)
    if len(uniq) == 1:
        return uniq[0], []
    if len(uniq) > 1:
        return uniq[0], [ambiguity_flag]
    return None, []


def _detect_severity(text: str, markers: dict[str, list[str]]) -> str | None:
    lowered = text.lower()
    for level in ["high", "medium", "low"]:
        for marker in markers.get(level, []):
            if _safe(marker).lower() in lowered:
                return level
    return None


def _infer_intent_type(target_role: str | None, target_section: str | None, action: str | None) -> str:
    if target_role and action in {"recheck", "rewrite", "redo", "refine", "tighten", "clarify"}:
        return "role_rework"
    if target_section:
        return "section_feedback"
    if action in {"resubmit"}:
        return "transition_hint"
    if action in {"summarize"}:
        return "comment"
    return "unknown"


def _infer_confidence(
    *,
    target_role: str | None,
    target_section: str | None,
    action: str | None,
    ambiguities: list[str],
) -> float:
    score = 0.35
    if target_section:
        score += 0.2
    if target_role:
        score += 0.2
    if action:
        score += 0.2
    if ambiguities:
        score -= 0.2
    return max(0.05, min(0.98, score))


def normalize_owner_intent(
    source_text: str,
    *,
    alias_config: dict[str, Any] | None = None,
    owner_id: str = "",
    group_id: str = "",
    workspace_id: str = "",
    project_id: str = "",
) -> NormalizedOwnerIntent:
    policy = resolve_policy_config(
        owner_id=owner_id,
        group_id=group_id,
        workspace_id=workspace_id,
        project_id=project_id,
    )

    text = _safe(source_text)
    if not text:
        return NormalizedOwnerIntent(
            intent_type="unknown",
            target_role=None,
            target_section=None,
            requested_action=None,
            requested_change=None,
            severity=None,
            confidence=0.05,
            ambiguity_flags=["empty_input"],
            ignored_reason="empty input",
            source_text=text,
            alias_version=str(policy.get("active_alias_version") or "owner.intent.alias.v0.1"),
            policy_version=str(policy.get("policy_version") or "policy.center.v0.1"),
            policy_scope=str(policy.get("policy_scope") or "default"),
            alias_scope=str(policy.get("alias_scope") or "default"),
            workspace_id=str(policy.get("workspace_id")) if policy.get("workspace_id") else None,
            project_id=str(policy.get("project_id")) if policy.get("project_id") else None,
        )

    config = alias_config or load_active_alias_dictionary(policy) or load_owner_intent_alias_config()
    section_aliases = config.get("section_aliases", {})
    role_aliases = config.get("role_aliases", {})
    action_aliases = config.get("action_aliases", {})
    severity_markers = config.get("severity_markers", {})

    if not isinstance(section_aliases, dict) or not isinstance(role_aliases, dict) or not isinstance(action_aliases, dict):
        raise ValueError("invalid alias configuration shape")

    target_section, section_flags = _detect_single_target(text, section_aliases, ambiguity_flag="multiple_section_candidates")
    target_role, role_flags = _detect_single_target(text, role_aliases, ambiguity_flag="multiple_role_candidates")
    requested_action, action_flags = _detect_single_target(text, action_aliases, ambiguity_flag="multiple_action_candidates")

    ambiguity_flags = section_flags + role_flags + action_flags
    severity = _detect_severity(text, severity_markers if isinstance(severity_markers, dict) else {})

    intent_type = _infer_intent_type(target_role, target_section, requested_action)
    ignored_reason = None

    if intent_type == "unknown":
        ambiguity_flags.append("intent_unresolved")
        ignored_reason = "could not normalize clear owner intent"

    if target_role and requested_action is None:
        ambiguity_flags.append("role_without_action")

    if requested_action == "resubmit" and target_section is None and target_role is None:
        intent_type = "transition_hint"

    confidence = _infer_confidence(
        target_role=target_role,
        target_section=target_section,
        action=requested_action,
        ambiguities=ambiguity_flags,
    )

    return NormalizedOwnerIntent(
        intent_type=intent_type,
        target_role=target_role,
        target_section=target_section,
        requested_action=requested_action,
        requested_change=text,
        severity=severity,
        confidence=confidence,
        ambiguity_flags=sorted(set(ambiguity_flags)),
        ignored_reason=ignored_reason,
        source_text=text,
        alias_version=str(policy.get("active_alias_version") or "owner.intent.alias.v0.1"),
        policy_version=str(policy.get("policy_version") or "policy.center.v0.1"),
        policy_scope=str(policy.get("policy_scope") or "default"),
        alias_scope=str(policy.get("alias_scope") or "default"),
        workspace_id=str(policy.get("workspace_id")) if policy.get("workspace_id") else None,
        project_id=str(policy.get("project_id")) if policy.get("project_id") else None,
    )
