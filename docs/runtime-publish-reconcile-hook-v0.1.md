# Runtime Publish Reconcile Hook v0.1

## 目标
针对 policy publish apply/rollback 失败与半提交，执行只读对账并输出 `runtime_reconcile_report`，不自动修复配置。

## 对账范围（v0.1）
- apply 失败但 config 已部分写入
- rollback 失败且 before/after 与 config 不一致
- artifact 存在但 config 状态不一致
- config 已变化但缺 result/audit artifact
- publish result=applied 但 active version 未生效

对比字段最小集合：
- `change_set.active_alias_version_from`
- `change_set.active_alias_version_to`
- artifact `before/after.active_alias_version`
- config center 当前 `active_alias_version`

## reconcile_status 定义
- `reconciled`
- `partially_reconciled`
- `manual_required`
- `no_action_needed`

## recommended_action 规则
- `backfill_artifact`：配置状态可解释但缺工件
- `verify_config`：结果与当前 active version 不一致
- `manual_rollback_check`：rollback 结果与 active version 不一致
- `manual_publish_review`：半提交或关键信息不足
- `no_action`：状态一致且工件完整

## 与现有模块关系
- 读取：publish request/result/audit artifact（如存在）
- 读取：`policy_config_center` 当前 active alias version
- 可关联：failure_id / recovery 上下文（可选）
- 不修改 publish FSM 状态迁移，不改变主流程语义

## Non-goals
- 不执行自动修复
- 不执行自动 rollback
- 不实现分布式 reconcile
- 不修改 router/validator/execution gate
