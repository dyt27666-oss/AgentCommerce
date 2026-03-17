# AgentCommerce v1

AgentCommerce 是一个以飞书为控制台、以 Council 为策略层、以 Codex/CLI 为执行层、以 Artifact 为治理核心的人类在环（HITL）AI 协作操作系统。

## 项目简介

本项目当前聚焦“治理型协作”而不是“通用聊天助手”：

- 把任务拆分为 `Chat / Council / Execution` 三条 lane。
- 用统一 artifact 作为状态、审批、执行和复盘的唯一可信载体。
- 在 owner 明确确认下推进状态迁移和执行触发。
- 通过 event log + snapshot 指标实现可观测、可审计、可恢复。

## 为什么不是普通 Agent Demo

普通 demo 往往只有“输入 -> 大模型 -> 输出”。AgentCommerce 的核心差异是：

1. `HITL`：关键动作必须 owner 明确确认。
2. `Artifact-first`：关键行为都落地结构化产物，而非只看 stdout。
3. `Governance over automation`：优先可监督、可追踪、可回放。
4. `Gate-based execution`：批准不等于执行，执行必须经过独立 gate。

## 系统架构总览

```text
Human Owner (Feishu)
  -> Feishu Control Layer
  -> Bridge Governance Layer
      -> Chat Lane
      -> Council Lane
      -> Execution Lane
  -> Artifact & Audit Layer
  -> Governance Event Log & Snapshot Metrics
  -> Runtime Failure Recovery Layer
```

关键实现目录：

- `tools/council_bridge/feishu_message_router.py`
- `tools/council_bridge/council_artifact_schema.py`
- `tools/council_bridge/council_artifact_state_machine.py`
- `tools/council_bridge/policy_publish_fsm.py`
- `tools/council_bridge/governance_event_log.py`
- `tools/council_bridge/governance_metrics_snapshot_job.py`
- `tools/council_bridge/runtime_failure_event_normalizer.py`
- `tools/council_bridge/runtime_recovery_attempt_runner.py`
- `tools/council_bridge/runtime_publish_reconcile_hook.py`
- `tools/council_bridge/runtime_event_log_degradation_recovery.py`

## 核心流程（Feishu -> Council -> Owner -> Execution/Audit）

```text
Owner 在 Feishu 发起任务
  -> Router 进入 Council 路径（可 observe）
  -> Council 生成/修订 artifact
  -> Owner 反馈与确认（needs_fix/revise/approve）
  -> 状态机校验 + owner-confirmed apply
  -> handoff gate 校验
  -> owner-confirmed execution dispatch
  -> execution receipt + audit artifacts
  -> event log + snapshot 指标
```

## Governance 与 Runtime Recovery 能力

### 治理能力（已实现）

- Council 统一 schema（plan/risk/review/decision/handoff）
- 状态迁移校验器（最小合法迁移 + 上下文约束）
- Feishu feedback mapping（保守映射）
- owner-confirmed apply transition
- execution handoff gate / dispatch protocol
- policy publish FSM + alias version gate

### 运行时恢复能力（已实现）

- runtime failure 标准化
- recovery attempt（有限 retry / ignore / manual_required）
- publish failure reconcile hook（只读对账）
- event log degradation queue + replay
- recovery metrics extension（v0.2 snapshot）

## 核心原则

- `Artifact-first`
- `Human-in-the-loop`
- `Lane boundary`（Chat 不等于审批，Council 不直接执行）
- `Gate & policy enforcement`
- `Auditability`

## 当前完成状态

### Phase 6.5（P1）

- T1 Scope Validator Core：完成
- T2 Router Observe Integration：完成
- T3 Policy Publish FSM：完成
- T4 Alias Version Gate：完成
- T5 Incremental Governance Event Log：完成
- T6 Metrics Snapshot Job：完成

### Phase 7.1

- A Failure Event Normalizer：完成
- B Recovery Attempt Runner：完成
- C Publish Failure Reconcile Hook：完成
- D Event Log Degradation Recovery：完成
- E Recovery Metrics Extension：完成

最新回归：`py -m pytest -q` 通过（331 tests）。

## 文档入口

- [文档导航](docs/index.md)
- [Architecture v1](docs/architecture-v1.md)
- [Final Delivery Report v1](docs/final-delivery-report-v1.md)

## 后续 Roadmap（Phase 7+）

1. Phase 7.2：运行时治理深化（恢复策略编排、证据链收敛、操作手册）。
2. Phase 8：平台化增强（版本治理、跨项目策略包、可展示层与对外交付标准化）。

## 快速开始

```powershell
py -m pip install -r requirements.txt
py -m pytest -q
```

如需查看治理/恢复样例，请参阅 `docs/*_samples_v0.1/` 与 recovery snapshot 样例。
