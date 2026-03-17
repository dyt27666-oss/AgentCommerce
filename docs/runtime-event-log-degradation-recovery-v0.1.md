# Runtime Event Log Degradation Recovery v0.1

## 目标
在 governance event ingest 失败时，提供标准化降级记录、队列化、有限补写(replay)与审计闭环。

## Degradation Artifact
`artifact_type=runtime_event_log_degradation`
- `schema_version=runtime.degradation.v0.1`
- `degradation_id`
- `related_failure_id / related_request_id / publish_id`
- `source_module`
- `original_event_type`
- `detected_at`
- `degradation_reason`
- `queue_status`
- `replay_status`
- `operator`
- `audit_trace`

## Queue 状态定义
- `queued`: 待补写
- `replayed`: 补写成功（包含 duplicate 视作成功）
- `replay_failed`: 本次补写失败，可继续重试
- `abandoned`: 达到最大补写次数后终止自动补写

## Replay 规则
- 仅处理 `queued/replay_failed`
- 默认 `max_replay_attempts=3`
- 成功条件：`ingest_status in {written, ignored_duplicate}`
- 失败条件：`invalid/exception/missing failed_event`
- 超过次数：`abandoned`

## Idempotency / Dedupe 原则
- queue 内通过 `degradation_id` 去重处理
- 已 `replayed/abandoned` 项不会重复补写
- `ignored_duplicate` 作为幂等成功

## 与 fallback log 的关系
- 原 fallback log 保留（兼容）
- degradation recovery 额外写队列与标准 artifact
- 若 degradation 模块本身失败，继续写 `runtime_event_log_degradation_fallback.log`

## Non-goals
- 不修改 governance_event_log 核心 schema
- 不实现分布式消息队列
- 不改变 router/publish FSM/validator/execution gate 主语义
- 不把该模块扩展为通用任务队列
