from __future__ import annotations

from tools.council_bridge.permission_policy import (
    LEVEL_DESTRUCTIVE_ACTION,
    LEVEL_LOCAL_EXECUTION,
    LEVEL_READ_ONLY,
    LEVEL_SAFE_WRITE,
    evaluate_permission_context,
)


def test_permission_default_is_read_only_for_analysis_request() -> None:
    decision = evaluate_permission_context("帮我分析一下这个问题")
    assert decision.requested_permission_level == LEVEL_READ_ONLY
    assert decision.granted_permission_level == LEVEL_READ_ONLY
    assert decision.permission_source == "default_read_only"
    assert decision.confirmation_required is False


def test_permission_grants_safe_write_from_explicit_phrase() -> None:
    decision = evaluate_permission_context("允许修改仓库文件但不要运行，修复这个 bug")
    assert decision.requested_permission_level == LEVEL_SAFE_WRITE
    assert decision.granted_permission_level == LEVEL_SAFE_WRITE
    assert decision.permission_source == "prompt_explicit_grant"
    assert decision.confirmation_required is False


def test_permission_requires_confirmation_for_local_execution_without_grant() -> None:
    decision = evaluate_permission_context("请运行测试并把结果发我")
    assert decision.requested_permission_level == LEVEL_LOCAL_EXECUTION
    assert decision.granted_permission_level == LEVEL_READ_ONLY
    assert decision.confirmation_required is True
    assert "允许修改并执行本地测试" in decision.recommended_grant_phrase


def test_permission_destructive_action_denied_by_default() -> None:
    decision = evaluate_permission_context("执行 git reset --hard 回滚到上一个版本")
    assert decision.requested_permission_level == LEVEL_DESTRUCTIVE_ACTION
    assert decision.granted_permission_level != LEVEL_DESTRUCTIVE_ACTION
    assert decision.confirmation_required is True
    assert decision.destructive_action_detected is True

