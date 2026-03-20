from __future__ import annotations

import json
from pathlib import Path

from tools.council_bridge import feishu_message_router as router_mod
from tools.council_bridge.bridge_worker import run_worker_once
from tools.council_bridge.execution_task_queue import DEFAULT_DB_PATH, fetch_next_pending_task
from tools.council_bridge.feishu_action_reconciler import reconcile_once
from tools.council_bridge.feishu_websocket_ingress import run_websocket_ingress_stub


def _runner_recorder(calls: list[list[str]]):
    def _run(command: list[str]):
        calls.append(command)
        return "success", "ok"

    return _run


def _payload(*, text: str, message_id: str = "m1", source: str = "webhook", chat_id: str = "oc_test") -> dict:
    return {
        "source": source,
        "event_id": f"ev-{message_id}" if source == "webhook" else "",
        "message_id": message_id,
        "chat_id": chat_id,
        "sender_id": "ou_test",
        "sender_name": "tester",
        "text": text,
        "create_time": "1711111111",
    }


def test_webhook_dispatch_routes_continue_once(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    result = router_mod.route_message(
        _payload(text="dispatch", message_id="m_dispatch"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        stage="dispatch_ready",
        check_completion_once=True,
        build_receipt_skeleton=True,
        runner=_runner_recorder(calls),
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert result["route_type"] == "action"
    assert result["result_status"] == "success"
    assert result["routed_entrypoint"] == "feishu_continue_once"
    assert len(calls) == 1


def test_webhook_approved_routes_final_review_once_in_review_ready(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    result = router_mod.route_message(
        _payload(text="approved", message_id="m_approved"),
        source_artifact="artifacts/council_codex_execution_receipt_skeleton.json",
        stage="review_ready",
        runner=_runner_recorder(calls),
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert result["route_type"] == "action"
    assert result["result_status"] == "success"
    assert result["routed_entrypoint"] == "final_review_once"
    assert len(calls) == 1


def test_webhook_approved_ignored_in_dispatch_ready(tmp_path: Path) -> None:
    result = router_mod.route_message(
        _payload(text="approved", message_id="m_wrong_stage"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert result["route_type"] == "ignored"
    assert result["result_status"] == "ignored"
    assert "not valid for stage 'dispatch_ready'" in result["result_info"]


def test_free_text_enters_chat_lane_and_queues_task(tmp_path: Path) -> None:
    result = router_mod.route_message(
        _payload(text="请总结本轮风险", message_id="m_chat"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        stage="dispatch_ready",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert result["route_type"] == "chat"
    assert result["result_status"] == "queued"
    assert isinstance(result["task_id"], str) and result["task_id"].startswith("task-")


def test_duplicate_message_is_deduped_for_chat_lane(tmp_path: Path) -> None:
    first = router_mod.route_message(
        _payload(text="hello bridge", message_id="m_dup_chat"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route1.json",
        queue_db_path=tmp_path / "q.db",
    )
    second = router_mod.route_message(
        _payload(text="hello bridge", message_id="m_dup_chat"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route2.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert first["result_status"] == "queued"
    assert second["result_status"] == "deduped"
    assert second["already_processed"] is True


def test_webhook_and_polling_both_can_enter_chat_lane(tmp_path: Path) -> None:
    r1 = router_mod.route_message(
        _payload(text="free text from webhook", message_id="m_wh_1", source="webhook"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe1.json",
        route_result_path=tmp_path / "route1.json",
        queue_db_path=tmp_path / "q1.db",
    )
    r2 = router_mod.route_message(
        _payload(text="free text from polling", message_id="m_pl_1", source="polling"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe2.json",
        route_result_path=tmp_path / "route2.json",
        queue_db_path=tmp_path / "q2.db",
    )
    assert r1["route_type"] == "chat" and r1["result_status"] == "queued"
    assert r2["route_type"] == "chat" and r2["result_status"] == "queued"


def test_worker_consumes_chat_task_and_writes_result(tmp_path: Path, monkeypatch) -> None:
    queue_db = tmp_path / "q.db"
    router_mod.route_message(
        _payload(text="请解释当前卡点", message_id="m_worker_1"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=queue_db,
    )

    from tools.council_bridge import feishu_chat_bridge as chat_mod

    sent: dict[str, str] = {}
    monkeypatch.setattr(chat_mod, "CHAT_REQUEST_PATH", tmp_path / "chat_req.json")
    monkeypatch.setattr(chat_mod, "CHAT_RESULT_PATH", tmp_path / "chat_res.json")
    monkeypatch.setattr(
        chat_mod,
        "generate_chat_reply",
        lambda **kwargs: {
            "reply_text": "这是LLM回复",
            "response_source": "llm",
            "llm_provider": "silra_compatible",
            "llm_model": "glm-4.7",
            "llm_error": "",
        },
    )
    monkeypatch.setattr(
        chat_mod,
        "send_text",
        lambda **kwargs: sent.update({"text": str(kwargs.get("text") or "")}) or {"code": 0, "msg": "ok"},
    )

    from tools.council_bridge import bridge_worker as worker_mod

    monkeypatch.setattr(worker_mod, "WORKER_RESULT_PATH", tmp_path / "worker_res.json")
    result = run_worker_once(db_path=queue_db)
    assert result["execution_status"] == "completed"
    assert (tmp_path / "chat_res.json").exists()
    chat_res = json.loads((tmp_path / "chat_res.json").read_text(encoding="utf-8"))
    assert chat_res["reply_status"] == "sent"
    assert chat_res["response_source"] == "llm"
    assert chat_res["llm_model"] == "glm-4.7"
    assert chat_res["response_profile"] == "chat_conversation"
    assert chat_res["artifact_visibility"] == "owner_visible"
    assert sent.get("text", "") == "这是LLM回复"


def test_worker_reply_failure_writes_error_artifact(tmp_path: Path, monkeypatch) -> None:
    queue_db = tmp_path / "q.db"
    router_mod.route_message(
        _payload(text="失败路径测试", message_id="m_worker_fail"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=queue_db,
    )

    from tools.council_bridge import feishu_chat_bridge as chat_mod

    monkeypatch.setattr(chat_mod, "CHAT_REQUEST_PATH", tmp_path / "chat_req.json")
    monkeypatch.setattr(chat_mod, "CHAT_RESULT_PATH", tmp_path / "chat_res.json")
    monkeypatch.setattr(chat_mod, "generate_chat_reply", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("llm_down")))
    monkeypatch.setattr(chat_mod, "send_text", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("send_failed")))

    from tools.council_bridge import bridge_worker as worker_mod

    monkeypatch.setattr(worker_mod, "WORKER_RESULT_PATH", tmp_path / "worker_res.json")
    result = run_worker_once(db_path=queue_db)
    assert result["execution_status"] == "failed"
    chat_res = json.loads((tmp_path / "chat_res.json").read_text(encoding="utf-8"))
    assert chat_res["reply_status"] == "failed"
    assert "send_failed" in chat_res["error_message"]
    assert chat_res["response_source"] == "rule_fallback"
    assert "llm_down" in chat_res["llm_error"]


def test_group_config_can_block_chat_lane(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        router_mod,
        "resolve_runtime_config",
        lambda owner_id, chat_id: {
            "chat_lane_enabled": True,
            "chat_lane_require_mention": False,
            "chat_lane_only_groups": [],
            "chat_lane_blocked_groups": ["oc_blocked"],
        },
    )
    result = router_mod.route_message(
        _payload(text="free text", message_id="m_block", chat_id="oc_blocked"),
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        dedupe_state_path=tmp_path / "dedupe.json",
        route_result_path=tmp_path / "route.json",
        queue_db_path=tmp_path / "q.db",
    )
    assert result["route_type"] == "ignored"
    assert "block-list" in result["ignored_reason"]


def test_reconciler_skips_already_processed_and_can_recover(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    runner = _runner_recorder(calls)
    messages = [
        {
            "message_id": "m3",
            "chat_id": "oc_test",
            "create_time": "1711111113",
            "body": {"content": '{"text":"dispatch"}'},
            "sender": {"sender_id": {"open_id": "ou_test"}},
        },
        {
            "message_id": "m2",
            "chat_id": "oc_test",
            "create_time": "1711111112",
            "body": {"content": '{"text":"dispatch"}'},
            "sender": {"sender_id": {"open_id": "ou_test"}},
        },
    ]
    # first pass: skip m3 because last_processed=m3
    new_last, results = reconcile_once(
        messages=messages,
        last_processed_message_id="m3",
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        action_stage="dispatch_ready",
        check_completion_once=False,
        build_receipt_skeleton=False,
        dedupe_state_path=str(tmp_path / "dedupe.json"),
        route_result_path=str(tmp_path / "route.json"),
        runner=runner,
    )
    assert new_last == "m3"
    assert results == []
    # recover pass: older last_processed -> m2 should be processed
    new_last2, results2 = reconcile_once(
        messages=messages,
        last_processed_message_id="m1",
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        action_stage="dispatch_ready",
        check_completion_once=False,
        build_receipt_skeleton=False,
        dedupe_state_path=str(tmp_path / "dedupe2.json"),
        route_result_path=str(tmp_path / "route2.json"),
        runner=runner,
    )
    assert new_last2 == "m3"
    assert any(r["route_type"] == "action" for r in results2)


def test_reconciler_parses_rich_text_content_for_mode_detection(tmp_path: Path) -> None:
    messages = [
        {
            "message_id": "m-rich-1",
            "chat_id": "oc_test",
            "create_time": "1711111114",
            "body": {
                "content": json.dumps(
                    {
                        "title": "",
                        "content": [
                            [
                                {"tag": "text", "text": "请开始执行并运行测试", "style": []},
                            ]
                        ],
                    },
                    ensure_ascii=False,
                )
            },
            "sender": {"sender_id": {"open_id": "ou_test"}},
        }
    ]
    _, results = reconcile_once(
        messages=messages,
        last_processed_message_id="",
        source_artifact="artifacts/council_codex_dispatch_ready.json",
        action_stage="dispatch_ready",
        check_completion_once=False,
        build_receipt_skeleton=False,
        dedupe_state_path=str(tmp_path / "dedupe.json"),
        route_result_path=str(tmp_path / "route.json"),
    )
    assert len(results) == 1
    assert results[0]["detected_mode"] == "workflow_request"
    assert results[0]["result_status"] == "needs_owner_action_protocol"


def test_websocket_ingress_stub_exists() -> None:
    result = run_websocket_ingress_stub()
    assert result["status"] == "stub"
