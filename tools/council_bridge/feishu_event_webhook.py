"""Feishu event webhook entrypoint (primary real-time path).

Design:
- receive Feishu event callback
- handle challenge verification
- optional signature verification
- normalize message payload
- persist parsed webhook event artifact
- async route via unified router
"""

from __future__ import annotations

import argparse
import hmac
import json
import threading
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tools.council_bridge.feishu_message_router import route_message


WEBHOOK_EVENT_PATH = Path("artifacts") / "council_feishu_webhook_event.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_message_text(content: str) -> str:
    if not isinstance(content, str) or not content.strip():
        return ""
    try:
        payload = json.loads(content)
        if isinstance(payload, dict) and isinstance(payload.get("text"), str):
            return payload["text"]
    except Exception:
        pass
    return content


def parse_feishu_event_to_message(event: dict[str, Any]) -> dict[str, Any]:
    header = event.get("header") if isinstance(event.get("header"), dict) else {}
    body = event.get("event") if isinstance(event.get("event"), dict) else {}
    message = body.get("message") if isinstance(body.get("message"), dict) else {}
    sender = body.get("sender") if isinstance(body.get("sender"), dict) else {}
    sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}

    content = message.get("content", "")
    text = _parse_message_text(content)
    sender_value = ""
    for key in ["open_id", "user_id", "union_id"]:
        value = sender_id.get(key)
        if isinstance(value, str) and value.strip():
            sender_value = value.strip()
            break

    return {
        "source": "webhook",
        "event_id": str(header.get("event_id") or ""),
        "message_id": str(message.get("message_id") or ""),
        "chat_id": str(message.get("chat_id") or ""),
        "sender_id": sender_value or "feishu_webhook",
        "sender_name": str(sender.get("sender_type") or ""),
        "text": str(text or ""),
        "create_time": str(message.get("create_time") or header.get("create_time") or ""),
        "raw_event_path": "",
    }


