from __future__ import annotations

import json
from pathlib import Path

import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge.alias_semantic_regression_suite import (
    run_alias_regression_gate,
)
from tools.council_bridge.policy_publish_fsm import (
    STATUS_APPLIED,
    STATUS_CONFIRMED,
    create_publish_request,
    advance_publish_status,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _alias_config(version: str) -> dict:
    return {
        "version": version,
        "section_aliases": {
            "risk": ["风险分析", "risk"],
            "scope": ["scope", "范围"],
        },
        "role_aliases": {
            "critic": ["critic", "批判"],
            "strategist": ["strategist", "策略"],
        },
        "action_aliases": {
            "recheck": ["重看", "recheck"],
            "tighten": ["收紧", "tighten"],
            "clarify": ["写清楚", "clarify"],
            "resubmit": ["重新提交", "resubmit"],
            "summarize": ["总结", "summarize"],
        },
        "severity_markers": {"high": ["不行"], "medium": ["不够"], "low": ["建议"]},
    }


def _bootstrap_policy_center(monkeypatch, tmp_path: Path, *, include_v2: bool = True) -> dict[str, Path]:
    default = tmp_path / "default.json"
    owner = tmp_path / "owner_overrides.json"
    group = tmp_path / "group_overrides.json"
    workspace = tmp_path / "workspace_overrides.json"
    project = tmp_path / "project_overrides.json"

    v1_path = tmp_path / "owner_intent_aliases.v1.json"
    v2_path = tmp_path / "owner_intent_aliases.v2.json"
    _write(v1_path, _alias_config("v1"))
    if include_v2:
        _write(v2_path, _alias_config("v2"))

    versions = {"v1": v1_path.as_posix()}
    if include_v2:
        versions["v2"] = v2_path.as_posix()

    _write(
        default,
        {
            "policy_version": "policy.center.v0.1",
            "lane_switches": {},
            "alias_registry": {"active_version": "v1", "versions": versions},
        },
    )
    _write(owner, {})
    _write(group, {})
    _write(workspace, {})
    _write(project, {})

    monkeypatch.setattr(pcc, "DEFAULT_CONFIG_PATH", default)
    monkeypatch.setattr(pcc, "OWNER_OVERRIDES_PATH", owner)
    monkeypatch.setattr(pcc, "GROUP_OVERRIDES_PATH", group)
    monkeypatch.setattr(pcc, "WORKSPACE_OVERRIDES_PATH", workspace)
    monkeypatch.setattr(pcc, "PROJECT_OVERRIDES_PATH", project)

    return {
        "default": default,
        "owner": owner,
        "group": group,
        "workspace": workspace,
        "project": project,
        "v1": v1_path,
        "v2": v2_path,
    }


def _cases(path: Path, rows: list[dict]) -> Path:
    _write(path, {"suite_version": "alias.regression.cases.v0.1", "cases": rows})
    return path


def _p0_case_ok() -> dict:
    return {
        "case_id": "p0-role-critic",
        "input": "请让 critic 重看",
        "expected": {"intent_type": "role_rework", "target_role": "critic", "requested_action": "recheck"},
        "priority": "P0",
    }


def test_gate_regression_pass(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    cases_path = _cases(tmp_path / "cases.json", [_p0_case_ok()])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["gate_decision"] == "allow_publish"
    assert report["summary"]["fail"] == 0


def test_gate_p1_warning_allows(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    bad_p1 = {
        "case_id": "p1-mismatch",
        "input": "scope 太宽了，请写清楚",
        "expected": {"intent_type": "section_feedback", "target_section": "risk", "requested_action": "clarify"},
        "priority": "P1",
    }
    cases_path = _cases(tmp_path / "cases.json", [bad_p1])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["summary"]["warn"] == 1
    assert report["gate_decision"] == "allow_publish"


def test_gate_p0_fail_blocks(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    bad_p0 = {
        "case_id": "p0-mismatch",
        "input": "请让 critic 重看",
        "expected": {"intent_type": "role_rework", "target_role": "strategist", "requested_action": "recheck"},
        "priority": "P0",
    }
    cases_path = _cases(tmp_path / "cases.json", [bad_p0])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["summary"]["fail"] == 1
    assert report["gate_decision"] == "block_publish"


def test_gate_empty_suite_warn_allow(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    cases_path = _cases(tmp_path / "cases.json", [])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["summary"]["warn"] == 1
    assert report["gate_decision"] == "allow_publish"


def test_gate_unknown_intent_output_p0_fail(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    case = {
        "case_id": "p0-unknown",
        "input": "行吧",
        "expected": {"intent_type": "section_feedback", "target_section": "risk"},
        "priority": "P0",
    }
    cases_path = _cases(tmp_path / "cases.json", [case])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["summary"]["fail"] == 1


def test_gate_alias_version_not_found_blocks(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path, include_v2=False)
    cases_path = _cases(tmp_path / "cases.json", [_p0_case_ok()])

    report = run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=tmp_path / "report.json",
    )

    assert report["gate_decision"] == "block_publish"


def test_gate_report_written(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    report_path = tmp_path / "report.json"
    cases_path = _cases(tmp_path / "cases.json", [_p0_case_ok()])

    run_alias_regression_gate(
        alias_version="v2",
        target_scope=type("Scope", (), {"scope_type": "owner", "scope_id": "owner_001"})(),
        cases_path=cases_path,
        report_path=report_path,
    )
    assert report_path.exists()


def test_publish_apply_blocked_by_regression_gate(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    request = tmp_path / "request.json"
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"
    audit = tmp_path / "audit.json"
    report = tmp_path / "alias_regression_report.json"

    bad_p0 = {
        "case_id": "p0-mismatch",
        "input": "请让 critic 重看",
        "expected": {"intent_type": "role_rework", "target_role": "strategist", "requested_action": "recheck"},
        "priority": "P0",
    }
    cases_path = _cases(tmp_path / "cases.json", [bad_p0])

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="regression block",
        output_path=request,
    )
    advance_publish_status(request_path=request, target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=review, result_artifact_path=result, audit_pack_path=audit)

    applied = advance_publish_status(
        request_path=request,
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        alias_regression_cases_path=cases_path,
        alias_regression_report_path=report,
    )

    assert applied["status"] == "blocked_by_regression"
    assert report.exists()


def test_publish_apply_allowed_when_regression_pass(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    request = tmp_path / "request.json"
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"
    audit = tmp_path / "audit.json"

    cases_path = _cases(tmp_path / "cases.json", [_p0_case_ok()])

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="regression pass",
        output_path=request,
    )
    advance_publish_status(request_path=request, target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=review, result_artifact_path=result, audit_pack_path=audit)

    applied = advance_publish_status(
        request_path=request,
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        alias_regression_cases_path=cases_path,
        alias_regression_report_path=tmp_path / "report.json",
    )

    assert applied["status"] == STATUS_APPLIED


def test_publish_apply_alias_version_not_found_blocked(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path, include_v2=False)
    request = tmp_path / "request.json"
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"
    audit = tmp_path / "audit.json"

    cases_path = _cases(tmp_path / "cases.json", [_p0_case_ok()])

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="version missing",
        output_path=request,
    )
    advance_publish_status(request_path=request, target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=review, result_artifact_path=result, audit_pack_path=audit)

    applied = advance_publish_status(
        request_path=request,
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        alias_regression_cases_path=cases_path,
        alias_regression_report_path=tmp_path / "report.json",
    )

    assert applied["status"] == "blocked_by_regression"


def test_publish_apply_uses_custom_cases_path(monkeypatch, tmp_path: Path) -> None:
    _bootstrap_policy_center(monkeypatch, tmp_path)
    request = tmp_path / "request.json"
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"
    audit = tmp_path / "audit.json"
    report = tmp_path / "my_report.json"

    cases_path = _cases(tmp_path / "my_cases.json", [_p0_case_ok()])

    create_publish_request(
        requested_by="owner_001",
        target_scope={"scope_type": "owner", "scope_id": "owner_001"},
        change_set={"active_alias_version_to": "v2"},
        reason="custom cases",
        output_path=request,
    )
    advance_publish_status(request_path=request, target_status=STATUS_CONFIRMED, actor="owner_001", note="confirm", review_artifact_path=review, result_artifact_path=result, audit_pack_path=audit)

    advance_publish_status(
        request_path=request,
        target_status=STATUS_APPLIED,
        actor="owner_001",
        note="apply",
        review_artifact_path=review,
        result_artifact_path=result,
        audit_pack_path=audit,
        alias_regression_cases_path=cases_path,
        alias_regression_report_path=report,
    )

    assert report.exists()
