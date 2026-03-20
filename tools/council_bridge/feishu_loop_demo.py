"""Feishu mobile review loop demo helper (v0).

This helper stitches together a semi-manual loop:
source artifact -> Feishu notification -> owner action -> continuation artifact.

It does not implement callbacks, orchestration, or automatic downstream execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.council_bridge.feishu_action_round_bridge import build_round_bridge, write_round_bridge
from tools.council_bridge.feishu_notifier import (
    _load_json,
    build_feishu_payload,
    is_feishu_send_success,
    resolve_keyword_marker,
    resolve_webhook_url,
    send_feishu_webhook,
    summarize_artifact,
)
from tools.council_bridge.feishu_owner_action_writer import (
    build_owner_action_artifact,
    write_owner_action_artifact,
)


DEFAULT_ACTION_OUTPUT = Path("artifacts") / "council_feishu_owner_action.json"
DEFAULT_CONTINUATION_OUTPUT = Path("artifacts") / "council_feishu_action_round_bridge.json"
DEFAULT_SUMMARY_OUTPUT = Path("artifacts") / "council_feishu_loop_demo_summary.json"


def _build_owner_readable_summary(
    *,
    source_artifact_path: Path,
    source_data: dict[str, Any],
    notification_level: str,
    send_mode: str,
    owner_action: str | None,
    continuation_status: str | None,
) -> dict[str, Any]:
    core_modules = ["feishu_notifier", "feishu_owner_action_writer", "feishu_action_round_bridge"]
    key_changes = [
        {
            "target": source_artifact_path.as_posix(),
            "change_type": "read",
            "purpose": "读取当前轮次的控制工件并生成 owner-facing 通知。",
        }
    ]
    if owner_action:
        key_changes.extend(
            [
                {
                    "target": DEFAULT_ACTION_OUTPUT.as_posix(),
                    "change_type": "new",
                    "purpose": "记录 owner 动作（dispatch/hold/needs_fix/reject）作为可审计输入。",
                },
                {
                    "target": DEFAULT_CONTINUATION_OUTPUT.as_posix(),
                    "change_type": "new",
                    "purpose": "生成 round continuation 建议，明确下一步链路。",
                },
            ]
        )

    successes = ["已生成飞书通知摘要文本。"]
    pending = []
    if send_mode == "send":
        successes.append("已尝试发送到 Feishu webhook。")
    else:
        pending.append("当前是 dry-run，尚未真实发送到 Feishu。")
    if owner_action:
        successes.append(f"已记录 owner_action={owner_action} 并生成 continuation artifact。")
    else:
        pending.append("未记录 owner action，回路尚未闭环。")

    next_actions = [
        {
            "what": "在终端查看摘要 JSON",
            "how": f"Get-Content -Raw {DEFAULT_SUMMARY_OUTPUT.as_posix()}",
            "where": DEFAULT_SUMMARY_OUTPUT.as_posix(),
        }
    ]
    if owner_action is None:
        next_actions.append(
            {
                "what": "在飞书发出明确动作",
                "how": "发送：dispatch / hold / needs_fix / reject",
                "where": "Feishu group chat",
            }
        )

    evidence = [
        {
            "artifact": source_artifact_path.as_posix(),
            "proves": "本轮 summary 基于该源 artifact 生成，身份链路可追溯。",
        },
        {
            "artifact": DEFAULT_SUMMARY_OUTPUT.as_posix(),
            "proves": "包含通知结果、owner-facing summary 与下一步动作建议。",
        },
    ]
    if owner_action:
        evidence.append(
            {
                "artifact": DEFAULT_CONTINUATION_OUTPUT.as_posix(),
                "proves": f"owner 动作已落盘并转化为 continuation 计划（state={continuation_status or 'n/a'}）。",
            }
        )

    return {
        "task_summary": {
            "what_we_did": "生成面向 owner 的控制链路通知摘要，并在可选情况下记录 owner_action continuation。",
            "core_modules": core_modules,
            "closed_loop": bool(owner_action),
        },
        "key_changes": key_changes,
        "outcome": {
            "successes": successes,
            "pending": pending,
            "run_state": "runnable" if owner_action else "notification_only",
        },
        "risks_or_gaps": [
            "dry-run 模式下不会验证真实 Feishu webhook 可达性。" if send_mode != "send" else "已发送但仍需群聊侧人工确认消息可见。",
            "owner_action 缺失时无法推进到下一轮自动链路。",
        ],
        "next_owner_action": next_actions,
        "concise_technical_evidence": evidence,
        "meta": {"notification_level": notification_level, "send_mode": send_mode},
    }


def run_feishu_loop_demo(
    source_artifact_path: Path,
    *,
    level: str = "brief",
    send_mode: str = "dry-run",
    webhook_url: str | None = None,
    keyword_marker: str | None = None,
    timeout_sec: int = 10,
    owner_action: str | None = None,
    owner_id: str | None = None,
    notes: str = "",
    action_output_path: Path = DEFAULT_ACTION_OUTPUT,
    continuation_output_path: Path = DEFAULT_CONTINUATION_OUTPUT,
) -> dict[str, Any]:
    source_data = _load_json(source_artifact_path)
    summary_text = summarize_artifact(str(source_artifact_path), source_data, level=level)
    marker = resolve_keyword_marker(keyword_marker)
    payload = build_feishu_payload(summary_text, keyword_marker=marker)

    notification_result: dict[str, Any]
    if send_mode == "send":
        webhook = resolve_webhook_url(webhook_url)
        if not webhook:
            raise ValueError(
                "Missing webhook URL. Use --webhook-url or AGENTCOMMERCE_FEISHU_WEBHOOK_URL or FEISHU_WEBHOOK_URL."
            )
        response = send_feishu_webhook(webhook, payload, timeout_sec=timeout_sec)
        success = is_feishu_send_success(response)
        notification_result = {
            "send_mode": "send",
            "feishu_send_success": success,
            "feishu_response": response,
        }
        if not success:
            code = response.get("code", "n/a")
            msg = response.get("msg", "unknown error")
            raise ValueError(f"Feishu webhook send failed: code={code}, msg={msg}")
    else:
        notification_result = {
            "send_mode": "dry-run",
            "feishu_send_success": False,
            "feishu_payload_preview": payload,
        }

    result: dict[str, Any] = {
        "source_artifact_path": source_artifact_path.as_posix(),
        "notification_level": level,
        "summary_text": summary_text,
        "notification_result": notification_result,
        "action_artifact_path": None,
        "continuation_artifact_path": None,
        "recommended_next_step": "Record owner action or continue manual review.",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }

    if owner_action:
        if not owner_id:
            raise ValueError("owner_id is required when owner_action is provided.")
        action_artifact = build_owner_action_artifact(
            source_data=source_data,
            source_artifact_path=source_artifact_path,
            owner_action=owner_action,
            owner_id=owner_id,
            notes=notes,
        )
        write_owner_action_artifact(action_output_path, action_artifact)
        continuation = build_round_bridge(action_artifact, source_path=action_output_path)
        write_round_bridge(continuation_output_path, continuation)
        result["action_artifact_path"] = action_output_path.as_posix()
        result["continuation_artifact_path"] = continuation_output_path.as_posix()
        result["recommended_next_step"] = continuation.get("recommended_next_step")
        result["round_flow_state"] = continuation.get("round_flow_state")

    result["owner_readable_summary"] = _build_owner_readable_summary(
        source_artifact_path=source_artifact_path,
        source_data=source_data,
        notification_level=level,
        send_mode=send_mode,
        owner_action=owner_action,
        continuation_status=result.get("round_flow_state"),
    )

    return result


def write_demo_summary(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu mobile review loop demo helper (v0).")
    parser.add_argument("--source-artifact", required=True, help="Source artifact path (dispatch_ready or completion).")
    parser.add_argument("--level", default="brief", choices=["brief", "detail"], help="Notification summary level.")
    parser.add_argument("--send-mode", default="dry-run", choices=["dry-run", "send"], help="Feishu send mode.")
    parser.add_argument("--webhook-url", default="", help="Optional explicit Feishu webhook URL.")
    parser.add_argument("--keyword-marker", default="", help="Optional keyword marker.")
    parser.add_argument("--timeout-sec", type=int, default=10, help="HTTP timeout for Feishu send.")
    parser.add_argument("--owner-action", default="", choices=["", "dispatch", "hold", "needs_fix", "reject"])
    parser.add_argument("--owner-id", default="", help="Owner id when owner-action is provided.")
    parser.add_argument("--notes", default="", help="Optional owner action notes.")
    parser.add_argument("--action-output", default=str(DEFAULT_ACTION_OUTPUT), help="Owner action artifact output path.")
    parser.add_argument(
        "--continuation-output",
        default=str(DEFAULT_CONTINUATION_OUTPUT),
        help="Continuation artifact output path.",
    )
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT), help="Demo summary output path.")
    args = parser.parse_args()

    result = run_feishu_loop_demo(
        source_artifact_path=Path(args.source_artifact),
        level=args.level,
        send_mode=args.send_mode,
        webhook_url=args.webhook_url,
        keyword_marker=args.keyword_marker,
        timeout_sec=args.timeout_sec,
        owner_action=args.owner_action or None,
        owner_id=args.owner_id or None,
        notes=args.notes,
        action_output_path=Path(args.action_output),
        continuation_output_path=Path(args.continuation_output),
    )
    summary_output = Path(args.summary_output)
    write_demo_summary(summary_output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[feishu-loop-demo] saved summary: {summary_output.as_posix()}")


if __name__ == "__main__":
    main()
