"""Demo scenarios for owner-confirmed execution dispatch v0.1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.execution_trigger_protocol import extract_execution_trigger
from tools.council_bridge.owner_confirmed_execution_dispatch import dispatch_owner_confirmed_execution


OUT_DIR = Path("artifacts") / "owner_confirmed_execution_dispatch_demo"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _handoff(*, readiness: str) -> dict[str, Any]:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": "handoff-dispatch-demo-001",
        "request_id": "req-dispatch-demo-001",
        "brief_id": "brief-dispatch-demo-001",
        "handoff_id": "handoff-dispatch-demo-001",
        "council_round": 1,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_dispatch_demo",
        "created_at": "2026-03-16T22:30:00+08:00",
        "updated_at": "2026-03-16T22:30:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": "handoff_ready",
        "summary": "dispatch demo",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "dispatch",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "run dispatch demo", "expected_outputs": ["receipt"]},
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["no destructive commands"],
        "no_go_zones": ["secrets"],
        "required_receipts": ["execution.receipt.v0.1"],
        "owner_approval_status": "approved",
        "execution_readiness_status": readiness,
    }


def run_demo() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, Any] = {}

    def fake_dispatch(**kwargs):
        return {"dispatch_status": "dispatched"}

    # A. valid dispatch
    case_a = OUT_DIR / "A_valid_dispatch"
    handoff_a = case_a / "handoff.json"
    _write(handoff_a, _handoff(readiness="ready"))
    trigger_a = extract_execution_trigger({"text": "dispatch_execution", "source": "feishu_action_protocol"})
    result_a = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_a,
        trigger=trigger_a,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed dispatch",
        dispatch_result_path=case_a / "dispatch_result.json",
        runtime_status_path=case_a / "runtime_status.json",
        execution_receipt_path=case_a / "execution_receipt.json",
        execution_brief_path=case_a / "execution_brief.json",
        dispatch_func=fake_dispatch,
    )
    scenarios["A_valid_dispatch"] = result_a

    # B. blocked dispatch (readiness != ready)
    case_b = OUT_DIR / "B_blocked_readiness"
    handoff_b = case_b / "handoff.json"
    _write(handoff_b, _handoff(readiness="blocked"))
    trigger_b = extract_execution_trigger({"text": "dispatch_execution", "source": "feishu_action_protocol"})
    result_b = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_b,
        trigger=trigger_b,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed dispatch",
        dispatch_result_path=case_b / "dispatch_result.json",
        runtime_status_path=case_b / "runtime_status.json",
        execution_receipt_path=case_b / "execution_receipt.json",
        execution_brief_path=case_b / "execution_brief.json",
    )
    scenarios["B_blocked_dispatch"] = result_b

    # C. invalid source (chat text includes keyword)
    case_c = OUT_DIR / "C_invalid_source"
    handoff_c = case_c / "handoff.json"
    _write(handoff_c, _handoff(readiness="ready"))
    trigger_c = extract_execution_trigger({"text": "dispatch_execution", "source": "feishu_chat"})
    result_c = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_c,
        trigger=trigger_c,
        confirmed_by="owner_001",
        confirmed_by_lane="chat",
        current_stage="execution_dispatch",
        reason="chat trigger",
        dispatch_result_path=case_c / "dispatch_result.json",
        runtime_status_path=case_c / "runtime_status.json",
        execution_receipt_path=case_c / "execution_receipt.json",
        execution_brief_path=case_c / "execution_brief.json",
    )
    scenarios["C_invalid_source"] = result_c

    # D. missing brief generation failure
    case_d = OUT_DIR / "D_brief_generation_failure"
    handoff_d = case_d / "handoff.json"
    _write(handoff_d, _handoff(readiness="ready"))
    trigger_d = extract_execution_trigger({"text": "dispatch_execution", "source": "feishu_action_protocol"})

    def boom_brief(*args, **kwargs):
        raise RuntimeError("mock brief generation failure")

    # force failure by passing broken brief mapper indirectly with dispatch function
    result_d = dispatch_owner_confirmed_execution(
        handoff_artifact_path=handoff_d,
        trigger=trigger_d,
        confirmed_by="owner_001",
        confirmed_by_lane="owner",
        current_stage="execution_dispatch",
        reason="owner confirmed dispatch",
        dispatch_result_path=case_d / "dispatch_result.json",
        runtime_status_path=case_d / "runtime_status.json",
        execution_receipt_path=case_d / "execution_receipt.json",
        execution_brief_path=case_d / "execution_brief.json",
        brief_builder=boom_brief,
    )
    scenarios["D_missing_or_failed_brief_dispatch"] = result_d

    summary = {"scenario_count": len(scenarios), "scenarios": scenarios}
    _write(OUT_DIR / "demo_summary.json", summary)
    return {"summary_path": (OUT_DIR / "demo_summary.json").as_posix(), "summary": summary}


def main() -> None:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
