"""Free-text chat bridge: queue task -> context summary -> Feishu reply."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_sender import send_text
from tools.council_bridge.permission_policy import evaluate_permission_context
from tools.council_bridge.chat_llm_adapter import generate_chat_reply


CHAT_REQUEST_PATH = Path("artifacts") / "council_feishu_chat_bridge_request.json"
CHAT_RESULT_PATH = Path("artifacts") / "council_feishu_chat_bridge_result.json"
ROUTE_RESULT_PATH = Path("artifacts") / "council_feishu_message_route_result.json"
CONTINUE_RESULT_PATH = Path("artifacts") / "council_feishu_continue_once_result.json"
FINAL_REVIEW_RESULT_PATH = Path("artifacts") / "council_final_review_once_result.json"
OWNER_FINAL_SUMMARY_PATH = Path("artifacts") / "council_owner_final_review_summary.json"
LOCAL_CHECK_PREFIX = "查:"
LOCAL_PERMISSION_PREFIX = "允许本地权限："
LEGACY_LOCAL_CHECK_CONFIRM_TOKEN = "CONFIRM_LOCAL_CHECK"


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
    lines: list[str] = []

    route_payload = _safe_load(ROUTE_RESULT_PATH)
    continue_payload = _safe_load(CONTINUE_RESULT_PATH)
    final_review_payload = _safe_load(FINAL_REVIEW_RESULT_PATH)
    owner_final_payload = _safe_load(OWNER_FINAL_SUMMARY_PATH)

    if isinstance(route_payload, dict):
        lines.append(
            "最近路由: "
            f"status={route_payload.get('result_status', 'n/a')} "
            f"route={route_payload.get('routed_entrypoint', 'n/a')} "
            f"stage={route_payload.get('action_stage', 'n/a')}"
        )

    if isinstance(continue_payload, dict):
        lines.append(
            "最近续跑: "
            f"final_status={continue_payload.get('final_status', 'n/a')} "
            f"flow={continue_payload.get('flow_state', 'n/a')} "
            f"next={continue_payload.get('next_manual_action', 'n/a')}"
        )

    if isinstance(final_review_payload, dict):
        lines.append(
            "最近最终拍板执行: "
            f"summary_status={final_review_payload.get('summary_status', 'n/a')} "
            f"decision={final_review_payload.get('final_decision', 'n/a')}"
        )

    if isinstance(owner_final_payload, dict):
        lines.append(
            "最近最终拍板摘要: "
            f"final_owner_decision={owner_final_payload.get('final_owner_decision', 'n/a')} "
            f"execution_status={owner_final_payload.get('execution_status', 'n/a')}"
        )

    req = correlated.get("request_id") or "n/a"
    brief = correlated.get("brief_id") or "n/a"
    handoff = correlated.get("handoff_id") or "n/a"
    head = f"关联身份: request_id={req}, brief_id={brief}, handoff_id={handoff}"
    return "\n".join([head] + lines) if lines else head


def _is_workflow_control_intent(user_text: str) -> bool:
    text = str(user_text or "").strip().lower()
    if not text:
        return False
    tokens = [
        "dispatch",
        "approved",
        "needs_fix",
        "reject",
        "hold",
        "开始执行",
        "运行测试",
        "execute",
        "apply_suggested_transition",
        "confirm_transition",
        "生成下一条指令",
        "下一条指令",
        "继续执行",
        "进入执行",
        "审批",
        "拍板",
    ]
    return any(token in text for token in tokens)


def _is_local_machine_question(user_text: str) -> bool:
    raw = str(user_text or "").strip()
    if raw.startswith(LOCAL_PERMISSION_PREFIX) or raw.startswith(LOCAL_CHECK_PREFIX):
        return True
    text = raw.lower()
    keywords = [
        "电脑",
        "本机",
        "本地",
        "应用",
        "进程",
        "正在运行",
        "运行中",
        "任务管理器",
        "installed app",
        "process",
        "feishu",
        "lark",
    ]
    return any(k in text for k in keywords)


def _is_local_feishu_query_intent(user_text: str) -> bool:
    text = str(user_text or "").strip().lower()
    keywords = [
        "飞书",
        "feishu",
        "lark",
        "是否运行",
        "在运行中",
        "进程",
        "process",
    ]
    return any(k in text for k in keywords)


def _has_local_check_confirmation(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if text.startswith(LOCAL_CHECK_PREFIX):
        return True
    if text.startswith(LOCAL_PERMISSION_PREFIX):
        return True
    return LEGACY_LOCAL_CHECK_CONFIRM_TOKEN in text


def _extract_local_permission_command(user_text: str) -> str:
    text = str(user_text or "").strip()
    if text.startswith(LOCAL_PERMISSION_PREFIX):
        return text[len(LOCAL_PERMISSION_PREFIX) :].strip()
    if text.startswith(LOCAL_CHECK_PREFIX):
        return text[len(LOCAL_CHECK_PREFIX) :].strip()
    return text


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _query_local_feishu_processes() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["cmd", "/c", "tasklist"],
            capture_output=True,
            text=False,
            timeout=10,
        )
        raw = proc.stdout or proc.stderr or b""
        text = _decode_bytes(raw)
        if proc.returncode != 0:
            return False, f"本机进程查询失败，exit_code={proc.returncode}"

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        hits = [
            ln
            for ln in lines
            if ("feishu" in ln.lower()) or ("lark" in ln.lower()) or ("飞书" in ln)
        ]
        if not hits:
            return True, "未检测到飞书相关进程（Feishu/Lark）。"

        preview = "\n".join(hits[:5])
        return True, f"检测到飞书相关进程 {len(hits)} 条：\n{preview}"
    except Exception as exc:
        return False, f"本机进程查询异常：{exc}"


def _build_reply_text(*, user_text: str, correlated: dict[str, Any]) -> str:
    req = correlated.get("request_id") or "n/a"
    context_suffix = f"\n上下文 request_id={req}" if req != "n/a" else ""

    if _is_workflow_control_intent(user_text):
        return (
            "这是执行请求，不按聊天消息直接触发，避免误执行。"
            "\n请发送协议动作词：dispatch / approved / needs_fix / reject / hold"
            "\n或直接说：生成下一条指令。"
            f"{context_suffix}"
        )

    if _is_local_machine_question(user_text):
        cmd_text = _extract_local_permission_command(user_text)
        if _is_local_feishu_query_intent(cmd_text):
            permission = evaluate_permission_context(user_text)
            if not _has_local_check_confirmation(user_text):
                return (
                    "这是本机只读查询请求，但当前授权不足。"
                    f"\n缺少权限：requested={permission.requested_permission_level}, granted={permission.granted_permission_level}"
                    f"\n原因：{permission.missing_permission_reason or '需要本地执行确认'}"
                    "\n请用以下任一授权格式："
                    "\n- 允许本地权限：查飞书是否运行"
                    "\n- 查: 飞书是否运行"
                    f"{context_suffix}"
                )

            ok, detail = _query_local_feishu_processes()
            return (
                f"本机只读查询{'成功' if ok else '失败'}。"
                f"\n{detail}"
                f"{context_suffix}"
            )

        return (
            "你提到的是本机环境查询。当前聊天通道不会直接执行通用本机命令。"
            "\n如果你要查飞书进程，请发送：查: 飞书是否运行"
            f"{context_suffix}"
        )

    return (
        "收到，我会按聊天模式处理，不会自动触发工作流执行。"
        "\n如果你要推进执行，请发送明确动作词（例如 dispatch）。"
        f"{context_suffix}"
    )


def _normalize_user_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    if not (text.startswith("{") and text.endswith("}")):
        return text
    try:
        payload = json.loads(text)
    except Exception:
        return text
    if not isinstance(payload, dict):
        return text
    if isinstance(payload.get("text"), str) and payload.get("text", "").strip():
        return payload["text"].strip()
    rich = payload.get("content")
    if not isinstance(rich, list):
        return text
    lines: list[str] = []
    for row in rich:
        if not isinstance(row, list):
            continue
        row_text = "".join(str(cell.get("text") or "") for cell in row if isinstance(cell, dict))
        if row_text.strip():
            lines.append(row_text.strip())
    return "\n".join(lines) if lines else text


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
    user_text = _normalize_user_text(str(message_payload.get("text") or ""))
    correlated = {
        "request_id": payload.get("correlated_request_id"),
        "brief_id": payload.get("correlated_brief_id"),
        "handoff_id": payload.get("correlated_handoff_id"),
    }
    request_obj = {
        "route_type": "chat",
        "response_profile": str(payload.get("response_profile") or "chat_conversation"),
        "artifact_visibility": str(payload.get("artifact_visibility") or "owner_visible"),
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
    permission = evaluate_permission_context(user_text)
    request_obj["permission_context"] = permission.to_dict()
    _write_json(request_artifact_path, request_obj)

    reply_text = _build_reply_text(user_text=user_text, correlated=correlated)
    response_source = "rule_fallback"
    llm_provider = ""
    llm_model = ""
    llm_error = ""
    try:
        llm_result = generate_chat_reply(
            user_text=user_text,
            correlated=correlated,
            permission_context=permission.to_dict(),
        )
        reply_text = str(llm_result.get("reply_text") or reply_text)
        response_source = str(llm_result.get("response_source") or "llm")
        llm_provider = str(llm_result.get("llm_provider") or "")
        llm_model = str(llm_result.get("llm_model") or "")
        llm_error = str(llm_result.get("llm_error") or "")
    except Exception as exc:
        llm_error = str(exc)

    result = {
        "route_type": "chat",
        "response_profile": str(payload.get("response_profile") or "chat_conversation"),
        "artifact_visibility": str(payload.get("artifact_visibility") or "owner_visible"),
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
        "permission_context": permission.to_dict(),
        "response_source": response_source,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_error": llm_error,
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
