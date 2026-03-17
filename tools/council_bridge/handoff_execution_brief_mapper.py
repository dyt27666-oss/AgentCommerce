"""Map a validated handoff artifact into standardized execution brief v0.1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BRIEF_OUTPUT_PATH = Path("artifacts") / "council_execution_brief.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_execution_brief(handoff: dict[str, Any], gate_result: dict[str, Any]) -> dict[str, Any]:
    payload = handoff.get("approved_execution_brief")
    if not isinstance(payload, dict):
        payload = {}

    objective = (
        payload.get("objective")
        or payload.get("goal")
        or handoff.get("summary")
        or "execution objective pending"
    )
    if not isinstance(objective, str):
        objective = str(objective)

    expected_outputs = payload.get("expected_outputs")
    if not isinstance(expected_outputs, list):
        expected_outputs = handoff.get("required_receipts") if isinstance(handoff.get("required_receipts"), list) else []

    risk_notes: list[str] = []
    no_go = handoff.get("no_go_zones")
    if isinstance(no_go, list) and no_go:
        risk_notes.append("no_go_zones enforced: " + "; ".join(str(x) for x in no_go))
    constraints = handoff.get("execution_constraints")
    if isinstance(constraints, list) and constraints:
        risk_notes.append("execution_constraints enforced: " + "; ".join(str(x) for x in constraints))

    return {
        "brief_version": "execution.brief.v0.1",
        "generated_at": _now_iso(),
        "source_handoff_id": handoff.get("handoff_id"),
        "objective": objective.strip(),
        "execution_scope": handoff.get("execution_scope") if isinstance(handoff.get("execution_scope"), list) else [],
        "execution_constraints": constraints if isinstance(constraints, list) else [],
        "no_go_zones": no_go if isinstance(no_go, list) else [],
        "expected_outputs": expected_outputs,
        "required_receipts": handoff.get("required_receipts") if isinstance(handoff.get("required_receipts"), list) else [],
        "risk_notes": risk_notes,
        "correlated_request_id": handoff.get("request_id"),
        "correlated_brief_id": handoff.get("brief_id"),
        "correlated_handoff_id": handoff.get("handoff_id"),
        "gate_reference": {
            "execution_handoff_ready": gate_result.get("execution_handoff_ready"),
            "gate_artifact_status": "observe_only",
        },
        "observe_only": True,
    }


def write_execution_brief(brief: dict[str, Any], output_path: Path = DEFAULT_BRIEF_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")

