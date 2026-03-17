from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.council_bridge.final_review_once import run_final_review_once


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _handoff() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "codex_ready_payload": {"allowed_files": ["docs/llm-assisted.md"]},
    }


def _receipt() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "execution_status": "completed",
        "changed_files": ["docs/llm-assisted.md"],
        "constraints_compliance": {"compliant": True, "note": "ok"},
        "summary": "done",
        "next_step_suggestion": "close",
    }


@pytest.mark.parametrize("decision", ["approved", "revision_request", "needs_fix", "rejected"])
def test_decision_paths_generate_summary(decision: str, tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    receipt = tmp_path / "receipt.json"
    summary_output = tmp_path / "final_summary.json"
    _write_json(handoff, _handoff())
    _write_json(receipt, _receipt())

    result = run_final_review_once(
        final_decision=decision,
        key_reason="reason",
        next_action="next",
        notes="n",
        handoff_path=handoff,
        receipt_path=receipt,
        summary_output_path=summary_output,
        prompt_path=tmp_path / "missing_prompt.txt",
        continue_once_path=tmp_path / "missing_continue_once.json",
        completion_path=tmp_path / "missing_completion.json",
        receipt_skeleton_path=tmp_path / "missing_skeleton.json",
    )
    assert result["final_decision"] == decision
    assert result["summary_status"] == "written"
    assert summary_output.exists()


def test_identity_inherited_from_summary(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    receipt = tmp_path / "receipt.json"
    summary_output = tmp_path / "final_summary.json"
    continue_once = tmp_path / "continue_once.json"
    _write_json(handoff, _handoff())
    _write_json(receipt, _receipt())
    _write_json(
        continue_once,
        {
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
        },
    )

    result = run_final_review_once(
        final_decision="approved",
        key_reason="reason",
        next_action="next",
        handoff_path=handoff,
        receipt_path=receipt,
        summary_output_path=summary_output,
        prompt_path=tmp_path / "missing_prompt.txt",
        continue_once_path=continue_once,
        completion_path=tmp_path / "missing_completion.json",
        receipt_skeleton_path=tmp_path / "missing_skeleton.json",
    )
    assert result["inherited_identity"]["request_id"] == "exec-req-001"
    assert result["inherited_identity"]["brief_id"] == "council-poc-brief-001"
    assert result["inherited_identity"]["handoff_id"] == "handoff-20260315-004"


def test_missing_required_input_is_explainable(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    _write_json(handoff, _handoff())
    with pytest.raises((FileNotFoundError, ValueError)):
        run_final_review_once(
            final_decision="approved",
            key_reason="reason",
            next_action="next",
            handoff_path=handoff,
            receipt_path=tmp_path / "missing_receipt.json",
        )

