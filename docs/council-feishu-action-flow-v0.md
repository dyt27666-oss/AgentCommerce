# Council Feishu Action Flow v0

This document defines the next minimal step after Feishu notifications:
capture a small owner action choice and map it back to local bridge artifacts.

This is still semi-manual.  
No callback orchestration or automatic mobile approval pipeline is implemented.

## 1. Why this step

Current state:

1. bridge artifacts can be summarized and sent to Feishu
2. owner can review status on mobile

Gap:

1. owner action after mobile review is not yet captured in a stable local artifact

v0 objective:

1. define a tiny action artifact that the owner fills manually
2. make the action explicit and auditable for local bridge flow

## 2. First useful actions

Use only these four actions first:

1. `dispatch`:
   - meaning: approved to continue local dispatch path
2. `hold`:
   - meaning: pause round for later decision
3. `needs_fix`:
   - meaning: fix inputs/contract fields before continuing
4. `reject`:
   - meaning: stop this round

## 3. Where actions apply

v0 primary stage:

1. after receiving Feishu notification for `council_codex_dispatch_ready.json`

secondary stage (optional):

1. after receiving Feishu notification for `council_codex_dispatch_completion.json`

## 4. Minimal local action artifact

Recommended file:

1. `artifacts/council_feishu_owner_action.json`

Template reference:

1. `docs/council-feishu-owner-action-template.json`
2. helper tool:
   - `tools/council_bridge/feishu_owner_action_writer.py`

The artifact should carry:

1. identity linkage:
   - `request_id`
   - `brief_id`
   - `handoff_id`
2. action decision:
   - `owner_action` (`dispatch` / `hold` / `needs_fix` / `reject`)
3. source context:
   - `source_artifact_path`
   - `source_state`
4. manual metadata:
   - `action_by`
   - `action_at`
   - `notes`

## 5. Connection to current bridge flow

Mapping guidance:

1. `dispatch`:
   - continue with existing local dispatch tools
2. `hold`:
   - stop and wait; no dispatch
3. `needs_fix`:
   - go back to handoff/input correction path
4. `reject`:
   - stop round and close as rejected

Tiny consistency rule with owner taxonomy:

1. use `needs_fix` for recoverable input/contract problems
2. use `reject` for scope/identity invalid cases

This action artifact does not replace current contract checks.  
It only records owner choice after mobile review.

Minimal writer command:

```bash
py tools/council_bridge/feishu_owner_action_writer.py --action dispatch --owner-id owner_mobile --notes "mobile review ok" --source-artifact artifacts/council_codex_dispatch_ready.json
```

Bridge-to-next-step command:

```bash
py tools/council_bridge/feishu_action_round_bridge.py --action-artifact artifacts/council_feishu_owner_action.json --output artifacts/council_feishu_action_round_bridge.json
```

This bridge output tells owner:

1. whether the round should `continue` / `pause` / `loop_back` / `stop`
2. recommended next local step
3. next tool/artifact paths to use

## 6. What remains manual

1. owner still reviews Feishu content and bridge artifacts
2. owner still fills action artifact manually
3. owner still runs local tools manually
4. owner still decides final review outcome

## 7. Explicitly out of scope in this phase

1. Feishu callback handlers
2. automatic action ingestion from mobile
3. orchestration/auto-dispatch/retry loop
4. MCP approval pipeline
5. workflow backbone changes

## 8. Mobile Review Loop Demo

Use one command entry to run a semi-manual loop demo:

```bash
py tools/council_bridge/feishu_loop_demo.py --source-artifact artifacts/council_codex_dispatch_ready.json --level detail --send-mode dry-run --owner-action dispatch --owner-id owner_mobile --notes "mobile review ok"
```

Manual rehearsal steps:

1. send (or preview) Feishu notification for source artifact
2. record owner action artifact (`council_feishu_owner_action.json`)
3. generate continuation artifact (`council_feishu_action_round_bridge.json`)
4. read `recommended_next_step` from continuation result

This is still semi-manual:

1. no callback trigger
2. no auto-run of downstream tools
3. owner keeps final control on next step execution

