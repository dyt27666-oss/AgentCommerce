from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from tools.council_bridge.manual_handoff_writer import build_handoff_artifact


def _template() -> dict:
    return {
        "handoff_id": "",
        "request_id": "",
        "brief_id": "",
        "approval_status": "",
        "approved_by": "",
        "approved_at": "",
        "codex_ready_payload": {},
        "validation_snapshot": {
            "dry_run_status": "",
            "dry_run_errors": [],
        },
        "notes": "",
    }


def _dry_run_valid() -> dict:
    return {
        "status": "valid",
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "codex_ready_payload": {
            "goal": "Clarify docs",
            "allowed_files": ["docs/llm-assisted.md"],
            "constraints": ["docs-only"],
        },
        "errors": [],
    }


def _dry_run_invalid() -> dict:
    return {
        "status": "invalid_input",
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "codex_ready_payload": None,
        "errors": ["missing owner_intent"],
    }


def test_build_handoff_artifact_approved_prefills_required_fields(tmp_path: Path) -> None:
    output_path = tmp_path / "council_bridge_handoff.json"
    now = datetime.fromisoformat("2026-03-15T14:30:00+08:00")

    result = build_handoff_artifact(
        dry_run=_dry_run_valid(),
        template=_template(),
        approval_status="approved",
        approved_by="owner_manual",
        notes="manual review passed",
        output_path=output_path,
        now=now,
    )

    assert re.match(r"^handoff-20260315-\d{3}$", result["handoff_id"])
    assert result["request_id"] == "exec-req-001"
    assert result["brief_id"] == "council-poc-brief-001"
    assert result["approval_status"] == "approved"
    assert result["approved_by"] == "owner_manual"
    assert result["approved_at"] == "2026-03-15T14:30:00+08:00"
    assert result["notes"] == "manual review passed"
    assert isinstance(result["codex_ready_payload"], dict)
    assert result["validation_snapshot"]["dry_run_status"] == "valid"
    assert result["validation_snapshot"]["dry_run_errors"] == []


@pytest.mark.parametrize("status", ["needs_fix", "rejected"])
def test_build_handoff_artifact_non_approved_forces_payload_null(
    tmp_path: Path, status: str
) -> None:
    output_path = tmp_path / "council_bridge_handoff.json"
    now = datetime.fromisoformat("2026-03-15T14:31:00+08:00")

    result = build_handoff_artifact(
        dry_run=_dry_run_invalid(),
        template=_template(),
        approval_status=status,
        approved_by="owner_manual",
        notes=f"{status} decision",
        output_path=output_path,
        now=now,
    )

    assert result["approval_status"] == status
    assert result["codex_ready_payload"] is None
    assert result["validation_snapshot"]["dry_run_status"] == "invalid_input"
    assert result["validation_snapshot"]["dry_run_errors"] == ["missing owner_intent"]


def test_build_handoff_artifact_approved_requires_valid_dry_run(tmp_path: Path) -> None:
    output_path = tmp_path / "council_bridge_handoff.json"

    with pytest.raises(ValueError, match="approved requires dry_run status == valid"):
        build_handoff_artifact(
            dry_run=_dry_run_invalid(),
            template=_template(),
            approval_status="approved",
            approved_by="owner_manual",
            notes="bad approved",
            output_path=output_path,
        )


def test_build_handoff_artifact_validates_approved_by_format(tmp_path: Path) -> None:
    output_path = tmp_path / "council_bridge_handoff.json"

    with pytest.raises(ValueError, match="approved_by must match"):
        build_handoff_artifact(
            dry_run=_dry_run_valid(),
            template=_template(),
            approval_status="approved",
            approved_by="Owner Manual",
            notes="manual review passed",
            output_path=output_path,
        )
