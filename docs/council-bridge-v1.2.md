# Council Bridge v1.2

## Scope
Bridge v1.2 adds a dual control plane on top of v1.1:

1. action lane (existing protocol, unchanged)
2. chat lane (free-text -> queue -> worker -> Feishu reply)

It keeps artifact-first audit and owner-governed workflow.

## Architecture

### Ingress

1. primary:
   - `tools/council_bridge/feishu_event_webhook.py`
2. fallback:
   - `tools/council_bridge/feishu_action_reconciler.py`
3. compatibility alias:
   - `tools/council_bridge/feishu_action_listener.py`
4. future reserved:
   - `tools/council_bridge/feishu_websocket_ingress.py` (stub)

### Routing

1. unified router:
   - `tools/council_bridge/feishu_message_router.py`
2. route types:
   - `action`
   - `chat`
   - `ignored`

### Execution

1. queue:
   - `tools/council_bridge/execution_task_queue.py` (SQLite)
2. worker:
   - `tools/council_bridge/bridge_worker.py`
3. chat processor:
   - `tools/council_bridge/feishu_chat_bridge.py`
4. service skeleton:
   - `tools/council_bridge/bridge_service.py`

### Config boundaries

1. system:
   - `config/bridge/system.json`
2. owner:
   - `config/bridge/owner_overrides.json`
3. group:
   - `config/bridge/group_overrides.json`

Merge order:

1. system < owner < group

## Artifacts

New in v1.2:

1. `artifacts/council_feishu_webhook_event.json`
2. `artifacts/council_feishu_message_route_result.json`
3. `artifacts/council_feishu_reconciler_result.json`
4. `artifacts/council_feishu_chat_bridge_request.json`
5. `artifacts/council_feishu_chat_bridge_result.json`
6. `artifacts/council_bridge_worker_result.json`
7. `artifacts/council_bridge_tasks.db`

## Local run

Webhook primary:

```bash
py tools/council_bridge/feishu_event_webhook.py --host 127.0.0.1 --port 8090 --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --check-completion-once --build-receipt-skeleton
```

Worker (loop):

```bash
py tools/council_bridge/bridge_worker.py --loop --interval-sec 2
```

Fallback reconciler (one-shot):

```bash
py tools/council_bridge/feishu_action_reconciler.py --max-polls 1 --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto
```

Unified service skeleton:

```bash
py tools/council_bridge/bridge_service.py --host 127.0.0.1 --port 8090 --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --run-reconciler
```

## Feishu setup

1. subscribe event type:
   - `im.message.receive_v1`
2. callback points to your webhook public URL
3. app has message read permissions
4. bot is in target chat/group

## Notes

1. action lane behavior remains compatible with v1.1
2. free-text chat lane is intentionally lightweight
3. chat lane does not bypass owner protocol
4. WebSocket ingress is only a reserved stub in v1.2

