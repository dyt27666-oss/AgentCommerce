from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.runtime_recovery_attempt_runner as rr


def _failure_event(failure_type: str, stage: str = "runtime_unknown") -> dict:
    return {
        "artifact_type": "runtime_failure_event",
        "schema_version": "runtime.failure.v0.1",
        "failure_id": "fail-abc123",
        "related_request_id": "req-1",
        "publish_id": "pub-1",
        "source_module": "test.module",
        "failure_type": failure_type,
        "failure_stage": stage,
        "detected_at": "2026-03-17T20:00:00+08:00",
        "recovery_action": "",
        "recovery_status": "pending",
        "operator": "system",
        "audit_trace": {"exception_type": "ValueError", "exception_message": "x", "stack_hint": "x"},
    }


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_artifact_write_failure_retry_path_success() -> None:
    out = rr.run_recovery_attempt(_failure_event("artifact_write_failure", "artifact_write"), recovery_policy={"force_attempt_result": "success"})
    assert out["recovery_action"] == "retry"
    assert out["attempt_result"] == "success"
    assert out["max_attempts"] == 3


def test_event_log_write_failure_retry_path_failed_retryable() -> None:
    out = rr.run_recovery_attempt(_failure_event("event_log_write_failure", "event_ingest"), recovery_policy={"stub_should_fail": True, "previous_attempt_no": 0})
    assert out["recovery_action"] == "retry"
    assert out["attempt_result"] == "failed_retryable"


def test_snapshot_job_failure_retry_path() -> None:
    out = rr.run_recovery_attempt(_failure_event("snapshot_job_failure", "snapshot_job"), recovery_policy={"stub_should_fail": True, "previous_attempt_no": 2})
    assert out["recovery_action"] == "retry"
    assert out["attempt_no"] == 3
    assert out["attempt_result"] == "failed_terminal"


def test_ingress_router_failure_manual_required() -> None:
    out = rr.run_recovery_attempt(_failure_event("ingress_router_failure", "ingress"))
    assert out["recovery_action"] == "manual_required"
    assert out["attempt_result"] == "manual_required"
    assert out["max_attempts"] == 0


def test_normalization_failure_manual_required() -> None:
    out = rr.run_recovery_attempt(_failure_event("normalization_failure", "normalization"))
    assert out["recovery_action"] == "manual_required"
    assert out["attempt_result"] == "manual_required"


def test_publish_apply_failure_manual_required_conservative() -> None:
    out = rr.run_recovery_attempt(_failure_event("publish_apply_failure", "publish_apply"), recovery_policy={"recovery_action": "retry"})
    assert out["recovery_action"] == "manual_required"
    assert out["attempt_result"] == "manual_required"


def test_unknown_failure_conservative_manual_required() -> None:
    out = rr.run_recovery_attempt(_failure_event("unknown_runtime_failure", "runtime_unknown"))
    assert out["recovery_action"] == "manual_required"


def test_idempotency_key_stable() -> None:
    event = _failure_event("artifact_write_failure", "artifact_write")
    out1 = rr.run_recovery_attempt(event, recovery_policy={"attempt_no": 1})
    out2 = rr.run_recovery_attempt(event, recovery_policy={"attempt_no": 1})
    assert out1["idempotency_key"] == out2["idempotency_key"]


def test_attempt_no_increment_from_previous_attempt_no() -> None:
    out = rr.run_recovery_attempt(_failure_event("artifact_write_failure"), recovery_policy={"previous_attempt_no": 2})
    assert out["attempt_no"] == 3


def test_emit_runtime_recovery_attempt_event_fallback(tmp_path: Path, monkeypatch) -> None:
    def _raise_ingest(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(rr, "ingest_governance_event", _raise_ingest)
    artifact = rr.run_recovery_attempt(_failure_event("artifact_write_failure"), recovery_policy={"attempt_no": 1})

    fallback = tmp_path / "fallback.log"
    out = rr.emit_runtime_recovery_attempt_event(
        artifact,
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        fallback_log_path=fallback,
    )
    assert out["emit_status"] == "fallback_logged"
    assert fallback.exists()


def test_run_and_emit_recovery_attempt_writes_artifact_and_event(tmp_path: Path) -> None:
    failure = _failure_event("artifact_write_failure", "artifact_write")
    result = rr.run_and_emit_recovery_attempt(
        failure,
        recovery_policy={"force_attempt_result": "success", "attempt_no": 1},
        operator="system",
        artifact_output_path=tmp_path / "attempt.json",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        fallback_log_path=tmp_path / "fallback.log",
        event_context={"workspace_id": "ws1", "project_id": "pj1", "owner_id": "owner1"},
    )
    assert (tmp_path / "attempt.json").exists()
    assert result["event_emit"]["emit_status"] == "event_logged"
    events = _read_jsonl(tmp_path / "events.log")
    assert events[-1]["event_type"] == "runtime_recovery_attempt"


def test_ignore_action_result_ignored() -> None:
    out = rr.run_recovery_attempt(_failure_event("unknown_runtime_failure"), recovery_policy={"recovery_action": "ignore"})
    assert out["recovery_action"] == "ignore"
    assert out["attempt_result"] == "ignored"
