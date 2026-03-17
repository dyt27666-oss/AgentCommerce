from __future__ import annotations

import pytest

from tools.council_bridge.final_review_summary_writer import build_final_review_summary


def _handoff() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "codex_ready_payload": {
            "allowed_files": ["docs/llm-assisted.md", "README.md"]
        },
    }


def _receipt() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "execution_status": "completed",
        "changed_files": ["docs/llm-assisted.md"],
        "constraints_compliance": {"compliant": True, "note": "All good."},
    }


def test_build_final_review_summary_success() -> None:
    summary = build_final_review_summary(
        handoff=_handoff(),
        receipt=_receipt(),
        final_decision="approved",
        key_reason="Output meets scope and constraints.",
        next_action="Close round.",
        notes="review complete",
    )
    assert summary["request_id"] == "exec-req-001"
    assert summary["brief_id"] == "council-poc-brief-001"
    assert summary["handoff_id"] == "handoff-20260315-004"
    assert summary["final_owner_decision"] == "approved"
    assert summary["execution_status"] == "completed"
    assert summary["scope_compliance_check"]["in_allowed_scope"] is True
    assert summary["scope_compliance_check"]["constraints_compliant"] is True


def test_build_final_review_summary_identity_mismatch_fails() -> None:
    bad_receipt = _receipt()
    bad_receipt["brief_id"] = "wrong-brief"
    with pytest.raises(ValueError, match="Identity mismatch"):
        build_final_review_summary(
            handoff=_handoff(),
            receipt=bad_receipt,
            final_decision="needs_fix",
            key_reason="identity mismatch",
            next_action="fix linkage",
        )
