# Council Owner-Confirmed Apply v0.1

## 1. Purpose
在 shadow mode 基础上，引入“owner 明确确认后再 apply”的最小能力。

原则：
1. 先 observe-only（mapping + validation）
2. 后 owner-confirmed apply
3. 不自动进入 execution lane

## 2. Confirm Signal Protocol
当前确认信号（文本关键词）：
1. `confirm_transition`
2. `apply_suggested_transition`

约束：
1. 仅 `owner/bridge` 协议来源可触发（如 `feishu_action_protocol`）
2. 普通 chat 文本命中关键词时仅 `ignored`

## 3. Apply Gate Conditions
必须同时满足：
1. mapping result: `is_mapped=true`
2. validation result: `is_valid=true`
3. 存在 `suggested_transition_request`
4. confirm lane 合法（owner/bridge）
5. stage 在 `council_review` 或 `owner_review`
6. target status 在允许集合内
7. 再次 `validate_transition(...)` 通过（防止状态漂移）

## 4. Apply Receipt Artifact
默认输出：`artifacts/council_owner_confirmed_apply_result.json`

核心字段：
1. `artifact_id/artifact_type`
2. `before_status/after_status`
3. `applied_transition`
4. `requested_by/confirmed_by/confirmed_by_lane`
5. `reason`
6. `mapping_artifact_id/validation_artifact_id`
7. `apply_status/apply_error`
8. `timestamp`
9. `observe_only_source`
10. `lineage_update`

失败也会落盘，不允许静默失败。

## 5. Router Integration
文件：`tools/council_bridge/feishu_message_router.py`

Council 路径行为：
1. 普通 feedback -> observe-only
2. 命中 confirm 协议 -> 调用 `owner_confirmed_transition_apply.apply_owner_confirmed_transition(...)`
3. route result 返回 apply 结果摘要

## 6. Boundaries
1. `handoff_ready` 仅表示治理可交接，不等于自动执行
2. 本阶段不触发 execution lane
3. chat lane 无 apply 授权语义
