# Incremental Governance Event Log v0.1（T5）

## 目标
在不替换现有 full scan metrics 的前提下，新增单进程文件级增量治理事件日志，支持：
- append-only 事件沉淀
- 去重与安全降级
- 增量 snapshot 统计

## 事件 Schema
统一字段：
- event_id
- event_type
- occurred_at
- request_id
- publish_id
- workspace_id
- project_id
- owner_id
- source_module
- source_artifact
- status
- payload_summary
- dedupe_key

## 去重规则
优先级：
1. 主键：`event_id`
2. 兜底：`event_type + source_artifact + status + timestamp_bucket`

实现方式：
- append log: `artifacts/governance_events.log`（JSONL）
- dedupe index: `artifacts/governance_events_dedupe_index.json`
- dedupe index 损坏时：重建并给 warning，不中断主流程

## 首批接入写入点
- scope validation result（router observe 阶段）
- router scope observe result
- policy publish result（applied / rejected / rolled_back）

所有接入均为附加记录，不改变原流程决策。

## Snapshot 逻辑
增量 snapshot 输出：
- scope_validation
- router_scope_observe
- policy_publish
- by_scope 聚合（workspace/project/owner）

当 event log 缺失或为空且允许 fallback：
- 返回 `source=full_scan_fallback`
- 调用现有 full scan metrics 结果作为兼容摘要

## 与现有 full scan metrics 的关系
- 本模块是增强层，不替代 full scan
- 可并行运行，用于后续 T6 周期快照作业

## 当前 non-goals
- 不做分布式一致性
- 不做多进程并发锁
- 不改 router 主决策
- 不改 publish FSM 语义
- 不做 UI
