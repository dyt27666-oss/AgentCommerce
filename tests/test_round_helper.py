from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.council_bridge.round_helper import prepare_round


def _approved_handoff() -> dict:
    return {
        "handoff_id": "handoff-20260315-010",
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "approval_status": "approved",
        "approved_by": "owner_manual",
        "approved_at": "2026-03-15T18:30:00+08:00",
        "codex_ready_payload": {
            "goal": "Clarify docs",
            "allowed_files": ["docs/llm-assisted.md"],
            "constraints": ["docs-only"],
            "validation_steps": ["py -m pytest -q"],
            "delivery_format": ["change summary"],
        },
        "validation_snapshot": {"dry_run_status": "valid", "dry_run_errors": []},
        "notes": "approved for execution prep",
    }


def test_prepare_round_generates_prompt_and_summary(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.json"
    prompt_path = tmp_path / "prompt.txt"
    summary_path = tmp_path / "summary.json"
    handoff_path.write_text(json.dumps(_approved_handoff()), encoding="utf-8")

    summary = prepare_round(str(handoff_path), str(prompt_path), str(summary_path))

    assert prompt_path.exists()
    assert summary_path.exists()
    assert summary["request_id"] == "exec-req-001"
    assert summary["brief_id"] == "council-poc-brief-001"
    assert summary["approval_status"] == "approved"
    assert "artifacts/council_codex_execution_receipt.json" in summary["expected_next_artifacts"]


def test_prepare_round_rejects_non_executable_handoff(tmp_path: Path) -> None:
    handoff = _approved_handoff()
    handoff["approval_status"] = "needs_fix"
    handoff["codex_ready_payload"] = None

    handoff_path = tmp_path / "handoff_bad.json"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")

    with pytest.raises(ValueError, match="not executable"):
        prepare_round(str(handoff_path), str(tmp_path / "prompt.txt"), str(tmp_path / "summary.json"))
