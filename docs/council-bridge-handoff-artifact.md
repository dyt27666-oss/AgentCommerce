# Council Bridge Handoff Artifact v0

## 1. Purpose

This document fixes one tiny contract in the current phase:

After readonly dry-run + manual review, what exact handoff artifact should be written for the next bridge step?

This is a **manual-phase artifact draft** only.

It is:

1. not a final stable protocol
2. not evidence of automated bridge execution in the repository
3. not a replacement for workflow/runtime logic

## 2. File Naming And Location

For current phase, use one fixed path:

- `artifacts/council_bridge_handoff.json`

Why this path is enough now:

1. colocated with existing dry-run exports
2. easy for human review
3. simple handoff target for next tiny bridge step

## 3. Minimal JSON Structure

```json
{
  "handoff_id": "handoff-001",
  "request_id": "exec-req-001",
  "brief_id": "council-poc-brief-001",
  "approval_status": "approved",
  "approved_by": "owner_manual",
  "approved_at": "2026-03-15T10:30:00+08:00",
  "codex_ready_payload": {
    "goal": "Clarify llm_assisted usage instructions without changing runtime behavior.",
    "allowed_files": [
      "docs/llm-assisted.md",
      "README.md"
    ],
    "constraints": [
      "do not change workflow graph",
      "do not edit strategy_agent/crawler/graph/tests",
      "do not add new runtime features"
    ],
    "validation_steps": [
      "git status --short --branch",
      "confirm only scoped docs files changed"
    ],
    "delivery_format": [
      "change summary",
      "changed files",
      "git status",
      "next-step recommendation"
    ]
  },
  "validation_snapshot": {
    "dry_run_status": "valid",
    "dry_run_errors": []
  },
  "notes": "Manual review passed under current Charter boundaries."
}
```

## 4. Field Sources

### From dry-run result

1. `request_id`
2. `brief_id`
3. `codex_ready_payload`
4. `validation_snapshot.dry_run_status` (`status`)
5. `validation_snapshot.dry_run_errors` (`errors`)

### From manual confirmation

1. `handoff_id`
2. `approval_status`
3. `approved_by`
4. `approved_at` (always required)
5. `notes`

## 5. Continue vs Stop Gate

### Allowed to continue to next bridge-prep step

1. `approval_status == "approved"`
2. `validation_snapshot.dry_run_status == "valid"`
3. `validation_snapshot.dry_run_errors` is empty
4. `codex_ready_payload.allowed_files` is bounded and expected

### Must stop and return for correction

1. `approval_status != "approved"`
2. dry-run status is invalid
3. dry-run errors are non-empty
4. payload constraints are missing/ambiguous
5. file scope violates current Charter boundary

## 6. Approved Status Values (Tiny Set)

Use only this tiny set now:

1. `approved`
2. `rejected`
3. `needs_fix`

No extra workflow states in current phase.

## 7. Why These Fields Are Enough Now

This set is sufficient for current phase because it captures:

1. identity: `handoff_id`, `request_id`, `brief_id`
2. gate decision: `approval_status`, `approved_by`, `approved_at`
3. executable input: `codex_ready_payload`
4. audit evidence: `validation_snapshot`, `notes`

Nothing else is required before introducing real bridge execution.

## 8. Boundary With Future Automation

Current artifact does:

1. freeze manual approval output
2. provide one reusable input object for next tiny bridge discussion

Current artifact does not do:

1. automatic trigger
2. Codex invocation
3. orchestration/retry
4. HITL platform integration
5. multi-agent runtime automation

## 9. Minimal Manual SOP

This SOP is for current manual phase only.

It is not automatic bridge execution.

### Step 1: Read dry-run result

Open:

- `artifacts/council_bridge_dry_run.json`
- `docs/council-bridge-handoff-template.json` (as fill template)

If this file does not exist, stop and regenerate dry-run output first.

### Step 2: Check mandatory gate fields

Check in order:

1. `status`
2. `errors`
3. `request_id`
4. `brief_id`
5. `codex_ready_payload.allowed_files`
6. `codex_ready_payload.constraints`

### Step 3: Decide continue or stop

Set decision by these rules:

1. set `approval_status = "approved"` only when:
   - `status == "valid"`
   - `errors` is empty
   - allowed files are bounded and expected
   - constraints are clear and in-scope
2. set `approval_status = "needs_fix"` when:
   - input is recoverable but needs correction
   - example: file scope too broad, ambiguous constraints
3. set `approval_status = "rejected"` when:
   - status is invalid and not acceptable for current round
   - or task intent conflicts with current Charter boundary

### Step 4: Fill manual fields

Populate these fields manually:

1. `handoff_id`
2. `approval_status`
3. `approved_by`
4. `approved_at`
5. `notes`

Field guidance:

1. `handoff_id`: use `handoff-YYYYMMDD-###`, example `handoff-20260315-001`
2. `approved_by`: current human reviewer id/name, example `owner_manual`
3. `approved_at`: ISO-8601 timestamp with timezone, example `2026-03-15T14:30:00+08:00`
4. `notes`: one short audit note for why approved/rejected/needs_fix

