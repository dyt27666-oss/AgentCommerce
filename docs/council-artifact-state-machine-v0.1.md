# Council Artifact State Machine v0.1

## 1. Purpose
本文件定义 Council Lane 最小状态迁移规则与校验器（v0.1）。

目标：
1. 固化“哪些迁移合法”
2. 把 owner feedback / lineage / approval / handoff readiness 纳入校验
3. 为后续飞书输入映射提供稳定治理内核

不包含：
1. 自动编排器
2. 飞书反馈自动映射器

## 2. Status Set
统一状态集合：
1. `draft`
2. `under_review`
3. `needs_fix`
4. `revised`
5. `resubmitted`
6. `ready_for_owner_review`
7. `owner_rejected`
8. `owner_approved`
9. `handoff_ready`

## 3. Allowed Transition Table
最小合法流转：
1. `draft -> under_review`
2. `under_review -> needs_fix`
3. `under_review -> ready_for_owner_review`
4. `needs_fix -> revised`
5. `revised -> resubmitted`
6. `resubmitted -> ready_for_owner_review`
7. `ready_for_owner_review -> owner_rejected`
8. `ready_for_owner_review -> owner_approved`
9. `owner_approved -> handoff_ready`（仅 handoff 且满足 readiness）

其余迁移均视为非法。

## 4. Governance Rules
1. Council 迁移不能直接进入 execution lane。
2. Chat lane 不具备 `owner_approved/owner_rejected/handoff_ready` 语义。
3. `owner_approved` 不是执行授权，仍需 handoff readiness 满足。
4. `owner_rejected` 不能直接回到批准路径，必须新一轮修订。
5. `needs_fix -> revised` 与 `revised -> resubmitted` 必须有 lineage 支撑。
6. 非法迁移必须返回明确 `validation_errors`。

## 5. Context-Aware Validation
校验器不是只看 from/to，还会检查：
1. `artifact_type`
2. `owner_feedback` / `triggering_feedback_id`
3. `parent_artifact_id` / `derived_from_artifact_ids` / `triggering_artifact_id`
4. `lineage.revision_completed`
5. owner approval lane 限制（仅 owner/bridge）
6. handoff 执行门禁

## 6. Execution Gate Candidate
仅满足以下条件才标记 `execution_gate_candidate=true`：
1. 迁移目标为 `handoff_ready`
2. `artifact_type == handoff`
3. 迁移有效
4. `owner_approval_status == approved`
5. `execution_readiness_status == ready`

反例：
1. `owner_approved` 但 readiness 不是 `ready` -> `execution_gate_candidate=false`
2. 任何非法迁移 -> `execution_gate_candidate=false`

## 7. Core API
文件：`tools/council_bridge/council_artifact_state_machine.py`

主要结构：
1. `TransitionRequest`
2. `TransitionResult`
3. `validate_transition(artifact, request)`
4. `apply_transition(artifact, request)`（可选写回）
5. `write_transition_audit(result)`

默认审计输出：
`artifacts/council_artifact_state_transition_result.json`

## 8. Sample Files
目录：`docs/council_artifact_state_machine_samples_v0.1/`

包含：
1. 4 个合法迁移样例
2. 4 个非法迁移样例
3. 2 个 handoff 执行门禁样例

## 9. Test Coverage
文件：`tests/test_council_artifact_state_machine.py`

覆盖：
1. 合法迁移通过
2. 非法迁移阻断
3. owner feedback 影响合法性
4. lineage 缺失阻断 revised/resubmitted
5. handoff readiness 不足时不可 execution candidate
6. chat lane 不具备批准语义

## 10. v0.1 Boundaries
已完成：
1. 最小迁移规则
2. 上下文校验
3. 审计产物输出
4. execution gate 预埋判定

预留：
1. 飞书反馈自动映射到 `target_section/feedback_type`
2. 多 artifact 批量事务迁移
3. 更细粒度策略（按 artifact_type 的差异化状态图）
