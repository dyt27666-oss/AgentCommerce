from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge.feishu_notifier import (
    apply_notify_mode,
    build_dedupe_key,
    build_feishu_payload,
    is_feishu_send_success,
    mark_notify_state,
    resolve_keyword_marker,
    resolve_webhook_url,
    should_suppress_send,
    summarize_artifact,
)


def test_summarize_dispatch_ready_blocked_contains_reason_and_action() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_ready": False,
        "blocking_reason": "prompt file not found",
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_ready.json", data)
    assert "dispatch_ready=False" in text
    assert "blocking_reason=prompt file not found" in text
    assert "next_action=Fix dispatch gates" in text


def test_summarize_dispatch_ready_detail_contains_gate_summary() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_ready": True,
        "gate_results": [{"gate": "a", "passed": True}, {"gate": "b", "passed": False}],
        "prompt_artifact_path": "artifacts/council_codex_prompt.txt",
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_ready.json", data, level="detail")
    assert "state_explanation=Dispatch gates passed." in text
    assert "gate_results=1/2 passed" in text
    assert "prompt_artifact_path=artifacts/council_codex_prompt.txt" in text


def test_summarize_owner_final_review_contains_decision() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "final_owner_decision": "approved",
        "execution_status": "completed",
        "next_action": "Close round.",
    }
    text = summarize_artifact("artifacts/council_owner_final_review_summary.json", data)
    assert "final_owner_decision=approved" in text
    assert "execution_status=completed" in text
    assert "next_action=Close round." in text


def test_summarize_completion_observation_uses_completion_state() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_status": "dispatched",
        "dispatch_attempted": True,
        "completion_observation_status": "running_no_execution_receipt",
        "next_action": "Wait for completion.",
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_completion.json", data)
    assert "completion_state=running_no_execution_receipt" in text
    assert "next_action=Wait for completion." in text


def test_summarize_completion_detail_contains_log_hints() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_status": "dispatched",
        "dispatch_attempted": True,
        "completion_observation_status": "running_no_execution_receipt",
        "next_action": "Wait for completion.",
        "dispatch_log_tail": {"stdout": "", "stderr": "error hint"},
        "dispatch_process": {"pid": 1234, "running": True},
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_completion.json", data, level="detail")
    assert "log_tail_stderr=error hint" in text
    assert "process_running=True" in text
    assert "execution_receipt_presence=no_or_pending" in text


def test_summarize_completion_review_is_decision_focused() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "dispatch_status": "dispatched",
        "dispatch_attempted": True,
        "completion_observation_status": "running_no_execution_receipt",
        "next_action": "Wait for completion.",
        "dispatch_log_tail": {"stdout": "", "stderr": "long raw log should not be dumped here"},
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_completion.json", data, level="review")
    assert "阶段：执行后状态观察" in text
    assert "状态解释：" in text
    assert "下一步建议：Wait for completion." in text
    assert "log_tail_stderr=" not in text


def test_summarize_skeleton_review_is_owner_fill_focused() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "execution_receipt_status": "skeleton_only",
        "identity_linkage_status": "matched",
        "dispatch_status": "dispatched",
        "completion_state": "execution_receipt_available",
        "suggested_owner_fill_fields": ["execution_status", "changed_files", "summary", "next_step_suggestion"],
    }
    text = summarize_artifact("artifacts/council_codex_execution_receipt_skeleton.json", data, level="review")
    assert "阶段：执行回执预填" in text
    assert "你需要补充：execution_status, changed_files, summary, next_step_suggestion" in text
    assert "可回复动作：approved / revision_request / needs_fix / rejected" in text


def test_summarize_final_review_review_mode_contains_decision_core() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-004",
        "final_owner_decision": "approved",
        "execution_status": "completed",
        "scope_compliance_check": {"in_allowed_scope": True, "constraints_compliant": True},
        "key_reason": "Looks good",
        "next_action": "Close round.",
    }
    text = summarize_artifact("artifacts/council_owner_final_review_summary.json", data, level="review")
    assert "阶段：最终拍板结果" in text
    assert "当前结果：决策=approved，执行状态=completed" in text
    assert "下一步建议：Close round." in text
    assert "可回复动作：当前为结果通知阶段，通常无需继续回复动作。" in text


def test_summarize_continue_once_review_mode_contains_key_fields() -> None:
    data = {
        "final_status": "executed_continue_success",
        "flow_state": "continue",
        "executed_step": "tools/council_bridge/codex_dispatch_runner.py",
        "completion_state": "execution_receipt_available",
        "owner_review_ready": True,
        "post_receipt_next_manual_action": "Run final review once.",
        "receipt_skeleton_status": "generated",
        "inherited_identity": {
            "request_id": "exec-req-001",
            "brief_id": "council-poc-brief-001",
            "handoff_id": "handoff-20260315-004",
        },
    }
    text = summarize_artifact("artifacts/council_feishu_continue_once_result.json", data, level="review")
    assert "阶段：飞书确认后本地续跑" in text
    assert "request_id=exec-req-001 | brief_id=council-poc-brief-001 | handoff_id=handoff-20260315-004" in text
    assert "当前结果：flow=continue" in text
    assert "评审就绪：owner_review_ready=True" in text
    assert "下一步建议：Run final review once." in text
    assert "可回复动作：approved / revision_request / needs_fix / rejected" in text


