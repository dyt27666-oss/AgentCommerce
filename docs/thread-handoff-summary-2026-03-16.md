# AgentCommerce 线程交接摘要（2026-03-16）

## 1. 当前定位与边界

- 项目核心仍是 **artifact-first / 半人工治理 / owner 拍板**。
- 主业务工作流骨干未改动：  
  `planner -> research -> crawler -> data_processing -> analysis -> strategy -> report`
- Bridge 线已进入 **v1.2 增量阶段**：在不做重编排的前提下，补齐飞书控制台入口与本地执行桥接。

## 2. 当前已可用能力（重点）

### 2.1 Action Lane（已稳定）

- `dispatch_ready + dispatch` 可自动触发本地续跑（`feishu_continue_once`）。
- `review_ready + approved` 可自动触发最终收口（`final_review_once`）。
- 支持动作词：`dispatch / hold / needs_fix / reject / approved / revision_request / rejected`（按阶段生效）。
- 阶段不匹配动作会被明确 `ignored`，并写审计工件。

### 2.2 Ingress 双入口（已落地）

- **Webhook 主入口**：`tools/council_bridge/feishu_event_webhook.py`
- **Polling 补偿入口**：`tools/council_bridge/feishu_action_reconciler.py`
- `feishu_action_listener.py` 现在是 reconciler 兼容封装，不再是唯一主入口。

### 2.3 去重与审计（已落地）

- 统一路由：`tools/council_bridge/feishu_message_router.py`
- 去重键优先级：`event_id -> message_id -> fallback组合键`
- 关键审计工件：
  - `artifacts/council_feishu_webhook_event.json`
  - `artifacts/council_feishu_message_route_result.json`
  - `artifacts/council_feishu_reconciler_result.json`
  - `artifacts/council_feishu_message_dedupe_state.json`

### 2.4 Chat Lane（v1.2 最小可用）

- 自由文本可进入 chat lane（不是动作词时）。
- 入队与消费：
  - `tools/council_bridge/execution_task_queue.py`（SQLite 队列）
  - `tools/council_bridge/bridge_worker.py`（消费 worker）
- Chat bridge 处理：
  - `tools/council_bridge/feishu_chat_bridge.py`
- 结果可回发飞书（依赖 webhook URL 环境变量）。
- 关键工件：
  - `artifacts/council_feishu_chat_bridge_request.json`
  - `artifacts/council_feishu_chat_bridge_result.json`
  - `artifacts/council_bridge_worker_result.json`

### 2.5 服务化骨架（已落地）

- `tools/council_bridge/bridge_service.py` 可统一启动：
  - webhook server
  - worker loop
  - optional reconciler loop

## 3. 本地验证结论（最近一次）

- 全量测试通过：`py -m pytest -q`
- 最近结果：`143 passed`
- 实测动作闭环已成功：
  - 飞书回复 `dispatch` -> 自动触发 continue 流程
  - 飞书回复 `approved` -> 自动触发 final review 收口

## 4. 关键运行入口（新线程可直接用）

### 4.1 发送飞书评审通知

```powershell
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_codex_dispatch_ready.json --level review --mode normal
```

### 4.2 短时监听（补偿扫描）

```powershell
py -m tools.council_bridge.feishu_action_reconciler --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage dispatch_ready --check-completion-once --build-receipt-skeleton --interval-sec 5 --max-polls 12 --page-size 1
```

### 4.3 服务骨架启动（建议）

```powershell
py tools/council_bridge/bridge_service.py --host 127.0.0.1 --port 8090 --run-reconciler
```

## 5. 配置边界（已预留）

- 代码：`tools/council_bridge/bridge_config.py`
- 配置样例：
  - `config/bridge/system.json`
  - `config/bridge/owner_overrides.json`
  - `config/bridge/group_overrides.json`
- 合并优先级：`system < owner < group`

## 6. 当前仍是手工/半手工的部分

1. 不是全自动编排：无 daemon 级任务编排引擎、无队列调度器、无回调审批闭环。
2. chat lane 目前是最小可用，不是完整对话记忆系统。
3. `feishu_websocket_ingress.py` 仅为 stub，未替换 webhook 主入口。
4. owner 仍负责最终治理判断（是否批准、是否回退、是否归档）。

## 7. 已知问题与注意事项

1. PowerShell 可能出现 `profile.ps1` 执行策略提示；建议命令使用 `-NoProfile` 运行。
2. 若飞书消息已被旧阶段监听窗口消费，可能出现“阶段不匹配忽略”；重发对应阶段通知并在正确阶段监听即可。
3. chat lane 回发失败时，通常是 webhook 环境变量未加载到当前进程；检查 `.env` 注入方式。

## 8. 新线程建议优先项（按价值排序）

1. **稳定性优先**：固定“监听窗口与阶段切换”策略，减少阶段错配忽略。
2. **chat lane 提升**：完善自由文本上下文裁剪与回复模板，提高移动端可读性。
3. **服务可用性**：把 `bridge_service` 做成更稳定的常驻运行入口（仍保持轻量，不引入重基础设施）。
4. **再评估 websocket ingress**：仅在 webhook 稳定性或延迟实测不足时再接入。

## 9. 一句话交接结论

当前项目已达到：  
**“飞书动作 -> 本地自动续跑 -> 最终收口”可用**，并已具备 v1.2 的最小 chat lane 与服务骨架；下一步应优先做稳定性和体验收敛，而不是扩架构。
