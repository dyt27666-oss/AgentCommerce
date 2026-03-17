# Example Flow v1（最典型端到端流程）

场景：owner 在 Feishu 反馈“风险分析不够”，系统完成 Council 修订建议、审计落地、失败可恢复与指标收敛。

1. owner 在 Feishu Control Layer 发送反馈消息。
2. `feishu_message_router.py` 接收 ingress payload，装配 request/artifact 上下文。
3. `scope_validator.py` 在 observe mode 输出 `scope_validation`（仅记录，不阻断路由）。
4. `owner_intent_normalization.py` 归一化意图，识别 `target_section=risk`、`requested_action=recheck`。
5. `feishu_feedback_mapping_adapter.py` 生成 `owner_feedback` 与 suggested transition（例如 `under_review -> needs_fix`）。
6. `council_artifact_state_machine.py` 执行 `validate_transition(...)`，返回合法性与原因；observe-only 阶段不自动 apply。
7. owner 发出明确确认信号后，`owner_confirmed_transition_apply.py` 执行 apply，更新 Council artifact 状态并写回执。
8. 若形成 handoff，`execution_handoff_gate.py` 校验 `owner_approval_status=approved`、`execution_readiness_status=ready` 与约束字段完整性。
9. 若收到明确 `dispatch_execution` 协议，`owner_confirmed_execution_dispatch.py` 才允许进入 Execution Layer，并由 `execution_dispatch_adapter.py` 调用现有执行入口。
10. 全流程关键结果写入 Artifact & Audit Layer，并通过 `governance_event_log.py` 记录事件。
11. `governance_metrics_snapshot_job.py` 聚合 scope/publish/recovery 指标，输出 `governance_metrics_snapshot`。
12. 若任一步失败，进入 Runtime Failure Recovery：`runtime_failure_event_normalizer.py` -> `runtime_recovery_attempt_runner.py` -> `runtime_publish_reconcile_hook.py` -> `runtime_event_log_degradation_recovery.py`，并将恢复结果继续回写 event log 与 snapshot。

约束结论：

- chat 普通文本不具审批或执行语义。
- handoff_ready 不等于自动执行。
- 失败不会静默吞掉，必须有 artifact/event 证据。
