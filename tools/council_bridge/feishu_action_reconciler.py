"""Feishu action reconciler (polling fallback, not primary path).

This module keeps polling as compensation/recovery scanner:
- scans recent group messages
- normalizes to unified payload
- routes via unified message router
- writes reconciliation artifacts
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request

from tools.council_bridge.feishu_message_router import route_message


STATE_PATH = Path("artifacts") / "council_feishu_reconciler_state.json"
RESULT_PATH = Path("artifacts") / "council_feishu_reconciler_result.json"
LOG_PATH = Path("artifacts") / "council_feishu_listener_log.json"
EVENT_PATH = Path("artifacts") / "council_feishu_listener_event.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _safe_load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return _load_json(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_json_list(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            current = json.load(f)
        if not isinstance(current, list):
            current = []
    else:
        current = []
    current.append(event)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_message_text(item: dict[str, Any]) -> str:
    body = item.get("body")
    if not isinstance(body, dict):
        return ""
    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        return ""
    try:
        decoded = json.loads(content)
        if isinstance(decoded, dict):
            if isinstance(decoded.get("text"), str):
                return decoded["text"]
            rich_content = decoded.get("content")
            if isinstance(rich_content, list):
                texts: list[str] = []
                for row in rich_content:
                    if not isinstance(row, list):
                        continue
                    for cell in row:
                        if isinstance(cell, dict) and isinstance(cell.get("text"), str):
                            text = cell.get("text", "").strip()
                            if text:
                                texts.append(text)
                if texts:
                    return "".join(texts)
    except Exception:
        pass
    return content


def _extract_sender(item: dict[str, Any]) -> str:
    sender = item.get("sender")
    if isinstance(sender, dict):
        sender_id = sender.get("sender_id")
        if isinstance(sender_id, dict):
            for key in ["open_id", "user_id", "union_id"]:
                value = sender_id.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return "feishu_reconciler"


def _to_message_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "polling",
        "event_id": "",
        "message_id": str(item.get("message_id") or ""),
        "chat_id": str(item.get("chat_id") or ""),
        "sender_id": _extract_sender(item),
        "sender_name": "",
        "text": _parse_message_text(item),
        "create_time": str(item.get("create_time") or ""),
        "raw_event_path": "",
    }


def _is_bridge_system_echo(payload: dict[str, Any]) -> bool:
    text = str(payload.get("text") or "").strip()
    if not text:
        return False
    # Ignore bridge-generated summaries/receipts to avoid self-triggering
    # action keywords such as "needs_fix"/"dispatch" embedded in reply text.
    return text.startswith("【Bridge")


def _get_tenant_access_token(app_id: str, app_secret: str, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": app_id, "app_secret": app_secret}
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    parsed = json.loads(body)
    if parsed.get("code") != 0:
        raise ValueError(f"Feishu token fetch failed: code={parsed.get('code')} msg={parsed.get('msg')}")
    token = parsed.get("tenant_access_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Feishu token fetch failed: missing tenant_access_token.")
    return token


def fetch_group_messages(
    *,
    app_id: str,
    app_secret: str,
    chat_id: str,
    base_url: str = "https://open.feishu.cn",
    page_size: int = 20,
) -> list[dict[str, Any]]:
    token = _get_tenant_access_token(app_id, app_secret, base_url)
    qs = parse.urlencode(
        {
            "container_id_type": "chat",
            "container_id": chat_id,
            "sort_type": "ByCreateTimeDesc",
            "page_size": page_size,
        }
    )
    url = f"{base_url.rstrip('/')}/open-apis/im/v1/messages?{qs}"
    req = request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    parsed = json.loads(body)
    if parsed.get("code") != 0:
        raise ValueError(f"Feishu messages fetch failed: code={parsed.get('code')} msg={parsed.get('msg')}")
    data = parsed.get("data", {})
    if not isinstance(data, dict):
        return []
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def reconcile_once(
    *,
    messages: list[dict[str, Any]],
    last_processed_message_id: str,
    source_artifact: str,
    action_stage: str,
    check_completion_once: bool,
    build_receipt_skeleton: bool,
    dedupe_state_path: str,
    route_result_path: str,
    queue_db_path: str = "artifacts/council_bridge_tasks.db",
    runner=None,
) -> tuple[str, list[dict[str, Any]]]:
    if not messages:
        return last_processed_message_id, []

    newest_id = str(messages[0].get("message_id") or last_processed_message_id)
    to_process: list[dict[str, Any]] = []
    for item in messages:
        mid = str(item.get("message_id") or "")
        if not mid:
            continue
        if last_processed_message_id and mid == last_processed_message_id:
            break
        to_process.append(item)

    results: list[dict[str, Any]] = []
    for item in reversed(to_process):
        payload = _to_message_payload(item)
        if _is_bridge_system_echo(payload):
            continue
        kwargs = {
            "source_artifact": source_artifact,
            "stage": action_stage,
            "check_completion_once": check_completion_once,
            "build_receipt_skeleton": build_receipt_skeleton,
            "dedupe_state_path": Path(dedupe_state_path),
            "route_result_path": Path(route_result_path),
            "queue_db_path": Path(queue_db_path),
        }
        if runner is not None:
            kwargs["runner"] = runner
        route_result = route_message(
            payload,
            **kwargs,
        )
        results.append(route_result)
    return newest_id, results


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu action reconciler (polling fallback scanner).")
    parser.add_argument("--app-id", default=os.getenv("AGENTCOMMERCE_FEISHU_APP_ID", ""))
    parser.add_argument("--app-secret", default=os.getenv("AGENTCOMMERCE_FEISHU_APP_SECRET", ""))
    parser.add_argument("--chat-id", default=os.getenv("AGENTCOMMERCE_FEISHU_CHAT_ID", ""))
    parser.add_argument("--base-url", default="https://open.feishu.cn")
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--max-polls", type=int, default=1, help="Fallback scanner: one-shot by default.")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--source-artifact", default="artifacts/council_codex_dispatch_ready.json")
    parser.add_argument(
        "--action-stage",
        default="auto",
        choices=["auto", "dispatch_ready", "review_ready", "final_summary"],
    )
    parser.add_argument("--check-completion-once", action="store_true")
    parser.add_argument("--build-receipt-skeleton", action="store_true")
    parser.add_argument("--state-path", default=str(STATE_PATH))
    parser.add_argument("--result-path", default=str(RESULT_PATH))
    parser.add_argument("--event-path", default=str(EVENT_PATH))
    parser.add_argument("--log-path", default=str(LOG_PATH))
    parser.add_argument("--dedupe-state-path", default="artifacts/council_feishu_message_dedupe_state.json")
    parser.add_argument("--route-result-path", default="artifacts/council_feishu_message_route_result.json")
    parser.add_argument("--queue-db-path", default="artifacts/council_bridge_tasks.db")
    args = parser.parse_args()

    if not args.app_id or not args.app_secret or not args.chat_id:
        raise SystemExit(
            "Missing Feishu credentials. Provide --app-id --app-secret --chat-id "
            "or set AGENTCOMMERCE_FEISHU_APP_ID / AGENTCOMMERCE_FEISHU_APP_SECRET / AGENTCOMMERCE_FEISHU_CHAT_ID."
        )

    state_path = Path(args.state_path)
    result_path = Path(args.result_path)
    event_path = Path(args.event_path)
    log_path = Path(args.log_path)
    state = _safe_load(state_path, {"last_processed_message_id": ""})
    last_processed = str(state.get("last_processed_message_id") or "")

    poll_count = 0
    final_results: list[dict[str, Any]] = []
    while True:
        poll_count += 1
        items = fetch_group_messages(
            app_id=args.app_id,
            app_secret=args.app_secret,
            chat_id=args.chat_id,
            base_url=args.base_url,
            page_size=args.page_size,
        )
        new_last, results = reconcile_once(
            messages=items,
            last_processed_message_id=last_processed,
            source_artifact=args.source_artifact,
            action_stage=args.action_stage,
            check_completion_once=args.check_completion_once,
            build_receipt_skeleton=args.build_receipt_skeleton,
            dedupe_state_path=args.dedupe_state_path,
            route_result_path=args.route_result_path,
            queue_db_path=args.queue_db_path,
        )
        last_processed = new_last
        final_results.extend(results)
        _write_json(state_path, {"last_processed_message_id": last_processed, "updated_at": _now_iso()})

        for result in results:
            _write_json(event_path, result)
            _append_json_list(log_path, result)
            print(json.dumps(result, ensure_ascii=False))

        if args.max_polls > 0 and poll_count >= args.max_polls:
            break
        time.sleep(max(0.2, float(args.interval_sec)))

    reconciler_result = {
        "event_time": _now_iso(),
        "poll_count": poll_count,
        "result_count": len(final_results),
        "source_artifact": args.source_artifact,
        "action_stage": args.action_stage,
        "last_processed_message_id": last_processed,
        "results": final_results,
    }
    _write_json(result_path, reconciler_result)
    print(f"\n[feishu-action-reconciler] saved: {result_path.as_posix()}")


if __name__ == "__main__":
    main()
