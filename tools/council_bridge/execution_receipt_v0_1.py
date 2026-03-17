"""Execution receipt schema helper v0.1 (for controlled handoff phase)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EXECUTION_RECEIPT_PATH = Path("artifacts") / "council_execution_receipt_v0_1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_execution_receipt_v0_1(
    *,
    execution_id: str,
    source_handoff_id: str,
    before_execution_state: str,
    execution_status: str,
    executed_actions_summary: list[str],
    changed_files: list[str],
    touched_resources: list[str],
    risk_flags: list[str],
    receipt_status: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "receipt_version": "execution.receipt.v0.1",
        "execution_id": execution_id,
        "source_handoff_id": source_handoff_id,
        "before_execution_state": before_execution_state,
        "execution_status": execution_status,
        "executed_actions_summary": executed_actions_summary,
        "changed_files": changed_files,
        "touched_resources": touched_resources,
        "risk_flags": risk_flags,
        "receipt_status": receipt_status,
        "next_action": next_action,
        "timestamp": _now_iso(),
    }


def write_execution_receipt_v0_1(receipt: dict[str, Any], output_path: Path = DEFAULT_EXECUTION_RECEIPT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

