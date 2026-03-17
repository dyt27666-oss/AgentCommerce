"""Incremental governance event log v0.1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_EVENT_LOG_PATH = Path("artifacts") / "governance_events.log"
DEFAULT_DEDUPE_INDEX_PATH = Path("artifacts") / "governance_events_dedupe_index.json"


@dataclass(slots=True)
class GovernanceEvent:
    event_id: str
    event_type: str
    occurred_at: str
    request_id: str | None
    publish_id: str | None
    workspace_id: str | None
    project_id: str | None
    owner_id: str | None
    source_module: str
    source_artifact: str
    status: str
    payload_summary: dict[str, Any]
    dedupe_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _timestamp_bucket(occurred_at: str) -> str:
    try:
        dt = datetime.fromisoformat(occurred_at)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return str(occurred_at)[:16]


def build_governance_event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: str,
    request_id: str | None,
    publish_id: str | None,
    workspace_id: str | None,
    project_id: str | None,
    owner_id: str | None,
    source_module: str,
    source_artifact: str,
    status: str,
    payload_summary: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> GovernanceEvent:
    payload = payload_summary if isinstance(payload_summary, dict) else {}
    fallback_key = "|".join(
        [
            _safe_text(event_type) or "unknown_event_type",
            _safe_text(source_artifact) or "unknown_source_artifact",
            _safe_text(status) or "unknown_status",
            _timestamp_bucket(_safe_text(occurred_at) or ""),
        ]
    )
    return GovernanceEvent(
        event_id=_safe_text(event_id) or "",
        event_type=_safe_text(event_type) or "",
        occurred_at=_safe_text(occurred_at) or "",
        request_id=_safe_text(request_id),
        publish_id=_safe_text(publish_id),
        workspace_id=_safe_text(workspace_id),
        project_id=_safe_text(project_id),
        owner_id=_safe_text(owner_id),
        source_module=_safe_text(source_module) or "",
        source_artifact=_safe_text(source_artifact) or "",
        status=_safe_text(status) or "",
        payload_summary=payload,
        dedupe_key=_safe_text(dedupe_key) or fallback_key,
    )


def _load_dedupe_index(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {"event_ids": {}, "fallback_keys": {}}, warnings
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        warnings.append("dedupe index corrupted; reinitialized")
        return {"event_ids": {}, "fallback_keys": {}}, warnings
    if not isinstance(data, dict):
        warnings.append("dedupe index invalid root; reinitialized")
        return {"event_ids": {}, "fallback_keys": {}}, warnings
    event_ids = data.get("event_ids") if isinstance(data.get("event_ids"), dict) else {}
    fallback_keys = data.get("fallback_keys") if isinstance(data.get("fallback_keys"), dict) else {}
    return {"event_ids": event_ids, "fallback_keys": fallback_keys}, warnings


def _write_dedupe_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(path: Path, event: GovernanceEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")


def ingest_governance_event(
    event: GovernanceEvent | dict[str, Any],
    *,
    log_path: Path = DEFAULT_EVENT_LOG_PATH,
    dedupe_index_path: Path = DEFAULT_DEDUPE_INDEX_PATH,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    ev = event if isinstance(event, GovernanceEvent) else build_governance_event(**event)

    required = {
        "event_id": ev.event_id,
        "event_type": ev.event_type,
        "occurred_at": ev.occurred_at,
        "source_module": ev.source_module,
        "source_artifact": ev.source_artifact,
        "status": ev.status,
        "dedupe_key": ev.dedupe_key,
    }
    for key, value in required.items():
        if not value:
            errors.append(f"{key} is required")

    if errors:
        return {
            "ingest_status": "invalid",
            "event_id": ev.event_id,
            "dedupe_key": ev.dedupe_key,
            "warnings": warnings,
            "errors": errors,
        }

    index, index_warnings = _load_dedupe_index(dedupe_index_path)
    warnings.extend(index_warnings)

    event_ids = index.get("event_ids", {})
    fallback_keys = index.get("fallback_keys", {})

    if ev.event_id in event_ids or ev.dedupe_key in fallback_keys:
        return {
            "ingest_status": "ignored_duplicate",
            "event_id": ev.event_id,
            "dedupe_key": ev.dedupe_key,
            "warnings": warnings,
            "errors": [],
        }

    _append_event(log_path, ev)
    event_ids[ev.event_id] = ev.occurred_at
    fallback_keys[ev.dedupe_key] = ev.occurred_at
    index["event_ids"] = event_ids
    index["fallback_keys"] = fallback_keys
    _write_dedupe_index(dedupe_index_path, index)

    return {
        "ingest_status": "written",
        "event_id": ev.event_id,
        "dedupe_key": ev.dedupe_key,
        "warnings": warnings,
        "errors": [],
    }


def load_governance_events(log_path: Path = DEFAULT_EVENT_LOG_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not log_path.exists():
        return [], warnings
    events: list[dict[str, Any]] = []
    for line_no, raw in enumerate(log_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            warnings.append(f"skip invalid json line at {line_no}")
            continue
        if isinstance(data, dict):
            events.append(data)
        else:
            warnings.append(f"skip non-object line at {line_no}")
    return events, warnings
