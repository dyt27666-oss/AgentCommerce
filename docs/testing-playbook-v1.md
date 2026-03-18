# AgentCommerce Testing Playbook v1（SOP）

本文件是“测试与展示阶段”可直接执行的操作手册。目标：跑完三类场景后，直接得到可验收、可演示的证据包。

## 1. 一键执行入口

```powershell
py tools/council_bridge/testing_playbook_v1_runner.py --run-id demo_v1
```

执行完成后，优先查看：

- `artifacts/testing_playbook_v1/<run_id>/demo_ready_report.md`
- `artifacts/testing_playbook_v1/<run_id>/demo_ready_summary.json`
- `artifacts/testing_playbook_v1/<run_id>/testing_playbook_summary.json`

## 2. 输出结构与证据约定

输出目录：`artifacts/testing_playbook_v1/<run_id>/`

关键文件：

1. `testing_playbook_summary.json`：完整原始结果
2. `demo_ready_summary.json`：演示/验收友好汇总
3. `demo_ready_report.md`：快速阅读报告
4. `governance_events.log`：事件证据
5. 每个场景目录的 `evidence_index.json`

场景目录：

- `scenario_a_normal_message/`
- `scenario_b_owner_feedback_publish/`
- `scenario_c_failure_recovery/`

## 3. 三个场景的输入与验收要点

### 3.1 场景 A：普通消息交互闭环

输入（mock）：

- `text="帮我总结当前状态，不触发执行"`
- `source="feishu_chat"`

期望路径：

- `feishu_message_router -> scope_validator(observe) -> chat lane queue`

验收标准：

- `route_type=chat`
- `result_status=queued`
- 出现 `scope_validation_result` / `router_scope_observe_result` 事件

证据文件：

- `scenario_a_normal_message/route_result.json`
- `scenario_a_normal_message/evidence_index.json`

### 3.2 场景 B：Owner feedback / publish 流程闭环

输入（mock）：

1. `text="风险分析不够，请修改后再给我"`（observe）
2. `text="apply_suggested_transition"` + `source="feishu_action_protocol"`（confirm）
3. publish 目标：`owner.intent.alias.v0.2`

期望路径：

- `router -> mapping -> validator -> owner_confirmed_transition_apply`
- `policy_publish_fsm: proposed -> confirmed -> applied`

验收标准：

- `owner_apply_result.apply_status=applied`
- `policy_publish_result.status=applied`
- `policy_change_audit_pack.json` 存在

证据文件：

- `scenario_b_owner_feedback_publish/council_feedback/evidence_index.json`
- `scenario_b_owner_feedback_publish/publish_fsm/policy_publish_result.json`
- `scenario_b_owner_feedback_publish/evidence_index.json`

### 3.3 场景 C：failure -> recovery 闭环

输入（最小可控注入）：

- 注入 `OSError("simulated artifact write failure for testing playbook")`

期望路径：

- `runtime_failure_event_normalizer`
- `runtime_recovery_attempt_runner`
- `runtime_publish_reconcile_hook`
- `runtime_event_log_degradation_recovery`
- `governance_metrics_snapshot_job`

字段级验收（不是仅存在性）：

- `runtime_failure_event.failure_type == artifact_write_failure`
- `runtime_failure_event.recovery_status == pending`
- `runtime_recovery_attempt.recovery_action == retry`
- `runtime_recovery_attempt.attempt_result` 属于允许集合
- `runtime_reconcile_report.reconcile_status` 属于允许集合
- `runtime_event_log_degradation.queue_status` 属于允许集合
- snapshot 中：
  - `metrics.runtime_failure.total >= 1`
  - `metrics.runtime_recovery_attempt.total >= 1`
  - `metrics.recovery_quality` 为非空对象

证据文件：