def test_summarize_continue_once_review_fallback_ids_from_continuation_path(tmp_path: Path) -> None:
    continuation = tmp_path / "continuation.json"
    continuation.write_text(
        json.dumps(
            {
                "request_id": "exec-req-001",
                "brief_id": "council-poc-brief-001",
                "handoff_id": "handoff-20260315-004",
            }
        ),
        encoding="utf-8",
    )
    data = {
        "final_status": "executed_continue_success",
        "flow_state": "continue",
        "continuation_artifact": continuation.as_posix(),
        "post_receipt_next_manual_action": "Run final review once.",
    }
    text = summarize_artifact("artifacts/council_feishu_continue_once_result.json", data, level="review")
    assert "request_id=exec-req-001 | brief_id=council-poc-brief-001 | handoff_id=handoff-20260315-004" in text


def test_summarize_dispatch_ready_review_includes_dispatch_action_hint() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "brief-001",
        "handoff_id": "handoff-001",
        "dispatch_ready": True,
    }
    text = summarize_artifact("artifacts/council_codex_dispatch_ready.json", data, level="review")
    assert "可回复动作：dispatch / hold / needs_fix / reject" in text


def test_build_feishu_payload_text_shape() -> None:
    payload = build_feishu_payload("hello")
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "[bridge] hello"


def test_build_feishu_payload_allows_empty_marker() -> None:
    payload = build_feishu_payload("hello", keyword_marker="")
    assert payload["content"]["text"] == "hello"


def test_apply_notify_mode_test_prefix() -> None:
    assert apply_notify_mode("[bridge] hello", mode="test").startswith("[TEST] ")
    assert apply_notify_mode("[bridge] hello", mode="normal") == "[bridge] hello"


def test_resolve_webhook_url_priority(monkeypatch) -> None:
    monkeypatch.delenv("AGENTCOMMERCE_FEISHU_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    assert resolve_webhook_url("https://explicit.example") == "https://explicit.example"

    monkeypatch.setenv("AGENTCOMMERCE_FEISHU_WEBHOOK_URL", "https://project.example")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://fallback.example")
    assert resolve_webhook_url("") == "https://project.example"
    assert resolve_webhook_url(None) == "https://project.example"

    monkeypatch.delenv("AGENTCOMMERCE_FEISHU_WEBHOOK_URL", raising=False)
    assert resolve_webhook_url("") == "https://fallback.example"


def test_is_feishu_send_success_rules() -> None:
    assert is_feishu_send_success({"code": 0, "msg": "success"}) is True
    assert is_feishu_send_success({"code": 19024, "msg": "Key Words Not Found"}) is False
    assert is_feishu_send_success({"raw_response": "ok"}) is True


def test_resolve_keyword_marker_priority(monkeypatch) -> None:
    monkeypatch.delenv("AGENTCOMMERCE_FEISHU_KEYWORD_MARKER", raising=False)
    monkeypatch.delenv("FEISHU_KEYWORD_MARKER", raising=False)
    assert resolve_keyword_marker("bridge-manual") == "bridge-manual"

    monkeypatch.setenv("AGENTCOMMERCE_FEISHU_KEYWORD_MARKER", "project-marker")
    monkeypatch.setenv("FEISHU_KEYWORD_MARKER", "fallback-marker")
    assert resolve_keyword_marker("") == "project-marker"
    assert resolve_keyword_marker(None) == "project-marker"

    monkeypatch.delenv("AGENTCOMMERCE_FEISHU_KEYWORD_MARKER", raising=False)
    assert resolve_keyword_marker("") == "fallback-marker"

    monkeypatch.delenv("FEISHU_KEYWORD_MARKER", raising=False)
    assert resolve_keyword_marker("") == "bridge"


def test_build_dedupe_key_is_stable() -> None:
    data = {
        "request_id": "exec-req-001",
        "brief_id": "brief-001",
        "handoff_id": "handoff-001",
    }
    key = build_dedupe_key("artifacts/a.json", "review", "normal", data)
    assert key == "artifacts/a.json|review|normal|exec-req-001|brief-001|handoff-001"


def test_dedupe_suppress_within_window_then_allows_after_window() -> None:
    state = {"entries": {}}
    key = "k1"
    mark_notify_state(
        state,
        key,
        artifact_path="artifacts/a.json",
        level="review",
        mode="normal",
        status="sent",
        now_ts=100.0,
    )
    assert should_suppress_send(state, key, dedupe_window_sec=60, now_ts=120.0) is True
    assert should_suppress_send(state, key, dedupe_window_sec=60, now_ts=170.0) is False
