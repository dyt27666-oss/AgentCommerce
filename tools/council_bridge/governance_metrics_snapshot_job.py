"""Governance Metrics Snapshot Job v0.2.

Periodic/manual snapshot job that aggregates incremental governance events into
an auditable snapshot artifact and extends runtime recovery quality metrics.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.governance_event_log import DEFAULT_EVENT_LOG_PATH, load_governance_events
from tools.council_bridge.platform_governance_metrics import build_governance_metrics_summary

DEFAULT_SNAPSHOT_OUTPUT_PATH = Path("artifacts") / "governance_metrics_snapshot.json"
SNAPSHOT_SCHEMA_VERSION = "governance.metrics.v0.2"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def _scope_key_from_values(*, workspace_id: Any, project_id: Any, owner_id: Any) -> str:
    workspace = _safe_text(workspace_id)
    project = _safe_text(project_id)
    owner = _safe_text(owner_id)
    return f"workspace:{workspace}|project:{project}|owner:{owner}"


def _scope_key(event: dict[str, Any]) -> str:
    return _scope_key_from_values(
        workspace_id=event.get("workspace_id"),
        project_id=event.get("project_id"),
        owner_id=event.get("owner_id"),
    )


def _is_valid_event(event: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = ["event_id", "event_type", "occurred_at", "source_artifact", "status", "dedupe_key"]
    for key in required:
        if not _safe_text(event.get(key), fallback=""):
            errors.append(f"missing field: {key}")
    return len(errors) == 0, errors


def _dedupe_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    seen_event_ids: set[str] = set()
    seen_fallback_keys: set[str] = set()
    unique_events: list[dict[str, Any]] = []
    warnings: list[str] = []
    counters = {
        "input_total": len(events),
        "invalid_events": 0,
        "duplicate_event_id": 0,
        "duplicate_fallback_key": 0,
        "kept_events": 0,
    }

    for event in events:
        is_valid, errors = _is_valid_event(event)
        if not is_valid:
            counters["invalid_events"] += 1
            warnings.append("skip invalid event: " + "; ".join(errors))
            continue

        event_id = _safe_text(event.get("event_id"), fallback="")
        fallback_key = _safe_text(event.get("dedupe_key"), fallback="")

        if event_id in seen_event_ids:
            counters["duplicate_event_id"] += 1
            continue
        if fallback_key in seen_fallback_keys:
            counters["duplicate_fallback_key"] += 1
            continue

        seen_event_ids.add(event_id)
        seen_fallback_keys.add(fallback_key)
        unique_events.append(event)

    counters["kept_events"] = len(unique_events)
    return unique_events, counters, warnings


def _init_metrics() -> dict[str, Any]:
    return {
        "scope_validation": {"pass": 0, "blocked": 0, "degraded": 0},
        "router_scope_observe": {"observed": 0, "warnings": 0, "invalid_scope": 0},
        "policy_publish": {"applied": 0, "rejected": 0, "rolled_back": 0},
        "runtime_failure": {
            "total": 0,
            "by_failure_type": {},
            "by_failure_stage": {},
        },
        "runtime_recovery_attempt": {
            "total": 0,
            "success": 0,
            "failed_retryable": 0,
            "failed_terminal": 0,
            "ignored": 0,
            "manual_required": 0,
        },
        "runtime_reconcile": {
            "no_action_needed": 0,
            "reconciled": 0,
            "partially_reconciled": 0,
            "manual_required": 0,
        },
        "runtime_event_log_degradation": {
            "queued": 0,
            "replayed": 0,
            "replay_failed": 0,
            "abandoned": 0,
        },
        "recovery_quality": {
            "recovery_rate": 0.0,
            "manual_intervention_rate": 0.0,
            "abandonment_rate": 0.0,
            "replay_success_rate": 0.0,
            "denominator_rules": {
                "recovery_rate": "runtime_recovery_attempt.total",
                "manual_intervention_rate": "runtime_recovery_attempt.total",
                "abandonment_rate": "runtime_event_log_degradation.total",
                "replay_success_rate": "runtime_event_log_degradation.replayed + replay_failed + abandoned",
            },
        },
    }


def _init_scope_bucket() -> dict[str, Any]:
    return {
        "scope_validation": {"pass": 0, "blocked": 0, "degraded": 0},
        "router_scope_observe": {"observed": 0, "warnings": 0, "invalid_scope": 0},
        "policy_publish": {"applied": 0, "rejected": 0, "rolled_back": 0},
        "runtime_failure": {"total": 0},
        "runtime_recovery_attempt": {
            "total": 0,
            "success": 0,
            "failed_retryable": 0,
            "failed_terminal": 0,
            "ignored": 0,
            "manual_required": 0,
        },
        "runtime_reconcile": {
            "no_action_needed": 0,
            "reconciled": 0,
            "partially_reconciled": 0,
            "manual_required": 0,
        },
        "runtime_event_log_degradation": {
            "queued": 0,
            "replayed": 0,
            "replay_failed": 0,
            "abandoned": 0,
        },
    }


def _inc_counter(mapping: dict[str, int], key: str) -> None:
    mapping[key] = int(mapping.get(key, 0)) + 1


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _apply_quality(metrics: dict[str, Any]) -> None:
    rec = metrics["runtime_recovery_attempt"]
    deg = metrics["runtime_event_log_degradation"]

    recovery_total = int(rec.get("total") or 0)
    degradation_total = int(deg.get("queued") or 0) + int(deg.get("replayed") or 0) + int(deg.get("replay_failed") or 0) + int(deg.get("abandoned") or 0)
    replay_outcomes = int(deg.get("replayed") or 0) + int(deg.get("replay_failed") or 0) + int(deg.get("abandoned") or 0)

    metrics["recovery_quality"]["recovery_rate"] = _ratio(int(rec.get("success") or 0), recovery_total)
    metrics["recovery_quality"]["manual_intervention_rate"] = _ratio(int(rec.get("manual_required") or 0), recovery_total)
    metrics["recovery_quality"]["abandonment_rate"] = _ratio(int(deg.get("abandoned") or 0), degradation_total)
    metrics["recovery_quality"]["replay_success_rate"] = _ratio(int(deg.get("replayed") or 0), replay_outcomes)


def _aggregate_incremental(events: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    metrics = _init_metrics()
    by_scope: dict[str, dict[str, Any]] = {}
    recovery_event_totals = {
        "runtime_failure": 0,
        "runtime_recovery_attempt": 0,
        "runtime_reconcile": 0,
        "runtime_event_log_degradation": 0,
    }

    for event in events:
        event_type = _safe_text(event.get("event_type"), fallback="")
        status = _safe_text(event.get("status"), fallback="")
        payload = event.get("payload_summary") if isinstance(event.get("payload_summary"), dict) else {}

        key = _scope_key(event)
        scope_bucket = by_scope.setdefault(key, _init_scope_bucket())

        if event_type == "scope_validation_result":
            if status == "pass":
                metrics["scope_validation"]["pass"] += 1
                scope_bucket["scope_validation"]["pass"] += 1
            elif status == "blocked":
                metrics["scope_validation"]["blocked"] += 1
                scope_bucket["scope_validation"]["blocked"] += 1
            elif status == "degraded_continue":
                metrics["scope_validation"]["degraded"] += 1
                scope_bucket["scope_validation"]["degraded"] += 1

        if event_type == "router_scope_observe_result":
            metrics["router_scope_observe"]["observed"] += 1
            scope_bucket["router_scope_observe"]["observed"] += 1
            if status in {"degraded_continue", "blocked"}:
                metrics["router_scope_observe"]["warnings"] += 1
                scope_bucket["router_scope_observe"]["warnings"] += 1
            if status == "blocked":
                metrics["router_scope_observe"]["invalid_scope"] += 1
                scope_bucket["router_scope_observe"]["invalid_scope"] += 1

        if event_type == "policy_publish_result":
            if status == "applied":
                metrics["policy_publish"]["applied"] += 1
                scope_bucket["policy_publish"]["applied"] += 1
            elif status == "rejected":
                metrics["policy_publish"]["rejected"] += 1
                scope_bucket["policy_publish"]["rejected"] += 1
            elif status == "rolled_back":
                metrics["policy_publish"]["rolled_back"] += 1
                scope_bucket["policy_publish"]["rolled_back"] += 1

        if event_type == "runtime_failure_event":
            recovery_event_totals["runtime_failure"] += 1
            metrics["runtime_failure"]["total"] += 1
            scope_bucket["runtime_failure"]["total"] += 1
            failure_type = _safe_text(payload.get("failure_type"))
            failure_stage = _safe_text(payload.get("failure_stage"))
            if failure_type:
                _inc_counter(metrics["runtime_failure"]["by_failure_type"], failure_type)
            if failure_stage:
                _inc_counter(metrics["runtime_failure"]["by_failure_stage"], failure_stage)

        if event_type == "runtime_recovery_attempt":
            recovery_event_totals["runtime_recovery_attempt"] += 1
            metrics["runtime_recovery_attempt"]["total"] += 1
            scope_bucket["runtime_recovery_attempt"]["total"] += 1
            if status in {"success", "failed_retryable", "failed_terminal", "ignored", "manual_required"}:
                metrics["runtime_recovery_attempt"][status] += 1
                scope_bucket["runtime_recovery_attempt"][status] += 1

        if event_type == "runtime_reconcile_report":
            recovery_event_totals["runtime_reconcile"] += 1
            if status in {"no_action_needed", "reconciled", "partially_reconciled", "manual_required"}:
                metrics["runtime_reconcile"][status] += 1
                scope_bucket["runtime_reconcile"][status] += 1

        if event_type == "runtime_event_log_degradation":
            recovery_event_totals["runtime_event_log_degradation"] += 1
            if status in {"queued", "replayed", "replay_failed", "abandoned"}:
                metrics["runtime_event_log_degradation"][status] += 1
                scope_bucket["runtime_event_log_degradation"][status] += 1

    _apply_quality(metrics)
    return metrics, by_scope, recovery_event_totals


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _scan_recovery_artifacts(artifacts_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    metrics = _init_metrics()
    by_scope: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    patterns = {
        "runtime_failure": "**/*runtime_failure_event*.json",
        "runtime_recovery_attempt": "**/*runtime_recovery_attempt*.json",
        "runtime_reconcile": "**/*runtime_reconcile_report*.json",
        "runtime_event_log_degradation": "**/*runtime_event_log_degradation*.json",
    }

    for category, pattern in patterns.items():
        for path in artifacts_dir.glob(pattern):
            data = _load_json(path)
            if not isinstance(data, dict):
                continue

            key = _scope_key_from_values(
                workspace_id=data.get("workspace_id"),
                project_id=data.get("project_id"),
                owner_id=data.get("owner_id") or data.get("operator"),
            )
            scope_bucket = by_scope.setdefault(key, _init_scope_bucket())

            if category == "runtime_failure":
                metrics["runtime_failure"]["total"] += 1
                scope_bucket["runtime_failure"]["total"] += 1
                ftype = _safe_text(data.get("failure_type"))
                fstage = _safe_text(data.get("failure_stage"))
                if ftype:
                    _inc_counter(metrics["runtime_failure"]["by_failure_type"], ftype)
                if fstage:
                    _inc_counter(metrics["runtime_failure"]["by_failure_stage"], fstage)

            if category == "runtime_recovery_attempt":
                metrics["runtime_recovery_attempt"]["total"] += 1
                scope_bucket["runtime_recovery_attempt"]["total"] += 1
                result = _safe_text(data.get("attempt_result"))
                if result in {"success", "failed_retryable", "failed_terminal", "ignored", "manual_required"}:
                    metrics["runtime_recovery_attempt"][result] += 1
                    scope_bucket["runtime_recovery_attempt"][result] += 1
                else:
                    warnings.append(f"unknown attempt_result in {path.as_posix()}")

            if category == "runtime_reconcile":
                status = _safe_text(data.get("reconcile_status"))
                if status in {"no_action_needed", "reconciled", "partially_reconciled", "manual_required"}:
                    metrics["runtime_reconcile"][status] += 1
                    scope_bucket["runtime_reconcile"][status] += 1
                else:
                    warnings.append(f"unknown reconcile_status in {path.as_posix()}")

            if category == "runtime_event_log_degradation":
                status = _safe_text(data.get("queue_status"))
                if status in {"queued", "replayed", "replay_failed", "abandoned"}:
                    metrics["runtime_event_log_degradation"][status] += 1
                    scope_bucket["runtime_event_log_degradation"][status] += 1
                else:
                    warnings.append(f"unknown degradation queue_status in {path.as_posix()}")

    _apply_quality(metrics)
    return metrics, by_scope, warnings


def _merge_scope_category(dst_by_scope: dict[str, Any], src_by_scope: dict[str, Any], category: str) -> None:
    for key, src_bucket in src_by_scope.items():
        dst_bucket = dst_by_scope.setdefault(key, _init_scope_bucket())
        if category in src_bucket:
            dst_bucket[category] = src_bucket[category]


def _merge_recovery_supplement(
    *,
    metrics: dict[str, Any],
    by_scope: dict[str, Any],
    scan_metrics: dict[str, Any],
    scan_by_scope: dict[str, Any],
    recovery_event_totals: dict[str, int],
) -> list[str]:
    supplemented: list[str] = []

    if recovery_event_totals.get("runtime_failure", 0) == 0 and scan_metrics["runtime_failure"]["total"] > 0:
        metrics["runtime_failure"] = scan_metrics["runtime_failure"]
        _merge_scope_category(by_scope, scan_by_scope, "runtime_failure")
        supplemented.append("runtime_failure")

    if recovery_event_totals.get("runtime_recovery_attempt", 0) == 0 and scan_metrics["runtime_recovery_attempt"]["total"] > 0:
        metrics["runtime_recovery_attempt"] = scan_metrics["runtime_recovery_attempt"]
        _merge_scope_category(by_scope, scan_by_scope, "runtime_recovery_attempt")
        supplemented.append("runtime_recovery_attempt")

    if recovery_event_totals.get("runtime_reconcile", 0) == 0:
        rec_total = sum(int(scan_metrics["runtime_reconcile"].get(k, 0)) for k in ["no_action_needed", "reconciled", "partially_reconciled", "manual_required"])
        if rec_total > 0:
            metrics["runtime_reconcile"] = scan_metrics["runtime_reconcile"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_reconcile")
            supplemented.append("runtime_reconcile")

    if recovery_event_totals.get("runtime_event_log_degradation", 0) == 0:
        deg_total = sum(int(scan_metrics["runtime_event_log_degradation"].get(k, 0)) for k in ["queued", "replayed", "replay_failed", "abandoned"])
        if deg_total > 0:
            metrics["runtime_event_log_degradation"] = scan_metrics["runtime_event_log_degradation"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_event_log_degradation")
            supplemented.append("runtime_event_log_degradation")

    _apply_quality(metrics)
    return supplemented


def build_governance_metrics_snapshot_job_result(
    *,
    event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    artifacts_dir: Path = Path("artifacts"),
    fallback_to_full_scan: bool = True,
) -> dict[str, Any]:
    events, read_warnings = load_governance_events(event_log_path)
    deduped_events, dedupe_stats, dedupe_warnings = _dedupe_events(events)

    warnings = list(read_warnings) + list(dedupe_warnings)
    source_mode = "incremental"
    source_details = {
        "incremental_events": len(deduped_events),
        "recovery_artifact_scan_used": False,
        "supplemented_categories": [],
    }

    metrics, by_scope, recovery_event_totals = _aggregate_incremental(deduped_events)

    if not deduped_events and fallback_to_full_scan:
        full_scan = build_governance_metrics_summary(artifacts_dir=artifacts_dir)
        scan_metrics, scan_by_scope, scan_warnings = _scan_recovery_artifacts(artifacts_dir)
        warnings.extend(scan_warnings)

        if scan_metrics["runtime_failure"]["total"] > 0:
            metrics["runtime_failure"] = scan_metrics["runtime_failure"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_failure")
        if scan_metrics["runtime_recovery_attempt"]["total"] > 0:
            metrics["runtime_recovery_attempt"] = scan_metrics["runtime_recovery_attempt"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_recovery_attempt")
        rec_total = sum(int(scan_metrics["runtime_reconcile"].get(k, 0)) for k in ["no_action_needed", "reconciled", "partially_reconciled", "manual_required"])
        if rec_total > 0:
            metrics["runtime_reconcile"] = scan_metrics["runtime_reconcile"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_reconcile")
        deg_total = sum(int(scan_metrics["runtime_event_log_degradation"].get(k, 0)) for k in ["queued", "replayed", "replay_failed", "abandoned"])
        if deg_total > 0:
            metrics["runtime_event_log_degradation"] = scan_metrics["runtime_event_log_degradation"]
            _merge_scope_category(by_scope, scan_by_scope, "runtime_event_log_degradation")
        _apply_quality(metrics)

        source_mode = "full_scan_fallback"
        source_details["recovery_artifact_scan_used"] = True

        return {
            "artifact_type": "governance_metrics_snapshot",
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "source_mode": source_mode,
            "metrics": metrics,
            "by_scope": by_scope,
            "notes": warnings + ["event log empty; fallback to full scan"],
            "job_stats": {
                "event_log_path": event_log_path.as_posix(),
                "dedupe": dedupe_stats,
                "warnings": warnings + ["event log empty; fallback to full scan"],
                "source_details": source_details,
            },
            "full_scan_fallback_summary": full_scan,
        }

    if fallback_to_full_scan:
        scan_metrics, scan_by_scope, scan_warnings = _scan_recovery_artifacts(artifacts_dir)
        warnings.extend(scan_warnings)
        supplemented = _merge_recovery_supplement(
            metrics=metrics,
            by_scope=by_scope,
            scan_metrics=scan_metrics,
            scan_by_scope=scan_by_scope,
            recovery_event_totals=recovery_event_totals,
        )
        if supplemented:
            source_mode = "mixed"
            source_details["recovery_artifact_scan_used"] = True
            source_details["supplemented_categories"] = supplemented
            warnings.append("recovery metrics supplemented from artifact scan")

    return {
        "artifact_type": "governance_metrics_snapshot",
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "source_mode": source_mode,
        "metrics": metrics,
        "by_scope": by_scope,
        "notes": warnings,
        "job_stats": {
            "event_log_path": event_log_path.as_posix(),
            "input_events": len(events),
            "deduped_events": len(deduped_events),
            "dedupe": dedupe_stats,
            "warnings": warnings,
            "source_details": source_details,
        },
    }


def write_governance_metrics_snapshot_job_artifact(
    snapshot: dict[str, Any],
    output_path: Path = DEFAULT_SNAPSHOT_OUTPUT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def run_governance_metrics_snapshot_job(
    *,
    event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
    artifacts_dir: Path = Path("artifacts"),
    output_path: Path = DEFAULT_SNAPSHOT_OUTPUT_PATH,
    fallback_to_full_scan: bool = True,
) -> dict[str, Any]:
    snapshot = build_governance_metrics_snapshot_job_result(
        event_log_path=event_log_path,
        artifacts_dir=artifacts_dir,
        fallback_to_full_scan=fallback_to_full_scan,
    )
    write_governance_metrics_snapshot_job_artifact(snapshot, output_path=output_path)
    return snapshot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run governance metrics snapshot job.")
    parser.add_argument("--event-log", default=str(DEFAULT_EVENT_LOG_PATH), help="Path to governance event log (jsonl)")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Artifacts directory for full-scan fallback")
    parser.add_argument("--output", default=str(DEFAULT_SNAPSHOT_OUTPUT_PATH), help="Output snapshot artifact path")
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable full scan fallback when event log is missing/empty",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    snapshot = run_governance_metrics_snapshot_job(
        event_log_path=Path(args.event_log),
        artifacts_dir=Path(args.artifacts_dir),
        output_path=Path(args.output),
        fallback_to_full_scan=not args.no_fallback,
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
