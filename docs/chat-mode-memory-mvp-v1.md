# Chat Mode Memory MVP v1

## Scope

This MVP only affects `route_type=chat` in Feishu bridge.

Goals:
1. Keep chat replies natural (avoid repeating workflow boilerplate).
2. Provide short-term context memory per `chat_id`.
3. Preserve minimal auditability in artifacts.

## Behavior

1. On each chat task, bridge loads recent turns from `artifacts/chat_memory/<chat_id>.json`.
2. Recent turns are passed into `generate_chat_reply(...)` as `conversation_history`.
3. After reply generation, the new user/assistant turn is appended back to memory store.
4. Workflow lanes (`dispatch/approved/needs_fix`) are not changed by this memory module.

## Defaults

1. Memory window default: `6` turns (`12` messages).
2. Per-task override supported via payload field `chat_memory_turns`.
3. LLM remains optional; if unavailable, rule fallback still works and is also stored as assistant turn.

## Artifact Fields

`artifacts/council_feishu_chat_bridge_result.json` now includes:
1. `chat_memory_enabled`
2. `chat_memory_window_turns`
3. `chat_memory_messages_used`
4. `chat_memory_path`
5. `chat_memory_messages`
6. `chat_memory_turns`

These fields explain:
1. whether memory is active,
2. how many historical messages were injected this turn,
3. where memory was persisted.