- `scenario_c_failure_recovery/runtime_failure_event.json`
- `scenario_c_failure_recovery/runtime_recovery_attempt.json`
- `scenario_c_failure_recovery/runtime_reconcile_report.json`
- `scenario_c_failure_recovery/runtime_event_log_degradation.json`
- `scenario_c_failure_recovery/governance_metrics_snapshot.json`
- `scenario_c_failure_recovery/evidence_index.json`

## 4. 真实 Feishu 测试 SOP

### 4.1 前置条件清单

1. 已配置 webhook 环境变量之一：
   - `AGENTCOMMERCE_FEISHU_WEBHOOK_URL`
   - `FEISHU_WEBHOOK_URL`
2. 具备可发送测试消息的飞书群。
3. 本地可执行 Python 命令（`py`）。

### 4.2 低延迟常驻监听（推荐）

为避免手动轮询导致回复慢，先启动常驻 listener + worker：

```powershell
powershell -ExecutionPolicy Bypass -File tools/council_bridge/start_realtime_chat.ps1
```

停止常驻进程：

```powershell
powershell -ExecutionPolicy Bypass -File tools/council_bridge/stop_realtime_chat.ps1
```

日志目录：

- `artifacts/realtime/feishu_listener.stdout.log`
- `artifacts/realtime/feishu_listener.stderr.log`
- `artifacts/realtime/bridge_worker.stdout.log`
- `artifacts/realtime/bridge_worker.stderr.log`
- `artifacts/realtime/*.pid`

### 4.3 操作步骤

1. 准备源 artifact（可用现有）：
   - `artifacts/council_codex_dispatch_ready.json`
2. 发送到飞书（真实发送）：

```powershell
py tools/council_bridge/feishu_loop_demo.py --source-artifact artifacts/council_codex_dispatch_ready.json --send-mode send --owner-action needs_fix --owner-id owner_001
```

3. 在飞书发送测试消息（建议顺序）：
   1. `风险分析不够`
   2. `scope 太宽`
   3. `这个可以，重新提交给我审核`
   4. `apply_suggested_transition`（必须走 action protocol 语义来源）
4. 本地检查：
   - `artifacts/council_feishu_message_route_result.json`
   - `artifacts/council_feishu_feedback_mapping_result.json`
   - `artifacts/council_artifact_state_transition_result.json`
   - `artifacts/council_owner_confirmed_apply_result.json`

### 4.4 成功判定

- 能看到 mapping + validation + apply 回执
- apply 必须是 owner-confirmed，不是普通 chat 文本误触发

## 5. 无 Feishu 配置（mock / dry-run）SOP

```powershell
py tools/council_bridge/testing_playbook_v1_runner.py --run-id local_dry_run
```

检查顺序：

1. `demo_ready_report.md`
2. `demo_ready_summary.json`
3. 三个场景目录下 `evidence_index.json`

## 6. 5 分钟演示脚本（建议）

1. 运行命令：`py tools/council_bridge/testing_playbook_v1_runner.py --run-id demo_5min`
2. 打开 `demo_ready_report.md`，先展示 `overall_status`。
3. 展示场景 A 的 `route_result.json`（证明普通消息入 chat queue）。
4. 展示场景 B 的 `owner_apply_result.json` + `policy_publish_result.json`（证明 HITL + publish gate）。
5. 展示场景 C 的 `evidence_index.json`（字段级检查结果）+ `governance_metrics_snapshot.json`（recovery 指标）。
6. 最后展示 `governance_events.log`（事件链可审计）。

## 7. 快速回归命令（可选）

```powershell
py -m pytest -q tests/test_feishu_council_feedback_router.py tests/test_policy_publish_fsm.py tests/test_runtime_failure_event_normalizer.py tests/test_runtime_recovery_attempt_runner.py tests/test_runtime_publish_reconcile_hook.py tests/test_runtime_event_log_degradation_recovery.py tests/test_recovery_metrics_extension.py
```

## 8. 约束说明

1. 本 playbook 仅增强测试支架，不改治理核心逻辑。
2. 故障注入只用于测试目录，不污染主流程状态。
3. publish 流程使用临时 policy center，避免覆盖主配置。
