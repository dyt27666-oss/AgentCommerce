"""Minimal Feishu sender utility for chat bridge replies (webhook-based)."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import request


def resolve_webhook_url(explicit_webhook_url: str | None = None) -> str:
    if explicit_webhook_url and explicit_webhook_url.strip():
        return explicit_webhook_url.strip()
    project_webhook = os.getenv("AGENTCOMMERCE_FEISHU_WEBHOOK_URL", "").strip()
    if project_webhook:
        return project_webhook
    return os.getenv("FEISHU_WEBHOOK_URL", "").strip()


def send_text(*, text: str, webhook_url: str | None = None, timeout_sec: int = 10) -> dict[str, Any]:
    url = resolve_webhook_url(webhook_url)
    if not url:
        raise ValueError("Missing Feishu webhook URL.")
    payload = {"msg_type": "text", "content": {"text": text}}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    try:
        return json.loads(body)
    except Exception:
        return {"raw_response": body}