## 9. Single-step Local Executor (After Continuation)

After `council_feishu_action_round_bridge.json` is generated, use:

```bash
py tools/council_bridge/bridge_round_executor.py --continuation artifacts/council_feishu_action_round_bridge.json
```

Current v0 behavior:

1. `continue`: executes one controlled local step only (dispatch runner path)
2. `pause`: no execution, writes pause summary
3. `stop`: no execution, writes stop summary
4. `loop_back`: no execution, writes loop-back summary and manual recommendation

Output artifact:

1. `artifacts/council_bridge_round_executor_result.json`

This helper is a single-step local executor, not orchestration.

## 10. Feishu Confirm -> Local Continue Once

To compress post-confirm multi-command work into one local entrypoint:

```bash
py tools/council_bridge/feishu_continue_once.py --source-artifact artifacts/council_codex_dispatch_ready.json --owner-action dispatch --owner-id owner_mobile --notes "feishu confirm"
```

This command chains:

1. owner action artifact creation (or reuse existing `--owner-action-artifact`)
2. action round bridge generation
3. round executor single-step execution

This is still semi-manual:

1. no Feishu callback
2. no auto-trigger listener
3. no orchestration engine

### Continue once with optional completion check

If you want one extra post-dispatch check (single shot, no polling):

```bash
py tools/council_bridge/feishu_continue_once.py --source-artifact artifacts/council_codex_dispatch_ready.json --owner-action dispatch --owner-id owner_mobile --check-completion-once
```

This option:

1. only runs when continue path dispatch succeeds
2. performs one-time completion capture
3. does not wait/retry/poll
4. does not auto-generate execution receipt
5. does not auto-trigger final review

### Continue once with optional receipt skeleton prefill

If you also want one-step receipt skeleton prefill:

```bash
py tools/council_bridge/feishu_continue_once.py --source-artifact artifacts/council_codex_dispatch_ready.json --owner-action dispatch --owner-id owner_mobile --check-completion-once --build-receipt-skeleton
```

This adds one optional action after completion check:

1. build `artifacts/council_codex_execution_receipt_skeleton.json` when completion data is available
2. keep result marked as `skeleton_only`
3. do not auto-generate final execution receipt
4. do not auto-run final review

## 11. Mobile decision-focused notification mode

If owner wants a compact decision snapshot on mobile:

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_feishu_continue_once_result.json --level review
```

`review` mode is optimized for mobile decision context:

1. current stage
2. current state explanation
3. recommended action
4. key identity and decision fields
5. risk/warnings summary without long raw log dump
6. 中文人类可读摘要（更少字段播报，更强调“这一步做了什么、你下一步该做什么”）

### Notify policy (normal/test + dedupe)

Use `normal` for formal workflow notifications:

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_owner_final_review_summary.json --level review --mode normal --dedupe-window-sec 60
```

