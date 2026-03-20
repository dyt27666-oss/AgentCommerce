from __future__ import annotations

from tools.council_bridge.message_mode_policy import (
    MODE_CHAT,
    MODE_OWNER_ACTION,
    MODE_SYSTEM_CONTROL,
    MODE_WORKFLOW_REQUEST,
    decide_message_mode,
)


def test_mode_priority_owner_action_beats_workflow_request() -> None:
    decision = decide_message_mode(
        text="请执行 apply_suggested_transition 并开始执行",
        source="feishu_action_protocol",
        detected_action="dispatch",
        execution_trigger_detected=True,
        council_confirm_keyword="apply_suggested_transition",
        role_rework_confirm_keyword=None,
    )
    assert decision.detected_mode == MODE_OWNER_ACTION
    assert decision.rule_hit == "owner_action_confirm_signal"


def test_mode_workflow_request_when_explicit_execute_intent() -> None:
    decision = decide_message_mode(
        text="请开始执行这个任务并给我结果",
        source="feishu_chat",
        detected_action=None,
        execution_trigger_detected=False,
        council_confirm_keyword=None,
        role_rework_confirm_keyword=None,
    )
    assert decision.detected_mode == MODE_WORKFLOW_REQUEST
    assert decision.rule_hit == "workflow_request_intent_keyword"


def test_mode_system_control_for_permission_statement() -> None:
    decision = decide_message_mode(
        text="允许修改并执行本地测试",
        source="feishu_chat",
        detected_action=None,
        execution_trigger_detected=False,
        council_confirm_keyword=None,
        role_rework_confirm_keyword=None,
    )
    assert decision.detected_mode == MODE_SYSTEM_CONTROL
    assert decision.rule_hit == "system_control_permission_statement"


def test_mode_chat_for_plain_conversation() -> None:
    decision = decide_message_mode(
        text="今天先总结一下当前进度",
        source="feishu_chat",
        detected_action=None,
        execution_trigger_detected=False,
        council_confirm_keyword=None,
        role_rework_confirm_keyword=None,
    )
    assert decision.detected_mode == MODE_CHAT
    assert decision.rule_hit == "chat_fallback"

