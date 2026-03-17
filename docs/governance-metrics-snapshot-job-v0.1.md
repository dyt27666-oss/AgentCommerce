# Governance Metrics Snapshot Job v0.1

## 目标
将 T5 的增量治理事件日志（event log）汇总为可周期执行的快照 artifact，支持手动触发与未来 cron 调度。

## 输入与关系
- 增量输入：`artifacts/governance_events.log`（JSONL）
- 兼容回退：当 event log 为空或不存在时，回退到 full scan（`platform_governance_metrics`）
- 输出：`artifacts/governance_metrics_snapshot.json`

## Aggregation 规则

### 1) scope_validation
- `status=pass` -> `metrics.scope_validation.pass`
- `status=blocked` -> `metrics.scope_validation.blocked`
- `status=degraded_continue` -> `metrics.scope_validation.degraded`

### 2) router_scope_observe
- `event_type=router_scope_observe_result` -> `observed +1`
- `status in {degraded_continue, blocked}` -> `warnings +1`
- `status=blocked` -> `invalid_scope +1`

### 3) policy_publish
- `status=applied` -> `applied +1`
- `status=rejected` -> `rejected +1`
- `status=rolled_back` -> `rolled_back +1`

### 4) by_scope 聚合
组合 key：
`workspace:{workspace_id}|project:{project_id}|owner:{owner_id}`

## Dedupe/验证逻辑
- job 内二次去重校验（不改 event schema）：
  - 主键：`event_id`
  - 兜底：`dedupe_key`
- 缺关键字段的事件记为 invalid，跳过计数并记录 warning。

## CLI
```bash
py -m tools.council_bridge.governance_metrics_snapshot_job \
  --event-log artifacts/governance_events.log \
  --artifacts-dir artifacts \
  --output artifacts/governance_metrics_snapshot.json
```

可选参数：
- `--no-fallback`：关闭 full scan fallback。

## Non-goals
- 不修改 event schema。
- 不修改 router/publish/validator 行为。
- 不启用 strict scope enforcement。
- 不接 UI，不做分布式调度。
