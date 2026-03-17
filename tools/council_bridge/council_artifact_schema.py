"""Unified Council artifact schema v0.1 (artifact-first, HITL-ready).

This module defines minimal, auditable, and round-friendly structures for:
1) plan
2) risk
3) review
4) decision
5) handoff

Design goals:
- stable object contract for council lane iteration
- explicit owner feedback mapping
- lineage and parent/derived traceability
- pre-embedded status fields for upcoming state machine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ARTIFACT_TYPE_PLAN = "plan"
ARTIFACT_TYPE_RISK = "risk"
ARTIFACT_TYPE_REVIEW = "review"
ARTIFACT_TYPE_DECISION = "decision"
ARTIFACT_TYPE_HANDOFF = "handoff"

COUNCIL_ARTIFACT_TYPES = {
    ARTIFACT_TYPE_PLAN,
    ARTIFACT_TYPE_RISK,
    ARTIFACT_TYPE_REVIEW,
    ARTIFACT_TYPE_DECISION,
    ARTIFACT_TYPE_HANDOFF,
}

COUNCIL_SCHEMA_VERSION = "council.artifact.v0.1"
COUNCIL_LANE = "council"

COUNCIL_STATUSES = {
    "draft",
    "under_review",
    "needs_fix",
    "revised",
    "resubmitted",
    "ready_for_owner_review",
    "owner_rejected",
    "owner_approved",
    "handoff_ready",
}

FEEDBACK_TYPES = {
    "needs_fix",
    "revision_request",
    "reject",
    "comment",
    "approval_note",
}

REVIEW_VERDICTS = {"pass", "revise", "block"}
HANDOFF_OWNER_APPROVAL_STATUS = {"pending", "approved", "needs_fix", "rejected"}
HANDOFF_EXECUTION_READINESS_STATUS = {"not_ready", "blocked", "ready"}


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_int(value: Any, field_name: str, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    return value


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object.")
    return value


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null.")
    stripped = value.strip()
    return stripped or None


def _require_enum(value: Any, field_name: str, allowed: set[str]) -> str:
    text = _require_str(value, field_name)
    if text not in allowed:
        joined = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {joined}.")
    return text


@dataclass(slots=True)
class OwnerFeedback:
    feedback_id: str
    feedback_source: str
    feedback_text: str
    feedback_type: Literal["needs_fix", "revision_request", "reject", "comment", "approval_note"]
    target_artifact_id: str
    target_section: str
    severity: str
    requested_change: str
    resolved_status: str
    resolved_by_artifact_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OwnerFeedback":
        feedback_type = _require_enum(data.get("feedback_type"), "feedback_type", FEEDBACK_TYPES)
        return cls(
            feedback_id=_require_str(data.get("feedback_id"), "feedback_id"),
            feedback_source=_require_str(data.get("feedback_source"), "feedback_source"),
            feedback_text=_require_str(data.get("feedback_text"), "feedback_text"),
            feedback_type=feedback_type,  # type: ignore[arg-type]
            target_artifact_id=_require_str(data.get("target_artifact_id"), "target_artifact_id"),
            target_section=_require_str(data.get("target_section"), "target_section"),
            severity=_require_str(data.get("severity"), "severity"),
            requested_change=_require_str(data.get("requested_change"), "requested_change"),
            resolved_status=_require_str(data.get("resolved_status"), "resolved_status"),
            resolved_by_artifact_id=_optional_str(data.get("resolved_by_artifact_id"), "resolved_by_artifact_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "feedback_source": self.feedback_source,
            "feedback_text": self.feedback_text,
            "feedback_type": self.feedback_type,
            "target_artifact_id": self.target_artifact_id,
            "target_section": self.target_section,
            "severity": self.severity,
            "requested_change": self.requested_change,
            "resolved_status": self.resolved_status,
            "resolved_by_artifact_id": self.resolved_by_artifact_id,
        }


@dataclass(slots=True)
class CouncilArtifactBase:
    artifact_type: str
    schema_version: str
    artifact_id: str
    request_id: str
    brief_id: str
    handoff_id: str | None
    council_round: int
    parent_artifact_id: str | None
    derived_from_artifact_ids: list[str]
    owner_id: str
    chat_id: str
    created_at: str
    updated_at: str
    produced_by_lane: str
    produced_by_role: str | None
    produced_by_roles: list[str]
    status: str
    summary: str
    constraints: list[str]
    assumptions: list[str]
    open_questions: list[str]
    next_action: str
    owner_feedback: list[OwnerFeedback] = field(default_factory=list)
    audit_trace: list[dict[str, Any]] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict_common(cls, data: dict[str, Any], expected_type: str) -> "CouncilArtifactBase":
        artifact_type = _require_enum(data.get("artifact_type"), "artifact_type", COUNCIL_ARTIFACT_TYPES)
        if artifact_type != expected_type:
            raise ValueError(f"artifact_type mismatch: expected {expected_type}, got {artifact_type}.")

        schema_version = _require_str(data.get("schema_version"), "schema_version")
        if schema_version != COUNCIL_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {COUNCIL_SCHEMA_VERSION}.")

        produced_by_lane = _require_str(data.get("produced_by_lane"), "produced_by_lane")
        if produced_by_lane != COUNCIL_LANE:
            raise ValueError("produced_by_lane must be council.")

        feedback_items = _require_list(data.get("owner_feedback", []), "owner_feedback")
        feedback = [OwnerFeedback.from_dict(item) for item in feedback_items]

        return cls(
            artifact_type=artifact_type,
            schema_version=schema_version,
            artifact_id=_require_str(data.get("artifact_id"), "artifact_id"),
            request_id=_require_str(data.get("request_id"), "request_id"),
            brief_id=_require_str(data.get("brief_id"), "brief_id"),
            handoff_id=_optional_str(data.get("handoff_id"), "handoff_id"),
            council_round=_require_int(data.get("council_round"), "council_round", minimum=1),
            parent_artifact_id=_optional_str(data.get("parent_artifact_id"), "parent_artifact_id"),
            derived_from_artifact_ids=[_require_str(x, "derived_from_artifact_ids item") for x in _require_list(data.get("derived_from_artifact_ids", []), "derived_from_artifact_ids")],
            owner_id=_require_str(data.get("owner_id"), "owner_id"),
            chat_id=_require_str(data.get("chat_id"), "chat_id"),
            created_at=_require_str(data.get("created_at"), "created_at"),
            updated_at=_require_str(data.get("updated_at"), "updated_at"),
            produced_by_lane=produced_by_lane,
            produced_by_role=_optional_str(data.get("produced_by_role"), "produced_by_role"),
            produced_by_roles=[_require_str(x, "produced_by_roles item") for x in _require_list(data.get("produced_by_roles", []), "produced_by_roles")],
            status=_require_enum(data.get("status"), "status", COUNCIL_STATUSES),
            summary=_require_str(data.get("summary"), "summary"),
            constraints=[_require_str(x, "constraints item") for x in _require_list(data.get("constraints", []), "constraints")],
            assumptions=[_require_str(x, "assumptions item") for x in _require_list(data.get("assumptions", []), "assumptions")],
            open_questions=[_require_str(x, "open_questions item") for x in _require_list(data.get("open_questions", []), "open_questions")],
            next_action=_require_str(data.get("next_action"), "next_action"),
            owner_feedback=feedback,
            audit_trace=[_require_dict(x, "audit_trace item") for x in _require_list(data.get("audit_trace", []), "audit_trace")],
            lineage=_require_dict(data.get("lineage", {}), "lineage"),
        )


@dataclass(slots=True)
class CouncilPlanArtifact:
    base: CouncilArtifactBase
    objective: str
    scope: list[str]
    steps: list[dict[str, Any]]
    dependencies: list[str]
    acceptance_criteria: list[str]
    proposed_execution_boundary: dict[str, Any]
    expected_outputs: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouncilPlanArtifact":
        return cls(
            base=CouncilArtifactBase.from_dict_common(data, ARTIFACT_TYPE_PLAN),
            objective=_require_str(data.get("objective"), "objective"),
            scope=[_require_str(x, "scope item") for x in _require_list(data.get("scope", []), "scope")],
            steps=[_require_dict(x, "steps item") for x in _require_list(data.get("steps", []), "steps")],
            dependencies=[_require_str(x, "dependencies item") for x in _require_list(data.get("dependencies", []), "dependencies")],
            acceptance_criteria=[_require_str(x, "acceptance_criteria item") for x in _require_list(data.get("acceptance_criteria", []), "acceptance_criteria")],
            proposed_execution_boundary=_require_dict(data.get("proposed_execution_boundary"), "proposed_execution_boundary"),
            expected_outputs=[_require_str(x, "expected_outputs item") for x in _require_list(data.get("expected_outputs", []), "expected_outputs")],
        )


@dataclass(slots=True)
class CouncilRiskArtifact:
    base: CouncilArtifactBase
    risk_items: list[dict[str, Any]]
    severity: str
    likelihood: str
    mitigation: list[str]
    blocked_actions: list[str]
    escalation_conditions: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouncilRiskArtifact":
        return cls(
            base=CouncilArtifactBase.from_dict_common(data, ARTIFACT_TYPE_RISK),
            risk_items=[_require_dict(x, "risk_items item") for x in _require_list(data.get("risk_items", []), "risk_items")],
            severity=_require_str(data.get("severity"), "severity"),
            likelihood=_require_str(data.get("likelihood"), "likelihood"),
            mitigation=[_require_str(x, "mitigation item") for x in _require_list(data.get("mitigation", []), "mitigation")],
            blocked_actions=[_require_str(x, "blocked_actions item") for x in _require_list(data.get("blocked_actions", []), "blocked_actions")],
            escalation_conditions=[_require_str(x, "escalation_conditions item") for x in _require_list(data.get("escalation_conditions", []), "escalation_conditions")],
        )


@dataclass(slots=True)
class CouncilReviewArtifact:
    base: CouncilArtifactBase
    review_findings: list[dict[str, Any]]
    missing_items: list[str]
    contradictions: list[str]
    unresolved_questions: list[str]
    recommended_revisions: list[str]
    review_verdict: Literal["pass", "revise", "block"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouncilReviewArtifact":
        review_verdict = _require_enum(data.get("review_verdict"), "review_verdict", REVIEW_VERDICTS)
        return cls(
            base=CouncilArtifactBase.from_dict_common(data, ARTIFACT_TYPE_REVIEW),
            review_findings=[_require_dict(x, "review_findings item") for x in _require_list(data.get("review_findings", []), "review_findings")],
            missing_items=[_require_str(x, "missing_items item") for x in _require_list(data.get("missing_items", []), "missing_items")],
            contradictions=[_require_str(x, "contradictions item") for x in _require_list(data.get("contradictions", []), "contradictions")],
            unresolved_questions=[_require_str(x, "unresolved_questions item") for x in _require_list(data.get("unresolved_questions", []), "unresolved_questions")],
            recommended_revisions=[_require_str(x, "recommended_revisions item") for x in _require_list(data.get("recommended_revisions", []), "recommended_revisions")],
            review_verdict=review_verdict,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class CouncilDecisionArtifact:
    base: CouncilArtifactBase
    recommended_path: str
    rejected_alternatives: list[str]
    decision_rationale: str
    tradeoffs: list[str]
    confidence: float
    council_recommendation: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouncilDecisionArtifact":
        confidence = data.get("confidence")
        if not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be a number between 0 and 1.")
        confidence_f = float(confidence)
        if confidence_f < 0 or confidence_f > 1:
            raise ValueError("confidence must be between 0 and 1.")

        return cls(
            base=CouncilArtifactBase.from_dict_common(data, ARTIFACT_TYPE_DECISION),
            recommended_path=_require_str(data.get("recommended_path"), "recommended_path"),
            rejected_alternatives=[_require_str(x, "rejected_alternatives item") for x in _require_list(data.get("rejected_alternatives", []), "rejected_alternatives")],
            decision_rationale=_require_str(data.get("decision_rationale"), "decision_rationale"),
            tradeoffs=[_require_str(x, "tradeoffs item") for x in _require_list(data.get("tradeoffs", []), "tradeoffs")],
            confidence=confidence_f,
            council_recommendation=_require_str(data.get("council_recommendation"), "council_recommendation"),
        )


@dataclass(slots=True)
class CouncilHandoffArtifact:
    base: CouncilArtifactBase
    approved_execution_brief: dict[str, Any]
    execution_scope: list[str]
    execution_constraints: list[str]
    no_go_zones: list[str]
    required_receipts: list[str]
    owner_approval_status: Literal["pending", "approved", "needs_fix", "rejected"]
    execution_readiness_status: Literal["not_ready", "blocked", "ready"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouncilHandoffArtifact":
        owner_approval_status = _require_enum(
            data.get("owner_approval_status"),
            "owner_approval_status",
            HANDOFF_OWNER_APPROVAL_STATUS,
        )
        execution_readiness_status = _require_enum(
            data.get("execution_readiness_status"),
            "execution_readiness_status",
            HANDOFF_EXECUTION_READINESS_STATUS,
        )

        return cls(
            base=CouncilArtifactBase.from_dict_common(data, ARTIFACT_TYPE_HANDOFF),
            approved_execution_brief=_require_dict(data.get("approved_execution_brief"), "approved_execution_brief"),
            execution_scope=[_require_str(x, "execution_scope item") for x in _require_list(data.get("execution_scope", []), "execution_scope")],
            execution_constraints=[_require_str(x, "execution_constraints item") for x in _require_list(data.get("execution_constraints", []), "execution_constraints")],
            no_go_zones=[_require_str(x, "no_go_zones item") for x in _require_list(data.get("no_go_zones", []), "no_go_zones")],
            required_receipts=[_require_str(x, "required_receipts item") for x in _require_list(data.get("required_receipts", []), "required_receipts")],
            owner_approval_status=owner_approval_status,  # type: ignore[arg-type]
            execution_readiness_status=execution_readiness_status,  # type: ignore[arg-type]
        )


CouncilArtifactModel = (
    CouncilPlanArtifact
    | CouncilRiskArtifact
    | CouncilReviewArtifact
    | CouncilDecisionArtifact
    | CouncilHandoffArtifact
)


def parse_council_artifact(data: dict[str, Any]) -> CouncilArtifactModel:
    artifact_type = _require_enum(data.get("artifact_type"), "artifact_type", COUNCIL_ARTIFACT_TYPES)
    if artifact_type == ARTIFACT_TYPE_PLAN:
        return CouncilPlanArtifact.from_dict(data)
    if artifact_type == ARTIFACT_TYPE_RISK:
        return CouncilRiskArtifact.from_dict(data)
    if artifact_type == ARTIFACT_TYPE_REVIEW:
        return CouncilReviewArtifact.from_dict(data)
    if artifact_type == ARTIFACT_TYPE_DECISION:
        return CouncilDecisionArtifact.from_dict(data)
    return CouncilHandoffArtifact.from_dict(data)