If `approval_status != "approved"`, keep `approved_at` filled as review time and explain correction reason in `notes`.

### Step 5: Save fixed handoff artifact

Write to:

- `artifacts/council_bridge_handoff.json`

This file is the fixed manual handoff input for next bridge-prep step.

Practical operation:

1. copy `docs/council-bridge-handoff-template.json`
2. fill fields using checked dry-run result + manual decision
3. save as `artifacts/council_bridge_handoff.json`

Semi-manual helper (optional):

```bash
py tools/council_bridge/manual_handoff_writer.py --approval-status approved --approved-by owner_manual --notes "Manual review passed."
```

This helper only writes the handoff artifact. It does not execute Codex tasks.

## 10. Tiny Rejected Example

```json
{
  "handoff_id": "handoff-20260315-002",
  "request_id": "exec-req-001",
  "brief_id": "council-poc-brief-001",
  "approval_status": "needs_fix",
  "approved_by": "owner_manual",
  "approved_at": "2026-03-15T15:10:00+08:00",
  "codex_ready_payload": null,
  "validation_snapshot": {
    "dry_run_status": "invalid_input",
    "dry_run_errors": [
      "council_brief.owner_intent must be a non-empty string."
    ]
  },
  "notes": "Needs fix: owner_intent missing in source input."
}
```

## 11. Field Meaning (Plain Language)

1. `handoff_id`: this review record id, created manually.
2. `request_id`: request id copied from dry-run result.
3. `brief_id`: brief id copied from dry-run result.
4. `approval_status`: manual decision (`approved` / `needs_fix` / `rejected`).
5. `approved_by`: who made the manual decision.
6. `approved_at`: when the manual decision was made.
7. `codex_ready_payload`: bounded task payload for next bridge step.
8. `validation_snapshot`: quick snapshot of dry-run gate fields.
9. `notes`: one short reason for audit.

## 12. Required vs Manual-Filled

### Required fields

1. `handoff_id`
2. `request_id`
3. `brief_id`
4. `approval_status`
5. `approved_by`
6. `approved_at`
7. `validation_snapshot.dry_run_status`
8. `validation_snapshot.dry_run_errors`

### Owner-filled manual fields

1. `handoff_id`
2. `approval_status`
3. `approved_by`
4. `approved_at`
5. `notes`

### Dry-run copied fields

1. `request_id`
2. `brief_id`
3. `codex_ready_payload` (for approved case)
4. `validation_snapshot` (`status` + `errors`)

## 13. Locked Rules (v0)

These rules are fixed for current semi-manual phase.

1. `approved_at` is always required for all statuses.
2. `codex_ready_payload`:
   - must be non-null when `approval_status == "approved"`
   - must be null when `approval_status` is `needs_fix` or `rejected`
3. `approved_by` format:
   - lowercase letters, numbers, `_` or `-`
   - recommended length: 3 to 32 characters
   - example: `owner_manual`, `pm_reviewer_01`
4. `validation_snapshot` minimum keys:
   - `dry_run_status`
   - `dry_run_errors`
5. `validation_snapshot` rules:
   - when `dry_run_status == "valid"`, `dry_run_errors` must be an empty list
   - when `dry_run_status != "valid"`, `dry_run_errors` must be non-empty
6. `handoff_id` recommended format:
   - `handoff-YYYYMMDD-###`

## 14. Typical Approved vs Needs_Fix Conditions

### Usually `approved` when

1. dry-run `status` is `valid`
2. dry-run `errors` is empty
3. allowed files are in-scope
4. constraints are clear
5. payload can be executed without re-guessing intent

### Usually `needs_fix` when

1. dry-run status is invalid but correctable
2. errors point to missing/invalid input fields
3. file scope is too broad and can be narrowed
4. constraints are unclear but can be clarified in one round

## 15. Ready-to-Use Example Files

Use these two tiny examples directly:

1. `docs/council-bridge-handoff-approved-example.json`
2. `docs/council-bridge-handoff-needs-fix-example.json`

These examples are manual-phase artifacts only, not automatic bridge outputs.

## 16. Quick Validity Matrix

Use this matrix before handing artifact to Codex:

| `approval_status` | `codex_ready_payload` | `validation_snapshot` | Can continue to Codex handoff |
|---|---|---|---|
| `approved` | must be non-null | `dry_run_status = valid` and empty `dry_run_errors` | yes |
| `needs_fix` | must be null | must include errors explaining fix | no |
| `rejected` | must be null | must include reason context in errors/notes | no |

For practical review steps, use:

- `docs/council-bridge-handoff-review-checklist.md`
- `docs/council-bridge-handoff-pack-v0.md` (single entry walkthrough)

After an approved handoff is ready, optional prompt adaptation is available:

```bash
py tools/council_bridge/handoff_prompt_adapter.py --handoff artifacts/council_bridge_handoff.json --output artifacts/council_codex_prompt.txt
```

This creates prompt text only. It does not execute Codex.
