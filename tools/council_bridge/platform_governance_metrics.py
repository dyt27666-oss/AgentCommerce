"""Governance metrics summary v0.1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACTS_DIR = Path("artifacts")
DEFAULT_SUMMARY_PATH = Path("artifacts") / "council_governance_metrics_summary.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _scope_key(record: dict[str, Any]) -> str:
    ws = str(record.get("workspace_id") or "unknown")
    pj = str(record.get("project_id") or "unknown")
    owner = str(record.get("sender_id") or record.get("confirmed_by") or record.get("owner_id") or "unknown")
    return f"workspace:{ws}|project:{pj}|owner:{owner}"


def _iter_records(artifacts_dir: Path) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "feedback_mapping": [],
        "role_rework_mapping": [],
        "state_validation": [],
        "apply": [],
        "dispatch": [],
        "route": [],
    }

    patterns = {
        "feedback_mapping": "**/*feedback_mapping*.json",
        "role_rework_mapping": "**/*role_rework_mapping*.json",
        "state_validation": "**/*state_transition_result*.json",
        "apply": "**/*owner_confirmed*apply*.json",
        "dispatch": "**/*execution_dispatch_result*.json",
        "route": "**/*message_route_result*.json",
    }

    for key, pattern in patterns.items():
        for path in artifacts_dir.glob(pattern):
            data = _load_json(path)
            if data:
                buckets[key].append(data)
    return buckets


def _count(records: list[dict[str, Any]], pred) -> int:
    return sum(1 for r in records if pred(r))


def build_governance_metrics_summary(*, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR) -> dict[str, Any]:
    buckets = _iter_records(artifacts_dir)

    feedback = buckets["feedback_mapping"]
    role_map = buckets["role_rework_mapping"]
    validations = buckets["state_validation"]
    applies = buckets["apply"]
    dispatches = buckets["dispatch"]

    normalization_records = feedback + role_map
    normalization_total = len(normalization_records)
    normalization_ambiguity = _count(normalization_records, lambda r: isinstance(r.get("ambiguity_flags"), list) and len(r.get("ambiguity_flags", [])) > 0)
    normalization_ignored = _count(normalization_records, lambda r: r.get("is_mapped") is False)
    normalization_hit = max(0, normalization_total - normalization_ignored)

    feedback_hit = _count(feedback, lambda r: r.get("is_mapped") is True)
    feedback_miss = _count(feedback, lambda r: r.get("is_mapped") is False)

    role_detected = _count(role_map, lambda r: r.get("is_mapped") is True)
    role_total = len(role_map)
    role_detect_rate = round((role_detected / role_total), 4) if role_total else 0.0

    validation_pass = _count(validations, lambda r: r.get("is_valid") is True)
    validation_block = _count(validations, lambda r: r.get("is_valid") is False)

    apply_success = _count(applies, lambda r: str(r.get("apply_status")) == "applied")
    apply_blocked = _count(applies, lambda r: str(r.get("apply_status")) in {"blocked", "failed"})

    dispatch_success = _count(dispatches, lambda r: str(r.get("dispatch_status")) in {"accepted", "dispatched"})
    dispatch_blocked = _count(dispatches, lambda r: str(r.get("dispatch_status")) in {"blocked", "failed"})

    all_scope_records = normalization_records + validations + applies + dispatches + buckets["route"]
    by_scope: dict[str, dict[str, int]] = {}
    for record in all_scope_records:
        key = _scope_key(record)
        bucket = by_scope.setdefault(
            key,
            {
                "normalization_events": 0,
                "mapping_events": 0,
                "validation_events": 0,
                "apply_events": 0,
                "dispatch_events": 0,
            },
        )
        if record in normalization_records:
            bucket["normalization_events"] += 1
        if record in feedback or record in role_map:
            bucket["mapping_events"] += 1
        if record in validations:
            bucket["validation_events"] += 1
        if record in applies:
            bucket["apply_events"] += 1
        if record in dispatches:
            bucket["dispatch_events"] += 1

    return {
        "metrics_version": "governance.metrics.v0.1",
        "artifacts_dir": artifacts_dir.as_posix(),
        "normalization": {
            "hit": normalization_hit,
            "ambiguity": normalization_ambiguity,
            "ignored": normalization_ignored,
            "total": normalization_total,
        },
        "feedback_mapping": {
            "hit": feedback_hit,
            "miss": feedback_miss,
            "total": len(feedback),
        },
        "role_rework": {
            "detected": role_detected,
            "total": role_total,
            "detect_rate": role_detect_rate,
        },
        "state_validation": {
            "pass": validation_pass,
            "block": validation_block,
            "total": len(validations),
        },
        "apply": {
            "success": apply_success,
            "blocked": apply_blocked,
            "total": len(applies),
        },
        "execution_dispatch": {
            "success": dispatch_success,
            "blocked": dispatch_blocked,
            "total": len(dispatches),
        },
        "by_scope": by_scope,
    }


def write_governance_metrics_summary(summary: dict[str, Any], output_path: Path = DEFAULT_SUMMARY_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
