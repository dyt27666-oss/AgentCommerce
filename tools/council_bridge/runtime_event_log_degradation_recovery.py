"""Runtime event log degradation recovery v0.1.

Standardizes ingest failure degradation records, queueing, and replay for
observability event chain only.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.governance_event_log import (
    DEFAULT_DEDUPE_INDEX_PATH,
    DEFAULT_EVENT_LOG_PATH,
    GovernanceEvent,
    build_governance_event,
    ingest_governance_event,
)

RUNTIME_DEGRADATION_SCHEMA_VERSION = "runtime.degradation.v0.1"
DEFAULT_DEGRADATION_ARTIFACT_PATH = Path("artifacts") / "runtime_event_log_degradation.json"
DEFAULT_DEGRADATION_QUEUE_PATH = Path("artifacts") / "runtime_event_log_degradation_queue.jsonl"
DEFAULT_DEGRADATION_FALLBACK_LOG_PATH = Path("artifacts") / "runtime_event_log_degradation_fallback.log"

QUEUE_QUEUED = "queued"
QUEUE_REPLAYED = "replayed"
QUEUE_REPLAY_FAILED = "replay_failed"
QUEUE_ABANDONED = "abandoned"
QUEUE_STATUSES = {QUEUE_QUEUED, QUEUE_REPLAYED, QUEUE_REPLAY_FAILED, QUEUE_ABANDONED}


REPLAY_CANDIDATE_STATUSES = {QUEUE_QUEUED, QUEUE_REPLAY_FAILED}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _write_queue(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(x, ensure_ascii=False) for x in items)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _to_event_dict(event: GovernanceEvent | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(event, GovernanceEvent):
        return event.to_dict()
    if isinstance(event, dict):
        return dict(event)
    return {}


def _infer_reason(ingest_result: dict[str, Any] | None, context: dict[str, Any]) -> str:
    if isinstance(ingest_result, dict):
        status = _safe_text(ingest_result.get("ingest_status"))
        if status == "invalid":
            return "ingest_invalid"
        if status == "ignored_duplicate":
            return "ingest_duplicate"
    if _safe_text(context.get("exception")):
        return "ingest_exception"
    if _safe_text(context.get("warning")):
        return "ingest_warning"
    return "ingest_unknown_failure"


def _build_degradation_artifact(
    *,
    failed_event: dict[str, Any],
    ingest_result: dict[str, Any] | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    degradation_id = f"degrade-{uuid.uuid4().hex}"
    related_failure_id = _safe_text(context.get("related_failure_id")) or None
    related_request_id = (
        _safe_text(context.get("related_request_id"))
        or _safe_text(failed_event.get("request_id"))
        or None
    )
    publish_id = (
        _safe_text(context.get("publish_id"))
        or _safe_text(failed_event.get("publish_id"))
        or None
    )
    source_module = _safe_text(context.get("source_module")) or _safe_text(failed_event.get("source_module")) or "runtime_unknown"
    original_event_type = _safe_text(failed_event.get("event_type")) or "unknown_event"

    return {
        "artifact_type": "runtime_event_log_degradation",
        "schema_version": RUNTIME_DEGRADATION_SCHEMA_VERSION,
        "degradation_id": degradation_id,
        "related_failure_id": related_failure_id,
        "related_request_id": related_request_id,
        "publish_id": publish_id,
        "source_module": source_module,
        "original_event_type": original_event_type,
        "detected_at": _now_iso(),
        "degradation_reason": _infer_reason(ingest_result, context),
        "queue_status": QUEUE_QUEUED,
        "replay_status": "pending",
        "operator": _safe_text(context.get("operator")) or "system",
        "audit_trace": {
            "ingest_result": ingest_result if isinstance(ingest_result, dict) else {},
            "failed_event_id": _safe_text(failed_event.get("event_id")) or None,
            "exception": _safe_text(context.get("exception")) or None,
            "warning": _safe_text(context.get("warning")) or None,
        },
    }


def write_runtime_event_log_degradation_artifact(
    artifact: dict[str, Any],
    output_path: Path = DEFAULT_DEGRADATION_ARTIFACT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def handle_event_log_degradation(
    failed_event: dict | GovernanceEvent | None = None,
    ingest_result: dict | None = None,
    context: dict | None = None,
    *,
    artifact_path: Path = DEFAULT_DEGRADATION_ARTIFACT_PATH,
    queue_path: Path = DEFAULT_DEGRADATION_QUEUE_PATH,
    fallback_log_path: Path = DEFAULT_DEGRADATION_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    event_dict = _to_event_dict(failed_event)

    try:
        artifact = _build_degradation_artifact(
            failed_event=event_dict,
            ingest_result=ingest_result if isinstance(ingest_result, dict) else None,
            context=ctx,
        )
        record = {
            "degradation": artifact,
            "failed_event": event_dict,
            "ingest_result": ingest_result if isinstance(ingest_result, dict) else {},
            "replay_attempts": 0,
            "error_detail": "",
            "last_replay_at": None,
        }

        write_runtime_event_log_degradation_artifact(artifact, artifact_path)
        _append_jsonl(queue_path, record)

        return {
            "degradation_id": artifact["degradation_id"],
            "queue_status": artifact["queue_status"],
            "artifact_path": artifact_path.as_posix(),
            "queue_path": queue_path.as_posix(),
            "handle_status": "queued",
        }
    except Exception as exc:
        try:
            _append_jsonl(
                fallback_log_path,
                {
                    "timestamp": _now_iso(),
                    "reason": "handle_event_log_degradation_exception",
                    "error": str(exc),
                    "failed_event": event_dict,
                    "ingest_result": ingest_result if isinstance(ingest_result, dict) else {},
                },
            )
        except Exception:
            pass
        return {
            "degradation_id": "",
            "queue_status": "",
            "artifact_path": artifact_path.as_posix(),
            "queue_path": queue_path.as_posix(),
            "handle_status": "fallback_logged",
        }


def _normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    degradation = item.get("degradation") if isinstance(item.get("degradation"), dict) else {}
    if _safe_text(degradation.get("queue_status")) not in QUEUE_STATUSES:
        degradation["queue_status"] = QUEUE_QUEUED
    out = {
        "degradation": degradation,
        "failed_event": item.get("failed_event") if isinstance(item.get("failed_event"), dict) else {},
        "ingest_result": item.get("ingest_result") if isinstance(item.get("ingest_result"), dict) else {},
        "replay_attempts": int(item.get("replay_attempts") or 0),
        "error_detail": _safe_text(item.get("error_detail")),
        "last_replay_at": item.get("last_replay_at"),
    }
    return out


def replay_degraded_events(
    queue_path: str | Path | None = None,
    operator: str = "system",
    *,
    governance_event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
    max_replay_attempts: int = 3,
    fallback_log_path: Path = DEFAULT_DEGRADATION_FALLBACK_LOG_PATH,
) -> dict[str, Any]:
    qpath = Path(queue_path) if queue_path else DEFAULT_DEGRADATION_QUEUE_PATH

    try:
        raw_items = _load_queue(qpath)
        items = [_normalize_record(x) for x in raw_items]
        updated: list[dict[str, Any]] = []

        replayed = 0
        replay_failed = 0
        abandoned = 0
        skipped = 0

        seen_ids: set[str] = set()
        for item in items:
            degradation = item["degradation"]
            failed_event = item["failed_event"]
            did = _safe_text(degradation.get("degradation_id"))
            if did and did in seen_ids:
                skipped += 1
                continue
            if did:
                seen_ids.add(did)

            queue_status = _safe_text(degradation.get("queue_status")) or QUEUE_QUEUED
            attempts = int(item.get("replay_attempts") or 0)

            if queue_status not in REPLAY_CANDIDATE_STATUSES:
                skipped += 1
                updated.append(item)
                continue

            if attempts >= max_replay_attempts:
                degradation["queue_status"] = QUEUE_ABANDONED
                degradation["replay_status"] = "abandoned"
                item["error_detail"] = "max replay attempts exceeded"
                abandoned += 1
                updated.append(item)
                continue

            try:
                event_obj: GovernanceEvent | dict[str, Any]
                if failed_event:
                    event_obj = failed_event
                else:
                    # Incomplete event payload, degrade safely.
                    degradation["queue_status"] = QUEUE_REPLAY_FAILED
                    degradation["replay_status"] = "failed"
                    item["replay_attempts"] = attempts + 1
                    item["last_replay_at"] = _now_iso()
                    item["error_detail"] = "missing failed_event payload"
                    replay_failed += 1
                    updated.append(item)
                    continue

                result = ingest_governance_event(
                    event_obj,
                    log_path=governance_event_log_path,
                    dedupe_index_path=governance_dedupe_index_path,
                )
                item["replay_attempts"] = attempts + 1
                item["last_replay_at"] = _now_iso()

                if result.get("ingest_status") in {"written", "ignored_duplicate"}:
                    degradation["queue_status"] = QUEUE_REPLAYED
                    degradation["replay_status"] = "success"
                    item["error_detail"] = ""
                    replayed += 1
                else:
                    if item["replay_attempts"] >= max_replay_attempts:
                        degradation["queue_status"] = QUEUE_ABANDONED
                        degradation["replay_status"] = "abandoned"
                        abandoned += 1
                    else:
                        degradation["queue_status"] = QUEUE_REPLAY_FAILED
                        degradation["replay_status"] = "failed"
                        replay_failed += 1
                    item["error_detail"] = "; ".join(result.get("errors") or ["replay ingest invalid"])
                updated.append(item)
            except Exception as exc:
                item["replay_attempts"] = attempts + 1
                item["last_replay_at"] = _now_iso()
                if item["replay_attempts"] >= max_replay_attempts:
                    degradation["queue_status"] = QUEUE_ABANDONED
                    degradation["replay_status"] = "abandoned"
                    abandoned += 1
                else:
                    degradation["queue_status"] = QUEUE_REPLAY_FAILED
                    degradation["replay_status"] = "failed"
                    replay_failed += 1
                item["error_detail"] = str(exc)
                updated.append(item)

        _write_queue(qpath, updated)

        return {
            "replay_status": "completed",
            "operator": _safe_text(operator) or "system",
            "queue_path": qpath.as_posix(),
            "processed": len(updated),
            "replayed": replayed,
            "replay_failed": replay_failed,
            "abandoned": abandoned,
            "skipped": skipped,
            "max_replay_attempts": max_replay_attempts,
        }
    except Exception as exc:
        try:
            _append_jsonl(
                fallback_log_path,
                {
                    "timestamp": _now_iso(),
                    "reason": "replay_degraded_events_exception",
                    "error": str(exc),
                    "queue_path": qpath.as_posix(),
                },
            )
        except Exception:
            pass
        return {
            "replay_status": "failed",
            "operator": _safe_text(operator) or "system",
            "queue_path": qpath.as_posix(),
            "processed": 0,
            "replayed": 0,
            "replay_failed": 0,
            "abandoned": 0,
            "skipped": 0,
            "max_replay_attempts": max_replay_attempts,
        }
