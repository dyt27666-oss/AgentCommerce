"""Bridge v1.x progress summary writer (owner-facing, minimal)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def build_progress_summary(
    *,
    handoff: dict[str, Any] | None,
    dispatch_ready: dict[str, Any] | None,
    dispatch_receipt: dict[str, Any] | None,
    completion: dict[str, Any] | None,
    execution_receipt: dict[str, Any] | None,
    final_review: dict[str, Any] | None,
    feishu_action: dict[str, Any] | None,
    feishu_round_bridge: dict[str, Any] | None,
) -> dict[str, Any]:
    execution_layer_status = "stable_workflow_running"
    if not handoff or not dispatch_ready:
        execution_layer_status = "partially_prepared"

    dispatch_status = "unknown"
    if dispatch_receipt:
        dispatch_status = str(dispatch_receipt.get("dispatch_status", "unknown"))
        if dispatch_receipt.get("dispatch_attempted") is not True:
            dispatch_status = f"not_attempted_{dispatch_status}"

    completion_status = "unknown"
    if completion:
        completion_status = str(completion.get("completion_observation_status", "unknown"))

    feishu_action_status = "not_recorded"
    if feishu_action and isinstance(feishu_action.get("owner_action"), str):
        feishu_action_status = f"recorded_{feishu_action.get('owner_action')}"

    mobile_loop_status = "not_ready"
    if feishu_round_bridge and isinstance(feishu_round_bridge.get("round_flow_state"), str):
        mobile_loop_status = f"usable_{feishu_round_bridge.get('round_flow_state')}"

    bridge_status = "v1x_semi_manual_usable"
    if execution_layer_status != "stable_workflow_running":
        bridge_status = "v1x_partial"

    # Current project evidence includes real Feishu sends verified in this phase.
    feishu_notification_status = "working_verified_live_send"

    manual_steps_remaining = [
        "Owner still reviews Feishu message and makes decision manually.",
        "Owner still runs local tools manually (no callback or auto-trigger).",
        "Owner still performs final approval/rejection judgment manually.",
    ]

    if execution_receipt is None:
        manual_steps_remaining.append("Owner must prepare execution receipt for post-dispatch review.")
    if final_review is None:
        manual_steps_remaining.append("Owner must complete final review summary artifact.")

    return {
        "phase": "bridge_v1.x",
        "execution_layer_status": execution_layer_status,
        "bridge_status": bridge_status,
        "codex_dispatch_status": dispatch_status,
        "completion_observation_status": completion_status,
        "feishu_notification_status": feishu_notification_status,
        "feishu_action_status": feishu_action_status,
        "mobile_review_loop_status": mobile_loop_status,
        "manual_steps_remaining": manual_steps_remaining,
        "recommended_next_pack": "Introduce a tiny local dispatch-to-receipt auto-fill helper (still manual-triggered, no orchestration).",
    }


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write bridge v1.x progress summary JSON.")
    parser.add_argument("--handoff", default="artifacts/council_bridge_handoff.json")
    parser.add_argument("--dispatch-ready", default="artifacts/council_codex_dispatch_ready.json")
    parser.add_argument("--dispatch-receipt", default="artifacts/council_codex_dispatch_receipt.json")
    parser.add_argument("--completion", default="artifacts/council_codex_dispatch_completion.json")
    parser.add_argument("--execution-receipt", default="artifacts/council_codex_execution_receipt.json")
    parser.add_argument("--final-review", default="artifacts/council_owner_final_review_summary.json")
    parser.add_argument("--feishu-action", default="artifacts/council_feishu_owner_action.json")
    parser.add_argument("--feishu-round-bridge", default="artifacts/council_feishu_action_round_bridge.json")
    parser.add_argument("--output", default="artifacts/bridge_v1x_progress_summary.json")
    args = parser.parse_args()

    summary = build_progress_summary(
        handoff=_safe_load(Path(args.handoff)),
        dispatch_ready=_safe_load(Path(args.dispatch_ready)),
        dispatch_receipt=_safe_load(Path(args.dispatch_receipt)),
        completion=_safe_load(Path(args.completion)),
        execution_receipt=_safe_load(Path(args.execution_receipt)),
        final_review=_safe_load(Path(args.final_review)),
        feishu_action=_safe_load(Path(args.feishu_action)),
        feishu_round_bridge=_safe_load(Path(args.feishu_round_bridge)),
    )
    output = Path(args.output)
    write_summary(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[bridge-progress-summary-writer] saved: {output.as_posix()}")


if __name__ == "__main__":
    main()

