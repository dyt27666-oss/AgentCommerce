# Council Feedback Shadow Mode v0.1

## 1. Integration Point
接入点：`tools/council_bridge/feishu_message_router.py` 的 `route_message(...)`。

当 `source_artifact` 被识别为 Council artifact 上下文时，路由进入：
`council_feedback_observer`。

## 2. Observe-Only Flow
消息流：
1. router 归一化消息 + 去重
2. 组装 Council 上下文
3. 调用 `map_feishu_feedback(...)`
4. 若有建议迁移，调用 `validate_transition(...)`
5. 写入 mapping / validation artifact
6. 返回可读摘要（仅建议）

保证：
1. 不调用 `apply_transition(...)`
2. 不修改当前 artifact `status`
3. 不触发 execution lane

## 3. Artifacts
1. `artifacts/council_feishu_feedback_mapping_result.json`
2. `artifacts/council_artifact_state_transition_result.json`（有建议迁移时）
3. `artifacts/council_feishu_message_route_result.json` 中补充：
   - `mapping_status`
   - `validation_status`
   - `suggested_transition_summary`
   - `observe_only`

## 4. Readable Summary
`route_result.result_info` 至少包含：
1. feedback 识别类型
2. target_section
3. 建议迁移
4. validation 结论
5. observe_only 提示（不会改状态）

## 5. Boundaries
1. chat lane 不具备批准语义
2. mapping adapter 只翻译不放行
3. 状态放行仍由 state machine 决定
