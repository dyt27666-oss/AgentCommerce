# Scope Validator Core v0.1（T1）

## 目标
为平台层提供独立的作用域完整性与一致性校验能力。
本模块仅负责校验与归一化，不做授权、不做状态迁移、不做执行放行。

## 输入字段
- `mode`: `strict` / `lenient`
- `workspace_id`
- `project_id`
- `policy_scope`
- `alias_scope`

## strict / lenient 语义
- strict:
  - 关键字段缺失或非法直接 `blocked`
- lenient:
  - 缺失字段允许降级，输出 warning + `degraded_continue`
  - 非法 scope 可回退到 `default`

## 规则摘要
1. `workspace_id/project_id` 缺失、空字符串、`null/none/unknown`:
   - strict: error + blocked
   - lenient: warning + 归一化为 `unknown`
2. `policy_scope` 非法格式:
   - strict: blocked
   - lenient: warning + 回退 `default`
3. `alias_scope` 非法格式:
   - strict: blocked
   - lenient: warning + 回退为 `policy_scope`
4. `alias_scope != policy_scope`:
   - strict: blocked
   - lenient: warning + 将 `alias_scope` 对齐到 `policy_scope`

## 最小合法 scope chain 格式
- `default`
- `default>workspace:ws_x`
- `default>workspace:ws_x>project:pj_y`
- `default>owner:owner_x>group:g1`

约束：
- 必须以 `default` 开头
- 分段分隔符为 `>`
- 非 default 段格式：`{owner|group|workspace|project}:{id}`
- 不能有空段

## 输出结构
- `mode`
- `is_valid`
- `errors`
- `warnings`
- `degraded_fields`
- `normalized_scope`
- `action` (`blocked` / `degraded_continue` / `pass`)

## 当前 non-goals
- 不接入 router 主流程（T2）
- 不实现 publish workflow（T3）
- 不改 apply/dispatch gate 权限边界
- 不做多租户策略调度
