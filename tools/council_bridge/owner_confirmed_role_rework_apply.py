"""Owner-confirmed role rework apply v0.1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.council_bridge.council_artifact_state_machine import TransitionRequest, apply_transition, validate_transition
from tools.council_bridge.council_role_contract import attach_role_metadata, build_role_metadata

DEFAULT_APPLY_PATH = Path("artifacts") / "council_owner_confirmed_role_rework_apply_result.json"
DEFAULT_ADVISORY_PATH = Path("artifacts") / "council_role_rework_advisory_artifact.json"
ALLOWED_CONFIRM_LANES = {"owner", "bridge"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise ValueError(f"json root must be object: {path}")
    return d


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_advisory_artifact(source: dict[str, Any], target_role: str, confirmed_by: str) -> dict[str, Any]:
    new = dict(source)
    base_id = str(source.get("artifact_id") or "artifact")
    new_id = f"{base_id}-{target_role}-rework-{int(datetime.now().timestamp())}"
    new["artifact_id"] = new_id
    new["parent_artifact_id"] = base_id
    derived = source.get("derived_from_artifact_ids")
    if not isinstance(derived, list):
        derived = []
    new["derived_from_artifact_ids"] = list({*derived, base_id})
    new["produced_by_role"] = target_role
    new["produced_by_roles"] = [target_role]
    new["status"] = "under_review"
    new["updated_at"] = _now_iso()
    new["summary"] = f"owner-confirmed role rework advisory generated for {target_role}"
    new["next_action"] = f"rerun council at role={target_role}"

    role_round = 1
    old_role_meta = source.get("role_metadata")
    rerun_of = None
    if isinstance(old_role_meta, dict):
        role_round = int(old_role_meta.get("role_round") or 1) + 1
        rerun_of = old_role_meta.get("role_run_id")

    role_meta = build_role_metadata(
        role=target_role,
        role_round=role_round,
        depends_on_roles=[],
        upstream_artifact_ids=[base_id],
        owner_feedback_ids=[],
        rerun_of_role_run_id=rerun_of if isinstance(rerun_of, str) else None,
    )
    role_meta["confirmed_by"] = confirmed_by
    return attach_role_metadata(new, role_meta)


def apply_owner_confirmed_role_rework(
    *,
    source_artifact_path: Path,
    mapping_result_path: Path,
    validation_result_path: Path,
    confirmed_by: str,
    confirmed_by_lane: str,
    reason: str,
    output_path: Path = DEFAULT_APPLY_PATH,
    advisory_artifact_path: Path = DEFAULT_ADVISORY_PATH,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "artifact_id": None,
        "before_status": None,
        "after_status": None,
        "target_role": None,
        "apply_status": "blocked",
        "apply_error": "",
        "advisory_artifact_id": None,
        "advisory_artifact_path": advisory_artifact_path.as_posix(),
        "confirmed_by": confirmed_by,
        "confirmed_by_lane": confirmed_by_lane,
        "reason": reason,
        "timestamp": _now_iso(),
    }

    def block(msg: str) -> dict[str, Any]:
        receipt["apply_status"] = "blocked"
        receipt["apply_error"] = msg
        _write(output_path, receipt)
        return receipt

    if confirmed_by_lane not in ALLOWED_CONFIRM_LANES:
        return block("only owner/bridge can confirm role rework apply")

    source = _load(source_artifact_path)
    mapping = _load(mapping_result_path)
    validation = _load(validation_result_path)

    receipt["artifact_id"] = source.get("artifact_id")
    receipt["before_status"] = source.get("status")

    if mapping.get("is_mapped") is not True:
        return block("role rework mapping is not mapped")
    if mapping.get("mapping_type") != "role_rework_hint":
        return block("mapping result is not role_rework_hint")
    if validation.get("is_valid") is not True:
        return block("role rework transition validation is invalid")

    target_role = mapping.get("target_role")
    if not isinstance(target_role, str) or not target_role:
        return block("missing target_role in mapping result")

    suggested = mapping.get("suggested_transition_request")
    if not isinstance(suggested, dict):
        return block("missing suggested_transition_request")

    trans_payload = dict(suggested)
    trans_payload["requested_by"] = confirmed_by
    trans_payload["requested_by_lane"] = confirmed_by_lane
    trans_payload["reason"] = reason or trans_payload.get("reason") or "owner confirmed role rework"
    transition = TransitionRequest.from_dict(trans_payload)

    final = validate_transition(source, transition)
    if not final.is_valid:
        return block("final validation failed: " + " | ".join(final.validation_errors))

    updated, applied = apply_transition(source, transition)
    if not applied.is_valid:
        return block("apply_transition failed unexpectedly")

    _write(source_artifact_path, updated)
    advisory = _build_advisory_artifact(updated, target_role, confirmed_by)
    _write(advisory_artifact_path, advisory)

    receipt["after_status"] = updated.get("status")
    receipt["target_role"] = target_role
    receipt["advisory_artifact_id"] = advisory.get("artifact_id")
    receipt["apply_status"] = "applied"
    _write(output_path, receipt)
    return receipt
