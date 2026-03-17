# Council Artifact Unified Schema v0.1

## 1. Scope
本文件定义 Council Lane 统一 artifact schema（v0.1），用于支撑：
1. 多轮打磨（round iteration）
2. owner feedback 结构化回链
3. Council -> Execution 标准化 handoff
4. 后续闭环状态机的最小数据基础

本阶段只定义对象与约束，不实现复杂状态机跳转。

## 2. Unified Top-Level Metadata
所有 Council artifacts 必须包含以下统一字段：

| field | required | notes |
|---|---|---|
| artifact_type | yes | `plan/risk/review/decision/handoff` |
| schema_version | yes | 固定 `council.artifact.v0.1` |
| artifact_id | yes | 全局唯一 id |
| request_id | yes | 一次 owner 任务主线 id |
| brief_id | yes | 对应 brief id |
| handoff_id | nullable | handoff 尚未生成时可为空 |
| council_round | yes | 从 1 开始递增 |
| parent_artifact_id | nullable | 直接父对象 |
| derived_from_artifact_ids | yes | 派生来源列表 |
| owner_id | yes | owner 标识 |
| chat_id | yes | 飞书会话/线程标识 |
| created_at | yes | ISO8601 |
| updated_at | yes | ISO8601 |
| produced_by_lane | yes | 固定 `council` |
| produced_by_role | nullable | 单角色产出时可填 |
| produced_by_roles | yes | 多角色可并列 |
| status | yes | 见状态字段定义 |
| summary | yes | 人类可读摘要 |
| constraints | yes | 约束列表 |
| assumptions | yes | 假设列表 |
| open_questions | yes | 未决问题 |
| next_action | yes | 下一动作建议 |
| owner_feedback | yes | owner 反馈数组（可空） |
| audit_trace | yes | 审计事件（可空） |
| lineage | yes | 血缘附加信息（可空对象） |

## 3. Five Artifact Types

### 3.1 Plan Artifact
用途：任务拆解、阶段计划、成功标准。

最小业务字段：
1. objective
2. scope
3. steps
4. dependencies
5. acceptance_criteria
6. proposed_execution_boundary
7. expected_outputs

### 3.2 Risk Artifact
用途：风险边界与越界约束。

最小业务字段：
1. risk_items
2. severity
3. likelihood
4. mitigation
5. blocked_actions
6. escalation_conditions

### 3.3 Review Artifact
用途：critic/reviewer 审查结果。

最小业务字段：
1. review_findings
2. missing_items
3. contradictions
4. unresolved_questions
5. recommended_revisions
6. review_verdict (`pass/revise/block`)

### 3.4 Decision Artifact
用途：Council 收敛结论（不等于 owner 最终批准）。

最小业务字段：
1. recommended_path
2. rejected_alternatives
3. decision_rationale
4. tradeoffs
5. confidence (0~1)
6. council_recommendation

### 3.5 Handoff Artifact
用途：Council -> Execution 正式交接对象。

最小业务字段：
1. approved_execution_brief
2. execution_scope
3. execution_constraints
4. no_go_zones
5. required_receipts
6. owner_approval_status (`pending/approved/needs_fix/rejected`)
7. execution_readiness_status (`not_ready/blocked/ready`)

## 4. Owner Feedback Mapping
owner 反馈结构字段：
1. feedback_id
2. feedback_source
3. feedback_text
4. feedback_type (`needs_fix/revision_request/reject/comment/approval_note`)
5. target_artifact_id
6. target_section
7. severity
8. requested_change
9. resolved_status
10. resolved_by_artifact_id

支持能力：
1. 指向具体不合格 section（`target_section`）
2. 指明希望修改方向（`requested_change`）
3. 回链到修订产物（`resolved_by_artifact_id`）
4. 供后续状态机判断修订完成度（`resolved_status`）

## 5. Status Field (State-Machine Ready, v0.1 Embedded)
统一可选状态：
1. draft
2. under_review
3. needs_fix
4. revised
5. resubmitted
6. ready_for_owner_review
7. owner_rejected
8. owner_approved
9. handoff_ready

说明：
1. 当前只做字段预埋与枚举约束。
2. 跳转规则将在后续闭环状态机实现中补齐。

## 6. Validation Model
代码入口：`tools/council_bridge/council_artifact_schema.py`

包含：
1. 五类 artifact dataclass
2. owner feedback dataclass
3. 顶层字段与枚举校验
4. `parse_council_artifact(...)` 统一解析入口

## 7. Sample Files
目录：`docs/council_artifact_samples_v0.1/`

包含：
1. `sample_plan.json`
2. `sample_risk.json`
3. `sample_review.json`
4. `sample_decision.json`
5. `sample_handoff.json`
6. `sample_owner_feedback.json`
7. `lineage_round_trip_example.json`

## 8. Governance Constraints
1. Council 只产出方案与交接对象，不直接执行。
2. Execution 只能接收 owner 审批后的 handoff。
3. Chat lane 仅解释/总结，不构成执行授权。
4. 关键状态必须可追溯到 artifact 与 audit_trace。

## 9. v0.1 Boundaries
已完成：
1. 统一元数据字段
2. 五类 artifact 最小结构
3. owner feedback 结构化映射
4. lineage/round-tripping 示例

预留到后续版本：
1. 完整状态机跳转规则
2. 飞书动作词到状态迁移的自动映射器
3. 与 execution gate 的强校验联动（如自动阻断）

## 10. External References (Engineering Patterns)
可借鉴思路（不是直接复制）：
1. AutoGen 多智能体会话结构：[microsoft/autogen](https://github.com/microsoft/autogen)
2. Open Interpreter 执行层边界思路：[OpenInterpreter/open-interpreter](https://github.com/OpenInterpreter/open-interpreter)
3. LangGraph 状态图与节点职责分离：[langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)

`minister` 的“飞书 AI 服务架构”仓库名在公开检索中未定位到唯一可信目标，当前记为：无确切信息。
