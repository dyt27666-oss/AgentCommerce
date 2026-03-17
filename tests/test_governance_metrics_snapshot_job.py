from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.governance_metrics_snapshot_job import (
    build_governance_metrics_snapshot_job_result,
    run_governance_metrics_snapshot_job,
    write_governance_metrics_snapshot_job_artifact,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")


def _event(
    *,
    event_id: str,
    event_type: str,
    status: str,
    dedupe_key: str,
    workspace_id: str = "ws_alpha",
    project_id: str = "pj_market",
    owner_id: str = "owner_001",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-03-17T15:00:00+08:00",
        "request_id": "req-1",
        "publish_id": "pub-1",
        "workspace_id": workspace_id,
        "project_id": project_id,
        "owner_id": owner_id,
        "source_module": "test",
        "source_artifact": "artifacts/source.json",
        "status": status,
        "payload_summary": {"k": "v"},
        "dedupe_key": dedupe_key,
    }


def test_snapshot_job_incremental_happy_path(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [
            _event(event_id="e1", event_type="scope_validation_result", status="pass", dedupe_key="k1"),
            _event(event_id="e2", event_type="router_scope_observe_result", status="degraded_continue", dedupe_key="k2"),
            _event(event_id="e3", event_type="policy_publish_result", status="applied", dedupe_key="k3"),
        ],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)

    assert snap["artifact_type"] == "governance_metrics_snapshot"
    assert snap["source_mode"] == "incremental"
    assert snap["metrics"]["scope_validation"]["pass"] == 1
    assert snap["metrics"]["router_scope_observe"]["observed"] == 1
    assert snap["metrics"]["router_scope_observe"]["warnings"] == 1
    assert snap["metrics"]["policy_publish"]["applied"] == 1


def test_snapshot_job_scope_aggregation_by_composite_key(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [
            _event(event_id="e1", event_type="scope_validation_result", status="pass", dedupe_key="k1", workspace_id="ws1", project_id="pj1", owner_id="ownerA"),
            _event(event_id="e2", event_type="policy_publish_result", status="rejected", dedupe_key="k2", workspace_id="ws1", project_id="pj1", owner_id="ownerA"),
            _event(event_id="e3", event_type="policy_publish_result", status="rolled_back", dedupe_key="k3", workspace_id="ws2", project_id="pj2", owner_id="ownerB"),
        ],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)

    assert "workspace:ws1|project:pj1|owner:ownerA" in snap["by_scope"]
    assert "workspace:ws2|project:pj2|owner:ownerB" in snap["by_scope"]
    assert snap["by_scope"]["workspace:ws1|project:pj1|owner:ownerA"]["policy_publish"]["rejected"] == 1


def test_snapshot_job_duplicate_event_id_ignored(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [
            _event(event_id="e1", event_type="policy_publish_result", status="applied", dedupe_key="k1"),
            _event(event_id="e1", event_type="policy_publish_result", status="applied", dedupe_key="k2"),
        ],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)
    assert snap["metrics"]["policy_publish"]["applied"] == 1
    assert snap["job_stats"]["dedupe"]["duplicate_event_id"] == 1


def test_snapshot_job_duplicate_fallback_key_ignored(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [
            _event(event_id="e1", event_type="scope_validation_result", status="degraded_continue", dedupe_key="same"),
            _event(event_id="e2", event_type="scope_validation_result", status="degraded_continue", dedupe_key="same"),
        ],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)
    assert snap["metrics"]["scope_validation"]["degraded"] == 1
    assert snap["job_stats"]["dedupe"]["duplicate_fallback_key"] == 1


def test_snapshot_job_invalid_event_rejected_from_aggregation(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    invalid = _event(event_id="", event_type="scope_validation_result", status="pass", dedupe_key="k1")
    valid = _event(event_id="e2", event_type="scope_validation_result", status="blocked", dedupe_key="k2")
    _write_events(event_log, [invalid, valid])

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)
    assert snap["metrics"]["scope_validation"]["pass"] == 0
    assert snap["metrics"]["scope_validation"]["blocked"] == 1
    assert snap["job_stats"]["dedupe"]["invalid_events"] == 1


def test_snapshot_job_empty_log_fallback_full_scan(tmp_path: Path) -> None:
    _write_json(tmp_path / "council_feishu_feedback_mapping_result.json", {"is_mapped": True, "ambiguity_flags": []})

    snap = build_governance_metrics_snapshot_job_result(
        event_log_path=tmp_path / "missing.log",
        artifacts_dir=tmp_path,
        fallback_to_full_scan=True,
    )

    assert snap["source_mode"] == "full_scan_fallback"
    assert "full_scan_fallback_summary" in snap


def test_snapshot_job_empty_log_without_fallback_returns_incremental_zero(tmp_path: Path) -> None:
    snap = build_governance_metrics_snapshot_job_result(
        event_log_path=tmp_path / "missing.log",
        artifacts_dir=tmp_path,
        fallback_to_full_scan=False,
    )

    assert snap["source_mode"] == "incremental"
    assert snap["metrics"]["scope_validation"]["pass"] == 0


def test_snapshot_job_output_write(tmp_path: Path) -> None:
    snapshot = {
        "artifact_type": "governance_metrics_snapshot",
        "schema_version": "governance.metrics.v0.1",
        "generated_at": "2026-03-17T15:00:00+08:00",
        "source_mode": "incremental",
        "metrics": {},
        "by_scope": {},
    }
    out = tmp_path / "snapshot.json"
    write_governance_metrics_snapshot_job_artifact(snapshot, out)
    assert out.exists()


def test_snapshot_job_runner_creates_artifact(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [_event(event_id="e1", event_type="policy_publish_result", status="rolled_back", dedupe_key="k1")],
    )
    out = tmp_path / "snapshot.json"

    result = run_governance_metrics_snapshot_job(
        event_log_path=event_log,
        artifacts_dir=tmp_path,
        output_path=out,
        fallback_to_full_scan=True,
    )

    assert out.exists()
    assert result["metrics"]["policy_publish"]["rolled_back"] == 1


def test_snapshot_job_router_invalid_scope_counted_from_blocked_status(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [_event(event_id="e1", event_type="router_scope_observe_result", status="blocked", dedupe_key="k1")],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)
    assert snap["metrics"]["router_scope_observe"]["observed"] == 1
    assert snap["metrics"]["router_scope_observe"]["warnings"] == 1
    assert snap["metrics"]["router_scope_observe"]["invalid_scope"] == 1


def test_snapshot_job_unknown_event_type_does_not_break_counts(tmp_path: Path) -> None:
    event_log = tmp_path / "events.log"
    _write_events(
        event_log,
        [_event(event_id="e1", event_type="unknown_event", status="ok", dedupe_key="k1")],
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=event_log, artifacts_dir=tmp_path)
    assert snap["source_mode"] == "incremental"
    assert snap["metrics"]["scope_validation"]["pass"] == 0
    assert snap["metrics"]["policy_publish"]["applied"] == 0
