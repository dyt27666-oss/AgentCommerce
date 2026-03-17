"""Minimal Feishu webhook notifier for bridge artifacts (v0).

This tool provides notification only. It does not orchestrate approvals or execution.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request

NOTIFY_STATE_PATH = Path("artifacts") / "council_feishu_notify_state.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_json_ids_from_path(path_value: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None, None, None
    p = Path(path_value)
    if not p.exists():
        return None, None, None
    try:
        payload = _load_json(p)
    except Exception:
        return None, None, None
    return payload.get("request_id"), payload.get("brief_id"), payload.get("handoff_id")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_notify_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"entries": {}, "updated_at": _now_iso()}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"entries": {}, "updated_at": _now_iso()}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    return {"entries": entries, "updated_at": data.get("updated_at")}


def _write_notify_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now_iso()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _ids(data: dict[str, Any]) -> str:
    request_id = data.get("request_id")
    brief_id = data.get("brief_id")
    handoff_id = data.get("handoff_id")

    inherited = data.get("inherited_identity") if isinstance(data.get("inherited_identity"), dict) else {}
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = inherited.get("request_id", "n/a")
    if not isinstance(brief_id, str) or not brief_id.strip():
        brief_id = inherited.get("brief_id", "n/a")
    if not isinstance(handoff_id, str) or not handoff_id.strip():
        handoff_id = inherited.get("handoff_id", "n/a")

    if any(str(x) == "n/a" for x in [request_id, brief_id, handoff_id]):
        # Best-effort fallback for result artifacts that only carry linkage via source paths.
        for key in ["continuation_artifact", "source_artifact", "owner_action_artifact"]:
            r, b, h = _safe_json_ids_from_path(data.get(key))
            if str(request_id) == "n/a" and isinstance(r, str) and r.strip():
                request_id = r
            if str(brief_id) == "n/a" and isinstance(b, str) and b.strip():
                brief_id = b
            if str(handoff_id) == "n/a" and isinstance(h, str) and h.strip():
                handoff_id = h
            if all(str(x) != "n/a" for x in [request_id, brief_id, handoff_id]):
                break
    return f"request_id={request_id} | brief_id={brief_id} | handoff_id={handoff_id}"


def build_dedupe_key(artifact_path: str, level: str, mode: str, data: dict[str, Any]) -> str:
    request_id = data.get("request_id")
    brief_id = data.get("brief_id")
    handoff_id = data.get("handoff_id")
    inherited = data.get("inherited_identity") if isinstance(data.get("inherited_identity"), dict) else {}
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = inherited.get("request_id", "")
    if not isinstance(brief_id, str) or not brief_id.strip():
        brief_id = inherited.get("brief_id", "")
    if not isinstance(handoff_id, str) or not handoff_id.strip():
        handoff_id = inherited.get("handoff_id", "")
    return "|".join(
        [
            Path(artifact_path).as_posix(),
            level,
            mode,
            str(request_id or ""),
            str(brief_id or ""),
            str(handoff_id or ""),
        ]
    )


def should_suppress_send(state: dict[str, Any], dedupe_key: str, dedupe_window_sec: int, now_ts: float | None = None) -> bool:
    if dedupe_window_sec <= 0:
        return False
    entries = state.get("entries")
    if not isinstance(entries, dict):
        return False
    entry = entries.get(dedupe_key)
    if not isinstance(entry, dict):
        return False
    last_sent_ts = entry.get("last_sent_ts")
    if not isinstance(last_sent_ts, (int, float)):
        return False
    current_ts = now_ts if now_ts is not None else time.time()
    return (current_ts - float(last_sent_ts)) < dedupe_window_sec


def mark_notify_state(
    state: dict[str, Any],
    dedupe_key: str,
    *,
    artifact_path: str,
    level: str,
    mode: str,
    status: str,
    now_ts: float | None = None,
) -> None:
    entries = state.setdefault("entries", {})
    if not isinstance(entries, dict):
        state["entries"] = {}
        entries = state["entries"]
    current_ts = now_ts if now_ts is not None else time.time()
    entries[dedupe_key] = {
        "artifact_path": Path(artifact_path).as_posix(),
        "level": level,
        "mode": mode,
        "last_status": status,
        "last_sent_ts": current_ts,
        "last_sent_at": datetime.fromtimestamp(current_ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def _short_text(value: Any, limit: int = 180) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _gate_summary(gates: Any) -> str:
    if not isinstance(gates, list) or not gates:
        return "n/a"
    passed = 0
    total = 0
    for gate in gates:
        if isinstance(gate, dict):
            total += 1
            if gate.get("passed") is True:
                passed += 1
    if total == 0:
        return "n/a"
    return f"{passed}/{total} passed"


def _review_state_explanation(completion_state: Any) -> str:
    state = str(completion_state or "")
    mapping = {
        "execution_receipt_available": "Execution receipt is available; owner can move to final decision.",
        "running_no_execution_receipt": "Dispatch is running; wait before final decision.",
        "process_exited_no_execution_receipt": "Dispatch process ended without execution receipt; inspect and decide retry/fix.",
        "not_dispatched": "Dispatch did not run successfully; owner should fix upstream state.",
    }
    return mapping.get(state, "Completion state observed; verify readiness before final decision.")


def _zh_completion_state(state: Any) -> str:
    mapping = {
        "execution_receipt_available": "已拿到执行回执",
        "running_no_execution_receipt": "执行仍在进行，暂未产出回执",
        "process_exited_no_execution_receipt": "进程已结束但未发现执行回执",
        "not_dispatched": "本轮未成功发起执行",
    }
    return mapping.get(str(state), str(state or "未知"))


def _zh_continue_status(status: Any) -> str:
    mapping = {
        "executed_continue_success": "续跑执行成功",
        "executed_continue_failed": "续跑执行失败",
        "paused_no_execution": "已暂停（未执行）",
        "stopped_no_execution": "已停止（未执行）",
        "loop_back_no_execution": "已回退（未执行）",
    }
    return mapping.get(str(status), str(status or "未知"))


def _zh_scope(scope: dict[str, Any]) -> str:
    in_scope = scope.get("in_allowed_scope", "n/a")
    compliant = scope.get("constraints_compliant", "n/a")
    return f"范围合规={in_scope}，约束合规={compliant}"


def _review_action_hint(artifact_path: str, data: dict[str, Any]) -> str:
    path_name = Path(artifact_path).name
    if "final_owner_decision" in data or path_name == "council_owner_final_review_summary.json":
        return "可回复动作：当前为结果通知阶段，通常无需继续回复动作。"
    if data.get("execution_receipt_status") == "skeleton_only":
        return "可回复动作：approved / revision_request / needs_fix / rejected"
    if data.get("completion_observation_status") == "execution_receipt_available":
        return "可回复动作：approved / revision_request / needs_fix / rejected"
    if isinstance(data.get("owner_review_ready"), bool) and data.get("owner_review_ready"):
        return "可回复动作：approved / revision_request / needs_fix / rejected"
    return "可回复动作：dispatch / hold / needs_fix / reject"


def summarize_artifact_review(artifact_path: str, data: dict[str, Any]) -> str:
    p = Path(artifact_path)
    name = p.name
    lines: list[str] = [f"[桥接评审] {name}", _ids(data)]

    if "completion_observation_status" in data:
        completion_state = data.get("completion_observation_status")
        lines.append("阶段：执行后状态观察")
        lines.append("本步做了什么：检查调度后进程状态，并判断是否可进入回执/评审。")
        lines.append(f"当前结果：{_zh_completion_state(completion_state)}（dispatch={data.get('dispatch_status', 'n/a')}）")
        proc = data.get("dispatch_process") if isinstance(data.get("dispatch_process"), dict) else {}
        lines.append(f"进程状态：running={proc.get('running', 'n/a')}")
        lines.append(f"状态解释：{_review_state_explanation(completion_state)}")
        lines.append("产出说明：该工件用于告诉你“现在能否进入最终拍板阶段”。")
        lines.append(f"下一步建议：{data.get('next_action', '先确认执行状态，再决定是否进入最终评审。')}")
        if data.get("blocking_reason"):
            lines.append(f"风险提示：{_short_text(data.get('blocking_reason'), limit=120)}")
        elif data.get("dispatch_log_tail"):
            lines.append("风险提示：日志中有运行线索；若你无法拍板，建议回桌面复核。")

    elif data.get("execution_receipt_status") == "skeleton_only":
        lines.append("阶段：执行回执预填")
        lines.append("本步做了什么：自动预填了回执骨架，减少手工录入。")
        lines.append(
            f"当前结果：身份关联={data.get('identity_linkage_status', 'n/a')}，dispatch={data.get('dispatch_status', 'n/a')}，completion={_zh_completion_state(data.get('completion_state'))}"
        )
        fill_fields = data.get("suggested_owner_fill_fields", [])
        if isinstance(fill_fields, list):
            top_fields = [str(x) for x in fill_fields[:4]]
            focus = ", ".join(top_fields) if top_fields else "execution_status, summary, next_step_suggestion"
            lines.append(f"你需要补充：{focus}")
        lines.append("产出说明：该工件不是最终回执，仅用于预填。")
        lines.append("下一步建议：补全必填字段后，执行 final_review_once 做最终收口。")
        if data.get("notes"):
            lines.append(f"风险提示：{_short_text(data.get('notes'), limit=140)}")

    elif "final_owner_decision" in data:
        lines.append("阶段：最终拍板结果")
        lines.append("本步做了什么：已记录 owner 最终决策与收口动作。")
        lines.append(f"当前结果：决策={data.get('final_owner_decision')}，执行状态={data.get('execution_status', 'n/a')}")
        scope = data.get("scope_compliance_check") if isinstance(data.get("scope_compliance_check"), dict) else {}
        lines.append(f"合规摘要：{_zh_scope(scope)}")
        lines.append(f"决策原因：{_short_text(data.get('key_reason', 'n/a'), limit=140)}")
        lines.append("产出说明：该工件可作为本轮最终审计记录。")
        lines.append(f"下一步建议：{data.get('next_action', '根据决策关闭本轮或开启修正轮次。')}")

    elif "final_status" in data and "flow_state" in data:
        lines.append("阶段：飞书确认后本地续跑")
        lines.append("本步做了什么：已串行执行 continue_once 链路（含可选 completion/skeleton）。")
        lines.append(
            f"当前结果：flow={data.get('flow_state')}，状态={_zh_continue_status(data.get('final_status'))}，completion={_zh_completion_state(data.get('completion_state'))}"
        )
        lines.append(f"执行步骤：{data.get('executed_step', 'n/a')}")
        lines.append(f"评审就绪：owner_review_ready={data.get('owner_review_ready', 'n/a')}")
        lines.append("产出说明：本工件用于告诉你本轮自动续跑到了哪一步、下一步该拍板还是回退。")
        lines.append(
            f"下一步建议：{data.get('post_receipt_next_manual_action') or data.get('next_manual_action', '按当前状态继续人工下一步。')}"
        )
        if data.get("receipt_skeleton_status"):
            lines.append(f"回执骨架状态：{data.get('receipt_skeleton_status')}")

    else:
        lines.append("阶段：通用评审")
        lines.append("本步做了什么：暂无该工件的专用摘要模板。")
        lines.append("下一步建议：请回桌面查看该工件详情。")

    if data.get("warnings"):
        lines.append(f"风险提示：{_short_text(data.get('warnings'), limit=140)}")
    if data.get("blocking_reason") and "risk=" not in "\n".join(lines):
        lines.append(f"风险提示：{_short_text(data.get('blocking_reason'), limit=140)}")
    lines.append(_review_action_hint(artifact_path, data))
    lines.append(f"辅助路径：{Path(artifact_path).as_posix()}")
    return "\n".join(lines)


def summarize_artifact(artifact_path: str, data: dict[str, Any], level: str = "brief") -> str:
    if level == "review":
        return summarize_artifact_review(artifact_path, data)

    p = Path(artifact_path)
    name = p.name
    lines: list[str] = [f"[Bridge Notice] {name}", _ids(data)]
    detail = level == "detail"

    if "approval_status" in data and "validation_snapshot" in data:
        # handoff
        status = data.get("approval_status")
        lines.append(f"handoff_status={status}")
        next_action = (
            "Run dispatch-prep and local dispatch."
            if status == "approved"
            else "Fix handoff fields before dispatch."
        )
        lines.append(f"next_action={next_action}")
    elif "dispatch_ready" in data:
        # dispatch-ready artifact
        ready = bool(data.get("dispatch_ready"))
        lines.append(f"dispatch_ready={ready}")
        if ready:
            lines.append("next_action=Run codex_dispatch_runner.")
        else:
            reason = data.get("blocking_reason") or "gate failed"
            lines.append(f"blocking_reason={reason}")
            lines.append("next_action=Fix dispatch gates and regenerate artifact.")
        if detail:
            lines.append(f"state_explanation={'Dispatch gates passed.' if ready else 'Dispatch gates blocked.'}")
            lines.append(f"gate_results={_gate_summary(data.get('gate_results'))}")
            if data.get("dispatch_notes"):
                lines.append(f"dispatch_notes={_short_text(data.get('dispatch_notes'))}")
            if data.get("prompt_artifact_path"):
                lines.append(f"prompt_artifact_path={data.get('prompt_artifact_path')}")
    elif "completion_observation_status" in data:
        # completion observation
        state = data.get("completion_observation_status")
        lines.append(f"completion_state={state}")
        if data.get("blocking_reason"):
            lines.append(f"blocking_reason={data.get('blocking_reason')}")
        lines.append(f"next_action={data.get('next_action', 'Follow completion guidance.')}")
        if detail:
            lines.append("state_explanation=Completion observed; decide whether receipt preparation can proceed.")
            log_tail = data.get("dispatch_log_tail")
            if isinstance(log_tail, dict):
                stdout_tail = _short_text(log_tail.get("stdout", ""))
                stderr_tail = _short_text(log_tail.get("stderr", ""))
                if stdout_tail:
                    lines.append(f"log_tail_stdout={stdout_tail}")
                if stderr_tail:
                    lines.append(f"log_tail_stderr={stderr_tail}")
            if data.get("dispatch_process"):
                proc = data.get("dispatch_process")
                if isinstance(proc, dict):
                    lines.append(f"process_running={proc.get('running', 'n/a')}")
            lines.append(
                f"execution_receipt_presence={'yes' if state == 'execution_receipt_available' else 'no_or_pending'}"
            )
    elif "dispatch_status" in data and "dispatch_attempted" in data:
        # dispatch receipt
        lines.append(f"dispatch_status={data.get('dispatch_status')}")
        if data.get("error"):
            lines.append(f"error={data.get('error')}")
        lines.append("next_action=Run dispatch completion capture.")
        if detail:
            lines.append("state_explanation=Dispatch attempted; confirm process state and logs.")
            proc = data.get("dispatch_process")
            if isinstance(proc, dict):
                lines.append(f"process_state={proc.get('state', 'n/a')}")
                lines.append(f"process_mode={proc.get('mode', 'n/a')}")
                lines.append(f"process_pid={proc.get('pid', 'n/a')}")
            logs = data.get("dispatch_log_paths")
            if isinstance(logs, dict):
                if logs.get("stdout"):
                    lines.append(f"log_stdout_path={logs.get('stdout')}")
                if logs.get("stderr"):
                    lines.append(f"log_stderr_path={logs.get('stderr')}")
    elif "final_owner_decision" in data:
        # owner final review summary
        lines.append(f"final_owner_decision={data.get('final_owner_decision')}")
        lines.append(f"execution_status={data.get('execution_status')}")
        lines.append(f"next_action={data.get('next_action', 'Owner review completed.')}")
    else:
        lines.append("state=unknown_artifact")
        lines.append("next_action=Check artifact format.")

    if data.get("warnings"):
        lines.append(f"warnings={data.get('warnings')}")
    if data.get("blocking_reason") and "blocking_reason=" not in "\n".join(lines):
        lines.append(f"blocking_reason={data.get('blocking_reason')}")

    lines.append(f"artifact_path={Path(artifact_path).as_posix()}")
    return "\n".join(lines)


def apply_notify_mode(text: str, mode: str = "normal") -> str:
    if mode == "test":
        return f"[TEST] {text}"
    return text


def build_feishu_payload(text: str, keyword_marker: str = "bridge", mode: str = "normal") -> dict[str, Any]:
    marker = (keyword_marker or "").strip()
    base_text = f"[{marker}] {text}" if marker else text
    final_text = apply_notify_mode(base_text, mode=mode)
    return {"msg_type": "text", "content": {"text": final_text}}


def resolve_webhook_url(explicit_webhook_url: str | None = None) -> str:
    if explicit_webhook_url and explicit_webhook_url.strip():
        return explicit_webhook_url.strip()
    project_webhook = os.getenv("AGENTCOMMERCE_FEISHU_WEBHOOK_URL", "").strip()
    if project_webhook:
        return project_webhook
    return os.getenv("FEISHU_WEBHOOK_URL", "").strip()


def resolve_keyword_marker(explicit_keyword_marker: str | None = None) -> str:
    if explicit_keyword_marker and explicit_keyword_marker.strip():
        return explicit_keyword_marker.strip()
    project_marker = os.getenv("AGENTCOMMERCE_FEISHU_KEYWORD_MARKER", "").strip()
    if project_marker:
        return project_marker
    fallback_marker = os.getenv("FEISHU_KEYWORD_MARKER", "").strip()
    if fallback_marker:
        return fallback_marker
    return "bridge"


def send_feishu_webhook(webhook_url: str, payload: dict[str, Any], timeout_sec: int = 10) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    try:
        return json.loads(body)
    except Exception:
        return {"raw_response": body}


def is_feishu_send_success(response: dict[str, Any]) -> bool:
    # Feishu webhook success shape is usually {"code": 0, "msg": "success", ...}.
    # If no "code" field exists, keep backward-compatible behavior and treat it as unknown-success.
    if "code" not in response:
        return True
    return response.get("code") == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Send bridge artifact summary to Feishu webhook.")
    parser.add_argument("--artifact", required=True, help="Path to bridge artifact JSON.")
    parser.add_argument(
        "--webhook-url",
        default="",
        help="Feishu webhook URL (or env: AGENTCOMMERCE_FEISHU_WEBHOOK_URL / FEISHU_WEBHOOK_URL).",
    )
    parser.add_argument(
        "--keyword-marker",
        default="",
        help="Feishu keyword marker (or env: AGENTCOMMERCE_FEISHU_KEYWORD_MARKER / FEISHU_KEYWORD_MARKER).",
    )
    parser.add_argument(
        "--level",
        default="brief",
        choices=["brief", "detail", "review"],
        help="Summary level: brief (default), detail, or review (mobile decision focused).",
    )
    parser.add_argument(
        "--mode",
        default="normal",
        choices=["normal", "test"],
        help="Notify mode. Use test mode to mark message as test explicitly.",
    )
    parser.add_argument(
        "--dedupe-window-sec",
        type=int,
        default=0,
        help="Suppress repeated sends for same key within N seconds (0 disables dedupe).",
    )
    parser.add_argument(
        "--notify-state-path",
        default=str(NOTIFY_STATE_PATH),
        help="Path to local notify state JSON used for dedupe audit.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload only, do not send.")
    parser.add_argument("--timeout-sec", type=int, default=10, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    data = _load_json(artifact_path)
    summary = summarize_artifact(str(artifact_path), data, level=args.level)
    keyword_marker = resolve_keyword_marker(args.keyword_marker)
    payload = build_feishu_payload(summary, keyword_marker=keyword_marker, mode=args.mode)
    dedupe_key = build_dedupe_key(str(artifact_path), args.level, args.mode, data)
    state_path = Path(args.notify_state_path)
    notify_state = _load_notify_state(state_path)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\n[feishu-notifier] dry-run only, not sent.")
        return

    if should_suppress_send(notify_state, dedupe_key, args.dedupe_window_sec):
        mark_notify_state(
            notify_state,
            dedupe_key,
            artifact_path=str(artifact_path),
            level=args.level,
            mode=args.mode,
            status="suppressed",
        )
        _write_notify_state(state_path, notify_state)
        print(
            json.dumps(
                {
                    "suppressed": True,
                    "reason": f"dedupe_window_sec={args.dedupe_window_sec}",
                    "dedupe_key": dedupe_key,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"\n[feishu-notifier] suppressed: {artifact_path.as_posix()}")
        return

    webhook = resolve_webhook_url(args.webhook_url)
    if not webhook:
        raise SystemExit(
            "Missing webhook URL. Use --webhook-url or AGENTCOMMERCE_FEISHU_WEBHOOK_URL or FEISHU_WEBHOOK_URL."
        )

    response = send_feishu_webhook(webhook, payload, timeout_sec=args.timeout_sec)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    mark_notify_state(
        notify_state,
        dedupe_key,
        artifact_path=str(artifact_path),
        level=args.level,
        mode=args.mode,
        status="sent",
    )
    _write_notify_state(state_path, notify_state)
    if not is_feishu_send_success(response):
        code = response.get("code", "n/a")
        msg = response.get("msg", "unknown error")
        raise SystemExit(f"Feishu webhook send failed: code={code}, msg={msg}")
    print(f"\n[feishu-notifier] sent: {artifact_path.as_posix()}")


if __name__ == "__main__":
    main()
