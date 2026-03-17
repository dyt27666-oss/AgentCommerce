"""Execution trigger protocol (v0.1).

Only explicit owner/bridge protocol signals can request execution handoff checks.
"""

from __future__ import annotations

import re
from typing import Any


EXECUTION_TRIGGER_KEYWORDS = ("confirm_execution_dispatch", "dispatch_execution")


def extract_execution_trigger(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "").lower()
    source = str(payload.get("source") or "").lower()
    keyword = None
    for item in EXECUTION_TRIGGER_KEYWORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(item)}(?![a-z0-9_])", text):
            keyword = item
            break

    if keyword is None:
        return {
            "is_trigger": False,
            "keyword": None,
            "authorized": False,
            "requested_by_lane": "chat",
            "ignored_reason": "",
        }

    authorized = "action_protocol" in source or "owner_action" in source or "bridge" in source
    return {
        "is_trigger": True,
        "keyword": keyword,
        "authorized": authorized,
        "requested_by_lane": "owner" if authorized else "chat",
        "ignored_reason": "" if authorized else "execution trigger keyword detected in non-authorized source.",
    }

