"""Readonly Council -> Codex bridge stub.

This module is intentionally tiny:
1. load json input
2. validate minimal contract
3. build normalized codex-ready payload

It does not execute Codex or mutate repository state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_input(path: str) -> dict[str, Any]:
    """Load and parse input json from disk."""
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input root must be a JSON object.")
    return data


def validate_contract(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate tiny PoC contract with explicit, field-level errors."""
    errors: list[str] = []

    council_brief = data.get("council_brief")
    codex_request = data.get("codex_execution_request")

    if not isinstance(council_brief, dict):
        errors.append("council_brief must be an object.")
    if not isinstance(codex_request, dict):
        errors.append("codex_execution_request must be an object.")
    if errors:
        return False, errors

    _require_non_empty_str(council_brief, "brief_id", "council_brief", errors)
    _require_non_empty_str(council_brief, "owner_intent", "council_brief", errors)

    _require_non_empty_str_list(council_brief, "scope", "council_brief", errors)
    _require_non_empty_str_list(council_brief, "non_goals", "council_brief", errors)
    _require_non_empty_str_list(
        council_brief, "touched_files", "council_brief", errors
    )
    _require_non_empty_str_list(
        council_brief, "acceptance_criteria", "council_brief", errors
    )
    _require_non_empty_str_list(
        council_brief, "validation_steps", "council_brief", errors
    )
    _require_non_empty_str_list(council_brief, "delivery_format", "council_brief", errors)

    _require_non_empty_str(codex_request, "request_id", "codex_execution_request", errors)
    _require_non_empty_str(codex_request, "brief_id", "codex_execution_request", errors)
    _require_object(codex_request, "execution_brief", "codex_execution_request", errors)
    _require_object(codex_request, "repo_context", "codex_execution_request", errors)
    _require_non_empty_str_list(
        codex_request, "constraints", "codex_execution_request", errors
    )

    if isinstance(codex_request.get("repo_context"), dict):
        _require_non_empty_str(
            codex_request["repo_context"], "repo", "codex_execution_request.repo_context", errors
        )
        _require_non_empty_str(
            codex_request["repo_context"], "branch", "codex_execution_request.repo_context", errors
        )

    cb_brief_id = council_brief.get("brief_id")
    req_brief_id = codex_request.get("brief_id")
    if _is_non_empty_str(cb_brief_id) and _is_non_empty_str(req_brief_id):
        if cb_brief_id.strip() != req_brief_id.strip():
            errors.append(
                "brief_id mismatch between council_brief.brief_id and "
                "codex_execution_request.brief_id."
            )

    return len(errors) == 0, errors


def build_codex_ready_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build normalized readonly output from tiny PoC input."""
    is_valid, errors = validate_contract(data)

    council_brief = data.get("council_brief", {})
    codex_request = data.get("codex_execution_request", {})

    result: dict[str, Any] = {
        "status": "valid" if is_valid else "invalid_input",
        "request_id": codex_request.get("request_id") if isinstance(codex_request, dict) else None,
        "brief_id": council_brief.get("brief_id") if isinstance(council_brief, dict) else None,
        "codex_ready_payload": None,
        "errors": errors,
    }

    if not is_valid:
        return result

    result["codex_ready_payload"] = {
        "goal": council_brief["owner_intent"].strip(),
        "scope": _normalize_str_list(council_brief["scope"]),
        "non_goals": _normalize_str_list(council_brief["non_goals"]),
        "allowed_files": _normalize_str_list(council_brief["touched_files"]),
        "acceptance_criteria": _normalize_str_list(council_brief["acceptance_criteria"]),
        "validation_steps": _normalize_str_list(council_brief["validation_steps"]),
        "constraints": _normalize_str_list(codex_request["constraints"]),
        "delivery_format": _normalize_str_list(council_brief["delivery_format"]),
        "repo_context": {
            "repo": codex_request["repo_context"]["repo"].strip(),
            "branch": codex_request["repo_context"]["branch"].strip(),
        },
    }
    return result


def export_dry_run_result(input_path: str, output_path: str) -> dict[str, Any]:
    """Run readonly dry-run flow and export structured result to JSON file."""
    try:
        data = load_input(input_path)
        result = build_codex_ready_payload(data)
    except Exception as exc:
        result = {
            "status": "invalid_input",
            "request_id": None,
            "brief_id": None,
            "codex_ready_payload": None,
            "errors": [f"runtime_error: {exc}"],
        }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_str_list(values: list[Any]) -> list[str]:
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def _require_non_empty_str(
    obj: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = obj.get(key)
    if not _is_non_empty_str(value):
        errors.append(f"{prefix}.{key} must be a non-empty string.")


def _require_non_empty_str_list(
    obj: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = obj.get(key)
    if not isinstance(value, list):
        errors.append(f"{prefix}.{key} must be a list of non-empty strings.")
        return
    if not value:
        errors.append(f"{prefix}.{key} must not be empty.")
        return
    invalid = [v for v in value if not _is_non_empty_str(v)]
    if invalid:
        errors.append(f"{prefix}.{key} must contain only non-empty strings.")


def _require_object(obj: dict[str, Any], key: str, prefix: str, errors: list[str]) -> None:
    value = obj.get(key)
    if not isinstance(value, dict):
        errors.append(f"{prefix}.{key} must be an object.")


def main() -> None:
    """Small local demo entry (readonly)."""
    parser = argparse.ArgumentParser(description="Readonly Council bridge stub demo.")
    parser.add_argument(
        "--input",
        default=str(Path("docs") / "council-mcp-input-sample.json"),
        help="Path to Council MCP input JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("artifacts") / "council_bridge_dry_run.json"),
        help="Path to exported dry-run JSON result file.",
    )
    args = parser.parse_args()

    result = export_dry_run_result(args.input, args.output)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[readonly-stub] dry-run result exported to: {args.output}")


if __name__ == "__main__":
    main()
