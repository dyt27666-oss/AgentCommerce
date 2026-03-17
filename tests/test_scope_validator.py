from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.scope_validator import (
    ACTION_BLOCKED,
    ACTION_DEGRADED_CONTINUE,
    ACTION_PASS,
    ScopeValidationInput,
    validate_scope,
    write_scope_validation_result,
)


def _payload(**kwargs):
    base = {
        "mode": "strict",
        "workspace_id": "ws_alpha",
        "project_id": "pj_market",
        "policy_scope": "default>workspace:ws_alpha>project:pj_market",
        "alias_scope": "default>workspace:ws_alpha>project:pj_market",
    }
    base.update(kwargs)
    return base


def test_strict_pass() -> None:
    result = validate_scope(_payload(mode="strict"))
    assert result.is_valid is True
    assert result.action == ACTION_PASS
    assert result.errors == []


def test_strict_missing_workspace_blocked() -> None:
    result = validate_scope(_payload(mode="strict", workspace_id=""))
    assert result.is_valid is False
    assert result.action == ACTION_BLOCKED
    assert any("workspace_id" in e for e in result.errors)


def test_strict_missing_project_blocked() -> None:
    result = validate_scope(_payload(mode="strict", project_id=None))
    assert result.is_valid is False
    assert result.action == ACTION_BLOCKED
    assert any("project_id" in e for e in result.errors)


def test_lenient_missing_scope_degraded() -> None:
    result = validate_scope(_payload(mode="lenient", workspace_id="unknown", project_id=""))
    assert result.is_valid is True
    assert result.action == ACTION_DEGRADED_CONTINUE
    assert "workspace_id" in result.degraded_fields
    assert "project_id" in result.degraded_fields
    assert result.normalized_scope["workspace_id"] == "unknown"


def test_strict_invalid_policy_scope_blocked() -> None:
    result = validate_scope(_payload(mode="strict", policy_scope="workspace:ws_alpha"))
    assert result.is_valid is False
    assert result.action == ACTION_BLOCKED
    assert any("policy_scope" in e for e in result.errors)


def test_lenient_invalid_policy_scope_reset_default() -> None:
    result = validate_scope(_payload(mode="lenient", policy_scope="workspace:ws_alpha"))
    assert result.is_valid is True
    assert result.action == ACTION_DEGRADED_CONTINUE
    assert result.normalized_scope["policy_scope"] == "default"
    assert any("policy_scope" in w for w in result.warnings)


def test_strict_alias_scope_mismatch_blocked() -> None:
    result = validate_scope(
        _payload(
            mode="strict",
            alias_scope="default>workspace:ws_alpha>project:pj_other",
        )
    )
    assert result.is_valid is False
    assert result.action == ACTION_BLOCKED
    assert any("alias_scope is not consistent" in e for e in result.errors)


def test_lenient_alias_scope_mismatch_warning() -> None:
    result = validate_scope(
        _payload(
            mode="lenient",
            alias_scope="default>workspace:ws_alpha>project:pj_other",
        )
    )
    assert result.is_valid is True
    assert result.action == ACTION_DEGRADED_CONTINUE
    assert result.normalized_scope["alias_scope"] == result.normalized_scope["policy_scope"]


def test_lenient_invalid_alias_scope_fallback_policy_scope() -> None:
    result = validate_scope(
        _payload(
            mode="lenient",
            alias_scope="bad-scope",
        )
    )
    assert result.is_valid is True
    assert result.normalized_scope["alias_scope"] == result.normalized_scope["policy_scope"]


def test_scope_chain_minimal_default_is_valid() -> None:
    result = validate_scope(
        _payload(
            mode="strict",
            policy_scope="default",
            alias_scope="default",
        )
    )
    assert result.is_valid is True
    assert result.action == ACTION_PASS


def test_scope_chain_with_empty_segment_invalid() -> None:
    result = validate_scope(
        _payload(
            mode="strict",
            policy_scope="default>>project:pj_market",
            alias_scope="default>>project:pj_market",
        )
    )
    assert result.is_valid is False
    assert result.action == ACTION_BLOCKED


def test_scope_chain_unknown_token_lenient_degraded() -> None:
    result = validate_scope(
        _payload(
            mode="lenient",
            policy_scope="unknown",
            alias_scope=None,
        )
    )
    assert result.is_valid is True
    assert result.action == ACTION_DEGRADED_CONTINUE
    assert result.normalized_scope["policy_scope"] == "default"


def test_input_dataclass_and_artifact_write(tmp_path: Path) -> None:
    inp = ScopeValidationInput.from_dict(_payload(mode="strict"))
    result = validate_scope(inp)
    out = tmp_path / "scope_validation_result.json"
    write_scope_validation_result(result, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["action"] == ACTION_PASS