def verify_signature_if_needed(
    *,
    raw_body: bytes,
    headers: dict[str, str],
    signing_secret: str,
) -> tuple[bool, str]:
    if not signing_secret:
        return True, "signature_check_skipped"

    timestamp = headers.get("X-Lark-Request-Timestamp", "")
    nonce = headers.get("X-Lark-Request-Nonce", "")
    signature = headers.get("X-Lark-Signature", "")
    if not timestamp or not nonce or not signature:
        return False, "signature headers missing"

    body_text = raw_body.decode("utf-8", errors="ignore")
    base = f"{timestamp}{nonce}{body_text}".encode("utf-8")
    expected = hmac.new(signing_secret.encode("utf-8"), base, digestmod=sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "signature mismatch"
    return True, "signature_verified"


class _WebhookHandler(BaseHTTPRequestHandler):
    config: dict[str, Any] = {}

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover
        return

    def _write_json_response(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(max(0, length))
            payload = json.loads(raw_body.decode("utf-8", errors="ignore"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be JSON object")

            challenge = payload.get("challenge")
            if isinstance(challenge, str) and challenge:
                self._write_json_response(200, {"challenge": challenge})
                return

            token_required = str(self.config.get("verification_token") or "")
            if token_required:
                token_actual = str(payload.get("token") or "")
                if token_actual != token_required:
                    self._write_json_response(403, {"code": 403, "msg": "verification token mismatch"})
                    return

            ok, sign_info = verify_signature_if_needed(
                raw_body=raw_body,
                headers={k: v for k, v in self.headers.items()},
                signing_secret=str(self.config.get("signing_secret") or ""),
            )
            if not ok:
                self._write_json_response(403, {"code": 403, "msg": sign_info})
                return

            header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
            event_type = str(header.get("event_type") or "")
            event_body = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            if event_type != "im.message.receive_v1" or not event_body:
                event_record = {
                    "received_at": self.config["now_fn"](),
                    "event_type": event_type or "unknown",
                    "parse_status": "ignored_non_message_event",
                    "signature_status": sign_info,
                }
                _write_json(Path(self.config["webhook_event_path"]), event_record)
                self._write_json_response(200, {"code": 0, "msg": "ignored"})
                return

            message_payload = parse_feishu_event_to_message(payload)
            event_record = {
                "received_at": self.config["now_fn"](),
                "event_type": event_type,
                "parse_status": "parsed",
                "signature_status": sign_info,
                "message": message_payload,
            }
            _write_json(Path(self.config["webhook_event_path"]), event_record)

            def _route_async() -> None:
                route_message(
                    message_payload,
                    source_artifact=str(self.config["source_artifact"]),
                    stage=str(self.config["action_stage"]),
                    check_completion_once=bool(self.config["check_completion_once"]),
                    build_receipt_skeleton=bool(self.config["build_receipt_skeleton"]),
                    dedupe_state_path=Path(self.config["dedupe_state_path"]),
                    route_result_path=Path(self.config["route_result_path"]),
                    queue_db_path=Path(self.config["queue_db_path"]),
                )

            threading.Thread(target=_route_async, daemon=True).start()
            self._write_json_response(200, {"code": 0, "msg": "ok"})
        except Exception as exc:
            self._write_json_response(500, {"code": 500, "msg": str(exc)})


def run_server(
    *,
    host: str,
    port: int,
    source_artifact: str,
    action_stage: str,
    check_completion_once: bool,
    build_receipt_skeleton: bool,
    verification_token: str,
    signing_secret: str,
    webhook_event_path: str,
    dedupe_state_path: str,
    route_result_path: str,
    queue_db_path: str,
) -> None:
    _WebhookHandler.config = {
        "source_artifact": source_artifact,
        "action_stage": action_stage,
        "check_completion_once": check_completion_once,
        "build_receipt_skeleton": build_receipt_skeleton,
        "verification_token": verification_token,
        "signing_secret": signing_secret,
        "webhook_event_path": webhook_event_path,
        "dedupe_state_path": dedupe_state_path,
        "route_result_path": route_result_path,
        "queue_db_path": queue_db_path,
        "now_fn": lambda: datetime_now_iso(),
    }
    server = ThreadingHTTPServer((host, port), _WebhookHandler)
    print(
        "[feishu-event-webhook] "
        f"listening on http://{host}:{port} "
        f"| stage={action_stage} | source_artifact={source_artifact}"
    )
    server.serve_forever()


def datetime_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu event webhook entrypoint (real-time).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--source-artifact", default="artifacts/council_codex_dispatch_ready.json")
    parser.add_argument(
        "--action-stage",
        default="auto",
        choices=["auto", "dispatch_ready", "review_ready", "final_summary"],
    )
    parser.add_argument("--check-completion-once", action="store_true")
    parser.add_argument("--build-receipt-skeleton", action="store_true")
    parser.add_argument("--verification-token", default="")
    parser.add_argument("--signing-secret", default="")
    parser.add_argument("--webhook-event-path", default=str(WEBHOOK_EVENT_PATH))
    parser.add_argument("--dedupe-state-path", default="artifacts/council_feishu_message_dedupe_state.json")
    parser.add_argument("--route-result-path", default="artifacts/council_feishu_message_route_result.json")
    parser.add_argument("--queue-db-path", default="artifacts/council_bridge_tasks.db")
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        source_artifact=args.source_artifact,
        action_stage=args.action_stage,
        check_completion_once=args.check_completion_once,
        build_receipt_skeleton=args.build_receipt_skeleton,
        verification_token=args.verification_token,
        signing_secret=args.signing_secret,
        webhook_event_path=args.webhook_event_path,
        dedupe_state_path=args.dedupe_state_path,
        route_result_path=args.route_result_path,
        queue_db_path=args.queue_db_path,
    )


if __name__ == "__main__":
    main()
