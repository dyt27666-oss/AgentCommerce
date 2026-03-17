from __future__ import annotations

from pathlib import Path

import pytest

from tools.council_bridge.feishu_action_round_bridge import build_round_bridge


def _base_action(action: str) -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "owner_action": action,
        "action_by": "owner_mobile",
        "action_at": "2026-03-15T12:00:00+08:00",
        "source_artifact_path": "artifacts/council_codex_dispatch_ready.json",
        "source_state": "dispatch_ready=True",
        "notes": "",
    }


def test_dispatch_action_maps_to_continue_flow() -> None:
    result = build_round_bridge(_base_action("dispatch"), source_path=Path("artifacts/council_feishu_owner_action.json"))
    assert result["round_flow_state"] == "continue"
    assert "dispatch_prep_adapter.py" in " ".join(result["next_tool_paths"])
    assert "codex_dispatch_runner.py" in " ".join(result["next_tool_paths"])


def test_hold_action_maps_to_pause_flow() -> None:
    result = build_round_bridge(_base_action("hold"), source_path=Path("artifacts/council_feishu_owner_action.json"))
    assert result["round_flow_state"] == "pause"
    assert result["next_tool_paths"] == []


def test_needs_fix_action_maps_to_loop_back_flow() -> None:
    result = build_round_bridge(_base_action("needs_fix"), source_path=Path("artifacts/council_feishu_owner_action.json"))
    assert result["round_flow_state"] == "loop_back"
    assert "manual_handoff_writer.py" in " ".join(result["next_tool_paths"])


def test_reject_action_maps_to_stop_flow() -> None:
    result = build_round_bridge(_base_action("reject"), source_path=Path("artifacts/council_feishu_owner_action.json"))
    assert result["round_flow_state"] == "stop"
    assert result["next_artifact_paths"] == []


def test_invalid_action_raises() -> None:
    with pytest.raises(ValueError, match="owner_action"):
        build_round_bridge(_base_action("approve"), source_path=Path("artifacts/council_feishu_owner_action.json"))

