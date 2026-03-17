"""Execution handoff gate validator v0.1.

This gate decides whether a handoff artifact can be transferred to execution lane.
It does not dispatch execution; it only produces gate results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.council_artifact_schema import CouncilHandoffArtifact, parse_council_artifact


DEFAULT_GATE_OUTPUT_PATH = Path("artifacts") / "council_execution_handoff_gate_result.json"
ALLOWED_GATE_STAGES = {"owner_review", "execution_gate"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _gate_item(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"gate": name, "passed": passed, "detail": detail}


def validate_execution_handoff_gate(
    *,
    artifact: dict[str, Any],
    current_stage: str,
    trigger: dict[str, Any],
) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    errors: list[str] = []
    handoff: CouncilHandoffArtifact | None = None

    try:
        parsed = parse_council_artifact(artifact)
        if isinstance(parsed, CouncilHandoffArtifact):
            handoff = parsed
        else:
            errors.append("artifact_type must be handoff.")
    except Exception as exc:
        errors.append(f"artifact schema parse failed: {exc}")

    if handoff is not None:
        gates.append(_gate_item("artifact_type_handoff", True, "handoff artifact recognized."))
    else:
        gates.append(_gate_item("artifact_type_handoff", False, "artifact is not a valid handoff object."))

    if handoff is not None and handoff.base.status == "handoff_ready":
        gates.append(_gate_item("status_handoff_ready", True, "handoff status is handoff_ready."))
    else:
        gates.append(_gate_item("status_handoff_ready", False, "handoff status must be handoff_ready."))

    if handoff is not None and handoff.owner_approval_status == "approved":
        gates.append(_gate_item("owner_approval_status", True, "owner_approval_status=approved."))
    else:
        gates.append(_gate_item("owner_approval_status", False, "owner_approval_status must be approved."))

    if handoff is not None and handoff.execution_readiness_status == "ready":
        gates.append(_gate_item("execution_readiness_status", True, "execution_readiness_status=ready."))
    else:
        gates.append(_gate_item("execution_readiness_status", False, "execution_readiness_status must be ready."))

    if current_stage in ALLOWED_GATE_STAGES:
        gates.append(_gate_item("stage_policy_allowed", True, f"stage={current_stage} allowed."))
    else:
        gates.append(_gate_item("stage_policy_allowed", False, f"stage={current_stage} not allowed for execution handoff gate."))

    required_fields_ok = False
    if handoff is not None:
        has_constraints = isinstance(handoff.execution_constraints, list) and len(handoff.execution_constraints) > 0
        has_no_go = isinstance(handoff.no_go_zones, list) and len(handoff.no_go_zones) > 0
        has_receipts = isinstance(handoff.required_receipts, list) and len(handoff.required_receipts) > 0
        required_fields_ok = has_constraints and has_no_go and has_receipts
    gates.append(
        _gate_item(
            "required_execution_fields",
            required_fields_ok,
            "execution_constraints/no_go_zones/required_receipts must be non-empty.",
        )
    )

    trigger_ok = bool(trigger.get("is_trigger")) and bool(trigger.get("authorized"))
    trigger_detail = "explicit execution trigger accepted." if trigger_ok else str(trigger.get("ignored_reason") or "missing explicit trigger.")
    gates.append(_gate_item("explicit_execution_trigger", trigger_ok, trigger_detail))

    pass_all = all(item["passed"] for item in gates)
    blocking = [f"{x['gate']}: {x['detail']}" for x in gates if not x["passed"]]
    if errors:
        blocking.extend(errors)

    result = {
        "event_time": _now_iso(),
        "artifact_id": artifact.get("artifact_id"),
        "artifact_type": artifact.get("artifact_type"),
        "request_id": artifact.get("request_id"),
        "brief_id": artifact.get("brief_id"),
        "handoff_id": artifact.get("handoff_id"),
        "current_status": artifact.get("status"),
        "current_stage": current_stage,
        "trigger": trigger,
        "gate_results": gates,
        "execution_handoff_ready": pass_all,
        "observe_only": True,
        "blocked_reason": " | ".join(blocking) if not pass_all else "",
        "next_action": (
            "Owner may proceed to owner-confirmed execution dispatch step (not automatic)."
            if pass_all
            else "Resolve blocked gates, then retry execution handoff gate."
        ),
    }
    return result


def write_execution_handoff_gate_result(result: dict[str, Any], output_path: Path = DEFAULT_GATE_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

