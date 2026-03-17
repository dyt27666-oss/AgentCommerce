from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.runtime_event_log_degradation_recovery as degr


def _event(event_id: str = "evt-1") -> dict:
    return {
        "event_id": event_id,
        "event_type": "runtime_failure_event",
        "occurred_at": "2026-03-17T23:00:00+08:00",
        "request_id": "req-1",
        "publish_id": "pub-1",
        "workspace_id": "ws1",
        "project_id": "pj1",
        "owner_id": "owner1",
        "source_module": "m",
        "source_artifact": "a",
        "status": "pending",
        "payload_summary": {},
        "dedupe_key": f"k-{event_id}",
    }


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_ingest_invalid_queued(tmp_path: Path) -> None:
    out = degr.handle_event_log_degradation(
        failed_event=_event(),
        ingest_result={"ingest_status": "invalid", "errors": ["x"]},
        context={"source_module": "runtime_failure_event_normalizer"},
        artifact_path=tmp_path / "artifact.json",
        queue_path=tmp_path / "queue.jsonl",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert out["handle_status"] == "queued"
    queue = _read_jsonl(tmp_path / "queue.jsonl")
    assert queue[0]["degradation"]["queue_status"] == "queued"


def test_ingest_exception_queued(tmp_path: Path) -> None:
    out = degr.handle_event_log_degradation(
        failed_event=_event("evt-2"),
        ingest_result=None,
        context={"source_module": "runtime_recovery_attempt_runner", "exception": "disk full"},
        artifact_path=tmp_path / "artifact.json",
        queue_path=tmp_path / "queue.jsonl",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert out["handle_status"] == "queued"
    queue = _read_jsonl(tmp_path / "queue.jsonl")
    assert queue[0]["degradation"]["degradation_reason"] == "ingest_exception"


def test_replay_success(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event=_event("evt-3"),
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    out = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    assert out["replayed"] == 1
    queue = _read_jsonl(tmp_path / "queue.jsonl")
    assert queue[0]["degradation"]["queue_status"] == "replayed"


def test_replay_failed(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event={"event_type": "x"},
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    out = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        max_replay_attempts=3,
    )
    assert out["replay_failed"] == 1


def test_max_replay_attempts_abandoned(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event={"event_type": "x"},
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    for _ in range(4):
        degr.replay_degraded_events(
            queue_path=tmp_path / "queue.jsonl",
            governance_event_log_path=tmp_path / "events.log",
            governance_dedupe_index_path=tmp_path / "dedupe.json",
            max_replay_attempts=3,
        )
    queue = _read_jsonl(tmp_path / "queue.jsonl")
    assert queue[0]["degradation"]["queue_status"] == "abandoned"


def test_queue_status_transitions(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event=_event("evt-4"),
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    q1 = _read_jsonl(tmp_path / "queue.jsonl")
    assert q1[0]["degradation"]["queue_status"] == "queued"
    degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    q2 = _read_jsonl(tmp_path / "queue.jsonl")
    assert q2[0]["degradation"]["queue_status"] == "replayed"


def test_idempotent_replay_skips_replayed(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event=_event("evt-5"),
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    first = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    second = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    assert first["replayed"] == 1
    assert second["replayed"] == 0
    assert second["skipped"] >= 1


def test_incomplete_event_safe_degradation(tmp_path: Path) -> None:
    degr.handle_event_log_degradation(
        failed_event={"event_id": "e"},
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    out = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    assert out["replay_failed"] == 1


def test_no_unhandled_exception_on_bad_queue_path(tmp_path: Path) -> None:
    out = degr.replay_degraded_events(
        queue_path=tmp_path / "bad" / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
    )
    assert out["replay_status"] in {"completed", "failed"}


def test_fallback_log_coexists(tmp_path: Path, monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise OSError("queue write fail")

    monkeypatch.setattr(degr, "write_runtime_event_log_degradation_artifact", _boom)
    out = degr.handle_event_log_degradation(
        failed_event=_event("evt-6"),
        ingest_result={"ingest_status": "invalid"},
        context={},
        artifact_path=tmp_path / "artifact.json",
        queue_path=tmp_path / "queue.jsonl",
        fallback_log_path=tmp_path / "fallback.log",
    )
    assert out["handle_status"] == "fallback_logged"
    assert (tmp_path / "fallback.log").exists()


def test_replay_failed_then_success(tmp_path: Path) -> None:
    # first queue an incomplete event causing replay_failed
    degr.handle_event_log_degradation(
        failed_event={"event_id": "evt-7"},
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        max_replay_attempts=3,
    )

    # append a valid queued event; ensure replay still works for queued items
    degr.handle_event_log_degradation(
        failed_event=_event("evt-8"),
        ingest_result={"ingest_status": "invalid"},
        context={},
        queue_path=tmp_path / "queue.jsonl",
    )
    out = degr.replay_degraded_events(
        queue_path=tmp_path / "queue.jsonl",
        governance_event_log_path=tmp_path / "events.log",
        governance_dedupe_index_path=tmp_path / "dedupe.json",
        max_replay_attempts=3,
    )
    assert out["replayed"] >= 1
