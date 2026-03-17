"""Run owner-confirmed apply transition demo scenarios (v0.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_message_router import route_message


OUT_DIR = Path("artifacts") / "council_owner_apply_demo"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _plan(status: str, *, artifact_id: str, request_id: str, brief_id: str, revision_done: bool = False) -> dict[str, Any]:
    lineage: dict[str, Any] = {}
    parent = None
    derived: list[str] = []
    if revision_done:
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
        "council_round": 1,
        "parent_artifact_id": parent,
        "derived_from_artifact_ids": derived,
        "owner_id": "owner_001",
        "chat_id": "oc_apply_demo",
        "created_at": "2026-03-16T20:00:00+08:00",
        "updated_at": "2026-03-16T20:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "planner",
        "produced_by_roles": ["planner"],
        "status": status,
        "summary": "owner apply demo artifact",
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


def _handoff(status: str, *, artifact_id: str, request_id: str, brief_id: str) -> dict[str, Any]:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": artifact_id,
        "council_round": 2,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_apply_demo",
        "created_at": "2026-03-16T20:00:00+08:00",
        "updated_at": "2026-03-16T20:00:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": status,
        "summary": "handoff demo",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "next",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "demo"},
        "execution_scope": ["demo"],
        "execution_constraints": ["demo"],
        "no_go_zones": ["demo"],
        "required_receipts": ["demo"],
        "owner_approval_status": "approved",
        "execution_readiness_status": "blocked",
    }


def _payload(*, text: str, message_id: str, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_apply_demo",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": text,
        "create_time": "1711111111",
    }


def _run_pair(case_dir: Path, *, artifact: dict[str, Any], observe_text: str, confirm_text: str) -> dict[str, Any]:
    artifact_path = case_dir / "artifact.json"
    mapping_path = case_dir / "mapping.json"
    validation_path = case_dir / "validation.json"
    apply_path = case_dir / "apply.json"
    route_observe = case_dir / "route_observe.json"
    route_confirm = case_dir / "route_confirm.json"
    dedupe1 = case_dir / "dedupe1.json"
    dedupe2 = case_dir / "dedupe2.json"
    queue_db = case_dir / "queue.db"
    _write_json(artifact_path, artifact)

    observe_result = route_message(
        _payload(text=observe_text, message_id=f"{case_dir.name}-observe", source="feishu_chat"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=dedupe1,
        route_result_path=route_observe,
        queue_db_path=queue_db,
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
    )

    confirm_result = route_message(
        _payload(text=confirm_text, message_id=f"{case_dir.name}-confirm", source="feishu_action_protocol"),
        source_artifact=artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=dedupe2,
        route_result_path=route_confirm,
        queue_db_path=queue_db,
        council_mapping_result_path=mapping_path,
        council_transition_result_path=validation_path,
        council_owner_apply_result_path=apply_path,
    )

    mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else None
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else None
    apply = json.loads(apply_path.read_text(encoding="utf-8")) if apply_path.exists() else None
    updated = json.loads(artifact_path.read_text(encoding="utf-8"))
    return {
        "observe_route_result": observe_result,
        "confirm_route_result": confirm_result,
        "mapping_result": mapping,
        "validation_result": validation,
        "apply_result": apply,
        "artifact_after": updated,
        "human_readable_summary": confirm_result.get("result_info") or observe_result.get("result_info"),
    }


def run_demo() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "01_under_review_to_needs_fix": _run_pair(
            OUT_DIR / "01_under_review_to_needs_fix",
            artifact=_plan("under_review", artifact_id="plan-apply-demo-001", request_id="req-a1", brief_id="brief-a1"),
            observe_text="这个方案不行，风险分析不够",
            confirm_text="apply_suggested_transition",
        ),
        "02_revised_to_resubmitted": _run_pair(
            OUT_DIR / "02_revised_to_resubmitted",
            artifact=_plan(
                "revised",
                artifact_id="plan-apply-demo-002",
                request_id="req-a2",
                brief_id="brief-a2",
                revision_done=True,
            ),
            observe_text="这个可以，重新提交给我审核",
            confirm_text="apply_suggested_transition",
        ),
        "03_illegal_transition_blocked": _run_pair(
            OUT_DIR / "03_illegal_transition_blocked",
            artifact=_handoff("owner_approved", artifact_id="handoff-apply-demo-001", request_id="req-a3", brief_id="brief-a3"),
            observe_text="handoff 还不能执行，receipt 要求没写清楚",
            confirm_text="apply_suggested_transition",
        ),
    }

    chat_case_dir = OUT_DIR / "04_chat_cannot_confirm"
    chat_case_dir.mkdir(parents=True, exist_ok=True)
    chat_artifact_path = chat_case_dir / "artifact.json"
    _write_json(chat_artifact_path, _plan("under_review", artifact_id="plan-apply-demo-004", request_id="req-a4", brief_id="brief-a4"))
    chat_result = route_message(
        _payload(text="行吧 apply_suggested_transition", message_id="chat-confirm-01", source="feishu_chat"),
        source_artifact=chat_artifact_path.as_posix(),
        stage="council_review",
        dedupe_state_path=chat_case_dir / "dedupe.json",
        route_result_path=chat_case_dir / "route.json",
        queue_db_path=chat_case_dir / "queue.db",
        council_mapping_result_path=chat_case_dir / "mapping.json",
        council_transition_result_path=chat_case_dir / "validation.json",
        council_owner_apply_result_path=chat_case_dir / "apply.json",
    )
    scenarios["04_chat_cannot_confirm"] = {
        "confirm_route_result": chat_result,
        "artifact_after": json.loads(chat_artifact_path.read_text(encoding="utf-8")),
        "human_readable_summary": chat_result.get("result_info"),
    }

    summary = {"scenario_count": len(scenarios), "scenarios": scenarios}
    _write_json(OUT_DIR / "demo_summary.json", summary)
    return {"summary_path": (OUT_DIR / "demo_summary.json").as_posix(), "summary": summary}


def main() -> None:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