Use `test` for rehearsal/debug messages (title will include `[TEST]`):

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_feishu_continue_once_result.json --level review --mode test --dedupe-window-sec 60
```

Dedupe behavior:

1. key includes `artifact_path + level + mode (+ identity when available)`
2. repeated sends in dedupe window are suppressed
3. send/suppress state is recorded in `artifacts/council_feishu_notify_state.json`
4. dedupe is local-only and time-window based (not a distributed lock)

## 12. Feishu Action Protocol

This protocol keeps action parsing fixed, stage-aware, and auditable.

### 12.1 Dispatch-ready stage

Recommended source artifacts:

1. `artifacts/council_codex_dispatch_ready.json`
2. `artifacts/council_feishu_continue_once_result.json` when not owner-review-ready

Valid reply actions:

1. `dispatch`: continue local dispatch path (listener routes to `feishu_continue_once.py`)
2. `hold`: pause current round (listener routes to `feishu_continue_once.py`)
3. `needs_fix`: loop back for handoff/input fixes (listener routes to `feishu_continue_once.py`)
4. `reject`: stop current round (listener routes to `feishu_continue_once.py`)

### 12.2 Completion / receipt-ready stage

Recommended source artifacts:

1. `artifacts/council_codex_execution_receipt_skeleton.json`
2. artifacts with `owner_review_ready=true`
3. completion artifacts with `completion_observation_status=execution_receipt_available`

Valid reply actions:

1. `approved`: final owner approve (listener routes to `final_review_once.py`)
2. `revision_request`: request targeted revision (listener routes to `final_review_once.py`)
3. `needs_fix`: request contract/input correction (listener routes to `final_review_once.py`)
4. `rejected`: final reject (listener routes to `final_review_once.py`)

### 12.3 Final summary stage

Typical artifact:

1. `artifacts/council_owner_final_review_summary.json`

Behavior:

1. this stage is mainly result notification
2. action replies are usually not needed
3. listener treats this stage as no-op for action routing

### 12.4 Listener interpretation rules

1. fixed keyword match only (no NLP free-text reasoning)
2. action meaning depends on current stage
3. invalid action for current stage is recorded as `ignored` with reason
4. listener audit artifacts remain:
   - `artifacts/council_feishu_listener_event.json`
   - `artifacts/council_feishu_listener_log.json`
   - `artifacts/council_feishu_listener_state.json`

## 13. Short-window listener usage (avoid "is it stuck?" confusion)

Listener is a short polling window, not a blocked dead process.

How to read runtime output:

1. `stage=...`:
   - current protocol stage (`dispatch_ready` or `review_ready`)
2. `allowed_actions=[...]`:
   - valid Feishu reply words for this run
3. `poll x/y | remaining~Ns`:
   - current poll progress and approximate wait time
4. `status=ignored`:
   - usually stage mismatch, with explicit `ignored_reason`
5. `status=success`:
   - action routed and local entrypoint triggered

Default listener window:

1. `interval-sec=3`
2. `max-polls=20`
3. around 60 seconds by default
4. use `--max-polls 0` only when you explicitly want long-running manual watch mode

Recommended short-window command:

```bash
py tools/council_bridge/feishu_action_listener.py --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --interval-sec 3 --max-polls 20
```

PowerShell startup noise note:

1. If your shell prints `profile.ps1` policy warnings, it is shell startup noise, not listener failure.
2. Recommended invocation to reduce noise:

```bash
powershell -NoProfile -Command "py tools/council_bridge/feishu_action_listener.py --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --interval-sec 3 --max-polls 20"
```

## 14. Webhook-first, polling-fallback (v1.x latency upgrade)

Current entry design:

1. primary entry (low latency):
   - `tools/council_bridge/feishu_event_webhook.py`
2. fallback reconciler (compensation scan):
   - `tools/council_bridge/feishu_action_reconciler.py`
3. compatibility alias:
   - `tools/council_bridge/feishu_action_listener.py` (delegates to reconciler)

Routing core:

1. both webhook and polling normalize into one payload schema
2. both call one unified router:
   - `tools/council_bridge/feishu_message_router.py`
3. router applies stage/action protocol and triggers:
   - `feishu_continue_once.py` or `final_review_once.py`

Idempotency:

1. dedupe key priority:
   - `event_id` -> `message_id` -> `chat_id+sender_id+text+create_time`
2. dedupe state:
   - `artifacts/council_feishu_message_dedupe_state.json`
3. repeated events are marked `deduped` and not re-executed

New artifacts:

1. parsed webhook event:
   - `artifacts/council_feishu_webhook_event.json`
2. route result:
   - `artifacts/council_feishu_message_route_result.json`
3. polling reconciliation result:
   - `artifacts/council_feishu_reconciler_result.json`

Webhook run command (example):

```bash
py tools/council_bridge/feishu_event_webhook.py --host 127.0.0.1 --port 8090 --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --check-completion-once --build-receipt-skeleton
```

Fallback reconciler command (one-shot):

```bash
py tools/council_bridge/feishu_action_reconciler.py --source-artifact artifacts/council_codex_dispatch_ready.json --action-stage auto --max-polls 1
```

Notes:

1. webhook is now the real-time action entry
2. polling is compensation/recovery only
3. free-text routing remains stub (`chat_bridge_stub`)
