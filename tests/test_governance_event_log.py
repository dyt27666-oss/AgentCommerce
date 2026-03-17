from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.governance_event_log import (
    build_governance_event,
    ingest_governance_event,
    load_governance_events,
)


def test_event_append_success(tmp_path: Path) -> None:
    event = build_governance_event(
        event_id="evt-1",
        event_type="scope_validation_result",
        occurred_at="2026-03-17T10:00:00+08:00",
        request_id="req-1",
        publish_id=None,
        workspace_id="ws1",
        project_id="pj1",
        owner_id="ownerA",
        source_module="test",
        source_artifact="artifacts/a.json",
        status="pass",
        payload_summary={"x": 1},
    )
    result = ingest_governance_event(event, log_path=tmp_path / "events.log", dedupe_index_path=tmp_path / "dedupe.json")
    assert result["ingest_status"] == "written"


def test_duplicate_event_id_ignored(tmp_path: Path) -> None:
    kwargs = dict(
        event_id="evt-dup",
        event_type="scope_validation_result",
        occurred_at="2026-03-17T10:00:00+08:00",
        request_id=None,
        publish_id=None,
        workspace_id="ws1",
        project_id="pj1",
        owner_id="ownerA",
        source_module="test",
        source_artifact="artifacts/a.json",
        status="pass",
        payload_summary={},
    )
    ingest_governance_event(build_governance_event(**kwargs), log_path=tmp_path / "events.log", dedupe_index_path=tmp_path / "dedupe.json")
    second = ingest_governance_event(build_governance_event(**kwargs), log_path=tmp_path / "events.log", dedupe_index_path=tmp_path / "dedupe.json")
    assert second["ingest_status"] == "ignored_duplicate"


def test_duplicate_fallback_key_ignored(tmp_path: Path) -> None:
    e1 = build_governance_event(
        event_id="evt-a",
        event_type="scope_validation_result",
        occurred_at="2026-03-17T10:00:11+08:00",
        request_id=None,
        publish_id=None,
        workspace_id="ws1",
        project_id="pj1",
        owner_id="ownerA",
        source_module="test",
        source_artifact="artifacts/same.json",
        status="pass",
        payload_summary={},
        dedupe_key="fallback-key-1",
    )
    e2 = build_governance_event(
        event_id="evt-b",
        event_type="scope_validation_result",
        occurred_at="2026-03-17T10:00:55+08:00",
        request_id=None,
        publish_id=None,
        workspace_id="ws1",
        project_id="pj1",
        owner_id="ownerA",
        source_module="test",
        source_artifact="artifacts/same.json",
        status="pass",
        payload_summary={},
        dedupe_key="fallback-key-1",
    )
    ingest_governance_event(e1, log_path=tmp_path / "events.log", dedupe_index_path=tmp_path / "dedupe.json")
    second = ingest_governance_event(e2, log_path=tmp_path / "events.log", dedupe_index_path=tmp_path / "dedupe.json")
    assert second["ingest_status"] == "ignored_duplicate"


def test_dedupe_corrupted_fallback_warning(tmp_path: Path) -> None:
    dedupe = tmp_path / "dedupe.json"
    dedupe.write_text("{bad json", encoding="utf-8")
    event = build_governance_event(
        event_id="evt-corrupt",
        event_type="scope_validation_result",
        occurred_at="2026-03-17T10:00:00+08:00",
        request_id=None,
        publish_id=None,
        workspace_id="ws1",
        project_id="pj1",
        owner_id="ownerA",
        source_module="test",
        source_artifact="artifacts/a.json",
        status="pass",
        payload_summary={},
    )
    result = ingest_governance_event(event, log_path=tmp_path / "events.log", dedupe_index_path=dedupe)
    assert result["ingest_status"] == "written"
    assert any("reinitialized" in w for w in result["warnings"])


def test_invalid_event_rejected(tmp_path: Path) -> None:
    result = ingest_governance_event(
        {
            "event_id": "",
            "event_type": "",
            "occurred_at": "",
            "request_id": None,
            "publish_id": None,
            "workspace_id": None,
            "project_id": None,
            "owner_id": None,
            "source_module": "",
            "source_artifact": "",
            "status": "",
            "payload_summary": {},
            "dedupe_key": "",
        },
        log_path=tmp_path / "events.log",
        dedupe_index_path=tmp_path / "dedupe.json",
    )
    assert result["ingest_status"] == "invalid"
    assert len(result["errors"]) > 0


def test_load_events_skip_invalid_lines(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    log.write_text('{"event_id":"ok","event_type":"x","occurred_at":"t","request_id":null,"publish_id":null,"workspace_id":null,"project_id":null,"owner_id":null,"source_module":"m","source_artifact":"a","status":"s","payload_summary":{},"dedupe_key":"k"}\nnot-json\n', encoding="utf-8")
    events, warnings = load_governance_events(log)
    assert len(events) == 1
    assert len(warnings) >= 1
