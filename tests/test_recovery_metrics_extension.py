from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.governance_metrics_snapshot_job import build_governance_metrics_snapshot_job_result


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in events) + "\n", encoding="utf-8")


def _event(*, event_id: str, event_type: str, status: str, dedupe_key: str, payload_summary: dict | None = None, workspace_id: str = "ws", project_id: str = "pj", owner_id: str = "owner") -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-03-18T01:00:00+08:00",
        "request_id": "req-1",
        "publish_id": "pub-1",
        "workspace_id": workspace_id,
        "project_id": project_id,
        "owner_id": owner_id,
        "source_module": "test",
        "source_artifact": "artifacts/source.json",
        "status": status,
        "payload_summary": payload_summary or {},
        "dedupe_key": dedupe_key,
    }


def test_failure_metrics_aggregation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_failure_event", status="pending", dedupe_key="k1", payload_summary={"failure_type": "artifact_write_failure", "failure_stage": "artifact_write"}),
            _event(event_id="e2", event_type="runtime_failure_event", status="pending", dedupe_key="k2", payload_summary={"failure_type": "event_log_write_failure", "failure_stage": "event_ingest"}),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    assert snap["metrics"]["runtime_failure"]["total"] == 2
    assert snap["metrics"]["runtime_failure"]["by_failure_type"]["artifact_write_failure"] == 1
    assert snap["metrics"]["runtime_failure"]["by_failure_stage"]["event_ingest"] == 1


def test_recovery_attempt_metrics_aggregation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_recovery_attempt", status="success", dedupe_key="k1"),
            _event(event_id="e2", event_type="runtime_recovery_attempt", status="manual_required", dedupe_key="k2"),
            _event(event_id="e3", event_type="runtime_recovery_attempt", status="failed_retryable", dedupe_key="k3"),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    m = snap["metrics"]["runtime_recovery_attempt"]
    assert m["total"] == 3
    assert m["success"] == 1
    assert m["manual_required"] == 1
    assert m["failed_retryable"] == 1


def test_reconcile_metrics_aggregation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_reconcile_report", status="reconciled", dedupe_key="k1"),
            _event(event_id="e2", event_type="runtime_reconcile_report", status="manual_required", dedupe_key="k2"),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    assert snap["metrics"]["runtime_reconcile"]["reconciled"] == 1
    assert snap["metrics"]["runtime_reconcile"]["manual_required"] == 1


def test_degradation_metrics_aggregation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_event_log_degradation", status="queued", dedupe_key="k1"),
            _event(event_id="e2", event_type="runtime_event_log_degradation", status="replayed", dedupe_key="k2"),
            _event(event_id="e3", event_type="runtime_event_log_degradation", status="abandoned", dedupe_key="k3"),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    d = snap["metrics"]["runtime_event_log_degradation"]
    assert d["queued"] == 1
    assert d["replayed"] == 1
    assert d["abandoned"] == 1


def test_recovery_quality_ratios(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_recovery_attempt", status="success", dedupe_key="k1"),
            _event(event_id="e2", event_type="runtime_recovery_attempt", status="manual_required", dedupe_key="k2"),
            _event(event_id="e3", event_type="runtime_event_log_degradation", status="replayed", dedupe_key="k3"),
            _event(event_id="e4", event_type="runtime_event_log_degradation", status="replay_failed", dedupe_key="k4"),
            _event(event_id="e5", event_type="runtime_event_log_degradation", status="abandoned", dedupe_key="k5"),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    q = snap["metrics"]["recovery_quality"]
    assert q["recovery_rate"] == 0.5
    assert q["manual_intervention_rate"] == 0.5
    assert q["replay_success_rate"] == round(1 / 3, 4)
    assert q["abandonment_rate"] == round(1 / 3, 4)


def test_by_scope_recovery_aggregation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_recovery_attempt", status="success", dedupe_key="k1", workspace_id="ws1", project_id="p1", owner_id="o1"),
            _event(event_id="e2", event_type="runtime_failure_event", status="pending", dedupe_key="k2", payload_summary={"failure_type": "artifact_write_failure", "failure_stage": "artifact_write"}, workspace_id="ws1", project_id="p1", owner_id="o1"),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    key = "workspace:ws1|project:p1|owner:o1"
    assert snap["by_scope"][key]["runtime_recovery_attempt"]["success"] == 1
    assert snap["by_scope"][key]["runtime_failure"]["total"] == 1


def test_unknown_scope_bucket_not_dropped(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(
        log,
        [
            _event(event_id="e1", event_type="runtime_recovery_attempt", status="ignored", dedupe_key="k1", workspace_id="", project_id="", owner_id=""),
        ],
    )
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    assert "workspace:unknown|project:unknown|owner:unknown" in snap["by_scope"]


def test_mixed_source_mode_when_recovery_events_missing_but_artifacts_present(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    # only non-recovery event in event log
    _write_events(log, [_event(event_id="e1", event_type="scope_validation_result", status="pass", dedupe_key="k1")])

    # recovery artifact for supplement
    _write_json(
        tmp_path / "runtime_failure_event_sample.json",
        {
            "artifact_type": "runtime_failure_event",
            "failure_type": "artifact_write_failure",
            "failure_stage": "artifact_write",
        },
    )

    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path, fallback_to_full_scan=True)
    assert snap["source_mode"] == "mixed"
    assert snap["metrics"]["runtime_failure"]["total"] == 1


def test_empty_data_safe_and_old_structure_kept(tmp_path: Path) -> None:
    snap = build_governance_metrics_snapshot_job_result(
        event_log_path=tmp_path / "missing.log",
        artifacts_dir=tmp_path,
        fallback_to_full_scan=False,
    )
    assert snap["metrics"]["scope_validation"]["pass"] == 0
    assert "runtime_failure" in snap["metrics"]
    assert "policy_publish" in snap["metrics"]


def test_full_scan_fallback_source_mode_and_recovery_from_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runtime_recovery_attempt_x.json",
        {
            "artifact_type": "runtime_recovery_attempt",
            "attempt_result": "manual_required",
        },
    )
    snap = build_governance_metrics_snapshot_job_result(
        event_log_path=tmp_path / "missing.log",
        artifacts_dir=tmp_path,
        fallback_to_full_scan=True,
    )
    assert snap["source_mode"] == "full_scan_fallback"
    assert snap["metrics"]["runtime_recovery_attempt"]["manual_required"] == 1


def test_zero_denominator_ratio_is_zero(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    _write_events(log, [_event(event_id="e1", event_type="scope_validation_result", status="pass", dedupe_key="k1")])
    snap = build_governance_metrics_snapshot_job_result(event_log_path=log, artifacts_dir=tmp_path)
    q = snap["metrics"]["recovery_quality"]
    assert q["recovery_rate"] == 0.0
    assert q["manual_intervention_rate"] == 0.0
    assert q["abandonment_rate"] == 0.0
    assert q["replay_success_rate"] == 0.0
