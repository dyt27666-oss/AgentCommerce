# Scope Validator Router Observe Integration v0.1

本轮仅做 observe-mode 接入：
- 在 router ingress parse 后、normalization 前执行 scope validation
- 仅记录 `scope_validation` 字段并输出 warning 日志
- 不改变任何 route decision

新增 router result 字段：
```json
"scope_validation": {
  "mode": "strict|lenient",
  "is_valid": true,
  "errors": [],
  "warnings": [],
  "degraded_fields": [],
  "normalized_scope": {
    "workspace_id": "...",
    "project_id": "...",
    "policy_scope": "...",
    "alias_scope": "..."
  },
  "action": "blocked|degraded_continue|pass"
}
```

注意：
- `action=blocked` 在本轮不会阻断 router
- execution/apply/dispatch/state-machine 行为均不变
