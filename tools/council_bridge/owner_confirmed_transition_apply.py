"""Owner-confirmed apply transition helper v0.1.

Reads observe-only mapping/validation artifacts, checks gating conditions,
and applies transition only with explicit owner-confirmed signal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.council_artifact_state_machine import TransitionRequest, apply_transition, validate_transition


DEFAULT_OUTPUT_PATH = Path("artifacts") / "council_owner_confirmed_apply_result.json"

ALLOWED_APPLY_TARGETS = {
    "needs_fix",
    "revised",
    "resubmitted",
    "ready_for_owner_review",
    "owner_rejected",
    "owner_approved",
    "handoff_ready",
}
ALLOWED_CONFIRM_LANES = {"owner", "bridge"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_owner_confirmed_transition(
    *,
    source_artifact_path: Path,
    mapping_result_path: Path,
    validation_result_path: Path,
    confirmed_by: str,
    confirmed_by_lane: str,
    reason: str,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    observe_only_source: str | None = None,
    current_stage: str | None = None,
) -> dict[str, Any]:
    timestamp = _now_iso()
    receipt: dict[str, Any] = {
        "artifact_id": None,
        "artifact_type": None,
        "before_status": None,
        "after_status": None,
        "applied_transition": None,
        "requested_by": None,
        "confirmed_by": confirmed_by,
        "confirmed_by_lane": confirmed_by_lane,
        "reason": reason,
        "mapping_artifact_id": mapping_result_path.as_posix(),
        "validation_artifact_id": validation_result_path.as_posix(),
        "apply_status": "blocked",
        "apply_error": "",
        "timestamp": timestamp,
        "observe_only_source": observe_only_source or "",
        "lineage_update": {},
    }

    def block(msg: str) -> dict[str, Any]:
        receipt["apply_status"] = "blocked"
        receipt["apply_error"] = msg
        _write_json(output_path, receipt)
        return receipt

    if confirmed_by_lane not in ALLOWED_CONFIRM_LANES:
        return block("confirm signal lane is not allowed; only owner/bridge can confirm apply.")

    if not reason.strip():
        return block("confirm reason is required.")

    if current_stage and current_stage not in {"council_review", "owner_review"}:
        return block("current stage does not allow owner-confirmed apply.")

    if not source_artifact_path.exists():
        return block(f"source artifact not found: {source_artifact_path.as_posix()}")
    if not mapping_result_path.exists():
        return block(f"mapping result artifact not found: {mapping_result_path.as_posix()}")
    if not validation_result_path.exists():
        return block(f"validation result artifact not found: {validation_result_path.as_posix()}")

    artifact = _load_json(source_artifact_path)
    mapping = _load_json(mapping_result_path)
    validation = _load_json(validation_result_path)

    receipt["artifact_id"] = artifact.get("artifact_id")
    receipt["artifact_type"] = artifact.get("artifact_type")
    receipt["before_status"] = artifact.get("status")

    if mapping.get("is_mapped") is not True:
        return block("mapping_status is not mapped.")
    suggested = mapping.get("suggested_transition_request")
    if not isinstance(suggested, dict):
        return block("no suggested_transition_request found in mapping result.")
    if validation.get("is_valid") is not True:
        return block("validation_status is not valid; apply is blocked.")

    target_status = suggested.get("target_status")
    if target_status not in ALLOWED_APPLY_TARGETS:
        return block("target status is not in allowed owner-confirmed apply set.")

    transition_payload = dict(suggested)
    transition_payload["requested_by"] = confirmed_by
    transition_payload["requested_by_lane"] = confirmed_by_lane
    transition_payload["reason"] = reason
    transition_payload["triggering_artifact_id"] = transition_payload.get("triggering_artifact_id") or str(artifact.get("artifact_id") or "")
    transition = TransitionRequest.from_dict(transition_payload)

    final_check = validate_transition(artifact, transition)
    if not final_check.is_valid:
        receipt["applied_transition"] = f"{transition.current_status}->{transition.target_status}"
        return block("final validation failed at apply time: " + " | ".join(final_check.validation_errors))

    updated, result = apply_transition(artifact, transition)
    receipt["requested_by"] = transition.requested_by
    receipt["applied_transition"] = f"{transition.current_status}->{transition.target_status}"
    receipt["after_status"] = updated.get("status")

    lineage = updated.get("lineage")
    if not isinstance(lineage, dict):
        lineage = {}
    lineage_update = {
        "last_confirmed_apply_at": timestamp,
        "last_confirmed_apply_by": confirmed_by,
        "last_confirmed_apply_transition": receipt["applied_transition"],
    }
    lineage.update(lineage_update)
    updated["lineage"] = lineage
    receipt["lineage_update"] = lineage_update

    if result.is_valid:
        _write_json(source_artifact_path, updated)
        receipt["apply_status"] = "applied"
        receipt["apply_error"] = ""
    else:
        receipt["apply_status"] = "failed"
        receipt["apply_error"] = "unexpected: apply_transition returned invalid result."

    _write_json(output_path, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply owner-confirmed transition from observe-only artifacts.")
    parser.add_argument("--artifact", required=True, help="Current artifact path.")
    parser.add_argument("--mapping", required=True, help="Observe-only mapping result artifact path.")
    parser.add_argument("--validation", required=True, help="Observe-only validation result artifact path.")
    parser.add_argument("--confirmed-by", required=True, help="Owner/bridge id.")
    parser.add_argument("--confirmed-by-lane", required=True, choices=sorted(ALLOWED_CONFIRM_LANES))
    parser.add_argument("--reason", required=True, help="Apply reason.")
    parser.add_argument("--current-stage", default="", help="Current stage, e.g. council_review.")
    parser.add_argument("--observe-only-source", default="", help="Reference path to observe-only route result.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Apply receipt output path.")
    args = parser.parse_args()

    result = apply_owner_confirmed_transition(
        source_artifact_path=Path(args.artifact),
        mapping_result_path=Path(args.mapping),
        validation_result_path=Path(args.validation),
        confirmed_by=args.confirmed_by,
        confirmed_by_lane=args.confirmed_by_lane,
        reason=args.reason,
        output_path=Path(args.output),
        observe_only_source=args.observe_only_source or None,
        current_stage=args.current_stage or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

