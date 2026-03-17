from __future__ import annotations

from tools.council_bridge.council_role_rework_adapter import map_role_rework_hint


def test_role_rework_mapping_hits_target_role() -> None:
    payload = {
        "source": "feishu_chat",
        "message_id": "m1",
        "sender_id": "owner_001",
        "text": "让 critic 重看",
        "current_artifact_id": "plan-1",
        "current_artifact_type": "plan",
        "current_artifact_status": "under_review",
        "current_request_id": "req-1",
        "current_brief_id": "brief-1",
    }
    result = map_role_rework_hint(payload)
    assert result.is_mapped is True
    assert result.target_role == "critic"
    assert result.suggested_transition_request is not None
    assert result.suggested_transition_request["target_status"] == "needs_fix"
    assert result.dictionary_version is not None
    assert result.policy_scope is not None


def test_role_rework_mapping_ignored_when_no_hint() -> None:
    payload = {
        "source": "feishu_chat",
        "message_id": "m2",
        "sender_id": "owner_001",
        "text": "请总结一下",
        "current_artifact_id": "plan-1",
        "current_artifact_type": "plan",
        "current_artifact_status": "under_review",
    }
    result = map_role_rework_hint(payload)
    assert result.is_mapped is False
    assert result.mapping_type == "ignored"
