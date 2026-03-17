"""Scope Validator Core v0.1.

Minimal scope completeness and consistency validator.
This module is translation/validation only; it does not authorize or execute.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VALIDATION_MODE_STRICT = "strict"
VALIDATION_MODE_LENIENT = "lenient"
VALIDATION_MODES = {VALIDATION_MODE_STRICT, VALIDATION_MODE_LENIENT}

ACTION_BLOCKED = "blocked"
ACTION_DEGRADED_CONTINUE = "degraded_continue"
ACTION_PASS = "pass"

VALID_SCOPE_SEGMENTS = {"owner", "group", "workspace", "project"}
SCOPE_SEGMENT_RE = re.compile(r"^(owner|group|workspace|project):[A-Za-z0-9_.-]+$")
UNKNOWN_TOKENS = {"unknown", "n/a", "na", "null", "none"}


@dataclass(slots=True)
class ScopeValidationInput:
    mode: str
    workspace_id: str | None
    project_id: str | None
    policy_scope: str | None
    alias_scope: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScopeValidationInput":
        return cls(
            mode=str(data.get("mode") or VALIDATION_MODE_LENIENT).strip().lower(),
            workspace_id=_normalize_optional_text(data.get("workspace_id")),
            project_id=_normalize_optional_text(data.get("project_id")),
            policy_scope=_normalize_optional_text(data.get("policy_scope")),
            alias_scope=_normalize_optional_text(data.get("alias_scope")),
        )


@dataclass(slots=True)
class ScopeValidationResult:
    mode: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degraded_fields: list[str] = field(default_factory=list)
    normalized_scope: dict[str, str] = field(default_factory=dict)
    action: str = ACTION_PASS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _is_missing_or_unknown(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in UNKNOWN_TOKENS


def _is_valid_scope_chain(value: str | None) -> bool:
    if value is None:
        return False
    text = value.strip()
    if not text:
        return False
    parts = [p.strip() for p in text.split(">")]
    if any(not p for p in parts):
        return False
    if parts[0] != "default":
        return False
    for part in parts[1:]:
        if not SCOPE_SEGMENT_RE.match(part):
            return False
        segment, _, seg_id = part.partition(":")
        if segment not in VALID_SCOPE_SEGMENTS:
            return False
        if not seg_id or seg_id.lower() in UNKNOWN_TOKENS:
            return False
    return True


def _strict_or_warn(
    *,
    mode: str,
    field_name: str,
    message: str,
    errors: list[str],
    warnings: list[str],
    degraded_fields: list[str],
) -> None:
    if mode == VALIDATION_MODE_STRICT:
        errors.append(message)
    else:
        warnings.append(message)
        degraded_fields.append(field_name)


def validate_scope(input_data: ScopeValidationInput | dict[str, Any]) -> ScopeValidationResult:
    payload = input_data if isinstance(input_data, ScopeValidationInput) else ScopeValidationInput.from_dict(input_data)

    mode = payload.mode
    if mode not in VALIDATION_MODES:
        mode = VALIDATION_MODE_LENIENT

    errors: list[str] = []
    warnings: list[str] = []
    degraded_fields: list[str] = []

    workspace_id = payload.workspace_id
    project_id = payload.project_id
    policy_scope = payload.policy_scope
    alias_scope = payload.alias_scope

    if _is_missing_or_unknown(workspace_id):
        _strict_or_warn(
            mode=mode,
            field_name="workspace_id",
            message="workspace_id is missing/unknown.",
            errors=errors,
            warnings=warnings,
            degraded_fields=degraded_fields,
        )
        if mode == VALIDATION_MODE_LENIENT:
            workspace_id = "unknown"

    if _is_missing_or_unknown(project_id):
        _strict_or_warn(
            mode=mode,
            field_name="project_id",
            message="project_id is missing/unknown.",
            errors=errors,
            warnings=warnings,
            degraded_fields=degraded_fields,
        )
        if mode == VALIDATION_MODE_LENIENT:
            project_id = "unknown"

    policy_scope_valid = _is_valid_scope_chain(policy_scope)
    if not policy_scope_valid:
        _strict_or_warn(
            mode=mode,
            field_name="policy_scope",
            message="policy_scope format is invalid.",
            errors=errors,
            warnings=warnings,
            degraded_fields=degraded_fields,
        )
        if mode == VALIDATION_MODE_LENIENT:
            policy_scope = "default"

    alias_scope_valid = _is_valid_scope_chain(alias_scope)
    if not alias_scope_valid:
        _strict_or_warn(
            mode=mode,
            field_name="alias_scope",
            message="alias_scope format is invalid.",
            errors=errors,
            warnings=warnings,
            degraded_fields=degraded_fields,
        )
        if mode == VALIDATION_MODE_LENIENT:
            alias_scope = policy_scope or "default"

    if _is_valid_scope_chain(policy_scope) and _is_valid_scope_chain(alias_scope):
        if policy_scope != alias_scope:
            _strict_or_warn(
                mode=mode,
                field_name="alias_scope",
                message="alias_scope is not consistent with policy_scope.",
                errors=errors,
                warnings=warnings,
                degraded_fields=degraded_fields,
            )
            if mode == VALIDATION_MODE_LENIENT:
                alias_scope = policy_scope

    is_valid = len(errors) == 0
    if not is_valid:
        action = ACTION_BLOCKED
    elif warnings or degraded_fields:
        action = ACTION_DEGRADED_CONTINUE
    else:
        action = ACTION_PASS

    normalized_scope = {
        "workspace_id": workspace_id or "unknown",
        "project_id": project_id or "unknown",
        "policy_scope": policy_scope or "default",
        "alias_scope": alias_scope or (policy_scope or "default"),
    }

    return ScopeValidationResult(
        mode=mode,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        degraded_fields=sorted(set(degraded_fields)),
        normalized_scope=normalized_scope,
        action=action,
    )


def write_scope_validation_result(result: ScopeValidationResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
