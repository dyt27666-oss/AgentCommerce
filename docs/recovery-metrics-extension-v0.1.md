# Recovery Metrics Extension v0.1

## 目标
将 runtime failure / recovery attempt / reconcile / degradation recovery 统一纳入 snapshot 指标，形成恢复质量最小观测体系。

## 新增指标定义

### runtime_failure
- `total`
- `by_failure_type`
- `by_failure_stage`

### runtime_recovery_attempt
- `total`
- `success`
- `failed_retryable`
- `failed_terminal`
- `ignored`
- `manual_required`

### runtime_reconcile
- `no_action_needed`
- `reconciled`
- `partially_reconciled`
- `manual_required`

### runtime_event_log_degradation
- `queued`
- `replayed`
- `replay_failed`
- `abandoned`

### recovery_quality
- `recovery_rate = success / runtime_recovery_attempt.total`
- `manual_intervention_rate = manual_required / runtime_recovery_attempt.total`
- `abandonment_rate = abandoned / (queued+replayed+replay_failed+abandoned)`
- `replay_success_rate = replayed / (replayed+replay_failed+abandoned)`
- 分母为 0 时统一返回 `0.0`

## by_scope 规则
- 按 `workspace_id/project_id/owner_id` 聚合 recovery 指标
- 缺失 scope 一律归入 `workspace:unknown|project:unknown|owner:unknown`
- 不做静默丢弃

## source_mode 兼容策略
- `incremental`: recovery 指标完全来自 event log
- `full_scan_fallback`: event log 空或不可用，使用 full scan + recovery artifact scan
- `mixed`: event log 有基础数据，但 recovery 事件不足，使用 artifact scan 补齐 recovery 维度
- 在 `job_stats.source_details` 与 `notes` 显式标注补齐来源和类别

## 与现有 snapshot 的关系
- 保留原有指标：`scope_validation` / `router_scope_observe` / `policy_publish`
- 扩展 schema 为 `governance.metrics.v0.2`
- 结构 additive，兼容旧消费方读取旧字段

## Non-goals
- 不修改治理主流程
- 不修改 event log 核心 schema
- 不实现 UI/dashboard 服务
- 不隐藏 recovery 数据不足，必须显式标注来源
