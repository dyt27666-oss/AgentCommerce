from __future__ import annotations

from tools.council_bridge.execution_receipt_skeleton_helper import build_execution_receipt_skeleton


def _source_paths() -> dict[str, str]:
    return {
        "dispatch_receipt": "artifacts/council_codex_dispatch_receipt.json",
        "completion": "artifacts/council_codex_dispatch_completion.json",
        "continue_once_result": "artifacts/council_feishu_continue_once_result.json",
        "handoff": "artifacts/council_bridge_handoff.json",
    }


def test_skeleton_generation_happy_path() -> None:
    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt={
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
            "dispatch_status": "dispatched",
        },
        completion={
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
            "completion_observation_status": "running_no_execution_receipt",
        },
        continue_once_result={
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
            "completion_check_attempted": True,
        },
        handoff={
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
        },
        source_paths=_source_paths(),
    )
    assert skeleton["request_id"] == "exec-req-001"
    assert skeleton["dispatch_status"] == "dispatched"
    assert skeleton["completion_state"] == "running_no_execution_receipt"
    assert skeleton["execution_receipt_status"] == "skeleton_only"
    assert skeleton["identity_linkage_status"] == "matched"
    assert "execution_status" in " ".join(skeleton["suggested_owner_fill_fields"])


def test_identity_linkage_inherited_and_mismatch_detected() -> None:
    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt={"request_id": "exec-req-001", "brief_id": "b1", "handoff_id": "h1", "dispatch_status": "dispatched"},
        completion={"request_id": "exec-req-002", "brief_id": "b1", "handoff_id": "h1", "completion_observation_status": "x"},
        continue_once_result=None,
        handoff=None,
        source_paths=_source_paths(),
    )
    assert skeleton["request_id"] == "exec-req-001"
    assert skeleton["identity_linkage_status"] == "mismatch_detected"
    assert any("mismatch" in x for x in skeleton["notes"])


def test_degraded_skeleton_with_missing_artifacts() -> None:
    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt=None,
        completion=None,
        continue_once_result={"request_id": "exec-req-001"},
        handoff=None,
        source_paths=_source_paths(),
    )
    assert skeleton["execution_receipt_status"] == "skeleton_only"
    assert skeleton["dispatch_status"] is None
    assert skeleton["completion_state"] is None
    assert skeleton["identity_linkage_status"] == "partial_missing"
    assert any("missing" in x for x in skeleton["notes"])


def test_missing_key_fields_add_explainable_notes() -> None:
    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt={"dispatch_status": "failed"},
        completion={"completion_observation_status": "not_dispatched"},
        continue_once_result={"completion_check_attempted": False},
        handoff=None,
        source_paths=_source_paths(),
    )
    assert skeleton["identity_linkage_status"] == "partial_missing"
    assert any("partial" in x for x in skeleton["notes"])
    assert any("did not run completion check" in x for x in skeleton["notes"])


def test_never_claims_final_receipt() -> None:
    skeleton = build_execution_receipt_skeleton(
        dispatch_receipt={"dispatch_status": "dispatched"},
        completion={"completion_observation_status": "execution_receipt_available"},
        continue_once_result=None,
        handoff=None,
        source_paths=_source_paths(),
    )
    assert skeleton["execution_receipt_status"] == "skeleton_only"

