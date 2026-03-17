from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.owner_intent_normalization import (
    load_owner_intent_alias_config,
    normalize_owner_intent,
)

SAMPLES = Path("docs") / "owner_intent_normalization_samples_v0.1.json"


def _cases() -> list[dict]:
    payload = json.loads(SAMPLES.read_text(encoding="utf-8-sig"))
    return payload["cases"]


def _case(case_id: str) -> dict:
    for case in _cases():
        if case["case_id"] == case_id:
            return case
    raise AssertionError(case_id)


def test_alias_config_loads() -> None:
    cfg = load_owner_intent_alias_config()
    assert cfg["version"] == "owner.intent.alias.v0.1"
    assert "risk" in cfg["section_aliases"]
    assert "strategist" in cfg["role_aliases"]


def test_normalize_section_alias() -> None:
    c = _case("section-risk-tighten")
    out = normalize_owner_intent(c["text"])
    assert out.intent_type == "section_feedback"
    assert out.target_section == "risk"
    assert out.requested_action == "tighten"


def test_normalize_role_rework_alias() -> None:
    c = _case("role-strategist-rewrite")
    out = normalize_owner_intent(c["text"])
    assert out.intent_type == "role_rework"
    assert out.target_role == "strategist"
    assert out.requested_action == "rewrite"


def test_normalize_transition_hint_resubmit() -> None:
    c = _case("resubmit-transition-hint")
    out = normalize_owner_intent(c["text"])
    assert out.intent_type == "transition_hint"
    assert out.requested_action == "resubmit"


def test_ambiguous_input_returns_unknown() -> None:
    c = _case("ambiguous")
    out = normalize_owner_intent(c["text"])
    assert out.intent_type == "unknown"
    assert "intent_unresolved" in out.ambiguity_flags
