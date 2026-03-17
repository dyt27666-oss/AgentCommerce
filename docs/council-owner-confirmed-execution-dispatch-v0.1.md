# Owner-Confirmed Execution Dispatch v0.1

## 1. Scope
本模块实现 Phase 5 最后子任务：
在 owner 明确确认后，允许通过 gate 的 handoff 进入真实 execution dispatch。

## 2. Flow
`Feishu confirm -> trigger protocol -> gate re-check -> execution brief -> dispatch adapter -> receipt/audit`

## 3. Hard Rules
1. 仅明确 trigger（`confirm_execution_dispatch` / `dispatch_execution`）可触发
2. 仅 owner/bridge 协议源可触发
3. chat 普通文本无执行权限
4. council lane 本身不直接执行
5. handoff_ready 不是自动执行

## 4. Required Gate Conditions
1. `artifact_type == handoff`
2. `status == handoff_ready`
3. `owner_approval_status == approved`
4. `execution_readiness_status == ready`
5. `stage == execution_dispatch`
6. execution 关键字段完整
7. trigger 授权通过
8. brief 生成成功

## 5. Artifacts
1. `artifacts/council_execution_dispatch_result.json`
2. `artifacts/council_execution_runtime_status.json`
3. `artifacts/council_execution_receipt.json`

失败同样写入，禁止静默失败。

## 6. Execution Lane Integration
通过 `execution_dispatch_adapter.py` 薄适配到现有 `codex_dispatch_runner.run_dispatch`，
不创建平行假执行路径。
