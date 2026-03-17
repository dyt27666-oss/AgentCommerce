# Phase 5 Minimal Architecture (v0.1)

## 1. Scope
Phase 5 目标是建立 `Council -> Execution` 的受控交接门禁，不扩展 Council 讨论本身。

当前链路：
1. owner/council 产出 `handoff` artifact
2. 明确 execution trigger（协议信号）
3. execution handoff gate 校验
4. 生成标准化 execution brief
5. observe-only 输出摘要与审计

注意：
1. 本阶段不自动执行 execution lane
2. `handoff_ready` 仅表示可交接，不表示自动执行

## 2. Execution Handoff Gate Rules
必须同时满足：
1. `artifact_type == handoff`
2. `status == handoff_ready`
3. `owner_approval_status == approved`
4. `execution_readiness_status == ready`
5. `current_stage in {owner_review, execution_gate}`
6. `execution_constraints/no_go_zones/required_receipts` 非空
7. 明确 execution trigger 且信号源合法（owner/bridge protocol）

## 3. Execution Trigger Protocol
允许关键词：
1. `confirm_execution_dispatch`
2. `dispatch_execution`

约束：
1. 仅 `feishu_action_protocol/owner_action/bridge` 源可触发
2. chat 普通文本即使命中关键词也会被阻断

## 4. Handoff -> Execution Brief Schema
标准 brief（`execution.brief.v0.1`）字段：
1. `objective`
2. `execution_scope`
3. `execution_constraints`
4. `no_go_zones`
5. `expected_outputs`
6. `required_receipts`
7. `risk_notes`
8. `correlated_request_id`
9. `correlated_brief_id`
10. `correlated_handoff_id`

## 5. Execution Receipt v0.1 (Schema)
最小回执结构：
1. `execution_id`
2. `source_handoff_id`
3. `before_execution_state`
4. `execution_status`
5. `executed_actions_summary`
6. `changed_files` / `touched_resources`
7. `risk_flags`
8. `receipt_status`
9. `next_action`
10. `timestamp`

## 6. Observe-Only Demo Output
本阶段 demo 只做：
1. gate 判定
2. execution brief 产出
3. human-readable summary

不会做：
1. execution dispatch
2. 自动改 execution runtime 状态
