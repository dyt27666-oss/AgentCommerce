# Runtime Recovery Attempt Runner v0.1

## 目标
在 `runtime_failure_event` 基础上，提供最小恢复尝试编排与审计记录能力：
- 生成 `runtime_recovery_attempt` artifact
- 写入 `governance_event_log`（`event_type=runtime_recovery_attempt`）
- event 写入失败时 fallback 到本地日志

## Recovery Action 规则
- 支持：`retry` / `ignore` / `manual_required`
- 本轮不执行真实 rollback
- `publish_apply_failure` 保守固定为 `manual_required`

## Retry Policy（v0.1）
- retryable:
  - `artifact_write_failure`
  - `event_log_write_failure`
  - `snapshot_job_failure`
  - 默认 `max_attempts=3`
- manual_required:
  - `ingress_router_failure`
  - `normalization_failure`
  - `publish_apply_failure`
  - `publish_rollback_failure`
  - `unknown_runtime_failure`（保守）
  - `max_attempts=0`

## Artifact Schema
最小字段：
- `artifact_type=runtime_recovery_attempt`
- `schema_version=runtime.recovery.v0.1`
- `failure_id`
- `related_request_id` / `publish_id`
- `source_module`
- `failure_type`
- `failure_stage`
- `detected_at`
- `recovery_action`
- `recovery_status`
- `operator`
- `attempt_no`
- `max_attempts`
- `idempotency_key`
- `attempt_result`
- `error_detail`
- `audit_trace`

## 与 Failure Normalizer 的关系
- Failure normalizer 负责标准化失败事件
- Attempt runner 读取 failure event 后做恢复动作判定与占位执行记录
- 两者共用 governance event log 与 fallback 思路

## Non-goals
- 不实现 reconcile
- 不实现真实 rollback executor
- 不修改 router / publish FSM / validator / execution gate
- 不引入分布式调度
