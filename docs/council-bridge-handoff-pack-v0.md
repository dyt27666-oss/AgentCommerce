# Council Bridge Handoff Pack v0

This is the single starting point for one manual handoff round.

Current stage is semi-manual only.  
No automatic bridge execution is implemented.

## 1. What to open first

1. Input evidence (dry-run result, required):
   - `artifacts/council_bridge_dry_run.json`
2. Fill template (required):
   - `docs/council-bridge-handoff-template.json`
3. Review checklist (required):
   - `docs/council-bridge-handoff-review-checklist.md`
4. Locked contract rules (required):
   - `docs/council-bridge-handoff-contract-v0.md`
5. Reference examples (optional):
   - `docs/council-bridge-handoff-approved-example.json`
   - `docs/council-bridge-handoff-needs-fix-example.json`
6. Semi-manual writer tool (optional but recommended):
   - `tools/council_bridge/manual_handoff_writer.py`
7. Prompt adapter tool (optional, after approved handoff):
   - `tools/council_bridge/handoff_prompt_adapter.py`
8. Guided round helper (optional, after approved handoff):
   - `tools/council_bridge/round_helper.py`
9. Dispatch-prep adapter (optional, before manual dispatch):
   - `tools/council_bridge/dispatch_prep_adapter.py`
10. Local dispatch runner (optional, after dispatch-ready):
   - `tools/council_bridge/codex_dispatch_runner.py`
11. Dispatch completion capture (optional, after dispatch attempt):
   - `tools/council_bridge/dispatch_completion_capture.py`
12. Completion-to-receipt bridge (optional, before execution receipt prep):
   - `tools/council_bridge/completion_receipt_bridge.py`
13. Feishu notifier (optional, mobile review surface):
   - `tools/council_bridge/feishu_notifier.py`

## 2. Recommended Naming/Path Conventions

Use these default paths in every manual round:

1. dry-run artifact (input evidence):
   - `artifacts/council_bridge_dry_run.json`
2. final handoff artifact (round output):
   - `artifacts/council_bridge_handoff.json`

Optional historical copies are allowed, but default path stays unchanged.

## 3. Handoff ID Rule (v0)

Recommended pattern:

- `handoff-YYYYMMDD-###`

Examples:

1. `handoff-20260315-001`
2. `handoff-20260315-002`
3. `handoff-20260316-001`

Use one date-based sequence per day to keep audit order simple.

## 4. Minimum File Set For One Round

### Required files

1. `artifacts/council_bridge_dry_run.json`
2. `docs/council-bridge-handoff-template.json`
3. `docs/council-bridge-handoff-review-checklist.md`
4. `docs/council-bridge-handoff-contract-v0.md`

### Optional reference files

1. `docs/council-bridge-handoff-approved-example.json`
2. `docs/council-bridge-handoff-needs-fix-example.json`
3. `docs/council-bridge-handoff-artifact.md`

## 5. One-round walkthrough (`approved`)

1. Open `artifacts/council_bridge_dry_run.json`.
2. Confirm:
   - `status == "valid"`
   - `errors == []`
   - `request_id`, `brief_id` exist.
3. Open `docs/council-bridge-handoff-template.json`.
4. Copy dry-run fields into template:
   - `request_id`
   - `brief_id`
   - `codex_ready_payload`
   - `validation_snapshot` (`dry_run_status`, `dry_run_errors`)
5. Fill manual fields:
   - `handoff_id`
   - `approval_status = "approved"`
   - `approved_by`
   - `approved_at`
   - `notes`
6. Verify against checklist.
7. Save final artifact to:
   - `artifacts/council_bridge_handoff.json`

Optional shortcut using semi-manual writer:

```bash
py tools/council_bridge/manual_handoff_writer.py --approval-status approved --approved-by owner_manual --notes "Manual review passed."
```

## 6. One-round walkthrough (`needs_fix`)

