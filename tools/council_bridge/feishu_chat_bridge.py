"""Free-text chat bridge: queue task -> context summary -> Feishu reply."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_sender import send_text


CHAT_REQUEST_PATH = Path("artifacts") / "council_feishu_chat_bridge_request.json"
CHAT_RESULT_PATH = Path("artifacts") / "council_feishu_chat_bridge_result.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_context_summary(correlated: dict[str, Any]) -> str:
    c = []
    for key, label in [
        ("artifacts/council_feishu_message_route_result.json", "最近路由结果"),
        ("artifacts/council_feishu_continue_once_result.json", "最近续跑结果"),
        ("artifacts/council_final_review_once_result.json", "最近最终拍板执行"),
        ("artifacts/council_owner_final_review_summary.json", "最近最终拍板摘要"),
    ]:
        payload = _safe_load(Path(key))
        if not isinstance(payload, dict):
            continue
        if "result_status" in payload:
            c.append(f"{label}: status={payload.get('result_status')} route={payload.get('routed_entrypoint')}")
        elif "final_status" in payload:
            c.append(f"{label}: final_status={payload.get('final_status')} flow={payload.get('flow_state')}")
        elif "summary_status" in payload:
            c.append(f"{label}: summary_status={payload.get('summary_status')} decision={payload.get('final_decision')}")
        elif "final_owner_decision" in payload:
            c.append(f"{label}: final_owner_decision={payload.get('final_owner_decision')}")
    req = correlated.get("request_id") or "n/a"
    brief = correlated.get("brief_id") or "n/a"
    handoff = correlated.get("handoff_id") or "n/a"
    head = f"关联身份: request_id={req}, brief_id={brief}, handoff_id={handoff}"
    return "\n".join([head] + c) if c else head


def _build_reply_text(*, user_text: str, correlated: dict[str, Any]) -> str:
    summary = _build_context_summary(correlated)
    return (
        "【Bridge Chat 摘要】\n"
        f"你刚刚的问题：{user_text}\n"
        f"{summary}\n"
        "建议：如果你要继续执行动作，请直接回复协议动作词（dispatch / approved / needs_fix 等）；"
        "如果你需要我生成下一条 Codex 指令，请明确说“生成下一条指令”。"
    )


def process_chat_task(
    task: dict[str, Any],
    *,
    request_artifact_path: Path | None = None,
    result_artifact_path: Path | None = None,
    webhook_url: str | None = None,
    force_send_error: bool = False,
) -> dict[str, Any]:
    request_artifact_path = request_artifact_path or CHAT_REQUEST_PATH
    result_artifact_path = result_artifact_path or CHAT_RESULT_PATH
    payload = task.get("payload", {})
    message_payload = payload.get("message_payload", {})
    user_text = str(message_payload.get("text") or "")
    correlated = {
        "request_id": payload.get("correlated_request_id"),
        "brief_id": payload.get("correlated_brief_id"),
        "handoff_id": payload.get("correlated_handoff_id"),
    }
    request_obj = {
        "route_type": "chat",
        "source": message_payload.get("source", "unknown"),
        "task_id": task.get("task_id"),
        "owner_id": message_payload.get("sender_id"),
        "chat_id": message_payload.get("chat_id"),
        "message_id": message_payload.get("message_id"),
        "execution_status": "received",
        "correlated_request_id": correlated["request_id"],
        "correlated_brief_id": correlated["brief_id"],
        "correlated_handoff_id": correlated["handoff_id"],
        "user_text": user_text,
        "created_at": _now_iso(),
    }
    _write_json(request_artifact_path, request_obj)

    reply_text = _build_reply_text(user_text=user_text, correlated=correlated)
    result = {
        "route_type": "chat",
        "source": message_payload.get("source", "unknown"),
        "task_id": task.get("task_id"),
        "owner_id": message_payload.get("sender_id"),
        "chat_id": message_payload.get("chat_id"),
        "message_id": message_payload.get("message_id"),
        "execution_status": "completed",
        "reply_status": "sent",
        "ignored_reason": "",
        "error_message": "",
        "correlated_request_id": correlated["request_id"],
        "correlated_brief_id": correlated["brief_id"],
        "correlated_handoff_id": correlated["handoff_id"],
        "reply_preview": reply_text[:300],
        "completed_at": _now_iso(),
    }
    try:
        if force_send_error:
            raise RuntimeError("forced_send_error")
        send_resp = send_text(text=reply_text, webhook_url=webhook_url)
        result["feishu_send_response"] = send_resp
    except Exception as exc:
        result["execution_status"] = "failed"
        result["reply_status"] = "failed"
        result["error_message"] = str(exc)
    _write_json(result_artifact_path, result)
    return result
