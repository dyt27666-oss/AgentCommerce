from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.council_role_collaboration_demo import write_sample
from tools.council_bridge.council_role_contract import (
    COUNCIL_ROLES,
    MINIMAL_ROLE_CHAIN,
    attach_role_metadata,
    build_minimal_role_chain,
    build_role_metadata,
    parse_owner_role_hint,
    synthesize_council_packet,
    validate_role_contracts,
    validate_role_metadata,
)


def test_role_contracts_are_complete_and_valid() -> None:
    errors = validate_role_contracts()
    assert errors == []


def test_minimal_role_chain_order_is_expected() -> None:
    chain = build_minimal_role_chain()
    assert [step.role for step in chain] == MINIMAL_ROLE_CHAIN


def test_owner_can_request_specific_role_rerun() -> None:
    hint = parse_owner_role_hint("请让 critic 重看")
    assert hint is not None
    assert hint.target_role == "critic"


def test_role_metadata_validation_enforces_no_execution_authority() -> None:
    artifact = {
        "artifact_id": "plan-r1",
        "produced_by_role": "planner",
    }
    role_meta = build_role_metadata(
        role="planner",
        role_round=1,
        depends_on_roles=[],
        upstream_artifact_ids=[],
    )
    updated = attach_role_metadata(artifact, role_meta)
    assert validate_role_metadata(updated) == []

    bad = dict(updated)
    bad["role_metadata"] = dict(updated["role_metadata"])
    bad["role_metadata"]["execution_authority"] = True
    errors = validate_role_metadata(bad)
    assert any("execution_authority" in err for err in errors)


def test_synthesize_council_packet_is_advisory_only() -> None:
    role_artifacts = []
    for idx, role in enumerate(COUNCIL_ROLES, start=1):
        role_artifacts.append(
            {
                "artifact_id": f"{role}-{idx}",
                "produced_by_role": role,
                "role_metadata": {
                    "role": role,
                    "role_run_id": f"{role}-r1",
                    "execution_authority": False,
                    "depends_on_roles": [],
                    "upstream_artifact_ids": [],
                    "owner_feedback_ids": [],
                },
            }
        )
    packet = synthesize_council_packet(role_artifacts)
    assert packet["can_enter_execution"] is False
    assert packet["requires_owner_review"] is True
    assert "strategist" in packet["roles_present"]


def test_role_collaboration_sample_can_be_written(tmp_path: Path) -> None:
    out = tmp_path / "sample.json"
    path = write_sample(out)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["phase"] == "6.1"
    assert payload["chain"] == MINIMAL_ROLE_CHAIN
    assert payload["owner_reroute_hint"]["target_role"] == "strategist"
