from __future__ import annotations

from tools.council_bridge.handoff_prompt_adapter import (
    build_codex_prompt,
    validate_executable_handoff,
)


def _approved_handoff() -> dict:
    return {
        "handoff_id": "handoff-20260315-001",
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "approval_status": "approved",
        "approved_by": "owner_manual",
        "approved_at": "2026-03-15T14:30:00+08:00",
        "codex_ready_payload": {
            "goal": "Clarify llm_assisted docs",
            "allowed_files": ["docs/llm-assisted.md"],
            "constraints": ["docs-only"],
            "validation_steps": ["py -m pytest -q"],
            "delivery_format": ["change summary", "git status"],
        },
        "validation_snapshot": {"dry_run_status": "valid", "dry_run_errors": []},
        "notes": "manual approved",
    }


def test_validate_executable_handoff_ok() -> None:
    errors = validate_executable_handoff(_approved_handoff())
    assert errors == []


def test_validate_executable_handoff_rejects_non_approved() -> None:
    handoff = _approved_handoff()
    handoff["approval_status"] = "needs_fix"
    handoff["codex_ready_payload"] = None
    errors = validate_executable_handoff(handoff)
    assert any("not executable" in e for e in errors)
    assert any("codex_ready_payload must be non-null" in e for e in errors)


def test_build_codex_prompt_contains_required_sections() -> None:
    prompt = build_codex_prompt(_approved_handoff())
    assert "Objective:" in prompt
    assert "Allowed Files (hard boundary):" in prompt
    assert "Constraints (hard boundary):" in prompt
    assert "Validation Steps:" in prompt
    assert "Delivery Format:" in prompt