1. Open `artifacts/council_bridge_dry_run.json`.
2. If errors exist or input is fixable but not ready, set:
   - `approval_status = "needs_fix"`
3. In template/result:
   - keep `request_id`, `brief_id`
   - set `codex_ready_payload = null`
   - keep `validation_snapshot` from dry-run
4. Fill manual fields:
   - `handoff_id`
   - `approved_by`
   - `approved_at`
   - `notes` (state exact fix action)
5. Verify with checklist (`needs_fix` section).
6. Save final artifact to:
   - `artifacts/council_bridge_handoff.json`
7. Return to source input correction and regenerate dry-run.

Optional shortcut using semi-manual writer:

```bash
py tools/council_bridge/manual_handoff_writer.py --approval-status needs_fix --approved-by owner_manual --notes "Needs fix: update source input and regenerate dry-run."
```

## 7. Fast decision rules

Use this quick rule before save:

1. `approved`:
   - `codex_ready_payload` must be non-null
   - `dry_run_status` must be `valid`
   - `dry_run_errors` must be empty
2. `needs_fix`:
   - `codex_ready_payload` must be null
   - `dry_run_errors` must be non-empty and fixable
3. `rejected`:
   - `codex_ready_payload` must be null
   - stop current round and redefine scope

## 8. Output of this pack

At the end of one manual round, there should be one artifact only:

- `artifacts/council_bridge_handoff.json`

This artifact is the input for the next manual bridge-prep step.

## 9. Optional Prompt Adapter Step (Approved Only)

After an approved handoff is prepared, you can generate a Codex-ready prompt text:

```bash
py tools/council_bridge/handoff_prompt_adapter.py --handoff artifacts/council_bridge_handoff.json --output artifacts/council_codex_prompt.txt
```

This step:

1. works only for executable `approved` handoff
2. refuses `needs_fix` / `rejected` or missing required fields
3. does not execute Codex; it only prepares prompt text

## 10. Optional Guided Round Helper (Approved Only)

If you want one guided flow output (prompt + round summary), run:

```bash
py tools/council_bridge/round_helper.py --handoff artifacts/council_bridge_handoff.json --prompt-output artifacts/council_codex_prompt.txt --summary-output artifacts/council_bridge_round_summary.json
```

This helper:

1. validates executable approved handoff under current v0 rules
2. prepares `artifacts/council_codex_prompt.txt`
3. prepares `artifacts/council_bridge_round_summary.json`
4. does not execute Codex and does not trigger automation

## 11. Optional Dispatch-Prep Adapter (Approved Only)

Before manual prompt carry, you can run:

```bash
py tools/council_bridge/dispatch_prep_adapter.py --handoff artifacts/council_bridge_handoff.json --prompt artifacts/council_codex_prompt.txt --output artifacts/council_codex_dispatch_ready.json
```

This adapter:

1. validates executable approved handoff
2. checks prompt file exists and is non-empty
3. writes dispatch-ready artifact with gate results
4. blocks clearly if gates fail
5. does not dispatch or execute Codex

## 12. Optional Local Dispatch Runner (After Dispatch-Ready)

If `artifacts/council_codex_dispatch_ready.json` is ready, attempt local dispatch:

```bash
py tools/council_bridge/codex_dispatch_runner.py --dispatch-ready artifacts/council_codex_dispatch_ready.json --prompt artifacts/council_codex_prompt.txt --output artifacts/council_codex_dispatch_receipt.json --timeout-sec 20
```

This runner:

1. attempts local Codex dispatch via non-interactive `codex exec` mode
2. writes `artifacts/council_codex_dispatch_receipt.json`
3. stops with clear failure when gates fail or command fails
4. does not orchestrate retries or external systems

If you need wait-for-finish behavior, use:

```bash
py tools/council_bridge/codex_dispatch_runner.py --dispatch-mode run
```

## 13. Optional Dispatch Completion Capture

