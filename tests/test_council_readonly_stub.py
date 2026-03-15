from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.council_bridge.readonly_stub import (
    build_codex_ready_payload,
    export_dry_run_result,
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


def test_export_dry_run_result_success_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "dry_run_success.json"
    result = export_dry_run_result("docs/council-mcp-input-sample.json", str(output))

    assert output.exists()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == result
    assert saved["status"] == "valid"
    assert saved["errors"] == []
    assert isinstance(saved["codex_ready_payload"], dict)


def test_export_dry_run_result_invalid_input_writes_structured_errors(
    tmp_path: Path,
) -> None:
    output = tmp_path / "dry_run_invalid.json"
    result = export_dry_run_result("docs/council-mcp-input-invalid-type.json", str(output))

    assert output.exists()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == result
    assert saved["status"] == "invalid_input"
    assert isinstance(saved["errors"], list)
    assert len(saved["errors"]) > 0
    assert saved["codex_ready_payload"] is None
