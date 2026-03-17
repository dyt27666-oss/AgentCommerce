from __future__ import annotations

from tools.council_bridge.handoff_execution_brief_mapper import build_execution_brief


def test_build_execution_brief_maps_required_fields() -> None:
    handoff = {
        "request_id": "req-brief-001",
        "brief_id": "brief-brief-001",
        "handoff_id": "handoff-brief-001",
        "summary": "demo summary",
        "approved_execution_brief": {"goal": "ship feature", "expected_outputs": ["receipt", "report"]},
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["no destructive git commands"],
        "no_go_zones": ["production data"],
        "required_receipts": ["execution_receipt_v0.1"],
    }
    gate = {"execution_handoff_ready": True}
    brief = build_execution_brief(handoff, gate)
    assert brief["objective"] == "ship feature"
    assert brief["execution_scope"] == ["tools/council_bridge"]
    assert brief["required_receipts"] == ["execution_receipt_v0.1"]
    assert brief["observe_only"] is True