After dispatch attempt, observe completion-side state:

```bash
py tools/council_bridge/dispatch_completion_capture.py --dispatch-receipt artifacts/council_codex_dispatch_receipt.json --execution-receipt artifacts/council_codex_execution_receipt.json --output artifacts/council_codex_dispatch_completion.json
```

This helper:

1. checks dispatch receipt outcome
2. checks if execution receipt is already available
3. records normalized completion observation and next manual action
4. does not execute Codex or orchestrate retries

## 14. Optional Completion->Receipt Bridge

To decide if execution-receipt preparation should proceed now:

```bash
py tools/council_bridge/completion_receipt_bridge.py --handoff artifacts/council_bridge_handoff.json --dispatch-receipt artifacts/council_codex_dispatch_receipt.json --completion artifacts/council_codex_dispatch_completion.json --output artifacts/council_codex_receipt_prep.json
```

This bridge:

1. interprets completion state
2. marks `receipt_prep_ready` true/false
3. provides structured next action or blocking reason
4. does not auto-generate execution receipt

## 15. Optional Feishu Notification (Webhook)

To push a compact mobile-friendly artifact summary:

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_codex_dispatch_completion.json --dry-run
```

Detail mode (for suspicious/blocked state inspection):

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_codex_dispatch_completion.json --level detail --dry-run
```

Send for real:

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_codex_dispatch_completion.json --webhook-url "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

Or use env webhook (priority: `AGENTCOMMERCE_FEISHU_WEBHOOK_URL` then `FEISHU_WEBHOOK_URL`):

```bash
py tools/council_bridge/feishu_notifier.py --artifact artifacts/council_codex_dispatch_completion.json
```

Keyword-protected webhooks are supported by default marker `bridge`.  
You can override marker via `--keyword-marker` or env (`AGENTCOMMERCE_FEISHU_KEYWORD_MARKER`, then `FEISHU_KEYWORD_MARKER`).

Supported artifact summaries:

1. `council_bridge_handoff.json`
2. `council_codex_dispatch_ready.json`
3. `council_codex_dispatch_receipt.json`
4. `council_codex_dispatch_completion.json`
5. `council_owner_final_review_summary.json`

## 16. Optional Feishu Owner Action Capture (Manual)

After mobile notification review, you can record a tiny local owner action:

1. flow guide:
   - `docs/council-feishu-action-flow-v0.md`
2. action template:
   - `docs/council-feishu-owner-action-template.json`
3. recommended saved artifact:
   - `artifacts/council_feishu_owner_action.json`

This step is manual-only in v0.  
It records owner choice (`dispatch` / `hold` / `needs_fix` / `reject`) but does not auto-trigger tools.

Use helper to reduce copy/fill work:

```bash
py tools/council_bridge/feishu_owner_action_writer.py --action dispatch --owner-id owner_mobile --notes "mobile review ok" --source-artifact artifacts/council_codex_dispatch_ready.json
```

Then convert owner action to a structured local next-step bridge:

```bash
py tools/council_bridge/feishu_action_round_bridge.py --action-artifact artifacts/council_feishu_owner_action.json --output artifacts/council_feishu_action_round_bridge.json
```

## 17. Notes About This Helper

`manual_handoff_writer.py` is still semi-manual:

1. it does not call Codex
2. it does not execute tasks
3. it only prepares the handoff artifact file with reduced copy/fill work

## 18. Execution Receipt Skeleton Helper (Prefill Only)

After completion capture, you can prefill a receipt skeleton:

```bash
py tools/council_bridge/execution_receipt_skeleton_helper.py --output artifacts/council_codex_execution_receipt_skeleton.json
```

This helper:

1. pre-fills stable linkage/state fields from current bridge artifacts
2. marks output as `execution_receipt_status = skeleton_only`
3. lists owner fields that still need manual confirmation/completion
4. does not auto-generate final execution receipt
5. is not final review or automatic acceptance
