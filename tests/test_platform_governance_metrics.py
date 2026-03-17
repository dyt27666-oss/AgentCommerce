from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.platform_governance_metrics import build_governance_metrics_summary, write_governance_metrics_summary


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_metrics_summary_counts_and_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "council_feishu_feedback_mapping_result.json",
        {
            "is_mapped": True,
            "ambiguity_flags": [],
            "workspace_id": "ws1",
            "project_id": "pj1",
            "sender_id": "ownerA",
        },
    )
    _write(
        tmp_path / "council_role_rework_mapping_result.json",
        {
            "is_mapped": False,
            "ambiguity_flags": ["intent_unresolved"],
            "workspace_id": "ws1",
            "project_id": "pj1",
            "sender_id": "ownerA",
        },
    )
    _write(
        tmp_path / "council_artifact_state_transition_result.json",
        {"is_valid": True, "workspace_id": "ws1", "project_id": "pj1", "sender_id": "ownerA"},
    )
    _write(
        tmp_path / "council_owner_confirmed_apply_result.json",
        {"apply_status": "applied", "workspace_id": "ws1", "project_id": "pj1", "confirmed_by": "ownerA"},
    )
    _write(
        tmp_path / "council_execution_dispatch_result.json",
        {"dispatch_status": "blocked", "workspace_id": "ws2", "project_id": "pj2", "confirmed_by": "ownerB"},
    )

    summary = build_governance_metrics_summary(artifacts_dir=tmp_path)
    assert summary["normalization"]["total"] == 2
    assert summary["normalization"]["hit"] == 1
    assert summary["normalization"]["ignored"] == 1
    assert summary["feedback_mapping"]["hit"] == 1
    assert summary["role_rework"]["detected"] == 0
    assert summary["state_validation"]["pass"] == 1
    assert summary["apply"]["success"] == 1
    assert summary["execution_dispatch"]["blocked"] == 1
    assert "workspace:ws1|project:pj1|owner:ownerA" in summary["by_scope"]

    out = tmp_path / "summary.json"
    write_governance_metrics_summary(summary, out)
    assert out.exists()
