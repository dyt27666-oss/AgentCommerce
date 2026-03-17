# Council Bridge Handoff Contract v0

## 1. Purpose

This file locks the minimum contract for the current semi-manual handoff artifact.

It is:

1. a tiny v0 contract for manual bridge preparation
2. not an automation protocol
3. not proof of implemented auto execution

## 2. Field Invariants

Every handoff artifact must include:

1. `handoff_id`
2. `request_id`
3. `brief_id`
4. `approval_status`
5. `approved_by`
6. `approved_at`
7. `codex_ready_payload`
8. `validation_snapshot`
9. `notes`

Recommended `handoff_id` format (v0):

- `handoff-YYYYMMDD-###`

## 3. approval_status Values

Allowed values only:

1. `approved`
2. `needs_fix`
3. `rejected`

No extra status values in v0.

## 4. Nullability Rules

1. `approved_at` is always required and must be a non-empty timestamp string.
2. `codex_ready_payload`:
   - required and non-null for `approved`
   - must be `null` for `needs_fix` and `rejected`
3. `notes` is always required and should be a short audit sentence.

## 5. approved_by Rule

`approved_by` is owner-filled and must use a simple stable id:

1. lowercase letters / numbers / `_` / `-`
2. recommended length: 3-32
3. examples: `owner_manual`, `qa_reviewer_01`

## 6. validation_snapshot Minimum Structure

`validation_snapshot` must include:

1. `dry_run_status`
2. `dry_run_errors`

Rules:

1. if `dry_run_status == "valid"`, `dry_run_errors` must be `[]`
2. if `dry_run_status != "valid"`, `dry_run_errors` must be a non-empty string list

## 7. Per-Status Expectations

### approved

1. `validation_snapshot.dry_run_status == "valid"`
2. `validation_snapshot.dry_run_errors == []`
3. `codex_ready_payload` is present and scoped
4. constraints and allowed files are in Charter boundary

### needs_fix

1. input is recoverable in next manual correction round
2. `codex_ready_payload == null`
3. `notes` explains exactly what to fix

### rejected

1. input is not acceptable for this round
2. `codex_ready_payload == null`
3. `notes` states rejection reason clearly

## 8. Status Consistency Matrix (Quick Use)

| `approval_status` | `codex_ready_payload` | `notes` | `validation_snapshot` minimum | Executable by Codex | Owner next action |
|---|---|---|---|---|---|
| `approved` | must be non-null | required, short audit note | must contain `dry_run_status` + `dry_run_errors`; `dry_run_status = valid` and `dry_run_errors = []` | yes (manual phase input ready) | pass artifact to next manual bridge step |
| `needs_fix` | must be null | required, explain exact fix | must contain `dry_run_status` + `dry_run_errors`; use non-empty errors when available, otherwise note manual fix reason in `notes` | no | return to source input correction, regenerate dry-run |
| `rejected` | must be null | required, explain rejection reason | must contain `dry_run_status` + `dry_run_errors`; may be invalid or out-of-scope | no | stop this round, redefine scope/intention |

## 9. Owner-Filled Fields

These are always filled manually:

1. `handoff_id`
2. `approval_status`
3. `approved_by`
4. `approved_at`
5. `notes`

These are copied from dry-run result:

1. `request_id`
2. `brief_id`
3. `codex_ready_payload` (approved only)
4. `validation_snapshot`

## 10. Safe Assumptions For Codex (When Reading Handoff Artifact)

If an artifact is marked `approved`, Codex can safely assume:

1. request identity fields are present
2. payload scope was manually reviewed
3. payload constraints were manually reviewed
4. dry-run validation passed at handoff time

Codex should not assume:

1. auto execution is enabled
2. orchestration/retry exists
3. any HITL platform integration exists

## 11. Default Artifact Paths (Manual Round)

Use these default paths for consistency:

1. dry-run input: `artifacts/council_bridge_dry_run.json`
2. final handoff output: `artifacts/council_bridge_handoff.json`

## 12. Practical Note

This contract is intentionally small.

If a field is not needed for current semi-manual bridge, do not add it in v0.
