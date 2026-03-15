from __future__ import annotations

import copy

from tools.council_bridge.readonly_stub import (
    build_codex_ready_payload,
    load_input,
    validate_contract,
)


def test_readonly_stub_success_from_sample() -> None:
    data = load_input("docs/council-mcp-input-sample.json")

    is_valid, errors = validate_contract(data)
    assert is_valid is True
    assert errors == []

    result = build_codex_ready_payload(data)
    assert result["status"] == "valid"
    assert result["errors"] == []
    assert result["request_id"] == "exec-req-001"
    assert result["brief_id"] == "council-poc-brief-001"
    assert isinstance(result["codex_ready_payload"], dict)
    assert result["codex_ready_payload"]["repo_context"]["repo"] == "AgentCommerce"


def test_readonly_stub_invalid_when_brief_id_mismatch() -> None:
    data = load_input("docs/council-mcp-input-sample.json")
    broken = copy.deepcopy(data)
    broken["codex_execution_request"]["brief_id"] = "mismatch-brief-id"

    is_valid, errors = validate_contract(broken)
    assert is_valid is False
    assert any("brief_id mismatch" in err for err in errors)

    result = build_codex_ready_payload(broken)
    assert result["status"] == "invalid_input"
    assert result["codex_ready_payload"] is None
    assert any("brief_id mismatch" in err for err in result["errors"])
