"""Minimal collaboration sample for Council roles (Phase 6.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.council_bridge.council_role_contract import (
    ROLE_CONTRACTS,
    attach_role_metadata,
    build_minimal_role_chain,
    build_role_metadata,
    parse_owner_role_hint,
    synthesize_council_packet,
)

DEFAULT_OUTPUT_DIR = Path("docs") / "council_role_samples_v0.1"
DEFAULT_SAMPLE_PATH = DEFAULT_OUTPUT_DIR / "minimal_role_collaboration_sample.json"


def build_minimal_role_collaboration_sample() -> dict[str, Any]:
    chain = build_minimal_role_chain()
    role_artifacts: list[dict[str, Any]] = []
    upstream_ids: list[str] = []

    for idx, step in enumerate(chain, start=1):
        role = step.role
        artifact_type = ROLE_CONTRACTS[role]["artifact_types"][0]
        artifact = {
            "artifact_type": artifact_type,
            "schema_version": "council.artifact.v0.1",
            "artifact_id": f"{role}-artifact-r1-{idx:02d}",
            "request_id": "req-role-collab-001",
            "brief_id": "brief-role-collab-001",
            "handoff_id": None,
            "council_round": 1,
            "parent_artifact_id": upstream_ids[-1] if upstream_ids else None,
            "derived_from_artifact_ids": list(upstream_ids[-2:]) if upstream_ids else [],
            "owner_id": "owner_001",
            "chat_id": "chat_role_collab",
            "created_at": "2026-03-16T20:00:00+08:00",
            "updated_at": "2026-03-16T20:00:00+08:00",
            "produced_by_lane": "council",
            "produced_by_role": role,
            "produced_by_roles": [role],
            "status": "under_review",
            "summary": f"{role} output",
            "constraints": ["HITL required"],
            "assumptions": [],
            "open_questions": [],
            "next_action": "owner review",
            "owner_feedback": [],
            "audit_trace": [],
            "lineage": {"phase": "6.1"},
        }
        role_meta = build_role_metadata(
            role=role,
            role_round=1,
            depends_on_roles=step.depends_on_roles,
            upstream_artifact_ids=list(upstream_ids),
        )
        role_artifacts.append(attach_role_metadata(artifact, role_meta))
        upstream_ids.append(artifact["artifact_id"])

    owner_hint = parse_owner_role_hint("让 strategist 重写")
    packet = synthesize_council_packet(role_artifacts)

    return {
        "phase": "6.1",
        "chain": [step.role for step in chain],
        "role_artifacts": role_artifacts,
        "owner_reroute_hint": {
            "target_role": owner_hint.target_role if owner_hint else None,
            "reason": owner_hint.reason if owner_hint else None,
            "source": owner_hint.source if owner_hint else None,
        },
        "council_packet": packet,
    }


def write_sample(path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    payload = build_minimal_role_collaboration_sample()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    output = write_sample()
    print(json.dumps({"sample_path": output.as_posix()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
