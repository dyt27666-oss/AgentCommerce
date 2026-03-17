"""Council artifact state transition validator v0.1.

This module keeps state transitions explicit, auditable, and governance-first.
It validates minimal Council lane transitions and pre-embeds execution gate checks.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.council_artifact_schema import (
    ARTIFACT_TYPE_HANDOFF,
    COUNCIL_STATUSES,
    CouncilHandoffArtifact,
    parse_council_artifact,
)


STATE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"under_review"},
    "under_review": {"needs_fix", "ready_for_owner_review"},
    "needs_fix": {"revised"},
    "revised": {"resubmitted"},
    "resubmitted": {"ready_for_owner_review"},
    "ready_for_owner_review": {"owner_rejected", "owner_approved"},
    "owner_rejected": set(),
    "owner_approved": {"handoff_ready"},
    "handoff_ready": set(),
}

PRIVILEGED_OWNER_STATES = {"owner_approved", "owner_rejected", "handoff_ready"}
OWNER_SIGNAL_LANES = {"owner", "bridge"}
CHAT_LANE = "chat"
DEFAULT_AUDIT_PATH = Path("artifacts") / "council_artifact_state_transition_result.json"


@dataclass(slots=True)
class TransitionRequest:
    artifact_id: str
    artifact_type: str
    current_status: str
    target_status: str
    requested_by: str
    requested_by_lane: str
    reason: str
    triggering_feedback_id: str | None = None
    triggering_artifact_id: str | None = None
    correlated_request_id: str | None = None
    correlated_brief_id: str | None = None
    correlated_handoff_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionRequest":
        required = [
            "artifact_id",
            "artifact_type",
            "current_status",
            "target_status",
            "requested_by",
            "requested_by_lane",
            "reason",
        ]
        for key in required:
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} must be a non-empty string.")

        return cls(
            artifact_id=data["artifact_id"].strip(),
            artifact_type=data["artifact_type"].strip(),
            current_status=data["current_status"].strip(),
            target_status=data["target_status"].strip(),
            requested_by=data["requested_by"].strip(),
            requested_by_lane=data["requested_by_lane"].strip(),
            reason=data["reason"].strip(),
            triggering_feedback_id=_optional_str(data.get("triggering_feedback_id")),
            triggering_artifact_id=_optional_str(data.get("triggering_artifact_id")),
            correlated_request_id=_optional_str(data.get("correlated_request_id")),
            correlated_brief_id=_optional_str(data.get("correlated_brief_id")),
            correlated_handoff_id=_optional_str(data.get("correlated_handoff_id")),
        )


@dataclass(slots=True)
class TransitionResult:
    is_valid: bool
    artifact_id: str
    artifact_type: str
    from_status: str
    to_status: str
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    required_missing_fields: list[str] = field(default_factory=list)
    suggested_next_action: str = ""
    execution_gate_candidate: bool = False
    derived_artifact_id: str | None = None
    audit_entry: dict[str, Any] = field(default_factory=dict)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional value must be a string when provided.")
    text = value.strip()
    return text or None


def _has_owner_feedback_for_fix(artifact: dict[str, Any], request: TransitionRequest) -> bool:
    if request.triggering_feedback_id:
        return True
    feedback = artifact.get("owner_feedback")
    if isinstance(feedback, list):
        for item in feedback:
            if not isinstance(item, dict):
                continue
            feedback_type = item.get("feedback_type")
            if feedback_type in {"needs_fix", "revision_request", "reject"}:
                return True
    return False


def _has_lineage_reference(artifact: dict[str, Any], request: TransitionRequest) -> bool:
    if request.triggering_artifact_id:
        return True
    parent = artifact.get("parent_artifact_id")
    if isinstance(parent, str) and parent.strip():
        return True
    derived = artifact.get("derived_from_artifact_ids")
    if isinstance(derived, list) and any(isinstance(x, str) and x.strip() for x in derived):
        return True
    return False


def _revision_completed(artifact: dict[str, Any]) -> bool:
    lineage = artifact.get("lineage")
    if not isinstance(lineage, dict):
        return False
    return lineage.get("revision_completed") is True


def _execution_candidate_for_handoff(model: Any, target_status: str) -> bool:
    if target_status != "handoff_ready":
        return False
    if not isinstance(model, CouncilHandoffArtifact):
        return False
    return model.owner_approval_status == "approved" and model.execution_readiness_status == "ready"


def validate_transition(artifact: dict[str, Any], request: TransitionRequest) -> TransitionResult:
    errors: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    try:
        model = parse_council_artifact(artifact)
    except Exception as exc:  # pragma: no cover - exact parser error varies
        errors.append(f"artifact schema validation failed: {exc}")
        model = None

    artifact_id = str(artifact.get("artifact_id", request.artifact_id))
    artifact_type = str(artifact.get("artifact_type", request.artifact_type))
    from_status = request.current_status
    to_status = request.target_status

    if request.current_status not in COUNCIL_STATUSES:
        errors.append("current_status is not a recognized Council status.")
    if request.target_status not in COUNCIL_STATUSES:
        errors.append("target_status is not a recognized Council status.")

    actual_status = artifact.get("status")
    if isinstance(actual_status, str) and actual_status != request.current_status:
        errors.append("request.current_status does not match artifact.status.")

    if request.artifact_id != artifact_id:
        errors.append("request.artifact_id does not match artifact.artifact_id.")
    if request.artifact_type != artifact_type:
        errors.append("request.artifact_type does not match artifact.artifact_type.")

    allowed = STATE_TRANSITIONS.get(request.current_status, set())
    if request.target_status not in allowed:
        errors.append(f"illegal state transition: {request.current_status} -> {request.target_status}.")

    if request.requested_by_lane == CHAT_LANE and request.target_status in PRIVILEGED_OWNER_STATES:
        errors.append("chat lane cannot request owner approval/rejection/handoff states.")

    if request.target_status in {"owner_approved", "owner_rejected"} and request.requested_by_lane not in OWNER_SIGNAL_LANES:
        errors.append("owner approval/rejection transitions require owner or bridge lane signal.")

    if request.current_status == "under_review" and request.target_status == "needs_fix":
        if not _has_owner_feedback_for_fix(artifact, request):
            errors.append("under_review -> needs_fix requires owner feedback or triggering_feedback_id.")
            missing.append("owner_feedback / triggering_feedback_id")

    if request.current_status == "needs_fix" and request.target_status == "revised":
        if not _has_lineage_reference(artifact, request):
            errors.append("needs_fix -> revised requires lineage reference to prior artifact.")
            missing.append("parent_artifact_id / derived_from_artifact_ids / triggering_artifact_id")
        if not _has_owner_feedback_for_fix(artifact, request):
            warnings.append("needs_fix -> revised has no explicit triggering feedback id.")

    if request.current_status == "revised" and request.target_status == "resubmitted":
        if not _has_lineage_reference(artifact, request):
            errors.append("revised -> resubmitted requires lineage linkage.")
            missing.append("parent_artifact_id / derived_from_artifact_ids / triggering_artifact_id")
        if not _revision_completed(artifact):
            errors.append("revised -> resubmitted requires lineage.revision_completed == true.")
            missing.append("lineage.revision_completed")

    if request.current_status == "ready_for_owner_review" and request.target_status == "owner_approved":
        if not request.reason.strip():
            errors.append("owner_approved transition requires non-empty reason (approval signal context).")
            missing.append("reason")

    if request.current_status == "owner_approved" and request.target_status == "handoff_ready":
        if request.artifact_type != ARTIFACT_TYPE_HANDOFF:
            errors.append("owner_approved -> handoff_ready is only valid for handoff artifact_type.")
        if isinstance(model, CouncilHandoffArtifact):
            if model.owner_approval_status != "approved":
                errors.append("handoff owner_approval_status must be approved for handoff_ready.")
                missing.append("owner_approval_status=approved")
            if model.execution_readiness_status != "ready":
                errors.append("handoff execution_readiness_status must be ready for handoff_ready.")
                missing.append("execution_readiness_status=ready")
        else:
            errors.append("handoff state validation requires a valid handoff artifact payload.")

    execution_candidate = False
    if model is not None:
        execution_candidate = _execution_candidate_for_handoff(model, request.target_status)

    if request.current_status == "owner_rejected" and request.target_status == "owner_approved":
        errors.append("owner_rejected artifacts cannot directly return to owner_approved without a new revision round.")

    is_valid = len(errors) == 0
    suggested_next_action = "transition accepted"
    if not is_valid:
        suggested_next_action = "fix validation errors and regenerate transition request with proper lineage/approval signals"
    elif request.target_status == "owner_approved" and not execution_candidate:
        suggested_next_action = "prepare/validate handoff readiness; owner_approved alone is not execution authorization"

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    audit_entry = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "from_status": request.current_status,
        "to_status": request.target_status,
        "is_valid": is_valid,
        "requested_by": request.requested_by,
        "requested_by_lane": request.requested_by_lane,
        "reason": request.reason,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "triggering_feedback_id": request.triggering_feedback_id,
        "triggering_artifact_id": request.triggering_artifact_id,
        "derived_artifact_id": None,
        "timestamp": timestamp,
    }

    return TransitionResult(
        is_valid=is_valid,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        from_status=from_status,
        to_status=to_status,
        validation_errors=errors,
        validation_warnings=warnings,
        required_missing_fields=missing,
        suggested_next_action=suggested_next_action,
        execution_gate_candidate=execution_candidate and is_valid,
        derived_artifact_id=None,
        audit_entry=audit_entry,
    )


def apply_transition(artifact: dict[str, Any], request: TransitionRequest) -> tuple[dict[str, Any], TransitionResult]:
    result = validate_transition(artifact, request)
    updated = dict(artifact)
    if result.is_valid:
        updated["status"] = request.target_status
        updated["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        trace = updated.get("audit_trace")
        if not isinstance(trace, list):
            trace = []
        trace.append(result.audit_entry)
        updated["audit_trace"] = trace
    return updated, result


def write_transition_audit(result: TransitionResult, output_path: Path = DEFAULT_AUDIT_PATH) -> None:
    payload = asdict(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/apply Council artifact state transition (v0.1).")
    parser.add_argument("--artifact", required=True, help="Artifact JSON path.")
    parser.add_argument("--request", required=True, help="Transition request JSON path.")
    parser.add_argument("--output", default=str(DEFAULT_AUDIT_PATH), help="Transition result artifact path.")
    parser.add_argument("--apply", action="store_true", help="Apply transition to artifact and overwrite file.")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    request_path = Path(args.request)
    artifact = _load_json(artifact_path)
    request = TransitionRequest.from_dict(_load_json(request_path))

    if args.apply:
        updated, result = apply_transition(artifact, request)
        artifact_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        result = validate_transition(artifact, request)

    write_transition_audit(result, Path(args.output))
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

