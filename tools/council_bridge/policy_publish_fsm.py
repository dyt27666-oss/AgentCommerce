"""Policy Publish FSM v0.1 (artifact-first).

Implements file-level policy alias version publish workflow:
proposed -> under_review -> confirmed -> applied -> rolled_back
and rejection paths.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tools.council_bridge.policy_config_center as pcc
from tools.council_bridge.governance_event_log import (
    DEFAULT_DEDUPE_INDEX_PATH as GOVERNANCE_DEDUPE_INDEX_PATH,
    DEFAULT_EVENT_LOG_PATH as GOVERNANCE_EVENT_LOG_PATH,
    build_governance_event,
    ingest_governance_event,
)
from tools.council_bridge.alias_semantic_regression_suite import (
    DEFAULT_REGRESSION_CASES_PATH,
    DEFAULT_REGRESSION_REPORT_PATH,
    run_alias_regression_gate,
)

SCHEMA_VERSION = "policy.publish.v0.1"
AUDIT_SCHEMA_VERSION = "policy.audit.v0.1"

STATUS_PROPOSED = "proposed"
STATUS_UNDER_REVIEW = "under_review"
STATUS_CONFIRMED = "confirmed"
STATUS_APPLIED = "applied"
STATUS_REJECTED = "rejected"
STATUS_ROLLED_BACK = "rolled_back"

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_PROPOSED: {STATUS_UNDER_REVIEW, STATUS_CONFIRMED, STATUS_REJECTED},
    STATUS_UNDER_REVIEW: {STATUS_CONFIRMED, STATUS_REJECTED},
    STATUS_CONFIRMED: {STATUS_APPLIED, STATUS_REJECTED},
    STATUS_APPLIED: {STATUS_ROLLED_BACK},
    STATUS_REJECTED: set(),
    STATUS_ROLLED_BACK: set(),
}

SCOPE_TYPES = {"owner", "workspace", "project", "default"}

DEFAULT_REQUEST_ARTIFACT_PATH = Path("artifacts") / "policy_publish_request.json"
DEFAULT_REVIEW_ARTIFACT_PATH = Path("artifacts") / "policy_publish_review.json"
DEFAULT_RESULT_ARTIFACT_PATH = Path("artifacts") / "policy_publish_result.json"
DEFAULT_AUDIT_ARTIFACT_PATH = Path("artifacts") / "policy_change_audit_pack.json"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PolicyTargetScope:
    scope_type: str
    scope_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyTargetScope":
        scope_type = str(data.get("scope_type") or "").strip().lower()
        scope_id = str(data.get("scope_id") or "").strip()
        if scope_type not in SCOPE_TYPES:
            raise ValueError(f"scope_type must be one of: {sorted(SCOPE_TYPES)}")
        if scope_type != "default" and not scope_id:
            raise ValueError("scope_id is required for owner/workspace/project scope")
        return cls(scope_type=scope_type, scope_id=scope_id)

    def to_dict(self) -> dict[str, Any]:
        return {"scope_type": self.scope_type, "scope_id": self.scope_id}


@dataclass(slots=True)
class PolicyChangeSet:
    active_alias_version_to: str
    active_alias_version_from: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyChangeSet":
        to_version = str(data.get("active_alias_version_to") or "").strip()
        from_version = str(data.get("active_alias_version_from") or "").strip() or None
        if not to_version:
            raise ValueError("change_set.active_alias_version_to is required")
        return cls(active_alias_version_to=to_version, active_alias_version_from=from_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_alias_version_to": self.active_alias_version_to,
            "active_alias_version_from": self.active_alias_version_from,
        }


@dataclass(slots=True)
class PolicyPublishRequest:
    schema_version: str
    artifact_type: str
    publish_id: str
    requested_by: str
    target_scope: PolicyTargetScope
    change_set: PolicyChangeSet
    status: str
    reason: str
    approver: str | None = None
    created_at: str = ""
    updated_at: str = ""
    review_notes: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    impact_estimate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "publish_id": self.publish_id,
            "requested_by": self.requested_by,
            "target_scope": self.target_scope.to_dict(),
            "change_set": self.change_set.to_dict(),
            "status": self.status,
            "reason": self.reason,
            "approver": self.approver,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "review_notes": self.review_notes,
            "history": self.history,
            "impact_estimate": self.impact_estimate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyPublishRequest":
        return cls(
            schema_version=str(data.get("schema_version") or SCHEMA_VERSION),
            artifact_type=str(data.get("artifact_type") or "policy_publish_request"),
            publish_id=str(data.get("publish_id") or "").strip(),
            requested_by=str(data.get("requested_by") or "").strip(),
            target_scope=PolicyTargetScope.from_dict(data.get("target_scope") or {}),
            change_set=PolicyChangeSet.from_dict(data.get("change_set") or {}),
            status=str(data.get("status") or "").strip(),
            reason=str(data.get("reason") or "").strip(),
            approver=str(data.get("approver") or "").strip() or None,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            review_notes=list(data.get("review_notes") or []),
            history=list(data.get("history") or []),
            impact_estimate=dict(data.get("impact_estimate") or {}),
        )


@dataclass(slots=True)
class PublishTransitionResult:
    is_valid: bool
    publish_id: str
    from_status: str
    to_status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    result_status: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _scope_context(scope: PolicyTargetScope) -> dict[str, str]:
    if scope.scope_type == "owner":
        return {"owner_id": scope.scope_id, "workspace_id": "", "project_id": ""}
    if scope.scope_type == "workspace":
        return {"owner_id": "", "workspace_id": scope.scope_id, "project_id": ""}
    if scope.scope_type == "project":
        return {"owner_id": "", "workspace_id": "", "project_id": scope.scope_id}
    return {"owner_id": "", "workspace_id": "", "project_id": ""}


def _current_effective_alias(scope: PolicyTargetScope) -> str:
    ctx = _scope_context(scope)
    cfg = pcc.resolve_policy_config(
        owner_id=ctx["owner_id"],
        workspace_id=ctx["workspace_id"],
        project_id=ctx["project_id"],
    )
    return str(cfg.get("active_alias_version") or "")


def _validate_transition(from_status: str, to_status: str) -> list[str]:
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        return [f"illegal publish transition: {from_status} -> {to_status}"]
    return []


def _ensure_version_exists(version: str) -> None:
    pcc.set_active_alias_version(version, config_path=pcc.DEFAULT_CONFIG_PATH, dry_run=True)


def _override_path_for_scope(scope_type: str) -> Path:
    if scope_type == "owner":
        return pcc.OWNER_OVERRIDES_PATH
    if scope_type == "workspace":
        return pcc.WORKSPACE_OVERRIDES_PATH
    if scope_type == "project":
        return pcc.PROJECT_OVERRIDES_PATH
    return pcc.DEFAULT_CONFIG_PATH


def _apply_alias_version_to_scope(scope: PolicyTargetScope, target_version: str) -> tuple[str, str, str]:
    _ensure_version_exists(target_version)
    before = _current_effective_alias(scope)

    if scope.scope_type == "default":
        pcc.set_active_alias_version(target_version, config_path=pcc.DEFAULT_CONFIG_PATH)
        after = _current_effective_alias(scope)
        return before, after, pcc.DEFAULT_CONFIG_PATH.as_posix()

    path = _override_path_for_scope(scope.scope_type)
    table = _load_json(path) if path.exists() else {}
    entry = table.get(scope.scope_id)
    if not isinstance(entry, dict):
        entry = {}
    alias_registry = entry.get("alias_registry")
    if not isinstance(alias_registry, dict):
        alias_registry = {}
    alias_registry["active_version"] = target_version
    entry["alias_registry"] = alias_registry
    table[scope.scope_id] = entry
    _write_json(path, table)

    after = _current_effective_alias(scope)
    return before, after, path.as_posix()


def _build_impact_estimate(scope: PolicyTargetScope, provided: dict[str, Any] | None = None) -> dict[str, Any]:
    if scope.scope_type in {"workspace", "project"}:
        if isinstance(provided, dict) and provided:
            out = dict(provided)
            out.setdefault("method", "manual_or_placeholder")
            return out
        return {
            "method": "placeholder",
            "estimated_owners": 0,
            "estimated_projects": 1 if scope.scope_type == "project" else 0,
            "note": "v0.1 placeholder estimate",
        }
    return provided if isinstance(provided, dict) else {}


def create_publish_request(
    *,
    requested_by: str,
    target_scope: dict[str, Any],
    change_set: dict[str, Any],
    reason: str,
    output_path: Path = DEFAULT_REQUEST_ARTIFACT_PATH,
    impact_estimate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope = PolicyTargetScope.from_dict(target_scope)
    cs = PolicyChangeSet.from_dict(change_set)
    now = _now_iso()
    req = PolicyPublishRequest(
        schema_version=SCHEMA_VERSION,
        artifact_type="policy_publish_request",
        publish_id=f"pub-{uuid.uuid4().hex[:10]}",
        requested_by=requested_by,
        target_scope=scope,
        change_set=cs,
        status=STATUS_PROPOSED,
        reason=reason,
        approver=None,
        created_at=now,
        updated_at=now,
        review_notes=[],
        history=[{"from": None, "to": STATUS_PROPOSED, "by": requested_by, "at": now}],
        impact_estimate=_build_impact_estimate(scope, impact_estimate),
    )
    _write_json(output_path, req.to_dict())
    return req.to_dict()


def _transition_request_status(
    request: PolicyPublishRequest,
    *,
    to_status: str,
    actor: str,
    note: str,
) -> PublishTransitionResult:
    errors = _validate_transition(request.status, to_status)
    if to_status == STATUS_APPLIED and request.status != STATUS_CONFIRMED:
        errors.append("apply requires confirmed status")
    if to_status == STATUS_ROLLED_BACK and request.status != STATUS_APPLIED:
        errors.append("rollback is only allowed from applied status")
    if request.status == STATUS_REJECTED and to_status == STATUS_APPLIED:
        errors.append("rejected publish cannot be applied")

    result = PublishTransitionResult(
        is_valid=len(errors) == 0,
        publish_id=request.publish_id,
        from_status=request.status,
        to_status=to_status,
        errors=errors,
        warnings=[],
        result_status="blocked" if errors else "ok",
        timestamp=_now_iso(),
    )

    if result.is_valid:
        request.history.append({"from": request.status, "to": to_status, "by": actor, "at": result.timestamp, "note": note})
        request.status = to_status
        request.updated_at = result.timestamp
        if to_status in {STATUS_CONFIRMED, STATUS_APPLIED, STATUS_REJECTED, STATUS_ROLLED_BACK}:
            request.approver = actor
    return result


def advance_publish_status(
    *,
    request_path: Path,
    target_status: str,
    actor: str,
    note: str,
    review_artifact_path: Path = DEFAULT_REVIEW_ARTIFACT_PATH,
    result_artifact_path: Path = DEFAULT_RESULT_ARTIFACT_PATH,
    audit_pack_path: Path = DEFAULT_AUDIT_ARTIFACT_PATH,
    alias_regression_cases_path: Path = DEFAULT_REGRESSION_CASES_PATH,
    alias_regression_report_path: Path = DEFAULT_REGRESSION_REPORT_PATH,
    governance_event_log_path: Path = GOVERNANCE_EVENT_LOG_PATH,
    governance_dedupe_index_path: Path = GOVERNANCE_DEDUPE_INDEX_PATH,
) -> dict[str, Any]:
    request = PolicyPublishRequest.from_dict(_load_json(request_path))
    regression: dict[str, Any] | None = None

    if target_status == STATUS_APPLIED:
        regression = run_alias_regression_gate(
            alias_version=request.change_set.active_alias_version_to,
            target_scope=request.target_scope,
            cases_path=alias_regression_cases_path,
            report_path=alias_regression_report_path,
        )
        if regression.get("gate_decision") == "block_publish":
            response = {
                "schema_version": SCHEMA_VERSION,
                "artifact_type": "policy_publish_result",
                "publish_id": request.publish_id,
                "requested_by": request.requested_by,
                "approver": actor,
                "target_scope": request.target_scope.to_dict(),
                "change_set": request.change_set.to_dict(),
                "from_status": request.status,
                "status": "blocked_by_regression",
                "transition_errors": ["alias semantic regression gate failed"],
                "timestamp": _now_iso(),
                "before": {},
                "after": {},
                "apply_error": "alias regression gate blocked publish",
                "changed_config_path": "",
                "alias_regression_report_path": alias_regression_report_path.as_posix(),
                "alias_regression_summary": regression.get("summary", {}),
            }
            _write_json(result_artifact_path, response)
            return response

    transition = _transition_request_status(request, to_status=target_status, actor=actor, note=note)

    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "policy_publish_result",
        "publish_id": request.publish_id,
        "requested_by": request.requested_by,
        "approver": actor,
        "target_scope": request.target_scope.to_dict(),
        "change_set": request.change_set.to_dict(),
        "from_status": transition.from_status,
        "status": "blocked" if not transition.is_valid else target_status,
        "transition_errors": transition.errors,
        "timestamp": transition.timestamp,
        "before": {},
        "after": {},
        "apply_error": "",
        "changed_config_path": "",
    }
    if target_status == STATUS_APPLIED and regression is not None:
        response["alias_regression_report_path"] = alias_regression_report_path.as_posix()
        response["alias_regression_summary"] = regression.get("summary", {})
        response["alias_regression_decision"] = regression.get("gate_decision")

    if not transition.is_valid:
        _write_json(result_artifact_path, response)
        return response

    # Persist request artifact state first.
    _write_json(request_path, request.to_dict())

    if target_status in {STATUS_UNDER_REVIEW, STATUS_CONFIRMED, STATUS_REJECTED}:
        review = {
            "schema_version": SCHEMA_VERSION,
            "artifact_type": "policy_publish_review",
            "publish_id": request.publish_id,
            "requested_by": request.requested_by,
            "approver": actor,
            "target_scope": request.target_scope.to_dict(),
            "change_set": request.change_set.to_dict(),
            "status": target_status,
            "note": note,
            "timestamp": transition.timestamp,
        }
        _write_json(review_artifact_path, review)

    if target_status == STATUS_APPLIED:
        before, after, changed_path = _apply_alias_version_to_scope(
            request.target_scope,
            request.change_set.active_alias_version_to,
        )
        request.change_set.active_alias_version_from = before
        _write_json(request_path, request.to_dict())
        response["before"] = {"active_alias_version": before}
        response["after"] = {"active_alias_version": after}
        response["changed_config_path"] = changed_path

    if target_status == STATUS_ROLLED_BACK:
        rollback_version = request.change_set.active_alias_version_from
        if not rollback_version:
            response["status"] = "blocked"
            response["apply_error"] = "rollback requires change_set.active_alias_version_from"
            _write_json(result_artifact_path, response)
            return response
        before, after, changed_path = _apply_alias_version_to_scope(
            request.target_scope,
            rollback_version,
        )
        response["before"] = {"active_alias_version": before}
        response["after"] = {"active_alias_version": after}
        response["changed_config_path"] = changed_path

    _write_json(result_artifact_path, response)

    if target_status in {STATUS_APPLIED, STATUS_ROLLED_BACK}:
        audit_pack = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "artifact_type": "policy_change_audit_pack",
            "publish_id": request.publish_id,
            "requested_by": request.requested_by,
            "approver": actor,
            "target_scope": request.target_scope.to_dict(),
            "status": target_status,
            "before": response["before"],
            "after": response["after"],
            "change_set": request.change_set.to_dict(),
            "impact_estimate": request.impact_estimate,
            "timestamp": transition.timestamp,
            "linked_artifacts": {
                "request": request_path.as_posix(),
                "result": result_artifact_path.as_posix(),
            },
        }
        _write_json(audit_pack_path, audit_pack)

    if target_status in {STATUS_APPLIED, STATUS_REJECTED, STATUS_ROLLED_BACK} and response["status"] == target_status:
        try:
            scope = request.target_scope
            workspace_id = scope.scope_id if scope.scope_type == "workspace" else None
            project_id = scope.scope_id if scope.scope_type == "project" else None
            owner_id = scope.scope_id if scope.scope_type == "owner" else actor
            event = build_governance_event(
                event_id=f"policy_publish:{request.publish_id}:{target_status}:{transition.timestamp}",
                event_type="policy_publish_result",
                occurred_at=transition.timestamp,
                request_id=None,
                publish_id=request.publish_id,
                workspace_id=workspace_id,
                project_id=project_id,
                owner_id=owner_id,
                source_module="policy_publish_fsm",
                source_artifact=result_artifact_path.as_posix(),
                status=target_status,
                payload_summary={
                    "from_status": transition.from_status,
                    "to_status": target_status,
                    "changed_config_path": response.get("changed_config_path"),
                },
            )
            response["event_ingest"] = ingest_governance_event(
                event,
                log_path=governance_event_log_path,
                dedupe_index_path=governance_dedupe_index_path,
            )
        except Exception as exc:  # event logging must not break publish workflow
            logger.warning("policy publish event logging failed: %s", exc)
            response["event_ingest"] = {
                "ingest_status": "invalid",
                "event_id": "",
                "dedupe_key": "",
                "warnings": ["event logging failed; publish result still valid"],
                "errors": [str(exc)],
            }

    return response
