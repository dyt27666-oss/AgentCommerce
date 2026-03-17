# Architecture v1（Phase 6.5 ~ 7.1）

## 目录

1. 文档范围
2. 分层架构
3. 关键流程
4. 关键 Artifact 类型
5. 关键 Event 类型
6. 核心状态机与门禁边界
7. Runtime Recovery 闭环
8. 可观测性与指标
9. 已实现 vs 后续方向

## 1. 文档范围

本文档描述 AgentCommerce 在 Phase 6.5 ~ 7.1 的可运行架构现状。

约束说明：

- 已实现：治理路由、artifact 状态、审批门禁、恢复与指标闭环。
- 未实现：复杂 UI、分布式调度、HA/多活、通用任务平台。

## 2. 分层架构

### 2.1 Feishu Control Layer

职责：接收 owner 输入、展示摘要、承载确认协议。

核心模块：

- `tools/council_bridge/feishu_message_router.py`
- `tools/council_bridge/feishu_feedback_mapping_adapter.py`

### 2.2 Bridge Governance Layer

职责：routing、dedupe、policy check、artifact logging、审计回传。

核心模块：

- `tools/council_bridge/scope_validator.py`
- `tools/council_bridge/policy_config_center.py`
- `tools/council_bridge/policy_publish_fsm.py`
- `tools/council_bridge/alias_semantic_regression_suite.py`

### 2.3 Council Multi-Agent Layer

职责：多角色策略协作（planner/researcher/critic/strategist/reviewer/reporter），只产出策略，不直接执行。

核心模块：

- `tools/council_bridge/council_role_contract.py`
- `tools/council_bridge/council_artifact_schema.py`
- `tools/council_bridge/council_artifact_state_machine.py`

### 2.4 Execution Layer

职责：在 owner-confirmed 前提下，根据 handoff brief 进入执行。

核心模块：

- `tools/council_bridge/execution_handoff_gate.py`
- `tools/council_bridge/owner_confirmed_execution_dispatch.py`
- `tools/council_bridge/execution_dispatch_adapter.py`

### 2.5 Artifact & Audit Layer

职责：所有关键动作写入结构化 artifact，支持复盘与审计。

典型产物目录：`artifacts/`、`docs/*samples*`。

### 2.6 Runtime Failure Recovery Layer

职责：故障标准化、恢复尝试、对账、降级补写、质量度量。

核心模块：

- `tools/council_bridge/runtime_failure_event_normalizer.py`
- `tools/council_bridge/runtime_recovery_attempt_runner.py`
- `tools/council_bridge/runtime_publish_reconcile_hook.py`
- `tools/council_bridge/runtime_event_log_degradation_recovery.py`

### 2.7 Governance Event Log / Snapshot Metrics

职责：统一事件落地与快照聚合。

核心模块：

- `tools/council_bridge/governance_event_log.py`
- `tools/council_bridge/governance_metrics_snapshot_job.py`

## 3. 关键流程

```text
Owner(Feishu)
  -> Router + Scope Validation (observe)
  -> Intent Normalization / Feedback Mapping
  -> Council Artifact Produce/Revise
  -> Owner Confirmed Apply (state transition)
  -> Handoff Gate
  -> Owner Confirmed Dispatch
  -> Execution Receipt
  -> Governance Event Log
  -> Metrics Snapshot
```

## 4. 关键 Artifact 类型

