# Alias Version Gate v0.1

## 目标
在 Policy Publish FSM 的 `confirmed -> applied` 之间增加语义回归门禁，防止新 alias version 破坏关键 owner intent 解析语义。

## 回归用例 Schema
文件：`docs/alias_semantic_regression_cases.v0.1.json`

```json
{
  "suite_version": "alias.regression.cases.v0.1",
  "cases": [
    {
      "case_id": "role-rework-critic-001",
      "input": "请让 critic 重看",
      "expected": {
        "intent_type": "role_rework",
        "target_role": "critic",
        "requested_action": "recheck"
      },
      "priority": "P0"
    }
  ]
}
```

## Gate Decision 规则
- `P0` mismatch -> `fail` -> `block_publish`
- `P1` mismatch -> `warn` -> `allow_publish`
- `P2` mismatch -> `warn` -> `allow_publish`（log only in v0.1）

报告 artifact：`artifacts/alias_regression_report.json`

## 与 Publish FSM 的关系
- 接入点：`advance_publish_status(..., target_status=applied)`
- 顺序：
  1. 读取 publish request（当前应为 confirmed）
  2. 执行 regression gate（目标 alias version）
  3. 若 `gate_decision=block_publish`：返回 `status=blocked_by_regression`
  4. 否则继续原有 apply 流程

## Non-goals
- 不修改 normalization 核心算法
- 不修改 publish FSM 状态迁移集合
- 不修改 router / execution gate / state machine
- 不引入 UI
