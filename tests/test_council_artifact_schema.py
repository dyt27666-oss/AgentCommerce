from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.council_bridge.council_artifact_schema import (
    CouncilDecisionArtifact,
    CouncilHandoffArtifact,
    CouncilPlanArtifact,
    CouncilReviewArtifact,
    CouncilRiskArtifact,
    OwnerFeedback,
    parse_council_artifact,
)


SAMPLES_DIR = Path("docs") / "council_artifact_samples_v0.1"


def _load(name: str) -> dict:
    path = SAMPLES_DIR / name
    return json.loads(path.read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize(
    ("sample", "expected_type"),
    [
        ("sample_plan.json", CouncilPlanArtifact),
        ("sample_risk.json", CouncilRiskArtifact),
        ("sample_review.json", CouncilReviewArtifact),
        ("sample_decision.json", CouncilDecisionArtifact),
        ("sample_handoff.json", CouncilHandoffArtifact),
    ],
)
def test_parse_council_artifact_samples(sample: str, expected_type: type) -> None:
    data = _load(sample)
    parsed = parse_council_artifact(data)
    assert isinstance(parsed, expected_type)


def test_owner_feedback_sample_parses() -> None:
    data = _load("sample_owner_feedback.json")
    feedback = OwnerFeedback.from_dict(data)
    assert feedback.feedback_type == "needs_fix"
    assert feedback.target_section == "steps"


def test_invalid_status_rejected_by_schema() -> None:
    data = _load("sample_plan.json")
    data["status"] = "running"
    with pytest.raises(ValueError, match="status must be one of"):
        parse_council_artifact(data)


def test_handoff_readiness_enum_is_enforced() -> None:
    data = _load("sample_handoff.json")
    data["execution_readiness_status"] = "unknown"
    with pytest.raises(ValueError, match="execution_readiness_status must be one of"):
        parse_council_artifact(data)
