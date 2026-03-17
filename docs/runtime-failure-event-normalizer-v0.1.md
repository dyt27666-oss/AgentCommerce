# Runtime Failure Event Normalizer v0.1

## 目标
将运行时异常和失败状态统一标准化为 `runtime_failure_event` artifact，并写入现有 `governance_event_log`，保证失败可审计。

## Schema
最小结构：
- `artifact_type=runtime_failure_event`
- `schema_version=runtime.failure.v0.1`
- `failure_id`
- `related_request_id`
- `publish_id`
- `source_module`
- `failure_type`
- `failure_stage`
- `detected_at`
- `recovery_action`
- `recovery_status=pending`
- `operator`
- `audit_trace.{exception_type, exception_message, stack_hint}`

## Failure Type Mapping
- router parse error -> `ingress_router_failure`
- normalization error -> `normalization_failure`
- artifact write error -> `artifact_write_failure`
- publish apply error -> `publish_apply_failure`
- rollback error -> `publish_rollback_failure`
- event log ingest error -> `event_log_write_failure`
- snapshot job error -> `snapshot_job_failure`
- unknown -> `unknown_runtime_failure`

## Stage Mapping
- `ingress`
- `normalization`
- `artifact_write`
- `publish_apply`
- `publish_rollback`
- `event_ingest`
- `snapshot_job`
- `runtime_unknown`

## Event Log 集成
`emit_runtime_failure_event(...)`：
1. `normalize_failure_event(...)`
2. 构造 `governance_event_log` 事件（`event_type=runtime_failure_event`）
3. 调用 `ingest_governance_event(...)`
4. 若 ingest invalid 或抛异常，fallback 写入 `artifacts/runtime_failure_fallback.log`
5. 不向上抛出未处理异常

## Non-goals
- 不实现 recovery runner
- 不实现 retry/reconcile 执行逻辑
- 不修改 router / publish FSM / validator / execution gate 行为
- 不引入分布式机制
