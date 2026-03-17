from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.dispatch_prep_adapter import prepare_dispatch_package


def _approved_handoff() -> dict:
    return {
        "handoff_id": "handoff-20260315-020",
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "approval_status": "approved",
        "approved_by": "owner_manual",
        "approved_at": "2026-03-15T19:00:00+08:00",
        "codex_ready_payload": {
            "goal": "Clarify docs",
            "allowed_files": ["docs/llm-assisted.md"],
            "constraints": ["docs-only"],
            "validation_steps": ["py -m pytest -q"],
            "delivery_format": ["change summary"],
        },
        "validation_snapshot": {"dry_run_status": "valid", "dry_run_errors": []},
        "notes": "approved",
    }


def test_dispatch_prep_approved_executable_path(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    prompt = tmp_path / "prompt.txt"
    output = tmp_path / "dispatch.json"
    handoff.write_text(json.dumps(_approved_handoff()), encoding="utf-8")
    prompt.write_text("prompt content", encoding="utf-8")

    artifact = prepare_dispatch_package(str(handoff), str(prompt), str(output))

    assert artifact["dispatch_ready"] is True
    assert "dispatch_notes" in artifact
    assert output.exists()


def test_dispatch_prep_non_approved_blocked(tmp_path: Path) -> None:
    data = _approved_handoff()
    data["approval_status"] = "needs_fix"
    data["codex_ready_payload"] = None
    handoff = tmp_path / "handoff.json"
    prompt = tmp_path / "prompt.txt"
    output = tmp_path / "dispatch.json"
    handoff.write_text(json.dumps(data), encoding="utf-8")
    prompt.write_text("prompt content", encoding="utf-8")

    artifact = prepare_dispatch_package(str(handoff), str(prompt), str(output))
    assert artifact["dispatch_ready"] is False
    assert "blocking_reason" in artifact
    assert "handoff_executable" in artifact["blocking_reason"]


def test_dispatch_prep_missing_prompt_blocked(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    output = tmp_path / "dispatch.json"
    handoff.write_text(json.dumps(_approved_handoff()), encoding="utf-8")

    artifact = prepare_dispatch_package(str(handoff), str(tmp_path / "missing_prompt.txt"), str(output))
    assert artifact["dispatch_ready"] is False
    assert "prompt_exists" in artifact["blocking_reason"]


def test_dispatch_prep_invalid_gate_state_blocked(tmp_path: Path) -> None:
    data = _approved_handoff()
    data["validation_snapshot"] = {"dry_run_status": "invalid_input", "dry_run_errors": ["bad"]}
    handoff = tmp_path / "handoff.json"
    prompt = tmp_path / "prompt.txt"
    output = tmp_path / "dispatch.json"
    handoff.write_text(json.dumps(data), encoding="utf-8")
    prompt.write_text("prompt content", encoding="utf-8")

    artifact = prepare_dispatch_package(str(handoff), str(prompt), str(output))
    assert artifact["dispatch_ready"] is False
    assert "dry_run_status must be 'valid'" in artifact["blocking_reason"]
