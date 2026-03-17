"""Incremental metrics snapshot from governance event log v0.1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.governance_event_log import DEFAULT_EVENT_LOG_PATH, load_governance_events
from tools.council_bridge.platform_governance_metrics import build_governance_metrics_summary

DEFAULT_SNAPSHOT_PATH = Path("artifacts") / "governance_events_snapshot.json"


def _scope_key(event: dict[str, Any]) -> str:
    ws = str(event.get("workspace_id") or "unknown")
    pj = str(event.get("project_id") or "unknown")
    owner = str(event.get("owner_id") or "unknown")
    return f"workspace:{ws}|project:{pj}|owner:{owner}"


def _count(events: list[dict[str, Any]], event_type: str, status: str | None = None) -> int:
    if status is None:
        return sum(1 for ev in events if ev.get("event_type") == event_type)
    return sum(1 for ev in events if ev.get("event_type") == event_type and str(ev.get("status")) == status)


def build_incremental_metrics_snapshot(
    *,
    event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    artifacts_dir: Path = Path("artifacts"),
    fallback_to_full_scan: bool = True,
) -> dict[str, Any]:
    events, warnings = load_governance_events(event_log_path)

    if not events and fallback_to_full_scan:
        full = build_governance_metrics_summary(artifacts_dir=artifacts_dir)
        return {
            "snapshot_version": "governance.snapshot.v0.1",
            "source": "full_scan_fallback",
            "warnings": warnings + ["event log empty; fallback to full scan"],
            "summary": full,
        }

    scope_validation_total = _count(events, "scope_validation_result")
    scope_validation_pass = _count(events, "scope_validation_result", "pass")
    scope_validation_degraded = _count(events, "scope_validation_result", "degraded_continue")
    scope_validation_blocked = _count(events, "scope_validation_result", "blocked")

    router_observe_total = _count(events, "router_scope_observe_result")
    router_observe_warning = sum(
        1
        for ev in events
        if ev.get("event_type") == "router_scope_observe_result"
        and str(ev.get("status")) in {"degraded_continue", "blocked"}
    )

    publish_total = _count(events, "policy_publish_result")
    publish_applied = _count(events, "policy_publish_result", "applied")
    publish_rejected = _count(events, "policy_publish_result", "rejected")
    publish_rolled_back = _count(events, "policy_publish_result", "rolled_back")

    by_scope: dict[str, dict[str, int]] = {}
    for ev in events:
        key = _scope_key(ev)
        bucket = by_scope.setdefault(
            key,
            {
                "scope_validation_events": 0,
                "router_scope_observe_events": 0,
                "policy_publish_events": 0,
            },
        )
        if ev.get("event_type") == "scope_validation_result":
            bucket["scope_validation_events"] += 1
        if ev.get("event_type") == "router_scope_observe_result":
            bucket["router_scope_observe_events"] += 1
        if ev.get("event_type") == "policy_publish_result":
            bucket["policy_publish_events"] += 1

    return {
        "snapshot_version": "governance.snapshot.v0.1",
        "source": "event_log",
        "event_log_path": event_log_path.as_posix(),
        "warnings": warnings,
        "scope_validation": {
            "total": scope_validation_total,
            "pass": scope_validation_pass,
            "degraded": scope_validation_degraded,
            "blocked": scope_validation_blocked,
        },
        "router_scope_observe": {
            "total": router_observe_total,
            "warning": router_observe_warning,
            "pass": max(0, router_observe_total - router_observe_warning),
        },
        "policy_publish": {
            "total": publish_total,
            "applied": publish_applied,
            "rejected": publish_rejected,
            "rolled_back": publish_rolled_back,
        },
        "by_scope": by_scope,
    }


def write_incremental_metrics_snapshot(snapshot: dict[str, Any], output_path: Path = DEFAULT_SNAPSHOT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
