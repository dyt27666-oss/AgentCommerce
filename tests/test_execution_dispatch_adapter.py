from __future__ import annotations

from pathlib import Path

from tools.council_bridge.execution_dispatch_adapter import dispatch_from_execution_brief


def test_dispatch_from_execution_brief_calls_existing_runner(monkeypatch, tmp_path: Path) -> None:
    brief = {
        "objective": "demo",
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["no destructive"],
        "no_go_zones": ["secrets"],
        "expected_outputs": ["receipt"],
        "required_receipts": ["execution.receipt.v0.1"],
        "risk_notes": ["demo risk"],
        "correlated_request_id": "req-001",
        "correlated_brief_id": "brief-001",
        "correlated_handoff_id": "handoff-001",
    }

    called = {}

    def _fake_run_dispatch(**kwargs):
        called.update(kwargs)
        return {"dispatch_status": "dispatched"}

    monkeypatch.setattr("tools.council_bridge.execution_dispatch_adapter.run_dispatch", _fake_run_dispatch)
    result = dispatch_from_execution_brief(
        brief=brief,
        dispatch_ready_path=tmp_path / "ready.json",
        prompt_path=tmp_path / "prompt.txt",
        dispatch_receipt_path=tmp_path / "receipt.json",
    )
    assert result["dispatch_status"] == "dispatched"
    assert called["dispatch_ready_path"].endswith("ready.json")
    assert called["prompt_path"].endswith("prompt.txt")

