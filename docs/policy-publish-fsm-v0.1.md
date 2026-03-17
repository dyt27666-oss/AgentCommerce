# Policy Publish FSM v0.1（T3）

## 目标
将 alias version 切换从单点函数升级为 artifact-first、可审计、可回滚的最小发布状态机。

## 状态定义与迁移
状态：
- proposed
- under_review
- confirmed
- applied
- rejected
- rolled_back

允许迁移：
- proposed -> under_review / confirmed / rejected
- under_review -> confirmed / rejected
- confirmed -> applied / rejected
- applied -> rolled_back

阻断规则：
- proposed 不能直接 applied
- rejected 后不能 applied
- rolled_back 只能从 applied 进入
- 非法迁移返回结构化错误 `transition_errors`

## Artifact 列表
- `policy_publish_request.json`
- `policy_publish_review.json`
- `policy_publish_result.json`
- `policy_change_audit_pack.json`

每个 artifact 均包含：
- schema_version
- publish_id
- requested_by
- approver（适用时）
- target_scope
- change_set
- status
- timestamp

apply/rollback 额外包含：
- before / after（active_alias_version）
- changed_config_path

## 与 Phase 6.4 配置中心关系
- apply 阶段复用 `set_active_alias_version(...)`（dry_run 校验 + default scope 应用）
- owner/workspace/project scope 通过 override 文件落地 active_version
- rollback 复用同一写入路径，切回 `active_alias_version_from`

## 当前 non-goals
- 不接 UI
- 不做多进程并发控制
- 不扩 execution / apply / dispatch 权限
- 不接 router 决策流程
- impact_estimate 当前为最小占位（workspace/project）
