"""Observe-only demo for execution handoff gate v0.1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_message_router import route_message


OUT_DIR = Path("artifacts") / "execution_handoff_observe_demo"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _handoff(*, artifact_id: str, readiness: str) -> dict[str, Any]:
    return {
        "artifact_type": "handoff",
        "schema_version": "council.artifact.v0.1",
        "artifact_id": artifact_id,
        "request_id": f"req-{artifact_id}",
        "brief_id": f"brief-{artifact_id}",
        "handoff_id": artifact_id,
        "council_round": 2,
        "parent_artifact_id": "decision-001",
        "derived_from_artifact_ids": ["decision-001"],
        "owner_id": "owner_001",
        "chat_id": "oc_exec_demo",
        "created_at": "2026-03-16T21:30:00+08:00",
        "updated_at": "2026-03-16T21:30:00+08:00",
        "produced_by_lane": "council",
        "produced_by_role": "strategist",
        "produced_by_roles": ["strategist"],
        "status": "handoff_ready",
        "summary": "execution handoff observe demo",
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "next_action": "owner check gate",
        "owner_feedback": [],
        "audit_trace": [],
        "lineage": {},
        "approved_execution_brief": {"goal": "prepare execution", "expected_outputs": ["execution receipt"]},
        "execution_scope": ["tools/council_bridge"],
        "execution_constraints": ["no destructive commands", "respect no_go_zones"],
        "no_go_zones": ["prod data", "secrets"],
        "required_receipts": ["execution.receipt.v0.1"],
        "owner_approval_status": "approved",
        "execution_readiness_status": readiness,
    }


def _payload(message_id: str) -> dict[str, Any]:
    return {
        "source": "feishu_action_protocol",
        "event_id": f"ev-{message_id}",
        "message_id": message_id,
        "chat_id": "oc_exec_demo",
        "sender_id": "owner_001",
        "sender_name": "Owner",
        "text": "dispatch_execution",
        "create_time": "1711111111",
    }


def run_demo() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for idx, readiness in enumerate(["ready", "blocked"], start=1):
        case_dir = OUT_DIR / f"{idx:02d}_{readiness}"
        artifact_path = case_dir / "handoff.json"
        route_path = case_dir / "route.json"
        gate_path = case_dir / "gate.json"
        brief_path = case_dir / "brief.json"
        _write(artifact_path, _handoff(artifact_id=f"handoff-exec-demo-{idx}", readiness=readiness))
        result = route_message(
            _payload(f"exec-demo-{idx}"),
            source_artifact=artifact_path.as_posix(),
            stage="execution_gate",
            dedupe_state_path=case_dir / "dedupe.json",
            route_result_path=route_path,
            queue_db_path=case_dir / "queue.db",
            council_execution_gate_result_path=gate_path,
            council_execution_brief_path=brief_path,
        )
        gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}
        brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else None
        scenarios.append(
            {
                "readiness": readiness,
                "route_result": result,
                "gate_result": gate,
                "brief_generated": brief is not None,
                "brief_path": brief_path.as_posix() if brief is not None else None,
                "human_readable_summary": result.get("result_info"),
            }
        )

    summary = {"observe_only": True, "scenario_count": len(scenarios), "scenarios": scenarios}
    _write(OUT_DIR / "demo_summary.json", summary)
    return {"summary_path": (OUT_DIR / "demo_summary.json").as_posix(), "summary": summary}


def main() -> None:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

