"""Round audit pack writer for semi-manual bridge v1.x.

This helper does not execute any bridge action.
It only consolidates round artifacts into:
1) machine-readable audit pack JSON
2) owner-facing summary markdown
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACTS = {
    "dispatch_ready": "artifacts/council_codex_dispatch_ready.json",
    "feishu_owner_action": "artifacts/council_feishu_owner_action.json",
    "feishu_round_bridge": "artifacts/council_feishu_action_round_bridge.json",
    "round_executor_result": "artifacts/council_bridge_round_executor_result.json",
    "continue_once_result": "artifacts/council_feishu_continue_once_result.json",
    "dispatch_completion": "artifacts/council_codex_dispatch_completion.json",
    "execution_receipt_skeleton": "artifacts/council_codex_execution_receipt_skeleton.json",
    "owner_final_review_summary": "artifacts/council_owner_final_review_summary.json",
}

DEFAULT_AUDIT_PACK_PATH = Path("artifacts") / "council_round_audit_pack.json"
DEFAULT_AUDIT_SUMMARY_PATH = Path("artifacts") / "council_round_audit_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_load(path: str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    return _load_json(p)


def _first_non_empty_str(data: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    inherited = data.get("inherited_identity")
    if isinstance(inherited, dict):
        iv = inherited.get(key)
        if isinstance(iv, str) and iv.strip():
            return iv.strip()
    return None


def _artifact_status(path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": path,
        "exists": isinstance(payload, dict),
    }


def _collect_identity(artifacts: dict[str, dict[str, Any] | None]) -> tuple[str | None, str | None, str | None, list[str]]:
    ids: dict[str, str | None] = {"request_id": None, "brief_id": None, "handoff_id": None}
    seen: dict[str, set[str]] = {"request_id": set(), "brief_id": set(), "handoff_id": set()}
    for payload in artifacts.values():
        for key in ["request_id", "brief_id", "handoff_id"]:
            value = _first_non_empty_str(payload, key)
            if value:
                seen[key].add(value)
                if ids[key] is None:
                    ids[key] = value
    notes: list[str] = []
    for key in ["request_id", "brief_id", "handoff_id"]:
        if len(seen[key]) > 1:
            notes.append(f"identity mismatch detected on {key}: {sorted(seen[key])}")
    return ids["request_id"], ids["brief_id"], ids["handoff_id"], notes


def _collect_executed_steps(artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    steps: list[str] = []
    if artifacts["dispatch_ready"] is not None:
        steps.append("dispatch_ready_generated")
    if artifacts["feishu_owner_action"] is not None:
        steps.append("owner_action_recorded")
    if artifacts["feishu_round_bridge"] is not None:
        steps.append("action_round_bridge_generated")
    executor = artifacts["round_executor_result"]
    if isinstance(executor, dict):
        status = executor.get("execution_status", "unknown")
        steps.append(f"round_executor:{status}")
    continue_once = artifacts["continue_once_result"]
    if isinstance(continue_once, dict):
        steps.append(f"continue_once:{continue_once.get('final_status', 'unknown')}")
        if continue_once.get("completion_check_attempted") is True:
            steps.append("completion_check_once_attempted")
        if continue_once.get("receipt_skeleton_attempted") is True:
            steps.append("receipt_skeleton_attempted")
    completion = artifacts["dispatch_completion"]
    if isinstance(completion, dict):
        steps.append(f"completion_capture:{completion.get('completion_observation_status', 'unknown')}")
    if artifacts["execution_receipt_skeleton"] is not None:
        steps.append("execution_receipt_skeleton_generated")
    if artifacts["owner_final_review_summary"] is not None:
        steps.append("owner_final_review_summary_generated")
    return steps


def _collect_owner_actions(artifacts: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    owner_action = artifacts["feishu_owner_action"]
    if isinstance(owner_action, dict):
        actions.append(
            {
                "type": "feishu_owner_action",
                "action": owner_action.get("owner_action"),
                "by": owner_action.get("action_by"),
                "at": owner_action.get("action_at"),
            }
        )
    final_review = artifacts["owner_final_review_summary"]
    if isinstance(final_review, dict):
        actions.append(
            {
                "type": "final_owner_decision",
                "action": final_review.get("final_owner_decision"),
                "by": "owner_manual",
                "at": None,
            }
        )
    return actions


def _compute_round_status(
    *,
    final_review: dict[str, Any] | None,
    completion: dict[str, Any] | None,
    continue_once: dict[str, Any] | None,
    round_executor: dict[str, Any] | None,
) -> str:
    if isinstance(final_review, dict) and isinstance(final_review.get("final_owner_decision"), str):
        return f"closed_{final_review.get('final_owner_decision')}"
    if isinstance(completion, dict):
        state = completion.get("completion_observation_status")
        if state == "execution_receipt_available":
            return "owner_review_ready"
        if isinstance(state, str):
            return f"post_dispatch_{state}"
    if isinstance(continue_once, dict):
        status = continue_once.get("final_status")
        if isinstance(status, str):
            return f"continue_once_{status}"
    if isinstance(round_executor, dict):
        status = round_executor.get("execution_status")
        if isinstance(status, str):
            return f"executor_{status}"
    return "in_progress"


def build_round_audit_pack(artifact_paths: dict[str, str]) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any] | None] = {
        key: _safe_load(path) for key, path in artifact_paths.items()
    }
    request_id, brief_id, handoff_id, identity_notes = _collect_identity(artifacts)
    completion_state = (
        artifacts["dispatch_completion"].get("completion_observation_status")
        if isinstance(artifacts["dispatch_completion"], dict)
        else "missing"
    )
    receipt_status = "missing"
    skeleton = artifacts["execution_receipt_skeleton"]
    if isinstance(skeleton, dict):
        receipt_status = str(skeleton.get("execution_receipt_status", "present_unknown"))
    final_review = artifacts["owner_final_review_summary"]
    final_decision = final_review.get("final_owner_decision") if isinstance(final_review, dict) else None

    missing = [name for name, payload in artifacts.items() if payload is None]
    audit_notes: list[str] = []
    if missing:
        audit_notes.append("missing artifacts: " + ", ".join(missing))
    audit_notes.extend(identity_notes)
    if not final_decision:
        audit_notes.append("round is not final-closed yet (no owner final decision artifact).")

    pack = {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "round_status": _compute_round_status(
            final_review=artifacts["owner_final_review_summary"],
            completion=artifacts["dispatch_completion"],
            continue_once=artifacts["continue_once_result"],
            round_executor=artifacts["round_executor_result"],
        ),
        "key_artifacts": {
            key: _artifact_status(path, artifacts[key]) for key, path in artifact_paths.items()
        },
        "executed_steps": _collect_executed_steps(artifacts),
        "owner_actions": _collect_owner_actions(artifacts),
        "completion_state": completion_state,
        "receipt_status": receipt_status,
        "final_decision": final_decision or "not_recorded",
        "audit_notes": audit_notes,
        "generated_at": _now_iso(),
    }
    return pack


def render_round_audit_summary_md(pack: dict[str, Any]) -> str:
    def _v(value: Any, default: str = "n/a") -> str:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return str(value)

    artifact_lines = []
    key_artifacts = pack.get("key_artifacts", {})
    if isinstance(key_artifacts, dict):
        for key, meta in key_artifacts.items():
            exists = meta.get("exists") if isinstance(meta, dict) else False
            path = meta.get("path") if isinstance(meta, dict) else ""
            state = "present" if exists else "missing"
            artifact_lines.append(f"- `{key}`: {state} ({path})")

    step_lines = []
    steps = pack.get("executed_steps", [])
    if isinstance(steps, list):
        step_lines = [f"- `{str(step)}`" for step in steps]

    action_lines = []
    actions = pack.get("owner_actions", [])
    if isinstance(actions, list):
        for act in actions:
            if isinstance(act, dict):
                action_lines.append(
                    f"- {act.get('type', 'owner_action')}: {act.get('action', 'n/a')} (by={act.get('by', 'n/a')})"
                )

    note_lines = []
    notes = pack.get("audit_notes", [])
    if isinstance(notes, list):
        note_lines = [f"- {str(n)}" for n in notes]

    lines = [
        "# Council Bridge Round Audit Summary",
        "",
        "## Round Identity",
        f"- request_id: {_v(pack.get('request_id'))}",
        f"- brief_id: {_v(pack.get('brief_id'))}",
        f"- handoff_id: {_v(pack.get('handoff_id'))}",
        "",
        "## Round Status",
        f"- round_status: {_v(pack.get('round_status'))}",
        f"- completion_state: {_v(pack.get('completion_state'))}",
        f"- receipt_status: {_v(pack.get('receipt_status'))}",
        f"- final_decision: {_v(pack.get('final_decision'))}",
        "",
        "## Key Artifacts",
        *(artifact_lines or ["- n/a"]),
        "",
        "## Executed Steps",
        *(step_lines or ["- n/a"]),
        "",
        "## Owner Actions",
        *(action_lines or ["- n/a"]),
        "",
        "## Audit Notes",
        *(note_lines or ["- n/a"]),
        "",
        "## Closing",
        "- 这份摘要用于复盘、汇报、归档与新会话续接，不触发任何执行动作。",
    ]
    return "\n".join(lines) + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write minimal bridge round audit pack.")
    parser.add_argument("--dispatch-ready", default=DEFAULT_ARTIFACTS["dispatch_ready"])
    parser.add_argument("--feishu-owner-action", default=DEFAULT_ARTIFACTS["feishu_owner_action"])
    parser.add_argument("--feishu-round-bridge", default=DEFAULT_ARTIFACTS["feishu_round_bridge"])
    parser.add_argument("--round-executor-result", default=DEFAULT_ARTIFACTS["round_executor_result"])
    parser.add_argument("--continue-once-result", default=DEFAULT_ARTIFACTS["continue_once_result"])
    parser.add_argument("--dispatch-completion", default=DEFAULT_ARTIFACTS["dispatch_completion"])
    parser.add_argument("--execution-receipt-skeleton", default=DEFAULT_ARTIFACTS["execution_receipt_skeleton"])
    parser.add_argument("--owner-final-review-summary", default=DEFAULT_ARTIFACTS["owner_final_review_summary"])
    parser.add_argument("--audit-pack-output", default=str(DEFAULT_AUDIT_PACK_PATH))
    parser.add_argument("--audit-summary-output", default=str(DEFAULT_AUDIT_SUMMARY_PATH))
    args = parser.parse_args()

    artifact_paths = {
        "dispatch_ready": args.dispatch_ready,
        "feishu_owner_action": args.feishu_owner_action,
        "feishu_round_bridge": args.feishu_round_bridge,
        "round_executor_result": args.round_executor_result,
        "continue_once_result": args.continue_once_result,
        "dispatch_completion": args.dispatch_completion,
        "execution_receipt_skeleton": args.execution_receipt_skeleton,
        "owner_final_review_summary": args.owner_final_review_summary,
    }
    pack = build_round_audit_pack(artifact_paths)
    summary_md = render_round_audit_summary_md(pack)

    pack_output = Path(args.audit_pack_output)
    summary_output = Path(args.audit_summary_output)
    write_json(pack_output, pack)
    write_text(summary_output, summary_md)

    print(json.dumps(pack, ensure_ascii=False, indent=2))
    print(f"\n[round-audit-pack-writer] saved pack: {pack_output.as_posix()}")
    print(f"[round-audit-pack-writer] saved summary: {summary_output.as_posix()}")


if __name__ == "__main__":
    main()

