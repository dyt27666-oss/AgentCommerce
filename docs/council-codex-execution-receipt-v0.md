# Council -> Codex Execution Receipt v0

This document defines the return artifact Codex should provide after processing an approved handoff.

This is documentation only for the current semi-manual phase.  
No automatic runtime integration is implemented.

## 1. Why This Receipt Is Needed

The receipt is needed so the owner can quickly verify:

1. what was actually done
2. whether constraints were respected
3. whether work is complete, partial, or blocked
4. what to do next

Without this receipt, the owner cannot audit execution quality consistently.

## 2. Default Receipt Path

Use one simple default output path:

- `artifacts/council_codex_execution_receipt.json`

Semi-manual helper command:

```bash
py tools/council_bridge/execution_receipt_writer.py --execution-status completed --changed-files "docs/llm-assisted.md" --summary "Updated docs wording." --next-step-suggestion "Owner review and approve merge." --constraints-compliant true --constraints-note "All edits stayed in allowed files."
```

This helper:

1. reads `artifacts/council_bridge_handoff.json`
2. carries `request_id` / `brief_id` / `handoff_id`
3. writes the receipt JSON only
4. does not execute Codex or any runtime automation

## 3. Minimum Receipt Fields

### Required fields

1. `request_id`
2. `brief_id`
3. `handoff_id`
4. `execution_status`
5. `changed_files`
6. `constraints_compliance`
7. `summary`
8. `next_step_suggestion`

### Optional fields

1. `validation_results`
2. `blocked_reason`
3. `partial_notes`
4. `warnings`
5. `generated_at`

## 4. Field Meaning (Plain Language)

1. `request_id`, `brief_id`, `handoff_id`:
   - must match the source handoff artifact identity.
2. `execution_status`:
   - one of `completed`, `partial`, `blocked`, `not_executed`.
3. `changed_files`:
   - list of files actually changed in this round (empty if none).
4. `constraints_compliance`:
   - `compliant` (`true/false`) and a short note.
5. `summary`:
   - concise description of what was delivered.
6. `next_step_suggestion`:
   - one practical next action for owner.

## 5. Link Back To Handoff Artifact

The receipt must reference the handoff artifact by:

1. matching `request_id`
2. matching `brief_id`
3. matching `handoff_id`

This keeps the bridge auditable round by round.

## 6. How To Report changed_files

Rules:

1. include only files actually modified
2. use repository-relative paths
3. keep list exact and small
4. if no changes, return `[]` and explain why in `summary`

## 7. How To Report Constraint Compliance

Use a minimal object:

```json
{
  "compliant": true,
  "note": "All edits stayed inside allowed_files and constraints."
}
```

If non-compliant:

1. set `compliant = false`
2. state exactly what constraint was violated
3. set `execution_status` to `partial` or `blocked` honestly

## 8. Honest Status Rules

### `completed`

Use when scoped work is finished and constraints are respected.

### `partial`

Use when some scope is done but not all.

Must include:

1. what is done
2. what is missing
3. what blocker/limit caused partial delivery

### `blocked`

Use when work could not proceed due to blocking condition.

Must include:

1. `blocked_reason`
2. a concrete next action

### `not_executed`

Use when execution did not start (for example, non-approved handoff).

Must include a short reason in `summary`.

## 9. What Owner Should Review First

Owner review order:

1. `execution_status`
2. `constraints_compliance`
3. `changed_files`
4. `summary`
5. `next_step_suggestion`

If status is `partial` or `blocked`, review `blocked_reason` / `partial_notes` immediately.

## 10. Minimal Receipt Example

```json
{
  "request_id": "exec-req-001",
  "brief_id": "council-poc-brief-001",
  "handoff_id": "handoff-20260315-004",
  "execution_status": "completed",
  "changed_files": [
    "docs/llm-assisted.md"
  ],
  "constraints_compliance": {
    "compliant": true,
    "note": "All edits stayed in allowed_files."
  },
  "summary": "Clarified llm_assisted steps and fallback checks.",
  "next_step_suggestion": "Owner can review wording and approve merge.",
  "generated_at": "2026-03-15T17:10:00+08:00"
}
```

This v0 receipt is intentionally small and manual-phase friendly.
