# AgentCommerce Docs Index

## Overview

- [README v1](../README.md)  
  GitHub 首页入口，包含项目定位、核心能力、边界与路线图。
- [Architecture v1](architecture-v1.md)  
  分层架构、控制流/数据流、Gate/FSM/Recovery 边界与实现映射。
- [Final Delivery Report v1](final-delivery-report-v1.md)  
  Phase 6.5 ~ 7.1 交付总表、测试证据、完成度与剩余缺口。
- [Example Flow v1](example-flow-v1.md)  
  最典型端到端流程（Feishu -> Governance -> Audit -> Recovery）。
- [Testing Playbook v1](testing-playbook-v1.md)  
  测试与展示阶段最小可执行方案（A/B/C 场景、落盘证据、验收清单）。
- [Git Operations Playbook v1](git-operations-playbook-v1.md)  
  稳定提交、tag 检查点、回滚恢复与演示前 Git 检查清单。
- [Mode And Permission Playbook v1](mode-and-permission-playbook-v1.md)  
  Chat/Workflow 模式判定、权限分级授权与确认策略。

## Governance

- [Scope Validator Core](scope-validator-core-v0.1.md)  
  scope 完整性校验规则（strict/lenient）。
- [Scope Validator Router Observe](scope-validator-router-observe-v0.1.md)  
  router observe-only 接入与结果字段。
- [Policy Publish FSM](policy-publish-fsm-v0.1.md)  
  alias version 发布状态机与审计产物。
- [Alias Version Gate](alias-version-gate-v0.1.md)  
  apply 前语义回归门禁与阻断规则。
- [Council Artifact Schema](council-artifact-schema-v0.1.md)  
  Council 统一 artifact schema 与 lineage 字段。
- [Council Artifact State Machine](council-artifact-state-machine-v0.1.md)  
  Council 状态迁移规则与门禁。

## Runtime Recovery

- [Runtime Failure Event Normalizer](runtime-failure-event-normalizer-v0.1.md)  
  runtime failure 标准化协议。
- [Runtime Recovery Attempt Runner](runtime-recovery-attempt-runner-v0.1.md)  
  最小 recovery action（retry/ignore/manual_required）。
- [Runtime Publish Reconcile Hook](runtime-publish-reconcile-hook-v0.1.md)  
  publish apply/rollback 半提交对账。
- [Runtime Event Log Degradation Recovery](runtime-event-log-degradation-recovery-v0.1.md)  
  event ingest 降级队列、replay 与审计闭环。

## Metrics / Observability

- [Incremental Governance Event Log](incremental-governance-event-log-v0.1.md)  
  统一治理事件 schema、去重与增量写入。
- [Governance Metrics Snapshot Job](governance-metrics-snapshot-job-v0.1.md)  
  周期快照任务与 fallback 汇总策略。
- [Recovery Metrics Extension](recovery-metrics-extension-v0.1.md)  
  恢复质量指标口径与 by_scope 聚合。

## Samples

- `docs/council_artifact_samples_v0.1/`：Council artifacts 与 owner feedback 样例。
- `docs/scope_validator_samples_v0.1/`：scope strict/lenient 校验结果样例。
- `docs/router_scope_validation_samples_v0.1/`：router observe scope 样例。
- `docs/policy_publish_samples_v0.1/`：publish request/result/audit pack 样例。
- `docs/governance_event_samples_v0.1/`：governance event 与 snapshot 样例。
- `docs/runtime_failure_samples_v0.1/`：runtime failure event 样例。
- `docs/runtime_recovery_samples_v0.1/`：recovery attempt 样例。
- `docs/runtime_reconcile_samples_v0.1/`：reconcile report 样例。
- `docs/runtime_event_log_degradation_samples_v0.1/`：degradation/replay 样例。

## Delivery / Roadmap

- [Final Delivery Report v1](final-delivery-report-v1.md)  
  当前交付收口状态与工程证据。
- [Roadmap](roadmap.md)  
  后续阶段演进方向（需结合当前实现边界阅读）。
