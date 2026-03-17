"""Run minimal online council feedback shadow-mode scenarios.

This script exercises:
router -> mapping adapter -> state-machine validator -> artifact logging
in observe-only mode (no apply_transition).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_message_router import route_message


OUT_DIR = Path("artifacts") / "council_shadow_demo"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_plan_artifact(*, artifact_id: str, status: str, request_id: str, brief_id: str, with_revision_done: bool = False) -> dict[str, Any]:
    lineage: dict[str, Any] = {}
    parent = None
    derived: list[str] = []
    if with_revision_done:
        lineage["revision_completed"] = True
        parent = f"{artifact_id}-parent"
        derived = [f"{artifact_id}-parent"]
    return {
        "artifact_type": "plan",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": None,
        "council_round": 2 if with_revision_done else 1,
        "parent_artifact_id": parent,
        "derived_from_artifact_ids": derived,
        "owner_id": "owner_001",
        "chat_id": "oc_demo",
        "created_at": "2026-03-16T18:00:00+08:00",
        "updated_at": "2026-03-16T18:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "demo plan artifact",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": lineage,
        "objective": "demo",
        "scope": ["demo"],
        "steps": [{"step_id": "s1", "title": "demo"}],
        "dependencies": [],
        "acceptance_criteria": ["demo"],
        "proposed_execution_boundary": {"execution_allowed": False},
        "expected_outputs": ["demo"],
    }


def _build_risk_artifact(*, artifact_id: str, status: str, request_id: str, brief_id: str) -> dict[str, Any]:
    return {
        "artifact_type": "risk",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": None,
        "council_round": 1,
        "parent_artifact_id": None,
        "derived_from_artifact_ids": [],
        "owner_id": "owner_001",
        "chat_id": "oc_demo",
        "created_at": "2026-03-16T18:00:00+08:00",
        "updated_at": "2026-03-16T18:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "critic",
        "produced_by_roles": ["critic"],
        "status": status,
        "summary": "demo risk artifact",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "risk_items": [{"risk_id": "r1", "description": "demo"}],
        "severity": "medium",
        "likelihood": "medium",
        "mitigation": ["demo"],
        "blocked_actions": [],
        "escalation_conditions": [],
    }


def _build_handoff_artifact(*, artifact_id: str, status: str, request_id: str, brief_id: str, handoff_id: str) -> dict[str, Any]:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "council_round": 2,
        "parent_artifact_id": "decision-demo-001",
        "derived_from_artifact_ids": ["decision-demo-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_demo",
        "created_at": "2026-03-16T18:00:00+08:00",
        "updated_at": "2026-03-16T18:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": status,
        "summary": "demo handoff artifact",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "demo"},
        "execution_scope": ["demo"],
        "execution_constraints": ["demo constraints"],
        "no_go_zones": ["demo no-go"],
        "required_receipts": ["demo receipt"],
        "owner_approval_status": "approved",
        "execution_readiness_status": "blocked",
    }


def _payload(*, message_id: str, text: str) -> dict[str, Any]:
    return {
        "source": "feishu_chat",
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_demo",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": text,
        "create_time": "1711111111",
    }


def run_demo() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = [
        {
            "name": "风险分析不够",
            "text": "这个方案不行，风险分析不够",
            "artifact": _build_risk_artifact(
                artifact_id="risk-demo-001",
                status="under_review",
                request_id="req-demo-001",
                brief_id="brief-demo-001",
            ),
        },
        {
            "name": "scope 太宽",
            "text": "scope 这里还是太宽了",
            "artifact": _build_plan_artifact(
                artifact_id="plan-demo-001",
                status="under_review",
                request_id="req-demo-002",
                brief_id="brief-demo-002",
            ),
        },
        {
            "name": "receipt 没写清楚",
            "text": "handoff 还不能执行，receipt 要求没写清楚",
            "artifact": _build_handoff_artifact(
                artifact_id="handoff-demo-001",
                status="owner_approved",
                request_id="req-demo-003",
                brief_id="brief-demo-003",
                handoff_id="handoff-demo-001",
            ),
        },
        {
            "name": "这个可以，重新提交给我审核",
            "text": "这个可以，重新提交给我审核",
            "artifact": _build_plan_artifact(
                artifact_id="plan-demo-002",
                status="revised",
                request_id="req-demo-004",
                brief_id="brief-demo-004",
                with_revision_done=True,
            ),
        },
        {
            "name": "这个只是注释，不代表批准",
            "text": "这个只是注释，不代表批准",
            "artifact": _build_plan_artifact(
                artifact_id="plan-demo-003",
                status="ready_for_owner_review",
                request_id="req-demo-005",
                brief_id="brief-demo-005",
            ),
        },
        {
            "name": "再改改",
            "text": "再改改",
            "artifact": _build_plan_artifact(
                artifact_id="plan-demo-004",
                status="under_review",
                request_id="req-demo-006",
                brief_id="brief-demo-006",
            ),
        },
    ]

    outputs: list[dict[str, Any]] = []
    for idx, case in enumerate(scenarios, start=1):
        slug = f"{idx:02d}"
        artifact_path = OUT_DIR / f"{slug}_artifact.json"
        route_path = OUT_DIR / f"{slug}_route_result.json"
        mapping_path = OUT_DIR / f"{slug}_mapping_result.json"
        validation_path = OUT_DIR / f"{slug}_validation_result.json"
        dedupe_path = OUT_DIR / f"{slug}_dedupe.json"
        queue_db = OUT_DIR / f"{slug}_queue.db"
        _write_json(artifact_path, case["artifact"])

        result = route_message(
            _payload(message_id=f"m-demo-{slug}", text=case["text"]),
            source_artifact=artifact_path.as_posix(),
            stage="council_review",
            dedupe_state_path=dedupe_path,
            route_result_path=route_path,
            queue_db_path=queue_db,
            council_mapping_result_path=mapping_path,
            council_transition_result_path=validation_path,
        )

        mapping = {}
        if mapping_path.exists():
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        validation: dict[str, Any] | None = None
        if validation_path.exists():
            validation = json.loads(validation_path.read_text(encoding="utf-8"))

        outputs.append(
            {
                "scenario": case["name"],
                "input_text": case["text"],
                "route_result_path": route_path.as_posix(),
                "mapping_result_path": mapping_path.as_posix(),
                "validation_result_path": validation_path.as_posix() if validation is not None else None,
                "route_result": result,
                "mapping_result": mapping,
                "validation_result": validation,
                "human_readable_summary": result.get("result_info"),
            }
        )

    summary = {"observe_only": True, "scenario_count": len(outputs), "scenarios": outputs}
    summary_path = OUT_DIR / "demo_summary.json"
    _write_json(summary_path, summary)
    return {"summary_path": summary_path.as_posix(), "summary": summary}


def main() -> None:
    result = run_demo()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

