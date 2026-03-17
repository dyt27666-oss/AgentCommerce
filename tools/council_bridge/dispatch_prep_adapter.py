"""Dispatch-prep adapter for semi-manual bridge v0.

This helper does not dispatch to Codex.
It only validates readiness and writes a dispatch-ready artifact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.council_bridge.handoff_prompt_adapter import load_handoff, validate_executable_handoff
except ModuleNotFoundError:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tools.council_bridge.handoff_prompt_adapter import load_handoff, validate_executable_handoff


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
OUTPUT_PATH = Path("artifacts") / "council_codex_dispatch_ready.json"


def _read_prompt(prompt_path: Path) -> tuple[bool, bool]:
    if not prompt_path.exists():
        return False, False
    content = prompt_path.read_text(encoding="utf-8")
    return True, bool(content.strip())


def build_dispatch_package(
    handoff: dict[str, Any],
    prompt_path: str,
    prompt_exists: bool,
    prompt_non_empty: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    handoff_errors = validate_executable_handoff(handoff)

    gate_results = [
        {
            "gate": "handoff_executable",
            "passed": len(handoff_errors) == 0,
            "detail": "passed" if len(handoff_errors) == 0 else "; ".join(handoff_errors),
        },
        {
            "gate": "prompt_exists",
            "passed": prompt_exists,
            "detail": "prompt file exists" if prompt_exists else "prompt file not found",
        },
        {
            "gate": "prompt_non_empty",
            "passed": prompt_non_empty,
            "detail": "prompt has content" if prompt_non_empty else "prompt is empty",
        },
    ]

    dispatch_ready = all(g["passed"] for g in gate_results)
    now_time = now or datetime.now(timezone.utc).astimezone()

    artifact: dict[str, Any] = {
        "request_id": handoff.get("request_id"),
        "brief_id": handoff.get("brief_id"),
        "handoff_id": handoff.get("handoff_id"),
        "dispatch_ready": dispatch_ready,
        "gate_results": gate_results,
        "prompt_artifact_path": Path(prompt_path).as_posix(),
        "generated_at": now_time.isoformat(timespec="seconds"),
    }

    if dispatch_ready:
        artifact["dispatch_notes"] = "Dispatch-prep gates passed. Manual dispatch can proceed."
    else:
        failed = [f"{g['gate']}: {g['detail']}" for g in gate_results if not g["passed"]]
        artifact["blocking_reason"] = " | ".join(failed)
    return artifact


def prepare_dispatch_package(handoff_path: str, prompt_path: str, output_path: str) -> dict[str, Any]:
    handoff = load_handoff(handoff_path)
    exists, non_empty = _read_prompt(Path(prompt_path))
    artifact = build_dispatch_package(handoff, prompt_path, exists, non_empty)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare dispatch-ready artifact from approved handoff.")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument("--prompt", default=str(PROMPT_PATH), help="Path to prompt text artifact.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to dispatch-ready artifact JSON.")
    args = parser.parse_args()

    artifact = prepare_dispatch_package(args.handoff, args.prompt, args.output)
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    print(f"\n[dispatch-prep] saved: {args.output}")
    if not artifact["dispatch_ready"]:
        print("[dispatch-prep] blocked: handoff is not dispatch-ready.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
