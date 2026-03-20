# AgentCommerce Mode And Permission Playbook v1

## 1. Mode Decision Rules（优先级从高到低）

1. `owner_action`
   - 命中 confirm 信号：`apply_suggested_transition` / `confirm_transition`
   - 或动作关键词出现在 `feishu_action_protocol` / `owner_action` source
2. `workflow_request`
   - 命中执行请求关键词：`请开始执行` / `运行测试` / `execute` 等
   - 或命中 workflow action 关键词（`dispatch` / `approved` / `needs_fix` / `reject`）
3. `system_control`
   - 命中权限/模式声明语句：`允许修改并执行本地测试`、`仅允许读`、`mode:...`
4. `chat`
   - 无明确控制信号时的默认回退

路由结果字段会落盘：

- `detected_mode`
- `detection_reason`
- `confidence`
- `rule_hit`
- `response_profile`（`chat_conversation` / `workflow_control`）
- `artifact_visibility`（`owner_visible` / `internal_audit`）

## 2. How Router Avoids Misrouting

1. 普通聊天误入 workflow 的保护：
   - 只有命中明确关键词才进入 `workflow_request`
   - 否则维持 `chat` fallback
2. 明确执行指令被当闲聊的保护：
   - 命中 `workflow_request` 时，不再直接当 idle chat
   - 返回 `route_type=workflow_request` + `result_status=needs_owner_action_protocol`

## 3. Permission Levels

1. `read_only`
2. `safe_write`
3. `local_execution`
4. `external_network`
5. `destructive_action`

`destructive_action` 默认禁止，除非用户显式授权。

典型 destructive 示例：

1. `git reset --hard`
2. 删除大量文件
3. 覆盖关键配置
4. 修改系统级配置
5. 执行不可逆命令

## 4. Permission Source Rules

1. `prompt_explicit_grant`
   - 当前消息中明确授权
2. `session_level_grant`
   - 会话级预授权（若上游提供）
3. `default_read_only`
   - 未授权时默认只读

当权限不足时落盘字段：

- `requested_permission_level`
- `granted_permission_level`
- `permission_source`
- `confirmation_required`
- `missing_permission_reason`
- `recommended_grant_phrase`

## 5. 建议授权短语模板

1. 仅允许读：`仅允许读，请先分析`
2. 允许改文件不执行：`允许修改仓库文件但不要运行`
3. 允许修改并执行本地测试：`允许修改并执行本地测试`
4. 允许联网：`允许访问联网能力`
5. 禁止 destructive：`禁止 destructive 操作`

## 6. Evidence Artifacts

1. `artifacts/council_feishu_message_route_result.json`
   - 查看 mode + permission 判定与原因
2. `artifacts/council_feishu_chat_bridge_result.json`
   - 查看聊天链路权限上下文与执行结果
3. `artifacts/council_feishu_loop_demo_summary.json`
   - 查看 owner-facing summary（task/outcome/risk/next action/evidence）
