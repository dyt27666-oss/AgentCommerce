# Council Bridge Lifecycle v0 (Semi-Manual)

This document connects the current bridge artifacts into one practical end-to-end flow.

This is documentation only for the current v0 phase.  
No automatic runtime integration is implemented.

## 1. Lifecycle Stages (Ordered)

### Stage 1: Dry-run preparation

Artifact:

- `artifacts/council_bridge_dry_run.json`

What happens:

1. generate dry-run result from council input
2. inspect dry-run status and errors

Gate to next stage:

1. dry-run file exists
2. `request_id` and `brief_id` are present

Stop condition:

1. dry-run file missing or malformed

### Stage 2: Manual handoff preparation

Artifacts used:

1. `artifacts/council_bridge_dry_run.json`
2. `docs/council-bridge-handoff-template.json`
3. `docs/council-bridge-handoff-review-checklist.md`
4. `docs/council-bridge-handoff-contract-v0.md`

Artifact produced:

- `artifacts/council_bridge_handoff.json`

What happens:

1. owner chooses `approval_status`
2. writer or manual fill produces handoff artifact
3. owner checks contract/checklist rules

Gate to next stage:

1. handoff file exists
2. required fields exist
3. status and nullability rules are consistent

Stop condition:

1. handoff contract rules fail

### Stage 3: Codex intake check

Artifact used:

- `artifacts/council_bridge_handoff.json`

Rule reference:

- `docs/council-codex-intake-v0.md`

What happens:

1. check if handoff is executable by status and snapshot
2. validate scope boundaries (`allowed_files`, `constraints`)

Gate to next stage:

1. `approval_status == "approved"`
2. payload is executable per intake rules

Stop condition:

1. status is `needs_fix` or `rejected`
2. required intake fields are missing

### Stage 4: Execution result recording

Artifact produced:

- `artifacts/council_codex_dispatch_receipt.json`
- `artifacts/council_codex_dispatch_completion.json`
- `artifacts/council_codex_execution_receipt.json`

Rule reference:

- `docs/council-codex-execution-receipt-v0.md`
- helper: `tools/council_bridge/execution_receipt_writer.py`
- helper: `tools/council_bridge/codex_dispatch_runner.py`
- helper: `tools/council_bridge/dispatch_completion_capture.py`

What happens:

1. local dispatch attempt is recorded (dispatch receipt)
2. post-dispatch completion-side observation is recorded (completion capture)
3. execution outcome is reported honestly (execution receipt)
4. changed files and compliance are recorded

Gate to next stage:

1. dispatch receipt is not blocked
2. completion observation does not indicate hard dispatch failure
3. execution receipt includes required identity, status, summary fields

Stop condition:

1. dispatch receipt is blocked/failed
2. completion observation indicates unresolved dispatch failure
3. execution receipt missing required fields

### Stage 5: Owner review and decision

Artifacts reviewed:

1. `artifacts/council_bridge_handoff.json`
2. `artifacts/council_codex_dispatch_receipt.json`
3. `artifacts/council_codex_dispatch_completion.json`
4. `artifacts/council_codex_execution_receipt.json`

What happens:

1. owner checks status, compliance, changed files, summary
2. owner decides close loop or run another round

End condition:

1. owner accepts result and closes round

Loop-back condition:

1. owner marks correction needed and starts new dry-run/handoff round

## 2. needs_fix Loop (Explicit)

The flow loops back when:

1. handoff status is `needs_fix`
2. intake check fails due to missing/invalid required fields
3. owner review finds result insufficient

Loop target:

1. return to Stage 1 (dry-run) or Stage 2 (handoff prep), depending on issue source

## 3. Where the Flow Must Stop

Stop immediately when:

1. handoff is `rejected`
2. constraints are out of boundary
3. identity linkage (`request_id`, `brief_id`, `handoff_id`) is inconsistent
4. receipt claims success but has missing required fields

## 4. Owner Checkpoints (What to Review First)

### Checkpoint A: after dry-run

1. `status`
2. `errors`
3. `request_id` / `brief_id`

### Checkpoint B: after handoff artifact

1. `approval_status`
2. `codex_ready_payload` nullability by status
3. `validation_snapshot`
4. `approved_by` / `approved_at` / `notes`

### Checkpoint C: after execution receipt

1. `execution_status`
2. `constraints_compliance`
3. `changed_files`
4. `summary`
5. `next_step_suggestion`

## 5. Minimal Successful v0 End-to-End Loop

A minimal successful loop is:

1. valid dry-run artifact generated
2. approved handoff artifact generated with required fields
3. intake rules mark handoff executable
4. execution receipt produced with required fields
5. owner reviews receipt and accepts round outcome

This is enough for current semi-manual bridge v0.
