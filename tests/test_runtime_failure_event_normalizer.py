from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.runtime_failure_event_normalizer as rfn


def _read_jsonl(path: Path) -> list[dict]:
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [json.loads(x) for x in lines]


def test_normalize_router_parse_failure() -> None:
    out = rfn.normalize_failure_event(
        exception=ValueError("parse failed"),
        failure_stage="ingress",
        source_module="feishu_message_router",
        context={"request_id": "req-1"},
    )
    assert out["failure_type"] == "ingress_router_failure"
    assert out["failure_stage"] == "ingress"


def test_normalize_normalization_exception() -> None:
    out = rfn.normalize_failure_event(
        exception=RuntimeError("normalization explode"),
        failure_stage="normalization",
        source_module="owner_intent_normalization",
    )
    assert out["failure_type"] == "normalization_failure"


def test_normalize_artifact_write_failure_from_alias() -> None:
    out = rfn.normalize_failure_event(
        failure_type="artifact_io_error",
        failure_stage="artifact_write",
        source_module="policy_publish_fsm",
    )
    assert out["failure_type"] == "artifact_write_failure"


def test_normalize_publish_apply_failure_from_stage() -> None:
    out = rfn.normalize_failure_event(
        failure_stage="publish_apply",
        source_module="policy_publish_fsm",
    )
    assert out["failure_type"] == "publish_apply_failure"


def test_normalize_unknown_exception_maps_unknown_failure() -> None:
    out = rfn.normalize_failure_event(
        exception=Exception("boom"),
        failure_stage="something_unknown",
        source_module="unknown_module",
    )
    assert out["failure_type"] == "unknown_runtime_failure"
    assert out["failure_stage"] == "runtime_unknown"


def test_missing_context_fields_safe_defaults() -> None:
    out = rfn.normalize_failure_event(source_module="router")
    assert out["related_request_id"] is None
    assert out["publish_id"] is None
    assert out["operator"] == "system"


def test_failure_id_uniqueness() -> None:
    a = rfn.normalize_failure_event(source_module="m")
    b = rfn.normalize_failure_event(source_module="m")
    assert a["failure_id"] != b["failure_id"]


def test_emit_runtime_failure_event_success_writes_event_log(tmp_path: Path) -> None:
    log_path = tmp_path / "events.log"
    dedupe_path = tmp_path / "events_dedupe.json"
    fallback_path = tmp_path / "fallback.log"

    result = rfn.emit_runtime_failure_event(
        exception=ValueError("bad payload"),
        failure_stage="ingress",
        source_module="feishu_message_router",
        context={"request_id": "req-2", "workspace_id": "ws1", "project_id": "pj1", "owner_id": "ownerA"},
        governance_event_log_path=log_path,
        governance_dedupe_index_path=dedupe_path,
        fallback_log_path=fallback_path,
    )

    assert result["emit_status"] == "event_logged"
    assert log_path.exists()
    events = _read_jsonl(log_path)
    assert events[-1]["event_type"] == "runtime_failure_event"
    assert not fallback_path.exists()


def test_emit_runtime_failure_event_fallback_when_ingest_invalid(tmp_path: Path, monkeypatch) -> None:
    def _fake_ingest(*args, **kwargs):
        return {"ingest_status": "invalid", "errors": ["bad ingest"]}

    monkeypatch.setattr(rfn, "ingest_governance_event", _fake_ingest)

    fallback_path = tmp_path / "fallback.log"
    result = rfn.emit_runtime_failure_event(
        exception=RuntimeError("ingest invalid"),
        failure_stage="event_ingest",
        source_module="governance_event_log",
        fallback_log_path=fallback_path,
    )

    assert result["emit_status"] == "fallback_logged"
    assert fallback_path.exists()


def test_emit_runtime_failure_event_fallback_when_ingest_raises(tmp_path: Path, monkeypatch) -> None:
    def _raise_ingest(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(rfn, "ingest_governance_event", _raise_ingest)

    fallback_path = tmp_path / "fallback.log"
    result = rfn.emit_runtime_failure_event(
        exception=RuntimeError("outer"),
        failure_stage="event_ingest",
        source_module="governance_event_log",
        fallback_log_path=fallback_path,
    )

    assert result["emit_status"] == "fallback_logged"
    assert fallback_path.exists()


def test_event_log_fallback_does_not_raise_when_fallback_write_fails(tmp_path: Path, monkeypatch) -> None:
    def _raise_ingest(*args, **kwargs):
        raise OSError("ingest failed")

    def _raise_fallback(*args, **kwargs):
        raise OSError("fallback failed")

    monkeypatch.setattr(rfn, "ingest_governance_event", _raise_ingest)
    monkeypatch.setattr(rfn, "_append_fallback_log", _raise_fallback)

    result = rfn.emit_runtime_failure_event(
        exception=RuntimeError("x"),
        failure_stage="event_ingest",
        source_module="m",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert result["emit_status"] == "fallback_logged"


def test_stage_alias_mapping_event_log_to_event_ingest() -> None:
    out = rfn.normalize_failure_event(
        failure_stage="event_log",
        source_module="governance_event_log",
    )
    assert out["failure_stage"] == "event_ingest"
    assert out["failure_type"] == "event_log_write_failure"