| Artifact Type | 作用 | 主要模块 | 状态/关键字段 |
|---|---|---|---|
| `plan/risk/review/decision/handoff` | Council 结构化策略产物 | `council_artifact_schema.py` | `artifact_type/status/lineage` |
| `policy_publish_request/review/result` | 发布流程治理 | `policy_publish_fsm.py` | `publish_id/status/change_set` |
| `policy_change_audit_pack` | 发布变更审计 | `policy_publish_fsm.py` | `before/after/impact_estimate` |
| `runtime_failure_event` | 失败标准化 | `runtime_failure_event_normalizer.py` | `failure_type/failure_stage` |
| `runtime_recovery_attempt` | 恢复尝试记录 | `runtime_recovery_attempt_runner.py` | `attempt_no/attempt_result` |
| `runtime_reconcile_report` | 发布失败对账报告 | `runtime_publish_reconcile_hook.py` | `reconcile_status/recommended_action` |
| `runtime_event_log_degradation` | event 降级记录 | `runtime_event_log_degradation_recovery.py` | `queue_status/replay_status` |
| `governance_metrics_snapshot` | 指标快照 | `governance_metrics_snapshot_job.py` | `source_mode/metrics/by_scope` |

## 5. 关键 Event 类型

| Event Type | 来源模块 | 用途 |
|---|---|---|
| `scope_validation_result` | router/scope validator | 记录 scope 校验观察结果 |
| `router_scope_observe_result` | router | 记录 observe 路径 |
| `policy_publish_result` | policy publish FSM | 记录发布结果 |
| `runtime_failure_event` | failure normalizer | 记录运行时失败 |
| `runtime_recovery_attempt` | recovery runner | 记录恢复动作结果 |
| `runtime_reconcile_report` | reconcile hook | 记录对账报告 |
| `runtime_event_log_degradation` | degradation recovery | 记录 ingest 降级与队列状态 |

## 6. 核心状态机与门禁边界

### 6.1 Council 状态机（已实现）

- 支持：`draft -> under_review -> needs_fix -> revised -> resubmitted -> ready_for_owner_review -> owner_approved/owner_rejected -> handoff_ready`。
- 关键约束：lineage 必须可追溯；chat lane 不具审批语义。

### 6.2 Apply / Dispatch 门禁（已实现）

- `owner_confirmed_transition_apply`：仅 owner 明确确认后 apply。
- `owner_confirmed_execution_dispatch`：handoff gate + owner dispatch 协议双重门禁。

### 6.3 Policy Publish FSM（已实现）

- `proposed -> under_review -> confirmed -> applied -> rolled_back`，含 reject 分支。
- `applied` 前置 alias regression gate。

### 6.4 边界声明

- 不存在“自动越权执行”。
- `handoff_ready` 不等于自动执行。
- recovery 组件不修改主状态机语义，只补审计与观测链。

## 7. Runtime failure -> recovery -> reconcile -> metrics 闭环

```text
runtime failure
  -> normalize(runtime_failure_event)
  -> recovery attempt(runtime_recovery_attempt)
  -> publish reconcile(runtime_reconcile_report)
  -> event ingest degradation(runtime_event_log_degradation)
  -> snapshot aggregation(recovery metrics v0.2)
```

闭环目标：

- 失败可归类
- 恢复可追踪
- 半提交可对账
- 降级可补写
- 质量可量化

## 8. 可观测性与指标

`governance.metrics.v0.2` 新增 recovery 指标：

- `runtime_failure.total/by_failure_type/by_failure_stage`
- `runtime_recovery_attempt.total/success/failed_retryable/failed_terminal/ignored/manual_required`
- `runtime_reconcile.no_action_needed/reconciled/partially_reconciled/manual_required`
- `runtime_event_log_degradation.queued/replayed/replay_failed/abandoned`
- `recovery_quality`：`recovery_rate/manual_intervention_rate/abandonment_rate/replay_success_rate`

source_mode：

- `incremental`
- `full_scan_fallback`
- `mixed`（显式标注补齐来源）

## 9. 已实现 vs 后续方向

### 已实现

- Council schema + state machine + owner confirmed apply
- execution handoff gate + dispatch protocol
- policy publish FSM + alias version gate
- runtime failure/recovery/reconcile/degradation recovery
- recovery metrics extension（v0.2 snapshot）

### 后续方向（未实现）

- UI 可视化治理面板
- 分布式调度与高可用
- 自动化修复策略编排（当前仅最小保守策略）
- 跨工作区策略包发布流水线
