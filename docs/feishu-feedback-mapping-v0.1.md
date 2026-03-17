# Feishu Feedback Mapping Adapter v0.1

## 1. Positioning
`feishu_feedback_mapping_adapter` 是翻译器，不是放行器。

职责：
1. 解析飞书消息
2. 结构化映射为 `owner_feedback`
3. 生成 `suggested_transition_request`
4. 输出 `mapping_confidence / ambiguity_flags / ignored_reason`

非职责：
1. 不直接修改 artifact 状态
2. 不赋予执行授权
3. 不替代 state machine validator

## 2. Input Fields
最小输入上下文：
1. `source`
2. `message_id`
3. `chat_id`
4. `sender_id`
5. `sender_name`
6. `text`
7. `current_stage`
8. `current_artifact_id`
9. `current_artifact_type`
10. `current_artifact_status`
11. `current_request_id`
12. `current_brief_id`
13. `current_handoff_id`

## 3. Output Fields
输出结构 `FeedbackMappingResult` 包含：
1. `is_mapped`
2. `mapping_type` (`action_keyword/natural_language/ignored`)
3. `owner_feedback`
4. `suggested_transition_request`
5. `target_artifact_id`
6. `target_section`
7. `feedback_type`
8. `requested_change`
9. `severity`
10. `confidence`
11. `ambiguity_flags`
12. `required_context_missing`
13. `ignored_reason`
14. `suggested_next_action`
15. 关联与审计字段（message/sender/correlated ids/timestamp）

## 4. Feedback Type Mapping Table
动作词映射：
1. `needs_fix` -> `needs_fix`
2. `revision_request` -> `revision_request`
3. `rejected` / `reject` -> `reject`
4. `approved` -> `approval_note`
5. `hold` -> `comment`
6. `dispatch` -> `comment`（Council 映射中标记 ignored）

自然语言映射（v0.1 规则）：
1. 风险不足类 -> `needs_fix`
2. 范围过宽类 -> `needs_fix`
3. 执行边界/receipt/readiness 缺失 -> `needs_fix`
4. “重新提交给我审核” -> `revision_request`
5. “只是注释/不代表批准” -> `comment`

## 5. Section Alias Table
1. `scope`: `scope/范围/太宽`
2. `steps`: `steps/步骤/流程`
3. `risk`: `risk/风险/风险分析`
4. `review`: `review/审查/评审`
5. `decision_rationale`: `决策依据/理由`
6. `execution_constraints`: `执行边界/执行约束`
7. `no_go_zones`: `禁区/不要做`
8. `receipts`: `receipt/receipts/回执`
9. `readiness`: `readiness/不能执行/可执行`

若命中多个 section 或未命中，返回 `ambiguity_flags`，避免激进猜测。

## 6. Transition Suggestion Rules (v0.1)
1. `needs_fix/revision_request` -> 建议 `needs_fix`（或按“重新提交审核”语义建议 `resubmitted/ready_for_owner_review`）
2. `reject` -> 在 `ready_for_owner_review` 且 owner/bridge 语境下建议 `owner_rejected`，否则保守建议 `needs_fix`
3. `approved` -> 仅当 `ready_for_owner_review + owner/bridge 协议语境` 才建议 `owner_approved`
4. `dispatch/hold` -> Council 映射中不建议状态迁移（ignored/comment）

## 7. Governance Constraints
1. chat lane 普通自然语言不能直接等价 `owner_approved`
2. adapter 只输出建议，最终由 `council_artifact_state_machine.validate_transition` 判定
3. 上下文缺失时返回 `required_context_missing`
4. 模糊输入优先保守映射（comment 或 needs_fix + ambiguity）

## 8. Audit Artifact
默认输出：
`artifacts/council_feishu_feedback_mapping_result.json`

至少包含：
1. `message_id/sender_id/text`
2. `mapping_type`
3. `owner_feedback`
4. `suggested_transition_request`
5. `confidence/ambiguity_flags/ignored_reason`
6. `correlated_artifact_id/correlated_request_id`
7. `timestamp`

## 9. Integration Chain
串联方式：
1. `feishu_feedback_mapping_adapter.map_feishu_feedback(...)` 生成建议
2. 若存在 `suggested_transition_request`，调用 `validate_transition(...)`
3. 仅在状态机返回合法后，进入后续人工/流程动作

这保证了：
1. mapping 与 governance 解耦
2. 任何误判都可被状态机阻断

## 10. v0.1 Conservative Boundaries
已完成：
1. 规则表 + 关键词 + section alias
2. 模糊输入保护
3. 与状态机可消费联调

后续可升级：
1. 更强语义解析（混合规则+模型）
2. 多语言同义词扩展
3. 历史轮次上下文增强
