"""Thin adapter to dispatch execution via existing codex dispatch runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.codex_dispatch_runner import run_dispatch


DEFAULT_DISPATCH_READY_PATH = Path("artifacts") / "council_execution_dispatch_ready.json"
DEFAULT_PROMPT_PATH = Path("artifacts") / "council_execution_brief_prompt.txt"
DEFAULT_DISPATCH_RECEIPT_PATH = Path("artifacts") / "council_execution_dispatch_receipt.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_prompt(brief: dict[str, Any]) -> str:
    def _lines(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items)

    objective = str(brief.get("objective") or "").strip()
    scope = [str(x) for x in (brief.get("execution_scope") or [])]
    constraints = [str(x) for x in (brief.get("execution_constraints") or [])]
    no_go = [str(x) for x in (brief.get("no_go_zones") or [])]
    outputs = [str(x) for x in (brief.get("expected_outputs") or [])]
    receipts = [str(x) for x in (brief.get("required_receipts") or [])]
    risk = [str(x) for x in (brief.get("risk_notes") or [])]

    return (
        "You are executing an owner-confirmed execution dispatch.\n\n"
        f"Objective:\n- {objective}\n\n"
        "Execution Scope:\n"
        f"{_lines(scope)}\n\n"
        "Execution Constraints:\n"
        f"{_lines(constraints)}\n\n"
        "No-Go Zones:\n"
        f"{_lines(no_go)}\n\n"
        "Expected Outputs:\n"
        f"{_lines(outputs)}\n\n"
        "Required Receipts:\n"
        f"{_lines(receipts)}\n\n"
        "Risk Notes:\n"
        f"{_lines(risk)}\n\n"
        "Rules:\n"
        "- Stay within scope and constraints.\n"
        "- Do not touch no-go resources.\n"
        "- Return receipt-aligned summary.\n"
    )


def dispatch_from_execution_brief(
    *,
    brief: dict[str, Any],
    codex_command: str = "codex.cmd",
    codex_args: list[str] | None = None,
    dispatch_mode: str = "spawn",
    timeout_sec: int = 120,
    dispatch_ready_path: Path = DEFAULT_DISPATCH_READY_PATH,
    prompt_path: Path = DEFAULT_PROMPT_PATH,
    dispatch_receipt_path: Path = DEFAULT_DISPATCH_RECEIPT_PATH,
) -> dict[str, Any]:
    prompt = _to_prompt(brief)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")

    dispatch_ready = {
        "request_id": brief.get("correlated_request_id"),
        "brief_id": brief.get("correlated_brief_id"),
        "handoff_id": brief.get("correlated_handoff_id"),
        "dispatch_ready": True,
        "gate_results": [
            {"gate": "execution_handoff_gate", "passed": True, "detail": "execution handoff gate passed."},
            {"gate": "execution_brief_present", "passed": True, "detail": "execution brief generated."},
        ],
        "prompt_artifact_path": prompt_path.as_posix(),
    }
    _write_json(dispatch_ready_path, dispatch_ready)

    return run_dispatch(
        dispatch_ready_path=dispatch_ready_path.as_posix(),
        prompt_path=prompt_path.as_posix(),
        output_path=dispatch_receipt_path.as_posix(),
        codex_command=codex_command,
        codex_args=codex_args,
        dispatch_mode=dispatch_mode,
        timeout_sec=timeout_sec,
    )

