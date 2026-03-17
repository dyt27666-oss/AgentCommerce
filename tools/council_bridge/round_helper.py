"""Guided semi-manual bridge round helper (v0).

This helper does not execute Codex or any external system.
It only validates approved handoff, prepares prompt artifact,
and produces a short round summary for owner actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from tools.council_bridge.handoff_prompt_adapter import (
        export_codex_prompt,
        load_handoff,
        validate_executable_handoff,
    )
except ModuleNotFoundError:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tools.council_bridge.handoff_prompt_adapter import (
        export_codex_prompt,
        load_handoff,
        validate_executable_handoff,
    )


HANDOFF_PATH = Path("artifacts") / "council_bridge_handoff.json"
PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
ROUND_SUMMARY_PATH = Path("artifacts") / "council_bridge_round_summary.json"
RECEIPT_PATH = (Path("artifacts") / "council_codex_execution_receipt.json").as_posix()
FINAL_REVIEW_PATH = (Path("artifacts") / "council_owner_final_review_summary.json").as_posix()


def build_round_summary(handoff: dict[str, Any], prompt_path: str) -> dict[str, Any]:
    return {
        "request_id": handoff.get("request_id"),
        "brief_id": handoff.get("brief_id"),
        "handoff_id": handoff.get("handoff_id"),
        "approval_status": handoff.get("approval_status"),
        "prompt_artifact_path": prompt_path,
        "expected_next_artifacts": [
            RECEIPT_PATH,
            FINAL_REVIEW_PATH,
        ],
        "next_manual_actions": [
            "Use prompt artifact with Codex manually (no auto execution).",
            "After execution, prepare artifacts/council_codex_execution_receipt.json.",
            "Complete artifacts/council_owner_final_review_summary.json.",
        ],
    }


def prepare_round(
    handoff_path: str,
    prompt_output_path: str,
    summary_output_path: str | None = None,
) -> dict[str, Any]:
    handoff = load_handoff(handoff_path)
    errors = validate_executable_handoff(handoff)
    if errors:
        raise ValueError("Handoff is not executable under v0 intake rules:\n- " + "\n- ".join(errors))

    export_codex_prompt(handoff_path, prompt_output_path)
    summary = build_round_summary(handoff, prompt_output_path)

    if summary_output_path:
        out = Path(summary_output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Guided semi-manual bridge round helper (v0).")
    parser.add_argument("--handoff", default=str(HANDOFF_PATH), help="Path to handoff artifact JSON.")
    parser.add_argument("--prompt-output", default=str(PROMPT_PATH), help="Path to output prompt text file.")
    parser.add_argument(
        "--summary-output",
        default=str(ROUND_SUMMARY_PATH),
        help="Path to output round summary JSON file.",
    )
    args = parser.parse_args()

    summary = prepare_round(
        handoff_path=args.handoff,
        prompt_output_path=args.prompt_output,
        summary_output_path=args.summary_output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[round-helper] prompt saved: {args.prompt_output}")
    print(f"[round-helper] summary saved: {args.summary_output}")


if __name__ == "__main__":
    main()
