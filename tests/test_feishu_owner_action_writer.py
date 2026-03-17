from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tools.council_bridge.feishu_owner_action_writer import (
    build_owner_action_artifact,
    infer_source_state,
)


def test_infer_source_state_dispatch_ready() -> None:
    state = infer_source_state({"dispatch_ready": True})
    assert state == "dispatch_ready=True"


def test_build_owner_action_artifact_reuses_identity() -> None:
    source_data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_ready": True,
    }
    now = datetime.fromisoformat("2026-03-15T12:00:00+08:00")
    artifact = build_owner_action_artifact(
        source_data=source_data,
        source_artifact_path=Path("artifacts/council_codex_dispatch_ready.json"),
        owner_action="dispatch",
        owner_id="owner_mobile",
        notes="ok",
        now=now,
    )

    assert artifact["request_id"] == "exec-req-001"
    assert artifact["brief_id"] == "council-poc-brief-001"
    assert artifact["handoff_id"] == "handoff-20260315-004"
    assert artifact["owner_action"] == "dispatch"
    assert artifact["source_state"] == "dispatch_ready=True"
    assert artifact["action_by"] == "owner_mobile"
    assert artifact["action_at"] == "2026-03-15T12:00:00+08:00"


def test_build_owner_action_artifact_rejects_invalid_action() -> None:
    with pytest.raises(ValueError, match="owner_action"):
        build_owner_action_artifact(
            source_data={"request_id": "r1"},
            source_artifact_path=Path("artifacts/council_codex_dispatch_ready.json"),
            owner_action="approve",
            owner_id="owner_mobile",
        )


def test_build_owner_action_artifact_requires_identity() -> None:
    with pytest.raises(ValueError, match="identity field"):
        build_owner_action_artifact(
            source_data={"dispatch_ready": True},
            source_artifact_path=Path("artifacts/council_codex_dispatch_ready.json"),
            owner_action="hold",
            owner_id="owner_mobile",
        )

