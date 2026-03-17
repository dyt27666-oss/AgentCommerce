"""Alias semantic regression suite and publish gate v0.1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.owner_intent_normalization import normalize_owner_intent
import tools.council_bridge.policy_config_center as pcc

DEFAULT_REGRESSION_CASES_PATH = Path("docs") / "alias_semantic_regression_cases.v0.1.json"
DEFAULT_REGRESSION_REPORT_PATH = Path("artifacts") / "alias_regression_report.json"


@dataclass(slots=True)
class AliasRegressionCase:
    case_id: str
    input: str
    expected: dict[str, Any]
    priority: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("json root must be object")
    return data


def load_alias_regression_cases(path: Path = DEFAULT_REGRESSION_CASES_PATH) -> list[AliasRegressionCase]:
    payload = _load_json(path)
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("regression cases must contain list field 'cases'")

    parsed: list[AliasRegressionCase] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        parsed.append(
            AliasRegressionCase(
                case_id=_safe_text(item.get("case_id")) or "case-unknown",
                input=_safe_text(item.get("input")),
                expected=dict(item.get("expected") or {}),
                priority=(_safe_text(item.get("priority")) or "P1").upper(),
            )
        )
    return parsed


def _scope_context(scope: Any) -> dict[str, str]:
    if scope.scope_type == "owner":
        return {"owner_id": scope.scope_id, "workspace_id": "", "project_id": ""}
    if scope.scope_type == "workspace":
        return {"owner_id": "", "workspace_id": scope.scope_id, "project_id": ""}
    if scope.scope_type == "project":
        return {"owner_id": "", "workspace_id": "", "project_id": scope.scope_id}
    return {"owner_id": "", "workspace_id": "", "project_id": ""}


def _load_alias_config_for_version(alias_version: str, scope: Any) -> tuple[dict[str, Any] | None, str | None]:
    ctx = _scope_context(scope)
    cfg = pcc.resolve_policy_config(
        owner_id=ctx["owner_id"],
        workspace_id=ctx["workspace_id"],
        project_id=ctx["project_id"],
    )
    registry = cfg.get("alias_registry") if isinstance(cfg.get("alias_registry"), dict) else {}
    versions = registry.get("versions") if isinstance(registry.get("versions"), dict) else {}
    alias_path = versions.get(alias_version) if isinstance(versions, dict) else None
    if not alias_path:
        return None, None
    path = Path(str(alias_path))
    if not path.exists():
        return None, str(path)
    payload = _load_json(path)
    return payload, str(path)


def _compare_expected(actual: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, list[str]]:
    diffs: list[str] = []
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            diffs.append(f"{key}: expected={expected_value!r}, actual={actual.get(key)!r}")
    return len(diffs) == 0, diffs


def _classify_case_result(*, priority: str, matched: bool) -> str:
    if matched:
        return "pass"
    if priority == "P0":
        return "fail"
    if priority == "P1":
        return "warn"
    return "warn"


def run_alias_regression_gate(
    *,
    alias_version: str,
    target_scope: Any,
    cases_path: Path = DEFAULT_REGRESSION_CASES_PATH,
    report_path: Path = DEFAULT_REGRESSION_REPORT_PATH,
) -> dict[str, Any]:
    warnings: list[str] = []
    cases: list[AliasRegressionCase] = []

    try:
        cases = load_alias_regression_cases(cases_path)
    except Exception as exc:
        return {
            "artifact_type": "alias_regression_report",
            "schema_version": "alias.regression.v0.1",
            "alias_version": alias_version,
            "generated_at": _now_iso(),
            "summary": {"total": 0, "pass": 0, "warn": 0, "fail": 1},
            "cases": [],
            "warnings": [f"failed to load regression cases: {exc}"],
            "gate_decision": "block_publish",
        }

    alias_config, alias_path = _load_alias_config_for_version(alias_version, target_scope)
    if alias_config is None:
        report = {
            "artifact_type": "alias_regression_report",
            "schema_version": "alias.regression.v0.1",
            "alias_version": alias_version,
            "generated_at": _now_iso(),
            "summary": {"total": len(cases), "pass": 0, "warn": 0, "fail": 1},
            "cases": [],
            "warnings": [f"alias version not found or alias file missing: {alias_version} ({alias_path or 'n/a'})"],
            "gate_decision": "block_publish",
        }
        write_alias_regression_report(report, report_path)
        return report

    if not cases:
        report = {
            "artifact_type": "alias_regression_report",
            "schema_version": "alias.regression.v0.1",
            "alias_version": alias_version,
            "generated_at": _now_iso(),
            "summary": {"total": 0, "pass": 0, "warn": 1, "fail": 0},
            "cases": [],
            "warnings": ["empty regression suite"],
            "gate_decision": "allow_publish",
            "alias_path": alias_path,
        }
        write_alias_regression_report(report, report_path)
        return report

    case_results: list[dict[str, Any]] = []
    pass_count = 0
    warn_count = 0
    fail_count = 0

    for case in cases:
        intent = normalize_owner_intent(case.input, alias_config=alias_config)
        actual = {
            "intent_type": intent.intent_type,
            "target_role": intent.target_role,
            "target_section": intent.target_section,
            "requested_action": intent.requested_action,
        }
        matched, diffs = _compare_expected(actual, case.expected)
        result = _classify_case_result(priority=case.priority, matched=matched)

        if result == "pass":
            pass_count += 1
        elif result == "warn":
            warn_count += 1
        else:
            fail_count += 1

        case_results.append(
            {
                "case_id": case.case_id,
                "priority": case.priority,
                "result": result,
                "input": case.input,
                "expected": case.expected,
                "actual": actual,
                "diffs": diffs,
            }
        )

    gate_decision = "block_publish" if fail_count > 0 else "allow_publish"
    report = {
        "artifact_type": "alias_regression_report",
        "schema_version": "alias.regression.v0.1",
        "alias_version": alias_version,
        "generated_at": _now_iso(),
        "summary": {"total": len(case_results), "pass": pass_count, "warn": warn_count, "fail": fail_count},
        "cases": case_results,
        "warnings": warnings,
        "gate_decision": gate_decision,
        "alias_path": alias_path,
    }
    write_alias_regression_report(report, report_path)
    return report


def write_alias_regression_report(report: dict[str, Any], output_path: Path = DEFAULT_REGRESSION_REPORT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
